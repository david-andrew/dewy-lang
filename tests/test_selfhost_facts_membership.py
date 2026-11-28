"""facts_membership: `h in? c` atoms, `<(in? c)>` contracts and their diagnostics."""
import subprocess

from tests.support import compiler  # noqa: F401

STORE = '''Store:type=[xs:array<int64> live:array<bool>]
Slot:type=[i:int64]
contains=(s:Store h:Slot):>bool=>h.i >=? 0 and h.i <? s.live.length and h.i <? s.xs.length and s.live[h.i]
get=(s:Store h:Slot<(in? s)>):>int64=>s.xs[h.i]
'''


def run(compiler, tmp_path, body, mode='run'):
    path = tmp_path / 'membership.dewy'
    path.write_text(STORE + body)
    return subprocess.run([compiler, mode, path], capture_output=True, text=True, timeout=60)


def test_facts_membership_guard_and_entry(compiler, tmp_path):  # noqa: F811
    ran = run(compiler, tmp_path, 'main=():>void=>{\n    let s=Store[[4 5] [true false]]\n'
              '    let h=Slot[0]\n    if h in? s {printl(get(s h))}\n}\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '4\n'


def test_facts_membership_unproven_names_both(compiler, tmp_path):  # noqa: F811
    checked = run(compiler, tmp_path, 'main=():>void=>{\n    let s=Store[[4 5] [true false]]\n'
                  '    let h=Slot[1]\n    printl(get(s h))\n}\n', 'check')
    assert checked.returncode == 1, checked.stderr
    assert 'cannot prove `h` is in `s`' in checked.stderr
    assert '`if h in? s`' in checked.stderr


def test_facts_membership_pool_refuted(compiler, tmp_path):  # noqa: F811
    checked = run(compiler, tmp_path, 'Box:type=[h:Handle]\n'
                  'contains=(p:Pool<int64> b:Box):>bool=>b.h in? p\n'
                  'read=(p:Pool<int64> b:Box<(in? p)>):>int64=>p[b.h]\n'
                  'main=():>void=>{\n    let p:Pool<int64>=Pool<int64>[]\n    let b=Box[p.add(3)]\n'
                  '    p.remove(b.h);\n    printl(read(p b))\n}\n', 'check')
    assert checked.returncode == 1, checked.stderr
    assert '`b` is no longer in `p`' in checked.stderr
