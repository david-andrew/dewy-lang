"""The prompt's session pieces (pipes to the session program, compiling an input under a snapshot
and setjmp, raw terminal input, completion probes) as a Dewy leaf agree with frozen Jo: the same
transcripts, exit codes and history."""
from tests.selfhost_process_double import compare_repl
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_repl_ops import TRANSCRIPTS


def test_repl_session_matches_twin(compiler, tmp_path, monkeypatch):
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_session',), TRANSCRIPTS)
    assert all(code == 0 for code, *_ in runs), runs
    assert '42' in runs[1][1] and 'restore values' in runs[3][2] and runs[4][1].split() == ['42', '12'], runs


def test_repl_session_errors_exit_and_crash_match_twin(compiler, tmp_path, monkeypatch):
    transcripts = [
        'let x=40\nx+2\nexit(3)\n',
        'let xs=[1 2]\nxs[0]\n:type xs\n:t 1+2\nnope(1)\nlet y: int = "s"\nxs\nquit\n',
        'let a=[1 2 3]\na[7]\na\nquit\n',
    ]
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_session', 'repl_drive', 'repl_ops'), transcripts)
    assert runs[0][0] == 3, runs


def test_repl_session_raw_keys_match_twin(compiler, tmp_path, monkeypatch):
    # (paced: the terminal is raw while each line is read; tab completion, backspace, ctrl-c)
    transcripts = [b'let total_score=40\ntotal_s\t+2\nlet y=13\x7f2\ny\n:quit\n',
                   b'let caf\xc3\xa9=1\ncaf\xc3\xa9+1\n\x03\n:quit\n']
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_session',), transcripts, paced=True, raw=True)
    assert runs[0][1].split()[-2:] == ['42', '12'] or '42' in runs[0][1], runs
