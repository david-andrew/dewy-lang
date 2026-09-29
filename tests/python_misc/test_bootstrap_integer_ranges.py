"""Exact range normalization preserves signs, open ends and large counts."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


ROOT = Path(__file__).resolve().parents[2]


def test_native_integer_range_normalization(tmp_path):
    cases, expected = [], []
    for anchor in (0, -(2**80), 2**80):
        for step in (1, 3, -1, -3):
            for distance in (-5, 0, 1, 8):
                right = anchor + distance
                for bounds in ('[]', '[)', '(]', '()'):
                    first = anchor + (step if bounds[0] == '(' else 0)
                    gap = (right - first if step > 0 else first - right) - (bounds[1] == ')')
                    count = 0 if gap < 0 else gap // abs(step) + 1
                    last = first + (count - 1) * step
                    cases.append(f'Case[({anchor}) ({anchor + step}) ({right}) "{bounds}"]')
                    expected.append(f'{first},{step},{last},{count}')
    source = tmp_path / 'ranges.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/integer_ranges.dewy'}" as ranges
Case:type=const [anchor:bigint second:bigint right:bigint bounds:string]
main=():>int64=>{{
    loop item in [{' '.join(cases)}] {{
        let result=ranges.normalize(item.anchor item.second item.right item.bounds)
        $runtime_assert result isnt? none and result.last isnt? none and result.count isnt? none
        printl("{{result.first}},{{result.step}},{{result.last}},{{result.count}}")
        if result.count >? 0 {{
            $runtime_assert ranges.contains(result.first result) and ranges.contains(result.last result)
        }}
        $runtime_assert not ranges.contains(result.first-result.step result)
        $runtime_assert not ranges.contains(result.last+result.step result)
    }}
    $runtime_assert ranges.normalize(1 1 10 '[]') is? none
    let unbounded=ranges.normalize(10 7 none '(]')
    $runtime_assert unbounded isnt? none and unbounded.count is? none and unbounded.last is? none
    $runtime_assert unbounded.first=?7 and ranges.contains((-80) unbounded) and not ranges.contains(6 unbounded)
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
