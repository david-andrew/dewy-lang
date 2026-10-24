"""Atomic stores obey plain fixed-width narrowing before publishing a sum."""
import subprocess
import shutil

import pytest

from tests.support import compiler, Scripts


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('payload,maximum', [('int64', 2**63-1), ('uint64', 2**64-1), ('int8', 127)])
@pytest.mark.parametrize('policy', ['', "<overflow='wrap'>", "<overflow='saturate'>"])
def test_atomic_store_boundary(compiler, tmp_path, payload, maximum, policy, target):
    source = tmp_path / 'atomic.dewy'
    source.write_text((f'''main=()=>{{
        let a=atomic<{payload}{policy}>({maximum})
        printl(a.add(1))
    }}''') + "\n$runtime_checks\n")
    binary = tmp_path / 'atomic'
    built = subprocess.run([compiler, 'build', source, '-o', binary] + (['--target', 'wasm32'] if target == 'wasm' else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is required for Wasm execution')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'atomic.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True)
    if policy:
        expected = maximum if 'saturate' in policy else 0 if payload == 'uint64' else -(maximum+1)
        assert ran.returncode == 0 and ran.stdout.strip() == str(expected), ran.stderr
    else:
        assert ran.returncode != 0 and not ran.stdout, ran.stderr
