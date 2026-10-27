"""A record batch uses its bounded invariant only behind a whole-array census."""
import os
import platform
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('nested', [False, True])
def test_bounded_record_batch_and_outliers(compiler, tmp_path, release, nested):
    definitions = 'P:type=[x:int64 y:int64 dx:int64 dy:int64]'
    x, y, dx, dy = 'x', 'y', 'dx', 'dy'
    make = 'P[x y dx dy]'
    if nested:
        definitions = 'V:type=[x:int64 y:int64]\nP:type=[p:V v:V]'
        x, y, dx, dy = 'p.x', 'p.y', 'v.x', 'v.y'
        make = 'P[p=V[x y] v=V[dx dy]]'
    source = tmp_path / 'batch.dewy'
    source.write_text(f'''$runtime_checks
{definitions}
step=(@ps:array<P>):>void=>{{
 loop i in 0.. and i <? ps.length {{
  let x=ps[i].{x}+ps[i].{dx}
  let y=ps[i].{y}+ps[i].{dy}
  if x <? 0 or x >=? 100 {{ps[i].{dx}=0-ps[i].{dx}; x=ps[i].{x}}}
  if y <? 0 or y >=? 100 {{ps[i].{dy}=0-ps[i].{dy}; y=ps[i].{y}}}
  ps[i].{x}=x
  ps[i].{y}=y
 }}
}}
run=(@ps:array<P> rounds:int64):>void=>{{
 let r:int64=0
 loop r <? rounds {{step(@ps); r+=1}}
}}
main=(args:array<string>)=>{{
 let n=int64(to_int(args[1]) ?? 0)
 let x=int64(to_int(args[2]) ?? 0)
 let y=int64(to_int(args[3]) ?? 0)
 let dx=int64(to_int(args[4]) ?? 0)
 let dy=int64(to_int(args[5]) ?? 0)
 let ps:array<P>=[loop i in [0..n) {make}]
 let saved=ps
 run(@ps 7)
 loop p in ps {{printl(p.{x} p.{y} p.{dx} p.{dy})}}
 loop p in saved {{printl(p.{x} p.{y} p.{dx} p.{dy})}}
}}
''')
    binaries = []
    for debug in (False, True):
        binary = tmp_path / ('scalar' if debug else 'guarded')
        built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        if not debug and not release and platform.machine().lower() in ('x86_64', 'amd64'):
            assert 'fn __h_reset_words_' in built.stdout, built.stdout
        binaries.append(binary)
    for values in ((1, 98, 2, -3), (-2**30, 2**30, 7, -9),
                   (-2**63, 2**63-1, 2**63-1, 1), (2**63-1, 0, 2**63-1, -1)):
        a, b, da, db = values
        for _ in range(7):
            na, nb = a+da, b+db
            if not 0 <= na < 100: da, na = -da, a
            if not 0 <= nb < 100: db, nb = -db, b
            a, b = na, nb
        for n in (0, 1, 17):
            expected = [' '.join(map(str, (a, b, da, db)))]*n + [' '.join(map(str, values))]*n
            for binary, sse in ((binaries[0], False), (binaries[0], True), (binaries[1], False)):
                env = dict(os.environ)
                env.pop('DEWY_NO_AVX', None)
                if sse: env['DEWY_NO_AVX'] = '1'
                ran = subprocess.run([binary, str(n), *map(str, values)], capture_output=True, text=True, env=env)
                assert ran.returncode == 0, ran.stderr
                assert ran.stdout.splitlines() == expected
    for binary in binaries:
        ran = subprocess.run([binary, '1', str(-2**63), '0', str(-2**63), '1'], capture_output=True, text=True)
        assert ran.returncode != 0 and 'integer overflow' in ran.stderr
