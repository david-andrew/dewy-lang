"""A broken C fixture must fail the rung before its Dewy source is checked."""
from pathlib import Path
import shutil

import pytest

from tools import ladder
from tools.cases import clean_environment


@pytest.mark.skipif(shutil.which('cc') is None, reason='requires a C compiler')
def test_ladder_c_library_build_failure(tmp_path):
    directory = tmp_path / '135_broken'
    directory.mkdir()
    (directory / 'broken.c').write_text('#error deliberate fixture build failure\n')
    # A nonexistent compiler ensures that the C failure is handled first.
    result = ladder.evaluate(Path('/unused/dewy-core'), directory, 'design',
                             tmp_path, clean_environment(), {'c_library': 'broken'})
    assert not result.ok
    assert not result.checked
    assert result.error.startswith('C fixture: ')
    assert 'deliberate fixture build failure' in result.error


@pytest.mark.parametrize('library', ['missing', '../outside', 42])
def test_ladder_c_library_requires_adjacent_source(tmp_path, monkeypatch, library):
    directory = tmp_path / '135_image'
    directory.mkdir()
    (directory / 'design.dewy').write_text('main = () => {}\n')
    (directory / 'expected.out').write_text('')
    monkeypatch.setattr(ladder, 'LADDER', tmp_path)
    doc = {'milestones': {'1': 'Example'}, 'design_passing': [],
           'programs': {'135_image': {'milestone': 1, 'c_library': library}}}
    assert ladder.validate(doc) == [
        '135_image needs c_library to name a C source beside design.dewy']
