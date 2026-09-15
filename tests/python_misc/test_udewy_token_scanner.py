"""Common token scans retain contextual rewrites and source locations."""
import pytest

from udewy import t1


@pytest.mark.parametrize('source, expected', [
    ('reader(1)', [('TK_IDENT_CALL', 6, 0), ('TK_NUMBER', 1, 7), ('TK_RIGHT_PAREN', None, 8)]),
    ('(f)(2)', [('TK_LEFT_PAREN', None, 0), ('TK_IDENT', 1, 1),
                ('TK_RIGHT_PAREN', None, 2), ('TK_EXPR_CALL', None, 2),
                ('TK_NUMBER', 2, 4), ('TK_RIGHT_PAREN', None, 5)]),
    ('not # comment\n =? 0', [('TK_NOT_EQ', None, 15), ('TK_NUMBER', 0, 18)]),
    ('x <<= 3', [('TK_IDENT', 1, 0), ('TK_UPDATE_ASSIGN', 'TK_LEFT_SHIFT', 4), ('TK_NUMBER', 3, 6)]),
    ('x: [int <uint8>]', [('TK_IDENT', 1, 0), ('TK_TYPE', 13, 3)]),
    (':><():>int>', [('TK_FN_TYPE', 9, 2)]),
    ('void( :void', [('TK_IDENT_CALL', 4, 0), ('TK_TYPE', 4, 7)]),
    ('0x_2A 0b_101 1_000', [('TK_NUMBER', 42, 0), ('TK_NUMBER', 5, 6), ('TK_NUMBER', 1000, 13)]),
])
def test_contextual_tokens(source, expected):
    actual = [(token.kind.name,
               token.value.name if isinstance(token.value, t1.Kind) else token.value,
               token.location) for token in t1.tokenize(source)]
    assert actual == expected


@pytest.mark.parametrize('source, message', [
    ('0x__', 'at least one digit'),
    ('0b__', 'at least one digit'),
    ('18446744073709551616', 'within 64 bits'),
    ('0x10000000000000000', 'within 64 bits'),
    ('import stuff', 'preprocessing directive'),
    ('x:[# comment\nint]', 'comments inside bracketed type annotations'),
    ('x:<# comment\nint>', 'comments inside type parameters'),
])
def test_scanning_keeps_literal_and_annotation_errors(source, message):
    with pytest.raises(SyntaxError, match=message):
        t1.tokenize(source)


@pytest.mark.parametrize('layout', [' ', '\t\r\n', '# one\n # two\n', ' # eof'])
def test_trivia_keeps_pending_annotation_and_eof(layout):
    source = 'let x:' + layout
    # A trailing provisional colon remains provisional just as without layout;
    # completing the annotation must replace it and retain the type's offset.
    assert t1.tokenize(source)[-1].kind == t1.Kind._TK_COLON
    source += '\nint'
    token = t1.tokenize(source)[-1]
    assert (token.kind, token.location, token.value) == (t1.Kind.TK_TYPE, len(source) - 3, 3)


def test_bad_annotation_reports_before_skipping_trivia():
    with pytest.raises(SyntaxError, match=r'line 1, column 4'):
        t1.tokenize('x:1 # comment\n int')
