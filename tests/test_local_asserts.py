"""`$runtime_assert` is its module's own explicit handling: it makes its
function `panics` only for callers in other modules (decisions.md, 2026-10-23),
unless the scope says `$assume_local_asserts=false` (assumptions.md)."""
import subprocess

from tests.support import compiler  # noqa: F401

HELPER = '''checked=(x:int64):>int64=>{
    $runtime_assert x >? 0
    return x
}
twice=(x:int64):>int64=>checked(x)*2
'''


def run(compiler, tmp_path, files, *arguments):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return subprocess.run([compiler, *arguments, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_same_module(compiler, tmp_path):
    # The module's own callers, transitively and through a handle, are not `panics`.
    source = HELPER + 'apply=(f:<(x:int64):>int64> x:int64):>int64=>f(x)\nmain=():>void=>printl(twice(3) + apply(@checked 1))\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'run')
    assert result.returncode == 0 and result.stdout == '7\n', result.stdout + result.stderr


def test_same_module_fails_at_run_time(compiler, tmp_path):
    result = run(compiler, tmp_path, {'main.dewy': HELPER + 'main=():>void=>printl(twice(0))\n'}, 'run')
    assert result.returncode == 101, result.stdout + result.stderr


def test_other_module(compiler, tmp_path):
    # A caller in another module sees `panics`, through the helper module's own callers too.
    files = {'helper.dewy': HELPER, 'main.dewy': '$runtime_checks=false\nfrom p"helper.dewy" import twice\nmain=():>void=>printl(twice(3))\n'}
    result = run(compiler, tmp_path, files, 'check')
    assert result.returncode != 0 and 'main.dewy:3:23: error: calling `twice` may panic (twice -> checked: `$runtime_assert` at' in result.stderr, result.stderr


def test_other_module_opted_in(compiler, tmp_path):
    files = {'helper.dewy': HELPER, 'main.dewy': 'from p"helper.dewy" import twice\nmain=():>void=>{\n    $runtime_checks\n    printl(twice(3))\n}\n'}
    result = run(compiler, tmp_path, files, 'run')
    assert result.returncode == 0 and result.stdout == '6\n', result.stdout + result.stderr


def test_opt_out(compiler, tmp_path):
    # `$assume_local_asserts=false` makes the module's own callers prove it or opt in.
    result = run(compiler, tmp_path, {'main.dewy': '$runtime_checks=false\n$assume_local_asserts=false\n' + HELPER + 'main=():>void=>printl(twice(3))\n'}, 'check')
    assert result.returncode != 0 and 'calling `checked` may panic (checked: `$runtime_assert` at' in result.stderr, result.stderr


def test_row_excludes_local(compiler, tmp_path):
    # A row excluding panics is a promise to every caller: a local assert breaks it.
    source = HELPER + 'strict=(x:int64):>int64 & no panics=>twice(x)\nmain=():>void=>printl(strict(3))\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'check')
    assert result.returncode != 0 and "effect contract violation in 'strict': it may panic" in result.stderr, result.stderr
