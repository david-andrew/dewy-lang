"""The watch's link map, patches, global (re)initialization and record migration agree with frozen
Jo: the same session transcripts, patch sizes, exit codes and files."""
from tests.selfhost_process_double import compare_watch
from tests.support import compiler  # noqa: F401

GAME = '''from p"helper.dewy" import label
State:type=[count:int64]
let state=State[0]
let values:array<int64>=[20 22]
let shown=""
pick=()=>values[1]
update=(dt:float64):>void=>{
    state.count+=1
    let line="label={label()} value={pick()}"
    if line not=? shown {
        printl(line)
        shown=line
    }
    sleep(5ms);
}
draw=():>void=>clear(BLACK)
$runtime_checks
'''


def test_watch_game_matches_twin(compiler, tmp_path, monkeypatch):
    grown = (GAME.replace('count:int64]', 'count:int64 health:int64=100]')
             .replace('value={pick()}', 'value={pick()} health={state.health}'))
    steps = [
        ('expect', 'label=one value=22'),
        ('save', 'helper.dewy', 'label=()=>"two"'),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'label=two value=22'),
        ('save', 'helper.dewy', 'label=()=>missing'),
        ('expect', 'keeps running the last version'),
        ('save', 'helper.dewy', 'label=()=>"three"'),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'label=three value=22'),
        # (a record's layout changes: its live value migrates, the new field gets its default)
        ('save', 'game.dewy', grown),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'label=three value=22 health=100'),
        # (a new global is initialized; a changed initializer runs again)
        ('save', 'game.dewy', grown.replace('let shown=""', 'let shown=""\nlet bonus=7')
         .replace('health={state.health}', 'health={state.health} bonus={bonus}')),
        ('expect', r'reloaded in \d+ ms:'), ('expect', 'bonus=7'),
    ]
    out, err, code, _ = compare_watch(compiler, tmp_path, monkeypatch, ('watch_ops',),
                                      {'game.dewy': GAME, 'helper.dewy': 'label=()=>"one"'}, steps, game=True)
    assert any('sending a patch' in line for line in err), err


def test_watch_program_matches_twin(compiler, tmp_path, monkeypatch):
    steps = [
        ('expect', 'first version'),
        ('save', 'main.dewy', 'main=():>void=>printl"second version"'),
        ('expect', 'second version'),
        ('save', 'main.dewy', 'main=():>void=>printl missing'),
        ('expect', 'waiting for changes'),
        ('save', 'main.dewy', 'main=():>void=>printl"third version"'),
        ('expect', 'third version'), ('expect', 'waiting for changes'),
        ('key', 'r\n'), ('expect', 'third version'),
    ]
    compare_watch(compiler, tmp_path, monkeypatch, ('watch_ops',),
                  {'main.dewy': 'main=():>void=>printl"first version"'}, steps)
