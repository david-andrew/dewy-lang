"""Color, member, file name and text call hints agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'float_constants/reject_old_inf',
    'bigint/error_9',
    'game/chart_series',
    'float_constants/reject_old_nan',
    'conversion/string_to_int_hint',
    'library_contracts/physics_polygon_points',
    'c=hsv(200.5 0.8 0.9)\nprintl(c)\n',
    'c=rgb(255 128 0)\nd=rgb(0.5 0.5 0.5 2.5)\nprintl(c)\nprintl(d)\n',
    'print(hello)\n',
]


def test_checks_call_hints_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
