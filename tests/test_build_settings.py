"""`$build.mode` and `$target` set in the main file; the command line overrides them."""
import platform
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

HOST = 'x86_64-linux'
REPORT = "main = () => {\n    printl($build.mode)\n    printl($target)\n}\n"


def native_host():
    if platform.machine() != 'x86_64' or platform.system() != 'Linux':
        pytest.skip('the expectation is for an x86-64 Linux host')


def run(compiler, tmp_path, source, *options, name='main.dewy', command=()):
    path = tmp_path / name
    path.write_text(source)
    return subprocess.run([compiler, *command, *options, path], capture_output=True, text=True,
                          timeout=120, check=False, cwd=tmp_path)


@pytest.mark.core_quick
def test_file_sets_build_mode(compiler, tmp_path):
    native_host()
    ran = run(compiler, tmp_path, "$build.mode = 'release'  # the shipped build\n" + REPORT)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'release\n{HOST}\n'
    assert 'warning' not in ran.stderr


def test_default_is_debug_for_this_machine(compiler, tmp_path):
    native_host()
    ran = run(compiler, tmp_path, REPORT)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'debug\n{HOST}\n'


def test_file_sets_target(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('$target = "wasm32"\nmain = () => printl($target.arch)\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'game'], capture_output=True, text=True,
                           timeout=120, check=False)
    assert built.returncode == 0, built.stderr
    assert (tmp_path / 'game.html').exists()
    assert 'warning' not in built.stderr


def test_expressions_check_the_settings(compiler, tmp_path):
    native_host()
    # (folded: the dead arms name functions that do not exist)
    source = ("$build.mode = 'release'\n$target = 'x86_64-linux'\nmain = () => {\n"
              "    if $build.mode =? 'debug' { missing_one() } else { printl('release arm') }\n"
              "    if $target.os =? 'windows' { missing_two() } else if $target.arch =? 'x86_64' { printl('x86') }\n"
              "}\n")
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'release arm\nx86\n'


@pytest.mark.parametrize('setting, flag', [("release", '--release'), ("debug", '--debug')])
def test_agreeing_override_is_quiet(compiler, tmp_path, setting, flag):
    native_host()
    ran = run(compiler, tmp_path, f"$build.mode = '{setting}'\n$target = '{HOST}'\n" + REPORT, flag, '--target', HOST)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'{setting}\n{HOST}\n'
    assert 'warning' not in ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('setting, flag', [("release", '--debug'), ("debug", '--release')])
def test_conflicting_mode_override_warns(compiler, tmp_path, setting, flag):
    native_host()
    ran = run(compiler, tmp_path, f"\n$build.mode = '{setting}'\n" + REPORT, flag)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'{flag[2:]}\n{HOST}\n'
    assert (f"main.dewy:2:1: warning: {flag} overrides `$build.mode = '{setting}'`: "
            f"this is a {flag[2:]} build") in ran.stderr


def test_conflicting_target_override_warns(compiler, tmp_path):
    native_host()
    ran = run(compiler, tmp_path, "$target = 'wasm32'\n" + REPORT, '--target', HOST)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'debug\n{HOST}\n'
    assert (f"warning: --target {HOST} overrides `$target = 'wasm32'`: this build is for {HOST}") in ran.stderr


def test_build_command_overrides_too(compiler, tmp_path):
    native_host()
    source = tmp_path / 'main.dewy'
    source.write_text("$build.mode = 'debug'\n" + REPORT)
    built = subprocess.run([compiler, 'build', source, '--release', '-o', tmp_path / 'main'], capture_output=True,
                           text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stderr
    assert "--release overrides `$build.mode = 'debug'`" in built.stderr
    ran = subprocess.run([tmp_path / 'main'], capture_output=True, text=True, timeout=10, check=False)
    assert ran.stdout == f'release\n{HOST}\n'


def test_file_target_outranks_the_output_name(compiler, tmp_path):
    native_host()
    source = tmp_path / 'main.dewy'
    source.write_text(f"$target = '{HOST}'\n" + REPORT)
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'main.exe'], capture_output=True,
                           text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([tmp_path / 'main.exe'], capture_output=True, text=True, timeout=10, check=False)
    assert ran.stdout == f'debug\n{HOST}\n'


@pytest.mark.core_quick
@pytest.mark.parametrize('option', ['--runtime-checks', '--runtime_checks=false', '$no_hidden_costs',
                                    '--bulletproof', '--fast-math', '--unsafe'])
@pytest.mark.parametrize('command', [(), ('build',)])
def test_safety_and_semantic_settings_are_refused(compiler, tmp_path, option, command):
    path = tmp_path / 'main.dewy'
    path.write_text(REPORT)
    words = [*command, path, option] if command else [option, path]
    ran = subprocess.run([compiler, *words], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 2, ran.stdout + ran.stderr
    assert 'cannot be set from the command line' in ran.stderr
    assert 'the command line sets only the build mode, --release or --debug, and the target, --target' in ran.stderr


def test_unknown_option_is_not_a_path(compiler, tmp_path):
    path = tmp_path / 'main.dewy'
    path.write_text(REPORT)
    ran = subprocess.run([compiler, 'build', path, '--fast'], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 2
    assert "unknown option '--fast'" in ran.stderr


@pytest.mark.parametrize('source, message', [
    ("main = () => {\n    $build.mode = 'release'\n}\n",
     "main.dewy:2:5: error: `$build.mode` is set at the top level of the program's main file"),
    ("$build.mode = 'release'\n$build.mode = 'debug'\nmain = () => 0\n",
     "main.dewy:2:1: error: `$build.mode` is set twice"),
    ("let m = 'release'\n$build.mode = m\nmain = () => 0\n",
     "`$build.mode` is set to a name in quotes, as `$build.mode = 'release'`"),
    ("$build.mode = 'fast'\nmain = () => 0\n", 'unknown build mode "fast"'),
    ("$target = 'wasm'\nmain = () => 0\n", "`$target`: unknown target 'wasm'"),
    ("$target.os = 'linux'\nmain = () => 0\n",
     "`$target.os` is part of the target: set the whole target, as `$target = 'aarch64-linux'`"),
    ("$build.debug\nmain = () => 0\n", "not `debug`: test `$build.mode =? 'debug'`"),
    ("main = () => 0\nx = 1  $target = 'wasm32'\n", "`$target = ...` goes on a line of its own, at its start"),
    ("#{\n$build.mode = 'release'\n}#\nmain = () => printl($build.mode)\n", None),
])
def test_setting_mistakes(compiler, tmp_path, source, message):
    ran = run(compiler, tmp_path, source)
    if message is None:
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == 'debug\n'
        return
    assert ran.returncode != 0
    assert message in ran.stderr, ran.stderr


def test_only_the_main_file_sets_them(compiler, tmp_path):
    (tmp_path / 'helper.dewy').write_text("$build.mode = 'release'\nhelp = () => 1\n")
    ran = run(compiler, tmp_path, 'import p"helper.dewy"\nmain = () => printl(help())\n')
    assert ran.returncode != 0
    assert "helper.dewy:1:1: error: `$build.mode` is set by the program's main file" in ran.stderr
