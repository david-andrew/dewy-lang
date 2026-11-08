"""The watch's Windows and macOS pieces (file times, console keys, the program's pipes, builds in a
child process) as Dewy target branches: here the Linux arms agree with frozen Jo; the cross-target
builds (tests/test_cross_target_builds.py) check the Windows and macOS arms."""
from tests.selfhost_process_double import compare_watch
from tests.support import compiler  # noqa: F401


def test_watch_windows_program_matches_twin(compiler, tmp_path, monkeypatch):
    steps = [
        ('expect', 'first version'), ('expect', r'program ended \(exit status 0\)'),
        ('save', 'main.dewy', 'main=():>void=>printl"second version"'),
        ('expect', 'second version'), ('expect', r'program ended \(exit status 0\)'),
        ('key', 'r\n'), ('expect', 'second version'), ('expect', r'program ended \(exit status 0\)'),
    ]
    compare_watch(compiler, tmp_path, monkeypatch, ('watch_ops', 'watch_drive'),
                  {'main.dewy': 'main=():>void=>printl"first version"'}, steps)
