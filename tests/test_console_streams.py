"""console: stderr messages, colour rules and console.debug left out of release builds."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''main=()=>{
    console.info("out")
    console.warn("careful")
    console.error("failed")
    console.debug("details {count()}")
}
calls=[0]
count=():>int64=>{calls[0]+=1 printl("evaluated") return calls[0]}
'''


def run(binary, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ('NO_COLOR', 'FORCE_COLOR', 'CLICOLOR_FORCE')}
    env.update(extra)
    return subprocess.run([binary], capture_output=True, text=True, timeout=10, env=env, check=False)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_console_streams(compiler, tmp_path, release):  # noqa: F811
    source = tmp_path / 'console.dewy'
    source.write_text(SOURCE)
    binary = tmp_path / 'console'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    plain = run(binary)
    if release:
        assert (plain.stdout, plain.stderr) == ('out\n', 'careful\nfailed\n')
    else:
        assert (plain.stdout, plain.stderr) == ('out\nevaluated\n', 'careful\nfailed\ndetails 1\n')
    forced = run(binary, FORCE_COLOR='1')
    assert '\x1b[33mcareful\x1b[0m\n\x1b[31mfailed\x1b[0m\n' in forced.stderr
    assert '\x1b[' not in forced.stdout
    assert run(binary, FORCE_COLOR='1', NO_COLOR='1').stderr.startswith('careful\n')
    assert '\x1b[31m' in run(binary, CLICOLOR_FORCE='1').stderr


def test_console_color_override(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'color.dewy'
    source.write_text('console.color="always"\nmain=()=>console.error("red")\n')
    binary = tmp_path / 'color'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert run(binary, NO_COLOR='1').stderr == '\x1b[31mred\x1b[0m\n'
