"""Common-field union lowering preserves places, temporaries and rejection paths."""
import subprocess
from tests.selfhost_build_double import compare_builds
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

SOURCE = r'''struct Left:
    value: int
struct Right:
    value: int
pick = (flag: bool) -> Left | Right:
    if flag: Left(7)
    else: Right(9)
main = ():
    chosen = pick(true)
    print(chosen.value)
    print(pick(false).value)
'''


def test_union_fields_program_matches_twin(compiler, tmp_path, monkeypatch):
    source = tmp_path / 'union.jo'
    source.write_text(SOURCE)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('union_fields',), [source])
    assert results[0][2] == 0, results[0][:5]
    for label in ('dewy', 'jo'):
        result = subprocess.run([tmp_path / label / 'p0-0'], capture_output=True, timeout=30)
        assert result.returncode == 0 and result.stderr == b''
        assert result.stdout == b'7\n9\n'

DRIVER = r'''use 'main.jo'
use 'union_fields.dewy'
use 'expr.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'checker_types.dewy'
use 'util.jo'
record = (name: str, ft: int) -> int:
    si = structs.len(); t = types.len()
    structs.push(StructInfo(name=name, resolved=true, fields=i32(fields.len()), type=i32(t)))
    types.push(TypeInfo(kind=.struct_, st=i32(si)))
    if ft != 0:
        fields.push(Field(name=i32(intern("value")), type=i32(ft)))
        structs[si].nfields = 1
    t
union = (ms: int[]) -> int:
    si = structs.len(); t = types.len()
    structs.push(StructInfo(union_=true, targs=i32(type_args.len()), ntargs=i32(ms.len())))
    loop m in ms: type_args.push(i32(m))
    types.push(TypeInfo(kind=.enum_, st=i32(si)))
    t
count = (n: int, kind: NK) -> int:
    if n == 0: return 0
    out = if nodes[n].kind == kind: 1 else: 0
    out += count(int(nodes[n].a), kind) + count(int(nodes[n].b), kind) + count(int(nodes[n].c), kind)
    loop k in kids(n): out += count(k, kind)
    out
show = (u: int, place: bool):
    nodes = [Node()]; lists = []; bc_count = 0; union_field_sources = {}
    a = mk(.call, 7)
    if place: nodes[a].kind = .ident; nodes[a].name = i32(intern("chosen"))
    n = mk(.field, 7); nodes[n].a = i32(a)
    result = union_field(n, u, intern("value"))
    print("result:{result == n}:block:{nodes[n].kind == .block}:fields:{count(n, .field)}:tests:{count(n, .istype)}:temps:{count(n, .vardecl)}:calls:{count(n, .call)}:mapped:{union_field_sources.has(n)}:counter:{bc_count}")
main = ():
    init_types()
    l = record("Left", T_INT); r = record("Right", T_INT); third = record("Third", T_INT)
    show(union([l, r]), true)
    show(union([l, r, third]), false)
    show(union([l, T_INT]), true)
    show(union([l, record("Missing", 0)]), true)
    show(union([l, record("Different", T_STR)]), true)
'''


def test_union_fields_direct_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('union_fields',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    lines = outputs[0].stdout.splitlines()
    assert b'fields:2:tests:1:temps:0:calls:0:mapped:true:counter:1' in lines[0]
    assert b'fields:3:tests:2:temps:1:calls:1:mapped:true:counter:1' in lines[1]
    assert all(b'result:false:block:false' in line and b'mapped:false:counter:0' in line for line in lines[2:])
