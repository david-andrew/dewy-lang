"""A failed `$expect` notes the value of each non-literal comparison operand, calls included."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''roman = (n:int64):>string => if n >? 0 "XL" else ""
$test
called = () => $expect roman(40) =? "XXXX", "subtractive"
$test
computed = () => {
    let xs = [1 2]
    $expect [loop x in xs x*2] =? [2 5]
}
main = () => 0
'''


def test_expect_operand_notes(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'notes.dewy'
    source.write_text(SOURCE)
    result = subprocess.run([compiler, 'test', source], capture_output=True, text=True,
                            timeout=60, check=False)
    assert result.returncode == 2, result.stdout + result.stderr
    notes = [line for line in (result.stdout + result.stderr).splitlines() if line.startswith('note:')]
    assert notes == ['note: roman(40) is XL', 'note: [loop x in xs x*2] is [2 4]'], result.stdout + result.stderr
