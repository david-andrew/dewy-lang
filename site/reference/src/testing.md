# Testing

> [Generated coverage](/status/#ref-testing) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

A test is an ordinary function marked `$test`. `$expect` states what it checks. `dewy test` builds the file with a generated entry that runs every test; an ordinary run or build of the same file runs its own `main` and ignores the tests.

## Test Functions

`$test` goes on the line before a module-level function declaration. The function is checked, compiled and callable like any other; only `dewy test` calls it automatically.

<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
add = (a:int b:int) => a+b

$test
adds_numbers = () => $expect add(20 22) =? 42

$test
adds_negatives = () => {
    $expect add(-1 -2) =? -3
    $expect add(-1 1) =? 0, "opposites cancel"
}

main = () => printl(add(20 22))
```

Running the file prints `42`. `dewy test` on it runs the two tests instead and does not run `main`.

## `$expect`

`$expect condition` or `$expect condition, message` checks a condition when the test runs. The message is a string and may interpolate values.

- A failed expectation is reported on standard error and **returns from the function it is in**. The test is marked failed; other tests still run.
- Because execution never continues past a false expectation, the code after it may assume it. `$expect value is? int` narrows `value` as an `if` would.
- An expectation the compiler proves costs nothing. One it refutes is a warning (`this expectation always fails`), not an error: the file still builds and the test fails when it runs.
- `$fail message` (or a bare `$fail`) always fails. Use it for code that must not be reached and for a test not written yet. Like `$expect`, it returns, so the code after it may assume the branch was not taken.

<!-- dewy-example: {"mode":"check"} -->
```dewy
$test
narrows = () => {
    let value:int? = 7
    $expect value is? int
    $expect value + 1 =? 8
}

$test
exit_statuses = () => {
    let status = run_silent("/usr/bin/false" [])
    if status is? exception { $fail "could not start the program" }
    $expect status =? 1, "false exited with {status}"
}
```

A failure report names the file and line, underlines the condition, gives the message, and adds a `note:` with the value of each compared operand that is not a literal:

```text
t.dewy:15:5: expectation failed: two and two
        $expect add(2 2) =? 5, "two and two"
                ^~~~~~~~~~~~~
note: add(2 2) is 4
```

### Helpers

Expectations live in functions that give no value: the test itself, or a helper it calls. A failure in a helper returns from the helper; the test goes on and is marked failed.

<!-- dewy-example: {"mode":"check"} -->
```dewy
starts_with_seven = (xs:array<int>) => {
    $expect xs.length >? 0, "empty input"
    $expect xs[0] =? 7
}

$test
helper_failure = () => {
    starts_with_seven([])
    printl"the test continues"
}
```

A function that returns a value cannot contain an expectation. It returns the value, and the test checks it:

<!-- dewy-example: {"mode":"reject","diagnostic":"expectations live in `void` functions"} -->
```dewy
first = (xs:array<int>):>int => {
    $expect xs.length >? 0
    return 1
}
```

### Assertions in Tests

`$assert` and `$runtime_assert` keep their meaning inside tests. A `$assert` the compiler cannot prove is a compile error, so no test runs. A failed `$runtime_assert` ends that test's process; the runner reports it as aborted and goes on. See [Refinements, Effects, and Safety](refinements-and-effects.md).

## Cases

`$test(cases=…)` runs the test once per case, reported as `name[index]`:

- a tuple or array literal passes each element as the one argument;
- an array of object literals passes each object's fields by name;
- a module constant array is looped over, each element the one argument.

<!-- dewy-example: {"mode":"check"} -->
```dewy
add = (a:int b:int) => a+b

$test(cases=(1 2 -3))
adds_zero = (x:int) => $expect add(x 0) =? x, "{x} changed"

$test(cases=[[a=1 b=2] [a=(-3) b=4]])
commutes = (a:int b:int) => $expect add(a b) =? add(b a)

Word:type = [text:string length:int]
WORDS:array<Word> = [Word["a" 1] Word["dewy" 4]]

$test(cases=WORDS)
lengths = (w:Word) => $expect w.text.length =? w.length
```

A test with parameters needs cases, and one without parameters cannot have them:

<!-- dewy-example: {"mode":"reject","diagnostic":"takes parameters: give it cases"} -->
```dewy
$test
needs_cases = (x:int) => $expect x =? x
```

<!-- dewy-example: {"mode":"reject","diagnostic":"takes no parameters, so it cannot be given cases"} -->
```dewy
$test(cases=(1 2))
no_parameters = () => $expect 1 =? 1
```

## Running Tests

```sh
dewy test file.dewy                  # every test in the file
dewy test file.dewy bounce wall      # tests whose names contain "bounce" or "wall"
dewy test --release file.dewy        # test a release build
dewy test --watch file.dewy bounce   # rerun after each edit
dewy test --json file.dewy           # one JSON object per test
dewy test dir/                       # every .dewy file under dir/ that declares tests
dewy test                            # the current directory
```

`dewy test` builds the selected file with a generated entry that calls each test, and each case, in declaration order. `main` and game callbacks do not run, and no window opens. Each test prints `.` when it passes and `F` when it fails. What a failing test printed is shown under `--- FAIL name[case]`, followed by the counts:

```text
......F
--- FAIL off_by_one
checking 2+2
t.dewy:15:5: expectation failed: two and two
        $expect add(2 2) =? 5, "two and two"
                ^~~~~~~~~~~~~
note: add(2 2) is 4
1 failed, 6 passed
```

Output from a passing test is not shown.

### Selecting Tests

Words after the file name select the tests whose names contain any of them; the rest are counted as not run (`2 passed (5 not run: their names do not match)`). No tests, or no matching names, is an error. Only tests declared in the selected file run; imported files supply code, not more tests.

Given a directory, `dewy test` runs each `.dewy` file under it that has a line starting with `$test`, skipping hidden directories and `__dewycache__`. It prints one line of marks per file and adds up the results.

### Build Modes

Tests use a debug build by default; `--release` tests a release build. `dewy check` checks a file's tests as well as its program.

### Isolation

On native hosts each test runs in its own child process. A test that aborts (a panic, a failed `$runtime_assert`, or a call to `exit`) does not stop the others, and changes a test makes to globals stay in that test. Linux and macOS fork after top-level initialization; Windows starts the executable again for each test, so top-level initialization repeats there (and a test's standard error is not collected). Files and other effects outside the program are shared.

```text
FF.
--- FAIL aborts
the test called exit(3) before its end
--- FAIL todo
t.dewy:6:14: expectation failed: not written yet
2 failed, 1 passed (1 aborted)
```

### Exit Status

| Status | Meaning |
|---|---|
| 0 | every selected test passed |
| 1 to 100 | that many tests failed (at most 100) |
| 101 | a test aborted |
| 102 | the file does not build |

### Watching and JSON

`--watch` reruns the selected tests when the source, an imported module or an embedded asset changes. Each run starts from fresh program state. After failing tests or a compile error it waits for the next edit; enter `r` to rerun or `q` to quit.

`--json` prints one object per test, with `test`, `status` and `ms`, plus `output` and `stdout` for a failure, then a summary:

```text
{"test":"commutes[0]","status":"pass","ms":0.2}
{"test":"off_by_one","status":"fail","ms":0.2,"output":"checking 2+2\n...","stdout":"checking 2+2\n"}
{"passed":1,"failed":1,"aborted":0,"not_run":5,"exit":1}
```

The VS Code extension runs the same command: **Dewy: Test Current File**, a release variant, a watch task, and a **Run test** code lens above each `$test`.

## Testing Whole Programs

A program's behavior is tested like anything else: a test runs the program and checks its status or output. `run_silent` gives the exit status, and `capture` also gives the output (see [Processes](command-line-programs.md#processes)).

<!-- dewy-example: {"mode":"check"} -->
```dewy
$test(cases=[
    [program="/usr/bin/true" expected=0]
    [program="/usr/bin/false" expected=1]
])
exit_status = (program:string expected:int) => {
    let status = run_silent(program [])
    if status is? exception { $fail "could not run {program}" }
    $expect status =? expected, "{program} exited with {status}"
}
```

Game logic is easiest to test when it takes its state and input as values. [`examples/paddle_tests.dewy`](https://github.com/david-andrew/dewy-lang/blob/master/examples/paddle_tests.dewy) imports a paddle game's model and checks bounces and misses without opening a window.

## Not Yet Built

The design also has test fixtures with teardown, `$test.case` introspection inside a test, documentation tests, generated cases with shrinking, and running tests in parallel. None of these is built yet.
