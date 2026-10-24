"""Branch alignment cannot add NOPs to a repeatedly executed scalar loop."""
import platform
import re
import shutil
import subprocess

import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_loop_padding_stays_outside_backedge(compiler, tmp_path, release):
    if platform.machine().lower() not in ('x86_64', 'amd64') or not shutil.which('objdump'):
        pytest.skip('x86-64 disassembly test')
    source = tmp_path / 'gcd.dewy'
    source.write_text('''gcd=(a:int64 b:int64):>int64=>{
let x=a;let y=b
loop y not=? 0 {let r=x%y;x=y;y=r}
return x
}
main=(args:array<string>)=>{
let a=int64(to_int(args[1]) ?? 0)
let b=int64(to_int(args[2]) ?? 0)
printl(gcd(a b))
}
''')
    binary = tmp_path / 'gcd'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    disassembly = subprocess.check_output(['objdump', '-d', binary], text=True)
    function = re.search(r'<gcd>:\n(.*?)(?=\n\n)', disassembly, re.S)
    assert function, disassembly
    instructions = []
    for line in function[1].splitlines():
        match = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*(\S.*)', line)
        if match:
            instructions.append((int(match[1], 16), match[2]))
    loops = []
    for address, instruction in instructions:
        jump = re.match(r'j\w+\s+([0-9a-f]+)\s', instruction)
        if jump and int(jump[1], 16) < address:
            loops.append((int(jump[1], 16), address))
    assert loops, function[1]
    for start, end in loops:
        assert not any('nop' in op for addr, op in instructions if start <= addr <= end), function[1]
    ran = subprocess.run([binary, '99999', '360360'], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.strip() == '9', ran.stdout + ran.stderr
