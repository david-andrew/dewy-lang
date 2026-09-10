"""Callable intersection constructs ordered overload values used by math."""
import test_bootstrap_check as source_values

CHOICE = 'let choose=((x:int64):>int64=>x+1) & ((x:string):>string=>x)\n'
MATH = (source_values.ROOT / 'library/math.dewy').read_text()
CASES = [
    CHOICE + 'choose(7)',
    CHOICE + 'choose("text")',
    CHOICE + 'choose(x=7)',
    CHOICE + 'let alias=@choose\nalias("text")',
    CHOICE + 'let all=@choose & ((x:bool):>bool=>x)\nall(true)',
    'let a=(x:int64):>int64=>x\nlet b=(x:string):>string=>x\nlet both=@a & @b\nboth(7)',
    MATH + '\nlet x:int64=7\nmin(x 9)',
    MATH + '\nlet x:uint64=7\nmax(x 9)',
]
ERRORS = [
    CHOICE + 'choose(true)',
    CHOICE + 'choose(7 8)',
    CHOICE + 'choose(missing=7)',
    'let bad=((x:int64):>int64=>x) & 7',
    'let identity=<T>(x:T):>T=>x\nlet alias=@identity\nalias(7)',
    'let choose=(<T>(x:array<T>):>T=>x[0]) & ((x:string):>string=>x)\nchoose([7])',
    'let choose=(<T>(x:array<T>):>T=>x[0]) & ((x:string):>string=>x)\nchoose("text")',
    'let choose=(<T>(x:array<T>):>T=>missing) & ((x:string):>string=>x)\nchoose([7])',
]


def test_native_overload_values_and_integer_math(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
