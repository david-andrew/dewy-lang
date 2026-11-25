"""driver_cold_dispatch in driver_dispatch matches its frozen twin through real CLI commands."""
import shutil

import pytest

from tests import selfhost_lsp_double, selfhost_process_double
from tests import test_selfhost_formatter_cli as formatter_cases
from tests import test_selfhost_watch_drive as watch_cases
from tests.repl_pty import run_repl
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_driver_cli import run
from tests.test_selfhost_new_project import files, KINDS

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_driver_dispatch_twins(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original_driver = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original_driver(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('driver_dispatch',))

    for arguments, status in [(['--print-lib'], 0), (['--print-lib', 'extra'], 2),
                              (['new'], 2), (['new', '-dash'], 2),
                              (['new', 'project', 'unknown-template'], 2),
                              # Earlier internal argument rewriting must still reach these commands.
                              (['--skip-fns', '', '', '--print-lib'], 0),
                              (['--skip-fns', '', '', 'add'], 2),
                              (['--skip-fns', '', '', 'fmt'], 2)]:
        results = [run(binary, arguments, tmp_path) for binary in binaries]
        assert results[0] == results[1] and results[0][0] == status, (arguments, results)
    assert not (tmp_path / 'project').exists()

    # Ordinary compile commands fall through to the Jo argument/state owner.
    (tmp_path / 'passthrough.dewy').write_text('main=():>void=>printl"passthrough"\n')
    for arguments in (['check', 'passthrough.dewy'], ['run', 'passthrough.dewy'],
                      ['passthrough.dewy', '--help'],
                      ['build', 'passthrough.dewy', '-o', 'passthrough']):
        outputs = []
        for binary in binaries:
            result = run(binary, arguments, tmp_path)
            assert result[0] == 0, (arguments, result)
            artifact = (tmp_path / 'passthrough').read_bytes() if arguments[0] == 'build' else None
            outputs.append((result, artifact))
        assert outputs[0] == outputs[1], arguments

    # Watch also falls through: compare its restarts and panic recovery with the
    # dispatcher itself frozen, using the established watch session driver.
    monkeypatch.setattr(selfhost_process_double, 'leaf_compilers', lambda *_: binaries)
    watched = tmp_path / 'watched'
    watched.mkdir()
    watch_cases.test_watch_drive_program_matches_twin(compiler, watched, monkeypatch)

    # No arguments choose the pipe path, and preserve stdin bytes/errors.
    for source in ('main=():>void=>printl"from stdin"\n', 'main=()=>{(}\n', ''):
        results = [run(binary, [], tmp_path, stdin=source) for binary in binaries]
        assert results[0] == results[1], (source, results)
    assert 'from stdin' in run(binaries[0], [], tmp_path,
                               stdin='main=():>void=>printl"from stdin"\n')[1]

    # Formatting checks, writes, errors and the >64 KiB stdin path use this dispatcher.
    monkeypatch.setattr(formatter_cases, 'leaf_compilers', lambda *_: binaries)
    formatted = tmp_path / 'formatted'
    formatted.mkdir()
    formatter_cases.test_formatter_cli_twins(compiler, formatted, monkeypatch)

    # Both compilers write to the same path from identical starting contents.
    created = tmp_path / 'created'
    created.mkdir()
    for kind in KINDS:
        outputs = []
        for binary in binaries:
            shutil.rmtree(created / 'Caf\u00e9 Project', ignore_errors=True)
            output = run(binary, ['new', 'Caf\u00e9 Project', kind], created)
            assert output[0] == 0, output
            outputs.append((output, files(created)))
        assert outputs[0] == outputs[1], kind
    results = [run(binary, ['new', 'Caf\u00e9 Project'], created) for binary in binaries]
    assert results[0] == results[1] and results[0][0] == 1, results

    # A terminal chooses the prompt path; history is part of the observable result.
    prompted = tmp_path / 'prompted'
    prompted.mkdir()
    outputs = []
    for binary in binaries:
        (prompted / 'repl-history').unlink(missing_ok=True)
        result = run_repl(binary, '40 + 2\n:quit\n', prompted)
        assert result.returncode == 0 and '42' in result.stdout, result
        outputs.append((result.returncode, result.stdout, result.stderr,
                        (prompted / 'repl-history').read_bytes()))
    assert outputs[0] == outputs[1]

    # Starting, requesting and shutting down the actual server must reach LSP.
    served = tmp_path / 'served'
    served.mkdir()
    logs = [selfhost_lsp_double.session(binary, served, [('workspace/symbol', {'query': ''})])
            for binary in binaries]
    assert logs[0] == logs[1]
