"""The differential oracle checks stores introduced by multi-value collection."""
import subprocess

import pytest
from tests.support import compiler  # noqa: F401
from tools.compiler import dewy_fuzz, dewy_fuzz_programs as g


@pytest.mark.parametrize('kind', ['unpack', 'block', 'if', 'literal'])
def test_multi_value_storage_checks_exact_result(kind):
    value = g.Bin(g.I, '<<', g.Lit(g.I, 3), g.Lit(g.I, 63))
    if kind == 'unpack':
        statement = g.Unpack(('...rest',), (value,), True, False, 'held', 'collect')
    else:
        item = {'block': g.MultiBlock(g.MULTI, (value,)),
                'if': g.MultiIf(g.MULTI, g.Lit(g.B, True), (value,)),
                'literal': value}[kind]
        statement = g.Print(g.MultiLit(g.AI, (item,)))
    assert g.Program((), (statement,)).outcome() == ('', 101)


@pytest.mark.parametrize('group', [False, True], ids=['array', 'group'])
@pytest.mark.parametrize('release', [False, True])
def test_unpack_keeps_fixed_width_mutable_bindings(compiler, tmp_path, group, release):
    unpack = g.Unpack(('first', '...rest', 'last'),
                      (g.Lit(g.I, 14), g.Lit(g.I, -14),
                       g.Field(g.I, g.Var(g.AI, 'xs'), 'length')),
                      group, True, 'held' if group else '')
    source = tmp_path / 'unpack.dewy'
    source.write_text('mutate=(@x:int64):>void=>{x+=1}\nmain=()=>{\n'
                      'let xs:array<int64>=[1 2]\n' + unpack.render() +
                      '\nmutate(@first); printl(first)\n}\n')
    binary = tmp_path / 'unpack'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == '14\n[-14]\n2\n15\n'


def test_integer_constructors_in_multi_module_value_groups(compiler, tmp_path):
    # This batch makes conversion-node symbols exceed the function table.
    # Checking a type constructor must not run function-only call hooks.
    assert dewy_fuzz.fuzz(compiler, seed=17, count=8, modes=('native', 'web'),
                          workers=2, shrink=0, quiet=True,
                          work=tmp_path / 'work', failures_dir=tmp_path / 'failures') == 0
