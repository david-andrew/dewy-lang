"""Unit scales fold exact numbers while retaining physical dimensions."""
import test_bootstrap_check as source_values

UNITS = 'const s:(1*Time)=1 transmute (1*Time)\nconst m:(1*Length)=1 transmute (1*Length)\n'
CASES = [
    UNITS + 'const ms=s/1000\nms',
    UNITS + 'const minute:(60*Time)=60*s\nconst hour:(3600*Time)=60*minute\nhour',
    UNITS + 'const scale=s/1000\nconst twice=scale+scale\ntwice',
    UNITS + 'const negative:((-1)*Time)=-s\nnegative',
    UNITS + 'const ratio=s/s\nratio',
    UNITS + 'const speed=m/s\nspeed',
    UNITS + 'const same=2*s >? s\nsame',
]
ERRORS = [
    UNITS + 's+m',
    UNITS + 's =? m',
    UNITS + 's+1',
    UNITS + 's/0',
    UNITS + 'const wrong:(2*Time)=s/1000',
]


def test_native_quantity_constants(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path)
