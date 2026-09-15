"""Integer singleton annotations describe refined words at value boundaries."""
from test_bootstrap_structural_text import build_program_driver, check_structural_text
from test_bootstrap_lowering import ROOT


CASES = [
    # Keep the complete corpus fixture, including mixed tagged unions and
    # exclusion narrowing, alongside isolated contracts and explicit results.
    (ROOT / 'dewy/tests/literal_unions.dewy').read_text().replace('return checks', 'return if checks=?63 42 else 0'),
    'let flip=(s:-1|1):>-1|1=>-s\nlet main=():>int64=>if flip(1)=?-1 and flip(-1)=?1 42 else 0',
    'let main=():>int64=>{let sign:-1|1=1 sign=-sign return if sign=?-1 42 else 0}',
    'let main=():>int64=>{let box=[sign:-1|1=1] box.sign=-box.sign return if box.sign=?-1 42 else 0}',
    'Fn:type=(s:-1|1):>-1|1\nlet flip:Fn=(s:-1|1):>-1|1=>-s\nlet main=():>int64=>if flip(1)=?-1 42 else 0',
    # Bare annotations retain the same binding across later writes.
    'count:uint8=1\ncount=40\nlet main=():>int64=>count+2',
    'let choose=(n:uint8):>bool=>n is? -1|1\nlet main=():>int64=>if choose(1) and not choose(255) 42 else 0',
    'let choose=(n:int64):>bool=>n isnt? -1|1\nlet main=():>int64=>if choose(0) and not choose(-1) and not choose(1) 42 else 0',
    'let calls:int64=0\nlet next=():>int64|none=>{calls+=1 return if calls=?1 none else -1}\nlet main=():>int64=>if next() is? none|-1 and next() is? -1|1 and calls=?2 42 else 0',
    'let calls:int64=0\nlet next=():>int64=>{calls+=1 return calls}\nlet main=():>int64=>if next() is? 0|1 and calls=?1 42 else 0',
    'let calls:int64=0\nlet next=():>uint8=>{calls+=1 return 1}\nlet main=():>int64=>if next() isnt? -1|-2 and calls=?1 42 else 0',
]
ERRORS = [
    'let flip=(s:-1|1):>-1|1=>0',
    'let flip=(s:-1|1):>-1|1=>s\nflip(0)',
    'let sign:-1|1=1\nsign=0',
    'let sign:-1|1=1\nsign+=1',
    'let box=[sign:-1|1=1]\nbox.sign=0',
    'count:uint8=1\ncount=300',
]


def test_native_integer_set_boundaries(tmp_path):
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
