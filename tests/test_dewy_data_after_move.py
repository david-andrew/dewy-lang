"""Sloppy: a record given an array variable, then `data()` of that variable in a later argument,
is an error: the pointer would point into the variable's own copy, not the record's."""
import subprocess

from tests.support import compiler  # noqa: F401

HEADER = '''struct State[T]:
    word: int
    value: T

struct Lock[T]:
    cell: State[T][]
    p: *State[T]

'''
MOVED = HEADER + '''make[T] = (v: T) -> Lock[T]:
    cell: State[T][] = [State[T](0, v)]
    Lock[T](cell, data(cell))

main = ():
    print(make(5).p.value)
'''
TAKEN_FIRST = HEADER + '''make[T] = (v: T) -> Lock[T]:
    cell: State[T][] = [State[T](0, v)]
    p = data(cell)
    Lock[T](cell, p)

main = ():
    l = make(5)
    print(l.p.value)
    print(l.p == data(l.cell))
'''


def test_data_after_move_is_rejected(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'moved.jo'
    source.write_text(MOVED)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode != 0
    assert "data(cell) reads 'cell' after it was moved into the Lock" in checked.stderr, checked.stderr
    assert ':11:23:' in checked.stderr, checked.stderr


def test_data_taken_first_shares_the_array(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'first.jo'
    source.write_text(TAKEN_FIRST)
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.split() == ['5', 'true'], run.stdout
