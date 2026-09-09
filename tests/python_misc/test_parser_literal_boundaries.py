"""Compound literal recognition at EOF must retain its final token."""
import pytest

from dewy.parser import t1
from dewy.reporting import SrcFile


@pytest.mark.parametrize('source,binary', [('1e10', False), ('1p10', True), ('1P0xA', True)])
def test_exponent_at_eof(source, binary):
    tokens = t1.tokenize(SrcFile(None, source))
    assert len(tokens) == 1
    assert isinstance(tokens[0], t1.Real)
    assert tokens[0].exponent.binary is binary


@pytest.mark.parametrize('source,content', [('$"""tail', 'tail'), ('$r"""\\n tail', '\\n tail'), ('$"""', '')])
def test_rest_of_file_string_keeps_final_body_token(source, content):
    tokens = t1.tokenize(SrcFile(None, source))
    assert len(tokens) == 1
    assert isinstance(tokens[0], t1.String)
    assert tokens[0].content == content


def test_empty_program_is_an_empty_block():
    from dewy.parser import p0
    tree = p0.parse(SrcFile(None, ''))
    assert tree.inner == []
    assert (tree.loc.start, tree.loc.stop) == (0, 0)


@pytest.mark.parametrize('keyword', ['break', 'continue'])
def test_labeled_exit_uses_the_normal_keyword_argument_shape(keyword):
    from dewy.parser import p0, t2
    source = SrcFile(None, f'{keyword} $outer')
    token = t2.postok(source)[0].items[0]
    assert isinstance(token.parts[1], t2.Chain)
    tree = p0.parse(source).inner[0]
    assert isinstance(tree.parts[1], p0.Atom)
    assert tree.parts[1].item.name == 'outer'


@pytest.mark.parametrize('operator', ['??', '<=>'])
def test_reserved_operator_reports_missing_precedence(operator):
    from dewy.parser import p0
    from dewy.reporting import ReportException
    with pytest.raises(ReportException, match='No precedence is defined'):
        p0.parse(SrcFile(None, f'a {operator} b'))
