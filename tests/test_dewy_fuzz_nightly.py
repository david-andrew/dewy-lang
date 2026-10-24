"""What the nightly program fuzzer found: oracle fixes, and the wrong code it tracks until fixed.

A tracked issue (tools/compiler/dewy_fuzz.py TRACKED) keeps its repro here as a strict xfail; a
fix makes the xfail fail, so the repro moves to tests/cases and the TRACKED entry goes.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401  (fixture)
from tools.compiler import dewy_fuzz
from tools.compiler import dewy_fuzz_programs as gen


def build_and_run(compiler, tmp_path, name, source, release=False):  # noqa: F811
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    built = subprocess.run([compiler, 'build', path, '-o', tmp_path / name, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return subprocess.run([tmp_path / name], capture_output=True, text=True, timeout=10, check=False)


def test_juxtaposition_never_reads_as_one_number():
    n, e, z = gen.Var(gen.I, 'n3'), gen.Var(gen.I, 'e29'), gen.Lit(gen.I, 0)
    assert gen.juxtaposed(gen.Lit(gen.I, 4), n, '4', 'n3') == '(4n3)'
    assert gen.juxtaposed(gen.Lit(gen.I, 4), e, '4', 'e29') == ''      # 4e29, an exponent
    assert gen.juxtaposed(z, n, '0', 'n3') == ''                       # 0n3, a base prefix


def test_unpacked_values_keep_their_declared_type(compiler, tmp_path):  # noqa: F811
    # Unannotated, `(15 0)` would be two `int`s; the oracle declares the names int64. A
    # value converted with the wrap policy has that policy's type until converted back.
    wrapped = gen.Bin(gen.I, '//', gen.Conv(gen.I, gen.Lit(gen.U, 29), wrap=True), gen.Lit(gen.I, 8))
    unpack = gen.Unpack(('v1', 'v2', 'v3'), (gen.Lit(gen.I, 15), gen.Lit(gen.I, 0), wrapped), False, True, 'p4')
    body = unpack.render().replace('\n', '\n    ')
    source = f'h=(@t:int64):>void=>{{}}\nmain=():>void=>{{\n    {body}\n    h(@v1)\n    h(@v3)\n    printl(v1 << 62)\n}}\n'
    ran = build_and_run(compiler, tmp_path, 'unpack', source)
    assert ran.returncode == 0 and ran.stdout == '15\n0\n3\n-4611686018427387904\n', source + ran.stdout + ran.stderr


# Wrong code tracked until fixed: (source, expected stdout).
TRACKED = {
    'release_record_field_after_call': (
        'g = (n:int64):>[left:float64 right:int64] => {\n'
        '    let result:[left:float64 right:int64] = [left=0.0 right=n]\n'
        '    return result\n'
        '}\n'
        'main = ():>void => {\n'
        '    let r:[left:float64 right:int64] = [left=2.25 right=1]\n'
        '    r.left += 1.0\n'
        '    r = g(1)\n'
        '    r.left += 3.0\n'
        '    printl(r)\n'
        '}\n',
        '[left=3.0 right=1]\n'),
}


def test_tracked_issues_have_repros_of_their_shape():
    assert {issue.name for issue in dewy_fuzz.TRACKED} == set(TRACKED)
    for issue in dewy_fuzz.TRACKED:
        assert issue.shape.search(TRACKED[issue.name][0]), issue.name


def test_tracked_repros_pass_in_default_builds(compiler, tmp_path):  # noqa: F811
    for name, (source, expected) in TRACKED.items():
        assert build_and_run(compiler, tmp_path, name, source).stdout == expected, name


@pytest.mark.parametrize('name', [pytest.param('release_record_field_after_call', marks=pytest.mark.xfail(
    reason='release: a float field updated after the record is replaced by a call result adds to its old value '
           '(inlining/scalar replacement)', strict=True))])
def test_tracked_wrong_output_in_release(compiler, tmp_path, name):  # noqa: F811
    source, expected = TRACKED[name]
    assert build_and_run(compiler, tmp_path, name, source, release=True).stdout == expected
