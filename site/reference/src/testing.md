# Testing

Tests are ordinary functions marked `$test`. `dewy test` finds them, builds each module with a generated runner as its entry, runs the runners, and adds up the failures. Nothing about a test function is special to the compiler beyond the annotation: it is checked, callable, and compiled like any other function, and a module keeps its own `main` for ordinary runs.

## `$test` and `$expect`

`$test` on the line before a module-level function declaration marks it as a test. `$expect condition` (or `$expect condition, message`) states what the test checks:

<!-- dewy-example: compiler -->

```dewy
let identity = (x:int64):>int64 => x

$test
let identity_is_itself = () => {
    $expect identity(42) =? 42, "forty-two isn't itself"
}
```

`$expect` has the same shape as `$assert` and `$runtime_assert` — a condition, an optional message that may interpolate values — and, like `$runtime_assert`, it is checked at runtime when the compiler cannot decide it. It differs in what a failure means:

- A failed expectation is recorded and **returns from the enclosing function**. The test stops at its first failure and the runner reports it; other tests still run. Because execution never continues past a false expectation, the code after one may assume it — `$expect v is? int64` narrows `v` exactly as an assertion does.
- The report is the assertion report (the condition underlined in its source line, the message, a `note:` with each operand's value), written to stderr as `expectation failed`; the test's stdout continues afterwards.
- An expectation the compiler *refutes* is a warning, not an error: the module still builds and the test fails when it runs. `$fail "not reached"` is the deliberate "fail here" (a literal `false` condition is not warned about either). An expectation the compiler proves costs nothing.
- Expectations live in `void` functions: the test itself, or a helper it calls (the helper returns on failure; the test goes on). A function that returns a value cannot contain one — it returns the value to the test that checks it.

`$fail message` (or a bare `$fail`) is an expectation that always fails — the deliberate "this must not be reached" of a test, and the honest placeholder for a test not written yet.

`$assert` and `$runtime_assert` keep their meaning inside tests. A `$assert` that fails is a compile error before any test runs; a failed `$runtime_assert` exits the test binary (the runner reports the file as aborted), so it is for invariants a test cannot sensibly continue past.

## Cases

`$test(cases=…)` runs the test once per case. A tuple or array of values passes each element as the single argument; an array of object literals passes each object's fields by name; a computed array (a module constant) is looped over with each element as the single argument:

<!-- dewy-example: compiler -->

```dewy
let identity = (x:int64):>int64 => x

$test(cases=(1 2 3 4))
let identity_holds = (x:int64) => $expect identity(x) =? x, "identity of {x} is not {x}. got {identity(x)}"

$test(cases=[
    [a=1 b=2]
    [a=5 b=7]
    [a=(-3) b=4]
])
let addition_commutes = (a:int64 b:int64) => {
    $expect a + b =? b + a
}
```

Each case is reported as `name[index]`. A test that takes parameters must be given cases, and one that takes none cannot be.

## Running tests

`dewy test` is the one command, a subcommand like `dewy analyze`:

- `dewy test file.dewy` runs one module's tests. The module is built with a generated entry that calls each test (per case), printing a green `.` for each pass and a red `F` for each failure as it goes; everything a test prints — its expectation report included — is captured and shown only if it fails, under a `--- FAIL name[case]` header after the marks, followed by the summary (`1 failed, 10 passed`). The exit status is the failure count (at most 100), or 101 when a `$runtime_assert` aborted the binary, 102 when the module did not build, 128+n for a signal. The binary is `<stem>.test` beside the module's ordinary one, and the module's own `main` is untouched.
- `dewy test [directory]` (default `.`) runs every `.dewy` file under the directory with a line beginning `$test` — hidden entries and `__dewycache__` are skipped — by running `dewy test` on each (one line per file: `tests/dewy/expectations.dewy .................`) and adding up the failures. The runner itself is a Dewy program (`tools/dewy_test.dewy`). Output of child processes a test starts is not captured; `run_silent` discards it.
- `--json` on either form switches every line to a JSON object (per test, per file, and a summary).

Each module's tests run in their own process, so a test cannot disturb another module's, and an aborted binary is reported without hiding the others.

## Whole programs

A program's behaviour is tested the same way as anything else: a test that builds an executable, runs it, and checks the result. The compiler's own fixture programs are tested like this (`tests/dewy/programs.dewy`), by running the host compiler and then the binary:

<!-- dewy-example: compiler -->

```dewy
$test(cases=[
    [name="overload_calls.dewy" expected=42]
    [name="file_io.dewy" expected=42]
])
let program_exit_status = (name:string expected:int64) => {
    let source = p"dewy/tests/{name}"
    let binary = p"__dewycache__/dewy/tests/{p(name).stem}"
    if not binary.exists {
        match run_silent("/usr/bin/env" ["python3" "-m" "dewy" "--compile" source.path]) {
            status:int64 => $expect status =? 0, "compiling {name} failed ({status})"
            <SpawnError> => $fail "could not start the compiler"
        }
    }
    match run_silent(binary.path []) {
        status:int64 => $expect status =? expected, "{name} exited with {status}"
        <SpawnError> => $fail "could not run {binary.path}"
    }
}
```

Once the compiler is written in Dewy, `compile` is a library function and the spawn disappears; the same goes for testing the compiler's own stages — `tokenize"…"`, `parse"…"`, `typecheck"…"` are ordinary functions whose results (`result is? UnterminatedString`) a test inspects, so invalid source is a string passed to them, never the body of a test.

## Planned

The design continues past what is implemented (see `dewy/status.md`): fixtures (`$test(fixtures=[db=temporary_db])`, passed before the case arguments, with lifecycle hooks for teardown), `$test.case` introspection inside a test, documentation tests (examples in doc strings and in these books), generated and guided cases (`cases=Generated`) with shrinking of failures, and parallel execution.
