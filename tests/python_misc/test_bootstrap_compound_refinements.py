"""Compound operands do not inherit the destination's store refinements."""
import test_bootstrap_check as source_values

CASES = [
    'let x:int64=84\nx >>= 1\nx+0',
    'let x:int64=21\nx <<= 1\nx+0',
    'let box:[x:int64]=[x=84]\nbox.x >>= 1\nbox.x',
    'let x:int8=84\nx >>= 1\nx+0',
    # Native reads retain the proved store contract; hosted reads erase its
    # anonymous predicates. Compare an arithmetic base-type result, while
    # exercising small operands that need not meet the destination's bound.
    # A no-op `as int64` may retain the already-proved source refinement.
    'let x:int64<n=>n>=?5>=5\nx+=1\nx+0',
    'let x:int64<n=>n>=?5>=6\nx+=1\nx-=1\nx+0',
    'let box:[x:int64<n=>n>=?5>]=[x=5]\nbox.x+=1\nbox.x',
    "let d:dict<string int64<n=>n>=?5>>=['x'->5]\nd['x']+=1\nd['x']",
    'let f=(names:array<int64>):>int64=>{let at:addr<i=>i<=?names.length>=0 loop at <? names.length {at+=1} return at}',
]


def test_native_compound_store_refinements(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [
        'let x:int64=84\nlet count:int64=1\nx >>= count',
        'let x:int64=21\nlet count:int64=1\nx <<= count',
    ])
    source_values.test_native_source_values(tmp_path, function_types=True)
