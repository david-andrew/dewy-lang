"""RSP frames preserve the established panic trace across mixed and stack-argument calls."""
import os
import platform
import subprocess

import pytest

from tests.support import compiler


RECURSION = '''@noinline
recurse = (n: int, a: int, b: int, c: int, d: int, e: int, f: int, g: int) -> int:
    if n == 0: panic("frame probe")
    recurse(n - 1, g, f, e, d, c, b, a) + a
@noinline
outer = (n: int) -> int:
    recurse(n, 1, 2, 3, 4, 5, 6, 7)
'''
# Keep enough parameters live over the call to require a large frame. The loop
# makes this an RBP frame while outer/recurse use RSP in non-debug native builds.
MIXED = RECURSION + ('@noinline\nwide = (' + ', '.join(f'x{i}: int' for i in range(24))
                     + ') -> int:\n    t = 0\n    loop j in [0..x0): t += j\n'
                     + '    r = outer(x0)\n    r + t + '
                     + ' + '.join(f'x{i}' for i in range(24)) + '\n'
                     + 'print(wide(' + ', '.join(str(i + 4) for i in range(24)) + '))\n')


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']], ids=['default', 'release', 'debug'])
@pytest.mark.parametrize('worker', [False, True], ids=['direct', 'worker'])
def test_rsp_panic_backtrace(compiler, tmp_path, flags, worker):
    if platform.machine().lower() not in ('x86_64', 'amd64') or platform.system() != 'Linux':
        pytest.skip('RSP unwinding is the Linux x86-64 backend')
    source = tmp_path / 'frames.jo'
    source.write_text(MIXED)
    binary = tmp_path / 'frames'
    env = {**os.environ, 'DEWY_EMIT_WORKERS': '1'}
    if worker:
        env['DEWY_EMIT_FORCE'] = '1'
    else:
        env.pop('DEWY_EMIT_FORCE', None)
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           env=env, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 101, ran.stderr
    assert ran.stdout == ''
    # Golden output from the frame-pointer backend, including recursion folding,
    # exact call-site lines and the top-level frame (no compiler helper frames).
    assert ran.stderr == ('panic: frame probe\n'
                          '    in recurse (frames.jo:3)\n'
                          '    called from recurse (frames.jo:4) (4 times)\n'
                          '    called from outer (frames.jo:7)\n'
                          '    called from wide (frames.jo:12)\n'
                          '    called from the top level of frames (frames.jo:14)\n')


def check_trace(compiler, tmp_path, name, source, flags, expected):
    path = tmp_path / f'{name}.jo'
    path.write_text(source)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', path, *flags, '-o', binary],
                           env={**os.environ, 'DEWY_EMIT_WORKERS': '1'},
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert (ran.returncode, ran.stdout, ran.stderr) == (101, '', expected)


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_rsp_fault_backtrace(compiler, tmp_path, flags):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('Linux x86-64 signal context')
    check_trace(compiler, tmp_path, 'fault', '''@noinline
read_ptr = (p: int) -> int:
    (p as *int)[0]
@noinline
outer = (p: int) -> int:
    read_ptr(p) + 1
print(outer(0))
''', flags, 'panic: crashed: memory access at 0x0 (a bad pointer, in code using raw pointers or C?)\n'
            '    in read_ptr\n'
            '    called from outer (fault.jo:6)\n'
            '    called from the top level of fault (fault.jo:7)\n')


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_rsp_foreign_callback_backtrace(compiler, tmp_path, flags):
    import json
    import shutil

    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64') or not shutil.which('cc'):
        pytest.skip('Linux x86-64 C interoperability')
    c = tmp_path / 'foreign.c'
    c.write_text('static volatile long result;\n'
                 'void invoke(void (*f)(long), long n) { f(n); result = n; }\n')
    library = tmp_path / 'foreign.so'
    built = subprocess.run(['cc', '-shared', '-fPIC', '-O2', c, '-o', library],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    check_trace(compiler, tmp_path, 'foreign', f'@lib({json.dumps(str(library))})\n' + '''extern invoke = (f: cfn(int), n: int)
@cabi
callback = (n: int):
    panic("foreign frame")
@noinline
cross = (n: int):
    f: cfn(int) = callback
    invoke(f, n)
@noinline
outer = (n: int):
    cross(n)
outer(7)
''', flags, 'panic: foreign frame\n'
            '    in callback (foreign.jo:5)\n'
            '    called from cross (foreign.jo:9)\n'
            '    called from outer (foreign.jo:12)\n'
            '    called from the top level of foreign (foreign.jo:13)\n')
