"""A divisor obligation survives the node wrappers coercions add (a union member, a conversion)."""
import subprocess

from tests.support import compiler  # noqa: F401

PROGRAM = '''Bad:type=type of error & [code:int64]
modulo=(p:int64):>int64|Bad=>{
    if p <? 0 return Bad[code=p]
    return p % (-7)
}
main=():>void=>{
    printl(modulo(15) is? Bad)
}
'''


def test_divisor_in_a_union_result_is_checked_not_a_compiler_crash(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(PROGRAM)
    result = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0 and 'panic: facts.jo' not in result.stderr, result.stderr
    assert result.stdout == 'false\n', result.stdout
