"""warn_if_facts visits, sticky verdicts and warning/reset ownership match frozen Jo."""
import pytest

from tests import selfhost_lsp_double
from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_driver_cli import run
from tests.test_warn_if import SOURCE, MESSAGES, warned

SERVICES = '''use 'checker_tokens.dewy'
use 'refinement_types.dewy'
struct FactState:
    live: bool = true
    visits: int = 0
struct WFFn:
    decl: i32 = 0
    ptypes: int[]
struct WFNode:
    pos: int = 0
nodes: WFNode[]
fns: WFFn[]
fact_speculating = 0
const T_INT = 1
ref_value = (term: RefTerm, self: int, args: int[], base: int, s: mut FactState) -> int:
    s.visits += 1
    print("value {term.kind} {term.value} base {base}")
    if term.kind == 2 or term.kind == 5:
        return if term.value < args.len(): args[term.value] else: 0
    term.value
fact_compare = (s: FactState, op: Tok, a: int, b: int) -> int:
    print("compare {a} {b}")
    if a == b: 1 else: 0
warn = (pos: int, message: str): print("WARN {pos}: {message}")
'''

DRIVER = '''use 'warn_if.jo'
show = (label: str, s: FactState):
    print("STATE {label}: {s.visits} {wi_fact_calls[20]}")
main = ():
    loop i in [0..50): nodes.push(WFNode(i*10))
    fns = [WFFn(), WFFn(decl=11, ptypes=[41]), WFFn(decl=12)]
    w = WarnIf(kind=WI_FACTS, atoms=[RefAtom(.eq, RefTerm(2,0), RefTerm(1,9))], message="first")
    wi_decls[11] = [WarnIf(kind=WI_TYPE), w, WarnIf(kind=WI_PATH)]
    wi_fact_calls[20] = 0
    wi_fact_targs[20] = 1
    s = FactState()
    fact_speculating = 1
    wi_fact_check(20, [9], s)
    show("speculating", s)
    fact_speculating = 0
    s.live = false
    wi_fact_check(20, [9], s)
    show("dead", s)
    s.live = true
    wi_fact_check(30, [9], s)
    show("no callee", s)
    wi_fact_targs[30] = 2
    wi_fact_check(30, [9], s)
    show("no declaration", s)
    wi_fact_check(20, [9], s)
    show("proven", s)
    kept = wi_fact_calls
    wi_fact_check(20, [8], s)
    show("unproven", s)
    print("KEPT {kept[20]}")
    wi_fact_check(20, [9], s)
    show("sticky", s)
    wi_fact_check(20, [], s)
    show("unknown", s)
    # Every atom is visited even after an earlier failure; only a direct
    # parameter on the left chooses its checked parameter type as the base.
    w.atoms = [RefAtom(.eq, RefTerm(2,0,path=[-1]), RefTerm(1,9)), RefAtom(.eq, RefTerm(5,0), RefTerm(1,9)), RefAtom(.eq, RefTerm(2,4), RefTerm(1,9))]
    wi_decls[11] = [w, WarnIf(kind=WI_FACTS, atoms=[], message="second")]
    wi_fact_check(20, [9], s)
    show("all atoms", s)
    wi_fact_calls[21] = 2
    wi_fact_requests = [FactRequest(20,1), FactRequest(21,1)]
    held_calls = wi_fact_calls
    held_requests = wi_fact_requests
    wi_fact_finish()
    print("RESET {wi_fact_calls.len()} {wi_fact_requests.len()} {held_calls[20]} {held_requests.len()} {wi_fact_targs.has(20)} {wi_decls.len()}")
    wi_fact_finish()
    # A registered visit not seen by the walk still warns.
    wi_fact_calls[22] = 0
    wi_fact_targs[22] = 1
    wi_fact_finish()
    print("FINAL {wi_fact_calls.len()} {wi_fact_requests.len()}")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_warn_if_facts_state_matches_twin(compiler, tmp_path, release):
    state = (ROOT / 'compiler/warn_if.jo').read_text()
    state = state[state.index('const WI_TYPE'):state.index('# facts.jo: the call n')]
    output = compare_narrow(
        compiler, tmp_path, release, ('checker_tokens', 'refinement_types', 'warn_if_facts'), DRIVER,
        doubles={'services.jo': SERVICES,
                 'warn_if.jo': "use 'services.jo'\nuse 'refinement_types.dewy'\n" + state},
        services=('ast', 'check', 'facts', 'facts_compare', 'refine', 'types', 'source_warnings'))
    text = output.decode()
    for label in ('speculating', 'dead', 'no callee', 'no declaration'):
        assert f'STATE {label}: 0 0\n' in text
    for line in ('STATE proven: 2 2', 'STATE unproven: 4 1', 'KEPT 2',
                 'STATE sticky: 6 1', 'STATE unknown: 8 1', 'STATE all atoms: 14 1',
                 'RESET 0 0 1 2 true 1', 'FINAL 0 0',
                 'WARN 200: first', 'WARN 200: second', 'WARN 220: first', 'WARN 220: second'):
        assert line + '\n' in text, text
    assert text.count('base 41') == 8, text
    assert text.count('base 1') == 6, text
    assert text.count('compare ') == 5, text


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_warn_if_facts_real_warnings_match_twin(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('warn_if_facts',))
    source = tmp_path / 'warnings.dewy'
    source.write_text('$runtime_checks\n\n' + SOURCE)
    for args in (['check', str(source)], ['build', str(source), '-o', str(tmp_path / 'program')],
                 ['check', '--obligations', str(source)]):
        got, expected = [run(b, args, tmp_path) for b in binaries]
        assert got == expected, (args, got, expected)
        assert got[0] == 0, got
        assert warned(got[2]) == [(14, MESSAGES[0]), (18, MESSAGES[1]), (22, MESSAGES[2])]
    # A strict policy may reject the body's checked arithmetic before the
    # soft-precondition walk finishes; that diagnostic must agree too.
    args = ['--internal-fact-policy=require-static', 'check', str(source)]
    got, expected = [run(b, args, tmp_path) for b in binaries]
    assert got == expected and got[0] in (0, 1), (got, expected)
    catalog = ROOT / 'tests/ladder/121_catalog_warnings/design.dewy'
    assert run(binaries[0], ['check', str(catalog)], tmp_path) == run(binaries[1], ['check', str(catalog)], tmp_path)
