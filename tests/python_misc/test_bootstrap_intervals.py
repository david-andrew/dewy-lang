"""Compare the native bounds-analysis interval kernel with hosted operations."""

import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.analyze.bounds import Interval, _BoundsValidator, _exclude_value
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
OPS = {'<?': '__lt__', '<=?': '__le__', '>?': '__gt__', '>=?': '__ge__', '=?': '__eq__', 'not=?': '__ne__'}


def spelling(value):
    if value is None:
        return '*'
    if isinstance(value, bool):
        return str(value).lower()
    lo = '-' if value.lower is None else str(value.lower)
    hi = '+' if value.upper is None else str(value.upper)
    return f'{lo},{hi},{str(value.capped).lower()}'


def test_native_interval_operations_match_hosted(tmp_path):
    endpoints = [None, -(10**80), -2, 0, 3, 10**80]
    intervals = [Interval(a, b, capped=i % 3 == 0)
                 for i, (a, b) in enumerate((a, b) for a in endpoints for b in endpoints)
                 if a is None or b is None or a <= b]
    bounds = ['none' if n is None else f'b{i}' for i, n in enumerate(endpoints)]
    literal_lines = [f'let b{i}:bigint = ({n})' for i, n in enumerate(endpoints) if n is not None]
    values = [f'intervals.Interval[{bounds[endpoints.index(v.lower)]} {bounds[endpoints.index(v.upper)]} {str(v.capped).lower()}]' for v in intervals]
    validator = _BoundsValidator.__new__(_BoundsValidator)
    arithmetic = []
    for operation in ['__add__', '__sub__', '__mul__', '__floordiv__', '__mod__', '__rshift__', '__lshift__']:
        for left in [Interval(-9, -7), Interval(10, 20, capped=True), Interval(None, 4)]:
            for right in [Interval(2, 2), Interval(1, 3), Interval(1, None)]:
                for word in ['int', 'int8']:
                    arithmetic.append((operation, left, right, word, None))
    arithmetic.extend([
        ('__add__', Interval(120, 127), Interval(1, 3), 'int8', None),
        ('__sub__', None, Interval(0, 10), 'int8', Interval(0, 100)),
        ('__sub__', Interval(0, 1000), Interval(0, 1000), 'int8', Interval(0, 100)),
    ])

    def interval_literal(value):
        if value is None:
            return 'none'
        lo = 'none' if value.lower is None else f'({value.lower})'
        hi = 'none' if value.upper is None else f'({value.upper})'
        return f'intervals.Interval[{lo} {hi} {str(value.capped).lower()}]'

    arithmetic_lines = []
    for operation, left, right, word, bound in arithmetic:
        width = Interval(-128, 127) if word == 'int8' else None
        arithmetic_lines.append(f"printl(spell(intervals.binary('{operation}' {interval_literal(left)} {interval_literal(right)} {interval_literal(width)} {interval_literal(bound)})))")
    source = tmp_path / 'intervals.dewy' 
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as intervals
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
spell = (value:intervals.Interval?):>string => {{
    if value is? none return '*'
    let lo = if value.lower is? none '-' else _bigint_as_string(value.lower)
    let hi = if value.upper is? none '+' else _bigint_as_string(value.upper)
    return "{{lo}},{{hi}},{{value.capped}}"
}}
boolean = (value:bool?):>string => {{
    if value is? none return '*'
    return if value 'true' else 'false'
}}
main = ():>int64 => {{
    {' '.join(literal_lines)}
    let values:array<intervals.Interval> = [{' '.join(values)}]
    let ops:array<facts.Operator> = [{' '.join(repr(op) for op in OPS)}]
    loop left in values {{
        loop right in values {{
            printl(spell(intervals.intersect(left right)))
            printl(spell(intervals.union(left right)))
            printl(spell(intervals.widen(left right)))
            loop op in ops {{ printl(boolean(intervals.decide(op left right))) }}
        }}
        loop op in ops {{
            printl(spell(intervals.constraint(op left true)))
            printl(spell(intervals.constraint(op left false)))
        }}
        printl(spell(intervals.exclude(left 0)))
    }}
    {chr(10).join(arithmetic_lines)}
    return 0
}}
''')
    expected = []
    for left in intervals:
        for right in intervals:
            expected.extend(map(spelling, [left.intersect(right), left.union(right), left.widen(right)]))
            expected.extend(spelling(_BoundsValidator._decide_comparison(op, left, right)) for op in OPS.values())
        for op in OPS.values():
            expected.extend(spelling(_BoundsValidator._comparison_constraint(op, left, truth)) for truth in (True, False))
        expected.append(spelling(_exclude_value(left, 0)))
    expected.extend(spelling(validator._binary_interval(operation, left, right, word, bound=bound))
                    for operation, left, right, word, bound in arithmetic)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected


@pytest.mark.parametrize('left', [Interval(10, 20), Interval(-20, -10)])
def test_unbounded_positive_divisor_includes_zero(left):
    validator = _BoundsValidator.__new__(_BoundsValidator)
    result = validator._binary_interval('__floordiv__', left, Interval(1, None), 'int')
    assert result is not None and result.lower <= 0 <= result.upper
    for numerator in range(left.lower, left.upper + 1):
        for divisor in (1, 2, 10, 1000):
            quotient = abs(numerator) // divisor * (-1 if numerator < 0 else 1)
            assert result.lower <= quotient <= result.upper
