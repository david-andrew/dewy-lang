"""The watch's driver (builds in a child, the program's pipes, file events, restarts and quits)
agrees with frozen Jo: the same session transcripts, exit codes and files."""
from tests.selfhost_process_double import compare_watch
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_watch_ops import GAME


def test_watch_drive_game_matches_twin(compiler, tmp_path, monkeypatch):
    steps = [
        ('expect', 'label=one value=22'),
        ('save', 'helper.dewy', 'label=()=>"two"'),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'label=two value=22'),
        ('save', 'helper.dewy', 'label=()=>missing'),
        ('expect', 'keeps running the last version'),
        ('save', 'helper.dewy', 'label=()=>"three"'),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'label=three value=22'),
        ('key', 'r\n'), ('expect', 'label=three value=22'),
    ]
    out, err, code, _ = compare_watch(compiler, tmp_path, monkeypatch, ('watch_drive',),
                                      {'game.dewy': GAME, 'helper.dewy': 'label=()=>"one"'}, steps, game=True)
    assert any('sending a patch' in line for line in err), err


def test_watch_drive_asset_matches_twin(compiler, tmp_path, monkeypatch):
    game = GAME.replace('let shown=""', 'let shown=""\nlet word=str_from_bytes($include_bytes(p"word.txt"))').replace(
        'value={pick()}', 'value={pick()} word={word}')
    steps = [
        ('expect', 'word=one'),
        ('save', 'word.txt', 'two'),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'word=two'),
    ]
    compare_watch(compiler, tmp_path, monkeypatch, ('watch_drive',),
                  {'game.dewy': game, 'helper.dewy': 'label=()=>"one"', 'word.txt': 'one'}, steps, game=True)


def test_watch_drive_program_matches_twin(compiler, tmp_path, monkeypatch):
    steps = [
        ('expect', 'first version'), ('expect', r'program ended \(exit status 0\)'),
        ('save', 'main.dewy', 'main=():>void=>printl"second version"'),
        ('expect', 'second version'), ('expect', r'program ended \(exit status 0\)'),
        ('save', 'main.dewy', 'main=():>void=>{printl"crash" panic"stop"}'),
        ('expect', r'program ended \(a panic\)'),
        ('save', 'main.dewy', 'main=():>void=>printl"third version"'),
        ('expect', 'third version'), ('expect', r'program ended \(exit status 0\)'),
        ('key', 'r\n'), ('expect', 'third version'), ('expect', r'program ended \(exit status 0\)'),
    ]
    compare_watch(compiler, tmp_path, monkeypatch, ('watch_drive',),
                  {'main.dewy': 'main=():>void=>printl"first version"'}, steps)
