"""Dictionary compound stores share lookup proofs and capture their key."""
import test_bootstrap_check as source_values
from test_bootstrap_bigint_operators import PREFIX

CASES = [
    "let calls:int64=0\nlet next=():>'a'=>{calls+=1 return 'a'}\nlet d:totaldict<'a' int64>=['a' -> 40]\nd[next()]+=2; d['a']",
    "let read=(d:totaldict<'a' int64>):>int64=>{let key=():>'a'=>'a' return d[key()]}",
    "let d=['a' -> 40]\nd['a']+=2; d['a']",
    "let d:dict<string int64>=['a' -> 40]\nlet key:string='a'\nif key in? d {d[key]+=2; d[key]}",
    "let box=[entries=['a' -> 40]]\nbox.entries['a']+=2; box.entries['a']",
    "let d=['a' -> 40]\nd['a'] += {d.pop('a'); 2}; d['a']",
    PREFIX + "let combine=(x:BigInt):>BigInt=>{let d:dict<string BigInt>=['a' -> x] d['a']+=x return d['a']}",
]
ERRORS = [
    "const d=['a' -> 40]\nd['a']+=2",
    "let d:dict<string int64>=['a' -> 40]\nd['b']+=2",
    "let d:dict<string int64>=['a' -> 40]\nlet key:string='a'\nif key in? d {d[key]+={key='missing'; 2}; d[key]}",
]


def test_native_dictionary_compound_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
