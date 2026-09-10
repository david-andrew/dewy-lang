"""Match coverage keeps holes and unbounded, arbitrary precision endpoints."""
import random
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.check import _ValueSet
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_integer_coverage(tmp_path):
    rng = random.Random(701)
    endpoints = [None, -2**100, -5, -1, 0, 1, 5, 2**100]
    cases = [([], [], 0), ([(None, -1), (1, None)], [(0, 0)], 0),
             ([(0, 0), (2, 2)], [(1, 1)], 1)]
    for _ in range(37):
        cases.append(([(rng.choice(endpoints), rng.choice(endpoints)) for _ in range(4)],
                      [(rng.choice(endpoints), rng.choice(endpoints)) for _ in range(3)],
                      rng.choice([-2**100, -1, 0, 1, 2**100])))

    def endpoint(value):
        return 'none' if value is None else str(value)

    def show(value):
        return ''.join(f'{endpoint(lo)}:{endpoint(hi)};' for lo, hi in value.intervals)

    expected = []
    for left, right, hole in cases:
        a, b = _ValueSet(left), _ValueSet(right)
        remaining = _ValueSet()
        for lo, hi in a.intervals:
            if (lo is None or lo <= hole) and (hi is None or hole <= hi):
                remaining.add((lo, hole-1))
                remaining.add((hole+1, hi))
            else:
                remaining.add((lo, hi))
        expected.append('|'.join([show(a.union(b)), show(a.intersect(b)), show(remaining),
                                  str(a.covers(b)).lower(), endpoint(a.first_uncovered(b))]))

    def intervals(rows):
        return '[' + ' '.join(f'[lower=({endpoint(lo)}) upper=({endpoint(hi)}) capped=false]' for lo, hi in rows) + ']'

    source = tmp_path / 'coverage.dewy'
    source.write_text(f'''import p"{ROOT / 'dewy/bootstrap/semantic/value_sets.dewy'}" as values
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
Case:type=const [left:values.Values right:values.Values hole:bigint]
normalized = (input:values.Values):>values.Values => {{
    let result:values.Values=[]
    loop interval in input {{values.add(@result interval)}}
    return result
}}
show = (input:values.Values):>string => {{
    let parts:array<string>=[]
    loop interval in input {{
        let lower=if interval.lower is? none 'none' else "{{interval.lower}}"
        let upper=if interval.upper is? none 'none' else "{{interval.upper}}"
        parts.push("{{lower}}:{{upper}};")
    }}
    return parts.join
}}
main = ():>int64 => {{
    let cases:array<Case>=[{' '.join(f'[left={intervals(a)} right={intervals(b)} hole=({hole})]' for a,b,hole in cases)}]
    loop case in cases {{
        let a=normalized(case.left)
        let b=normalized(case.right)
        let probe=values.first_uncovered(a b)
        let missing=if probe is? none 'none' else "{{probe}}"
        printl("{{show(values.union(a b))}}|{{show(values.intersect(a b))}}|{{show(values.exclude(a case.hole))}}|{{values.covers(a b)}}|{{missing}}")
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
