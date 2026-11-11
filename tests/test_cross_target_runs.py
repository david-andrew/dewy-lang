"""Programs whose behavior once differed by target, run on each: x86-64 Linux natively,
aarch64 Linux under qemu-aarch64, x86-64 Windows under Wine in the sloppy-wine container."""
import platform
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

WINE_IMAGE = 'localhost/sloppy-wine:latest'
TARGETS = ['x86_64-linux', 'aarch64-linux', 'x86_64-windows']


def wine_ready():
    podman = shutil.which('podman')
    return podman is not None and subprocess.run([podman, 'image', 'exists', WINE_IMAGE], capture_output=True,
                                                 timeout=30).returncode == 0


def build(compiler, tmp_path, source, target, *flags):
    (tmp_path / 'main.dewy').write_text(source)
    binary = tmp_path / ('main.exe' if 'windows' in target else 'main')
    built = subprocess.run([compiler, 'build', tmp_path / 'main.dewy', '--target', target, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=300, cwd=tmp_path)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(target, binary, *args, setup=''):
    """Run a built program on its target: (exit status, stdout, stderr)."""
    if target == 'x86_64-linux':
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            pytest.skip('needs an x86-64 Linux host')
        command = [binary, *args]
    elif target == 'aarch64-linux':
        if (runner := shutil.which('qemu-aarch64')) is None:
            pytest.skip('no qemu-aarch64')
        command = [runner, binary, *args]
    else:
        if not wine_ready():
            pytest.skip(f'the Windows run needs podman and {WINE_IMAGE}')
        script = f'{setup} wine /w/{binary.name} "$@"'
        command = ['podman', 'run', '--rm', '-e', 'LANG=C.UTF-8', '-v', f'{binary.parent}:/w:z', WINE_IMAGE,
                   'sh', '-c', script, 'sh', *args]
    ran = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=300, cwd=binary.parent)
    return ran.returncode, ran.stdout.replace('\r\n', '\n'), ran.stderr.replace('\r\n', '\n')


# Every iteration overflows its stack, on the main thread and on the pool's workers at once:
# each worker's stack ends in a guard and has its own signal stack, so the first overflow is
# reported (once) and nothing runs into a neighbouring worker's stack.
WORKER_OVERFLOW = """$program.max_cores = 4
$runtime_checks

depth = (n:int64):>int64 => if n <=? 0 0 else 1 + depth(n - 1)
main = (argv:array<string>):>void => {
    let n = to_int(argv[1]) ?? 0
    if 0 <=? n and n <=? 100000000 {
        printl([parallel s in [0..16) depth(n + s)].sum)
    }
}
"""


@pytest.mark.parametrize('target', TARGETS)
def test_worker_stack_overflow_is_reported(compiler, tmp_path, target):
    binary = build(compiler, tmp_path, WORKER_OVERFLOW, target)
    assert run(target, binary, '1000')[:2] == (0, '16120\n')
    for _ in range(3):
        status, out, err = run(target, binary, '1000000')
        assert status == 101, (status, err[-2000:])
        assert err.count('panic: stack overflow') == 1, err[-2000:]


# A task's stack overflows into its guard: its own signal stack, between two guards, lets the
# handler report it (tasks run on Linux only).
TASK_OVERFLOW = """$runtime_checks

depth = (n:int64):>int64 => if n <=? 0 0 else 1 + depth(n - 1)
main = (argv:array<string>):>void => {
    let n = to_int(argv[1]) ?? 0
    if 0 <=? n and n <=? 100000000 {
        concurrent {
            let a = spawn depth(n)
            let b = spawn depth(n + 1)
        }
        printl"{a} {b}"
    }
}
"""


@pytest.mark.parametrize('target', ['x86_64-linux', 'aarch64-linux'])
def test_task_stack_overflow_is_reported(compiler, tmp_path, target):
    binary = build(compiler, tmp_path, TASK_OVERFLOW, target)
    assert run(target, binary, '1000')[:2] == (0, '1000 1001\n')
    status, out, err = run(target, binary, '1000000')
    assert status == 101 and err.count('panic: stack overflow') == 1, (status, err[-2000:])


def far_branch_program():
    """One function over 1 MB of arm64 code: an if/else, a loop with `continue` and `break`
    and an overflow check all branch across more than a conditional branch reaches."""
    body = lambda line: [line.format(k=k, m=k % 89 + 2) for k in range(16000)]
    return '\n'.join([
        '$runtime_checks', '',
        'big = (n:int64 mode:int64):>int64 => {',
        '    let i:int64 = 0', '    let t:int64 = 0', '    let u:int64 = 1',
        '    loop i <? n {', '        i += 1', '        if i % 3 =? 0 { continue }',
        '        if mode =? 2 and i =? 2 { break }', '        if i % 2 =? 0 {',
        *body('            u = (u * {m} + {k}) % 1000003'), '        } else {',
        *body('            u = (u + {k} * t) % 999983'), '        }',
        '        t = (t + u) % 1000000007', '    }',
        '    if mode =? 1 {', '        let top:int64 = int64.max - 10 + t % 2', '        return top + 20', '    }',
        '    return t + i', '}',
        'main = (argv:array<string>):>void => {', '    let m = to_int(argv[1]) ?? 0',
        '    if 0 <=? m and m <=? 5 { printl"{big(7 0)} {big(5 2)} {big(3 m)}" }', '}', ''])


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_arm64_branches_reach_across_large_functions(compiler, tmp_path, flags):
    binary = build(compiler, tmp_path, far_branch_program(), 'aarch64-linux', *flags)
    assert run('aarch64-linux', binary, '0')[:2] == (0, '1886348 3 683785\n')
    status, out, err = run('aarch64-linux', binary, '1')
    assert (status, 'integer overflow' in err) == (101, True), (status, out, err)


# A machine set to India Standard Time, as Windows names it, is in Asia/Kolkata: CLDR's table
# says Asia/Calcutta, the name tz keeps only as a link.
WINDOWS_ZONE = """$time.zone = 'system'

main = (argv:array<string>):>void => {
    let text = if argv.length >? 1 argv[1] else "2026-07-01T12:00"
    printl(zoned(text))
}
"""


def test_windows_zone_names_are_current(compiler, tmp_path):
    source = WINDOWS_ZONE.replace("'system'", "'India Standard Time'")
    binary = build(compiler, tmp_path, source, 'x86_64-linux')
    assert run('x86_64-linux', binary)[:2] == (0, '2026-07-01T12:00:00+05:30[Asia/Kolkata]\n')


def test_windows_machine_zone_reads_as_linux_does(compiler, tmp_path):
    binary = build(compiler, tmp_path, WINDOWS_ZONE, 'x86_64-windows')
    status, out, err = run('x86_64-windows', binary,
                           setup='ln -sf /usr/share/zoneinfo/Asia/Kolkata /etc/localtime && unset TZ &&')
    assert (status, out) == (0, '2026-07-01T12:00:00+05:30[Asia/Kolkata]\n'), err


# Windows reads `\` as a separator and `C:\` or `\\server\share\` as a root, as pathlib does.
WINDOWS_PATHS = r"""main = ():>void => {
    loop text in ["C:\\Users\\ann\\notes.txt" "\\\\srv\\share\\d\\f.txt" "dir\\sub\\x.tar.gz" "C:\\" "a/b\\c"] {
        let q = p(text)
        printl"{q.name} {q.parent} {q.parts} {q.is_absolute} {q.with_suffix(".md")}"
    }
}
"""


def test_windows_paths_split_at_backslashes(compiler, tmp_path):
    binary = build(compiler, tmp_path, WINDOWS_PATHS, 'x86_64-windows')
    status, out, err = run('x86_64-windows', binary)
    assert (status, out.splitlines()) == (0, [
        'notes.txt C:/Users/ann ["C:/" "Users" "ann" "notes.txt"] true C:/Users/ann/notes.md',
        'f.txt //srv/share/d ["//srv/share/" "d" "f.txt"] true //srv/share/d/f.md',
        'x.tar.gz dir/sub ["dir" "sub" "x.tar.gz"] false dir/sub/x.tar.md',
        ' C:/ ["C:/"] true C:/.md',
        'c a/b ["a" "b" "c"] false a/b/c.md']), err
