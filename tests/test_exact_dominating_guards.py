"""Cheap lowering guards expire on writes and do not cross loop backedges."""
import re
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_dominating_guard_and_invalidations(compiler, tmp_path, release):
    source = tmp_path / 'guards.dewy'
    source.write_text('''$no_assumed_bounds
safe=(x:int64):>int64=>{if x <? 9223372036854775807 return x+1;return 0}
changed=(x:int64):>int64=>{
    if x <? 9223372036854775807 {x=9223372036854775807;return x+1}
    return 0
}
backedge=(x:int64):>int64=>{
    let total:int64=0
    if x <? 9223372036854775807 {
        loop i in [0..2) {total=x+1;x=9223372036854775807}
    }
    return total
}
wide=(x:int64):>int64=>{if x >? 0 return (x+x)+0;return 0}
choice=(x:int64 flag:bool):>int64=>{if x <? 9223372036854775807 or flag return x+1;return 0}
affine=(x:int64):>int64=>{if x >=? 0 return 3*x+1;return 0}
main=(args:array<string>)=>{
    let x=int64(to_int(args[2]) ?? 0)
    if args[1]=?"safe" printl(safe(x))
    else if args[1]=?"changed" printl(changed(x))
    else if args[1]=?"loop" printl(backedge(x))
    else if args[1]=?"wide" printl(wide(x))
    else if args[1]=?"choice" printl(choice(x true))
    else printl(affine(x))
}
''')
    binary = tmp_path / 'guards'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    bodies = re.split(r'^fn ', built.stdout, flags=re.M)
    safe = next((body for body in bodies if body.startswith('f_safe_')), None)
    if safe: assert 'checked_add' not in safe, safe
    for op, x, expected in [('safe', -2**63, -2**63+1), ('safe', 2**63-2, 2**63-1),
                            ('safe', 2**63-1, 0), ('changed', 1, None), ('loop', 1, None),
                            ('wide', 2**63-1, None), ('choice', 2**63-1, None),
                            ('affine', 1, 4), ('affine', 2**63-1, None), ('affine', -1, 0)]:
        ran = subprocess.run([binary, op, str(x)], capture_output=True, text=True)
        if expected is None:
            assert ran.returncode == 101 and not ran.stdout, (op, x, ran.stdout, ran.stderr)
        else:
            assert ran.returncode == 0 and ran.stdout.strip() == str(expected), (op, x, ran.stdout, ran.stderr)
