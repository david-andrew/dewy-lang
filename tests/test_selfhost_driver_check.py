"""driver_check_arguments in driver_check match their frozen twin."""
import os

import pytest

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_driver_cli import run


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_driver_check_twins(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('driver_check',))
    (tmp_path / 'good.dewy').write_text('main=():>void=>printl"checked"\n')
    (tmp_path / 'two-errors.dewy').write_text(
        'first=():>int64=>"one"\nsecond=():>int64=>"two"\n'
        'main=():>void=>{printl(first());printl(second());}\n')
    (tmp_path / 'tests-bad.dewy').write_text(
        'main=():>void=>{}\n$test\nbad=():>void=>{let x:int64="test error";}\n')
    (tmp_path / 'ragged-\udcff.jo').write_text('main = (): print("bytes")\n')

    def compare(arguments, status, env=None):
        results = [run(binary, arguments, tmp_path, env=env) for binary in binaries]
        assert results[0] == results[1] and results[0][0] == status, (arguments, results)
        return results[0]

    for args, status in [
        (['check'], 2), (['check', '--obligations'], 1),
        (['check', 'good.dewy'], 0),
        (['check', '--obligations', 'good.dewy'], 0),
        (['check', 'good.dewy', '--obligations'], 0),
        (['check', '--obligations', 'good.dewy', '--obligations'], 0),
        (['check', 'good.dewy', 'ignored', '--obligations'], 0),
        (['check', 'ragged-\udcff.jo'], 0),
        (['check', 'missing.dewy'], 1), (['check', 'tests-bad.dewy'], 1),
        (['--skip-fns', '', '', 'check', 'good.dewy'], 1),
        (['--eager-bodies', '--skip-fns', '', '', 'check', 'good.dewy'], 1),
        (['--skip-fns', '', '', '--eager-bodies', 'check', 'good.dewy'], 1),
    ]:
        compare(args, status)
    errors = compare(['check', 'two-errors.dewy'], 1)
    assert 'one' in errors[2] and 'two' in errors[2], errors

    # Empty/malformed records, multiple separators, warning keys, decimal
    # fallbacks and non-UTF-8 bytes retain the Jo replay parser's byte semantics.
    for skips, prior in [
        ('w17.2,1:4,ignored,0:bad', '0\x1fheld diagnostic\x1eignored\x1e:\x1fsecond held'),
        ('w\u0301,\udcff:2,:4,,w', 'bad\x1fraw-\udcff\x1fstill in message\x1e\x1fignored'),
        ('0:0,0:0', '0\x1f\x1e0\x1frepeated'),
    ]:
        compare(['--skip-fns', skips, prior, 'check', 'good.dewy'], 1)

    # The retained Jo stop/compile boundary must see the prepared path/modes;
    # profiling stops do not lower, while an empty setting takes the normal path.
    for stop in ('', 'lex', 'parse', 'check', 'unrecognized-stop'):
        env = dict(os.environ, DEWY_STOP=stop)
        for args in (['check', 'good.dewy'], ['check', '--obligations', 'good.dewy']):
            compare(args, 0, env)
