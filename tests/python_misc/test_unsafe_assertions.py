"""Unchecked local facts keep their source and cannot silently erase effects."""
import json
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import unsafe_audit
from dewy.semantic.errors import UserError
from tests.python_misc.test_scalar_projection import execute


SOURCE = '''read_at=(xs:array<int64> i:int64):>int64=>{
    $unsafe_assert 0<=?i and i<?xs.length, 'validated by the producer'
    return xs[i]
}
main=():>int64=>read_at([42] 0)
'''


def test_unsafe_index_has_no_runtime_assertion_and_keeps_audit(tmp_path):
    output = codegen(SrcFile(None, SOURCE))
    execute(tmp_path, 'assumed-index', output)
    report = json.loads(unsafe_audit.render(unsafe_audit.last_entries))
    assert len(report['assumptions']) == 1
    entry = report['assumptions'][0]
    assert entry['condition'] == '0<=?i and i<?xs.length'
    assert entry['message'] == 'validated by the producer'
    assert entry['scope'] == 'read_at'
    assert any(check['kind'] == 'index' for check in entry['candidate_checks'])
    assert 'validated by the producer' not in output


@pytest.mark.parametrize('mutation', ['i=xs.length', 'xs.clear()'])
def test_assumption_does_not_survive_replacement_or_resize(mutation):
    source = SOURCE.replace('    return xs[i]', f'    {mutation}\n    return xs[i]')
    with pytest.raises(UserError, match='bounds|index'):
        codegen(SrcFile(None, source))


def test_assumption_cannot_erase_an_effectful_condition():
    with pytest.raises(UserError, match='pure fact condition'):
        codegen(SrcFile(None, 'condition=():>bool=>{printl("effect") return true}\nmain=():>int64=>{$unsafe_assert condition()\nreturn 42}'))


def test_assumption_message_must_be_static():
    with pytest.raises(UserError, match='string literal'):
        codegen(SrcFile(None, 'f=(ok:bool msg:string)=>{$unsafe_assert ok, msg}'))


def test_checked_proof_cannot_use_an_assumption():
    with pytest.raises(UserError, match='unsupported operation in a checked proof'):
        codegen(SrcFile(None, '$proof\nf=(x:int64):> <x>?0>=>{$unsafe_assert x>?0}'))


def test_folded_and_unused_assumptions_are_not_lost():
    codegen(SrcFile(None, 'unused=()=>{$unsafe_assert true, "explicit assumption"}\nmain=():>int64=>42'))
    assert len(unsafe_audit.last_entries) == 1
    assert unsafe_audit.last_entries[0].condition == 'true'
    codegen(SrcFile(None, 'main=():>int64=>42'))
    assert not unsafe_audit.last_entries


def test_cli_writes_persistent_audit_and_replaces_stale_entries(tmp_path):
    from dewy.__main__ import run
    from udewy.cache import cache_artifact
    source = tmp_path / 'assumption.dewy'
    source.write_text(SOURCE)
    assert run(['-c', str(source)]) == 0
    path = cache_artifact(source, '.udewy').with_suffix('.unsafe.json')
    report = json.loads(path.read_text())
    assert report['assumptions'][0]['path'] == str(source)
    source.write_text('main=():>int64=>42')
    assert run(['-c', str(source)]) == 0
    assert not json.loads(path.read_text())['assumptions']


def test_test_command_keeps_audit(tmp_path):
    from dewy.__main__ import test as test_command
    from udewy.cache import cache_artifact
    source = tmp_path / 'assumption_test.dewy'
    source.write_text('$test\nlet checked=()=>{$unsafe_assert true, "external guarantee"}\n')
    assert test_command([str(source)]) == 0
    path = cache_artifact(source, '.test.udewy').with_suffix('.unsafe.json')
    assert json.loads(path.read_text())['assumptions'][0]['message'] == 'external guarantee'


def test_cached_prelude_retains_unused_assumptions(tmp_path, monkeypatch):
    from dewy.semantic import modules, prelude as prelude_config
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('DEWY_NO_PRELUDE_CACHE', raising=False)
    prelude = tmp_path / 'prelude.dewy'
    prelude.write_text('unused=()=>{$unsafe_assert true, "cached guarantee"}\n')
    monkeypatch.setattr(prelude_config, 'library', tmp_path)
    monkeypatch.setattr(modules, 'prelude_files', lambda target: (prelude,))
    source = SrcFile(None, 'main=():>int64=>42\n')
    codegen(source)
    cold = unsafe_audit.render(unsafe_audit.last_entries)
    assert json.loads(cold)['assumptions'][0]['path'] == str(prelude)
    codegen(source)
    assert unsafe_audit.render(unsafe_audit.last_entries) == cold
    modules._resident_preludes.clear()  # exercise the persistent cache too
    codegen(source)
    assert unsafe_audit.render(unsafe_audit.last_entries) == cold
