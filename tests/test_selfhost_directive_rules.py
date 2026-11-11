"""Deferred obligations, prototype warnings, default effect rows and function-entry scopes agree
with frozen Jo: both compilers build programs that use settings, with the same messages and bytes."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

CASES = sorted([*(ROOT / 'tests/cases/directives').glob('*.dewy'), *(ROOT / 'tests/cases/effects').glob('*.dewy'),
                *(ROOT / 'tests/cases/notraps11').glob('*.dewy')])

# (a function whose body sets a policy its signature does not: entry bindings take the body's;
# an `$ide` index of runtime checks)
MIXED = '''$runtime_checks
pick=(xs:array<int64> i:int64):>int64=>{
    xs[i]
}
main=()=>{
    let xs=[1 2 3]
    printl(pick(xs 1))
}
'''


def outcome(binary, tmp_path, label, paths=CASES):
    out = tmp_path / label
    out.mkdir()
    results = []
    for i, path in enumerate([*paths, tmp_path / 'mixed.dewy']):
        target = out / f'p{i}'
        r = subprocess.run([binary, 'build', path, '-o', target], capture_output=True, text=True, timeout=120,
                           check=False)
        made = target.read_bytes() if target.exists() else b''
        results.append((path.name, r.returncode, r.stdout, r.stderr.replace(str(binary), 'dewy-core'), made))
    return results


def test_directive_rules_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    (tmp_path / 'mixed.dewy').write_text(MIXED)
    dewy, jo = leaf_compilers(compiler, tmp_path, ('directive_rules',))
    expected = outcome(jo, tmp_path, 'jo')
    assert outcome(dewy, tmp_path, 'dewy') == expected
    assert len(CASES) > 100 and any(r[1] == 0 for r in expected) and any(r[1] != 0 for r in expected)
    assert any('prototype:' in r[3] for r in expected)
