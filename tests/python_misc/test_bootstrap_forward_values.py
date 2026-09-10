"""Known function signatures permit bodies to refer to later value declarations."""
import test_bootstrap_check as source_values

CASES = [
    'let read=(value:int64=1):>int64=>ANSWER+value\nconst ANSWER=41\nread()',
    'let answer:int64=42\nlet read=(value:int64=answer):>int64=>value\nread()',
    'let read=():>int64=>ANSWER\nconst ANSWER:int64=42\nread()',
    'let read=():>int64=>ANSWER\nconst ANSWER=42\nread()',
    'let read=():>int64=>answer\nlet answer:int64=42\nread()',
    'let read=(name:string):>bool=>name in? WORDS\nconst WORDS:set<string>=set["x"]\nread("x")',
    'let answer:int64=1\nlet outer=():>int64=>{let read=():>int64=>answer\nlet answer:int64=42\nreturn read()}\nouter()',
    'let read=():>int64=>answer\nanswer:int64=42\nread()',
    # Source checking admits these bindings; initialization rejects the eager
    # call before the later declaration (covered by the graph test).
    'let read=():>int64=>answer\nread()\nlet answer:int64=42',
]
ERRORS = [
    'let read=(value:int64=answer):>int64=>value\nlet answer:int64=42',
    'let answer:int64=1\nlet read=(value:int64=answer):>int64=>LATER\nconst LATER=42',
    'let read=():>int64=>MISSING',
    'let read=():>int64=>ANSWER\nconst ANSWER:string="wrong"',
]


def test_native_function_bodies_see_later_values(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
