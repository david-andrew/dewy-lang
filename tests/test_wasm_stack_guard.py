"""Large wasm frames must not overwrite the module's constant data."""
import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler


def test_large_recursive_frames_trap_before_data(compiler, tmp_path):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed to execute the web runner')
    source = tmp_path / 'frames.dewy'
    source.write_text('''count=(n:int64):>int64=>{
 let data:array<int64 length=32768>=[]
 data[0]=n
 if n =? 0 return data[0]
 let inner=count(n-1)
 return inner+data[0]
}
main=():>void=>exit(count(32))
''')
    output = tmp_path / 'frames'
    built = subprocess.run([compiler, 'build', source, '--target', 'wasm32', '-o', output],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    scripts = Scripts()
    scripts.feed(output.with_suffix('.html').read_text())
    runner = output.with_suffix('.cjs')
    runner.write_text('\n'.join(scripts.parts))
    ran = subprocess.run([node, runner], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 101, ran.stdout + ran.stderr
    assert 'unreachable' in ran.stderr, ran.stderr
