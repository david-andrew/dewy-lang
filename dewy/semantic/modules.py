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
from .analyze import bounds, initialization, representation
from .errors import user_error
from .prelude import prelude_files


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


_validated_prelude_modules: set[tuple[Path, int, str]] = set()


def _has_handle_union_member(type_: object) -> bool:
    """Whether a type stores an aggregate behind an arena handle: a union
    member that is an object, array, or recursive reference inside an object
    field (field cells have no prepared trees), anywhere in the type."""
    if isinstance(type_, ty.ObjectType):
        for field in type_.fields:
            if isinstance(field.type, ty.TypeOr) and any(
                isinstance(ty.unfold(item) if not isinstance(item, ty.NamedType) else item, (ty.ObjectType, ty.ArrayType, ty.NamedType))
                for item in field.type.items
            ):
                return True
            if _has_handle_union_member(field.type):
                return True
        return False
    if isinstance(type_, ty.TypeOr):
        return any(_has_handle_union_member(item) for item in type_.items)
    if isinstance(type_, ty.ArrayType):
        return _has_handle_union_member(type_.element)
    return False


def _has_runtime_array_field(object_type: ty.ObjectType) -> bool:
    for field in object_type.fields:
        if isinstance(field.type, ty.ArrayType) and field.type.length is None:
            return True
        if isinstance(field.type, ty.ObjectType) and _has_runtime_array_field(field.type):
            return True
    return False


class ModuleCompiler:
    """Load and check one reachable module graph."""

    def __init__(self, entry: SrcFile, target: str = 'x86_64'):
        self.entry = entry
        self.target = target
        self.type_system = ty.TypeSystem()
        builtins.apply_builtin_promote_rules(self.type_system)
        self.registry = sb.BindingRegistry()
        self.records: dict[Path, ModuleRecord] = {}
        self.order: list[ModuleRecord] = []
        self.stack: list[Path] = []
        self.prelude_bindings: dict[str, sb.Binding] = {}
        self.prelude_loaded = False
        self.prelude_paths: set[Path] = set()
        self.representation_notes: list[representation.RepresentationNote] = []
        self.finished_roots: dict[int, hir.Block] = {}

    def _ensure_prelude(self) -> None:
        if self.prelude_loaded:
            return
        self.prelude_loaded = True
        for path in prelude_files(self.target):
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
        if prelude:
            self.prelude_paths.add(path)
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

        block, no_prelude = check._parse_module(srcfile, target=self.target)
        if not prelude and not no_prelude:
            self._ensure_prelude()
        root, ctx = check._typecheck_module(
            srcfile,
            block=block,
            type_system=self.type_system,
            registry=self.registry,
            module_loader=self,
            target=self.target,
            prelude_bindings=(
                self.prelude_bindings
                if prelude or not no_prelude
                else None
            ),
        )
        # Bounds are validated per module so diagnostics point into the right
        # file (the merged program mixes prelude and user nodes). Prelude files
        # are validated once per process: their checked form never changes.
        validation_key = (path, path.stat().st_mtime_ns, self.target) if prelude else None
        if validation_key is None or validation_key not in _validated_prelude_modules:
            self._validate_and_select(root, srcfile, prelude_module=prelude, no_prelude=no_prelude)
            if validation_key is not None:
                _validated_prelude_modules.add(validation_key)
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
        importer_path = ctx.srcfile.path.resolve()
        return self.load(
            ctx.srcfile.path.parent / path_text,
            importer=ctx.srcfile,
            loc=loc,
            # A module imported by a prelude file is prelude too: pruned when
            # unused and named as part of the prelude.
            prelude=importer_path in self.prelude_paths,
        )

    @staticmethod
    def _module_slug(record: ModuleRecord) -> str:
        from .prelude import library

        raw = 'memory'
        if record.path is not None:
            raw = record.path.stem
            try:
                relative = record.path.resolve().relative_to(library.resolve())
                raw = '_'.join([*relative.parts[:-1], relative.stem])
            except ValueError:
                pass
        stem = re.sub(r'[^A-Za-z0-9_]+', '_', raw).strip('_')
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

    def _collect_referenced_binding_ids(self, value: Any, found: set[int]) -> None:
        if isinstance(value, hir.ExpressedIdentifier):
            if value.binding_id is not None:
                found.add(value.binding_id)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_referenced_binding_ids(item, found)
            return
        if isinstance(value, tuple):
            for item in value:
                self._collect_referenced_binding_ids(item, found)
            return
        if isinstance(value, dict):
            for item in value.values():
                self._collect_referenced_binding_ids(item, found)
            return
        if is_dataclass(value) and (
            isinstance(value, hir.AST)
            or isinstance(value, (hir.ObjectField, hir.Param))
        ):
            for field in fields(value):
                if field.name in {'loc', 'type', 'binding_id', 'name'}:
                    continue
                self._collect_referenced_binding_ids(getattr(value, field.name), found)

    # Prelude declarations the backend may call without a source reference.
    BACKEND_RUNTIME_HELPERS = frozenset({'_arena_alloc'})

    def _program_needs_arena(self, extra_roots: list[Any] = ()) -> bool:
        """Whether lowering will call the arena: a runtime-length array result,
        growth method, dictionary store, or `main(args)` in the program or in
        the prelude declarations it uses."""
        found = False

        def walk(value: Any) -> None:
            nonlocal found
            if found:
                return
            if isinstance(value, hir.TypeValue) and (
                ty.mentions_named_type(value.value) or _has_handle_union_member(value.value)
            ):
                # recursive members and aggregate union members of fields live behind arena handles
                found = True
                return
            if isinstance(value, (hir.ObjectLiteral, hir.Declare)) and _has_handle_union_member(
                value.type if isinstance(value, hir.ObjectLiteral) else (value.annotation or value.expr.type)
            ):
                found = True
                return
            if (
                isinstance(value, hir.RepresentationCast)
                and ty.optional_payload(value.type) == ty.StringType()
                and isinstance(value.expr.type, ty.ArrayType)
            ):
                # `bytes as string | undefined` builds the decoded string in the arena
                found = True
                return
            if isinstance(value, hir.FunctionLiteral):
                rettype = value.rettype
                if isinstance(rettype, ty.ArrayType) and rettype.length is None:
                    found = True
                    return
                if isinstance(rettype, ty.ObjectType) and _has_runtime_array_field(rettype):
                    # runtime-length array fields of an object result are arena-backed
                    found = True
                    return
            if isinstance(value, (hir.ArrayMethod, hir.DictStore, hir.DictRemove, hir.DictLookup, hir.DictContains, hir.DictEntries, hir.SetAlgebra, hir.DictView)):
                # Growth methods and dictionary stores relocate data into the arena.
                found = True
                return
            if (
                isinstance(value, hir.ObjectLiteral)
                and isinstance(value.type, ty.ObjectType)
                and _has_runtime_array_field(value.type)
            ):
                # runtime-length array fields are copied into the arena at
                # module startup and when the object is returned
                found = True
                return
            if (
                isinstance(value, hir.Declare)
                and value.name == 'main'
                and isinstance(value.expr, hir.FunctionLiteral)
                and value.expr.pos_or_kw_args
            ):
                # `main(args)` builds the argument strings in the arena.
                found = True
                return
            if isinstance(value, hir.AST):
                for field in fields(value):
                    walk(getattr(value, field.name))
            elif isinstance(value, hir.ObjectField):
                walk(value.value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)

        for record in self.order:
            if not record.prelude:
                walk(record.root)
        for root in extra_roots:
            walk(root)
        return found

    def _needed_prelude_binding_ids(self) -> set[int]:
        needed: set[int] = set()
        for record in self.order:
            if not record.prelude:
                self._collect_referenced_binding_ids(record.root, needed)

        prelude_items = [
            item
            for record in self.order
            if record.prelude
            for item in record.root.items
            if isinstance(item, hir.Declare) and item.binding_id is not None
        ]
        def close_over_references() -> None:
            changed = True
            while changed:
                changed = False
                for item in prelude_items:
                    if item.binding_id not in needed:
                        continue
                    before = len(needed)
                    self._collect_referenced_binding_ids(item.expr, needed)
                    changed = changed or len(needed) > before

        close_over_references()
        # Arena consumers may live in prelude code the program pulled in
        # (for example `read_bytes` growing its result), so include the
        # needed prelude declarations when deciding whether to keep the arena.
        needed_prelude = [item for item in prelude_items if item.binding_id in needed]
        if self._program_needs_arena(extra_roots=needed_prelude):
            for item in prelude_items:
                if item.name in self.BACKEND_RUNTIME_HELPERS and item.binding_id is not None:
                    needed.add(item.binding_id)
            close_over_references()
        return needed

    def _validate_and_select(
        self,
        root: hir.Block,
        srcfile: SrcFile,
        *,
        prelude_module: bool,
        no_prelude: bool,
    ) -> None:
        """Bounds validation, then big-integer representation for unproven `int` values.

        Prelude modules and `$no_prelude` programs keep the strict rule (an
        unproven word is an error) because the big-integer fallback lives in
        the prelude itself.
        """
        if prelude_module or no_prelude or 'BigInt' not in self.prelude_bindings:
            bounds.validate_bounds(root, self.registry, srcfile)
            return
        unfit: dict = {}
        bounds.validate_bounds(root, self.registry, srcfile, unfit)
        notes = representation.select_representations(root, self.registry, srcfile, self.prelude_bindings, unfit)
        self.representation_notes.extend(notes)

    def finish(self, entry: ModuleRecord) -> hir.Block:
        names = self._emitted_names(entry)
        needed_prelude = self._needed_prelude_binding_ids()
        items: list[hir.AST] = []
        for record in self.order:
            renamed = self._rename(record.root, names)
            assert isinstance(renamed, hir.Block)
            self.finished_roots[id(record)] = renamed
            for item in renamed.items:
                if isinstance(item, hir.Void):
                    continue
                if (
                    record.prelude
                    and isinstance(item, hir.Declare)
                    and item.binding_id is not None
                    and item.binding_id not in needed_prelude
                ):
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
        initialization.validate_initialization(root, self.registry, entry.srcfile)
        return root


def typecheck_program(
    srcfile: SrcFile,
    *,
    include_prelude: bool = True,
    target: str = 'x86_64',
) -> hir.Block:
    representation.last_notes.clear()
    compiler = ModuleCompiler(srcfile, target)
    if srcfile.path is not None:
        entry = compiler.load(srcfile.path, entry=True)
        merged = compiler.finish(entry)
        return merged if include_prelude else compiler.finished_roots[id(entry)]

    from . import check

    block, no_prelude = check._parse_module(srcfile, target=target)
    if not no_prelude:
        compiler._ensure_prelude()
    root, ctx = check._typecheck_module(
        srcfile,
        block=block,
        type_system=compiler.type_system,
        registry=compiler.registry,
        module_loader=compiler,
        target=target,
        prelude_bindings=compiler.prelude_bindings if not no_prelude else None,
    )
    compiler._validate_and_select(root, srcfile, prelude_module=False, no_prelude=no_prelude)
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
