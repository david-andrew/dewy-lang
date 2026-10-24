"""The language server drops errors that only follow from a body it left out, by their marker, and
keeps real errors whatever their words."""
import pytest

from tests.test_core_editor_features import Client, compiler_path

LEFT_OUT = '''mk=(n:int64)=>{
    n.foo()
    n
}
main=()=>{
    printl(mk(1) + 1)
    printl(mk(2)[0])
    loop x in mk(3) {printl(x)}
    printl(-mk(4))
    let f=mk(5)
    printl(f(1))
}
'''

# (the second error mentions `never`, and follows from nothing)
NEVER_WORDS = '''first=():>int64=>{
    return missing
}
fail=(msg:string):>never=>{
    printl(msg)
}
main=()=>{
    fail("x")
}
'''


def errors(tmp_path, name, text):
    source = tmp_path / name
    source.write_text(text)
    client = Client(compiler_path(), tmp_path)
    try:
        found = client.set_text(source.as_uri(), text, 1)
    finally:
        client.close()
    return [(d['range']['start']['line'], d['message']) for d in found if d['severity'] == 1]


@pytest.mark.core_quick
def test_errors_following_a_left_out_body_are_dropped(tmp_path):
    found = errors(tmp_path, 'left_out.dewy', LEFT_OUT)
    assert [line for line, _ in found] == [1], found
    assert 'foo' in found[0][1]


@pytest.mark.core_quick
def test_a_real_error_mentioning_never_is_kept(tmp_path):
    found = errors(tmp_path, 'never_words.dewy', NEVER_WORDS)
    assert [line for line, _ in found] == [1, 3], found
    assert 'giving `never` must not finish' in found[1][1]
