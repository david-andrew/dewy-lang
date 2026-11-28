"""A `$extern` named like another engine's callback is C's function, not a misspelled hook."""
import os
import subprocess

from tests.support import compiler  # noqa: F401

ENV = dict(os.environ, DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')


def test_extern_quit_names_are_not_hooks(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('''$extern
on_exit = (f:((status:int32 arg:ptr<uint8>?):>void) arg:ptr<uint8>?):>int32
$export
bye = (_status:int32 _arg:ptr<uint8>?):>void => {}
main = ():>void => {
    $unsafe on_exit(@bye none);
    printl("main")
}
''')
    run = subprocess.run([compiler, source], env=ENV, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout == 'main\n'
    assert 'warning:' not in run.stderr, run.stderr


def test_quit_hook_near_miss_still_warns(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('''update = (dt:float64):>void => {}
on_exit = ():>void => printl("bye")
''')
    built = subprocess.run([compiler, 'check', source], env=ENV, capture_output=True, text=True, timeout=60)
    assert 'nothing calls on_exit' in built.stdout + built.stderr
