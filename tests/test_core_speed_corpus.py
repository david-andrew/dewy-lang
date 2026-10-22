"""The compile-speed corpora: line counting and program selection, no compiles."""
import pytest

from tools.compiler import speed_corpus as corpus

pytestmark = pytest.mark.core_quick


def test_source_lines_skip_blanks_and_comments():
    text = ('# header\n\nlet a=1 # trailing\n   # indented\n'
            '#{ block\nstill comment\n#{ nested }#\nmore }#\n'
            'let b=2 #{ inline }#\n#{ one line }#\n  \t\nlet c=3\n')
    assert corpus.source_lines(text) == 3
    assert corpus.source_lines('') == 0


def test_library_lines_from_time_output():
    stderr = ('check 1 ms\nsources: 74 files, 31 Dewy lines (857 bytes), 37819 implementation lines (1495141 bytes)\n')
    assert corpus.library_lines(stderr, 31) == 37819
    assert corpus.library_lines(stderr, 11) == 37839
    with pytest.raises(ValueError):
        corpus.library_lines('no counts', 0)


def test_root_files_follow_relative_imports_only(tmp_path):
    (tmp_path / 'main.dewy').write_text('from p"model.dewy" import x\nfrom p"@lib/game/image.jo" import deflate\n'
                                        '# from p"ignored.dewy" import y\n')
    (tmp_path / 'model.dewy').write_text('from p"main.dewy" import z\nlet x=1\n')
    (tmp_path / 'ignored.dewy').write_text('let y=1\n')
    files = corpus.root_files(tmp_path / 'main.dewy')
    assert [f.name for f in files] == ['main.dewy', 'model.dewy']
    assert [f.name for f in corpus.standalone(sorted(tmp_path.glob('*.dewy')))] == ['ignored.dewy']
    (tmp_path / 'main.dewy').write_text('printl"hi"\n')
    assert [f.name for f in corpus.standalone(sorted(tmp_path.glob('*.dewy')))] == ['ignored.dewy', 'model.dewy']


def test_corpora_membership(tmp_path):
    found = corpus.corpora(tmp_path)
    assert list(found) == ['compiler', 'ladder+examples', 'game', 'tier-4']
    assert corpus.ROOT / 'compiler/zip.dewy' in found['compiler']
    assert all(path.suffix == '.dewy' for paths in found.values() for path in paths)
    mixed = found['ladder+examples']
    assert corpus.LADDER / '01_word_count/core.dewy' in mixed
    assert not any(path.name == 'design.dewy' for path in mixed)
    assert corpus.ROOT / 'examples/dunes.dewy' in mixed and corpus.ROOT / 'examples/dunes_model.dewy' not in mixed
    early = {int(path.parent.name.split('_')[0]) for path in mixed if path.parent.parent == corpus.LADDER}
    assert early and max(early) < corpus.TIER4_FIRST
    assert all(int(path.parent.name.split('_')[0]) >= corpus.TIER4_FIRST for path in found['tier-4'])
    assert [path.name for path in found['game']] == ['dunes.dewy', 'game.dewy']
