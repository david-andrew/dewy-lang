"""The source compiler keeps options separate from program arguments."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_invocation_options(tmp_path):
    source = tmp_path / 'options.dewy'
    source.write_text(f'''
from reporting import Error
import p"{ROOT / 'dewy/bootstrap/invocation/options.dewy'}" as options
let main=(argv:array<string>):>int64=>{{
    let request=options.parse(argv)
    if request is? Error {{printl(request.title); return 2}}
    printl(request.command)
    printl(if request.source is? none '' else request.source)
    printl(request.target)
    printl("{{request.compile_only}}:{{request.help}}:{{request.version}}:{{request.json}}:{{request.brief}}:{{request.build}}")
    printl(if request.debugger is? none '' else request.debugger)
    loop argument in request.arguments {{printl(argument)}}
    return 0
}}
''')
    seed = source.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    for args, expected in [
        (['-c', '--target', 'arm', 'file.dewy', '--help', '-t'], ['run', 'file.dewy', 'arm', 'true:false:false:false:false:false', '', '--help', '-t']),
        (['--', '-source.dewy', '--'], ['run', '-source.dewy', 'x86_64', 'false:false:false:false:false:false', '', '--']),
        (['--help'], ['run', '', 'x86_64', 'false:true:false:false:false:false', '']),
        (['--version'], ['run', '', 'x86_64', 'false:false:true:false:false:false', '']),
        (['test', '--json', '--brief'], ['test', '.', 'x86_64', 'false:false:false:true:true:false', '']),
        (['analyze', '--target=c', 'file.dewy'], ['analyze', 'file.dewy', 'c', 'false:false:false:false:false:false', '']),
        (['debug', '--debugger', 'lldb', '--build', 'file.dewy', '--flag'], ['debug', 'file.dewy', 'x86_64', 'false:false:false:false:false:true', 'lldb', '--flag']),
        (['update'], ['update', '', 'x86_64', 'false:false:false:false:false:false', '']),
    ]:
        result = subprocess.run([binary, *args], capture_output=True, text=True, timeout=20, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == expected
    for args in [[], ['--target'], ['-t', 'unknown', 'file.dewy'], ['test', '-c'], ['analyze', 'a', 'b'], ['update', 'file.dewy'], ['debug', '--debugger', 'unknown', 'file.dewy']]:
        result = subprocess.run([binary, *args], capture_output=True, text=True, timeout=20, check=False)
        assert result.returncode == 2, (args, result.stdout, result.stderr)
