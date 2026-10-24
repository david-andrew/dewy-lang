"""Every string the runtime makes is followed by a 0 (the lexers read up to it; C reads a
string's data). Each is made where a freed block of its size class held 255s, so a constructor
that stops zeroing its memory must still write the 0."""
import subprocess

from tests.support import compiler  # noqa: F401

PROGRAM = '''
# a block of the size class of n bytes, its bytes 255, freed: the next of that class reuses it
dirty = (n: int):
    p = __alloc_raw(n)
    mem_set(p, 255, n)
    __free(p)

ends = (s: str) -> bool: data(s)[len(s)] == 0

path = args()[1]
dirty(24 + 40 + 1)
print(ends(__str_new(40) as str))
dirty(24 + 11)
b = "hello, " + "{len(args()) + 1000}"
print(ends(b))
dirty(24 + 7)
print(ends(b[2..9]))
d = "x" + "{len(args())}"
dirty(64)
loop i in [0..20): d += "yz"
print(ends(d))
write_file(path, "some contents of a file")
dirty(24 + 24)
if let e = read_file(path): print(ends(e) and len(e) == 23)
'''


def test_strings_end_with_zero(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'ends.jo'
    source.write_text(PROGRAM)
    binary = tmp_path / 'ends'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary, tmp_path / 'file.txt'], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'true\n' * 5
