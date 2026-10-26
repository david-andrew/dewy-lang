"""Dictionaries resist hash flooding: keys crafted to collide under the old unkeyed hashes
(an invertible integer finalizer, a record hash whose second field cancels the first) stay
fast, since slots come from a hash keyed per process. `hash` itself stays the same each run."""
import resource
import subprocess

from tests.support import compiler

MASK = (1 << 64) - 1
COUNT = 100_000


def _unfmix(y):
    # inverse of the murmur3 finalizer the integer keys used to hash with
    inv1 = pow(0xFF51AFD7ED558CCD, -1, 1 << 64)
    inv2 = pow(0xC4CEB9FE1A85EC53, -1, 1 << 64)
    h = y ^ (y >> 33)
    h = (h * inv2) & MASK
    h ^= h >> 33
    h = (h * inv1) & MASK
    return h ^ (h >> 33)


def _signed(u):
    return u - (1 << 64) if u >> 63 else u


def _old_record_mix(h, x):
    m = ((h ^ x) * 0x100000001B3) & MASK
    return m ^ (m >> 29)


def _int_keys():
    # every key's old hash is a multiple of 2^24: one slot chain
    return [str(_signed(_unfmix(i << 24))) for i in range(1, COUNT + 1)]


def _record_keys():
    # the second field cancels the first: every key had the same full 64-bit hash
    h0 = 0xCBF29CE484222325
    return [f'{a} {_signed(_old_record_mix(h0, a) ^ (1 << 40))}' for a in range(1, COUNT + 1)]


INTS = r'''
main=(args:array<string>)=>{
    let text=read_text(args[1]) or_throw
    let d:dict<int64 int64>=[]
    let e:dict<int int64>=[]
    loop line in text.split("\n") {
        if line.length >? 0 {
            let k=to_int(line) ?? 0
            d[k as int64]=1
            e[k]=1
        }
    }
    printl"{d.length} {e.length}"
}
$runtime_checks
'''

RECORDS = r'''
P:type=[a:int64 b:int64]
main=(args:array<string>)=>{
    let text=read_text(args[1]) or_throw
    let d:dict<P int64>=[]
    loop line in text.split("\n") {
        if line.length >? 0 {
            let parts=line.split(" ")
            d[P[(to_int(parts[0]) ?? 0) as int64 (to_int(parts[1]) ?? 0) as int64]]=1
        }
    }
    printl"{d.length}"
}
$runtime_checks
'''

STABLE = r'''
P:type=[a:int64 b:string]
main=()=>{
    let d:dict<string int64>=[]
    loop i in [0..50) {d["k{(i*37)%50}"]=i}
    let keys:array<string>=[]
    loop k in d.keys() {keys.push(k)}
    printl"{hash(12345)} {hash("abc")} {hash(P[1 "x"])} {keys[0]} {keys[1]} {keys[49]}"
}
$runtime_checks
'''


def _run_cpu(binary, keys):
    """Run once; return the result and the child's CPU seconds (user+sys), which a loaded
    machine inflates far less than wall time."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    ran = subprocess.run([binary, keys], capture_output=True, text=True, timeout=120, check=False)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return ran, (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)


def _assert_flat(binary, tmp_path, crafted, control, expected):
    """Crafted keys must cost about what the same number of ordinary keys cost. Quadratic
    chains made them ~80x slower (8 s against 0.1 s), so a 10x factor plus 0.5 s of slack
    separates the two by a wide margin on any machine, since both runs share the load."""
    (tmp_path / 'crafted.txt').write_text('\n'.join(crafted) + '\n')
    (tmp_path / 'control.txt').write_text('\n'.join(control) + '\n')
    controls = []
    for _ in range(2):
        ran, seconds = _run_cpu(binary, tmp_path / 'control.txt')
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.split() == expected
        controls.append(seconds)
    ran, seconds = _run_cpu(binary, tmp_path / 'crafted.txt')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split() == expected
    assert seconds < 10 * min(controls) + 0.5, (seconds, controls)


def _build(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True,
                           text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def test_crafted_integer_keys_stay_fast(compiler, tmp_path):
    control = [str(i * 7919) for i in range(1, COUNT + 1)]
    _assert_flat(_build(compiler, tmp_path, 'ints', INTS), tmp_path, _int_keys(), control, [str(COUNT)] * 2)


def test_crafted_record_keys_stay_fast(compiler, tmp_path):
    control = [f'{a} {a * 7919}' for a in range(1, COUNT + 1)]
    _assert_flat(_build(compiler, tmp_path, 'records', RECORDS), tmp_path, _record_keys(), control, [str(COUNT)])


def test_hash_and_iteration_are_the_same_every_run(compiler, tmp_path):
    binary = _build(compiler, tmp_path, 'stable', STABLE)
    first = subprocess.run([binary], capture_output=True, text=True, timeout=30, check=True).stdout
    second = subprocess.run([binary], capture_output=True, text=True, timeout=30, check=True).stdout
    assert first == second
    assert first.split()[3:] == ['k0', 'k37', 'k13']
