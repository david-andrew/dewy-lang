"""A read-only loop item inherits its source's counter dependencies."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('dependent', [False, True])
def test_iteration_progress_depends_on_source(compiler, tmp_path, dependent):
    source = tmp_path / 'iteration.dewy'
    values = '[count]' if dependent else '[2 3]'
    source.write_text(('''main=(args:array<string>)=>{
let count=int64(to_int(args[1]) ?? 0)
loop round in [0..2) {loop step in ''' + values + ''' {count+=step}}
printl(count)
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'iteration'
    result = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    run = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    if dependent:
        assert run.returncode == 101 and not run.stdout
    else:
        assert run.returncode == 0 and run.stdout.strip() == str(2**62 + 10)


def test_counter_dependency_through_array_argument(compiler, tmp_path):
    source = tmp_path / 'array_call.dewy'
    source.write_text(('''read=(xs:array<int64>):>int64=>xs[0]
main=(args:array<string>)=>{
let count=int64(to_int(args[1]) ?? 0)
loop round in [0..2) {let xs=[count];count+=read(xs)}
printl(count)
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'array_call'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    bad = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout
