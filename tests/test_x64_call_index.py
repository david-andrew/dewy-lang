"""Weighted call boundaries exclude endpoints and preserve explicit cold calls."""
import subprocess

from tests.support import ROOT, compiler


def test_release_call_boundary_index(compiler, tmp_path):
    source = tmp_path / 'call_index.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\nuse '{ROOT / 'compiler/ir.jo'}'\n"
                      f"use '{ROOT / 'compiler/ir_types.dewy'}'\n" + '''
loop length in [4, 65, 7, 129, 3]:
    loop stride in [1, 2, 5, 200]:
        ir_begin("calls", 0)
        ir.code = fill(Ins(.nop, 0, -1, 0, 0, 0, 0), length)
        analyze(true)
        call_pos.clear()
        call_w.clear()
        loop p in [0..length):
            if p % stride == 0:
                cold = p % 3 == 0
                ir.code[p] = Ins(.call, 0, -1, 0, 0, if cold: 2 else: 0, 0)
                call_pos.push(p)
                call_w.push(if cold: 1 else: 1 << (p % 7))
        allocate_release()
        loop s in [-1..length):
            loop e in [0..length + 1):
                weight = 0
                count = 0
                cold = false
                loop k in [0..call_pos.len()):
                    p = call_pos[k]
                    if s < p and p < e:
                        count += 1
                        weight += call_w[k]
                        cold = ir.code[p].c == 2
                if count == 1 and cold: weight = -1
                assert(ra_cross_w(s, e) == weight, "call boundary")
    ir_begin("empty", 0)
    analyze(true)
    allocate_release()
    assert(ra_cross_w(-1, 0) == 0, "empty after reuse")
print("ok")
''')
    binary = tmp_path / 'call_index'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == 'ok\n', ran.stdout + ran.stderr
