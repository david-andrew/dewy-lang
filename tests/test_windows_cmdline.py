"""Windows command lines: every argument reads back unchanged under CommandLineToArgvW's rules."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

SEPARATOR = '--next--'

# The quoting function itself, built for this machine: each group of arguments its command
# line, as byte values.
QUOTER = '''
main = ():
    argv = args()
    group: str[]
    loop a in argv[1..]:
        if a == "--next--":
            print(bytes(__w32_cmdline(group)))
            group.clear()
        else: group.push(a)
'''

VECTORS = [
    ['prog'],
    ['C:\\Program Files\\tool.exe', 'plain'],
    ['prog', ''],
    ['prog', 'a b', 'c\td', 'e\nf', 'g\vh'],
    ['prog', 'say "hi"', '"', '""', 'x"'],
    ['prog', 'dir\\', 'dir with space\\', 'C:\\a\\b\\\\', '\\\\server\\share\\'],
    ['prog', 'a\\"b', 'a\\\\"b', 'a\\\\\\"b', '\\"', '\\\\"', 'trail\\\\'],
    ['prog', 'x" & calc.exe & "', '" --flag "', 'a\\" injected "b'],
    ['prog', 'unicode é 日本', 'tab\tand\\\\back"slash'],
]


def parse_command_line(line):
    """CommandLineToArgvW (and the C runtime since 2008): the program name up to the next
    quote or space, then arguments with the backslash and quote rules."""
    out = []
    i = 0
    n = len(line)
    if i < n and line[i] == '"':
        end = line.index('"', 1)
        out.append(line[1:end])
        i = end + 1
    else:
        end = i
        while end < n and line[end] not in ' \t':
            end += 1
        out.append(line[i:end])
        i = end
    while True:
        while i < n and line[i] in ' \t':
            i += 1
        if i >= n:
            return out
        arg = []
        quoted = False
        while i < n and (quoted or line[i] not in ' \t'):
            if line[i] == '\\':
                count = 0
                while i < n and line[i] == '\\':
                    count += 1
                    i += 1
                if i < n and line[i] == '"':
                    arg.append('\\' * (count // 2))
                    if count % 2:
                        arg.append('"')
                        i += 1
                else:
                    arg.append('\\' * count)
            elif line[i] == '"':
                if quoted and i + 1 < n and line[i + 1] == '"':
                    arg.append('"')
                    i += 2
                else:
                    quoted = not quoted
                    i += 1
            else:
                arg.append(line[i])
                i += 1
        out.append(''.join(arg))


@pytest.mark.core_quick
def test_parser_reference():
    assert parse_command_line(r'p a\\\"b "c d" e\f "g\\"') == ['p', 'a\\"b', 'c d', 'e\\f', 'g\\']


@pytest.mark.core_quick
def test_command_lines_round_trip(compiler, tmp_path):
    source = tmp_path / 'quoter.jo'
    source.write_text(QUOTER)
    binary = tmp_path / 'quoter'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    argv = [str(binary)]
    for vector in VECTORS:
        argv += vector + [SEPARATOR]
    ran = subprocess.run(argv, capture_output=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.decode().splitlines()
    assert len(lines) == len(VECTORS)
    for vector, line in zip(VECTORS, lines):
        text = bytes(int(b) for b in line.strip('[]').split(', ') if b).decode()
        assert parse_command_line(text) == vector, text
    # (no quotes where none are needed)
    assert lines[0] == '[' + ', '.join(str(b) for b in b'prog') + ']'


ECHO = '''$runtime_checks
main=()=>{
    loop a in args()[1..] printl(a.length)
    loop a in args()[1..] printl(a)
}
'''

RUNNER = '''$runtime_checks
main=()=>{
    let argv=args()
    let status=run(argv[1] argv[2..])
    if status is? int64 exit(status)
    exit(99)
}
'''


@pytest.mark.skipif(os.name != 'nt', reason='a Windows child process reads its own command line')
def test_windows_run_round_trip(compiler, tmp_path):
    binaries = {}
    for name, program in (('echo', ECHO), ('runner', RUNNER)):
        source = tmp_path / f'{name}.dewy'
        source.write_text(program)
        binary = tmp_path / f'{name}.exe'
        built = subprocess.run([compiler, 'build', source, '-o', binary],
                               capture_output=True, text=True, timeout=60, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        binaries[name] = binary
    for vector in VECTORS[1:]:
        args = [a for a in vector[1:] if '\n' not in a and '\v' not in a]
        ran = subprocess.run([binaries['runner'], binaries['echo'], *args],
                             capture_output=True, timeout=30, check=False)
        assert ran.returncode == 0, ran.stderr
        lines = ran.stdout.decode().splitlines()
        assert lines == [str(len(a)) for a in args] + args
