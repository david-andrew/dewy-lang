"""A match over a union of string literals (an enumeration) with literal arms dispatches
through a table, as a Sloppy match over an enum does, and keeps its meaning: grouped arms,
bindings, a fallback, a boolean result, an `int` result (which stays a chain of compares: the
lowering's lookup table holds plain words)."""
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''Dir:type='n' | 'e' | 's' | 'w' | 'up' | 'down'
name=(d:Dir):>string=>match d {
    <'n'> => "north"
    <'e'> => "east"
    <'s'> => "south"
    other:'w'|'up' => "{other}!"
    _ => "down"
}
vertical=(d:Dir):>bool=>match d {
    <'up'|'down'> => true
    _ => false
}
steps=(d:Dir):>int=>{
    let n=match d {
        <'n'|'s'> => 10
        <'e'|'w'> => 20
        _ => 30
    }
    n
}
main=():>void=>{
    loop d in members(Dir) {printl"{d} {name(d)} {vertical(d)} {steps(d)}"}
}
'''

EXPECTED = ['down down true 30', 'e east false 20', 'n north false 10', 's south false 10', 'up up! true 30',
            'w w! false 20']


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_enumeration_match_is_a_table(compiler, tmp_path, release):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    binary = tmp_path / 'main'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--ir', *flags, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ir = built.stdout + built.stderr
    probe = re.search(r'^fn f_name_.*?(?=^fn |\Z)', ir, re.M | re.S)
    assert probe and 'brtable' in probe[0], ir
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == EXPECTED
