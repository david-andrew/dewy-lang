"""Program startup installs the same universe, prelude, game entry points and runtime demands."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_startup_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    # The read at top level needs the element type inferred from the function's push.
    pusher = tmp_path / 'pusher.jo'
    pusher.write_text('xs = []\nfill = (): xs.push(42)\nfill()\nprint(xs[0])\n')
    programs = (pusher, 'tests/cases/ffi/libc_calls.dewy', 'tests/cases/target/build_record.dewy',
                'examples/dunes.dewy', 'tests/cases/ffi/extern_local.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_startup',), programs,
                             flags=((), ('--release',)))
    assert all(r[2] == 0 for r in results[:-2])
    assert all(r[2] != 0 for r in results[-2:])
