"""Recursive wait certificates, protocols and foreign boundaries match frozen Jo."""
import re

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


def test_deadlock_certificates_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = r'''use 'main.jo'
use 'util.jo'
use 'source_types.dewy'
main = ():
    saved_files = files; saved_lines = src_lines
    first = files.len(); files.push(SrcFile(path="outer.dewy", src="a\nb"))
    second = files.len(); files.push(SrcFile(path="inner.dewy", src="a\nb"))
    assert(nd_where(mkpos(first, 2), mkpos(first, 0)) == "line 2")
    loop path in ["plain", "a/", "/", "a//b", "a/é", "a/\xff.bin"]:
        files[second].path = path
        base = path[rfind(path, "/") + 1..]
        assert(nd_where(mkpos(second, 2), mkpos(first, 0)) == "{base}:2")
    files = saved_files; src_lines = saved_lines
    lower_test_cli()
    print("checked")
'''
    cases = []
    for case in ('no_deadlocks/foreign_block', 'no_deadlocks/function_value',
                 'no_deadlocks/serve_withdrawn', 'no_deadlocks/join_held',
                 'no_deadlocks/poll', 'no_deadlocks/raw_channel',
                 'no_deadlocks/request_withdrawn', 'no_deadlocks/uncertified_callee',
                 'no_deadlocks/pipeline_withdrawn', 'deadlock/recursive_service_held',
                 'no_deadlocks/select', 'no_deadlocks/race_spread', 'no_deadlocks/first_ok',
                 'no_deadlocks/merged_inbox', 'no_deadlocks/within'):
        source = ROOT / 'tests/cases' / (case + '.dewy')
        cases.append((source, 41, source.with_suffix('.err').read_bytes().splitlines()[0]))
    for case in ('no_deadlocks/audited_adapter', 'no_deadlocks/certified_locks',
                 'no_deadlocks/protocol_opted_out', 'protocols/request_reply',
                 'protocols/pipeline_feedback', 'protocols/pipeline_optional',
                 'protocols/protocol_outer_client', 'protocols/protocol_cancel',
                 'deadlock/recursive_service'):
        cases.append((ROOT / 'tests/cases' / (case + '.dewy'), 0, b'checked\n'))
    for source, status, expected in cases:
        modules = modules_for(source, tmp_path / 'unused', 'deadlock_certificates')
        modules.arguments = ('check', str(source))
        modules.runtime_driver = lambda text: text
        modules['util.jo'], count = re.subn(
            r'(?m)^fatal = \([^\n]*\):\n(?:[ \t].*\n|\n)*',
            'fatal = (p: int, msg: str): print(msg); exit(41)\n\n',
            modules['util.jo'], count=1)
        assert count == 1
        result = compare_leaf(compiler, tmp_path, False, driver, status=status,
                              extra_stems=('deadlock_certificates',), jo_doubles=modules)
        assert expected in result, (source, result)
