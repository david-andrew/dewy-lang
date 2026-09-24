"""A loop condition hoisted out of the `loop` test keeps its short circuit.

µDewy `and`/`or` short-circuit only as `if`/`loop` conditions. A condition
whose family test needs statements (a brand range for a type with
descendants) is evaluated before every iteration; a later operand reading a
field of the narrowed value must not run for another node.
"""
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

SOURCE = '''AST = $abstract type of [loc:int64]
Block = type of AST & [items:array<addr> scoped:bool]
Scoped = type of Block & [arena:int64]
Other = type of AST & [x:int64 y:int64 z:int64]
node_at = (nodes:array<AST> id:addr):>AST => {
    $runtime_assert id <? nodes.length
    return nodes[id]
}
unwrap = (id:addr nodes:array<AST>):>AST => {
    let value = node_at(nodes id)
    loop value is? Block and not value.scoped and value.items.length =? 1 {value = node_at(nodes value.items[0])}
    return value
}
main = ():>int64 => {
    let nodes:array<AST> = [Other[1 39 0 0] Block[2 [0] false] Scoped[3 [1] false 9]]
    return unwrap(1 nodes).loc + unwrap(2 nodes).loc * 10 + unwrap(0 nodes).loc * 100 - 69
}'''


def test_hoisted_loop_condition_short_circuits(tmp_path):
    execute(tmp_path, 'loop-short-circuit', codegen(SrcFile(None, SOURCE)))
