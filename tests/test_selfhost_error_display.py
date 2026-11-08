"""How errors are shown (the source line and caret, library errors moved to the program's call,
generic calls as notes, held errors in source order, assert messages' conditions) as a Dewy leaf
agrees with frozen Jo: the same exit codes, messages and output bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

CASES = [
    'tests/cases/witness/generic_instance.dewy',
    'tests/cases/dogfood23_proofs/errors_every_function.dewy',
    'tests/cases/dogfood24_proofs/errors_after_two_type_errors.dewy',
    'tests/cases/errors/library_division_location.dewy',
    'tests/cases/errors/inferred_result_error_cascade.dewy',
    'tests/cases/errors/or_throw_optional_error.dewy',
    'tests/cases/errors/unit_import_hint.dewy',
]

ASSERTS = '''main = ():>void => {
    let words = "a b\tc".split(" ")
    $runtime_assert(words.length =? 3 and ("(" =? words[0] or words[1] =? "]"))
}
'''

# (the lexer corpus's generated-14: an error on a line holding bytes that are not UTF-8, its
# start inside no character; the Jo original showed the line's bytes as they are)
GENERATED_14 = (b'ab {}]:\t{#[\'{\n<9}a\t#\'b"({a\t(b:?]>_?b(\'\xff(:"<#\\\'[a0# "[#0\xff(:\t\xff{a: \t"<('
                b'\n\x80<><(c<".<')

# (a caret after multi-byte characters, and an assert's condition holding them)
WIDE = 'main = ():>void => {\n    let s = "é…"\n    $runtime_assert(s =? "ü" or s.length =? 9)\n    let x:int64 = "µ" + 1\n}\n'

TABBED = 'main = ():>void => {\n\tlet x:int64 = "text"\n\tprintl"{x}"\n}\n'


def test_error_display_matches_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'asserts.dewy').write_text(ASSERTS)
    (tmp_path / 'tabbed.dewy').write_text(TABBED)
    (tmp_path / 'generated-14.dewy').write_bytes(GENERATED_14)
    (tmp_path / 'wide.dewy').write_text(WIDE)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('error_display',),
                             CASES + ['asserts.dewy', 'tabbed.dewy', 'generated-14.dewy', 'wide.dewy'])
    assert sum(r[2] != 0 for r in results) >= 6, [r[:3] for r in results]
    assert all('panic' not in r[4] for r in results), [r[4] for r in results if 'panic' in r[4]]
    shown = next(r for r in results if r[0].endswith('generated-14.dewy'))
    assert shown[2] == 1 and 'unterminated string' in shown[4], shown[:5]
