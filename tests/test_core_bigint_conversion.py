"""Big integers convert to and from decimal text in subquadratic time (Karatsuba products,
divide and conquer over powers of 10^9 with Barrett division), and `to_int` refuses more
decimal digits than `max_digits=` (a million by default) as Python does since CVE-2020-10735."""
import random
import resource
import subprocess
import sys

from tests.support import compiler
from tools.compiler import speed
from tools.filelock import lock_exclusive

PROGRAM = r'''
main=(args:array<string>)=>{
    let mode=args[1]
    if mode =? "mul" {
        let a=to_int(args[2])
        let b=to_int(args[3])
        if a is? error or b is? error return
        printl"{a*b}"
    } else if mode =? "int" {
        let text=read_text(args[2]) or_throw
        let v=to_int(text max_digits=0)
        if v is? error {printl"none" return}
        let back="{v}"
        printl"{back =? text.trim()}"
    } else if mode =? "limit" {
        let digits:array<string>=[]
        loop i in [0..1000001) digits.push("7")
        let long=digits.join("")
        printl"{to_int(long) is? TooManyDigits} {to_int("123456" max_digits=5) is? TooManyDigits} {to_int("12345" max_digits=5) ?? 0}"
        printl"{to_int("-12" max_digits=2) ?? 0} {(to_int(long max_digits=0) ?? 0) % 1000}"
        let one:int=1
        printl(format((one << 4001)+5 "x").length)
    }
}
$runtime_checks
'''


def _build(compiler, tmp_path):
    source = tmp_path / 'conv.dewy'
    source.write_text(PROGRAM)
    binary = tmp_path / 'conv'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=180, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def test_products_and_text_match_python(compiler, tmp_path):
    sys.set_int_max_str_digits(0)
    binary = _build(compiler, tmp_path)
    rng = random.Random(11)
    for da, db in [(12, 7), (900, 900), (6000, 6000), (25000, 9000), (40000, 3), (30000, 30000)]:
        a = rng.randrange(10 ** (da - 1), 10 ** da)
        b = -rng.randrange(10 ** (db - 1), 10 ** db)
        ran = subprocess.run([binary, 'mul', str(a), str(b)], capture_output=True, text=True,
                             timeout=60, check=False)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.strip() == str(a * b), (da, db)


# Convert and print 300,000 digits: about 54 G user-space instructions today (digit by digit,
# about 300 G; the work is the same whatever the machine's load). Without perf counters, CPU
# seconds stand in (about 8 s today, about 50 s digit by digit): less exact, but not wall time.
INSTRUCTION_LIMIT = 100e9
CPU_SECONDS_LIMIT = 25


def _cost(binary, *arguments):
    """(stdout, cost, limit, unit) of running the binary: its instructions, else its CPU seconds."""
    try:
        speed.CACHE.mkdir(parents=True, exist_ok=True)
        with (speed.CACHE / 'speed.lock').open('w') as lock:
            lock_exclusive(lock)
            counter = speed.Counter('perf')
    except (RuntimeError, OSError, subprocess.CalledProcessError):
        counter = None
    if counter is not None:
        instructions, out = counter.run([str(binary), *arguments], speed.clean_env())
        return out, instructions, INSTRUCTION_LIMIT, 'instructions'
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    ran = subprocess.run([binary, *arguments], capture_output=True, text=True, timeout=300, check=False)
    assert ran.returncode == 0, ran.stderr
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    seconds = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
    return ran.stdout, seconds, CPU_SECONDS_LIMIT, 'CPU seconds'


def test_long_decimal_text_converts_quickly(compiler, tmp_path):
    sys.set_int_max_str_digits(0)
    binary = _build(compiler, tmp_path)
    digits = ''.join(random.Random(5).choice('0123456789') for _ in range(300_000))
    text = tmp_path / 'digits.txt'
    text.write_text('9' + digits)
    out, cost, limit, unit = _cost(binary, 'int', str(text))
    assert out.split()[0] == 'true'
    assert cost < limit, f'{cost:.3g} {unit} (limit {limit:.3g})'


def test_max_digits(compiler, tmp_path):
    binary = _build(compiler, tmp_path)
    ran = subprocess.run([binary, 'limit'], capture_output=True, text=True, timeout=120, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split('\n')[:3] == ['true true 12345', '-12 777', '1001']
