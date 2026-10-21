"""Stack callback proofs must reject every retaining/value-copy boundary."""
import pytest

from tests.support import compiler, run_value_batch


CASES = {
    'stack-allocation-and-cleanup': '''Callback:type=():>int64
invoke=(callback:Callback before:int64):>int64=>{
 if alloc_count() not=?before return 1
 return callback()
}
exercise=(n:int64):>int64=>{
 let values:array<int64>=[n]
 let before=alloc_count()
 let callback=()=>values[0]
 if alloc_count() not=?before return 2
 return invoke(@callback before)
}
main=()=>{
 let before=alloc_count()
 loop i in [0..20) {
  if exercise(42) not=?42 return 3
  if alloc_count() not=?before return 4
 }
 return 42
}''',
    'array-after-creation': '''Callback:type=():>int64
make=(n:int64):>array<Callback>=>{
 let callback=()=>n
 let saved:array<Callback>=[]
 saved.push(@callback)
 return saved
}
main=()=>{let saved=make(42) return saved[0]()}''',
    'nested-return': '''make=(n:int64)=>{
 let inner=()=>{let callback=()=>n return @callback}
 return inner()
}
main=()=>{let callback=make(42) return callback()}''',
    'captured-by-closure': '''make=(n:int64)=>{
 let callback=()=>n
 let outer=()=>callback()
 return @outer
}
main=()=>{let callback=make(42) return callback()}''',
    'retaining-parameter': '''Callback:type=():>int64
let saved:array<Callback>=[]
retain=(callback:Callback)=>{saved.push(@callback)}
make=(n:int64)=>{let callback=()=>n retain(@callback)}
main=()=>{make(42) return saved[0]()}''',
    'borrowed-managed-capture': '''Callback:type=():>int64
invoke=(callback:Callback):>int64=>callback()+callback()
main=()=>{
 let total=0
 loop i in [0..21) {
  let values:array<int64>=[i i+1]
  let callback=()=>values[1]-values[0]
  total+=invoke(@callback)
 }
 return total
}''',
    'mutable-snapshot': '''Callback:type=():>int64
invoke=(callback:Callback):>int64=>callback()+callback()
main=()=>{
 let n:int64=0
 let callback=()=>{n+=1 return n}
 let a=invoke(@callback)
 let b=invoke(@callback)
 return if a=?3 and b=?3 and callback()=?1 42 else 1
}''',
    'shared-capture': '''Callback:type=():>int64
invoke=(callback:Callback):>int64=>callback()+callback()
main=()=>{
 let n:int64=0
 let callback=($capture @n)=>{n+=1 return n}
 let a=invoke(@callback)
 let b=invoke(@callback)
 return if a=?3 and b=?7 and n=?4 42 else 1
}''',
    'forwarded-retaining-parameter': '''Callback:type=():>int64
let saved:array<Callback>=[]
retain=(callback:Callback)=>{saved.push(@callback)}
forward=(callback:Callback)=>retain(@callback)
make=(n:int64)=>{let callback=()=>n forward(@callback)}
main=()=>{make(42) return saved[0]()}''',
    'conditional-call': '''Callback:type=():>int64
invoke=(callback:Callback choose:bool):>int64=>{
 if choose return callback()
 return 0
}
main=()=>{
 let n:int64=21
 let callback=()=>n
 return invoke(@callback true)+invoke(@callback true)
}''',
    'owner-capture-drop': '''drops:int64=0
Handle=type of [value:int64
 $__drop__
 release=():>void=>{drops+=1}
]
exercise=()=>{
 let owner=Handle[42]
 let callback=()=>owner.value
 $runtime_assert callback()=?42 and drops=?0
}
main=()=>{exercise() return if drops=?1 42 else 1}''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_stack_callback_boundaries(compiler, tmp_path, release, target):
    for name, (code, diagnostic) in run_value_batch(
            compiler, tmp_path, CASES, release, target).items():
        assert code == '42', f'{name}: {diagnostic or code}'


@pytest.mark.core_quick
def test_known_callback_ir(compiler, tmp_path):
    """After inlining, only a stable propagated address changes call ABI."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'devirtualize.jo'
    source.write_text(f"use '{root}/compiler/ir.jo'\nuse '{root}/compiler/opt.jo'\n" + '''
ir_begin("known", 0)
ir.vtypes = [i8(0), i8(0), i8(0), i8(0)]
ir.args = [i32(1)]
ir.code = [Ins(.faddr, 0, 0, 0, 0, 0, 123),
           Ins(.iconst, 0, 1, 0, 0, 0, 41),
           Ins(.mov, 0, 3, 0, 0, 0, 0),
           Ins(.calli, 0, 2, 0, 1, 3, 0),
           Ins(.ret, 0, 0, 2, 0, 0, 0)]
optimize()
dump_ir()
ir_begin("dynamic", 1)
ir.nparams = 1
ir.vtypes = [i8(0), i8(0)]
ir.code = [Ins(.calli, 0, 1, 0, 0, 0, 0), Ins(.ret, 0, 0, 1, 0, 0, 0)]
optimize()
dump_ir()
ir_begin("foreign", 2)
ir.vtypes = [i8(0), i8(0)]
ir.code = [Ins(.faddr, 0, 0, 0, 0, 0, 123),
           Ins(.callc, 0, 1, 0, 0, 0, 0), Ins(.ret, 0, 0, 1, 0, 0, 0)]
optimize()
dump_ir()
''')
    binary = tmp_path / 'devirtualize'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    known, dynamic, foreign = ran.stdout.split('fn ')[1:]
    assert 'calli' not in known and 'c=0 imm=123' in known, known
    assert 'calli' in dynamic, dynamic
    assert 'callc' in foreign, foreign
