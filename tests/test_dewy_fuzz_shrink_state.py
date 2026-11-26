from tools.compiler import dewy_fuzz_targeted as fuzz


def test_shrinking_keeps_mutations_used_by_later_expected_outputs():
    checks = [('x = x + 1\nprintl(x)', '1\n'), ('printl(x)', '1\n'), ('printl(9)', '9\n')]
    test = fuzz.Test('arith', 1, [], ['let x:int = 0'], checks)

    class Runner:
        def outcome(self, candidate, mode):
            if not candidate.setup:
                return 'reject', 'missing x', ''
            # A defect in the second observation persists even if a reducer
            # mistakenly removes the update its expected output depends on.
            if checks[1] in candidate.checks:
                return 'mismatch', 'wrong output', ''
            return 'pass', '', candidate.expected

    failure = fuzz.Failure(test, 'native', 'mismatch', 'wrong output')
    reduced = fuzz.Fuzzer.shrink(Runner(), failure)
    assert reduced.checks == checks[:2]
