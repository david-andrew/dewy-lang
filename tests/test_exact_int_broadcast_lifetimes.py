"""Producer proofs follow immutable values and preserve owned bigint outliers."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_broadcast_producer_lifetimes(compiler, tmp_path, release):
    source = tmp_path / 'lifetimes.dewy'
    source.write_text('''$runtime_checks
const N:int64=17
plain=(m:array<int64 length=[N N]>):>int=>{
 let h=m .+ 1
 let g=h .* m .- h
 return sum(g)+sum(h)
}
changed=(m:array<int64 length=[N N]> x:int where:int64):>int=>{
 let h=m .+ 1
 let saved=h
 if where=?0 h[0 0]=x
 let g=h .* m .- h
 if where=?1 g[0 0]=x
 if where=?2 h[0 0]=x
 return sum(g)+sum(h)+sum(saved)
}
minimum=(x:int):>int=>{
 let a=[x x]
 let b=min.(a a)
 return sum(b)
}
main=(args:array<string>)=>{
 let x=to_int(args[1]) ?? 0
 let where=int64(to_int(args[2]) ?? 0)
 let m=reshape([loop i in [0..N*N) int64(i%31-15)] N N)
 let p=plain(m)
 let c=changed(m x where)
 let v=minimum(x)
 let before=alloc_count()
 loop _ in [0..8) {plain(m); changed(m x where); minimum(x);}
 let after=alloc_count()
 printl(p c v after-before)
}
''')
    binaries = []
    for debug in (False, True):
        binary = tmp_path / ('scalar' if debug else 'guarded')
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        binaries.append(binary)
    m = [i % 31 - 15 for i in range(17*17)]
    original_h = [v+1 for v in m]
    plain = sum(v*v-1 for v in m)+sum(original_h)
    for x in (-5, 2**130, -2**130):
        for where in range(3):
            h = original_h[:]
            if where == 0: h[0] = x
            g = [a*(b-1) for a, b in zip(h, m)]
            if where == 1: g[0] = x
            if where == 2: h[0] = x
            expected = f'{plain} {sum(g)+sum(h)+sum(original_h)} {2*x} 0'
            for binary, sse in ((binaries[0], False), (binaries[0], True), (binaries[1], False)):
                env = dict(os.environ)
                env.pop('DEWY_NO_AVX', None)
                if sse: env['DEWY_NO_AVX'] = '1'
                ran = subprocess.run([binary, str(x), str(where)], capture_output=True, text=True, env=env)
                assert ran.returncode == 0, ran.stderr
                assert ran.stdout.strip() == expected
