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
from ..reporting import Warning as RepWarning
from .analyze import bounds, initialization, representation
from .errors import user_error, UserError
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


class ModuleCompiler:
    """Load and check one reachable module graph."""

    def __init__(self, entry: SrcFile, target: str = 'x86_64', *, test: bool = False):
        self.entry = entry
        self.target = target
        self.test = test   # the entry module's `$test` functions get the generated runner as the program's entry
        self.type_system = ty.TypeSystem()
        builtins.apply_builtin_promote_rules(self.type_system)
        self.registry = sb.BindingRegistry()
        self.records: dict[Path, ModuleRecord] = {}
        self.prototype: check.ModuleDirectives | None = None
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
        if self._restore_checked_prelude():
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
        self._store_checked_prelude()

    # ---- the checked-prelude cache ----
    # Checking the prelude's modules costs ~0.85 s of a ~1 s warm compile,
    # and their checked form only changes when the library or the compiler
    # does. The compiler's state right after the prelude is loaded — the
    # type system, the binding registry, the module records (parse trees,
    # checked HIR, exports) — is pickled once under `__dewycache__/prelude/`,
    # keyed by the target and a digest of the library and compiler sources,
    # and later compiles start from it. `DEWY_NO_PRELUDE_CACHE=1` disables it.
    _PRELUDE_STATE_FIELDS = (
        'type_system', 'registry', 'records', 'order', 'prelude_bindings',
        'prelude_loaded', 'prelude_paths', 'representation_notes', 'finished_roots',
    )

    def _checked_prelude_path(self) -> Path | None:
        import hashlib
        import os
        if os.environ.get('DEWY_NO_PRELUDE_CACHE'):
            return None
        digest = hashlib.sha256()
        for path in prelude_files(self.target):
            digest.update(path.read_bytes())
        root = Path(__file__).resolve().parents[1]
        for path in sorted(root.rglob('*.py')):
            if '__pycache__' not in path.parts:
                digest.update(path.read_bytes())
        return Path('__dewycache__') / 'prelude' / f'{self.target}-{digest.hexdigest()[:24]}.pickle'

    def _restore_checked_prelude(self) -> bool:
        import pickle
        if self.records or self.registry.by_id:
            # a `$no_prelude` module was checked first and lives in this
            # registry: the prelude must be checked into it, not swapped in
            return False
        cache_path = self._checked_prelude_path()
        if cache_path is None or not cache_path.is_file():
            return False
        try:
            state, nominal_types, validated = pickle.loads(cache_path.read_bytes())
        except Exception:
            return False   # a stale or corrupt entry: check the prelude and rewrite it
        for name in self._PRELUDE_STATE_FIELDS:
            setattr(self, name, state[name])
        ty.USER_NOMINAL_TYPES.update(nominal_types)
        _validated_prelude_modules.update(validated)
        return True

    def _store_checked_prelude(self) -> None:
        import pickle
        if not all(record.prelude for record in self.records.values()):
            return   # a user module is already in this compiler's state
        cache_path = self._checked_prelude_path()
        if cache_path is None:
            return
        state = {name: getattr(self, name) for name in self._PRELUDE_STATE_FIELDS}
        validated = {key for key in _validated_prelude_modules if key[2] == self.target}
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_name(f'{cache_path.name}.{id(self)}.tmp')
            tmp.write_bytes(pickle.dumps((state, dict(ty.USER_NOMINAL_TYPES), validated), protocol=pickle.HIGHEST_PROTOCOL))
            tmp.replace(cache_path)
        except (OSError, pickle.PicklingError, TypeError, AttributeError):
            pass   # the cache is an optimization; a state that cannot be pickled is checked every time

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

        block, directives = check._parse_module(srcfile, target=self.target)
        no_prelude = directives.no_prelude
        if directives.prototype:
            if not entry:
                user_error(
                    srcfile,
                    '`$prototype` belongs in the entry module',
                    Pointer(span=Span(0, 0), message='an imported module cannot loosen the program-wide proofs'),
                )
            self.prototype = directives
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
            test=self.test and entry,
        )
        # Bounds are validated per module so diagnostics point into the right
        # file (the merged program mixes prelude and user nodes). Prelude files
        # are validated once per process: their checked form never changes.
        validation_key = (path, path.stat().st_mtime_ns, self.target) if prelude else None
        if validation_key is None or validation_key not in _validated_prelude_modules:
            # `ctx.srcfile`: in test mode the entry's source has the generated runner appended
            self._validate_and_select(root, ctx.srcfile, prelude_module=prelude, no_prelude=no_prelude, ctx=ctx)
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
    BACKEND_RUNTIME_HELPERS = frozenset({'_arena_alloc', '_arena_release', '_region_new', '_region_alloc', '_region_reset', '_region_release'})

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
        # The arena is always kept: string views, strings that escape into
        # arrays and objects, growth, decoded bytes and `main(args)` all
        # allocate from it, and the lowering falls back to *frame* storage
        # for views when it is absent — which dangles as soon as a view is
        # returned (`p"dir/x.dewy".stem` crashed in a program that happened
        # to touch nothing else in the arena). It is a few lines and maps
        # memory only on first use, so there is nothing to save by pruning it.
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
        ctx: object | None = None,
    ) -> None:
        """Bounds validation, then big-integer representation for unproven `int` values.

        Prelude modules and `$no_prelude` programs keep the strict rule (an
        unproven word is an error) because the big-integer fallback lives in
        the prelude itself.
        """
        from . import check

        prototype_sites: dict | None = None
        if self.prototype is not None and ctx is not None and not prelude_module and not no_prelude:
            prototype_sites = {}
        if prelude_module or no_prelude or 'BigInt' not in self.prelude_bindings:
            bounds.validate_bounds(root, self.registry, srcfile, target=self.target)
            return
        unfit: dict = {}
        bounds.validate_bounds(root, self.registry, srcfile, unfit, target=self.target, prototype_sites=prototype_sites)
        if prototype_sites:
            assert ctx is not None
            unhandled = check.insert_prototype_checks(root, prototype_sites, ctx=ctx)
            if unhandled:
                raise UserError(unhandled[0])   # no runtime check could stand in for this proof
            if self.prototype is not None and self.prototype.prototype_warnings:
                check.last_prototype_reports.extend(
                    RepWarning(
                        srcfile=report.srcfile,
                        title=f'prototype: {report.title}',
                        message=report.message,
                        pointer_messages=report.pointer_messages,
                        notes=[*report.notes, 'deferred to a runtime check by `$prototype`'],
                        hint=report.hint,
                    )
                    for _kind, report in prototype_sites.values()
                )
        notes = representation.select_representations(root, self.registry, srcfile, self.prelude_bindings, unfit)
        self.representation_notes.extend(notes)

    def finish(self, entry: ModuleRecord) -> hir.Block:
        from . import check
        check.validate_brand_matches()   # every module is loaded: the brands are a closed world
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
    test: bool = False,
) -> hir.Block:
    from . import check

    representation.last_notes.clear()
    check.last_prototype_reports.clear()
    check.pending_brand_matches.clear()
    bounds.last_cap_notes.clear()
    ty.reset_program_brands()   # the program's minted brands: a closed world per compile
    compiler = ModuleCompiler(srcfile, target, test=test)
    if srcfile.path is not None:
        entry = compiler.load(srcfile.path, entry=True)
        merged = compiler.finish(entry)
        return merged if include_prelude else compiler.finished_roots[id(entry)]

    from . import check

    check.last_prototype_reports.clear()

    block, _directives = check._parse_module(srcfile, target=target)
    no_prelude = _directives.no_prelude
    if _directives.prototype:
        compiler.prototype = _directives
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
        test=test,
    )
    compiler._validate_and_select(root, ctx.srcfile, prelude_module=False, no_prelude=no_prelude, ctx=ctx)
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
