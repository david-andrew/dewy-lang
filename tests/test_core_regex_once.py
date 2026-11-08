"""A literal regex is made once where it is written: in a loop it costs about what a regex made
before the loop does, and threads reaching the place at once each see a whole value."""
import subprocess

from tests.support import ROOT, compiler
from tests.test_secrets_taken import _counter
from tools.compiler import speed

LOOP = r'''main=(args:array<string>)=>{
    let n=0
    if args[1] =? "inside" {
        loop i in [0..20000) {
            let m="hello world {i}".find(regex(r"o w(or)ld"))
            if m isnt? Missing {n+=m.start}
        }
    } else {
        let r=regex(r"o w(or)ld")
        loop i in [0..20000) {
            let m="hello world {i}".find(r)
            if m isnt? Missing {n+=m.start}
        }
    }
    printl(n)
}
$runtime_checks
'''

PARALLEL = r'''hit=(i:int64):>int64=>{
    let m="item {i} key={i * 3}".find(regex(r"key=(\d+)"))
    if m isnt? Missing {return m.text.length}
    -1
}
# (reached only by the workers: never kept, each makes its own)
only=(i:int64):>int64=>{
    let m="{i}-{i}".find(regex(r"(\d+)-(\d+)"))
    if m isnt? Missing {return m.end}
    -1
}
total=(xs:array<int64>):>int64=>{
    let n:int64=0
    loop v in xs {n+=v}
    n
}
main=()=>{
    let xs:array<int64>=[loop i in [0..3000) i]
    printl(total(parallel_map(xs @hit)))
    printl(hit(5))
    printl(total(parallel_map(xs @hit)))
    printl(total(parallel_map(xs @only)))
    printl(total(parallel_map(xs @only)))
}
'''


def _build(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True,
                           timeout=180, check=False, env={**speed.clean_env(), 'DEWY_CORE_LIB': str(ROOT / 'lib')})
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def test_literal_regex_in_a_loop_costs_what_one_made_before_it_does(compiler, tmp_path):
    binary = _build(compiler, tmp_path, 'loop', LOOP)
    counter = _counter()
    inside, out = counter.run([str(binary), 'inside'], speed.clean_env())
    assert out.strip() == '80000'
    before, out = counter.run([str(binary), 'before'], speed.clean_env())
    assert out.strip() == '80000'
    # (made on every pass it was 2.8 times the cost)
    assert inside < before * 1.2, (inside, before)


def test_threads_reaching_one_literal_regex_each_see_a_whole_value(compiler, tmp_path):
    binary = _build(compiler, tmp_path, 'parallel', PARALLEL)
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=120, check=False)
    assert ran.returncode == 0, ran.stderr
    expected = sum(len(f'key={i * 3}') for i in range(3000))
    ends = sum(len(f'{i}-{i}') for i in range(3000))
    assert ran.stdout.split() == [str(expected), '6', str(expected), str(ends), str(ends)]
