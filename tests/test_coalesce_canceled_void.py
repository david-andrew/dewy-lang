"""`??` on a file operation inside a function declared `:>void` names the real issue: the
operation can give `Canceled`, which `??` passes on and a void result cannot hold."""
import subprocess

from tests.support import compiler  # noqa: F401


def build(compiler, source):  # noqa: F811
    return subprocess.run([compiler, 'build', source, '-o', source.with_suffix('')],
                          capture_output=True, text=True, timeout=60, check=False)


def test_void_function_names_canceled(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'void.dewy'
    source.write_text('main = ():>void => {\n    let files = p".".walk ?? []\n    printl(files.length)\n}\n')
    built = build(compiler, source)
    assert built.returncode != 0
    assert 'passes `Canceled` on' in built.stderr and '`:>void | Canceled`' in built.stderr, built.stderr
    assert 'does not return a value' not in built.stderr


def test_declared_canceled_or_inferred_result_works(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'fine.dewy'
    source.write_text('count = ():>void | Canceled => {\n    let files = p".".walk ?? []\n    printl(files.length >=? 0)\n}\n'
                      'main = () => {\n    let names = p".".list ?? []\n    printl(names.length >=? 0)\n}\n')
    built = build(compiler, source)
    assert built.returncode == 0, built.stderr
