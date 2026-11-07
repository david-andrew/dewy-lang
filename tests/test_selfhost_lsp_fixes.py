"""Quick fixes, workspace symbols and the message reader agree with frozen Jo over one session."""
from tests.selfhost_lsp_double import leaf_compilers, session
from tests.support import ROOT, compiler  # noqa: F401

FIXES = '''step=(dt:float64):>float64=>dt
main=()=>{
    let total=0
    let ratio=1.5
    let xs=[1 2 3]
    loop x in xs {x+=1}
    let s="abc"
    if s.startswith("a") && !False {printl(s)}
    let n:int64=2.0
    let g=step
    printl("{totl} {ratio} {n} {True} {xs.lenght()}")
    let r=[1 2; 3 4]
    loop i in [0..3) {ratio=ratio*2.0}
    let p=f.read_text()
}
'''

# (fixes that ask the checker where a name is declared: a program that checks)
VALID = '''main=()=>{
    let ratio=1.5
    let xs=[1.0 2.0 3.0]
    loop x in xs {x+=1.0}
    loop i in [0..3) {ratio=ratio*2.0}
    printl("{ratio} {xs[0]}")
}
'''

IMPL = '''f = (a: int) -> int:
    loop i in [0..3):
        i += 1
    a += 1
    a
'''


def at(text, needle, nth=0):
    """The LSP position of the nth occurrence of needle."""
    k = -1
    for _ in range(nth + 1):
        k = text.index(needle, k + 1)
    line = text.count('\n', 0, k)
    return {'line': line, 'character': k - (text.rfind('\n', 0, k) + 1)}


def diag(text, needle, message, nth=0):
    start = at(text, needle, nth)
    return {'range': {'start': start, 'end': start}, 'message': message, 'severity': 1}


def test_lsp_fixes_session(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'fixes.dewy').write_text(FIXES)
    (root / 'impl.jo').write_text(IMPL)
    (root / 'valid.dewy').write_text(VALID)
    fixes, impl, valid = ((root / name).as_uri() for name in ('fixes.dewy', 'impl.jo', 'valid.dewy'))
    dewy_diags = [
        diag(FIXES, 'totl', "unknown name 'totl' (did you mean 'total'?)"),
        diag(FIXES, 'True', "unknown name 'True' (use `true`)"),
        diag(FIXES, '&&', 'use `and` for logical and'),
        diag(FIXES, '!', 'use `not` instead of `!`'),
        diag(FIXES, '2;', 'this `;` is attached to the value before it'),
        diag(FIXES, 's.startswith', "no member 'startswith' on string: write `s.starts_with(...)`"),
        diag(FIXES, 'xs.lenght', "no member 'lenght': `xs.length()` counts the elements"),
        diag(FIXES, 'step\n', 'write `@step` for the function itself'),
        diag(FIXES, 'f.read_text', 'this path is not proven to stay inside its base: validate it, '
                                   '`root.confine(f) or_throw`'),
        diag(FIXES, '2.0', 'expected i64, found f64'),
        diag(FIXES, 's)}', 'the value expects f64, found i64 here'),
        diag(FIXES, 'g=step', 'expected u8, found str'),
    ]
    valid_diags = [
        diag(VALID, 'ratio=ratio', 'this exact value grows each iteration; annotate `float64` (or another '
                                   'explicit representation) to state it'),
        diag(VALID, 'x+=1', "'x' is changed here but never read afterwards: `loop @x` updates the elements"),
        diag(VALID, 'x+=1', "cannot modify loop variable 'x' (write `loop @item` to change the elements)"),
    ]
    impl_diags = [
        diag(IMPL, 'i += 1', "cannot modify loop variable 'i'"),
        diag(IMPL, 'a += 1', "cannot modify parameter 'a'"),
        diag(IMPL, 'loop', 'expected i32, found i64'),
    ]
    whole = {'start': {'line': 0, 'character': 0}, 'end': {'line': 20, 'character': 0}}
    steps = [
        ('text', (fixes, FIXES, 1)),
        ('text', (impl, IMPL, 1)),
        ('text', (valid, VALID, 1)),
        ('textDocument/codeAction', {'textDocument': {'uri': valid}, 'range': whole,
                                     'context': {'diagnostics': valid_diags}}),
        ('textDocument/codeAction', {'textDocument': {'uri': fixes}, 'range': whole,
                                     'context': {'diagnostics': dewy_diags}}),
        ('textDocument/codeAction', {'textDocument': {'uri': impl}, 'range': whole,
                                     'context': {'diagnostics': impl_diags}}),
        ('workspace/symbol', {'query': 'st'}),
        ('workspace/symbol', {'query': 'MAIN'}),
        ('workspace/symbol', {'query': ''}),
        ('text', (fixes, FIXES.replace('totl', 'total'), 2)),
        ('textDocument/codeAction', {'textDocument': {'uri': fixes}, 'range': whole,
                                     'context': {'diagnostics': dewy_diags[:3]}}),
    ]
    dewy, jo = leaf_compilers(compiler, tmp_path, ('lsp_fixes',))
    expected = session(jo, root, steps)
    assert session(dewy, root, steps) == expected
    missing = [title for title in ("Change 'totl' to 'total'", "Change '&&' to 'and'", 'Make it `loop mut`',
                  "Mark 'a' `mut`", 'Write it as 2', 'Validate it', 'Annotate it', 'Update stored elements',
                  'Convert it', '@step', "Change 'startswith'", "Change 'lenght'", 'row break', "Change '!'",
                  "Change 'True'") if title not in expected]
    assert not missing, (missing, expected)
