"""Check which executions and compiler output the whole-program oracle records."""
import os

import pytest

from tests import whole_oracle


@pytest.mark.parametrize('code,parallel', [
    ('# No parallel work here\nprintl("threads") # spawn example', False),
    ('let xs=[parallel i in [0..10) i]', True),
    ('let xs=parallel_range(4 work)', True),
    ('tasks { spawn work() }', True),
    ('let pipe=channel<int64>()', True),
    ('let t=Thread.start(work)', True),
    ('from p"worker.dewy" import work\nwork()', True),
])
def test_oracle_runs_one_cpu_only_for_concurrency(tmp_path, monkeypatch, code, parallel):
    monkeypatch.setattr(os, 'sched_setaffinity', lambda *_: None, raising=False)
    monkeypatch.setattr(whole_oracle, 'HOST_MACHINE', 62)
    (tmp_path / 'worker.dewy').write_text('work=()=>{tasks {spawn printl(1)}}')
    source = tmp_path / 'program.dewy'
    source.write_text(code)
    binary = tmp_path / 'program'
    binary.write_bytes(b'\x7fELF' + bytes(14) + b'\x3e\x00')
    binary.chmod(0o755)
    runs = []

    def run(path, cwd, setup=None):
        assert (path, cwd) == (binary, tmp_path)
        runs.append(setup)
        return {'status': 0, 'stdout': 'ok\n', 'stderr': ''}

    monkeypatch.setattr(whole_oracle, '_run', run)
    outcome = whole_oracle.build(['build', source], 0, b'', b'', [binary], tmp_path)
    assert outcome['files']['program']['run']['stdout'] == 'ok\n'
    assert runs == ([None, whole_oracle._one_cpu] if parallel else [None])


def test_oracle_limits_executable_runtime(tmp_path, monkeypatch):
    def run(*args, **kwargs):
        assert kwargs['timeout'] == 2
        raise whole_oracle.subprocess.TimeoutExpired(args[0], kwargs['timeout'])

    monkeypatch.setattr(whole_oracle.subprocess, 'run', run)
    assert whole_oracle._run(tmp_path / 'program', tmp_path) == 'timeout'


@pytest.mark.parametrize('program', ['95_kv_store', '96_ct_crypto'])
def test_oracle_leaves_stress_runs_to_the_ladder(tmp_path, program):
    assert not whole_oracle._native(tmp_path / program / 'design.dewy')


def test_oracle_keeps_user_diagnostics_on_ir_builds(tmp_path):
    warning = b'other.dewy:3:5: warning: unused name\n'
    result = whole_oracle.build(['build', '--ir'], 1, b'fn _internal\n', warning, [], tmp_path)
    assert (result['status'], result['stdout'], result['stderr']) == (1, '', warning.decode())
