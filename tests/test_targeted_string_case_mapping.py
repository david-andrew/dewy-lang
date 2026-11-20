from tools.compiler import dewy_fuzz_targeted as targeted


def test_targeted_strings_expect_full_uppercase_mapping():
    program = targeted.make('strings', 31000059)
    assert ('printl(s.upper())', '  ΛBZSSB\n') in program.checks
