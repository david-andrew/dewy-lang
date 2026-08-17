"""Typed, file-relative Dewy module loading."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass, replace
from os import PathLike
from pathlib import Path
from typing import Any

from ..reporting import Pointer, Span, SrcFile
from . import bindings as sb
from . import builtins, hir, ty
from .analyze import bounds, initialization
from .errors import user_error
from .prelude import PRELUDE_FILES


@dataclass
class ModuleRecord:
    path: Path | None
    srcfile: SrcFile
    # BindingRegistry keys syntax by identity, so parsed trees must outlive the graph.
    syntax: object
    root: hir.Block
    exports: dict[str, sb.Binding]
    index: int
    entry: bool = False
    prelude: bool = False


class ModuleCompiler:
    """Load and check one reachable module graph."""

    def __init__(self, entry: SrcFile):
        self.entry = entry
        self.type_system = ty.TypeSystem()
        builtins.apply_builtin_promote_rules(self.type_system)
        self.registry = sb.BindingRegistry()
        self.records: dict[Path, ModuleRecord] = {}
        self.order: list[ModuleRecord] = []
        self.stack: list[Path] = []
        self.prelude_bindings: dict[str, sb.Binding] = {}
        self.prelude_loaded = False
        self.finished_roots: dict[int, hir.Block] = {}

    def _ensure_prelude(self) -> None:
        if self.prelude_loaded:
            return
        self.prelude_loaded = True
        for path in PRELUDE_FILES:
            resolved = path.resolve()
            if resolved in self.stack:
                continue
            record = self.load(resolved, prelude=True)
            for name, binding in record.exports.items():
                if name in self.prelude_bindings:
                    raise ValueError(
                        f'prelude binding `{name}` is defined by more than one file'
                    )
                self.prelude_bindings[name] = binding

    def load(
        self,
        path: PathLike[str],
        *,
        importer: SrcFile | None = None,
        loc: Span | None = None,
        entry: bool = False,
        prelude: bool = False,
    ) -> ModuleRecord:
        path = Path(path).resolve()
        cached = self.records.get(path)
        if cached is not None:
            return cached
        if path in self.stack:
            cycle = [*self.stack[self.stack.index(path):], path]
            source = importer or self.entry
            user_error(
                source,
                'cyclic import',
                Pointer(
                    span=loc or Span(0, 0),
                    message='this import closes a cycle',
                ),
                hint=' -> '.join(item.name for item in cycle),
            )
        if not path.exists():
            source = importer or self.entry
            user_error(
                source,
                'import file not found',
                Pointer(
                    span=loc or Span(0, 0),
                    message=f'no file exists at `{path}`',
                ),
            )
        self.stack.append(path)
        srcfile = self.entry if entry else SrcFile.from_path(path)
        from . import check

        block, no_prelude = check._parse_module(srcfile)
        if not prelude and not no_prelude:
            self._ensure_prelude()
        root, ctx = check._typecheck_module(
            srcfile,
            block=block,
            type_system=self.type_system,
            registry=self.registry,
            module_loader=self,
            prelude_bindings=(
                self.prelude_bindings
                if prelude or not no_prelude
                else None
            ),
        )
        exports: dict[str, sb.Binding] = {}
        for item in root.items:
            if not isinstance(item, hir.Declare) or item.binding_id is None:
                continue
            exports[item.name] = self.registry.by_id[item.binding_id]
        index = sum(not record.prelude for record in self.order)
        record = ModuleRecord(
            path,
            srcfile,
            block,
            root,
            exports,
            index,
            entry,
            prelude,
        )
        self.records[path] = record
        self.order.append(record)
        self.stack.pop()
        return record

    def import_module(
        self,
        path_text: str,
        *,
        ctx: Any,
        loc: Span,
    ) -> ModuleRecord:
        if ctx.srcfile.path is None:
            user_error(
                ctx.srcfile,
                'imports require a file-backed source',
                Pointer(span=loc, message='this source has no containing directory'),
            )
        return self.load(
            ctx.srcfile.path.parent / path_text,
            importer=ctx.srcfile,
            loc=loc,
        )

    @staticmethod
    def _module_slug(record: ModuleRecord) -> str:
        stem = re.sub(
            r'[^A-Za-z0-9_]+',
            '_',
            record.path.stem if record.path is not None else 'memory',
        ).strip('_')
        if record.prelude:
            return f'prelude_{stem or "module"}'
        return f'{record.index + 1}_{stem or "module"}'

    def _emitted_names(self, entry: ModuleRecord) -> dict[int, str]:
        names: dict[int, str] = {}
        for record in self.order:
            slug = self._module_slug(record)
            for name, binding in record.exports.items():
                names[binding.id] = (
                    name
                    if record is entry
                    else f'__dewy_module_{slug}_{name}'
                )
        return names

    def _rename(self, value: Any, names: dict[int, str]) -> Any:
        if isinstance(value, hir.Declare):
            renamed = names.get(value.binding_id, value.name)
            return replace(
                value,
                name=renamed,
                expr=self._rename(value.expr, names),
            )
        if isinstance(value, hir.ExpressedIdentifier):
            return replace(value, name=names.get(value.binding_id, value.name))
        if isinstance(value, list):
            return [self._rename(item, names) for item in value]
        if isinstance(value, tuple):
            return tuple(self._rename(item, names) for item in value)
        if isinstance(value, dict):
            return {
                key: self._rename(item, names)
                for key, item in value.items()
            }
        if is_dataclass(value) and (
            isinstance(value, hir.AST)
            or isinstance(value, (hir.ObjectField, hir.Param))
        ):
            updates = {
                field.name: self._rename(getattr(value, field.name), names)
                for field in fields(value)
                if field.name not in {'loc', 'type', 'binding_id', 'name'}
            }
            return replace(value, **updates)
        return value

    def finish(self, entry: ModuleRecord) -> hir.Block:
        names = self._emitted_names(entry)
        items: list[hir.AST] = []
        for record in self.order:
            renamed = self._rename(record.root, names)
            assert isinstance(renamed, hir.Block)
            self.finished_roots[id(record)] = renamed
            for item in renamed.items:
                if isinstance(item, hir.Void):
                    continue
                items.append(item)
                if isinstance(item, hir.Declare) and item.binding_id is not None:
                    binding = self.registry.by_id[item.binding_id]
                    binding.declaration = item
                    if isinstance(item.expr, hir.FunctionLiteral):
                        binding.function = item.expr
        root = hir.Block(
            entry.root.loc,
            entry.root.type,
            items,
            True,
        )
        bounds.validate_bounds(root, self.registry, entry.srcfile)
        initialization.validate_initialization(root, self.registry, entry.srcfile)
        return root


def typecheck_program(
    srcfile: SrcFile,
    *,
    include_prelude: bool = True,
) -> hir.Block:
    compiler = ModuleCompiler(srcfile)
    if srcfile.path is not None:
        entry = compiler.load(srcfile.path, entry=True)
        merged = compiler.finish(entry)
        return merged if include_prelude else compiler.finished_roots[id(entry)]

    from . import check

    block, no_prelude = check._parse_module(srcfile)
    if not no_prelude:
        compiler._ensure_prelude()
    root, ctx = check._typecheck_module(
        srcfile,
        block=block,
        type_system=compiler.type_system,
        registry=compiler.registry,
        module_loader=compiler,
        prelude_bindings=compiler.prelude_bindings if not no_prelude else None,
    )
    exports = {
        item.name: compiler.registry.by_id[item.binding_id]
        for item in root.items
        if isinstance(item, hir.Declare) and item.binding_id is not None
    }
    entry = ModuleRecord(
        None,
        srcfile,
        block,
        root,
        exports,
        sum(not record.prelude for record in compiler.order),
        entry=True,
    )
    compiler.order.append(entry)
    merged = compiler.finish(entry)
    return merged if include_prelude else compiler.finished_roots[id(entry)]
