"""The prompt's line editing and completion on multi-byte text agree with frozen Jo, which cuts the
line at bytes: Delete and ctrl-d on a character, completions that share only part of a character."""
from tests.selfhost_process_double import compare_repl
from tests.support import compiler  # noqa: F401

TRANSCRIPTS = [
    # (completions that agree up to the middle of a character)
    'let éaé=1\nlet éaè=2\né\t\n:quit\n',
    # (Delete and ctrl-d with the cursor before a two-, three- and four-byte character)
    '1+中\x1b[D\x1b[3~\n:quit\n',
    '"é"\x1b[D\x1b[D\x04\n:quit\n',
    '"😀"\x1b[D\x1b[D\x1b[3~\n:quit\n',
    # (backspace and kill after wide characters; word deletion)
    'let y="😀é"\n"😀é\x7f\x7f"\n1+é中\x1b[D\x0b\nlet é=3\né é\x17é\n:quit\n',
]


def test_repl_multibyte_matches_twin(compiler, tmp_path, monkeypatch):
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_ops',), TRANSCRIPTS)
    assert not any('panic' in run[2] for run in runs), runs
