"""tools/compiler/build.py builds into an existing output directory of an earlier build, and never into any other."""
import pytest

from tools.compiler import build as builder


def fake_build(output, **_):
    (output / 'bin').mkdir()
    (output / 'bin/dewy-core').write_text('new')
    return output / 'bin/dewy-core'


def test_a_fresh_directory_is_created_and_marked(tmp_path):
    out = tmp_path / 'core'
    assert builder.claim_output(out) is None
    assert (out / builder.OUTPUT_MARKER).is_file()


def test_an_earlier_output_is_replaced_and_its_copy_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'build_into', fake_build)
    out = tmp_path / 'core'
    out.mkdir()
    (out / 'build.json').write_text('{}')
    (out / 'old.txt').write_text('old')
    assert builder.build(out) == out / 'bin/dewy-core'
    assert (out / 'bin/dewy-core').read_text() == 'new' and not (out / 'old.txt').exists()
    assert not (tmp_path / 'core.previous').exists()
    # (and again: the marker of the run before names it an output)
    assert builder.build(out) == out / 'bin/dewy-core'


def test_a_failed_build_keeps_the_earlier_output(tmp_path, monkeypatch, capsys):
    def failing(output, **_):
        (output / 'self-build.log').write_text('boom')
        raise RuntimeError('self-build.log: boom')
    monkeypatch.setattr(builder, 'build_into', failing)
    out = tmp_path / 'core'
    out.mkdir()
    (out / 'build.json').write_text('{}')
    (out / 'old.txt').write_text('old')
    with pytest.raises(RuntimeError, match='boom'):
        builder.build(out)
    assert (tmp_path / 'core.previous/old.txt').read_text() == 'old'
    assert (out / 'self-build.log').read_text() == 'boom'
    assert 'core.previous' in capsys.readouterr().err
    # (the failed output is an output too: the next run replaces it)
    monkeypatch.setattr(builder, 'build_into', fake_build)
    builder.build(out)
    assert not (tmp_path / 'core.previous').exists()


def test_a_directory_that_is_not_a_build_output_is_refused(tmp_path):
    out = tmp_path / 'home'
    out.mkdir()
    (out / 'notes.txt').write_text('mine')
    with pytest.raises(RuntimeError, match='pass a new directory'):
        builder.claim_output(out)
    assert (out / 'notes.txt').read_text() == 'mine'
    file = tmp_path / 'file'
    file.write_text('x')
    with pytest.raises(RuntimeError, match='pass a new directory'):
        builder.claim_output(file)


def test_a_stray_previous_directory_is_never_deleted(tmp_path):
    out = tmp_path / 'core'
    out.mkdir()
    (out / 'build.json').write_text('{}')
    stray = tmp_path / 'core.previous'
    stray.mkdir()
    (stray / 'keep.txt').write_text('mine')
    with pytest.raises(RuntimeError, match='core.previous'):
        builder.claim_output(out)
    assert (stray / 'keep.txt').exists() and (out / 'build.json').exists()
