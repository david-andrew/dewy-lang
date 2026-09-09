"""Compile the sketch once; compare its tokens/pairs with hosted t0 on small programs."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.parser import t0
from dewy.reporting import SrcFile
from udewy.cache import cache_layout
from udewy.frontend import EntryPointOptions, entry_point

REPO = Path(__file__).resolve().parents[2]
SKETCH = REPO / 'dewy/bootstrap/parser/t0_sketch.dewy'

# A test entry point prints semantic fields rather than parsing Token.__as__.
# All scanning, selection, construction, and stack handling comes from the sketch.
DUMP_MAIN = r'''
# Keep this independent of the Number test below: the current backend mishandles
# sequential subtype tests on an abstract nominal family (see sketch notes).
dump_exponent = (token:Token):>void => {
    if token is? ExponentMarker {
        printl"E\t{token.power.prefix}\t{token.power.loc.start}\t{token.power.loc.stop}"
    }
}
main = (argv:array<string>):>int64 => {
    if argv.length <? 2 return 2
    path = p(argv[1])
    body = path.read_text
    if body isnt? string return 2
    result = tokenize(SrcFile[path=path.path body=body])
    if result is? TokenError { result.fail }
    loop token in result.tokens {
        printl"T\t{token.typename}\t{token.loc.start}\t{token.loc.stop}"
        if token is? Number { printl"N\t{token.prefix}" }
        dump_exponent(token)
    }
    loop pair in result.pairs { printl"P\t{pair.opening}\t{pair.closing}" }
    return 0
}
'''


@pytest.fixture(scope='module')
def sketch_binary(tmp_path_factory):
    folder = tmp_path_factory.mktemp('bootstrap-t0')
    source = SKETCH.read_text().split('\nmain = ', 1)[0] + DUMP_MAIN
    emitted = folder / 'sketch.udewy'
    emitted.write_text(codegen(SrcFile(SKETCH, source)))
    assert entry_point(emitted, [], EntryPointOptions(compile_only=True)) == 0
    cache_dir, name = cache_layout(emitted)
    return (cache_dir / name).resolve()


def run_sketch(binary, folder, source):
    path = folder / 'input.dewy'
    path.write_bytes(source.encode())
    return subprocess.run([str(binary), str(path)], capture_output=True, text=True, timeout=10)


def read_dump(output):
    tokens, pairs = [], []
    for line in output.splitlines():
        fields = line.split('\t')
        if fields[0] == 'T':
            tokens.append([fields[1], int(fields[2]), int(fields[3]), None, None])
        elif fields[0] == 'N':
            tokens[-1][3] = fields[1]
        elif fields[0] == 'E':
            tokens[-1][4] = (fields[1], int(fields[2]), int(fields[3]))
        elif fields[0] == 'P':
            pairs.append((int(fields[1]), int(fields[2])))
        else:
            pytest.fail(f'unexpected dump line: {line}')
    return tokens, pairs


@pytest.mark.parametrize('source', [
    '',
    '[1..3) (1..3] {[1](2)}',
    '0x[ff (10) ff] 0r[z]',
    '$name $ a << b <a >? b> <(a >> b)>',
    '0zXE 0zxe 0xAf 0tT',
    '1e10 1 e10 1e+10 1p0xAf',
    '"" r"" t""',
    '"hello" \'world\'',
    '"""hello""" """"""',
    'r"\\n {literal} ${also literal}"',
    '"a{1+2}b"',
    't"a${1+2}b {literal}"',
    '\'outer{"inner"}end\'',
    r'"a\"b\n\q\{c"',
    r'"\u0041\U00AF\u{ff (10) 0d65}"',
    '"a\\\nb"',
    '# comment\n#{ outer #{ inner }# }# "tail"',
])
def test_matches_hosted_tokens_and_pairs(sketch_binary, tmp_path, source):
    run = run_sketch(sketch_binary, tmp_path, source)
    assert run.returncode == 0, run.stderr
    actual_tokens, actual_pairs = read_dump(run.stdout)
    expected_tokens, expected_pairs = [], []
    for token in t0.tokenize(SrcFile(None, source)):
        prefix = token.prefix if isinstance(token, t0.Number) else None
        power = (token.power.prefix, token.power.loc.start, token.power.loc.stop) if isinstance(token, t0.ExponentMarker) else None
        expected_tokens.append([type(token).__name__, token.loc.start, token.loc.stop, prefix, power])
        partner = getattr(token, 'matching_right', None) or getattr(token, 'matching_quote', None)
        if partner is not None and partner.idx > token.idx:
            expected_pairs.append((token.idx, partner.idx))
    assert actual_tokens == expected_tokens
    assert actual_pairs == sorted(expected_pairs, key=lambda pair: pair[1])


@pytest.mark.parametrize(('source', 'message'), [
    ('prefix [}', 'Mismatched opening and closing delimiters'),
    ('0x[1)', 'Mismatched opening and closing delimiters'),
    ('prefix { [', 'Unclosed delimiters'),
    ('prefix "unterminated', 'Unclosed delimiters'),
    ('prefix "a{[', 'Unclosed delimiters'),
    ('"trailing\\', 'Incomplete escape sequence'),
    (r'"\u12"', 'Unicode escape sequence is too short'),
    (r'"\x41"', 'Hex byte escapes are not supported'),
    ('0r123', 'Number base too high'),
    ('prefix #{ unclosed', 'Unterminated block comment'),
])
def test_malformed_input_reports(sketch_binary, tmp_path, source, message):
    run = run_sketch(sketch_binary, tmp_path, source)
    assert run.returncode == 1, run.stdout + run.stderr
    assert message in run.stderr


def test_graphemes_and_crlf(sketch_binary, tmp_path):
    # Dewy's spans count graphemes, unlike Python's t0 offsets. CRLF is one,
    # and a combining accent stays with its preceding letter.
    run = run_sketch(sketch_binary, tmp_path, '"e\u0301"\r\n')
    assert run.returncode == 0, run.stderr
    tokens, pairs = read_dump(run.stdout)
    assert [(t[0], t[1], t[2]) for t in tokens] == [
        ('StringQuoteOpener', 0, 1), ('StringChars', 1, 2),
        ('StringQuoteCloser', 2, 3), ('Whitespace', 3, 4),
    ]
    assert pairs == [(0, 2)]
    assert not run.stderr


def test_lone_cr_warning_does_not_discard_tokens(sketch_binary, tmp_path):
    run = run_sketch(sketch_binary, tmp_path, '"e\u0301"\r\n\r')
    assert run.returncode == 0, run.stderr
    assert run.stderr.count('Lone carriage return') == 1
    # Report.warn currently leaves ordinary output routed to stderr. Check the
    # lexical result independently of that pre-existing reporting-library bug.
    records = '\n'.join(line for line in (run.stdout + run.stderr).splitlines()
                        if line.startswith(('T\t', 'N\t', 'E\t', 'P\t')))
    tokens, pairs = read_dump(records)
    assert [(t[0], t[1], t[2]) for t in tokens] == [
        ('StringQuoteOpener', 0, 1), ('StringChars', 1, 2),
        ('StringQuoteCloser', 2, 3), ('Whitespace', 3, 5),
    ]
    assert pairs == [(0, 2)]
