"""driver_options and driver_timing match their frozen twins through the real CLI.

The paired compilers exercise driver_early_options, driver_release_timing and driver_emit_timing,
including byte arguments, stdin, settings, artifacts and directory tests.
"""
import os
import re
import subprocess

import pytest

from tests import selfhost_build_double, selfhost_lsp_double
from tests import test_selfhost_driver_cli as cli_cases
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('driver_options', 'driver_timing')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_driver_options_timing_twins(compiler, tmp_path, monkeypatch, release):
    original_driver = selfhost_lsp_double.cached_driver
    leaf_compilers = selfhost_lsp_double.leaf_compilers
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original_driver(compiler, path, release, modules))

    def paired(compiler, path, _leaves):
        return leaf_compilers(compiler, path, LEAVES)

    monkeypatch.setattr(cli_cases, 'leaf_compilers', paired)
    monkeypatch.setattr(selfhost_build_double, 'leaf_compilers', paired)
    builds = tmp_path / 'builds'
    builds.mkdir()
    cli_cases.test_driver_cli_builds_match_twin(compiler, builds, monkeypatch)
    commands = tmp_path / 'commands'
    commands.mkdir()
    cli_cases.test_driver_cli_commands_match_twin(compiler, commands, monkeypatch)

    binaries = leaf_compilers(compiler, tmp_path, LEAVES)
    option_cases = [(['--version'], 0), (['version'], 0), (['--help'], 0),
                    (['help'], 0), (['-h'], 0), (['update'], 2),
                    (['upgrade'], 2), (['add'], 2), (['hello.dewy', '--help'], 0)]
    option_cases += [([command, '--help'], 0)
                     for command in ('build', 'check', 'test', 'fmt', 'new', 'watch')]
    option_cases += [(['build', 'missing.dewy', '--release', '-h'], 0),
                     (['watch', 'missing.dewy', '-h'], 0),
                     (['new', 'missing', '--help'], 0)]
    for arguments, status in option_cases:
        runs = [cli_cases.run(binary, arguments, commands) for binary in binaries]
        assert runs[0] == runs[1], (arguments, runs)
        assert runs[0][0] == status, (arguments, runs)
    assert not (commands / 'missing').exists()

    # Both once-per-build timing callbacks retain their text shape. Durations
    # themselves vary; normalize only those measured values.
    source = tmp_path / 'timing.dewy'
    source.write_text('main=():>void=>printl"ok"\n')
    outputs = []
    env = dict(os.environ, DEWY_CORE_LIB=str(ROOT / 'lib'), DEWY_PAR_TIME='1', DEWY_EMIT_WORKERS='1')
    for binary in binaries:
        run = subprocess.run([binary, 'build', '--release', '--time', source, '-o', tmp_path / 'timing'],
                             capture_output=True, text=True, timeout=90, env=env)
        assert run.returncode == 0, run.stdout + run.stderr
        lines = [line for line in run.stderr.splitlines() if line.startswith(('release:', 'emit:', 'lower:'))]
        assert any(line.startswith('release:') for line in lines), lines
        assert any(line.startswith('emit:') for line in lines), lines
        outputs.append([re.sub(r'[0-9]+\.[0-9]+ ms', '<time> ms', line) for line in lines])
    assert outputs[0] == outputs[1]

    # Known intervals also compare the actual numeric fields, independently of
    # scheduling. Only the fields that read the clock need normalization.
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', """use 'main.jo'
use 'driver_timing.dewy'
main = ():
    driver_release_timing(1.0, 1.125, 1.5)
    driver_emit_timing(0.0)
""")
    probes = leaf_compilers(compiler, tmp_path, LEAVES)
    for enabled in (False, True):
        probe_env = dict(env)
        if not enabled:
            probe_env.pop('DEWY_PAR_TIME')
        outputs = []
        for binary in probes:
            run = subprocess.run([binary], capture_output=True, text=True,
                                 timeout=30, env=probe_env)
            assert run.returncode == 0, run.stdout + run.stderr
            assert run.stdout == ''
            if enabled:
                assert run.stderr.startswith('release: optimize 125.0 ms, inline 375.0 ms, versioning and licm ')
                assert '\nemit: here, ' in run.stderr
            else:
                assert run.stderr == ''
            outputs.append(re.sub(r'(versioning and licm |emit: here, )[0-9]+\.[0-9]+ ms',
                                  r'\1<time> ms', run.stderr))
        assert outputs[0] == outputs[1]
