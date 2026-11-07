"""The interactive prompt's compile, placement, line reading, completion and history agree with
frozen Jo: the same transcripts, messages, exit codes and saved history."""
from tests.selfhost_process_double import compare_repl
from tests.support import compiler  # noqa: F401

TRANSCRIPTS = [
    ('1+2\nlet xs=[20 22]\nlet saved=xs\nxs[0]=99\nsaved[0]+saved[1]\n'
     'Point:type=[x:int64 y:int64]\nlet point=Point[20 22]\npoint.x=40\npoint.x+point.y\n'
     '1/2+1/3\n:type 1/2\n:quit\n'),
    ('let score=20\nread=()=>score\nscore=40\nread()+2\nlet score=99\nread()\nscore\n'
     'identity=<T>(value:T):>T=>value\nidentity(42)\n:type identity\n:quit\n'),
    ('{\n# A comment inside the final expression.\nlet x=20\nx+22\n}\n'
     'f=(x)=>{\nx+2\n}\nf(40)\n[loop i in [0..3) i*2]\n'
     'let text="""first\nan unmatched " inside triple quotes\nlast"""\ntext.length >? 10\n'
     'let raw=r"\\hello"\nraw.length\n:quit\n'),
    ('let xs=[20 22]\n{xs[0]=99 panic("restore values")}\nxs[0]\n'
     'missing_repl_name\nxs[1]\nbroken=()=>missing_repl_name\n'
     'explode=():>int64=>{panic("restore declarations") return 42}\n'
     'let transient_repl=explode()\ntransient_repl\n:help\n:doc printl\n:quit\n'),
    # (completion: tab after a prefix; backspace)
    'let total_score=40\ntotal_s\t+2\nlet y=13\x7f2\ny\n:quit\n',
]


def test_repl_matches_twin(compiler, tmp_path, monkeypatch):
    runs = compare_repl(compiler, tmp_path, monkeypatch, ('repl_ops',), TRANSCRIPTS)
    assert all(code == 0 for code, *_ in runs), runs
    assert '42' in runs[1][1] and 'restore values' in runs[3][2] and runs[4][1].split() == ['42', '12'], runs
