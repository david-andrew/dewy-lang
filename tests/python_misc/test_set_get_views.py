"""A set-valued `get` with a default is read in place when nothing can change
its dictionary during the read: a loop that keeps the dictionary, a
membership test whose key cannot write, or a local whose lifetime keeps it
(the default is then kept as an owned local). A loop that replaces the entry it
iterates keeps a snapshot of the entries."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

VIEWED = '''$explicit_copies
count=(users:dict<int64 set<int64>> name:int64 probe:int64):>int64=>{
    let total:int64=0
    loop user in users.get(name set[]) {total+=user}
    if probe in? users.get(name set[]) {total+=100}
    let list=users.get(name set[])
    return total+list.length*1000
}
main=():>int64=>{
    let users:dict<int64 set<int64>>=[]
    users[1]=set[2 3]
    let ok=count(users 1 3) =? 2105 and count(users 9 3) =? 0
    return if ok 42 else 1
}
'''
# The loop body replaces the entry it iterates: the loop keeps a snapshot.
REPLACED = '''count=(@users:dict<int64 set<int64>> name:int64):>int64=>{
    let total:int64=0
    loop user in users.get(name set[]) {
        total+=user
        users[name]=set[]
    }
    return total
}
main=():>int64=>{
    let users:dict<int64 set<int64>>=[]
    users[1]=set[2 3]
    let total=count(@users 1)
    return if total =? 5 and users.get(1 set[]).length =? 0 42 else 1
}
'''
# Key/value iteration over a dictionary read from another dictionary keeps a
# snapshot when the loop replaces that entry (hosted once read freed storage).
PAIRS = '''count=(@tables:dict<int64 dict<int64 int64>> name:int64):>int64=>{
    let total:int64=0
    loop [k v] in tables.get(name []) {
        total+=k*10+v
        tables[name]=[]
    }
    return total
}
main=():>int64=>{
    let tables:dict<int64 dict<int64 int64>>=[]
    tables[1]=[1->2 3->4]
    let total=count(@tables 1)
    return if total =? 46 and tables.get(1 []).length =? 0 42 else 1
}
'''
CASES = [VIEWED, REPLACED, PAIRS]
ERRORS = ['$explicit_copies\n' + REPLACED]


@pytest.mark.parametrize('source', CASES)
def test_set_get_views(tmp_path, source):
    execute(tmp_path, 'set-get-view', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_replaced_set_entry_keeps_its_snapshot(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_set_get_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
