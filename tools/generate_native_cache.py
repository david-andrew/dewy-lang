"""Generate typed native cache codecs from the checked snapshot declaration.

This development tool reads the hosted compiler's type model. Its output is
ordinary Dewy source committed beside the bootstrap compiler; native builds
must never invoke Python to serialize or restore a prelude.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dewy.reporting import SrcFile
from dewy.semantic import modules, ty
from dewy.semantic.hir_display import type_to_dewy


class Schema:
    def __init__(self, compiler, root, integer):
        self.integer = integer
        self.integer_key = self.key(integer)
        self.integer_members = {self.key(item) for item in integer.items}
        self.aliases = {}
        for module in compiler.order:
            if not module.path.is_relative_to(ROOT):
                continue
            for name, binding in module.exports.items():
                if binding.type_value is not None and not isinstance(binding.type_value, ty.GenericTypeAlias):
                    self.aliases.setdefault(self.key(binding.type_value), (module.path, name))
        self.types = {}
        self.visit(root)

    @staticmethod
    def key(value):
        return type_to_dewy(value)

    @staticmethod
    def field_type(field):
        return ty.RefinedType(field.type, field.refinement) if field.refinement else field.type

    def children(self, value):
        key = self.key(value)
        if key == self.integer_key or key in self.integer_members:
            return []
        if isinstance(value, ty.RefinedType):
            return [value.base]
        if isinstance(value, ty.TypeOr):
            # Optional BigInts are flattened unions in the hosted type model.
            # Keep their logical integer codec instead of serializing limbs
            # as an ordinary record whose field invariants would be lost.
            keys = {self.key(item) for item in value.items}
            if self.integer_members <= keys:
                return [self.integer, *(item for item in value.items if self.key(item) not in self.integer_members)]
            return value.items
        if isinstance(value, ty.ArrayType):
            return [value.element]
        if isinstance(value, ty.ObjectType):
            if value.brand == 'dict':
                return list(ty.dict_key_value(value))
            if value.brand == 'set':
                return [ty.set_element(value)]
            children = [self.field_type(field) for field in value.fields]
            if value.brand in ty.USER_BRANDS:
                children += [ty.USER_BRAND_TYPES[child] for child in sorted(ty.brand_children(value.brand))]
            return children
        if isinstance(value, (str, ty.StringType, ty.StringLiteralType, ty.IntegerLiteralType)):
            return []
        raise ValueError(f'No snapshot codec for {type(value).__name__}: {key}')

    def visit(self, value):
        key = self.key(value)
        if key in self.types:
            return
        self.types[key] = value
        for child in self.children(value):
            self.visit(child)

    def manifest(self):
        return [
            {'type': key, 'kind': type(value).__name__,
             'alias': [str(self.aliases[key][0].relative_to(ROOT)), self.aliases[key][1]] if key in self.aliases else None,
             'children': [self.key(child) for child in self.children(value)]}
            for key, value in self.types.items()
        ]


class Generator:
    def __init__(self, schema, output):
        self.schema = schema
        self.names = {key: f'Value{index}' for index, key in enumerate(schema.types)}
        paths = sorted({path for path, _ in schema.aliases.values()
                        if path.is_relative_to(ROOT / 'dewy/bootstrap') or path.is_relative_to(ROOT / 'library')})
        self.modules = {path: '_'.join(path.relative_to(ROOT).with_suffix('').parts[-2:]) for path in paths}
        self.output = output

    def name(self, value):
        return self.names[self.schema.key(value)]

    def expression(self, value):
        key = self.schema.key(value)
        if key == self.schema.integer_key:
            return 'bigint'
        if key in self.schema.integer_members and isinstance(value, ty.ObjectType):
            return 'bigint & ~0'
        if key in self.schema.aliases:
            path, name = self.schema.aliases[key]
            return f'{self.modules[path]}.{name}'
        if isinstance(value, str):
            return value
        if isinstance(value, (ty.StringLiteralType, ty.IntegerLiteralType)):
            return type_to_dewy(value)
        if isinstance(value, ty.TypeOr):
            return ' | '.join(self.name(item) for item in self.schema.children(value))
        if isinstance(value, ty.ArrayType):
            length = '' if value.length is None else f' length={value.length}'
            return f'array<{self.name(value.element)}{length}>'
        if isinstance(value, ty.ObjectType) and value.brand == 'dict':
            key, item = ty.dict_key_value(value)
            return f'dict<{self.name(key)} {self.name(item)}>'
        if isinstance(value, ty.ObjectType) and value.brand == 'set':
            return f'set<{self.name(ty.set_element(value))}>'
        if isinstance(value, ty.RefinedType) and key == 'addr':
            return 'addr'
        raise ValueError(f'No source type name for {key}')

    def variants(self, value):
        if isinstance(value, ty.TypeOr):
            return self.schema.children(value)
        if isinstance(value, ty.ObjectType) and value.brand in ty.USER_BRANDS:
            descendants = []
            def visit(brand):
                for child in sorted(ty.brand_children(brand)):
                    visit(child)
                    descendants.append(ty.USER_BRAND_TYPES[child])
            visit(value.brand)
            return descendants
        return []

    def encode_fields(self, value):
        return ['bytes.write_byte(0 @out)'] + [
            f'encode_{self.name(self.schema.field_type(field))}(value.{field.name} @out)' for field in value.fields]

    def decode_fields(self, value):
        lines = ['if bytes.read_byte(@input) not=? 0 or input.failed return miss(@input)']
        args = []
        for index, field in enumerate(value.fields):
            name = f'field_{index}'
            lines += [f'let {name}=decode_{self.name(self.schema.field_type(field))}(@input)',
                      f'if {name} is? CacheMiss return {name}']
            args.append(f'{field.name}={name}')
        lines.append(f'return {self.name(value)}[{" ".join(args)}]')
        return lines

    def bodies(self, value):
        key = self.schema.key(value)
        primitive = {'string': ('write_text', 'read_text'), 'bool': ('write_bool', 'read_bool'),
                     'int64': ('write_integer', 'read_integer'), 'uint64': ('write_word', 'read_word'),
                     'uint8': ('write_byte', 'read_byte'), 'addr': ('write_word', 'read_address')}
        nonzero = key in self.schema.integer_members and isinstance(value, ty.ObjectType)
        if key == self.schema.integer_key or nonzero:
            write, read = 'write_bigint', 'read_bigint'
        elif key in primitive:
            write, read = primitive[key]
        else:
            write = read = None
        if write:
            argument = 'value as uint64' if key == 'addr' else 'value'
            condition = 'input.failed or result =? 0' if nonzero else 'input.failed'
            return [f'bytes.{write}({argument} @out)'], [
                f'let result=bytes.{read}(@input)', f'if {condition} return miss(@input)', 'return result']
        if isinstance(value, (ty.StringLiteralType, ty.IntegerLiteralType)) or key == 'none':
            literal = type_to_dewy(value)
            return ['bytes.write_byte(0 @out)'], [
                'if bytes.read_byte(@input) not=? 0 or input.failed return miss(@input)', f'return {literal}']
        if isinstance(value, ty.ArrayType) or isinstance(value, ty.ObjectType) and value.brand in {'dict', 'set'}:
            dictionary = isinstance(value, ty.ObjectType) and value.brand == 'dict'
            array = isinstance(value, ty.ArrayType)
            if dictionary:
                k, item = ty.dict_key_value(value)
                loop = f'loop [key item] in value {{encode_{self.name(k)}(key @out) encode_{self.name(item)}(item @out)}}'
            else:
                item = value.element if array else ty.set_element(value)
                loop = f'loop item in value {{encode_{self.name(item)}(item @out)}}'
            encode = ['bytes.write_word(value.length as uint64 @out)', loop]
            decode = ['let count=bytes.read_count(@input)', 'if input.failed return miss(@input)',
                      f'let result:{self.name(value)}={"set[]" if not array and not dictionary else "[]"}']
            if array:
                if value.length is not None:
                    raise ValueError('Fixed array cache codec needs a checked builder')
                decode.append('result.reserve(count)')
            decode.append('loop index in 0.. and index <? count {')
            if dictionary:
                decode += [f'    let key=decode_{self.name(k)}(@input)', '    if key is? CacheMiss return key']
            decode += [f'    let item=decode_{self.name(item)}(@input)', '    if item is? CacheMiss return item']
            if dictionary:
                decode += ['    if key in? result return miss(@input)', '    result[key]=item']
            elif array:
                decode.append('    result.push(item)')
            else:
                decode += ['    if item in? result return miss(@input)', '    result.add(item)']
            decode += ['}', 'return result']
            return encode, decode
        variants = self.variants(value)
        if variants or isinstance(value, ty.TypeOr):
            encode, decode = [], ['let tag=bytes.read_word(@input)', 'if input.failed return miss(@input)']
            for index, variant in enumerate(variants):
                name = self.name(variant)
                encode.append(f'if value is? {name} {{bytes.write_word({index} @out) encode_{name}(value @out) return}}')
                decode.append(f'if tag =? {index} return decode_{name}(@input)')
            concrete = isinstance(value, ty.ObjectType) and value.brand not in ty.USER_ABSTRACT_BRANDS
            if concrete:
                encode += [f'bytes.write_word({len(variants)} @out)', *self.encode_fields(value)]
                decode += [f'if tag not=? {len(variants)} return miss(@input)', *self.decode_fields(value)]
            else:
                encode.append('out.failed=true')
                decode.append('return miss(@input)')
            return encode, decode
        if isinstance(value, ty.ObjectType):
            return self.encode_fields(value), self.decode_fields(value)
        raise ValueError(f'No codec body for {key}')

    def render(self):
        import os
        imports = ['import p"cache_bytes.dewy" as bytes']
        used = {self.schema.aliases[key][0] for key in self.schema.types if key in self.schema.aliases}
        for path in sorted(used):
            relative = os.path.relpath(path, self.output.parent)
            imports.append(f'import p"{relative}" as {self.modules[path]}')
        lines = ['# Generated by tools/generate_native_cache.py. Edit the declarations or generator.',
                 '# Dictionary/set tables are rebuilt; append-only arena order is preserved.', *imports, '',
                 'CacheMiss=type of any & []',
                 'miss=(@input:bytes.Reader):>CacheMiss=>{input.failed=true return CacheMiss[]}', '']
        for key, value in self.schema.types.items():
            lines.append(f'{self.names[key]}:type={self.expression(value)}')
        for key, value in self.schema.types.items():
            name = self.names[key]
            encode, decode = self.bodies(value)
            lines += ['', f'encode_{name}=(value:{name} @out:bytes.Writer):>void=>{{',
                      *('    '+line for line in encode), '}',
                      f'decode_{name}=(@input:bytes.Reader):>{name}|CacheMiss=>{{',
                      *('    '+line for line in decode), '}']
        lines += ['',
                  'encode=(value:Value0):>array<uint8>|CacheMiss=>{',
                  '    let output=bytes.Writer[]',
                  '    encode_Value0(value @output)',
                  '    if output.failed return CacheMiss[]',
                  '    return output.bytes', '}',
                  'decode=(value:array<uint8>):>Value0|CacheMiss=>{',
                  '    let input=bytes.Reader[value]',
                  '    let result=decode_Value0(@input)',
                  '    if result is? CacheMiss return result',
                  '    if not bytes.complete(input) return miss(@input)',
                  '    return result', '}']
        return '\n'.join(lines)+'\n'


def load_schema():
    with tempfile.TemporaryDirectory(prefix='dewy-cache-schema-') as directory:
        source = Path(directory) / 'schema.dewy'
        source.write_text(
            f'import p"{ROOT / "dewy/bootstrap/semantic/module_state.dewy"}" as state\n'
            'Snapshot:type=state.PreludeSnapshot\nCacheInteger:type=bigint\n')
        compiler = modules.ModuleCompiler(SrcFile.from_path(source))
        entry = compiler.load(source, entry=True)
        return Schema(compiler, entry.exports['Snapshot'].type_value,
                      entry.exports['CacheInteger'].type_value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, help='write the checked schema inventory')
    parser.add_argument('--output', type=Path, default=ROOT / 'dewy/bootstrap/semantic/cache_values.dewy')
    parser.add_argument('--check', action='store_true', help='verify committed output without changing it')
    args = parser.parse_args()
    schema = load_schema()
    if args.schema:
        args.schema.write_text(json.dumps(schema.manifest(), indent=2) + '\n')
    generated = Generator(schema, args.output).render()
    if args.check:
        if not args.output.exists() or args.output.read_text() != generated:
            parser.exit(1, f'{args.output} needs regeneration\n')
    else:
        args.output.write_text(generated)
    print(dict(Counter(type(value).__name__ for value in schema.types.values())))


if __name__ == '__main__':
    main()
