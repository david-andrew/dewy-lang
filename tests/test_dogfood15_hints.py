"""Diagnostics met while writing ordinary programs (dogfood round 15)."""
import subprocess

from tests.support import compiler  # noqa: F401


def check(compiler, tmp_path, source):
    path = tmp_path / 'hint.dewy'
    path.write_text(source)
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    return checked.stdout + checked.stderr


def test_helper_named_draw_says_it_makes_a_game(compiler, tmp_path):
    text = check(compiler, tmp_path, 'draw = (board:array<int>):>void => printl(board)\nmain = () => draw([1 2])\n')
    assert 'the game calls draw with nothing' in text
    assert 'a program with a top-level `draw` is a game' in text and '`draw_board`' in text


def test_helper_named_update_says_it_makes_a_game(compiler, tmp_path):
    text = check(compiler, tmp_path, 'update = (n:int):>int => n+1\nmain = () => printl(update(1))\n')
    assert 'a program with a top-level `update` is a game' in text


def test_quantity_floor_division_names_the_count(compiler, tmp_path):
    text = check(compiler, tmp_path, 'main = () => {\n    let t:int * Time = 125s\n    printl(t // minute)\n}\n')
    assert 'not defined for physical quantities' in text
    assert '`(t/s) // 60`' in text


def test_shape_contract_names_its_parameter_and_relation(compiler, tmp_path):
    source = '''step = (p:array<float64 length=[4 4]>):>array<float64 length=[4 4]> => p
show = (q:array<float64 length=[4 4]>):>void => printl(q[0 0])
main = () => {
    let plate = zeros(4 4)
    let i = 0
    loop i <? 3 {
        plate = step(plate)
        if i =? 1 plate = zeros(4 5)
        i += 1
    }
    show(plate)
}
'''
    text = check(compiler, tmp_path, source)
    assert 'plate.data.length matches its shape' in text
    assert '(data matches shape)' not in text
    assert ':1:9: note: the contract is declared here' in text
    assert ':2:' not in text.split('the contract is declared here')[0].splitlines()[-1]
