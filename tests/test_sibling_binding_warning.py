"""A binding given sibling literals warns, suggesting an annotation; an annotated one does not."""
import subprocess

from tests.support import compiler  # noqa: F401

FAMILY = '''Shape:type=type of any & [name:string='shape']
Circle:type=type of Shape & [r:int64]
Square:type=type of Shape & [s:int64]
'''


def check(compiler, tmp_path, body):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(FAMILY + 'main=()=>{\n' + body + '}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if 'warning:' in line]


def test_sibling_binding_warns_with_annotations(compiler, tmp_path):  # noqa: F811
    warnings = check(compiler, tmp_path, '    let s = Circle[r=1]\n    printl(s.r)\n    s = Square[s=2]\n    printl(s.s)\n')
    assert len(warnings) == 1, warnings
    assert ':5:9:' in warnings[0], warnings
    for hint in ('Circle | Square', '`let s:Circle|Square = ...`', '`let s:Circle = ...`', '`let s:Square = ...`'):
        assert hint in warnings[0], warnings


def test_annotated_or_same_type_binding_is_quiet(compiler, tmp_path):  # noqa: F811
    assert check(compiler, tmp_path, '    let s:Circle|Square = Circle[r=1]\n    printl(s.r)\n    s = Square[s=2]\n    printl(s.s)\n') == []
    assert check(compiler, tmp_path, '    let s = Circle[r=1]\n    s = Circle[r=2]\n    printl(s.r)\n') == []
