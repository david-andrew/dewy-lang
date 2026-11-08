"""The precedence help after a type error: said only where the operand `as` or `??` takes, written without
parentheses, is what the error lands on; an operand the program grouped itself, and errors elsewhere, get none."""
import subprocess

from tests.support import compiler  # noqa: F401


def check(compiler, tmp_path, body):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text('main = () => {\n    let b:array<uint8> = [82 73 70 70]\n    let m:bool | none = none\n' + body + '\n}\n')
    return subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)


def test_parenthesized_operands_get_no_help(compiler, tmp_path):  # noqa: F811
    for body in ('    printl((b.length >=? 4 and b[0..4)) as string ?? "")',
                 '    printl((m ?? b.length) >? 3)',
                 '    printl(b.length >=? 4 and (b[0..4) as string ?? ""))'):
        checked = check(compiler, tmp_path, body)
        assert checked.returncode != 0 and 'type mismatch' in checked.stderr, (body, checked.stderr)
        assert 'binds looser' not in checked.stderr and 'binds tighter' not in checked.stderr, (body, checked.stderr)


def test_other_errors_inside_the_operand_get_no_help(compiler, tmp_path):  # noqa: F811
    for body in ('    printl(b.length >=? 4 and nothing as string)',
                 '    printl(m ?? nothing >? 3)'):
        checked = check(compiler, tmp_path, body)
        assert checked.returncode != 0, body
        assert 'binds looser' not in checked.stderr and 'binds tighter' not in checked.stderr, (body, checked.stderr)


def test_the_grouping_meant_compiles(compiler, tmp_path):  # noqa: F811
    for body in ('    printl(b.length >=? 4 and (b[0..4) as string ?? "") =? "RIFF")',
                 '    printl(m ?? (b.length >? 3))'):
        checked = check(compiler, tmp_path, body)
        assert checked.returncode == 0, (body, checked.stderr)
