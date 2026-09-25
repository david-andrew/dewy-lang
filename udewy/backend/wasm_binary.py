"""WebAssembly text from the µDewy wasm32 backend to a binary module, without `wat2wasm`.

The wasm32 backend emits a closed WAT dialect (see ROADMAP "Direct binary
fast path"): module-level `type`, `import`, `global`, `table`, `func`,
`elem`, `data` and `export` forms, and function bodies as flat instruction
lists with labeled `block`/`loop`/`if`. This encodes exactly that dialect in
the order `wat2wasm` writes it, with minimal LEB128 sizes. Anything else is
an error, never a guess. Mirrors `udewy/bootstrap/backend/wasm_binary.udewy`.
"""
from __future__ import annotations

VALUE_TYPES = {'i32': 0x7F, 'i64': 0x7E, 'f32': 0x7D, 'f64': 0x7C}

# Opcodes without immediates.
SIMPLE = {
    'unreachable': 0x00, 'nop': 0x01, 'return': 0x0F, 'drop': 0x1A, 'select': 0x1B,
    'i32.eqz': 0x45, 'i32.eq': 0x46, 'i32.ne': 0x47, 'i32.lt_s': 0x48, 'i32.lt_u': 0x49, 'i32.gt_s': 0x4A,
    'i32.gt_u': 0x4B, 'i32.le_s': 0x4C, 'i32.le_u': 0x4D, 'i32.ge_s': 0x4E, 'i32.ge_u': 0x4F,
    'i64.eqz': 0x50, 'i64.eq': 0x51, 'i64.ne': 0x52, 'i64.lt_s': 0x53, 'i64.lt_u': 0x54, 'i64.gt_s': 0x55,
    'i64.gt_u': 0x56, 'i64.le_s': 0x57, 'i64.le_u': 0x58, 'i64.ge_s': 0x59, 'i64.ge_u': 0x5A,
    'i32.add': 0x6A, 'i32.sub': 0x6B, 'i32.mul': 0x6C, 'i32.and': 0x71, 'i32.or': 0x72, 'i32.xor': 0x73,
    'i64.add': 0x7C, 'i64.sub': 0x7D, 'i64.mul': 0x7E, 'i64.div_s': 0x7F, 'i64.div_u': 0x80, 'i64.rem_s': 0x81,
    'i64.rem_u': 0x82, 'i64.and': 0x83, 'i64.or': 0x84, 'i64.xor': 0x85, 'i64.shl': 0x86, 'i64.shr_s': 0x87,
    'i64.shr_u': 0x88,
    'i32.wrap_i64': 0xA7, 'i64.extend_i32_s': 0xAC, 'i64.extend_i32_u': 0xAD, 'i64.trunc_f32_s': 0xAE,
    'i64.trunc_f64_s': 0xB0, 'f32.convert_i64_s': 0xB4, 'f64.convert_i64_s': 0xB9,
    'i32.reinterpret_f32': 0xBC, 'i64.reinterpret_f64': 0xBD, 'f32.reinterpret_i32': 0xBE,
    'f64.reinterpret_i64': 0xBF,
}
# Loads and stores: opcode and natural alignment (log2 bytes).
MEMORY = {
    'i32.load': (0x28, 2), 'i64.load': (0x29, 3), 'i32.load8_s': (0x2C, 0), 'i32.load8_u': (0x2D, 0),
    'i64.load8_s': (0x30, 0), 'i64.load8_u': (0x31, 0), 'i64.load16_s': (0x32, 1), 'i64.load16_u': (0x33, 1),
    'i64.load32_s': (0x34, 2), 'i64.load32_u': (0x35, 2), 'i32.store': (0x36, 2), 'i64.store': (0x37, 3),
    'i32.store8': (0x3A, 0), 'i64.store8': (0x3C, 0), 'i64.store16': (0x3D, 1), 'i64.store32': (0x3E, 2),
}


class WatError(Exception):
    pass


def _uleb(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def _sleb(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if (value == 0 and not low & 0x40) or (value == -1 and low & 0x40):
            out.append(low)
            return bytes(out)
        out.append(low | 0x80)


def _vector(items: list[bytes]) -> bytes:
    return _uleb(len(items)) + b''.join(items)


def _name(text: str) -> bytes:
    data = text.encode()
    return _uleb(len(data)) + data


def _tokens(text: str) -> list[str]:
    """S-expression tokens: parentheses, quoted strings, and atoms."""
    tokens: list[str] = []
    at = 0
    length = len(text)
    while at < length:
        char = text[at]
        if char in ' \t\r\n':
            at += 1
        elif char == ';' and text.startswith(';;', at):
            end = text.find('\n', at)
            at = length if end < 0 else end
        elif char in '()':
            tokens.append(char)
            at += 1
        elif char == '"':
            end = at + 1
            while text[end] != '"':
                end += 2 if text[end] == '\\' else 1
            tokens.append(text[at:end + 1])
            at = end + 1
        else:
            end = at
            while end < length and text[end] not in ' \t\r\n()':
                end += 1
            tokens.append(text[at:end])
            at = end
    return tokens


def _tree(tokens: list[str]):
    """Nested lists for parenthesized forms; atoms stay strings."""
    stack: list[list] = [[]]
    for token in tokens:
        if token == '(':
            stack.append([])
        elif token == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(token)
    if len(stack) != 1:
        raise WatError('unbalanced parentheses')
    return stack[0]


def _string_bytes(token: str) -> bytes:
    body = token[1:-1]
    out = bytearray()
    at = 0
    escapes = {'n': 10, 't': 9, 'r': 13, '"': 34, "'": 39, '\\': 92}
    while at < len(body):
        char = body[at]
        if char != '\\':
            out.extend(char.encode())
            at += 1
            continue
        following = body[at + 1]
        if following in escapes:
            out.append(escapes[following])
            at += 2
        else:
            out.append(int(body[at + 1:at + 3], 16))
            at += 3
    return bytes(out)


def _integer(text: str) -> int:
    return int(text.replace('_', ''), 0)


class _Module:
    def __init__(self, forms: list):
        self.types: list[bytes] = []
        self.type_index: dict[bytes, int] = {}
        self.type_names: dict[str, int] = {}
        self.imports: list[bytes] = []
        self.function_names: dict[str, int] = {}
        self.imported_functions = 0
        self.functions: list[list] = []
        self.globals: list[bytes] = []
        self.global_names: dict[str, int] = {}
        self.tables: list[bytes] = []
        self.table_names: dict[str, int] = {}
        self.memories: list[bytes] = []
        self.memory_imported = False
        self.exports: list[bytes] = []
        self.elements: list[list] = []
        self.data: list[list] = []
        self.forms = forms

    def signature(self, items: list) -> int:
        """The type index of the `param`/`result` clauses in `items` (named params allowed)."""
        params: list[int] = []
        results: list[int] = []
        for item in items:
            # The signature ends at the first instruction: an `if (result ...)`
            # in a body is a block type, not the function's result.
            if isinstance(item, str):
                if item.startswith('$'):
                    continue
                break
            if not item or item[0] not in ('param', 'result', 'type', 'local', 'export'):
                break
            head = item[0]
            if head == 'param':
                types = [value for value in item[1:] if not value.startswith('$')]
                params.extend(VALUE_TYPES[value] for value in types)
            elif head == 'result':
                results.extend(VALUE_TYPES[value] for value in item[1:])
            elif head == 'type':
                return self.type_names[item[1]] if item[1].startswith('$') else _integer(item[1])
        return self.intern_type(params, results)

    def intern_type(self, params: list[int], results: list[int]) -> int:
        encoded = b'\x60' + _vector([bytes([value]) for value in params]) + _vector([bytes([value]) for value in results])
        index = self.type_index.get(encoded)
        if index is None:
            index = self.type_index[encoded] = len(self.types)
            self.types.append(encoded)
        return index

    def collect(self) -> None:
        # Explicit types first, then imports, then definitions, in text
        # order: the index spaces of a module.
        for form in self.forms:
            if form[0] == 'type':
                function = form[2]
                self.type_names[form[1]] = self.signature(function[1:])
        for form in self.forms:
            head = form[0]
            if head == 'import':
                module, field, description = _string_bytes(form[1]), _string_bytes(form[2]), form[3]
                kind = description[0]
                entry = _uleb(len(module)) + module + _uleb(len(field)) + field
                if kind == 'func':
                    name = description[1] if len(description) > 1 and description[1].startswith('$') else None
                    if name:
                        self.function_names[name] = self.imported_functions
                    self.imported_functions += 1
                    entry += b'\x00' + _uleb(self.signature(description[1:]))
                elif kind == 'memory':
                    limits = [value for value in description[1:] if not value.startswith('$')]
                    entry += b'\x02' + self.limits(limits)
                    self.memory_imported = True
                else:
                    raise WatError(f'unsupported import {kind}')
                self.imports.append(entry)
        for form in self.forms:
            head = form[0]
            if head == 'func':
                name = form[1] if len(form) > 1 and isinstance(form[1], str) and form[1].startswith('$') else None
                if name:
                    self.function_names[name] = self.imported_functions + len(self.functions)
                self.functions.append(form)
            elif head == 'global':
                name = form[1]
                self.global_names[name] = len(self.globals)
                kind = form[2]
                if isinstance(kind, list) and kind[0] == 'mut':
                    encoded = bytes([VALUE_TYPES[kind[1]], 1])
                else:
                    encoded = bytes([VALUE_TYPES[kind], 0])
                self.globals.append(encoded + self.constant(form[3]))
            elif head == 'table':
                name = form[1]
                self.table_names[name] = len(self.tables)
                limits = [value for value in form[2:] if value != 'funcref']
                self.tables.append(b'\x70' + self.limits(limits))
            elif head == 'memory':
                self.memories.append(self.limits([value for value in form[1:] if not value.startswith('$')]))
            elif head == 'elem':
                self.elements.append(form)
            elif head == 'data':
                self.data.append(form)
        for form in self.forms:
            if form[0] == 'func':
                self.signature(form[1:])
        for form in self.forms:
            if form[0] == 'export':
                name = _string_bytes(form[1])
                kind, target = form[2][0], form[2][1]
                if kind == 'func':
                    self.exports.append(_uleb(len(name)) + name + b'\x00' + _uleb(self.function_index(target)))
                elif kind == 'table':
                    self.exports.append(_uleb(len(name)) + name + b'\x01' + _uleb(self.table_names[target]))
                elif kind == 'memory':
                    self.exports.append(_uleb(len(name)) + name + b'\x02' + _uleb(0))
                elif kind == 'global':
                    self.exports.append(_uleb(len(name)) + name + b'\x03' + _uleb(self.global_names[target]))
                else:
                    raise WatError(f'unsupported export {kind}')

    @staticmethod
    def limits(values: list[str]) -> bytes:
        if len(values) == 1:
            return b'\x00' + _uleb(_integer(values[0]))
        return b'\x01' + _uleb(_integer(values[0])) + _uleb(_integer(values[1]))

    @staticmethod
    def constant(expression: list) -> bytes:
        opcode = {'i32.const': 0x41, 'i64.const': 0x42}[expression[0]]
        return bytes([opcode]) + _sleb(_signed(expression[1], 64 if opcode == 0x42 else 32)) + b'\x0b'

    def function_index(self, name: str) -> int:
        if name.startswith('$'):
            return self.function_names[name]
        return _integer(name)

    def code(self, form: list) -> bytes:
        locals_: dict[str, int] = {}
        local_types: list[int] = []
        param_count = 0
        at = 1
        if len(form) > 1 and isinstance(form[1], str):
            at = 2
        body: list = []
        for item in form[at:]:
            # Header clauses come before the first instruction; a later
            # `(type ...)` belongs to a call_indirect.
            if not body and isinstance(item, list) and item and item[0] in ('param', 'result', 'local', 'type', 'export'):
                if item[0] == 'param':
                    if len(item) > 2 and item[1].startswith('$'):
                        locals_[item[1]] = param_count
                        param_count += 1
                    else:
                        param_count += len(item) - 1
                elif item[0] == 'local':
                    if len(item) > 2 and item[1].startswith('$'):
                        locals_[item[1]] = param_count + len(local_types)
                        local_types.append(VALUE_TYPES[item[2]])
                    else:
                        for value in item[1:]:
                            local_types.append(VALUE_TYPES[value])
                continue
            body.append(item)
        # Locals are encoded as runs of one type.
        runs: list[bytes] = []
        index = 0
        while index < len(local_types):
            end = index
            while end < len(local_types) and local_types[end] == local_types[index]:
                end += 1
            runs.append(_uleb(end - index) + bytes([local_types[index]]))
            index = end
        out = bytearray(_vector(runs))
        self.instructions(body, locals_, out)
        out.append(0x0B)
        return _uleb(len(out)) + bytes(out)

    def instructions(self, items: list, locals_: dict[str, int], out: bytearray) -> None:
        labels: list[str | None] = []
        at = 0
        while at < len(items):
            item = items[at]
            at += 1
            if isinstance(item, list):
                if item and item[0] == 'type':
                    raise WatError('stray type clause')
                raise WatError(f'folded instructions are not supported: {item[:2]}')
            name = item

            def operand() -> str:
                nonlocal at
                if at >= len(items) or isinstance(items[at], list):
                    raise WatError(f'{name} needs an operand')
                value = items[at]
                at += 1
                return value

            def label_depth(target: str) -> int:
                if target.startswith('$'):
                    for depth, label in enumerate(reversed(labels)):
                        if label == target:
                            return depth
                    raise WatError(f'unknown label {target}')
                return _integer(target)

            if name in SIMPLE:
                out.append(SIMPLE[name])
            elif name in MEMORY:
                opcode, align = MEMORY[name]
                offset = 0
                while at < len(items) and isinstance(items[at], str) and items[at].startswith(('offset=', 'align=')):
                    key, _, value = items[at].partition('=')
                    if key == 'offset':
                        offset = _integer(value)
                    else:
                        align = _integer(value).bit_length() - 1
                    at += 1
                out.append(opcode)
                out += _uleb(align) + _uleb(offset)
            elif name in ('block', 'loop', 'if'):
                label = None
                if at < len(items) and isinstance(items[at], str) and items[at].startswith('$'):
                    label = items[at]
                    at += 1
                block_type = b'\x40'
                if at < len(items) and isinstance(items[at], list) and items[at] and items[at][0] == 'result':
                    block_type = bytes([VALUE_TYPES[items[at][1]]])
                    at += 1
                labels.append(label)
                out.append({'block': 0x02, 'loop': 0x03, 'if': 0x04}[name])
                out += block_type
            elif name == 'else':
                if at < len(items) and isinstance(items[at], str) and items[at].startswith('$'):
                    at += 1
                out.append(0x05)
            elif name == 'end':
                if at < len(items) and isinstance(items[at], str) and items[at].startswith('$'):
                    at += 1
                if not labels:
                    raise WatError('end without a block')
                labels.pop()
                out.append(0x0B)
            elif name in ('br', 'br_if'):
                out.append(0x0C if name == 'br' else 0x0D)
                out += _uleb(label_depth(operand()))
            elif name == 'call':
                out.append(0x10)
                out += _uleb(self.function_index(operand()))
            elif name == 'call_indirect':
                table = 0
                if at < len(items) and isinstance(items[at], str) and items[at].startswith('$'):
                    table = self.table_names[operand()]
                if at >= len(items) or not isinstance(items[at], list):
                    raise WatError('call_indirect needs a type')
                clauses = []
                while at < len(items) and isinstance(items[at], list) and items[at] and items[at][0] in ('type', 'param', 'result'):
                    clauses.append(items[at])
                    at += 1
                out.append(0x11)
                out += _uleb(self.signature(clauses)) + _uleb(table)
            elif name in ('local.get', 'local.set', 'local.tee'):
                target = operand()
                out.append({'local.get': 0x20, 'local.set': 0x21, 'local.tee': 0x22}[name])
                out += _uleb(locals_[target] if target.startswith('$') else _integer(target))
            elif name in ('global.get', 'global.set'):
                target = operand()
                out.append(0x23 if name == 'global.get' else 0x24)
                out += _uleb(self.global_names[target] if target.startswith('$') else _integer(target))
            elif name == 'i32.const':
                out.append(0x41)
                out += _sleb(_signed(operand(), 32))
            elif name == 'i64.const':
                out.append(0x42)
                out += _sleb(_signed(operand(), 64))
            elif name == 'memory.grow':
                out += b'\x40\x00'
            elif name == 'memory.size':
                out += b'\x3f\x00'
            else:
                raise WatError(f'unsupported instruction {name}')
        if labels:
            raise WatError('unterminated block')

    def element(self, form: list) -> bytes:
        offset = self.constant(form[1] if isinstance(form[1], list) else form[2])
        names = [value for value in form[2:] if isinstance(value, str) and value != 'func']
        return b'\x00' + offset + _vector([_uleb(self.function_index(name)) for name in names])

    def data_segment(self, form: list) -> bytes:
        offset = self.constant(form[1])
        content = b''.join(_string_bytes(token) for token in form[2:])
        return b'\x00' + offset + _uleb(len(content)) + content

    def encode(self) -> bytes:
        self.collect()
        out = bytearray(b'\x00asm\x01\x00\x00\x00')

        def section(identifier: int, payload: bytes) -> None:
            out.append(identifier)
            out.extend(_uleb(len(payload)))
            out.extend(payload)

        # Function signatures register their types before the type section
        # is written, so every section below is built first.
        function_types = [_uleb(self.signature(form[1:])) for form in self.functions]
        code = [self.code(form) for form in self.functions]
        elements = [self.element(form) for form in self.elements]
        data = [self.data_segment(form) for form in self.data]
        if self.types:
            section(1, _vector(self.types))
        if self.imports:
            section(2, _vector(self.imports))
        if function_types:
            section(3, _vector(function_types))
        if self.tables:
            section(4, _vector(self.tables))
        if self.memories:
            section(5, _vector(self.memories))
        if self.globals:
            section(6, _vector(self.globals))
        if self.exports:
            section(7, _vector(self.exports))
        if elements:
            section(9, _vector(elements))
        if code:
            section(10, _vector(code))
        if data:
            section(11, _vector(data))
        return bytes(out)


def _signed(text: str, bits: int) -> int:
    value = _integer(text)
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >= 1 << (bits - 1) else value


def assemble(text: str) -> bytes:
    """The binary module for WAT `text` from the µDewy wasm32 backend."""
    forms = _tree(_tokens(text))
    if len(forms) != 1 or not isinstance(forms[0], list) or forms[0][0] != 'module':
        raise WatError('expected one (module ...)')
    module = forms[0][1:]
    return _Module(module).encode()


if __name__ == '__main__':
    # `python -m udewy.backend.wasm_binary in.wat out.wasm`: the direct path
    # on its own, for comparing it with `wat2wasm`.
    import sys
    if len(sys.argv) != 3:
        sys.exit('usage: python -m udewy.backend.wasm_binary in.wat out.wasm')
    with open(sys.argv[1]) as source, open(sys.argv[2], 'wb') as output:
        output.write(assemble(source.read()))
