"""Native test annotation extraction produces checked, executable runners."""
import json
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen, codegen_inner
from dewy.reporting import SrcFile
from dewy.semantic import check
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_test_runner_source(tmp_path):
    driver = tmp_path / 'runner-source.dewy'
    driver.write_text(f'''
from reporting import Error, SrcFile
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/test_syntax.dewy'}" as tests
let main=(argv:array<string>):>int64=>{{
    $runtime_assert argv.length =? 2
    let text=p(argv[1]).read_text
    $runtime_assert text is? string
    let source=SrcFile[argv[1] text]
    let parsed=parser.parse(source)
    if parsed is? Error {{parsed.fail}}
    let prepared=tests.prepare(source parsed run_tests=true)
    if prepared is? Error {{prepared.fail}}
    print(prepared.source.body)
    return 0
}}
''')
    seed = driver.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(driver)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    cases = [
        ('$test\nlet works=()=>{$expect 1+1 =? 2}\nlet main=():>int64=>77', 1, 0),
        ('$test(cases=(1 2 (-3)))\nlet nonzero=(n:int64)=>{$expect n not=? 0}', 3, 0),
        ('$test(cases=[[a=1 b=2] [a=2 b=1]])\nlet order=(a:int64 b:int64)=>{$expect a <? b}', 1, 1),
        ('let cases=[1 2]\n$test(cases=cases)\nlet positive=(n:int64)=>{$expect n >? 0}', 2, 0),
        ('let values=():>array<int64>=>[1 2]\n$test(cases=values())\nlet positive=(n:int64)=>{$expect n >? 0}', 2, 0),
        ('let value=42', 0, 0),
    ]
    for index, (body, passed, failed) in enumerate(cases):
        source = tmp_path / f'case-{index}.dewy'
        source.write_text(body)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        augmented = SrcFile(source, result.stdout)
        ast = check.typecheck_and_resolve(augmented, include_prelude=True)
        output = tmp_path / f'case-{index}.udewy'
        output.write_text(codegen_inner(ast, augmented, entry_name='__dewy_test_main'))
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        run = subprocess.run([cache_artifact(output).resolve(), '--json'], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == failed, run.stdout + run.stderr
        assert json.loads(run.stdout.splitlines()[-1]) == {'passed': passed, 'failed': failed}
    for index, body in enumerate(['$test', '$test\nlet value=42',
            '$test\nlet f=(x:int64)=>{}', '$test(cases=[1])\nlet f=()=>{}',
            '$test(other=[1])\nlet f=(x:int64)=>{}', '$test(cases=[1] cases=[2])\nlet f=(x:int64)=>{}']):
        source = tmp_path / f'bad-{index}.dewy'
        source.write_text(body)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode != 0, body
