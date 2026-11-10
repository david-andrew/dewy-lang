"""Batched golden cases never share standard output: a raw write to fd 1 lands in its own case."""
from tests.support import compiler  # noqa: F401 (fixture)
from tools.cases import CASES
from tests.test_core_case_top_level_output import run, write

RAW = ('# modes: native native-release\nif $target.os =? "linux" {\n'
       '    output=(xs:array<uint8>):>void=>{syscall(1 1 xs.data() xs.length);}\n} else {\n'
       '    output=(xs:array<uint8>):>void=>{printl("A")}\n}\nmain=()=>output([65 10])\n')


def test_raw_write_stays_in_its_case(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    # (the streams case writes to both streams, the raw writer follows it in the same batch)
    write(root, 'console/streams',
          '# modes: native native-release\nmain=()=>{\n    printl("one")\n    printl("hidden" file=stderr)\n    printl("auto")\n}\n',
          out='one\nauto\n')
    write(root, 'data/raw', RAW, out='A\n')
    write(root, 'data/after', '# modes: native native-release\nmain=()=>{printl("after")}\n', out='after\n')
    assert run(compiler, root, tmp_path, monkeypatch) == 0


def test_repo_streams_and_syscall_in_one_batch(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    for name in ('console/streams', 'data_readonly/syscall'):
        source = CASES / f'{name}.dewy'
        write(root, name, source.read_text(), out=source.with_suffix('.out').read_text())
    assert run(compiler, root, tmp_path, monkeypatch) == 0

