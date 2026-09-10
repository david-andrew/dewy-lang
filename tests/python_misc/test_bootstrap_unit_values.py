"""Names of error mints and contextual record inhabitants enter value HIR."""
import test_bootstrap_check as source_values

CASES = [
    'Missing=type of error\nMissing',
    'Missing=type of error\nlet value=Missing\nvalue',
    'Missing=type of error\nlet find=():>int64|Missing=>Missing\nfind()',
    'Missing=type of error\nChild=type of Missing\nlet value:Missing=Child\nvalue',
    'Empty=type of []\nlet value=Empty\nvalue',
    'Empty=type of []\nconst value=Empty\nvalue',
    'Empty=type of []\nlet make=():>Empty=>Empty\nmake()',
    'Empty=type of []\nlet values:array<Empty>=[Empty Empty]\nvalues.length',
    'Root=$abstract type of []\nEmpty=type of Root\nlet value:Root=Empty\nvalue',
    'Default=type of [x:int64=7 y:int64=x+1]\nlet value=Default\nvalue.y',
    'Default=type of [x:int64=7]\nlet make=():>Default=>Default\nmake().x',
    'Default=type of [x:int64=7]\nDefault as string',
    (source_values.ROOT / 'library/linux/files.dewy').read_text(),
]
ERRORS = [
    'Missing=type of error\nMissing()',
    'Empty=type of []\nlet value:int64=Empty',
    'Root=$abstract type of []\nlet value:Root=Root',
    'Required=type of [x:int64]\nlet value:Required=Required',
]


def test_native_unit_values_and_filesystem_foundation(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
