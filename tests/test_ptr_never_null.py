"""`xs.ptr` is a ptr<T>, never null, on every target: an empty or zeroed array's is a real
address. The native C boundary is in tests/cases/ffi/ptr_*_to_c; here the web page's
imports stand in for C, and ARM64 (which loads no C library under QEMU) reads through it."""
import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name  # noqa: F401 (fixture)

# The page's functions standing in for C: the address it was handed, and C's strlen.
PAGE_C = '''const pageC = {imports: (mem) => ({
  page_address: (p) => BigInt(p),
  strlen: (p) => { const m = new Uint8Array(mem().buffer); let n = Number(p); while (m[n]) n++; return BigInt(n - Number(p)); },
})};
'''
PAGE_PROGRAM = '''page_address=(p:ptr<uint8>):>uint64 => $extern
strlen=(s:ptr<uint8>):>uint64 => $extern
main=():>void=>$unsafe {
    let empty:array<uint8>=[]
    let rows:array<array<uint8>>=[[104 105 0]]
    rows.resize(2)
    let zeroed=rows[1]
    let names:array<string>=["dewy"]
    names.resize(2)
    let unset=names[1]
    printl(page_address(empty.ptr) not=? 0 page_address(zeroed.ptr) not=? 0 page_address((unset as array<uint8>).ptr) not=? 0)
    printl(strlen((unset as array<uint8>).ptr) strlen(rows[0].ptr) strlen((names[0] as array<uint8>).ptr))
    printl(page_address(rows[0].ptr + 1) - page_address(rows[0].ptr) rows[0].ptr[1])
}
$runtime_checks
'''


def build(compiler, tmp_path, source, flags):
    path = tmp_path / 'probe.dewy'
    path.write_text(source)
    binary = tmp_path / 'probe'
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ptr_reaches_page_imports(compiler, tmp_path, release):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is needed to run a web build')
    flags = ['--target', target_name('wasm'), *(['--release'] if release else [])]
    binary = build(compiler, tmp_path, PAGE_PROGRAM, flags)
    scripts = Scripts()
    scripts.feed(binary.with_suffix('.html').read_text())
    script = '\n'.join(scripts.parts)
    assert 'dewy.run(bin)' in script
    runner = tmp_path / 'probe.cjs'
    runner.write_text(PAGE_C + script.replace('dewy.run(bin)', '(dewy.extra.push(pageC), dewy.run(bin))'))
    ran = subprocess.run([node, runner], capture_output=True, text=True, timeout=30, check=False)
    assert (ran.returncode, ran.stdout) == (0, 'true true true\n0 2 4\n1 105\n'), ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ptr_never_null_arm64(compiler, tmp_path, release):
    qemu = shutil.which('qemu-aarch64') or shutil.which('qemu-aarch64-static')
    if qemu is None:
        pytest.skip('QEMU is needed to run an ARM64 build')
    source = '''first=(p:ptr<uint8>):>uint8 => $unsafe p[0]
main=():>void=>$unsafe {
    let names:array<string>=["dewy"]
    names.resize(2)
    let unset=names[1]
    printl(first((unset as array<uint8>).ptr) first((names[0] as array<uint8>).ptr))
    let rows:array<array<uint8>>=[[7 8]]
    rows.resize(2)
    let zeroed=rows[1]
    let p=zeroed.ptr
    printl(zeroed.length first(rows[0].ptr) rows[0].ptr[1] (p + 0) =? p)
}
$runtime_checks
'''
    flags = ['--target', target_name('linux-arm64'), *(['--release'] if release else [])]
    binary = build(compiler, tmp_path, source, flags)
    ran = subprocess.run([qemu, binary], capture_output=True, text=True, timeout=30, check=False)
    assert (ran.returncode, ran.stdout) == (0, '0 100\n0 7 8 true\n'), ran.stderr
