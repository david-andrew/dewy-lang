"""Packages end to end: a build block's `package(...)` lines, git fetching, the `dewy.lock` pins
and the package cache, all offline (directories and git repositories made under tmp_path).

Packages are a feature of `.jo` programs for now: a Dewy-surface file's build block is not
read for `package(...)` lines.
"""
import os
import re
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

pytestmark = pytest.mark.skipif(shutil.which('git') is None, reason='git is not installed')

HEX40 = re.compile(r'[0-9a-f]{40}')


class Sandbox:
    """A program directory, a package cache and a user cache, none of them outside tmp_path."""

    def __init__(self, compiler, tmp_path):
        self.compiler = compiler
        self.root = tmp_path
        self.prog = tmp_path / 'prog'
        self.prog.mkdir()
        self.cache = tmp_path / 'packages'
        self.env = {
            'PATH': os.environ['PATH'],
            'HOME': str(tmp_path / 'home'),
            'XDG_CACHE_HOME': str(tmp_path / 'xdg'),
            'DEWY_PACKAGES': str(self.cache),
            'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_CONFIG_SYSTEM': os.devnull,
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_NAME': 'T', 'GIT_AUTHOR_EMAIL': 't@example.com',
            'GIT_COMMITTER_NAME': 'T', 'GIT_COMMITTER_EMAIL': 't@example.com',
        }

    def git(self, repo, *args):
        done = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, env=self.env,
                              timeout=60, check=False)
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    def repo(self, name, files):
        """A git repository with one commit of files, tagged v1 (annotated)."""
        path = self.root / name
        path.mkdir()
        self.git(path, '-c', 'init.defaultBranch=main', 'init', '-q')
        self.commit(path, files, 'one')
        self.git(path, 'tag', '-a', 'v1', '-m', 'v1')
        return path

    def commit(self, path, files, message):
        for file, text in files.items():
            (path / file).write_text(text)
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-q', '-m', message)
        return self.git(path, 'rev-parse', 'HEAD')

    def program(self, packages, body='print(lib.greet())', name='main.jo'):
        """main.jo with a build block of `name = package(...)` lines and a main that runs body."""
        lines = ''.join(f'    {n} = package({args})\n' for n, args in packages.items())
        imports = ''.join(f'import {n}\n' for n in packages)
        (self.prog / name).write_text(f'build:\n{lines}\n{imports}main = ():\n    {body}\n')
        return self.prog / name

    def run(self, *args, cwd=None):
        return subprocess.run([self.compiler, *args], capture_output=True, text=True, env=self.env,
                              timeout=120, check=False, cwd=cwd or self.prog)

    def lock(self):
        text = (self.prog / 'dewy.lock').read_text()
        return [line for line in text.splitlines() if line and not line.startswith('#')]


@pytest.fixture
def box(compiler, tmp_path):
    return Sandbox(compiler, tmp_path)


def url(path):
    return f'"file://{path}"'


def test_directory_package_builds_and_runs(box):
    pkg = box.root / 'shapes'
    pkg.mkdir()
    (pkg / 'shapes.jo').write_text('area = (w: int, h: int) -> int: w * h\n')
    (pkg / 'extra.jo').write_text('double = (x: int) -> int: x * 2\n')
    source = box.prog / 'main.jo'
    source.write_text('build:\n    shapes = package("../shapes")\n\nimport shapes\nimport \'shapes/extra.jo\'\n'
                      'main = ():\n    print(extra.double(shapes.area(3, 4)))\n')
    built = box.run('build', source, '-o', box.prog / 'out')
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([box.prog / 'out'], capture_output=True, text=True, env=box.env, timeout=60, check=False)
    assert ran.stdout == '24\n'
    # a directory package is used in place: no pin, nothing fetched
    assert not (box.prog / 'dewy.lock').exists()
    assert not box.cache.exists()


def test_directory_package_resolves_from_the_program_not_the_working_directory(box):
    pkg = box.root / 'lib'
    pkg.mkdir()
    (pkg / 'lib.jo').write_text('greet = () -> str: "from lib"\n')
    source = box.program({'lib': '"../lib"'})
    ran = box.run(source, cwd=box.root)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'from lib\n'


def test_a_package_brings_the_packages_its_own_build_block_names(box):
    (box.root / 'b').mkdir()
    (box.root / 'b' / 'b.jo').write_text('bval = () -> int: 7\n')
    (box.root / 'a').mkdir()
    (box.root / 'a' / 'a.jo').write_text('build:\n    b = package("../b")\n\nimport b\naval = () -> int: b.bval() + 1\n')
    source = box.program({'a': '"../a"'}, body='print(a.aval())')
    ran = box.run(source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '8\n'


def test_missing_directory_package_is_an_error_naming_it(box):
    source = box.program({'lib': '"../nothere"'})
    ran = box.run(source)
    assert ran.returncode != 0
    assert "package 'lib': there is no directory" in ran.stderr


def test_git_package_pinned_by_tag_writes_a_lock_and_fills_the_cache(box):
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "v1"\n'})
    source = box.program({'lib': f'{url(src)}, "v1"'})
    ran = box.run(source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'v1\n'
    assert 'fetching lib' in ran.stderr
    (line,) = box.lock()
    name, where, ref, commit = line.split(' ')
    assert (name, where, ref) == ('lib', f'file://{src}', 'v1')
    assert HEX40.fullmatch(commit)
    # the fetch is in the cache we named, keyed by the commit, and is the only thing written there
    (entry,) = box.cache.iterdir()
    assert entry.name.endswith('@' + commit[:12])
    assert (entry / 'lib.jo').read_text() == 'greet = () -> str: "v1"\n'
    assert (entry / '.dewy-fetched').read_text() == commit


def test_annotated_tag_is_pinned_to_the_commit_it_names(box):
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "v1"\n'})
    assert box.run(box.program({'lib': f'{url(src)}, "v1"'})).returncode == 0
    assert box.lock()[0].split(' ')[3] == box.git(src, 'rev-parse', 'v1^{commit}')


def test_second_build_reuses_the_pin_when_the_tag_moves(box):
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "v1"\n'})
    source = box.program({'lib': f'{url(src)}, "v1"'})
    assert box.run(source).stdout == 'v1\n'
    lock = (box.prog / 'dewy.lock').read_text()
    # the tag moves to new code
    second = box.commit(src, {'lib.jo': 'greet = () -> str: "v2"\n'}, 'two')
    box.git(src, 'tag', '-f', '-a', 'v1', '-m', 'v1 again')
    assert box.git(src, 'rev-parse', 'v1^{commit}') == second
    ran = box.run(source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'v1\n'
    assert 'fetching' not in ran.stderr
    assert (box.prog / 'dewy.lock').read_text() == lock
    assert len(list(box.cache.iterdir())) == 1
    # deleting the pin takes the tag's new commit, in a new cache entry
    (box.prog / 'dewy.lock').unlink()
    ran = box.run(source)
    assert ran.stdout == 'v2\n'
    assert (box.prog / 'dewy.lock').read_text() != lock
    assert len(list(box.cache.iterdir())) == 2


def test_lock_is_written_beside_the_program(box):
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "v1"\n'})
    source = box.program({'lib': f'{url(src)}, "v1"'})
    assert box.run(source, cwd=box.root).returncode == 0
    assert (box.prog / 'dewy.lock').exists()
    assert not (box.root / 'dewy.lock').exists()


def test_package_without_a_ref_follows_the_default_branch_and_a_commit_pins_exactly(box):
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "one"\n'})
    first = box.git(src, 'rev-parse', 'HEAD')
    box.commit(src, {'lib.jo': 'greet = () -> str: "two"\n'}, 'two')
    head = box.git(src, 'rev-parse', 'HEAD')
    ran = box.run(box.program({'lib': url(src)}))
    assert ran.stdout == 'two\n', ran.stderr
    assert box.lock()[0].split(' ')[2:] == ['-', head]       # no ref is written as -
    (box.prog / 'dewy.lock').unlink()
    ran = box.run(box.program({'lib': f'{url(src)}, "{first}"'}))
    assert ran.stdout == 'one\n', ran.stderr
    assert box.lock()[0].split(' ')[2:] == [first, first]


def test_unknown_tag_is_an_error_and_writes_no_lock(box):
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "v1"\n'})
    ran = box.run(box.program({'lib': f'{url(src)}, "v9"'}))
    assert ran.returncode != 0
    assert "has no 'v9'" in ran.stderr
    assert not (box.prog / 'dewy.lock').exists()


@pytest.fixture
def pinned(box):
    """A program with a git package, built once: (box, source, the lock text, the commit)."""
    src = box.repo('src', {'lib.jo': 'greet = () -> str: "v1"\n'})
    source = box.program({'lib': f'{url(src)}, "v1"'})
    assert box.run(source).returncode == 0
    lock = (box.prog / 'dewy.lock').read_text()
    return source, lock, box.lock()[0].split(' ')[3]


@pytest.mark.parametrize('garbage', ['total garbage\n', '', 'lib too few fields\n', '\x00\x01 ?\n'])
def test_garbled_lock_lines_are_resolved_again(box, pinned, garbage):
    source, lock, commit = pinned
    (box.prog / 'dewy.lock').write_text(garbage)
    ran = box.run(source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'v1\n'
    assert box.lock()[0].endswith(' ' + commit)       # pinned again, to the same commit
    assert 'fetching' not in ran.stderr                # (the cache still has it)


def test_garbled_lock_resolves_against_the_current_tag(box, pinned):
    source, _, commit = pinned
    src = box.root / 'src'
    box.commit(src, {'lib.jo': 'greet = () -> str: "v2"\n'}, 'two')
    box.git(src, 'tag', '-f', '-a', 'v1', '-m', 'again')
    (box.prog / 'dewy.lock').write_text('not a pin\n')
    ran = box.run(source)
    assert ran.stdout == 'v2\n', ran.stderr
    assert box.lock()[0].split(' ')[3] != commit


def test_pin_with_a_malformed_commit_is_resolved_again(box, pinned):
    source, lock, commit = pinned
    (box.prog / 'dewy.lock').write_text(re.sub(r' [0-9a-f]{40}$', ' zzzz', lock, flags=re.M))
    ran = box.run(source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'v1\n'
    assert box.lock()[0].endswith(' ' + commit)


def test_pin_to_a_commit_the_repository_lacks_is_an_error(box, pinned):
    source, lock, _ = pinned
    (box.prog / 'dewy.lock').write_text(re.sub(r' [0-9a-f]{40}$', ' ' + '0123456789' * 4, lock, flags=re.M))
    ran = box.run(source)
    assert ran.returncode != 0
    assert 'git could not fetch commit' in ran.stderr


def test_cache_location_follows_dewy_packages(box, pinned):
    source, _, commit = pinned
    assert [p.name.split('@')[1] for p in box.cache.iterdir()] == [commit[:12]]
    # a fresh cache directory is filled again, from the pin
    other = box.root / 'other-cache'
    box.env['DEWY_PACKAGES'] = str(other)
    ran = box.run(source)
    assert ran.stdout == 'v1\n', ran.stderr
    assert 'fetching lib' in ran.stderr
    assert [p.name.split('@')[1] for p in other.iterdir()] == [commit[:12]]


def test_without_dewy_packages_the_cache_is_under_the_user_cache_directory(box, pinned):
    source, _, commit = pinned
    del box.env['DEWY_PACKAGES']
    ran = box.run(source)
    assert ran.stdout == 'v1\n', ran.stderr
    fetched = list((box.root / 'xdg' / 'dewy' / 'packages').iterdir())
    assert [p.name.split('@')[1] for p in fetched] == [commit[:12]]
    assert not (box.root / 'home').exists() or not any((box.root / 'home').rglob('*@*'))
