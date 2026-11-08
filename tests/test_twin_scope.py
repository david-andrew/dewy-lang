"""`tools.core test --base REV` scopes twin tests by the files they read, from the real import graph."""
import pytest

from tools import core, twin_scope

TWINS = len(twin_scope.twin_files())


def scoped(*changed):
    return {name.removeprefix('tests/test_selfhost_').removesuffix('.py') for name in twin_scope.scoped_out(set(changed))}


def test_nothing_changed_scopes_every_twin_out():
    assert len(twin_scope.scoped_out(set())) == TWINS
    assert len(twin_scope.scoped_out({'docs/design/decisions.md', 'ROADMAP.md'})) == TWINS


def test_toolchain_inputs_scope_nothing_out():
    for name in ('lib/core/rt.jo', 'stage0/sloppy0.c', 'tools/compiler/build.py', 'tests/conftest.py', 'tests/driver_cache.py'):
        assert twin_scope.scoped_out({name}) == [], name


def test_a_compiler_file_reaches_the_twins_that_import_it():
    # sha's twin links compiler/sha.* alone; a driver that links the whole compiler reads every file
    changed = scoped('compiler/base64.dewy')
    assert 'base64' not in changed and 'sha' in changed and 'float_ops' not in changed
    # the closure follows imports: a file only some other module imports still reaches the whole-compiler twins
    assert 'float_ops' not in scoped('compiler/util.jo') and 'base64' in scoped('compiler/util.jo')


def test_a_test_file_or_a_case_it_names_reaches_only_its_twin():
    assert 'sha' not in scoped('tests/test_selfhost_sha.py') and 'base64' in scoped('tests/test_selfhost_sha.py')
    changed = scoped('tests/cases/comptime/semantics.dewy')
    assert 'float_ops' not in changed and 'sha' in changed


def test_a_shared_double_reaches_the_group_it_feeds():
    changed = scoped('tests/selfhost_facts_double.py')
    assert 'float_ops' not in changed and 'sha' in changed


def test_base_option_is_taken_out_of_the_pytest_arguments():
    assert core.take_base(['-k', 'x', '--base', 'origin/master', '-m', 'nightly']) == (['-k', 'x', '-m', 'nightly'], 'origin/master')
    assert core.take_base(['--base=abc']) == ([], 'abc')
    assert core.take_base(['-k', 'x']) == (['-k', 'x'], None)
    with pytest.raises(SystemExit):
        core.take_base(['--base'])
