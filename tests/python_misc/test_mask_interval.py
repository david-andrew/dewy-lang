"""A bitwise `and` with a non-negative operand bounds its result: the mask's
own range proves an index, in both compilers (the masked hexadecimal digit
of dewy/audits/2026-10-03)."""
from test_bootstrap_structural_text import build_program_driver, check_structural_text

CASES = [
    # The mask on either side, and a mask narrower than the table.
    '''digit=(h:uint64):>string=>{let digits='0123456789abcdef' let i:uint64=h and 15 return digits[i]}
first=(h:uint64):>string=>{let digits='0123456789abcdef' let i:uint64=7 and h return digits[i]}
main=():>int64=>{
    let high:uint64=255
    let low:uint64=16
    return if digit(high) =? 'f' and digit(low) =? '0' and first(high) =? '7' 42 else 1
}''',
    # A signed value keeps only the mask's bits, whatever its sign.
    '''pick=(x:int64):>string=>{let digits='0123456789abcdef' let i=x and 15 return digits[i]}
main=():>int64=>if pick(-1) =? 'f' and pick(-16) =? '0' 42 else 1''',
]

ERRORS = [
    # A mask wider than the table proves nothing about the index.
    "digit=(h:uint64):>string=>{let digits='0123456789abcdef' let i:uint64=h and 31 return digits[i]}\nmain=():>int64=>42",
    # A negative mask clears no high bit.
    "pick=(x:int64):>string=>{let digits='0123456789abcdef' let i=x and (-16) return digits[i]}\nmain=():>int64=>42",
]


def test_mask_interval(tmp_path):
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
