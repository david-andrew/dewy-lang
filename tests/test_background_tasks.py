"""`main = (app:BackgroundTasks)` (decisions.md batch 5, D4 Q3): the program's task group. Its
tasks live as long as the program; at the end (after `main`, after the last frame, or at
`exit`) the runtime stops and joins them. Command-line arguments beside it are not yet
supported: how the two combine is still being designed. The group's own task API waits
for that design, so a library helper stands in for it here."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

# Stands in for the group's task API: a task in the program's group that runs until the
# program's end stops it, then a check after the end that it was stopped and joined.
WATCHER = '''watch_done = atomic(0)
watch = (app: BackgroundTasks) -> void:
    started = atomic(0)
    __task_spawn(app.__group, ():
        started.store(1)
        loop not __task_canceled(): __task_pause()
        watch_done.store(1)
    )
    loop started.load() == 0: __task_pause()
    __at_end(watch_report)

watch_report = () -> void:
    print(if watch_done.load() == 1: "stopped and joined at the end" else: "still running at the end")
'''


def run(compiler, tmp_path, source, *flags):
    (tmp_path / 'main.dewy').write_text(source)
    (tmp_path / 'watcher.jo').write_text(WATCHER)
    return subprocess.run([compiler, 'run', *flags, 'main.dewy'], text=True, capture_output=True, timeout=120, cwd=tmp_path)


def test_main_takes_the_programs_group(compiler, tmp_path):
    result = run(compiler, tmp_path, 'ready = (_group:BackgroundTasks) => printl"the program\'s group"\n'
                 'main = (app:BackgroundTasks) => ready(app)\n')
    assert result.returncode == 0 and result.stdout == "the program's group\n", result.stdout + result.stderr


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_group_is_stopped_and_joined_at_the_end(compiler, tmp_path, flags):
    result = run(compiler, tmp_path, 'from p"watcher.jo" import watch\n'
                 'main = (app:BackgroundTasks) => {\n    watch(app)\n    printl"main done"\n}\n', *flags)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'main done\nstopped and joined at the end\n', result.stdout + result.stderr


def test_exit_also_stops_the_group(compiler, tmp_path):
    result = run(compiler, tmp_path, 'from p"watcher.jo" import watch\n'
                 'main = (app:BackgroundTasks) => {\n    watch(app)\n    exit(3)\n}\n')
    assert result.returncode == 3 and result.stdout == 'stopped and joined at the end\n', result.stdout + result.stderr


@pytest.mark.parametrize('params', ['argv:array<string> app:BackgroundTasks', 'app:BackgroundTasks argv'])
def test_arguments_beside_it_are_not_yet_supported(compiler, tmp_path, params):
    result = run(compiler, tmp_path, f'main = ({params}) => printl(argv)\n')
    assert result.returncode != 0
    assert ('error: Dewy does not yet support `main` taking both command-line arguments and `BackgroundTasks`: '
            'how they combine is still being designed, so take one or the other') in result.stderr, result.stderr


def test_arguments_alone_still_work(compiler, tmp_path):
    result = run(compiler, tmp_path, 'main = (argv) => printl(argv.length)\n')
    assert result.returncode == 0 and result.stdout == '1\n', result.stdout + result.stderr
