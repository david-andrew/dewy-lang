"""`m.x(...)` with x a variable of module m: the error names m's x, not a name of the calling file."""
import subprocess

from tests.support import compiler  # noqa: F401


def check(compiler, source):  # noqa: F811
    return subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)


def test_module_variable_called(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'm.dewy').write_text('let count:int64 = 3\ndouble = (x:int64):>int64 => x * 2\n')
    sources = {
        'plain.dewy': 'import p"m.dewy" as m\nmain = () => printl(m.count(4))\n',
        'local.dewy': 'import p"m.dewy" as m\nmain = () => {\n    let count:string = "x"\n    printl(m.count(4))\n}\n',
        'global.dewy': 'import p"m.dewy" as m\nlet count:bool = true\nmain = () => printl(m.count(4))\n',
    }
    for name, text in sources.items():
        (tmp_path / name).write_text(text)
        checked = check(compiler, tmp_path / name)
        assert checked.returncode != 0, name
        assert "'count' is a variable of type int64, not a function" in checked.stderr, (name, checked.stderr)


def test_module_function_beside_variable(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'm.dewy').write_text(('double = (x:int64):>int64 => x * 2\n') + "\n$runtime_checks\n")
    source = tmp_path / 'main.dewy'
    source.write_text(('import p"m.dewy" as m\nlet double:int64 = 5\nmain = () => printl(m.double(4) + double)\n') + "\n$runtime_checks\n")
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 0 and ran.stdout == '13\n', ran.stderr
