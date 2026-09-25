"""Typed, file-relative Dewy module loading."""

from __future__ import annotations

import re
from dataclasses import dataclass, is_dataclass
from ..utils import dataclass_replace as replace
from ..parser.t1 import normalize_identifier
from os import PathLike
from pathlib import Path
from typing import Any

from ..reporting import Pointer, Span, SrcFile
from ..utils import dataclass_fields as fields
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
    explicit_copies: bool = False


_PRELUDE_CACHE_VERSION = 5


class _ResidentPrelude:
    """The checked prelude kept live in the process, loaded from its pickle once.

    Restoring the prelude means building some hundred thousand objects, which
    was two thirds of a small compile; a compile that starts from the same
    objects instead pays nothing. A compile *adds* to that state — bindings,
    module records, named types, generic instances, the instance names it
    writes into a generic's defining scope — and ``rollback`` takes those
    additions back before the next compile starts (the prelude's own bindings
    get their `declaration`/`function` re-pointed at each compile's renamed
    copy, which is the same value every time). `DEWY_NO_RESIDENT_PRELUDE=1`
    reloads the pickle for every compile, the old way.
    """

    def __init__(self, state: dict, registries: dict, cache_path: Path) -> None:
        self.state = state
        self.registries = registries
        stat = cache_path.stat()
        self.stamp = (stat.st_size, stat.st_mtime_ns)   # the entry as loaded: a rewritten (or corrupted) file is loaded again
        registry = state['registry']
        self.next_id = registry.next_id
        self.next_route_id = registry.next_route_id
        self.records = dict(state['records'])
        self.included_files = dict(state['included_files'])
        self.input_resolutions = dict(state['input_resolutions'])
        self.order = list(state['order'])
        self.notes = list(state['representation_notes'])
        system = state['type_system']
        self.named_types = set(system._named_types)
        self.type_parents = {name: set(parents) for name, parents in system._type_parents.items()}
        self.type_children = {name: set(children) for name, children in system._type_children.items()}
        self.promote_rules = dict(system._promote_rules)
        # every generic the prelude declares: its instances so far, and the
        # scope of its defining module (an instantiation writes its name there)
        self.generics: list[tuple[hir.GenericSource, dict, dict, dict, dict]] = []
        seen: set[int] = set()
        for record in self.order:
            for source in _generic_sources(record.root, seen):
                context = source.context
                self.generics.append((
                    source,
                    dict(source.instances),
                    dict(context.declarations.maps[0]),
                    dict(context.binding_scopes.maps[0]),
                    dict(context.local_place_roots),
                ))

    def rollback(self) -> None:
        state = self.state
        registry = state['registry']
        registry.rollback_allocations(self.next_id, self.next_route_id)
        state['records'].clear()
        state['records'].update(self.records)
        state['included_files'].clear()
        state['included_files'].update(self.included_files)
        state['input_resolutions'].clear()
        state['input_resolutions'].update(self.input_resolutions)
        state['order'][:] = self.order
        state['representation_notes'][:] = self.notes
        state['finished_roots'].clear()
        system = state['type_system']
        system._named_types.clear()
        system._named_types.update(self.named_types)
        system._type_parents.clear()
        system._type_parents.update({name: set(parents) for name, parents in self.type_parents.items()})
        system._type_children.clear()
        system._type_children.update({name: set(children) for name, children in self.type_children.items()})
        system._nominal_ancestors.clear()
        system._promote_rules.clear()
        system._promote_rules.update(self.promote_rules)
        for source, instances, declarations, scopes, local_places in self.generics:
            source.instances.clear()
            source.instances.update(instances)
            source.context.local_place_roots.clear()
            source.context.local_place_roots.update(local_places)
            source.context.declarations.maps[0].clear()
            source.context.declarations.maps[0].update(declarations)
            source.context.binding_scopes.maps[0].clear()
            source.context.binding_scopes.maps[0].update(scopes)


def _generic_sources(value: object, seen: set[int]) -> list[hir.GenericSource]:
    """Every `GenericFunction`'s source under a checked tree."""
    found: list[hir.GenericSource] = []
    if id(value) in seen:
        return found
    if isinstance(value, hir.GenericFunction):
        seen.add(id(value))
        found.append(value.source)
        return found
    if is_dataclass(value) and not isinstance(value, type) and isinstance(value, hir.AST):
        seen.add(id(value))
        for field_ in fields(value):
            found.extend(_generic_sources(getattr(value, field_.name), seen))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_generic_sources(item, seen))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_generic_sources(item, seen))
    return found


_resident_preludes: dict[Path, _ResidentPrelude] = {}


class ModuleCompiler:
    """Load and check one reachable module graph."""

    def __init__(self, entry: SrcFile, target: str = 'x86_64', *, test: bool = False, debug: bool = False, debug_variables: bool = True):
        self.entry = entry
        self.target = target
        self.test = test   # the entry module's `$test` functions get the generated runner as the program's entry
        self.debug_variables = debug_variables
        self.debug = debug   # user modules get the debugger's formatters
        self.type_system = ty.TypeSystem()
        builtins.apply_builtin_promote_rules(self.type_system)
        self.registry = sb.BindingRegistry()
        self.records: dict[Path, ModuleRecord] = {}
        self.included_files: dict[Path, bytes] = {}
        self.input_resolutions: dict[Path, Path] = {}
        self.prototype: check.ModuleDirectives | None = None
        self.order: list[ModuleRecord] = []
        self.stack: list[Path] = []
        self.prelude_bindings: dict[str, sb.Binding] = {}
        self.prelude_loaded = False
        self.prelude_paths: set[Path] = set()
        self.representation_notes: list[representation.RepresentationNote] = []
        self.finished_roots: dict[int, hir.Block] = {}
        self.lifecycle_hooks: dict[int, tuple[hir.Declare, SrcFile]] | None = None

    def _ensure_prelude(self) -> None:
        from . import check
        if self.prelude_loaded:
            return
        if self._restore_checked_prelude():
            check.reset_synthesized_names()   # the program's names start where they would after a fresh check
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
        check.reset_synthesized_names()   # the prelude's dictionary and key names are its own; the program's start over

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
        'included_files', 'input_resolutions',
    )

    def _checked_prelude_path(self) -> Path | None:
        import hashlib
        import os
        from .prelude import library
        if os.environ.get('DEWY_NO_PRELUDE_CACHE'):
            return None
        digest = hashlib.sha256()
        digest.update(f'checked-prelude-{_PRELUDE_CACHE_VERSION}:{self.target}\0'.encode())
        digest.update(str(library.resolve()).encode() + b'\0')
        for path in prelude_files(self.target):
            digest.update(str(path.resolve()).encode() + b'\0')
            digest.update(path.read_bytes())
        root = Path(__file__).resolve().parents[1]
        for path in sorted(root.rglob('*.py')):
            if '__pycache__' not in path.parts:
                digest.update(path.read_bytes())
        return Path('__dewycache__') / 'prelude' / f'{self.target}-{digest.hexdigest()[:24]}.pickle'

    @staticmethod
    def _prelude_inputs_match(records: dict[Path, ModuleRecord], included: dict[Path, bytes], resolutions: dict[Path, Path]) -> bool:
        # Include imports of the prelude, not only the initial file list used
        # in the cache key. Equal sizes and timestamps do not prove equality.
        try:
            if not records or not all(
                record.prelude and path == record.path
                and path.read_text() == record.srcfile.body
                for path, record in records.items()
            ):
                return False
            # Record reads when checking performs them, including inputs
            # whose HIR later disappears through constant folding. Retain
            # path resolution too: a redirected source symlink can change
            # file-relative imports even when its own contents are identical.
            return (all(path.resolve() == target for path, target in resolutions.items())
                    and all(path.read_bytes() == content for path, content in included.items()))
        except (OSError, UnicodeError):
            return False

    def _restore_checked_prelude(self) -> bool:
        import os
        import pickle
        if self.records or self.registry.by_id:
            # a `$no_prelude` module was checked first and lives in this
            # registry: the prelude must be checked into it, not swapped in
            return False
        cache_path = self._checked_prelude_path()
        if cache_path is None or not cache_path.is_file():
            return False
        resident = _resident_preludes.get(cache_path)
        stat = cache_path.stat()
        if resident is not None and resident.stamp != (stat.st_size, stat.st_mtime_ns):
            del _resident_preludes[cache_path]
            resident = None
        if resident is not None:
            if not self._prelude_inputs_match(resident.records, resident.included_files, resident.input_resolutions):
                del _resident_preludes[cache_path]
                return False
            # the state a compile in this process already loaded: what that
            # compile added is rolled back, and the same objects serve again
            resident.rollback()
            state, nominal_types = resident.state, resident.registries
        else:
            try:
                version, state, nominal_types = pickle.loads(cache_path.read_bytes())
                if version != _PRELUDE_CACHE_VERSION or not self._prelude_inputs_match(state['records'], state['included_files'], state['input_resolutions']):
                    return False
            except Exception:
                return False   # a stale or corrupt entry: check the prelude and rewrite it
            if not (isinstance(nominal_types, dict) and 'nominal' in nominal_types and 'brands' in nominal_types):
                return False   # an entry from before the registries were stored: check the prelude and rewrite it
            if not os.environ.get('DEWY_NO_RESIDENT_PRELUDE'):
                _resident_preludes.clear()   # one prelude per process (a different target or a changed library replaces it)
                _resident_preludes[cache_path] = _ResidentPrelude(state, nominal_types, cache_path)
        for name in self._PRELUDE_STATE_FIELDS:
            setattr(self, name, state[name])
        # the brand registries a minted type lives in (`let Warning = type of Report & […]` in the prelude)
        ty.USER_NOMINAL_TYPES.update(nominal_types['nominal'])
        ty.USER_BRANDS.update(nominal_types['brands'])
        ty.USER_BRAND_PARENTS.update(nominal_types['parents'])
        ty.USER_BRAND_TYPES.update(nominal_types['types'])
        ty.USER_ABSTRACT_BRANDS.update(nominal_types['abstract'])
        return True

    def _store_checked_prelude(self) -> None:
        import os
        import pickle
        if not all(record.prelude for record in self.records.values()):
            return   # a user module is already in this compiler's state
        cache_path = self._checked_prelude_path()
        if cache_path is None:
            return
        state = {name: getattr(self, name) for name in self._PRELUDE_STATE_FIELDS}
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_name(f'{cache_path.name}.{os.getpid()}.{id(self)}.tmp')   # per process: parallel test workers store the same entry at once
            registries = {
                'nominal': dict(ty.USER_NOMINAL_TYPES), 'brands': set(ty.USER_BRANDS), 'parents': dict(ty.USER_BRAND_PARENTS),
                'types': dict(ty.USER_BRAND_TYPES), 'abstract': set(ty.USER_ABSTRACT_BRANDS),
            }
            tmp.write_bytes(pickle.dumps((_PRELUDE_CACHE_VERSION, state, registries), protocol=pickle.HIGHEST_PROTOCOL))
            tmp.replace(cache_path)
        except (OSError, pickle.PicklingError, TypeError, AttributeError):
            pass   # the cache is an optimization; a state that cannot be pickled is checked every time

    def record_binary_input(self, requested: Path, path: Path, content: bytes) -> None:
        self.input_resolutions[requested.absolute()] = path.resolve()
        self.included_files[path] = content

    def load(
        self,
        path: PathLike[str],
        *,
        importer: SrcFile | None = None,
        loc: Span | None = None,
        entry: bool = False,
        prelude: bool = False,
    ) -> ModuleRecord:
        requested = Path(path).absolute()
        path = requested.resolve()
        if prelude:
            self.input_resolutions[requested] = path
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
            debug_variables=self.debug_variables,
            debug_formatters=self.debug and not prelude and not no_prelude,   # the prelude is cached and never debugged
            prelude_module=prelude,
            prelude_bindings=(
                self.prelude_bindings
                if prelude or not no_prelude
                else None
            ),
            test=self.test and entry,
        )
        # A restored prelude already retains its validated HIR. Any module
        # actually checked here needs validation too: unchanged source can
        # acquire different facts from a changed dependency. A separate cache
        # keyed only by this file's timestamp would reuse stale proofs.
        # `ctx.srcfile` includes the generated runner in entry test mode.
        root = self._validate_and_select(root, ctx.srcfile, prelude_module=prelude, no_prelude=no_prelude, ctx=ctx)
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
            explicit_copies=directives.explicit_copies,
        )
        self.records[path] = record
        self.order.append(record)
        self.stack.pop()
        return record

    def import_library(self, name: str, *, ctx: Any, loc: Span) -> ModuleRecord:
        """`import units` / `from linux.system import …`: a module of the library by
        name (a subfolder is a dotted prefix). Looked up in the compiler's library
        directory; a project-local library directory is the natural first entry
        of this search when vendoring wants it."""
        from .prelude import library

        for root in (library,):
            candidate = root / f'{name}.dewy'
            if candidate.is_file():
                importer = ctx.srcfile.path.resolve() if ctx.srcfile.path is not None else None
                return self.load(candidate, importer=ctx.srcfile, loc=loc, prelude=importer in self.prelude_paths)
        available = sorted(
            str(path.relative_to(library).with_suffix('')).replace('/', '.')
            for path in library.rglob('*.dewy')
            if 'old' not in path.parts and not path.stem.startswith('_')
        )
        user_error(
            ctx.srcfile,
            f'no library module `{name.replace("/", ".")}`',
            Pointer(span=loc, message='not a module of the library'),
            hint='library modules: ' + ', '.join(available),
        )

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
            expr = self._rename(value.expr, names)
            if renamed == value.name and expr is value.expr:
                return value
            return replace(
                value,
                name=renamed,
                expr=expr,
            )
        if isinstance(value, hir.ExpressedIdentifier):
            name = names.get(value.binding_id, value.name)
            return value if name == value.name else replace(value, name=name)
        if isinstance(value, list):
            items = [self._rename(item, names) for item in value]
            return items if any(new is not old for new, old in zip(items, value)) else value
        if isinstance(value, tuple):
            items = tuple(self._rename(item, names) for item in value)
            return items if any(new is not old for new, old in zip(items, value)) else value
        if isinstance(value, dict):
            items = {
                key: self._rename(item, names)
                for key, item in value.items()
            }
            return items if any(items[key] is not value[key] for key in value) else value
        if is_dataclass(value) and (
            isinstance(value, hir.AST)
            or isinstance(value, (hir.ObjectField, hir.Param))
        ):
            updates = {
                name: self._rename(getattr(value, name), names)
                for name in hir.child_fields(type(value))
            }
            return replace(value, **updates) if any(new is not getattr(value, name) for name, new in updates.items()) else value
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
            for name in hir.child_fields(type(value)):
                self._collect_referenced_binding_ids(getattr(value, name), found)

    # Prelude declarations the backend may call without a source reference,
    # by their bound names (`_arena_alloc_16` is the identifier `_arena_alloc₁₆`).
    BACKEND_RUNTIME_HELPERS = frozenset(normalize_identifier(name) for name in {'_arena_alloc', '_arena_release', '_arena_alloc_8', '_arena_alloc_16', '_arena_alloc_32', '_arena_alloc_64', '_arena_alloc_128', '_arena_alloc_256', '_arena_release_8', '_arena_release_16', '_arena_release_32', '_arena_release_64', '_arena_release_128', '_arena_release_256', '_arena_note_copy', '_region_new', '_region_alloc', '_region_reset', '_region_release', '_union_tree'})

    def _needed_runtime_binding_ids(self, entry: ModuleRecord) -> set[int]:
        """Follow runtime references before renaming and lowering imports.

        The entry's declarations remain available to HIR tools, including
        compilation of a module with no main. Imported function declarations
        do not execute at startup; keep only their referenced dependency graph.
        Non-function user initializers always remain, in module load order.
        Callback values and lazy defaults contribute ordinary HIR references.
        """
        needed: set[int] = set()
        for record in self.order:
            # Ownership operations are implicit call edges. Until the
            # ownership pass materializes them, keep their declarations so
            # runtime validation cannot mistake an imported resource for an
            # ordinary memberwise value after pruning its unreferenced hook.
            for item in record.root.items:
                if (isinstance(item, hir.Declare) and item.binding_id is not None
                        and isinstance(item.expr, hir.FunctionLiteral)
                        and item.expr.lifecycle is not None):
                    needed.add(item.binding_id)
            if record is entry:
                self._collect_referenced_binding_ids(record.root, needed)
            elif not record.prelude:
                for item in record.root.items:
                    if not self._imported_function(item):
                        self._collect_referenced_binding_ids(item, needed)

        # Debugger formatters are invoked externally, not by source calls.
        if self.debug:
            for record in self.order:
                for item in record.root.items:
                    if isinstance(item, hir.Declare) and item.name.startswith('__dewy_debug_show_') and item.binding_id is not None:
                        needed.add(item.binding_id)

        prelude_items = [
            item
            for record in self.order
            if record.prelude
            for item in record.root.items
            if isinstance(item, hir.Declare) and item.binding_id is not None
        ]
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
        # Reachability is a graph walk. A dependency already visited need not
        # have its whole function body scanned again when another root grows.
        declarations = {
            item.binding_id: item
            for record in self.order
            for item in record.root.items
            if isinstance(item, hir.Declare) and item.binding_id is not None
        }
        pending = list(needed)
        visited: set[int] = set()
        while pending:
            binding_id = pending.pop()
            if binding_id in visited:
                continue
            visited.add(binding_id)
            item = declarations.get(binding_id)
            if item is not None:
                references: set[int] = set()
                self._collect_referenced_binding_ids(item.expr, references)
                needed.update(references)
                pending.extend(references - visited)
        return needed

    @staticmethod
    def _imported_function(item: hir.AST) -> bool:
        return (isinstance(item, hir.Declare) and item.binding_id is not None
                and isinstance(item.expr, (hir.FunctionLiteral, hir.OverloadedFunction)))

    @staticmethod
    def _hooks(root: hir.Block):
        return (item for item in root.items if isinstance(item, hir.Declare)
                and isinstance(item.expr, hir.FunctionLiteral) and item.expr.lifecycle is not None)

    def _materialize_ownership(self, root: hir.Block, source: SrcFile) -> hir.Block:
        from . import lifecycle_runtime
        # Restored prelude records may already contain prepared hooks. Build
        # their small inventory once; ordinary modules must not repeatedly
        # copy or walk the complete imported/prelude graph for this pass.
        if self.lifecycle_hooks is None:
            self.lifecycle_hooks = {item.binding_id: (item, record.srcfile)
                                    for record in self.order for item in self._hooks(record.root)}
        if not self.lifecycle_hooks and not any(self._hooks(root)):
            return root
        # Imported hooks supply call identities, but only this module's
        # functions (including nested literals/specializations) are rewritten.
        prefix = [item for item, _ in self.lifecycle_hooks.values()]
        sources = [source for _, source in self.lifecycle_hooks.values()]
        combined = hir.Program(root.loc, root.type, [*prefix, *root.items], root.scoped,
                               (*sources, *(source for _ in root.items)), (),
                               binding_registry=self.registry, target=self.target)
        selected = {id(node) for node in hir.walk(root) if isinstance(node, hir.FunctionLiteral)}
        effect_context = hir.Block(root.loc, root.type,
                                   [*(record.root for record in self.order), combined], False)
        prepared = lifecycle_runtime.prepare(combined, source, selected=selected, validate=False,
                                             effect_context=effect_context)
        return replace(root, items=prepared.items[len(prefix):])

    def _validate_and_select(self, root: hir.Block, srcfile: SrcFile, *,
                             prelude_module: bool, no_prelude: bool,
                             ctx: object | None = None) -> hir.Block:
        from .errors import NotImplementedYet
        options = dict(prelude_module=prelude_module, no_prelude=no_prelude, ctx=ctx)
        from . import local_places
        root = local_places.prepare(root, self.registry, srcfile)
        try:
            # Both file and in-memory modules share the native ordering:
            # insert implicit operations before proving facts about effects.
            prepared = self._materialize_ownership(root, srcfile)
        except NotImplementedYet:
            # Unsupported ownership retains ordinary source fact diagnostics.
            self._prove_and_select_representations(root, srcfile, **options)
            raise
        self._prove_and_select_representations(prepared, srcfile, **options)
        assert self.lifecycle_hooks is not None
        self.lifecycle_hooks.update((item.binding_id, (item, srcfile)) for item in self._hooks(prepared))
        return prepared

    def _prove_and_select_representations(
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

        # Imported bodies are already checked, but are not children of this
        # module. Borrow proofs must resolve their calls in the loaded graph.
        effect_context = hir.Block(root.loc, root.type,
                                   [*(record.root for record in self.order), root], False)
        prototype_sites: dict | None = None
        if self.prototype is not None and ctx is not None and not prelude_module and not no_prelude:
            prototype_sites = {}
        if prelude_module or no_prelude or 'BigInt' not in self.prelude_bindings:
            bounds.validate_bounds(root, self.registry, srcfile, target=self.target, effect_context=effect_context)
            return
        unfit: dict = {}
        bounds.validate_bounds(root, self.registry, srcfile, unfit, target=self.target, prototype_sites=prototype_sites, effect_context=effect_context)
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
        from . import check, unsafe_audit
        from .analyze import place_contracts, public_effects, storage_lifetimes
        # Parent-place safety needs imported helper bodies and must also
        # check unused source functions before runtime reachability pruning.
        source_items = [record.root for record in self.order]
        ownership_registry = self.registry if any(
            isinstance(item, hir.Declare) and isinstance(item.expr, hir.FunctionLiteral)
            and item.expr.lifecycle is not None for record in self.order for item in record.root.items
        ) else None
        source_graph = hir.Program(
            entry.root.loc, entry.root.type, source_items, True,
            tuple(record.srcfile for record in self.order), (),
        )
        place_contracts.validate(source_graph, self.registry, entry.srcfile)
        storage_lifetimes.validate(source_graph, self.registry, entry.srcfile)
        # Imported direct callees participate in the same inference as local
        # helpers. Every module's bounds pass has certified iterator storage
        # by now; a syntactic `guarded` hint alone is never allocation proof.
        public_effects.validate(source_graph, self.registry, entry.srcfile)
        # Snapshot source assumptions before pruning unused imports or
        # lowering. Warm prelude records carry the same checked HIR.
        if any('$unsafe_assume' in record.srcfile.body for record in self.order):
            unsafe_audit.last_entries[:] = [entry for record in self.order for entry in unsafe_audit.collect(record.root, record.srcfile)]
        check.validate_brand_matches()   # every module is loaded: the brands are a closed world
        names = self._emitted_names(entry)
        needed = self._needed_runtime_binding_ids(entry)
        items: list[hir.AST] = []
        item_sources: list[SrcFile] = []
        for record in self.order:
            # Filter before the recursive rename: discarded functions should
            # cost neither rebuilt HIR nor downstream lowering/analysis work.
            kept = [item for item in record.root.items if not (
                record is not entry
                and isinstance(item, hir.Declare)
                and item.binding_id is not None
                and item.binding_id not in needed
                and (record.prelude or self._imported_function(item))
            )]
            renamed = self._rename(replace(record.root, items=kept), names)
            assert isinstance(renamed, hir.Block)
            self.finished_roots[id(record)] = hir.Program(
                renamed.loc, renamed.type, renamed.items, renamed.scoped,
                tuple(record.srcfile for _ in renamed.items),
                (record.srcfile,) if record.explicit_copies else (),
                binding_registry=ownership_registry, target=self.target, ownership_prepared=True,
            )
            for item in renamed.items:
                if isinstance(item, hir.Void):
                    continue
                items.append(item)
                item_sources.append(record.srcfile)
                if isinstance(item, hir.Declare) and item.binding_id is not None:
                    binding = self.registry.by_id[item.binding_id]
                    binding.declaration = item
                    if isinstance(item.expr, hir.FunctionLiteral):
                        binding.function = item.expr
        root = hir.Program(
            entry.root.loc,
            entry.root.type,
            items,
            True,
            tuple(item_sources),
            tuple(record.srcfile for record in self.order if record.explicit_copies),
            binding_registry=ownership_registry, target=self.target, ownership_prepared=True,
        )
        initialization.validate_initialization(root, self.registry, entry.srcfile)
        return root


def typecheck_program(
    srcfile: SrcFile,
    *,
    include_prelude: bool = True,
    target: str = 'x86_64',
    test: bool = False,
    debug: bool = False,
    debug_variables: bool = True,
) -> hir.Block:
    from . import check

    from . import unsafe_audit
    unsafe_audit.last_entries.clear()
    representation.last_notes.clear()
    check.last_prototype_reports.clear()
    check.pending_brand_matches.clear()
    check.debug_formatters.clear()
    check.debug_variable_types.clear()
    check.reset_synthesized_names()
    bounds.last_cap_notes.clear()
    ty.reset_program_brands()   # the program's minted brands: a closed world per compile
    compiler = ModuleCompiler(srcfile, target, test=test, debug=debug, debug_variables=debug_variables)
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
        debug_variables=debug_variables,
    )
    root = compiler._validate_and_select(root, ctx.srcfile, prelude_module=False, no_prelude=no_prelude, ctx=ctx)
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
        explicit_copies=_directives.explicit_copies,
    )
    compiler.order.append(entry)
    merged = compiler.finish(entry)
    return merged if include_prelude else compiler.finished_roots[id(entry)]
