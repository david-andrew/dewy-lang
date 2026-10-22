"""Buffered input preserves byte contents and cursor behavior across refills."""
import subprocess

import pytest

from tests.support import compiler


PROGRAM = r'''
main=(args:array<string>):>void=>exit(entry(args)) entry=(args:array<string>):>int64=>{
if args[1]=?"stdin" {
    let all=read_stdin()
    if all is? Canceled return 6
    write(all)
    let tail=read_stdin()
    return if tail is? string and tail=?"" and read_line() is?none 0 else 1
}
if args[1]=?"after-line" {
    let line=read_line()
    if line is?none return 2
    if line is?Canceled return 6
    let tail=read_stdin()
    if tail is?Canceled return 6
    write(line) write("|") write(tail)
    return if read_line() is?none 0 else 3
}
let opened=open_file(args[1])
if opened is?none return 4
if opened is?Canceled return 6
let f=opened
if args.length>?2 {
 let data=f.read_bytes(3)
 if data is?Canceled return 6
 write(str_from_bytes(data)) write("|")
}
loop true {
    let line=f.read_line()
    if line is?none break
    if line is?Canceled return 6
    write(line) write("\n")
}
let last=f.read_bytes(1)
if last is?Canceled return 6
if last.length not=?0 or f.read_line() isnt?none return 5
f.close()
return 0}
'''


@pytest.fixture(params=['default', 'release', 'debug'])
def input_program(compiler, tmp_path, request):
    source = tmp_path / 'input.dewy'
    source.write_text(PROGRAM)
    binary = tmp_path / 'input'
    flags = {'default': [], 'release': ['--release'], 'debug': ['-g']}[request.param]
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def normalized_lines(data):
    # This API recognizes LF and removes one CR immediately before LF or EOF.
    if not data:
        return b''
    lines = data.split(b'\n')
    if data.endswith(b'\n'):
        lines.pop()
    return b''.join(line.removesuffix(b'\r') + b'\n' for line in lines)


@pytest.mark.core_quick
def test_core_file_line_refills(input_program, tmp_path):
    cases = [b'', b'\n', b'\r\n\n', b'last', b'last\r', b'a\x00b\r\nlast',
             'café Ω\n尾\r\n'.encode(), b'a\rb\n']
    cases += [b'a' * n + b'\r\n' + b'last\r' for n in (65534, 65535, 65536, 131071)]
    cases += [b'prefix\n' + b'z' * (5 * 65536 + 19) + b'\nend']
    for index, data in enumerate(cases):
        path = tmp_path / f'lines-{index}.txt'
        path.write_bytes(data)
        for prefix in (False, True):
            command = [input_program, path, *(['prefix'] if prefix else [])]
            ran = subprocess.run(command, capture_output=True, timeout=10)
            expected = ((data[:3] + b'|' + normalized_lines(data[3:])) if prefix
                        else normalized_lines(data))
            assert ran.returncode == 0, (index, prefix, ran.returncode, ran.stderr)
            assert ran.stdout == expected, (index, prefix, len(ran.stdout), len(expected))


@pytest.mark.core_quick
def test_core_stdin_buffered_tail(input_program):
    cases = [b'', b'\x00\xff\n\r', 'café Ω尾'.encode()]
    cases += [bytes(range(256)) * n + b'tail\x00' for n in (16, 256, 1025)]
    for data in cases:
        ran = subprocess.run([input_program, 'stdin'], input=data, capture_output=True, timeout=10)
        assert ran.returncode == 0, (ran.returncode, ran.stderr)
        assert ran.stdout == data
    for n in (0, 1, 4094, 4095, 4096, 65535):
        first = b'x' * n
        tail = bytes(range(256)) * 260 + b'last\x00'
        ran = subprocess.run([input_program, 'after-line'], input=first + b'\r\n' + tail,
                             capture_output=True, timeout=10)
        assert ran.returncode == 0, (n, ran.returncode, ran.stderr)
        assert ran.stdout == first + b'|' + tail, n
