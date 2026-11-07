"""Language-server JSON access, document lookup, replies and lenses agree with frozen Jo over one session."""
from tests.selfhost_lsp_double import leaf_compilers, session
from tests.support import compiler  # noqa: F401

MODEL = '''# A record and its step.
Point:type=[x:float64 y:float64]
fresh=():>Point=>Point[1.0 2.0]
advance=(@p:Point dt:float64):>void=>{
    p.x+=dt
}
'''

GAME = '''from p"model.dewy" import fresh, advance
let world=fresh()
step=(dt:float64):>void=>{
    advance(@world min(dt 0.05))
}
$test
fresh_world=()=>$expect world.x =? 1.0
main=()=>{
    let total=0
    loop i in [0..3) {total+=i}
    # a comment with "text"
    printl("{total} and {world.x}")
}
'''


def test_lsp_ops_session(compiler, tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'model.dewy').write_text(MODEL)
    (root / 'game.dewy').write_text(GAME)
    model, game = (root / 'model.dewy').as_uri(), (root / 'game.dewy').as_uri()

    def at(uri, line, character):
        return {'textDocument': {'uri': uri}, 'position': {'line': line, 'character': character}}
    whole = {'start': {'line': 0, 'character': 0}, 'end': {'line': 12, 'character': 0}}
    steps = [
        ('text', (model, MODEL, 1)),
        ('text', (game, GAME, 1)),
        ('textDocument/hover', at(game, 3, 6)),
        ('textDocument/hover', at(game, 10, 12)),
        ('textDocument/definition', at(game, 3, 6)),
        ('textDocument/references', {**at(model, 3, 1), 'context': {'includeDeclaration': True}}),
        ('textDocument/documentHighlight', at(game, 9, 18)),
        ('textDocument/completion', at(game, 3, 22)),
        ('textDocument/completion', at(game, 10, 25)),
        ('textDocument/signatureHelp', at(game, 3, 21)),
        ('textDocument/signatureHelp', at(game, 3, 30)),
        ('textDocument/inlayHint', {'textDocument': {'uri': game}, 'range': whole}),
        ('textDocument/semanticTokens/full', {'textDocument': {'uri': game}}),
        ('textDocument/documentSymbol', {'textDocument': {'uri': game}}),
        ('textDocument/codeLens', {'textDocument': {'uri': game}}),
        ('textDocument/formatting', {'textDocument': {'uri': model}, 'options': {'tabSize': 4, 'insertSpaces': True}}),
        ('textDocument/codeAction', {'textDocument': {'uri': game}, 'range': whole, 'context': {'diagnostics': []}}),
        ('workspace/symbol', {'query': 'adv'}),
        ('textDocument/prepareRename', at(game, 9, 18)),
        ('textDocument/rename', {**at(game, 9, 18), 'newName': 'sum'}),
        ('text', (model, MODEL.replace('dt:float64', 'dt:float64 extra:int64'), 2)),
        ('textDocument/hover', at(game, 3, 6)),
        ('text', (game, GAME.replace('{total} and', '{missing} and'), 2)),
        ('notify', ('textDocument/didClose', {'textDocument': {'uri': model}})),
        ('textDocument/definition', at(game, 3, 6)),
    ]
    dewy, jo = leaf_compilers(compiler, tmp_path, 'lsp_ops')
    expected = session(jo, root, steps)
    assert session(dewy, root, steps) == expected
    assert '"result": null' not in expected[:200]
