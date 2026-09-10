"""Native comparison transfer retains all feasible values and relational routes."""
import itertools
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_comparison_transfer(tmp_path):
    module = ROOT / 'dewy/bootstrap/semantic/analyze'
    intervals = [(-3, -1), (-2, 2), (0, 0), (0, 3), (1, 1), (1, 3)]
    operators = {'<?': lambda a, b: a < b, '<=?': lambda a, b: a <= b,
                 '>?': lambda a, b: a > b, '>=?': lambda a, b: a >= b,
                 '=?': lambda a, b: a == b, 'not=?': lambda a, b: a != b}
    calls, expected = [], []
    for op, truth, left, right in itertools.product(operators, (False, True), intervals, intervals):
        calls.append(f'probe("{op}" {str(truth).lower()} ({left[0]}) ({left[1]}) ({right[0]}) ({right[1]}))')
        feasible = [(a, b) for a in range(left[0], left[1] + 1) for b in range(right[0], right[1] + 1)
                    if operators[op](a, b) == truth]
        expected.append(feasible)
    source = f'''
import p"{module / 'comparison_facts.dewy'}" as comparisons
import p"{module / 'intervals.dewy'}" as ranges
import p"{module / 'fact_state.dewy'}" as facts
import p"{module / 'relations.dewy'}" as relations
import p"{module.parent / 'propositions.dewy'}" as propositions
let probe=(op:propositions.Operator truth:bool al:int64 ah:int64 bl:int64 bh:int64):>void=>{{
    let state:facts.State=[]
    facts.put(@state facts.value(facts.Term[1]) ranges.Interval[al ah])
    facts.put(@state facts.value(facts.Term[2]) ranges.Interval[bl bh])
    let context=relations.Context[facts.Context[cap=100]]
    let result=comparisons.refine(state op comparisons.Operand[ranges.Interval[al ah] facts.Term[1]] comparisons.Operand[ranges.Interval[bl bh] facts.Term[2]] truth context)
    if result is? none {{printl("none") return}}
    let left=facts.lookup(result facts.value(facts.Term[1]))
    let right=facts.lookup(result facts.value(facts.Term[2]))
    $runtime_assert left isnt? none and right isnt? none
    printl("{{left.lower}} {{left.upper}} {{right.lower}} {{right.upper}}")
}}
let main=():>int64=>{{
    {chr(10).join(calls)}
    let state:facts.State=[]
    facts.put(@state facts.index(2 7) ranges.exact(1))
    comparisons.ordered(@state comparisons.Operand[term=facts.Term[1]] comparisons.Operand[term=facts.Term[2]] false)
    $runtime_assert facts.index(1 7).key in? state
    comparisons.ordered(@state comparisons.Operand[term=facts.Term[3] shift=2] comparisons.Operand[term=facts.Term[4] shift=4] true)
    let offset=facts.lookup(state facts.order(facts.Term[3] facts.Term[4]))
    $runtime_assert offset isnt? none and offset.lower =? -1
    comparisons.ordered(@state comparisons.Operand[term=facts.Term[5]] comparisons.Operand[term=facts.Term[6 'length']] true)
    $runtime_assert facts.index(5 6).key in? state
    let strict=comparisons.refine(state 'not=?' comparisons.Operand[term=facts.Term[1]] comparisons.Operand[term=facts.Term[2]] true relations.Context[facts.Context[cap=100]])
    $runtime_assert strict isnt? none
    let gap=facts.lookup(strict facts.order(facts.Term[1] facts.Term[2]))
    $runtime_assert gap isnt? none and gap.lower =? 1
    return 0
}}
'''
    output = tmp_path / 'comparison.udewy'
    input_path = tmp_path / 'comparison.dewy'
    input_path.write_text(source)
    output.write_text(codegen(SrcFile.from_path(input_path)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == len(expected)
    for line, feasible, call in zip(lines, expected, calls, strict=True):
        if line == 'none':
            assert not feasible, (call, feasible)
            continue
        al, ah, bl, bh = map(int, line.split())
        assert all(al <= a <= ah and bl <= b <= bh for a, b in feasible), (call, line, feasible)
        # For interval operands these basic comparisons have a feasible pair
        # exactly when the transfer leaves a live state.
        assert feasible, (call, line)
