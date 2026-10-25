"""Byte scan idioms preserve short circuiting, exit indices and bounded loads."""
import platform

import pytest

from tests.support import compiler
from tests.test_byte_find import build_run


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [(), ('--release',), ('-g',), ('--target', 'wasm32')])
def test_scan_loop_bytes(compiler, tmp_path, flags):
    ir = build_run(compiler, tmp_path, '''
@noinline
scan = (p: u8[], start: int, n: int, c: u8) -> int:
    i = start
    loop i < n and p[i] != c: i += 1
    i
@noinline
skip = (p: u8[], start: int, n: int, c: u8) -> int:
    i = start
    loop i < n and p[i] == c: i += 1
    i
@noinline
array_scan = (a: u8[], start: int, stop: int, c: u8) -> int:
    i = start
    loop i < stop and a[i] != c: i += 1
    i
@noinline
oracle = (p: u8[], start: int, n: int, c: u8, equal: bool) -> int:
    loop i in [start..n):
        if (p[i] == c) != equal: return i
    if start < n: n else: start
main = () -> int:
    a = fill(u8(0), 300)
    p = data(a)
    loop byte in [0..256):
        c = u8(byte)
        loop j in [0..300): p[j] = c
        loop n in [0, 1, 7, 8, 9, 15, 16, 17, 31, 32, 33, 127, 255, 257]:
            loop at in [0, 1, n / 2, n - 1, n, n + 1]:
                if at >= 0: p[at] = c xor 1
                loop start in [0, 1, 7, n, n + 1]:
                    if scan(a, start, n, c xor 1) != oracle(a, start, n, c xor 1, false): return 1
                    if skip(a, start, n, c) != oracle(a, start, n, c, true): return 2
                    if array_scan(a, start, n, c xor 1) != oracle(a, start, n, c xor 1, false): return 3
                if at >= 0: p[at] = c
    if scan(a, 9223372036854775807, 0, u8(1)) != 9223372036854775807: return 4
    if skip(a, 0, 0, u8(1)) != 0: return 5
    p[0] = 1
    # A stop beyond the array is harmless when an earlier byte stops the scan.
    if array_scan(a, 0, 400, u8(1)) != 0: return 7
    42
''', flags)
    if platform.machine().lower() in ('x86_64', 'amd64') and not flags:
        assert 'findbyte' in ir


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('no_avx', [False, True], ids=['avx2-host', 'sse2'])
def test_scan_loop_guard_pages(compiler, tmp_path, release, no_avx):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('guard-page syscalls require x86-64 Linux')
    build_run(compiler, tmp_path, '''
@noinline
scan = (p: u8[], n: int, c: u8) -> int:
    i = 0
    loop i < n and p[i] != c: i += 1
    i
@noinline
skip = (p: u8[], n: int, c: u8) -> int:
    i = 0
    loop i < n and p[i] == c: i += 1
    i
@noinline
tally = (p: u8[], n: int, c: u8) -> int:
    i = 0
    count = 0
    loop i < n:
        if p[i] == c: count += 1
        i += 1
    count
@noinline
class_scan = (p: u8[], n: int) -> int:
    i = 0
    loop i < n and p[i] >= u8(128): i += 1
    i
main = () -> int:
    area = syscall(9, 0, 12288, 3, 0x22, -1, 0)
    if area < 0: return 1
    if syscall(10, area, 4096, 0) != 0: return 2
    if syscall(10, area + 8192, 4096, 0) != 0: return 3
    loop n in [0..258):
        loop at_end in [false, true]:
            p = (if at_end: area + 8192 - n else: area + 4096 + 24) as *u8
            # An actual array header establishes the readable byte span.
            (p as *int)[-3] = -1
            (p as *int)[-2] = n
            (p as *int)[-1] = n
            a: u8[]
            (&a as **u8)[0] = p - 24
            loop c in [u8(0), u8(1), u8(128), u8(255)]:
                loop j in [0..n): p[j] = c
                if scan(a, n, c xor 1) != n or skip(a, n, c) != n: return 4
                if tally(a, n, c) != n: return 7
                if class_scan(a, n) != (if c >= 128: n else: 0): return 8
                loop j in [0..n):
                    p[j] = c xor 1
                    if scan(a, n, c xor 1) != j or skip(a, n, c) != j: return 5
                    if tally(a, n, c) != n - 1: return 9
                    p[j] = c
    if syscall(11, area, 12288) != 0: return 6
    42
''', ('--release',) if release else (), no_avx)


CLASS_PREDICATES = [
    "p[i] == u8(32) or p[i] == u8(9) or p[i] == u8(10) or p[i] == u8(13)",
    "p[i] >= u8(48) and p[i] <= u8(57)",
    "(p[i] >= u8(65) and p[i] <= u8(90)) or p[i] == u8(95) or (p[i] >= u8(97) and p[i] <= u8(122)) or p[i] >= u8(128)",
    "p[i] == c",
    "p[i] != c",
]


@pytest.mark.parametrize('flags', [(), ('--release',), ('-g',), ('--target', 'wasm32')])
@pytest.mark.parametrize('predicate', CLASS_PREDICATES)
def test_scan_loop_classes_and_counts(compiler, tmp_path, flags, predicate):
    ir = build_run(compiler, tmp_path, f'''
@noinline
scan = (p: u8[], start: int, n: int, c: u8) -> int:
    i = start
    loop i < n and ({predicate}): i += 1
    i
@noinline
tally = (p: u8[], start: int, n: int, c: u8) -> int:
    i = start
    count = 13
    loop i < n:
        if {predicate}: count += 1
        i += 1
    count + i * 1000
@noinline
oracle_scan = (p: u8[], start: int, n: int, c: u8) -> int:
    loop i in [start..n):
        if not ({predicate}): return i
    if start < n: n else: start
@noinline
oracle_tally = (p: u8[], start: int, n: int, c: u8) -> int:
    count = 13
    loop i in [start..n):
        if {predicate}: count += 1
    count + (if start < n: n else: start) * 1000
main = () -> int:
    a = fill(u8(0), 280)
    p = data(a)
    loop byte in [0..256):
        c = u8(byte)
        loop j in [0..280): p[j] = c
        loop n in [0, 1, 7, 8, 15, 16, 17, 31, 32, 33, 127, 255, 257]:
            loop start in [0, 1, 7, n, n + 1]:
                if scan(a, start, n, c) != oracle_scan(a, start, n, c): return 1
                if tally(a, start, n, c) != oracle_tally(a, start, n, c): return 2
        loop j in [0..280): p[j] = u8((byte + j) % 256)
        loop n in [0, 1, 7, 8, 15, 16, 17, 31, 32, 33, 127, 255, 257]:
            if scan(a, 0, n, c) != oracle_scan(a, 0, n, c): return 3
            if tally(a, 0, n, c) != oracle_tally(a, 0, n, c): return 4
    42
''', flags)
    if platform.machine().lower() in ('x86_64', 'amd64') and not flags:
        assert 'scanbytes' in ir


@pytest.mark.parametrize('flags', [(), ('--release',), ('-g',), ('--target', 'wasm32')])
def test_scan_loop_dewy_const_table(compiler, tmp_path, flags):
    table = ' '.join(str(int(65 <= c <= 90 or c == 95 or 97 <= c <= 122 or c >= 128) * 34)
                     for c in range(256))
    source = tmp_path / 'class.dewy'
    source.write_text('''$runtime_checks
const classes:array<uint8 length=256>=[''' + table + ''']
scan=(p:array<uint8> n:int64):>int64=>$unsafe {
    let i:int64=0
    loop i <? n and classes[p[i]] & 34 not=? 0 {i+=1}
    i
}
tally=(p:array<uint8> n:int64):>int64=>$unsafe {
    let i:int64=0
    let count:int64=0
    loop i <? n {
        if classes[p[i]] & 34 not=? 0 {count+=1}
        i+=1
    }
    count
}
check_classes=(p:array<uint8> n:int64):>int64=>scan(p n)+tally(p n)*1000
''')
    ir = build_run(compiler, tmp_path, f'''use '{source}'
main = () -> int:
    a = fill(u8(65), 257)
    p = data(a)
    if check_classes(a, 257) != 257257: return 1
    p[133] = 0
    if check_classes(a, 257) != 256133: return 2
    loop j in [0..257): p[j] = 255
    if check_classes(a, 257) != 257257: return 3
    42
''', flags)
    if platform.machine().lower() in ('x86_64', 'amd64') and not flags:
        assert 'scanbytes' in ir


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_scan_loop_graphemes_and_overflow_fallback(compiler, tmp_path, flags):
    source = tmp_path / 'semantics.dewy'
    source.write_text('''$runtime_checks
scan_text=(text:string):>int64=>{
    let i:int64=0
    loop i <? text.length and text[i] not=? "x" {i+=1}
    i
}
check_text=():>int64=>scan_text("é🇺🇸x")
''')
    build_run(compiler, tmp_path, f'''use '{source}'
@noinline
tally = (p: u8[], n: int, initial: int) -> int:
    count = initial
    i = 0
    loop i < n:
        if p[i] == u8(1): count += 1
        i += 1
    count
main = () -> int:
    if check_text() != 2: return 1
    a = fill(u8(1), 64)
    # Jo's int wraps; the versioned counter guard must keep that fallback.
    if tally(a, 64, 9223372036854775807) != -9223372036854775745: return 2
    if tally(a, 64, -100) != -36: return 3
    42
''', flags)


def test_scan_loop_parallel_classes(compiler, tmp_path):
    from tests.test_core_fused_determinism import check
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('fused workers require x86-64 Linux')
    source = tmp_path / 'classes.dewy'
    functions = []
    for k in range(30):
        functions.append(f'''scan{k}=(a:array<uint8>):>int64=>{{
    let i:int64=0
    loop i <? a.length and (a[i] =? {k} or a[i] =? {k + 2}) {{i+=1}}
    i
}}''')
    source.write_text('\n'.join(functions) + '\nmain=():>void=>{\nlet a:array<uint8>=[0 2 1]\n' +
                      '\n'.join(f'printl(scan{k}(a))' for k in range(30)) + '\n}\n$runtime_checks\n')
    check(compiler, source, tmp_path, DEWY_EMIT_FORCE='1')


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_scan_loop_class_live_registers(compiler, tmp_path, flags):
    # Keep caller-saved integer and vector values live across class scans/counts.
    floats = '\n'.join(f'    x{k} = f64(n + {k}) * 0.5' for k in range(24))
    uses = ' + '.join(f'x{k}' for k in range(24))
    searches = '\n'.join(f'''    r{k} = {k}
    loop r{k} < n and (p[r{k}] == u8(1) or p[r{k}] == u8(3)): r{k} += 1''' for k in range(24))
    sum_searches = ' + '.join(f'r{k}' for k in range(24))
    build_run(compiler, tmp_path, '''@noinline
probe = (p: u8[], n: int) -> int:
''' + floats + '\n' + searches + f'\n    int({uses}) + {sum_searches}\n' + '''
main = () -> int:
    a = fill(u8(1), 96)
    a[60] = 2
    if probe(a, 96) != 2730: return 1
    a[60] = 3
    if probe(a, 96) != 3594: return 2
    42
''', flags)


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_scan_loop_unproved_pointer_span(compiler, tmp_path, flags):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('guard-page syscalls require x86-64 Linux')
    build_run(compiler, tmp_path, '''
@noinline
raw_scan = (p: *u8, n: int, c: u8) -> int:
    i = 0
    loop i < n and p[i] != c: i += 1
    i
@noinline
raw_class = (p: *u8, n: int) -> int:
    i = 0
    loop i < n and (p[i] == u8(1) or p[i] == u8(3)): i += 1
    i
main = () -> int:
    area = syscall(9, 0, 8192, 3, 0x22, -1, 0)
    if area < 0: return 1
    if syscall(10, area + 4096, 4096, 0) != 0: return 2
    p = (area + 4095) as *u8
    p[0] = 42
    # The actual accessed byte is valid, despite n extending into the guard page.
    if raw_scan(p, 100, u8(42)) != 0 or raw_class(p, 100) != 0: return 3
    if syscall(11, area, 8192) != 0: return 4
    42
''', flags)
