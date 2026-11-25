"""driver_run_command/driver_build_output/driver_build_arguments in driver_commands match their frozen twin."""
import os

import pytest

from tests import selfhost_lsp_double, selfhost_process_double
from tests import test_selfhost_driver_cli as cli_cases
from tests import test_selfhost_watch_drive as watch_cases
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_driver_commands_twins(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('driver_commands',))

    # Reuse command-level checks of refusals, test directory traversal, filters,
    # JSON results, source settings, internal options, and stdin execution.
    monkeypatch.setattr(cli_cases, 'leaf_compilers', lambda *_: binaries)
    cli_cases.test_driver_cli_commands_match_twin(compiler, tmp_path, monkeypatch)

    (tmp_path / 'arguments.dewy').write_text(
        'from p"@lib/core/os.jo" import args\n'
        'main=():>void=>printl"{args()}"\n')
    (tmp_path / 'bad.dewy').write_text('main=():>void=>{let a:int64="bad";}\n')
    (tmp_path / 'clean').mkdir()
    (tmp_path / 'clean' / 'a_test.dewy').write_text(cli_cases.PASSING)
    cases = [
        (['check'], 2), (['run'], 2), (['run', '--target'], 2),
        (['check', 'hello.dewy'], 0),
        (['check', '--obligations', 'hello.dewy'], 0),
        (['check', 'hello.dewy', '--obligations'], 0),
        (['check', 'bad.dewy'], 1),
        (['build', '--release'], 2), (['build', '--target'], 2),
        (['build', '-o'], 2), (['build', '-o', 'only-output'], 2),
        (['build', '--target', 'unknown', 'hello.dewy'], 2),
        (['build', 'hello.dewy', '--exit-codes'], 0),
        (['build', '--ir', 'hello.dewy', '-o', 'ir-output'], 0),
        (['build', '--host-ir', 'hello.dewy'], 0),
        (['build', '-g', '--release', '--debug', 'hello.dewy', '-o', 'more/flags.bin'], 0),
        (['build', 'bad.dewy', 'hello.dewy', '-o', 'last-source'], 0),

        (['run', '--target', 'x86_64-linux', '--release', 'arguments.dewy', '--debug', 'caf\u00e9'], 0),
        (['--debug', '--target', 'x86_64-linux', 'arguments.dewy', '$target=wasm32'], 0),
        (['run', '--target', 'wasm32', 'watch', 'hello.dewy'], 1),
        (['--skip-fns', '', '', 'check', 'hello.dewy'], 1),
        (['test', '--target', 'wasm32', '--json', 'clean', 'adds'], 0),
        (['run', 'test', 'clean', 'adds'], 0),
        (['test', '--target', 'x86_64-linux', '--json', 'clean', 'nothing'], 1),
        (['buidl'], 1), (['qqqqqqqq'], 1), (['--\udcff'], 2),
    ]
    for arguments, status in cases:
        results = [cli_cases.run(binary, arguments, tmp_path) for binary in binaries]
        assert results[0] == results[1] and results[0][0] == status, (arguments, results)

    # All profiling stops remain in Jo and preserve statuses/output after dispatch moves.
    for stop in ('lex', 'parse', 'check'):
        env = dict(os.environ, DEWY_STOP=stop)
        results = [cli_cases.run(binary, ['check', 'hello.dewy'], tmp_path, env=env)
                   for binary in binaries]
        assert results[0] == results[1] and results[0][0] == 0, (stop, results)

    # Missing test paths default to the working directory; options without a
    # filename still run piped source, while an explicit run reports usage.
    for arguments, cwd, stdin, status in [
        (['test', '--json'], tmp_path / 'suite', None, 102),
        (['--release'], tmp_path, 'main=():>void=>printl"pipe"\n', 0),
        (['run', '--debug'], tmp_path, 'main=():>void=>printl"pipe"\n', 2),
    ]:
        results = [cli_cases.run(binary, arguments, cwd, stdin=stdin) for binary in binaries]
        assert results[0] == results[1] and results[0][0] == status, (arguments, results)

    # Exercise watch startup, program restarts and recovery through the moved
    # owner, rather than only testing the lower-level watch service.
    monkeypatch.setattr(selfhost_process_double, 'leaf_compilers', lambda *_: binaries)
    watched = tmp_path / 'watched'
    watched.mkdir()
    watch_cases.test_watch_drive_program_matches_twin(compiler, watched, monkeypatch)

    # Build output ownership: no -o, a setting relative to the source, an
    # absolute setting, no extension, and non-UTF-8 path bytes.
    program = 'main=():>void=>printl"output"\n'
    nested = tmp_path / 'folder.with.dot'
    nested.mkdir()
    (nested / 'Caf\u00e9.name.dewy').write_text(program)
    (nested / 'targeted.dewy').write_text(program)
    (nested / 'source').write_text('main = (): print("output")\n')
    (nested / 'ragged-\udcff.jo').write_text('main = (): print("output")\n')
    (nested / 'configured.jo').write_text(
        'build:\n    output = "relative/artifact"\n\nmain = (): print("output")\n')
    absolute = tmp_path / 'absolute-output'
    (nested / 'absolute.jo').write_text(
        f'build:\n    output = "{absolute}"\n\nmain = (): print("output")\n')
    for source, artifact, flags in [
        (nested / 'Caf\u00e9.name.dewy', nested / 'Caf\u00e9.name', []),
        (nested / 'source', nested / 'source.bin', []),
        (nested / 'ragged-\udcff.jo', nested / 'ragged-\udcff', []),
        (nested / 'configured.jo', nested / 'relative/artifact', []),
        (nested / 'absolute.jo', absolute, []),
        (nested / 'targeted.dewy', nested / 'targeted.exe', ['--target', 'x86_64-windows']),
        (nested / 'targeted.dewy', nested / 'targeted.html', ['--target', 'wasm32']),
    ]:
        results = []
        for binary in binaries:
            artifact.unlink(missing_ok=True)
            result = cli_cases.run(binary, ['build', str(source), *flags], tmp_path)
            assert result[0] == 0, (source, result)
            results.append((result, artifact.read_bytes()))
        assert results[0] == results[1], source
        assert source.exists(), source
