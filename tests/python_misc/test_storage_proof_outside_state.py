"""Reading outside state keeps the shared storage proof; writing it does not.

`storage_borrows.prove` admits a forwarded argument only when no call made
while it is lent can change its storage. Storage the argument may share with
module state changes only through a write or raw exposure of that state, so
a function that merely reads module state no longer blocks the proof for its
callers (row S5). A function that writes outside state still blocks it, and
the block still reaches every caller through the call graph.
"""
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from dewy.semantic import hir

READS = '''let verbose:bool=false
peek = (xs:array<int64>):>int64 => if verbose xs.length+100 else xs.length
outer = (xs:array<int64>):>int64 => peek(xs) + peek(xs)
main = ():>int64 => {
    let xs:array<int64>=[1 2 3]
    return outer(xs)*7
}
'''
WRITES = READS.replace('if verbose xs.length+100 else xs.length', '{verbose=not verbose return xs.length}')


def proved_arguments(source):
    """`(callee, argument proved)` for every call to `peek` or `outer`."""
    captured = []
    original = lower._Lowerer.__init__

    def capture(self, root, *rest, **options):
        original(self, root, *rest, **options)
        proofs = self.storage_borrow_proofs
        for node in hir.walk(self.root):
            if isinstance(node, hir.FunctionCall) and getattr(node.func, 'name', None) in ('peek', 'outer'):
                captured.append((node.func.name, id(node.pos_args[0]) in proofs.arguments.get(id(node), ())))

    lower._Lowerer.__init__ = capture
    try:
        codegen(SrcFile(None, source), debug_locations=False)
    finally:
        lower._Lowerer.__init__ = original
    return captured


def test_reading_module_state_keeps_the_proof():
    results = proved_arguments(READS)
    assert results and all(proved for _name, proved in results), results


def test_writing_module_state_blocks_callers():
    results = proved_arguments(WRITES)
    # `outer` forwards its parameter to the writer: no longer proved. `main`
    # passes a fresh private local, which cannot share storage with module
    # state, so its argument stays proved although `main` is blocked too.
    assert [proved for name, proved in results if name == 'peek'] == [False, False]
    assert [proved for name, proved in results if name == 'outer'] == [True]
