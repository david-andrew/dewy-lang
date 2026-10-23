# Testing

> **Language design.** [Generated coverage](/status/#ref-testing) names measured programs and target restrictions; examples here illustrate the design.

## Current project tests

Mark a module-level function with `$test` on the line before it and state what it checks with `$expect`, as in `adds_numbers = () => $expect 20+22 =? 42`, then run `dewy test file.dewy`. A condition the program itself relies on is `$assert` (decided at compile time) or `$runtime_assert` (checked when it runs). See the [project testing guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md#test-a-project). The sections below describe the design, with coverage reported separately.

## Design test functions

In the language design, tests are ordinary functions marked `$test`. The test driver finds them, builds each module with a generated runner as its entry, runs the runners, and adds up the failures. Nothing about a test function is special to the compiler beyond the annotation: it is checked, callable, and compiled like any other function, and a module keeps its own `main` for ordinary runs.

## `$test` and `$expect`

`$test` on the line before a module-level function declaration marks it as a test. `$expect condition` (or `$expect condition, message`) states what the test checks:

<!-- dewy-example: {"mode":"design-only"} -->
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

<!-- dewy-example: {"mode":"design-only"} -->
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

For the current compiler, use the [project-test guide](#current-project-tests).
The `$test` model above specifies test discovery and per-case expectations;
its runner behavior is part of the design rather than a promise about the current
command. Historical driver details are retained in the [archive](/archive/).

## Whole programs

A program's behaviour is tested the same way as anything else: a test that builds an executable, runs it, and checks the result. The design can express a subprocess-based compiler test as follows:

<!-- dewy-example: {"mode":"design-only"} -->
```dewy
$test(cases=[
    [name="overload_calls.dewy" expected=42]
    [name="file_io.dewy" expected=42]
])
let program_exit_status = (name:string expected:int64) => {
    let source = p"dewy/tests/{name}"
    let binary = p"__dewycache__/dewy/tests/{p(name).stem}"
    if not binary.exists {
        match run_silent("dewy" ["build" source.path "-o" binary.path]) {
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

The further design includes: fixtures (`$test(fixtures=[db=temporary_db])`, passed before the case arguments, with lifecycle hooks for teardown), `$test.case` introspection inside a test, documentation tests (examples in doc strings and in these books), generated and guided cases (`cases=Generated`) with shrinking of failures, and parallel execution.
