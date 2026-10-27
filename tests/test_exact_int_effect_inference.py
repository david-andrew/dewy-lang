"""Early callback-row inference must preserve exact arithmetic at word limits."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_callback_inference_preserves_exact_comparison(compiler, tmp_path, flags):
    source = tmp_path / 'callback.dewy'
    source.write_text('''$runtime_checks
less=(a:int64 b:int64):>bool=>a+b <? 0
apply=(f:<(a:int64 b:int64):>bool & allocates> a:int64 b:int64):>bool & allocates=>f(a b)
main=(args:array<string>)=>{
 let a=int64(to_int(args[1]) ?? 0)
 let b=int64(to_int(args[2]) ?? 0)
 printl(apply(@less a b))
}
''')
    binary = tmp_path / 'callback'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for a, b in [(2**63-1, 1), (-2**63, -1), (2**63-1, 2**63-1),
                 (-2**63, -2**63), (1, -2)]:
        ran = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.strip() == str(a+b < 0).lower()
