"""Native array-length transfer matches the hosted HIR evaluator."""

import subprocess
from pathlib import Path

from test_bootstrap_fact_state import fact
from test_bootstrap_intervals import spelling

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_length_transfer_matches_hosted(tmp_path):
    loc = Span(0, 0)
    registry = bindings.BindingRegistry()
    array_type = ty.ArrayType('int64', None)
    registry.by_id[1] = bindings.Binding(1, 'xs', 'value', loc, array_type)
    registry.by_id[3] = bindings.Binding(3, 'count', 'value', loc, 'int64')
    array = hir.ExpressedIdentifier(loc, array_type, 'xs', binding_id=1)
    count = hir.ExpressedIdentifier(loc, 'int64', 'count', binding_id=3)
    zero = hir.Integer(loc, ty.IntegerLiteralType(0), '0d', 0)
    signature = ty.FunctionType([], [], None, 'int64')
    unknown = hir.FunctionCall(loc, 'int64', hir.ExpressedIdentifier(loc, signature, 'unknown'), [], {})
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), hir.Block(loc, 'void', [], False))
    validator.max_length = 1024
    interval, length, order = bounds.Interval, bounds._length_key, bounds._order_key
    before_values = [None, interval.exact(0), interval.exact(3), interval(1, 8)]
    count_values = [None, interval.exact(0), interval.exact(2), interval(1, 4)]
    lines, expected = [], []
    case = 0

    def source_interval(value):
        if value is None:
            return 'none'
        lo = 'none' if value.lower is None else f'({value.lower})'
        hi = 'none' if value.upper is None else f'({value.upper})'
        return f'ranges.Interval[{lo} {hi} {str(value.capped).lower()}]'

    for method in ['push', 'insert', 'pop', 'truncate', 'clear']:
        for before in before_values:
            for count_value in count_values if method == 'truncate' else [None]:
                state = {
                    order(4, length(1)): interval(2, None),
                    order(length(1), length(2)): interval(0, None),
                    bounds._remainder_key(length(1), length(2), 4): interval(1, None),
                    bounds._index_fact_key(4, 1): interval(None, None),
                }
                if before is not None:
                    state[length(1)] = before
                if count_value is not None:
                    state[3] = count_value
                args = [zero] if method == 'push' else [zero, zero] if method == 'insert' else [unknown if count_value is None else count] if method == 'truncate' else []
                call = hir.FunctionCall(loc, 'void', hir.ArrayMethod(loc, signature, array, method), args, {})
                lines.append(f'    let s{case}:facts.State = []')
                for key, value in state.items():
                    lines.append(f'    facts.put(@s{case} {fact(key)[0]} {source_interval(value)})')
                lines.append(f'    lengths.apply(@s{case} 1 "{method}" {source_interval(count_value)} 1024);')
                lines.append(f'    emit("{case}" s{case})')
                validator._eval(call, state, validate=False)
                expected.extend(f'{case}|{fact(key)[1]}|{spelling(value)}' for key, value in state.items())
                case += 1
    source = tmp_path / 'length_facts.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/length_facts.dewy'}" as lengths
emit = (label:string state:facts.State):>void => {{
    loop entry in state.values {{
        let lo = if entry.interval.lower is? none '-' else _bigint_as_string(entry.interval.lower)
        let hi = if entry.interval.upper is? none '+' else _bigint_as_string(entry.interval.upper)
        printl("{{label}}|{{entry.fact.key}}|{{lo}},{{hi}},{{entry.interval.capped}}")
    }}
}}
main = ():>int64 => {{
{chr(10).join(lines)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
