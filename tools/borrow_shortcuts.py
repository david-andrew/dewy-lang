"""List the call arguments lowering borrows without the shared storage proof.

Usage: python tools/borrow_shortcuts.py FILE.dewy [--list N] [--by reason|file|site]

Allocation contracts (`semantic/analyze/public_effects.py`) count a storage
effect for every aggregate call argument outside `storage_borrows.prove`'s
borrowed arguments. Lowering forwards those same arguments and may borrow
more (closure matrix row S5). This compiles FILE with the hosted compiler and
classifies each aggregate argument outside the proof:

- `copied`: lowering copied it too (a `copy:` note at the argument);
- `moved`: lowering moved it (a move note at the argument);
- `shortcut`: lowering passed it without a copy or move: a borrow the shared
  proof does not know, so contracts count a copy that never happens.

It also counts proved arguments lowering copies at the call anyway: owning
(donated) parameters, whose copy contracts count in the callee's body.
Shortcuts are moved into the shared proof or recorded as cost-only.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str]) -> int:
    parser = ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('file')
    parser.add_argument('--list', type=int, default=20, help='show this many groups')
    parser.add_argument('--examples', type=int, default=0, help='show this many examples per cause')
    parser.add_argument('--by', choices=['file', 'callee', 'type'], default='callee')
    args = parser.parse_args(argv)

    from dewy.backend.udewy import codegen, lower
    from dewy.reporting import SrcFile
    from dewy.semantic import bindings, hir, ty
    from dewy.semantic.analyze.effects import _literal_params, _unwrap
    from dewy.semantic.analyze.public_effects import scalar
    from dewy.semantic.analyze.storage_borrows import borrowable

    def key(srcfile, span):
        return (str(getattr(srcfile, 'path', None)), span.start, span.stop)

    def aggregate(node):
        type_ = ty.strip_refinement(node.type)
        return not scalar(type_) and not isinstance(type_, (ty.FunctionType, ty.OverloadType)) and type_ not in ('int', 'uint')

    def callee(call):
        return getattr(call.func, 'name', None) or type(call.func).__name__

    def survey(lowerer, root):
        """Every aggregate argument with its proof status and, if unproved,
        why; taken before lowering rewrites the tree the proof analysed."""
        proofs, analysis, summaries = lowerer.storage_borrow_proofs, lowerer.allocator_analysis, lowerer.program_effects

        def read_only(binding):
            summary = summaries.for_param_binding(binding) if binding is not None else None
            return summary is not None and summary.read_only

        def cause(literal, call, argument):
            """Why the shared proof left this argument unproved, in the order
            `storage_borrows.prove` checks."""
            if ty.string_valued(argument.type):
                return 'a string (an immutable share, never copied when passed)'
            if literal is None:
                return 'module startup'
            if id(literal) in proofs.blocked:
                return 'caller reaches unmodelled or ambient effects'
            targets = analysis._direct_targets(call)
            if not targets:
                return 'callee not resolved statically'
            for target in targets:
                for value, parameter in analysis._pair_arguments(call, target) or ():
                    if value is argument and (parameter is None or parameter.place or not read_only(parameter.binding_id)):
                        return 'callee writes or keeps its parameter'
            path = bindings.access_path(argument, unwrap=_unwrap)
            root_node = path.root
            if not isinstance(root_node, hir.ExpressedIdentifier) or root_node.binding_id is None:
                return 'not a named owner (a call result, literal or conversion)'
            own = next((p for p in _literal_params(literal) if p.binding_id == root_node.binding_id), None)
            if own is None:
                return 'local owner not proved stable (written, captured or not a fresh value)'
            if not read_only(own.binding_id):
                return 'caller writes or keeps the parameter it passes on'
            if own.place:
                return 'a place parameter beside other place parameters'
            if not borrowable(own.type):
                return 'parameter type is not ordinary storage'
            if path.steps:
                return 'a projection of a read-only parameter (route not read-only at that path, or storage shape differs)'
            return 'a read-only parameter whose type differs from the callee parameter type'

        records = []

        def visit(node, srcfile, literal):
            if isinstance(node, hir.FunctionLiteral):
                literal = node
                if node.source is not None:
                    srcfile = node.source
            if isinstance(node, hir.FunctionCall):
                borrowed = proofs.arguments.get(id(node), set()) | proofs.literal_arguments.get(id(node), set())
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    if isinstance(argument, hir.Place) or not aggregate(argument):
                        continue
                    where = f'{getattr(srcfile, "path", None)}:{srcfile.offset_to_row_col(argument.loc.start)[0] + 1}'
                    proved = id(argument) in borrowed
                    records.append(dict(spot=key(srcfile, argument.loc), where=where, callee=callee(node),
                                        type=str(ty.strip_refinement(argument.type))[:90], proved=proved,
                                        cause=None if proved else cause(literal, node, argument)))
            for child in hir.children(node):
                visit(child, srcfile, literal)

        sys.setrecursionlimit(100000)
        sources = getattr(root, 'item_sources', None)
        for index, item in enumerate(root.items):
            source = sources[index] if sources and index < len(sources) and sources[index] is not None else lowerer.srcfile
            visit(item, source, None)
        return records

    surveys = []
    original = lower._Lowerer.__init__

    def capture(self, root, *rest, **options):
        original(self, root, *rest, **options)
        # The constructor analyses its own copy (dimensions erased).
        surveys.append((self, survey(self, self.root)))

    lower._Lowerer.__init__ = capture
    try:
        codegen(SrcFile.from_path(Path(args.file)), debug_locations=False)
    finally:
        lower._Lowerer.__init__ = original
    lowerer, records = surveys[-1]
    # String escapes are not storage transfers in either analysis.
    copied = {key(note.srcfile, note.loc) for note in lowerer.copy_notes if note.kind != 'string'}
    moved = {key(note.srcfile, note.loc) for note in lowerer.move_notes if note.moved}

    classes: Counter = Counter()
    causes: Counter = Counter()
    examples: dict = {}
    shortcuts = []
    donated = []
    for record in records:
        if record['proved']:
            # Proved, yet lowering copies at the call: an owning (donated)
            # parameter. Contracts count that copy in the callee instead.
            if record['spot'] in copied:
                donated.append(record)
            continue
        kind = 'copied' if record['spot'] in copied else 'moved' if record['spot'] in moved else 'shortcut'
        classes[kind] += 1
        if kind == 'shortcut':
            shortcuts.append(record)
            causes[record['cause']] += 1
            examples.setdefault(record['cause'], []).append(record)

    print(f'aggregate arguments: {len(records)}; proved by the shared proof: {sum(r["proved"] for r in records)}')
    print(f'outside the shared proof: {sum(classes.values())}')
    for kind in ('copied', 'moved', 'shortcut'):
        print(f'  {kind}: {classes[kind]}')
    print(f'proved, yet copied at the call (donated; counted in the callee): {len(donated)}')
    print('shortcuts by cause:')
    for name, count in causes.most_common():
        print(f'  {count:6d} {name}')
        for record in examples[name][:args.examples]:
            print(f'           {record["where"]} {record["callee"]} {record["type"]}')
    field = {'file': lambda r: r['where'].rsplit(':', 1)[0], 'callee': lambda r: r['callee'], 'type': lambda r: r['type']}[args.by]
    print(f'shortcuts by {args.by}:')
    for name, count in Counter(field(r) for r in shortcuts).most_common(args.list):
        print(f'  {count:6d} {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
