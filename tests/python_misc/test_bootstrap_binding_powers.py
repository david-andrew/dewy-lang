"""Precomputed native powers retain the hosted precedence table's alternatives."""
import json
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.parser import p0
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def expected_powers(labels):
    left, right, assocs = [], [], []
    for label in labels:
        for rank, (assoc, group) in enumerate(reversed(p0.operator_groups)):
            names = [item if isinstance(item, str) else item.__name__ for item in group]
            if label not in names:
                continue
            l, r = p0.bind_power_table[rank]
            if l >= 0 and l not in left:
                left.append(l)
            if r >= 0 and r not in right:
                right.append(r)
            if assoc.name not in assocs:
                assocs.append(assoc.name)
    # Order is not a precedence preference. Parsing considers every power.
    return sorted(left or [-1]), sorted(right or [-1]), sorted(assocs)


def test_native_powers_match_hosted_table(tmp_path):
    names = list(dict.fromkeys(item if isinstance(item, str) else item.__name__
                              for _, group in p0.operator_groups for item in group))
    cases = [[name] for name in names + ['??', '<=>', 'unknown']]
    cases += [['CallJuxtapose', 'MultiplyJuxtapose'], ['`', '+'], ['+', '`'],
              ['~', '?'], ['unknown', '+'], ['+', '+'], []]
    def string(value):
        # Dewy interpolation braces must be escaped even inside a literal.
        return json.dumps(value).replace('{', '\\{').replace('}', '\\}')
    declarations = [f'check([{ " ".join(string(label) for label in labels) }])' for labels in cases]
    source = tmp_path / 'powers.dewy'
    source.write_text(f'''from reporting import Span
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/parser/t1.dewy'}" as tokens
import p"{ROOT / 'dewy/bootstrap/parser/t2.dewy'}" as post
check=(labels:array<string>):>void=>{{
    let nodes:array<tokens.Token>=[]
    let op=post.Juxtapose[loc=Span[0 0] options=labels]
    let power=parser.powers(op nodes)
    printl("{{[loop p in power.left \"{{p}}\"].join(',')}};{{[loop p in power.right \"{{p}}\"].join(',')}};{{power.assocs.join(',')}}")
}}
main=():>int64=>{{
    {chr(10).join(declarations)}
    return 42
}}
''')
    output = tmp_path / 'powers.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                         text=True, timeout=10, check=False)
    assert run.returncode == 42, run.stderr
    actual = []
    for line in run.stdout.splitlines():
        left, right, assocs = line.split(';')
        actual.append((sorted(map(int, left.split(','))), sorted(map(int, right.split(','))),
                       sorted(assocs.split(',')) if assocs else []))
    assert actual == [expected_powers(labels) for labels in cases]


def test_binding_power_lookup_allocation(tmp_path):
    source = ROOT / 'tests/fixtures/native_binding_powers.dewy'
    output = tmp_path / 'lookup.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                         text=True, timeout=10, check=False)
    assert run.returncode == 42, run.stderr
    assert 0 <= int(run.stdout) < 20_000_000
