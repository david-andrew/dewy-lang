"""Call resolution errors agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'secret/leak_argument',
    'dictionary/totaldict_pop',
    'named/value_missing',
    'fixed/array_grow',
    'generic/local_arity',
    'optional/to_int_optional_name',
    'handle/partial_generic_unknown',
    'argument/place_for_value',
    'dogfood32_proofs/self_call_method_name',
    'default/reference_closure_return',
    'union_hash/member_hash',
    'units/parameter_mismatch',
    'handle/joined_defaults',
    'conversion/bitcast_method',
    'empty_literal/no_binding_generic_rejected',
    'empty_literal/wrong_context_rejected',
    'expected_args/disagree_method',
    'x="a" % 3\nprintl(x)\n',
    'let xs=[1 2 3]\nprintl(join("," xs))\n',
]


def test_checks_call_errors_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
