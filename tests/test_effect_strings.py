"""String operations in effect rows (docs/design/effects.md, slice 4; compiler/effect_library.jo):
reading text costs nothing, building it allocates, and indexing, slicing, narrowing and
format specifications may fail unless the caller's facts or a literal rule it out. Integer
interpolation, big values included, cannot panic."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='run'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


MAIN = 'main = ():>(void | OutOfMemory) & no panics => {\n'

# Closed `& allocates` rows over text, and reading text under the strict lane's
# `no allocates & no panics`, in a `$bulletproof` module.
ACCEPT = '''$bulletproof
Bad:type = type of error & [message:string]
parse = (text:string):>(int32 | Bad) & allocates => {
    let n = to_int(text.trim() max_digits=6)
    if n is? NotAnInteger or n is? TooManyDigits return Bad["not a number"]
    if n <? -1000 or n >? 1000 return Bad["out of range"]
    int32(n)
}
show = (label:string n:int64 big:int x:float64 on:bool):>string & allocates => "{label}={n} {big} {x} {x:.2f} {on}"
fields = (line:string):>string & allocates => {
    let parts = line.split(",")
    let out = ""
    loop p in parts out = "{out}[{p.trim().upper()}]"
    if parts.length >? 1 out = "{out} second={parts[1]}"
    if line.length >? 2 out = "{out} head={line[0..2)} first={line[0]}"
    out
}
quiet = (text:string):>bool => text.length >? 2 and text.startswith("a") and text <? "b" and not text.is_empty
''' + MAIN + '''    let big = 10^30
    loop t in ["12" " -7 " "x" "5000"] {
        match parse(t) {
            v:int32 => printl"{v}"
            e:Bad => printl"{e.message}"
            <OutOfMemory> => return OutOfMemory
        }
    }
    let s = show("n" 42 big 1.5 true)
    if s is? OutOfMemory return OutOfMemory
    printl(s)
    let f = fields("ab,c d")
    if f is? OutOfMemory return OutOfMemory
    printl"{f} {quiet("abc")}"
    loop i in [0..3) printl"{i} {big - i}"
}
'''


@pytest.mark.core_quick
def test_string_rows_accept(compiler, tmp_path):
    result = run(compiler, tmp_path, ACCEPT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ('12\n-7\nnot a number\nout of range\n'
                             'n=42 1000000000000000000000000000000 1.5 1.50 true\n'
                             '[AB][C D] second=c d head=ab first=a true\n'
                             '0 1000000000000000000000000000000\n1 999999999999999999999999999999\n'
                             '2 999999999999999999999999999998\n'), result.stdout


# Each operation, in a function whose row does not permit its cost.
REJECT = {
    # building text allocates
    'interpolation': ('f = (n:int64):>string & no allocates => "{n}"\n', 'allocation exceeds'),
    'trim': ('f = (t:string):>string & no allocates => t.trim()\n', 'allocation exceeds'),
    'split': ('f = (t:string):>int64 & no allocates => t.split(",").length\n', 'allocation exceeds'),
    'big_int': ('f = (n:int):>int & no allocates => n * n\n', 'allocation exceeds'),
    # an unproven index, slice or narrowing may fail
    'index': ('f = (t:string):>string & allocates => t[3]\n', 'possible failure exceeds'),
    'slice': ('f = (t:string):>string & allocates => t[1..3]\n', 'possible failure exceeds'),
    'element': ('f = (t:string):>string & allocates => t.split(",")[5]\n', 'possible failure exceeds'),
    'narrow': ('f = (n:int):>int32 & allocates => int32(n)\n', 'possible failure exceeds'),
    # a specification known only at run time may be one the library refuses
    'spec': ('f = (x:float64 spec:string):>string & allocates => format(x spec)\n', 'possible failure exceeds'),
}


@pytest.mark.parametrize('name', REJECT)
def test_string_rows_reject(compiler, tmp_path, name):
    body, message = REJECT[name]
    result = run(compiler, tmp_path, '$runtime_checks\n' + body + 'main = () => printl(1)\n', 'check')
    assert result.returncode != 0 and "effect contract violation in 'f'" in result.stderr, result.stdout + result.stderr
    assert message in result.stderr, result.stderr


# The same reads pass a closed row that permits nothing.
def test_string_reads_no_effects(compiler, tmp_path):
    source = ('quiet = (t:string):>bool & no_effects => t.length >? 2 and t.endswith("c") and t =? "abc"\n'
              'main = () => printl(quiet("abc"))\n')
    result = run(compiler, tmp_path, source)
    assert result.returncode == 0 and result.stdout == 'true\n', result.stdout + result.stderr
