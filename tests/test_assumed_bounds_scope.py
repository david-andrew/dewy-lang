"""`$no_assumed_bounds` acts in its scope (docs/LANGUAGE.md): the array-length ceiling
is lifted for code written there, not for other modules that are compiled with it,
nor for other functions of its own module."""
import subprocess

from tests.support import compiler  # noqa: F401

GROW = '''grow = (n:int64):>void => {
    let p:array<int64<(<? p.length)>> = []
    loop _ in [0..n) { p.push(p.length) }
    printl(p.length)
}
'''
STRICT = '$no_assumed_bounds\nbig = (hi:int64):>void => printl(hi)\n'
BULLETPROOF = '$bulletproof\nident = (a:int64):>int64 => a\n'
REFUSED = 'cannot prove refinement `p.length <? p.length + 1`'


def run(compiler, tmp_path, files, command='run'):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_alone(compiler, tmp_path):
    result = run(compiler, tmp_path, {'grow.dewy': GROW, 'main.dewy': 'import p"grow.dewy"\ngrow(3)\n'})
    assert result.returncode == 0 and result.stdout == '3\n', result.stdout + result.stderr


def test_other_module_strict(compiler, tmp_path):
    files = {'strict.dewy': STRICT, 'grow.dewy': GROW, 'main.dewy': 'import p"strict.dewy"\nimport p"grow.dewy"\ngrow(3)\nbig(1)\n'}
    result = run(compiler, tmp_path, files)
    assert result.returncode == 0 and result.stdout == '3\n1\n', result.stdout + result.stderr


def test_other_module_bulletproof(compiler, tmp_path):
    files = {'bp.dewy': BULLETPROOF, 'grow.dewy': GROW,
             'main.dewy': 'import p"bp.dewy"\nimport p"grow.dewy"\ngrow(2)\nprintl(ident(5))\n'}
    result = run(compiler, tmp_path, files)
    assert result.returncode == 0 and result.stdout == '2\n5\n', result.stdout + result.stderr


def test_strict_module_own_code(compiler, tmp_path):
    # The strict module itself still proves without the ceiling, whoever imports it.
    files = {'grow.dewy': '$no_assumed_bounds\n' + GROW, 'main.dewy': 'import p"grow.dewy"\ngrow(3)\n'}
    result = run(compiler, tmp_path, files, 'check')
    assert result.returncode != 0 and 'grow.dewy:4:' in result.stderr and REFUSED in result.stderr, result.stderr


def test_strict_importer_of_lax_module(compiler, tmp_path):
    # A strict main importing a module without the setting: main's own push is refused.
    main = '$no_assumed_bounds\nimport p"grow.dewy"\ngrow(3)\nlet q:array<int64<(<? q.length)>> = []\nloop _ in [0..4) { q.push(q.length) }\n'
    result = run(compiler, tmp_path, {'grow.dewy': GROW, 'main.dewy': main}, 'check')
    assert result.returncode != 0 and 'main.dewy:5:' in result.stderr and 'grow.dewy' not in result.stderr, result.stderr


def test_sibling_function(compiler, tmp_path):
    # A function-level setting leaves the module's other functions their ceiling.
    source = GROW + 'strict = (n:int64):>void => {\n    $no_assumed_bounds\n    printl(n)\n}\ngrow(3)\nstrict(1)\n'
    result = run(compiler, tmp_path, {'main.dewy': source})
    assert result.returncode == 0 and result.stdout == '3\n1\n', result.stdout + result.stderr


def test_function_level_setting(compiler, tmp_path):
    source = GROW.replace('=> {\n', '=> {\n    $no_assumed_bounds\n', 1) + 'grow(3)\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'check')
    assert result.returncode != 0 and REFUSED in result.stderr, result.stderr


def test_nested_block_setting(compiler, tmp_path):
    # A block inside the function holding the setting: the push in it is refused.
    source = GROW.replace('    loop _ in [0..n) { p.push(p.length) }\n',
                          '    if n >? 0 {\n        $no_assumed_bounds\n        loop _ in [0..n) { p.push(p.length) }\n    }\n') + 'grow(3)\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'check')
    assert result.returncode != 0 and REFUSED in result.stderr, result.stderr
