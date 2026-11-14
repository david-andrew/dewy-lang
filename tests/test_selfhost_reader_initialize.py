"""The frontend's sentinel initialization preserves unrelated context state in both twins."""
import pytest
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

FIELDS = ('dc_axis_depth', 'dc_condition_depth', 'dc_empty_id', 'dc_head_depth', 'dc_initial_at',
          'dc_literal_at', 'dc_live_at', 'dc_member_depth', 'dc_spread_depth', 'dc_target_problem',
          'dc_value_start')
SERVICES = ('struct Reader:\n' + ''.join(f'    {field}: int\n' for field in FIELDS) +
            '    extra: int\nstruct Context:\n    reader: Reader\n    file: int\ndc_parser: Context\n')
DRIVER = ('main = ():\n    dc_parser.file = 42; dc_parser.reader.extra = 99\n' +
          ''.join(f'    dc_parser.reader.{field} = {i+1}\n' for i, field in enumerate(FIELDS)) +
          '    assert(dc_reader_initialize() and dc_reader_initialize())\n' +
          ''.join(f'    assert(dc_parser.reader.{field} == -1)\n' for field in FIELDS) +
          '    assert(dc_parser.file == 42 and dc_parser.reader.extra == 99)\n    print("ok")\n')

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_reader_initialize_twins(compiler, tmp_path, release):
    assert compare_narrow(compiler, tmp_path, release, ('reader_initialize',), DRIVER,
                          doubles={'services.jo': SERVICES}, services=('dewy_context',)) == b'ok\n'
