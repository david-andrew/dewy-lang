"""A splat import that shadows a prelude name warns, naming both sources (also in the editor);
selecting the name, or importing the module `as` a name, says which is meant and is quiet."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

HELPERS = '''mean=(xs:array<int64>):>int64=>xs.length
first=(xs:array<int64>):>int64=>7
own=():>int64=>1
'''


def warnings_of(compiler, path):  # noqa: F811
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if 'shadows the prelude' in line]


def test_splat_shadowing_the_prelude_warns(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'helpers.dewy').write_text(HELPERS)
    source = tmp_path / 'main.dewy'
    source.write_text('import p"helpers.dewy"\nprintl"{mean([1 2])} {first([1 2])} {own()}"\n')
    found = warnings_of(compiler, source)
    assert len(found) == 2, found
    mean = next(line for line in found if '`mean`' in line)
    assert ':1:1: warning: `mean` from the splat import of helpers.dewy shadows the prelude\'s `mean` (lib/std/nd.jo)' in mean
    assert '`from p"helpers.dewy" import mean`' in mean and '`import p"helpers.dewy" as helpers`' in mean
    assert any("the prelude's `first` (lib/prelude/arrays.dewy)" in line for line in found)
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.stdout.split() == ['2', '7', '1'], run.stdout + run.stderr


def test_selected_or_named_imports_are_quiet(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'helpers.dewy').write_text((HELPERS) + "\n$runtime_checks\n")
    selected = tmp_path / 'selected.dewy'
    selected.write_text(('import p"helpers.dewy"\nfrom p"helpers.dewy" import mean, first\nprintl"{mean([1 2])} {own()}"\n') + "\n$runtime_checks\n")
    named = tmp_path / 'named.dewy'
    named.write_text(('import p"helpers.dewy" as h\nprintl"{h.mean([1 2])} {mean([1 2])}"\n') + "\n$runtime_checks\n")
    assert warnings_of(compiler, selected) == []
    assert warnings_of(compiler, named) == []


def test_editor_shows_the_warning(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    (tmp_path / 'helpers.dewy').write_text(HELPERS)
    source = tmp_path / 'main.dewy'
    text = 'import p"helpers.dewy"\nprintl"{own()}"\n'
    source.write_text(text)
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        warnings = [d for d in diagnostics if d['severity'] == 2 and 'shadows the prelude' in d['message']]
        assert len(warnings) == 2, diagnostics
        assert all(d['range']['start'] == {'line': 0, 'character': 0} for d in warnings), warnings
    finally:
        client.close()
