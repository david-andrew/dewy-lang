"""Evaluator ABI, immutable value snapshots, frame growth and nested entry."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DRIVER = '''main = ():
    value = CTValue()
    frame = CTFrame()
    place = CTPlace()
    scalar = CVal()
    print("{size_of(CTValue)} {size_of(CTFrame)} {size_of(CTPlace)} {size_of(CVal)}")
    print("{int(&value.type)-int(&value)} {int(&value.i)-int(&value)} {int(&value.f)-int(&value)} {int(&value.s)-int(&value)} {int(&value.items)-int(&value)}")
    print("{int(&frame.values)-int(&frame)} {int(&frame.refs)-int(&frame)} {int(&frame.signal)-int(&frame)} {int(&frame.result)-int(&frame)} {int(&frame.depth)-int(&frame)}")
    print("{int(&place.frame)-int(&place)} {int(&place.local)-int(&place)} {int(&place.path)-int(&place)}")
    print("{int(&scalar.is_str)-int(&scalar)} {int(&scalar.i)-int(&scalar)} {int(&scalar.s)-int(&scalar)}")
    print("{value.type} {value.i} {value.f} {value.s} {value.items} {frame.values.len()} {frame.refs.len()} {frame.signal} {frame.result} {frame.depth} {place.frame} {place.local} {place.path} {scalar.is_str} {scalar.i} {scalar.s}")
    values = [CTValue(), CTValue(type=7, i=91, s="first", items=[0])]
    frames = [CTFrame(values={3:1}, refs={4:0}, signal=2, result=1, depth=7)]
    places = [CTPlace(frame=0, local=3, path=[0])]
    saved = frames[0]
    old = values[1]
    loop i in [0..200):
        values.push(CTValue(type=i, i=i, items=[1]))
        frames.push(CTFrame(values={3:i}, refs={4:0}))
        places.push(CTPlace(frame=i+1, local=3, path=[0,i]))
    values[1].items[0]=201
    frames[0].values[3]=201
    frames.truncate(1)
    print("{values.len()} {frames.len()} {places.len()} {values[1].items} {old.items}")
    print("{frames[0].values[3]} {saved.values[3]} {frames[0].signal} {frames[0].result} {frames[0].depth} {places[200].path}")
'''
EXPECTED = (
    "40 120 24 24\n"
    "0 8 16 24 32\n"
    "0 48 96 104 112\n"
    "0 8 16\n"
    "0 8 16\n"
    "0 0 0.0  [] 0 0 0 0 0 0 0 [] false 0 \n"
    "202 1 201 [201] [0]\n"
    "201 1 2 1 7 [0, 199]\n"
)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_evaluator_state_twins(compiler, tmp_path, release):  # noqa: F811
    for extension in ('dewy', 'jo'):
        module = f'evaluator_state.{extension}'
        (tmp_path / module).write_text((ROOT / 'compiler' / module).read_text())
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(f"use '{module}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == EXPECTED
