"""collect_fns, collect_module, collect_in and collect_named (a call's function family by
name: the module's own table, its uses', the Dewy prelude's, the prelude's, the rational's
exact members; a Dewy module's own binding shadowing them, kept while the name's stamp
stands) match frozen Jo, host services and surface hiding included."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_call_queries import DRIVER as QUERIES
from tests.test_selfhost_checker_resolve import compare

DRIVER = QUERIES.split('main = ():')[0] + r'''
cl_ctxs: FnCtx[] = [FnCtx(mod = 0), FnCtx(mod = 1), FnCtx(mod = 2), FnCtx(mod = 3)]
cl_cx = -1
# (modules: 0 Jo, using 1; 1 Dewy; 2 a prelude module; 3 Dewy, the Dewy prelude's)
cl_bits: int[] = [0, 2, 1, 2]
cl_uses: int[][] = [[1], [], [], []]
cl_built = false
cl_prelude_used: bool[]
cl_home_first: int[]
cl_home_mod: int[] = [1, 0]
cl_home_next: int[] = [0, 0]
cl_demanded: bool[]
cl_scanned = false
cl_dp_by_name: int[]
cl_dp_mods: int[] = [3, -1]
cl_found = -1
cl_probed = 4
cl_reach: int[]
cl_exact: bool[]
cl_marks: i32[]
cl_hidden: int[]
cl_demand = (name: int):
    print("demand:{name}")
    loop cl_demanded.len() <= name: cl_demanded.push(false)
    cl_demanded[name] = true
cl_use_home_host = (m: int, name: int) -> int:
    print("use_home:{m}:{name}")
    cl_built = true
    -2
cl_dp_host = (name: int) -> int:
    print("prelude_module:{name}")
    -1
cl_reach_host = (m: int, dm: int): print("reach:{m}:{dm}")
cl_rational_host = (m: int, name: int, out: *(int[])):
    print("rational:{m}:{name}")
    out[0].push(99)
cl_grow = (d: int): cl_marks.resize(d + 4)
cl_named_first: int[]
cl_named_grow = (name: int):
    print("named_grow:{name}")
    cl_named_first.resize(name + 2)
cl_ide = false
cl_ticks: int[]
cl_struct = 1
cl_named: NamedFamily[]
cl_named_decls: int[]
cl_named_hidden: int[]
cl_host = CheckerCollectHost(cl_demand, cl_use_home_host, cl_dp_host, cl_reach_host, cl_rational_host, cl_grow, cl_named_grow)
cl_input = CheckerCollectInput(&cl_ctxs, &cl_cx, &cl_bits, &cl_uses, &cl_built, &cl_prelude_used, &cl_home_first, &cl_home_mod, &cl_home_next, &cl_demanded, &cl_scanned, &cl_dp_by_name, &cl_dp_mods, &cl_found, &cl_probed, &cl_reach, &cl_exact, &cl_marks, &cl_hidden, &cl_host, &cl_ide, &cl_ticks, &cl_struct, &cl_named_first, &cl_named, &cl_named_decls, &cl_named_hidden)
cl_binding = checker_collect_bind(&cl_input)
show = (label: str, out: int[]):
    print("{label}:{out}:{cl_hidden}")
    cl_hidden.clear()
main = ():
    prepare()
    pn = intern_text("_p")
    qn = intern_text("__q")
    prelude_syms.resize(qn + 1); prelude_syms[pn] = 2
    name_first.resize(qn + 1); name_first[qn] = 3
    # (declarations 11-13; sym 3's family goes on to 5 (Dewy only) and 6 (Sloppy only))
    query_syms[1].decl = 11; query_syms[2].decl = 12; query_syms[3].decl = 13
    query_syms.push(Sym(kind = .fns, decl = 15, surface = 1))
    query_syms.push(Sym(kind = .fns, decl = 16, surface = 2))
    query_syms[3].next = 5; query_syms[5].next = 6
    cl_home_first = [0, 0, 1]
    cl_dp_by_name = [0, 1, 2]
    loop round in [0, 1, 2]:
        if round == 1:
            cl_scanned = true
            cl_exact = [false, true]
        if round == 2:
            cl_prelude_used = [true]
            cl_dp_mods[0] = 1
            cl_found = 7
            cl_reach = [0, 1]
        loop c in [-1, 0, 1, 2, 3]:
            cl_cx = c
            loop name in [1, 2, pn, qn]:
                out: int[]
                collect_fns(name, &out)
                show("fns:{round}:{c}:{name}", out)
        cl_cx = 1
        loop m in [-1, 0, 1, 2, 3]:
            loop name in [1, 2, qn]:
                out: int[] = [12]
                collect_module(m, name, &out)
                show("module:{round}:{m}:{name}", out)
        loop hide in [0, 1, 2]:
            out: int[] = [13]
            collect_in(1, qn, hide, &out)
            collect_in(-1, pn, hide, &out)
            show("in:{round}:{hide}", out)
    # collect_named: a Dewy module's own non-method declarations shadow the rest (methods,
    # first parameter `$self...`, stay); kept by name, module and current module per stamp
    self_name = intern_text("$self")
    param = node(.param); nodes[param].name = i32(self_name)
    loop nodes.len() < 120: nodes.push(Node())
    method = node(.fn_, 0, 0, 0, [param])
    query_syms.push(Sym(kind = .fns, decl = i32(method)))
    query_syms[2].next = 7
    loop round in [0, 1, 2]:
        if round == 1: cl_struct = 2
        if round == 2:
            cl_ticks = [0, 0, 5]
            cl_ide = true
        loop c in [0, 1, 3]:
            cl_cx = c
            loop name in [1, 2, qn]:
                loop mod in [-1, 0, 1]:
                    loop again in [0, 1]:
                        out: int[]
                        if again == 1 and mod == 1: out.push(method)
                        if again == 1 and mod == 0: out.push(16)
                        collect_named(name, mod, &out)
                        show("named:{round}:{c}:{name}:{mod}:{again}", out)
    print("families:{cl_named.len()}:{cl_named_decls.len()}:{cl_named_hidden.len()}")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_collect_twins(compiler, tmp_path, release):  # noqa: F811
    out = compare(compiler, tmp_path, release, DRIVER, extra_stems=('checker_call_queries',))
    assert out.decode().endswith('ok\n')
