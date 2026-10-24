"""Scalar lexer dispatch stays identical at every bounded punctuation prefix."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core import lexer_span_helpers


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_punctuation_dispatch(compiler, tmp_path, release):
    source = tmp_path / 'punctuation.jo'
    source.write_text(lexer_span_helpers(compiler, tmp_path) + '''
main = () -> int:
    # Every operator spelling, every truncated prefix, and every next byte.
    # Longer spellings continue through the reference scanner. The next byte
    # is deliberately outside stop in the truncated cases.
    loop code in [1..int(DewyToken.multiply_apply)):
        word = dn_token_text(DewyToken(code))
        if len(word) == 0 or dn_ident_start(word[0]): continue
        loop following in [0..256):
            text = word + chr(following)
            files = [SrcFile(path = "punct.dewy", src = text, is_dewy = true)]
            loop stop in [1..len(word) + 1):
                expected = dn_lex_symbol(data(text), 0, stop)
                loop intern_names in [false, true]:
                    ts = dn_lex(0, 0, stop, intern_names)
                    assert(ts[0].symbol == expected)
                    assert(ts[0].start == 0)
                    assert(ts[0].stop == len(dn_token_text(expected)))
            # Include a following punctuation or Unicode identifier in the span.
            if following == 61 or following == 63 or following == 62 or following >= 128:
                expected = dn_lex_symbol(data(text), 0, len(text))
                ts = dn_lex(0, 0, len(text))
                assert(ts[0].symbol == expected)
                assert(ts[0].stop == len(dn_token_text(expected)))
    42
''')
    binary = tmp_path / 'punctuation'
    built = subprocess.run([compiler, 'build', source, *(['--release'] if release else []), '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 42, ran.stdout + ran.stderr
