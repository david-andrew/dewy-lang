"""Attempts cannot hide a possible later wait, or certify a failed transfer."""
import subprocess

import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('maker,typ', [('channel', 'Channel'), ('mpmc', 'Mpmc')])
def test_try_receive_cannot_hide_later_cycle(compiler, tmp_path, maker, typ):
    source = tmp_path / 'attempt_cycle.dewy'
    source.write_text(f'''ping = (out:{typ}<int64> back:{typ}<int64>):>void => {{
    out.try_send(1);
    out.try_receive;
    out.send(2);
    out.send(3);
    back.receive;
}}
main = () => {{
    let a = {maker}<int64>(1)
    let b = {maker}<int64>(1)
    concurrent {{ spawn ping(a b); spawn ping(b a) }}
}}
''')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    # The attempt's outcome is not proved; a warning is required, never silence.
    assert run.returncode == 0, run.stderr
    assert 'warning:' in run.stderr and 'may wait forever' in run.stderr, run.stderr


def test_attempt_is_not_a_guaranteed_filler(compiler, tmp_path):
    source = tmp_path / 'failed_filler.dewy'
    source.write_text('''main = () => {
    let c = channel<int64>(1)
    concurrent {
        spawn { c.try_send(1); }
        c.receive;
        c.receive;
    }
}
''')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    assert 'warning:' in run.stderr and 'may wait forever' in run.stderr, run.stderr


@pytest.mark.parametrize('maker,typ', [('channel', 'Channel'), ('mpmc', 'Mpmc')])
def test_attempt_through_returned_alias_affects_original(compiler, tmp_path, maker, typ):
    source = tmp_path / 'alias_cycle.dewy'
    source.write_text(f'''alias = (q:{typ}<int64>):>{typ}<int64> => q
main = () => {{
    let a = {maker}<int64>(1)
    let b = {maker}<int64>(1)
    let aa = alias(a)
    let bb = alias(b)
    concurrent {{
        spawn {{ aa.try_send(1); a.send(2); b.receive; }}
        spawn {{ bb.try_send(1); b.send(2); a.receive; }}
    }}
}}
''')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    assert 'warning:' in run.stderr and 'may wait forever' in run.stderr, run.stderr
