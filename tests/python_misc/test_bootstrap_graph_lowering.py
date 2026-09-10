"""Validate module proofs and startup before native graph legalization."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_graph_initialization_and_entry(tmp_path):
    driver = tmp_path / 'graph.dewy'
    driver.write_text(f'''
from reporting import Error
import p"{ROOT / 'dewy/bootstrap/semantic/modules.dewy'}" as modules
import p"{ROOT / 'dewy/bootstrap/backend/udewy/graph.dewy'}" as graph
import p"{ROOT / 'dewy/bootstrap/backend/udewy/program.dewy'}" as program
main=(argv:array<string>):>int64=>{{
    $runtime_assert argv.length =? 2
    let engine=modules.Engine[]
    let entry=modules.load(argv[1] @engine)
    if entry is? Error {{entry.fail}}
    let lowered=graph.lower_validated(entry @engine)
    if lowered is? Error {{lowered.fail}}
    let code=program.render(lowered.program lowered.input)
    if code is? Error {{code.fail}}
    printl(code)
    return 0
}}
''')
    seed = driver.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(driver)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    cases = [
        ({
            'core.dewy': 'let count:int64=0\nlet tick=():>int64=>{count+=1 return count}',
            'left.dewy': 'import p"core.dewy" as core\nlet value:int64=core.tick()',
            'right.dewy': 'import p"./core.dewy" as core\nlet value:int64=core.tick()',
            'entry.dewy': 'import p"left.dewy" as left\nimport p"right.dewy" as right\nimport p"core.dewy" as core\nlet main=():>int64=>left.value+right.value+core.count+37',
        }, 42),
        ({
            'dependency.dewy': 'let main=():>int64=>99\nlet initialized:int64=main()',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet value=dependency.initialized',
        }, 0),
        ({
            'left.dewy': 'let answer=():>int64=>20',
            'right.dewy': 'let answer=():>int64=>22',
            'entry.dewy': 'import p"left.dewy" as left\nimport p"right.dewy" as right\nlet main=():>int64=>left.answer()+right.answer()',
        }, 42),
        ({
            'dependency.dewy': 'let unused=():>array<int64>=>[1 2]',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet main=():>int64=>42',
        }, 42),
    ]
    for index, (files, expected) in enumerate(cases):
        folder = tmp_path / f'case-{index}'
        folder.mkdir()
        for name, text in files.items():
            (folder / name).write_text(text)
        result = subprocess.run([binary, folder / 'entry.dewy'], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        output = folder / 'program.udewy'
        output.write_text(result.stdout)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], timeout=10, check=False)
        assert run.returncode == expected
    bad = tmp_path / 'bad'
    bad.mkdir()
    (bad / 'dependency.dewy').write_text('let make=():>array<int64>=>[1 2]\nlet value=make()')
    (bad / 'entry.dewy').write_text('import p"dependency.dewy" as dependency\nlet main=():>int64=>42')
    result = subprocess.run([binary, bad / 'entry.dewy'], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode != 0
    assert str(bad / 'dependency.dewy') in result.stderr

    for index, (body, title) in enumerate([
        ('let f=(n:int64):>int64=>{ $assert n >? 0\nreturn n }', 'cannot prove assertion'),
        ('let main=(n:int64):>int64=>n', '`main` must take no arguments'),
        ('let x:int=9223372036854775807\nlet main=():>int=>x+1', 'cannot prove this integer fits'),
        ('call(); let call=():>int64=>42', 'before'),
    ]):
        path = tmp_path / f'rejected-{index}.dewy'
        path.write_text(body)
        result = subprocess.run([binary, path], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode != 0, body
        assert title in result.stderr, result.stdout + result.stderr
