"""Local promotion preserves ABI boundaries and reduces frame traffic."""
from pathlib import Path
import subprocess

import pytest

from udewy import p0, t1
from udewy.backend import get_backend


def test_promoted_locals_match_stack_execution(tmp_path):
    source = (Path(__file__).parents[2] / 'udewy/tests/test_local_registers.udewy').read_text()
    outputs = []
    for enabled in (False, True):
        backend = get_backend('x86_64')
        backend.debug_info = False
        if not enabled:
            backend._allocate_locals = lambda: None
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


# ---------------------------------------------------------------------------
# The shared allocator (LocalRegisterAllocator / la_* in common.udewy)
# ---------------------------------------------------------------------------

from udewy.backend.common import LocalRegisterAllocator


def _allocate(sites, *, loops=(), clobbers=(), allocs=None, callee=('C0', 'C1'), caller=('S0', 'S1')):
    allocator = LocalRegisterAllocator()
    for key, line in (allocs or {}).items():
        allocator.note_alloc(key, line)
    for line, key, other, store in sites:
        allocator.note_site(line, key, other, store)
    for start, end in loops:
        allocator.begin_loop(start)
        allocator.end_loop(end)
    for line in clobbers:
        allocator.note_clobber(line)
    allocator.assign(list(callee), list(caller))
    return allocator


def test_call_free_intervals_take_scratch_registers_first():
    allocator = _allocate([(1, 0, 'x', True), (5, 0, 'x', False), (2, 1, 'x', True), (9, 1, 'x', False)])
    assert allocator.assignment == ['S0', 'S1']


def test_intervals_spanning_a_clobber_only_take_preserved_registers():
    allocator = _allocate([(1, 0, 'x', True), (9, 0, 'x', False)], clobbers=[4])
    assert allocator.assignment == ['C0']
    # Clobbers outside the interval do not constrain it.
    allocator = _allocate([(1, 0, 'x', True), (9, 0, 'x', False)], clobbers=[0, 10])
    assert allocator.assignment == ['S0']


def test_loops_widen_values_declared_before_them():
    # Declared at line 0, touched inside the loop [3, 20] with a call at 15.
    allocator = _allocate([(1, 0, 'x', True), (5, 0, 'x', False)], loops=[(3, 20)], clobbers=[15], allocs={0: 0})
    assert allocator.assignment == ['C0']
    # Declared inside the loop body: the store precedes every read per iteration.
    allocator = _allocate([(4, 0, 'x', True), (5, 0, 'x', False)], loops=[(3, 20)], clobbers=[15], allocs={0: 4})
    assert allocator.assignment == ['S0']


def test_nested_loops_widen_through_every_enclosing_loop():
    sites = [(1, 0, 'x', True), (12, 0, 'x', False)]
    allocator = _allocate(sites, loops=[(10, 14), (5, 30)], clobbers=[25], allocs={0: 0})
    assert allocator.assignment == ['C0']


def test_busier_intervals_evict_quieter_ones_when_registers_run_out():
    sites = [(1, 0, 'x', True), (40, 0, 'x', False)]        # score 2
    sites += [(2, 1, 'x', True), (41, 1, 'x', False)]       # score 2
    sites += [(3, 2, 'x', True)] + [(10 + i, 2, 'x', False) for i in range(8)]  # score 9
    allocator = _allocate(sites, clobbers=[30], callee=('C0', 'C1'), caller=())
    assert allocator.assignment == [None, 'C1', 'C0']


def test_registers_are_reused_after_an_interval_ends():
    sites = [(1, 0, 'x', True), (3, 0, 'x', False), (5, 1, 'x', True), (7, 1, 'x', False)]
    allocator = _allocate(sites, callee=(), caller=('S0',))
    assert allocator.assignment == ['S0', 'S0']


def test_single_use_and_pinned_slots_stay_in_memory():
    allocator = LocalRegisterAllocator()
    allocator.note_site(1, 0, 'x', True)
    allocator.note_site(2, 1, 'x', True)
    allocator.note_site(3, 1, 'x', False)
    allocator.pin(1)
    allocator.assign(['C0'], ['S0'])
    assert allocator.assignment == [None, None]


def test_rewrite_turns_sites_into_their_register_form():
    allocator = _allocate([(0, 0, '    movq %rax, ', ''), (2, 0, '    cmpq $3, ', '')])
    code = ['    movq %rax, -48(%rbp)', 'other', '    cmpq $3, -48(%rbp)']
    allocator.rewrite(code)
    assert code == ['    movq %rax, S0', 'other', '    cmpq $3, S0']


# ---------------------------------------------------------------------------
# Every native backend allocates through the shared pass.
# ---------------------------------------------------------------------------

CROSS_TARGET_SOURCE = '''
let helper = (x:int):>int => { return x + 1 }
let with_calls = (n:int):>int => {
    let acc:int = 0
    let i:int = 0
    loop i <? n {
        acc = acc + helper(i)
        i = i + 1
    }
    return acc
}
let call_free = (n:int):>int => {
    let total:int = 0
    let i:int = 0
    loop i <? n {
        total = total + i * i
        i = i + 1
    }
    return total
}
let main = ():>int => {
    if with_calls(10) not=? 55 { return 1 }
    if call_free(10) not=? 285 { return 2 }
    return 0
}
'''

CROSS_TARGET_EXPECTATIONS = {
    # (a loop value that survives calls, a loop value in a call-free loop)
    'x86_64': ('movq %rax, %rbx', 'movq %rax, %r8'),
    'arm': ('mov x19, x0', 'mov x11, x0'),
    'riscv': ('mv s1, a0', 'mv t2, a0'),
}


@pytest.mark.parametrize('target', sorted(CROSS_TARGET_EXPECTATIONS))
def test_every_native_backend_allocates_loop_locals(target):
    backend = get_backend(target)
    backend.debug_info = False
    assembly = p0.parse(t1.tokenize(CROSS_TARGET_SOURCE), CROSS_TARGET_SOURCE, backend)
    preserved, scratch = CROSS_TARGET_EXPECTATIONS[target]
    assert preserved in assembly and scratch in assembly
    backend = get_backend(target)
    backend.debug_info = True
    assembly = p0.parse(t1.tokenize(CROSS_TARGET_SOURCE), CROSS_TARGET_SOURCE, backend)
    assert preserved not in assembly and scratch not in assembly


def test_arm_out_of_range_slots_keep_their_frame_homes():
    count = 200
    source = '\n'.join(['let main = ():>int => {', *[f'    let v{i}:int = {i}' for i in range(count)],
                        f'    let total:int = v0 + v{count - 1}', '    loop total >? 0 { total = total - v1 - v199 }',
                        '    return total', '}'])
    backend = get_backend('arm')
    backend.debug_info = False
    assembly = p0.parse(t1.tokenize(source), source, backend)
    # v199 and total sit beyond the single-instruction offset range; v1 does not.
    assert 'str x0, [x9]' in assembly and 'ldr x0, [x9]' in assembly
    assert 'mov x11, x0' in assembly


def _cross_toolchain(prefixes, emulator):
    from shutil import which
    if which(emulator) is None:
        return None
    for prefix in prefixes:
        if which(f'{prefix}as') and which(f'{prefix}ld'):
            return prefix
    return None


# test_local_registers and test_intrinsic_operands use x86-64 syscall numbers
# and fail on AArch64 with or without allocation.
@pytest.mark.parametrize('fixture', ['test_cached_operands.udewy', 'test_immediate_operands.udewy',
                                     'test_address_displacements.udewy', 'test_pending_operands.udewy'])
def test_allocated_arm_programs_run_under_qemu(tmp_path, fixture):
    if _cross_toolchain(['aarch64-linux-gnu-', 'aarch64-elf-', 'aarch64-unknown-elf-'], 'qemu-aarch64') is None:
        pytest.skip('AArch64 toolchain or qemu-aarch64 not installed')
    source = (Path(__file__).parents[2] / 'udewy/tests' / fixture).read_text()
    for name, program in [(fixture.split('.')[0], source), ('cross_target', CROSS_TARGET_SOURCE)]:
        backend = get_backend('arm')
        backend.debug_info = False
        assembly = p0.parse(t1.tokenize(program), program, backend)
        binary = backend.compile_and_link(assembly, name, tmp_path)
        assert subprocess.run(['qemu-aarch64', str(binary)], timeout=30).returncode == 0


def test_x86_pending_values_fold_into_memory_operands():
    source = (Path(__file__).parents[2] / 'udewy/tests/test_pending_operands.udewy').read_text()
    backend = get_backend('x86_64')
    backend.debug_info = False
    assembly = p0.parse(t1.tokenize(source), source, backend)
    # A local plus offset is the base of loads and stores, a constant is
    # stored directly, and a load is compared against an immediate in place.
    import re
    assert re.search(r'movq %r12, 24\(%r\w+\)', assembly)
    assert re.search(r'movzbq 40\(%r\w+\), %rax', assembly)
    assert 'movq $7, %r12' in assembly
    assert re.search(r'cmpq \$140, 8\(%r\w+\)', assembly)
    assert re.search(r'movq \$5, %r\w+', assembly)

