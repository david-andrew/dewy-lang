"""A binding of only temperature literals whose uses disagree about its kind warns, naming
both uses (also in the editor); it stays a point and the difference use reads it as one."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

SOURCE = '''from units import K, °C, °F
reading=(c:int)=>c*°C
let t=reading(25)
let rise=20°C
printl"{t + rise} {rise as °F}"
printl"{rise <? t}"
'''


def warnings_of(compiler, path):  # noqa: F811
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if 'holds only temperature literals' in line]


def test_conflicting_uses_warn_naming_both(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    found = warnings_of(compiler, source)
    assert len(found) == 1, found
    assert ':4:5: warning: `rise` holds only temperature literals' in found[0]
    assert '`t + rise` (line 5) needs a difference, `rise <? t` (line 6) a point' in found[0]
    assert 'It stays a point' in found[0]
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.stdout.split() == ['45°C', '68°F', 'true'], run.stdout + run.stderr


def test_agreeing_uses_are_quiet(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE.replace('printl"{rise <? t}"', 'printl"{t - rise}"'))
    assert warnings_of(compiler, source) == []
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.stdout.split() == ['45°C', '36°F', '5°C'], run.stdout + run.stderr


def test_editor_shows_the_warning(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), SOURCE, 1)
        warnings = [d for d in diagnostics if d['severity'] == 2 and 'holds only temperature literals' in d['message']]
        assert len(warnings) == 1, diagnostics
        assert warnings[0]['range']['start'] == {'line': 3, 'character': 4}, warnings
    finally:
        client.close()
