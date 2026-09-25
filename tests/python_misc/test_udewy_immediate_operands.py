"""Word boundaries and saved operands exercise both immediate and register paths."""
from pathlib import Path
import subprocess

from udewy import p0, t1
from udewy.backend import get_backend
from udewy.backend.common import Backend


def test_immediates_reduce_code_and_match_register_execution(tmp_path, monkeypatch):
    # Measured with gas's short jumps: the direct path's always-near jumps
    # add the same bytes to both builds and dilute the ratio.
    monkeypatch.setenv('UDEWY_OBJECT', 'as')
    source = (Path(__file__).parents[2] / 'udewy/tests/test_immediate_operands.udewy').read_text()
    text_sizes = []
    for optimized in (False, True):
        backend = get_backend('x86_64')
        backend.debug_info = False
        if not optimized:
            backend.binary_immediate = Backend.binary_immediate.__get__(backend)
        assembly = p0.parse(t1.tokenize(source), source, backend)
        binary = backend.compile_and_link(assembly, f'word-operations-{optimized}', tmp_path)
        assert subprocess.run([binary], timeout=5).returncode == 0
        # Compare emitted machine code, not assembly text (symbol names and
        # formatting are unrelated to the immediate-operand optimization).
        sections = subprocess.run(['size', '-A', binary], check=True,
                                  capture_output=True, text=True).stdout
        text_sizes.append(next(int(line.split()[1]) for line in sections.splitlines()
                               if line.split() and line.split()[0] == '.text'))
    assert text_sizes[1] < text_sizes[0] * .9


def test_immediate_word_operations_against_independent_expected_results(tmp_path):
    # Cross positive/negative sign-extension boundaries with both large and
    # small left values. Results are computed as 64-bit words, not Python's
    # unbounded signed integers. Keep comparisons signed, as µDewy specifies.
    mask = (1 << 64) - 1
    def signed(n):
        n &= mask
        return n if n < (1 << 63) else n - (1 << 64)
    operations = {
        '+': lambda a, b: a + b, '-': lambda a, b: a - b, '*': lambda a, b: a * b,
        'and': lambda a, b: a & b, 'or': lambda a, b: a | b, 'xor': lambda a, b: a ^ b,
        '<<': lambda a, b: a << (b & 63), '>>': lambda a, b: (a & mask) >> (b & 63),
        '=?': lambda a, b: -int(a == b), 'not=?': lambda a, b: -int(a != b),
        '<?': lambda a, b: -int(a < b), '>?': lambda a, b: -int(a > b),
        '<=?': lambda a, b: -int(a <= b), '>=?': lambda a, b: -int(a >= b),
    }
    values = [0, 1, -1, -(1 << 63), (1 << 63) - 1,
              -(1 << 31) - 1, -(1 << 31), (1 << 31) - 1, 1 << 31, 0xffffffff]
    statements = []
    for left in values:
        statements.append(f'n = {left & mask}')
        for right in values:
            for op, evaluate in operations.items():
                result = evaluate(signed(left), signed(right)) & mask
                statements.append(f'if (n {op} {right & mask}) not=? {result} {{return 1}}')
    source = 'let main=():>int=>{\nlet n:int=0\n' + '\n'.join(statements) + '\nreturn 0\n}'
    backend = get_backend('x86_64')
    backend.debug_info = False
    assembly = p0.parse(t1.tokenize(source), source, backend)
    binary = backend.compile_and_link(assembly, 'word-matrix', tmp_path)
    assert subprocess.run([binary], timeout=5).returncode == 0
