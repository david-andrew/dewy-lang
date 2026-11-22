"""Mark growth and copy-on-write snapshots agree for the live leaf and its twin."""
from tests import leaf_oracle
from tests.driver_cache import build_driver
from tests.leaf_driver import DriverPair
from tests.support import ROOT, compiler  # noqa: F401


def test_checker_node_marks_twins(compiler):
    driver = """main = ():
    marks: bool[]
    node_mark(marks, 0)
    print("{node_marked(marks, 0)}:{node_marked(marks, 63)}:{node_marked(marks, 64)}")
    snapshot = marks
    node_mark(marks, 63)
    node_mark(marks, 64)
    print("{snapshot.len()}:{snapshot[0]}:{snapshot[63]}")
    print("{marks.len()}:{marks[0]}:{marks[62]}:{marks[63]}:{marks[64]}")
"""
    binaries = []
    for suffix in ('dewy', 'jo') if leaf_oracle.builds_twin() else ('dewy',):
        name = f'checker_node_marks.{suffix}'
        modules = {name: (ROOT / 'compiler' / name).read_text(),
                   'driver.jo': f"use '{name}'\n" + driver}
        binaries.append(build_driver(compiler, modules, False))
    assert DriverPair(tuple(binaries)).compare() == b'true:false:false\n64:true:false\n192:true:false:true:true\n'
