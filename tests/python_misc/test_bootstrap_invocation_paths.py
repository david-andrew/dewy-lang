"""Native cache names and process discovery agree with the compiler pair."""
import os
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_invocation_paths(tmp_path):
    source = tmp_path / 'paths.dewy'
    source.write_text(f'''
from reporting import Error
import p"{ROOT / 'dewy/bootstrap/invocation/cache.dewy'}" as cache
import p"{ROOT / 'dewy/bootstrap/invocation/platform.dewy'}" as platform
let main=(argv:array<string>):>int64=>{{
    $runtime_assert argv.length >=? 3
    let cwd=platform.kernel_path(false)
    if cwd is? Error {{cwd.fail}}
    let executable=platform.kernel_path(true)
    if executable is? Error {{executable.fail}}
    printl(cwd)
    printl(executable)
    printl(cache.artifact(argv[1] cwd '.udewy'))
    let error=platform.directories(argv[2])
    if error isnt? none {{error.fail}}
    let library=platform.library_root(executable cwd)
    if library is? Error {{library.fail}}
    printl(library)
    let compiler=platform.udewy(executable cwd)
    if compiler is? Error {{compiler.fail}}
    printl(compiler)
    return 0
}}
''')
    seed = source.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    cwd = tmp_path / 'working'
    cwd.mkdir()
    directory = cwd / 'cache/subdirectory'
    env = dict(os.environ, DEWY_LIBRARY_ROOT=str(ROOT / 'library'), DEWY_UDEWY=str(binary), PWD='/untrusted')
    for text in ['hello.dewy', 'a/../b/file.dewy', '__dewycache__/nested/file.udewy',
                 str(tmp_path / 'outside/😀.dewy'), str(cwd / 'local.dewy'),
                 str(tmp_path / 'working-cousin/file.dewy'), '.hidden']:
        result = subprocess.run([binary, text, directory], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == [str(cwd), str(binary),
            str(cache_artifact(Path(text), '.udewy', cwd=cwd)), str(ROOT / 'library'), str(binary)]
        assert directory.is_dir()
