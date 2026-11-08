"""The prompt's driver (starting the session program, running inputs, completion, history and the
command loop) as a Dewy leaf agrees with frozen Jo: the same transcripts, exit codes and history."""
from tests.selfhost_process_double import compare_repl
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_repl_ops import TRANSCRIPTS


def test_repl_drive_matches_twin(compiler, tmp_path, monkeypatch):
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_drive', 'proc_sys'), TRANSCRIPTS)
    assert all(code == 0 for code, *_ in runs), runs
    assert '42' in runs[1][1] and 'restore values' in runs[3][2] and runs[4][1].split() == ['42', '12'], runs


def test_repl_drive_exit_and_crash_match_twin(compiler, tmp_path, monkeypatch):
    transcripts = [
        'let x=40\nx+2\nexit(3)\n',
        'let xs=[1 2]\nxs[0]\n:type xs\n:t 1+2\nquit\n',
    ]
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_drive',), transcripts)
    assert runs[0][0] == 3, runs
