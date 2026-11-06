"""Package resolution, fetching, pins and `add` match frozen Jo, offline in a temporary directory."""
import os
import shutil
import subprocess

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.skipif(shutil.which('git') is None, reason='git is not installed')

DRIVER = r'''
use 'pkg.jo'
show = ():
    keys = pkg_dirs.keys(); keys.sort()
    loop k in keys: print("dir {k} {pkg_dirs[k]}")
    keys = pkg_errs.keys(); keys.sort()
    loop k in keys: print("err {k} {pkg_errs[k]}")
    print(pkg_specs.len())
main = ():
    a = args()
    print(a[1..])
    if a[1] == "add":
        pkg_add_main(a)
        return
    print(user_cache_dir())
    print(pkg_cache())
    print(core_cache())
    print(file_exists(core_cache()))
    pkg_mkdirs(""); pkg_mkdirs("a/b/c"); pkg_mkdirs("a/b/c"); print(file_exists("a/b/c/."))
    print(pkg_git(["--version"]).0)
    print(pkg_git(["no-such-command"]).0 != 0)
    url = a[2]
    print(pkg_resolve(url, "") == a[3])
    print(pkg_resolve(url, "main") == a[3])
    print(pkg_resolve(url, "v1") == a[3])
    print(pkg_resolve(url, a[3]))
    print(pkg_resolve(url, "missing")); print(pkg_why)
    print(pkg_resolve(url, "two")); print(pkg_why)
    print(pkg_resolve("/no/such/repository", "")); print(pkg_why)
    print(pkg_get(url, a[3], "fetched"))
    print(read_file("fetched/.dewy-fetched") ?? "none")
    print(read_file("fetched/lib.jo") ?? "none")
    print(pkg_get("/no/such/repository", a[3], "failed"))
    # Resolving all: directories, missing ones, bad sources, git packages pinned and locked.
    write_file("main.jo", "")
    pkg_resolve_all("main.jo"); show()
    pkg_specs = [PkgSpec("local", "local_pkg", "", "."), PkgSpec("gone", "no_dir", "", "."), PkgSpec("dash", "-x", "", "."), PkgSpec("abs", a[4], "", "/ignored")]
    pkg_resolve_all("main.jo"); show()
    print(read_file("dewy.lock") ?? "none")
    pkg_dirs = {}; pkg_errs = {}
    git_url = "file://{url}"
    pkg_specs = [PkgSpec("offline", git_url, "", ".")]
    pkg_resolve_all("main.jo"); show()
    pkg_errs = {}
    pkg_fetch = true
    pkg_specs = [PkgSpec("online", git_url, "main", "."), PkgSpec("bad", git_url, "missing", "."), PkgSpec("unsafe", git_url, "-x", ".")]
    pkg_resolve_all("sub/main.jo"); show()
    make_dirs("sub")
    pkg_dirs = {}; pkg_errs = {}
    pkg_specs = [PkgSpec("online", git_url, "main", ".")]
    pkg_resolve_all("sub/main.jo"); show()
    print(read_file("sub/dewy.lock") ?? "none")
    pkg_dirs = {}; pkg_errs = {}
    pkg_fetch = false
    pkg_specs = [PkgSpec("online", git_url, "main", ".")]
    pkg_resolve_all("sub/main.jo"); show()
    # A package's own packages come along.
    pkg_specs = []
    pkg_scan_main("x", "scanned")
    print(pkg_specs.len())
    print(pkg_main("one", "one_file") ?? "none")
    print(pkg_main("named", "two_files") ?? "none")
    print(pkg_main("other", "two_files") ?? "none")
    pkg_scan("program.jo", "build:\n    a = package(\"../a\")\n")
    print(pkg_specs.len())
    print("pkg ok")
'''


def git(directory, *arguments):
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'a', 'GIT_AUTHOR_EMAIL': 'a@b', 'GIT_COMMITTER_NAME': 'a', 'GIT_COMMITTER_EMAIL': 'a@b',
           'GIT_AUTHOR_DATE': '2026-01-01T00:00:00Z', 'GIT_COMMITTER_DATE': '2026-01-01T00:00:00Z'}
    return subprocess.run(['git', '-C', directory, *arguments], capture_output=True, text=True, check=True, env=env).stdout.strip()


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_pkg_ops_twins(compiler, tmp_path, release, monkeypatch):  # noqa: F811
    repository = tmp_path / 'repository'
    repository.mkdir()
    git(repository, 'init', '-q', '-b', 'main')
    (repository / 'lib.jo').write_text('value = 1\n')
    git(repository, 'add', '.')
    git(repository, 'commit', '-qm', 'one')
    git(repository, 'tag', 'v1')
    git(repository, 'tag', 'two')
    git(repository, 'branch', 'two')
    commit = git(repository, 'rev-parse', 'HEAD')
    run = tmp_path / 'run'
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    monkeypatch.setenv('DEWY_PACKAGES', str(tmp_path / 'packages'))

    def fresh():
        for directory in (run, tmp_path / 'cache', tmp_path / 'packages'):
            shutil.rmtree(directory, ignore_errors=True)
        (run / 'local_pkg').mkdir(parents=True)
        (run / 'local_pkg/local.jo').write_text('build:\n    inner = package("../inner")\n')
        (run / 'inner').mkdir()
        (run / 'one_file').mkdir()
        (run / 'one_file/only.jo').write_text('')
        (run / 'two_files').mkdir()
        (run / 'two_files/named.jo').write_text('')
        (run / 'two_files/second.jo').write_text('')
        (run / 'two_files/notes.txt').write_text('')
        (run / 'scanned').mkdir()
        (run / 'scanned/a.jo').write_text('build:\n    a = package("../inner")\n')
        (run / 'scanned/b.txt').write_text('build:\n    b = package("../inner")\n')
        (run / 'game.jo').write_text('value = 1\n')
        return run

    def files(directory):
        return sorted((str(p.relative_to(directory)), p.read_bytes()) for p in directory.rglob('*')
                      if p.is_file() and '.git' not in p.parts)

    add = [(('add',), 2), (('add', 'inner'), 0), (('add', 'inner', 'my_name', 'game.jo'), 0), (('add', 'no_dir', 'x'), 1), (('add', 'inner', 'value', 'missing.jo'), 0)]
    outputs = compare_narrow(compiler, tmp_path, release, ('source_types', 'manifest', 'module_paths', 'json_doc', 'pkg_ops'), DRIVER,
                             doubles={'pkg.jo': (ROOT / 'compiler/pkg.jo').read_text().replace("use 'util.jo'\n", '').replace("use 'lex.jo'\n", '')},
                             run_in=fresh, observe=files,
                             invocations=[(('all', str(repository), commit, str(run / 'inner')), 0)] + add)
    assert outputs[0].endswith(b'pkg ok\n')
    for text in (b'names both', b'has no', b'could not reach', b'is not a directory or a git URL', b'there is no directory', b'not fetched yet'):
        assert text in outputs[0], text
