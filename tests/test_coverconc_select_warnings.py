"""Named and conditional receive waits participate in channel diagnostics."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('wait', ['@ready', 'if active @a.receive else none',
                                  'if active @ready else none'])
@pytest.mark.parametrize('queue', ['channel', 'mpmc'])
def test_prepared_select_receivers_are_visible(compiler, tmp_path, wait, queue):
    source = tmp_path / 'fan_in.dewy'
    prepare = '    let ready = @a.receive\n' if '@ready' in wait else ''
    source.write_text(f'''produce = (out:{'Channel' if queue == 'channel' else 'Mpmc'}<int64> n:int64) => {{
    loop i in [0..n) {{ out.send(i) or_throw }}
    out.close()
}}
main = () => {{
    let a = {queue}<int64>(1)
    let b = {queue}<int64>(1)
{prepare}    let active = true
    concurrent {{
        spawn produce(a 10)
        spawn produce(b 10)
        loop active {{
            match select({wait}) {{
                _:int64 => {{}}
                <Closed> => {{active = false}}
                <Canceled> => break
            }}
        }}
    }}
}}
''')
    result = subprocess.run([compiler, 'check', source], capture_output=True,
                            text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    warnings = [line for line in result.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == 1, result.stderr
    assert "may wait to send into 'b'" in warnings[0], result.stderr
