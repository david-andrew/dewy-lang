"""The process code's system calls (pipes, fork, waits, reads, polls) as Dewy target branches agree
with frozen Jo: the same watch transcripts, exit codes and files."""
from tests.selfhost_process_double import compare_watch
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_watch_ops import GAME


def test_proc_sys_program_watch_matches_twin(compiler, tmp_path, monkeypatch):
    steps = [
        ('expect', 'first version'), ('expect', r'program ended \(exit status 0\)'),
        ('save', 'main.dewy', 'main=():>void=>printl"second version"'),
        ('expect', 'second version'), ('expect', r'program ended \(exit status 0\)'),
        ('save', 'main.dewy', 'main=():>void=>{printl"crash" panic"stop"}'),
        ('expect', r'program ended \(a panic\)'),
        ('key', 'r\n'), ('expect', 'crash'), ('expect', r'program ended \(a panic\)'),
    ]
    compare_watch(compiler, tmp_path, monkeypatch, ('proc_sys',),
                  {'main.dewy': 'main=():>void=>printl"first version"'}, steps)


def test_proc_sys_game_watch_matches_twin(compiler, tmp_path, monkeypatch):
    steps = [
        ('expect', 'label=one value=22'),
        ('save', 'helper.dewy', 'label=()=>"two"'),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'label=two value=22'),
        ('save', 'helper.dewy', 'label=()=>missing'),
        ('expect', 'keeps running the last version'),
    ]
    compare_watch(compiler, tmp_path, monkeypatch, ('proc_sys', 'watch_drive'),
                  {'game.dewy': GAME, 'helper.dewy': 'label=()=>"one"'}, steps, game=True)
