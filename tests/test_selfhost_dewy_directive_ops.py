"""Metatag bundles load once and restore the lexer; settings apply; dropped arms record names."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

STEMS = ('source_types', 'dewy_tokens', 'node_store', 'dewy_parser', 'dewy_directive_ops')

SERVICES = r'''use 'source_types.dewy'
use 'dewy_tokens.dewy'
use 'node_store.dewy'
use 'dewy_parser.dewy'
use 'dewy_directives.jo'
struct DirBundle:
    name: int
    allocation_failure: bool
struct LexerDouble:
    suspect_brace: int
lib_dir = "library"
nodes: Node[] = [Node()]
lists: i32[]
files: SrcFile[] = [SrcFile()]
dc_parser: ParserContext
dn_lexer = LexerDouble(5)
dn_metatags = 0
dn_block_comments: int[]
dw_bigint_import = 0
dir_bundles_loaded = false
dir_bundles: DirBundle[]
oom_files: {int: bool} = {}
sources: {str: str} = {}
payloads: {int: str} = {}
loaded_made: int[]
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
kids2 = (n: int) -> int[]: node_kids2(nodes, lists, n)
isolation_children = (k: NK) -> int:
    if k == .tuple: return 16
    if k == .field: return 1
    if k == .cast: return 2
    if k == .if_: return 7
    -1
fatal = (pos: int, msg: str) -> never:
    print("fatal {pos}: {msg}")
    exit(41)
intern = (text: str) -> int: if text == "bundle": 7 else if text == "failing": 8 else: 9
pos_file = (pos: int) -> int: pos / 100
read_source = (path: str) -> str?:
    print("read {path}")
    sources.get(path)
dn_payload = (token: DewyLexeme) -> str: payloads[token.start]
dw_dir_known = (name: str) -> bool: name != "unknown"
dir_builtin = (name: str) -> bool: name == "builtin"
dir_bundle_index = (name: int) -> int:
    loop i in [0..dir_bundles.len()):
        if dir_bundles[i].name == name: return i
    -1
dir_bundle_resolve = (b: int, chain: mut int[]): print("resolve {b}")
dir_set = (name: int, value: int, start: int, end: int, at: int): print("set {name} {value} {start} {end} {at}")
oom_module = (file: int, pos: int):
    print("oom {file} {pos}")
    oom_files[file] = true
dw_target_dropped_name = (nm: int, pos: int): print("dropped {nm} {pos}")
dewy_fast_file = (file: int) -> int[]:
    print("parse {file} {files[file].path} {files[file].dir} {files[file].src} {files[file].is_dewy}")
    # (what parsing the bundles leaves behind, which the lexed source must not see)
    dc_parser.tokens = []
    dc_parser.file = 99
    dc_parser.reader.dn_lazy_left = true
    dc_parser.reader.dn_in_interpolation = 88
    dn_metatags = 77
    dn_block_comments = [66]
    dn_lexer.suspect_brace = 55
    dw_bigint_import = 44
    loaded_made
'''

DRIVER = r'''
use 'dewy_directives.jo'
meta = (pos: int, text: str) -> DewyLexeme:
    payloads[pos] = text
    DewyLexeme(.metatag, i32(0), pos, 0, false, false)
state = ():
    print("{dw_dir_dollars} {dir_bundles_loaded} {dc_parser.file} {dc_parser.tokens.len()} {dc_parser.reader.dn_lazy_left} {dc_parser.reader.dn_in_interpolation} {dn_metatags} {dn_block_comments} {dn_lexer.suspect_brace} {dw_bigint_import} {dc_parser.source}")
n_ = (k: NK, a: int = 0, b: int = 0, c: int = 0, name: int = 0, pos: int = 0) -> int:
    nodes.push(Node(kind=k, a=i32(a), b=i32(b), c=i32(c), name=i32(name), pos=pos))
    nodes.len() - 1
list = (k: NK, items: int[]) -> int:
    n = n_(k)
    node_set_list(mut nodes, mut lists, n, items)
    n
id = (name: int, pos: int) -> int: n_(.ident, 0, 0, 0, name, pos)
main = ():
    a = args()
    case = if a.len() > 1: a[1] else: ""
    files = [SrcFile(path="main", src="source text"), SrcFile(path="other", src="other text")]
    other = DewyLexeme(.identifier, i32(0), 0, 0, false, false)
    if case == "made":
        sources["library/directives.dewy"] = "bundles"
        loaded_made = [n_(.fn_, 0, 0, 0, 0, 123)]
        dc_parser.file = 1; dn_metatags = 1
        dc_parser.tokens = [meta(1, "unknown")]
        dw_dir_lexed(1)
    if case == "module":
        dir_bundles = [DirBundle(8, true)]
        dw_dir_apply("failing", 1, 300, 1, 2, false)
    if case != "": return
    # No metatags, then known ones: nothing loads.
    dc_parser.tokens = [other]
    dw_dir_lexed(0); state()
    dn_metatags = 2
    dc_parser.tokens = [other, meta(1, "a"), other, meta(2, "b"), meta(3, "unknown")]
    dw_dir_lexed(0); state()
    # An unknown one past the counted metatags, and within them; a missing library file.
    dn_metatags = 3
    dc_parser.tokens = [meta(1, "a"), meta(2, "unknown")]
    dc_parser.file = 1
    dc_parser.source = "lexed"
    dc_parser.reader.dn_in_interpolation = 3
    dn_block_comments = [4]
    dn_lexer.suspect_brace = 6
    dw_bigint_import = 8
    state()
    dw_dir_lexed(1); state()
    print(files.len())
    # Loaded: the file is registered, and everything the bundles' parse changed is restored.
    dir_bundles_loaded = false
    sources["library/directives.dewy"] = "bundles"
    dw_dir_lexed(1); state()
    print(files.len())
    dn_metatags = 1
    dw_dir_lexed(1); state()
    print(files.len())
    dw_dir_load(); state()
    # Names and settings.
    loop name in ["builtin", "realtime", "bundle", "nothing"]: print(dw_dir_name(name))
    dir_bundles = [DirBundle(7, false), DirBundle(8, true)]
    print(dw_dir_name("bundle"))
    dw_dir_apply("plain", 1, 100, 1, 2, false)
    dw_dir_apply("bundle", 1, 100, 1, 2, false)
    dw_dir_apply("bundle", 0, 100, 1, 2, false)
    dw_dir_apply("failing", 0, 100, 1, 2, false)
    dw_dir_apply("failing", 1, 200, 1, 2, true)
    dw_dir_apply("failing", 1, 200, 1, 2, true)
    # Dropped arms: each child slot and mask, lambdas' second lists, bounds.
    dw_target_dropped_node(0); dw_target_dropped_node(nodes.len() + 5); dw_target_dropped_node(-1)
    dw_target_dropped_node(id(1, 10))
    dw_target_dropped_node(n_(.field, id(2, 11), id(3, 12), id(4, 13)))
    dw_target_dropped_node(n_(.cast, id(5, 14), id(6, 15), id(7, 16)))
    dw_target_dropped_node(n_(.if_, id(8, 17), id(9, 18), id(10, 19)))
    dw_target_dropped_node(list(.tuple, [id(11, 20), id(12, 21)]))
    other_kind = list(.call, [id(13, 22)]); nodes[other_kind].a = i32(id(14, 23))
    dw_target_dropped_node(other_kind)
    lam = list(.lambda, [id(15, 24)]); nodes[lam].b = i32(id(16, 25))
    node_set_list2(mut nodes, mut lists, lam, [id(17, 26)])
    dw_target_dropped_node(lam)
    print("directive ops ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_dewy_directive_ops_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = compare_narrow(compiler, tmp_path, release, STEMS, DRIVER,
                             doubles={'services.jo': SERVICES, 'dewy_directives.jo': 'dw_dir_dollars = true\n'},
                             services=('util', 'ast', 'ide', 'check', 'effects', 'directives', 'dewy_nodes', 'dewy_fast', 'dewy_direct', 'isolation', 'oom', 'oom_ops', 'isolation_ops', 'dewy_context'),
                             invocations=[((), 0), (('made',), 41), (('module',), 41)])
    assert outputs[0].endswith(b'directive ops ok\n')
    assert b'lib/directives.dewy defines bundles only' in outputs[1] and b'a module policy' in outputs[2]
