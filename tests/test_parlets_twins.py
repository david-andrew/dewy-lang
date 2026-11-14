"""`let` items of parallel blocks running as tasks match their frozen leaves: dewy_reader
against its seed, and the task, race and deadlock leaves."""
import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
from tools.compiler import parser_diff

CASES = sorted(str(p.relative_to(parser_diff.ROOT))
               for p in (parser_diff.ROOT / 'tests/cases/parallel_lets').glob('*.dewy'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_parlets_dewy_reader(compiler, tmp_path, release):
    pair = parser_diff.build_pair(compiler, tmp_path, release)
    failures = parser_diff.compare(pair, [parser_diff.ROOT / p for p in CASES], tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_parlets_leaves(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('checks_type_hooks', 'concurrency_tasks', 'lower_races', 'deadlock_walk',
                    'deadlock_channel_walk', 'deadlock_certificates'),
                   CASES, flags=((), ('--release',)))
