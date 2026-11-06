"""The library declaration index reads every unit, name and flag as frozen Jo does."""
import re

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

STATE = re.sub(r"(?m)^(use '[^']*'|#.*)\n", '', (ROOT / 'compiler/scan.jo').read_text())

EDGES = r'''# a comment first
    indented first
# two
# comments

plain = 1
typed: int = 2
const LIMIT = 3
struct Point:
    x: int
enum Color: red, green
extern puts(s: *u8) -> int
type Alias = int
type Generic[T] = T[]
type notype
generic[T] = (x: T) -> T: x
a, b = pair()
a, b,
x == 1
print("statement")
([]=)[K, V] = (d: mut {K: V}, k: K, v: V): 0
(unclosed = 3
) closing
] closing
} closing
@nominal
struct Nominal:
    y: int
@export @nominal fun_attr = 1
@export
exported = (): 0
@other("x") attr_value = 2
@open(unclosed
after_open = 3
use 'module.jo'
from x import y
import z
use = 1
from = 2
import = 3
text = "a {b + "nested {c} " + 'q'} d" # comment "not a string"
raw = r"\" # after a raw quote
rname = "x"
triple = """a "quoted" line
second {{ line
"""
when TARGET == "windows":
    inside_a = 1
    inside_b, inside_c = 2
    when TARGET == "x":
        nested = 1
        print("nested statement")
    else:
        nested_else = 2
            deep = 3
    @nominal
    struct InWhen:
        z: int
    # comment in when

	tabbed = 1
else when TARGET == "y":
    other = r"\"
    spanning = "two
lines"
else when TARGET == "z":
  shallow = 1
    deeper = 2
  shallow2 = 3
else:
    last = 3
after_when = 1
when A:
        eight = 1
            nine = 2
        ten = 3
else:
  two = 1
  three = 2
done = 1
open_string = "never ends
'''

DRIVER = r'''
use 'scan.jo'
show = (src: str):
    r = scan_source(src)
    print("{r.0} {r.1}")
    loop u in [r.0..r.1):
        names: str[]
        loop k in [su_name0[u]..su_name0[u + 1]): names.push(src[su_name_at[k]..su_name_at[k] + su_name_len[k]))
        print("{su_start[u]} {su_end[u]} {su_flags[u]} {names}")
main = ():
    a = args()
    loop i in [1..a.len()):
        print(a[i])
        show(read_file(a[i]) ?? "")
    loop src in ["", "\n", "#", "x", "x = 1", "\tx = 1\n", "when A:\n", "when A:\n    b = 1", "else\n", "@", "@a", "a.b = 1\n", "1 = 2\n", "é = 1\n", "\"", "x = '", "x = \"\\", "x = r\"\\\"\ny = 1\n", "t", "s", "e", "c", "type", "e\n", "en", "ex"]:
        show(src)
    print("scan ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_scan_index_twins(compiler, tmp_path, release):  # noqa: F811
    edges = tmp_path / 'edges.jo'
    edges.write_text(EDGES)
    # (the largest library files, and every odd shape in one more)
    library = sorted((ROOT / 'lib').rglob('*.jo'), key=lambda p: -p.stat().st_size)[:8]
    output = compare_narrow(compiler, tmp_path, release, ('scan_index',), DRIVER, doubles={'scan.jo': STATE, 'services.jo': ''}, services=('util',),
                            invocations=[((str(edges), *map(str, library)), 0)])
    assert output.endswith(b'scan ok\n')
    for name in (b'"shallow2"', b'"Nominal"', b'"inside_c"', b'"nested_else"', b'"InWhen"', b'"Generic"', b'"[]="', b'"exported"'):
        assert name in output, name
