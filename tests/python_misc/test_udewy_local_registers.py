"""Local promotion preserves ABI boundaries and reduces frame traffic."""
from pathlib import Path
import subprocess

from udewy import p0, t1
from udewy.backend import get_backend


def test_promoted_locals_match_stack_execution(tmp_path):
    source = (Path(__file__).parents[2] / 'udewy/tests/test_local_registers.udewy').read_text()
    outputs = []
    for enabled in (False, True):
        backend = get_backend('x86_64')
        backend.debug_info = False
        if not enabled:
            backend._promote_locals = lambda: None
        assembly = p0.parse(t1.tokenize(source), source, backend)
        binary = backend.compile_and_link(assembly, f'locals-{enabled}', tmp_path)
        assert subprocess.run([binary], timeout=5).returncode == 0
        outputs.append(assembly)
    assert outputs[1].count('(%rbp)') < outputs[0].count('(%rbp)') * .8
    assert 'movq %rax, %rbx' in outputs[1] and 'movq %rax, %r15' in outputs[1]


def test_debug_locals_keep_their_frame_locations(tmp_path):
    source = 'let main=():>int=>{let n:int=0 loop n <? 42 {n=n+1} return n}'
    backend = get_backend('x86_64')
    backend.debug_info = True
    assembly = p0.parse(t1.tokenize(source), source, backend)
    assert 'movq %rax, -48(%rbp)' in assembly
    assert 'movq -48(%rbp), %rax' in assembly
    binary = backend.compile_and_link(assembly, 'debug-locals', tmp_path)
    assert subprocess.run([binary], timeout=5).returncode == 42


def test_promoted_allocation_pointers_retain_eight_byte_rounding(tmp_path):
    source = 'let main=():>int=>{let a:int=__alloca__(1) let b:int=__alloca__(1) return a-b}'
    backend = get_backend('x86_64')
    backend.debug_info = False
    assembly = p0.parse(t1.tokenize(source), source, backend)
    binary = backend.compile_and_link(assembly, 'allocation-locals', tmp_path)
    assert subprocess.run([binary], timeout=5).returncode == 8
