"""Check mark growth and copy-on-write snapshots against the expected output."""
from tests.driver_cache import build_driver
from tests.leaf_driver import LeafDriver
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


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
    name = 'checker_node_marks.dewy'
    modules = {name: (ROOT / 'compiler' / name).read_text(), 'driver.jo': f"use '{name}'\n" + driver}
    probe = LeafDriver(build_driver(compiler, modules, False))
    assert probe.compare() == b'true:false:false\n64:true:false\n192:true:false:true:true\n'
