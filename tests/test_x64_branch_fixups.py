"""Forward fixups preserve destinations across short-branch boundaries."""
import subprocess
from tests.support import ROOT, compiler  # noqa: F401


def test_forward_branch_destinations(compiler, tmp_path):
    source = tmp_path / 'fixups.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\n" + '''
loop backward in [false, true]:
    loop offset in [0..160):
        loop cc in [0..17):
            loop gap in [0, 1, 122, 123, 124, 125, 126, 127, 128]:
                if backward and gap != 0: continue
                code = []
                loop k in [0..offset): b(0x90)
                fix = if cc == 16: jmp32() else: jcc32(cc)
                loop k in [0..gap): b(0xCC)
                size = code.len()
                target = if backward: 0 else: size
                original = code
                patch_branch(fix, target)
                assert(original[fix] == 0 and original[fix + 3] == 0, "fixup changed shared code")
                assert(code.len() == size, "fixup moved code")
                text = "{offset} {cc} {size} {target}"
                loop value in code: text += " {int(value)}"
                print(text)
''')
    binary = tmp_path / 'fixups'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    for line in ran.stdout.splitlines():
        offset, cc, size, target, *values = map(int, line.split())
        code = bytes(values)
        assert len(code) == size and code[:offset] == b'\x90' * offset
        start = offset
        if code[start:start+2] == b'\x66\x90':
            start += 2
        elif code[start] == 0x90:
            start += 1
        if code[start] == 0xE9:
            end = start + 5
            displacement = int.from_bytes(code[start+1:end], 'little', signed=True)
            assert cc == 16
        elif code[start] == 0x0F:
            end = start + 6
            displacement = int.from_bytes(code[start+2:end], 'little', signed=True)
            assert code[start+1] == 0x80 + cc
        else:
            end = start + 2
            displacement = int.from_bytes(code[start+1:end], 'little', signed=True)
            if cc == 16:
                assert code[start] == 0xEB
                assert code[end:offset+5] == {0: b'\x0f\x1f\x00', 1: b'\x66\x90', 2: b'\x90'}[start-offset]
            else:
                assert code[start] == 0x70 + cc
                assert code[end:offset+6] == {0: b'\x0f\x1f\x40\x00', 1: b'\x0f\x1f\x00', 2: b'\x66\x90'}[start-offset]
        assert end + displacement == target
        assert code[offset + (5 if cc == 16 else 6):] == b'\xcc' * (size-offset-(5 if cc == 16 else 6))
