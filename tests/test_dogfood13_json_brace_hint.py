"""A JSON-looking string error gives a usable raw literal spelling."""
import subprocess

from tests.support import compiler  # noqa: F401


def test_json_brace_hint_and_raw_string(compiler, tmp_path):
    bad = tmp_path / 'json_bad.dewy'
    bad.write_text('main=()=>{let raw="{\\"version\\":1}"; printl(raw)}\n')
    checked = subprocess.run([compiler, 'check', bad], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'unterminated string' in checked.stderr
    assert "r'...'" in checked.stderr

    good = tmp_path / 'json_good.dewy'
    good.write_text('main=()=>printl(r\'{"version":1}\')\n')
    checked = subprocess.run([compiler, 'check', good], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    output = tmp_path / 'json_good'
    built = subprocess.run([compiler, 'build', good, '-o', output], text=True,
                           capture_output=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([output], text=True, capture_output=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == '{"version":1}\n', ran.stdout + ran.stderr

    # A real interpolation still parses and evaluates as an expression.
    interpolated = tmp_path / 'interpolated.dewy'
    interpolated.write_text('main=()=>{let version=1; printl("version {version}")}\n')
    checked = subprocess.run([compiler, 'check', interpolated], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
