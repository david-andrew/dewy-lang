"""The library's obligations follow its own policy, however its functions came to be analyzed."""
import os
import subprocess

from tests.support import ROOT, compiler  # noqa: F401

# A totaldict assignment and a socket call make the facts pass analyze library
# functions (map insertion, `int32` narrowing in net.dewy) for their own
# requests; the program's own unproven index is the only error.
SOURCE = '''import net
const RADIX:totaldict<'0b'|'0x' int64> = ['0b' -> 2 '0x' -> 16]
let names:totaldict<-1|0|1 string> = [-1 -> "neg" 0 -> "zero" 1 -> "pos"]
names[1] = "plus"
pick = (xs:array<int64> i:int64):>int64 => xs[i]
main = ():>void | net.NetError => {
    printl(RADIX['0x'] + pick([1 2 3] 1))
    let server = net.tcp_listen(0) or_throw
    printl(server.port >? 0)
}
'''


def test_library_obligations_stay_the_librarys(compiler, tmp_path):
    source = tmp_path / 'program.dewy'
    source.write_text(SOURCE)
    for policy in ('require-static-all', 'require-static-measure'):
        result = subprocess.run([compiler, f'--internal-fact-policy={policy}', 'check', 'program.dewy'],
                                text=True, capture_output=True, timeout=60, cwd=tmp_path)
        errors = [line for line in result.stderr.splitlines() if ': error: ' in line]
        assert errors and all(line.startswith('program.dewy:5:') for line in errors), result.stderr
