"""The prompt's line editing and completion on multi-byte text agree with frozen Jo, which cuts the
line at bytes: Delete and ctrl-d on a character, completions that share only part of a character."""
import re

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


LEFT, RIGHT, HOME, END, DELETE, CTRL_D, BACKSPACE = (b'\x1b[D', b'\x1b[C', b'\x1b[H', b'\x1b[F', b'\x1b[3~', b'\x04',
                                                       b'\x7f')
E, ZHONG, SMILE = 'é'.encode(), '中'.encode(), '😀'.encode()
MARK = '́'.encode()  # a combining acute accent: a character of its own
# (typed bytes, the line that is submitted): every editing key takes a whole character, and a byte
# that does not belong to a sequence is a character by itself
EDITS = [
    (b'x' + E + ZHONG + SMILE + BACKSPACE * 2, b'x' + E),
    (b'x' + E + ZHONG + SMILE + BACKSPACE * 4 + b'y', b'y'),
    (E + ZHONG + SMILE + HOME + DELETE, ZHONG + SMILE),
    (E + ZHONG + SMILE + HOME + DELETE * 3, b''),
    (E + ZHONG + SMILE + HOME + RIGHT + CTRL_D, E + SMILE),
    (E + ZHONG + SMILE + LEFT + CTRL_D + b'!', E + ZHONG + b'!'),
    (E + ZHONG + SMILE + LEFT * 2 + DELETE + b'!', E + b'!' + SMILE),
    (E + ZHONG + SMILE + HOME + RIGHT * 5 + BACKSPACE, E + ZHONG),
    (E + ZHONG + SMILE + HOME + RIGHT * 2 + LEFT * 3 + b'+', b'+' + E + ZHONG + SMILE),
    (b'ab' + LEFT + E + LEFT + CTRL_D, b'ab'),
    (b'ab' + LEFT + ZHONG + SMILE + BACKSPACE + b'c', b'a' + ZHONG + b'cb'),
    (b'e' + MARK + b'x' + BACKSPACE * 2, b'e'),
    (b'e' + MARK + b'x' + LEFT * 2 + CTRL_D + b'-', b'e-x'),
    (b'e' + MARK + b'x' + LEFT * 2 + RIGHT + DELETE, b'e' + MARK),
    (b'a\x80\x80b' + LEFT * 3 + DELETE, b'a\x80b'),
    (b'a\x80\x80b' + LEFT * 2 + BACKSPACE, b'a\x80b'),
    (b'a\x80\xbfb' + LEFT + BACKSPACE * 2 + BACKSPACE, b'b'),
    (b'\xe4\xb8' + BACKSPACE + b'z', b'\xe4z'),
    (b'\xe4\xb8' + LEFT + CTRL_D, b'\xe4'),
    (b'\xc3x' + BACKSPACE * 2 + b'q', b'q'),
    (b'\xf0\x9f\x98' + LEFT * 2 + DELETE, b'\xf0\x98'),
    (b'\xc0\x80\xed\xa0\x80' + HOME + DELETE, b'\x80\xed\xa0\x80'),
    (b'\xf4\x90\x80\x80' + BACKSPACE, b'\xf4\x90\x80'),
    (b'\xff' + E + b'\xfe' + LEFT * 2 + DELETE, b'\xff\xfe'),
    (b'\x80' + HOME + b'\xc3' + END + b'.', b'\xc3\x80.'),
    (b'\x80' + HOME + b'\xc3' + CTRL_D, b''),  # (the typed byte and the one after it made one character)
]


def test_editing_keys_take_whole_characters(compiler, tmp_path, monkeypatch):
    typed = [keys + b'\n' for keys, _ in EDITS]
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_ops',), [t + b':quit\n' for t in typed], paced=True)
    for (keys, line), run in zip(EDITS, runs):
        assert 'panic' not in run[2], (keys, run)
        history = run[3].split(b'\n')
        assert history[0] == line or not line.strip(), (keys, line, history)


def test_completion_stops_between_characters(compiler, tmp_path, monkeypatch):
    """Names that agree up to the middle of a character complete to the characters they share."""
    lines = [b'let \xc3\xa9a\xc3\xa9=1\n', b'let \xc3\xa9a\xc3\xa8=2\n', b'\xc3\xa9\t\n', b':quit\n']
    run = compare_repl(compiler, tmp_path, monkeypatch, ('repl_ops',), [b''.join(lines)], paced=True)[0]
    assert 'panic' not in run[2], run
    assert run[3].split(b'\n')[2] == b'\xc3\xa9a', run[3]


# (typed keys, the column the cursor is moved to when the line is drawn last): the prompt is four columns, a wide
# character takes two, and a combining mark none
CURSOR_COLUMNS = [
    (ZHONG, 6),
    (SMILE, 6),
    (b'e' + MARK, 5),
    (b'a' + ZHONG + SMILE + b'e' + MARK, 10),
    (ZHONG + LEFT, 4),
    (b'x' + ZHONG + LEFT, 5),
    (b'x' + ZHONG + LEFT * 2, 4),
    (b'e' + MARK + LEFT, 5),
    (b'e' + MARK + LEFT * 2, 4),
    (SMILE + ZHONG + LEFT + RIGHT, 8),
    (ZHONG + SMILE + HOME + RIGHT, 6),
    (ZHONG + b'ab' + HOME + DELETE, 4),
]


def test_cursor_goes_by_display_columns(compiler, tmp_path, monkeypatch):
    """After wide characters and combining marks the cursor is drawn where they leave it, in both builds."""
    transcripts = [keys + CTRL_D + b'\n:quit\n' for keys, _ in CURSOR_COLUMNS]
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_ops',), transcripts, paced=True, raw=True)
    for (keys, columns), run in zip(CURSOR_COLUMNS, runs):
        assert 'panic' not in run[2], (keys, run)
        drawn = run[1].split('\r\n')[0]  # (what was drawn before the line was submitted)
        moves = re.findall(r'\x1b\[(\d+)C', drawn)
        assert moves and int(moves[-1]) == columns, (keys, columns, moves)
