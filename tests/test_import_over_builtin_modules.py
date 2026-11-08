"""A selected import wins over Dewy's built-in reading of its name (find, rfind, chars, index_of,
to_int, sleep, sin) in the module that imports it, whoever else imports that module and in
whichever order: a chain, a Dewy cycle, a cycle through a Jo module, an entry naming the module
first or last. A compiler built with checker_call_services' frozen twin (the bootstrap and interim
stages) reads them alike (LANGUAGE.md, "Modules and games")."""
import subprocess

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

FILES = {
    # (a and b import each other; find with two and three arguments, rfind)
    'a.dewy': '''from p"@lib/core/str.jo" import (find rfind)
from p"b.dewy" import (b_one)
a_find=(s:string):>int=>{find(s "x") + b_one() - 1}
a_rfind=(s:string):>int=>{rfind(s "x")}
a_find3=(s:string):>int=>{find(s "x" 6)}
''',
    'b.dewy': '''from p"a.dewy" import (a_find a_rfind a_find3)
b_one=():>int=>{1}
b_all=(s:string):>void=>{printl("{a_find(s)} {a_rfind(s)} {a_find3(s)}")}
''',
    'only_b.dewy': '''from p"b.dewy" import (b_all)
b_all("é漢xyx")
''',
    'a_first.dewy': '''from p"a.dewy" import (a_find)
from p"b.dewy" import (b_all)
printl(a_find("é漢xyx"))
b_all("é漢xyx")
''',
    # (a Dewy module in a cycle with a Jo module that uses it)
    'ja.dewy': '''from p"@lib/core/str.jo" import (find)
from p"jb.jo" import (jb_one)
ja_find=(s:string):>int=>{find(s "x") * jb_one()}
''',
    'jb.jo': '''use 'ja.dewy'
jb_one = () -> int: 1
jb_find = (s: str) -> int: ja_find(s)
''',
    'jo_entry.jo': '''use 'jb.jo'
main = ():
    print(jb_find("é漢xyx"))
''',
    'jo_cycle.dewy': '''from p"jb.jo" import (jb_find)
from p"ja.dewy" import (ja_find)
printl(jb_find("é漢xyx"))
printl(ja_find("é漢xyx"))
''',
    'q.dewy': '''from p"@lib/core/os.jo" import (sleep)
from p"@lib/core/str.jo" import (to_int)
q=():>void=>{
    sleep(0.001)
    printl(to_int("0x10") ?? -1)
}
''',
    'r.dewy': '''from p"@lib/core/array.jo" import (index_of)
from p"@lib/core/str.jo" import (chars)
from p"@lib/core/math.jo" import (sin)
r=():>void=>{
    printl(index_of([1 2 3] 9))
    printl(chars("é漢").length)
    let f:(x:float64:>float64) = @sin
    printl(f(0.0))
}
''',
    'others.dewy': '''from p"r.dewy" import (r)
from p"q.dewy" import (q)
q()
r()
''',
    # (a program's own modules exporting find: a Dewy and a Jo one, splat and selected)
    'uf.dewy': 'find=(s:string sub:string):>int=>{100}\n',
    'uj.jo': 'find = (s: str, sub: str) -> int: 200\n',
    'splat_dewy.dewy': 'import p"uf.dewy"\nprintl(find("é漢xyx" "x"))\n',
    'named_dewy.dewy': 'from p"uf.dewy" import (find)\nprintl(find("é漢xyx" "x"))\n',
    'splat_jo.dewy': 'import p"uj.jo"\nprintl(find("é漢xyx" "x"))\n',
    'named_jo.dewy': 'from p"uj.jo" import (find)\nprintl(find("é漢xyx" "x"))\n',
}

# (str.jo's find and rfind count bytes, its to_int reads hex, index_of misses with -1, chars
# counts code points; Dewy's own would say 2 4 ..., none, 2 graphemes)
EXPECTED = {
    'only_b.dewy': '5 7 7\n',
    'a_first.dewy': '5\n5 7 7\n',
    'jo_entry.jo': '5\n',
    'jo_cycle.dewy': '5\n5\n',
    'others.dewy': '16\n-1\n2\n0.0\n',
    'splat_dewy.dewy': '100\n',
    'named_dewy.dewy': '100\n',
    'splat_jo.dewy': '200\n',
    'named_jo.dewy': '200\n',
}


def write(tmp_path):
    for name, text in FILES.items():
        (tmp_path / name).write_text(text)


def test_import_wins_in_its_module(compiler, tmp_path):  # noqa: F811
    write(tmp_path)
    for entry, expected in EXPECTED.items():
        r = subprocess.run([compiler, entry], cwd=tmp_path, capture_output=True, text=True,
                           timeout=120, check=False)
        assert (r.returncode, r.stdout) == (0, expected), (entry, r.stderr)


def test_import_over_builtin_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    write(tmp_path)
    entries = list(EXPECTED)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_call_services',), entries)
    for i, (entry, result) in enumerate(zip(entries, results)):
        assert result[2] == 0, (entry, result[4])
        r = subprocess.run([tmp_path / 'jo' / f'p{i}-0'], cwd=tmp_path, capture_output=True,
                           text=True, timeout=60, check=False)
        assert (r.returncode, r.stdout) == (0, EXPECTED[entry]), (entry, r.stderr)
