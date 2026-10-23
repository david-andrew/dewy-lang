"""An error reaching main prints its kind and `message` only, unless the build is a debug build
(-g): the rest of a payload may hold secrets."""
import subprocess

from tests.support import compiler

SOURCE = '''AuthError:type=type of error & [message:string secret:string]
Offline:type=type of error & [host:string]
main=(args:array<string>):>void|AuthError|Offline=>{
    if args.length >? 1 return Offline["internal.example"]
    return AuthError[message="login failed" secret="hunter2"]
}
'''


def _stderr(compiler, tmp_path, flags, *args):
    source = tmp_path / 'err.dewy'
    source.write_text(SOURCE)
    binary = tmp_path / ('err' + ''.join(flags))
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary], capture_output=True,
                           text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary, *args], capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode in (1, 2)
    return ran.stderr.strip()


def test_default_and_release_builds_hide_the_payload(compiler, tmp_path):
    for flags in ([], ['--release']):
        assert _stderr(compiler, tmp_path, flags) == 'error: AuthError: login failed'
        assert _stderr(compiler, tmp_path, flags, 'x') == 'error: Offline'


def test_debug_build_prints_the_payload(compiler, tmp_path):
    assert _stderr(compiler, tmp_path, ['-g']) == 'error: AuthError[message="login failed" secret="hunter2"]'
