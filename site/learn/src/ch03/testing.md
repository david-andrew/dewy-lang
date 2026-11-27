# Testing

Tests in Dewy are ordinary functions in your source files. Mark one with `$test`, state what it checks with `$expect`, and run `dewy test`. There is no framework to install, no naming convention to follow and no separate test language: a test can call anything the file can.

## A first test

`$test` goes on the line before a function at the top level of a file. `$expect` takes a condition, and optionally a message after a comma:

<!-- dewy-example: {"mode": "test", "file": "add.dewy", "stdout": "..\n2 passed\n"} -->
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

`dewy test add.dewy` builds the file with a generated entry that calls each test in order. It prints a `.` for each one that passes, then the counts. `main` does not run. The other way round, `dewy add.dewy` runs `main` and prints `42`, and the tests are only checked: they compile like any other function, so a test that no longer type-checks breaks the build straight away.

## When an expectation fails

A failing test prints `F`, and after the marks the runner shows what went wrong:

<!-- dewy-example: {"mode": "test", "file": "add.dewy", "exit": 1, "stdout": ".F\n--- FAIL off_by_one\nchecking 2+2\nadd.dewy:9:5: expectation failed: two and two\n        $expect add(2 2) =? 5, \"two and two\"\n                ^~~~~~~~~~~~~\nnote: add(2 2) is 4\n1 failed, 1 passed\n"} -->
```dewy
add = (a:int b:int) => a+b

$test
adds_numbers = () => $expect add(20 22) =? 42

$test
off_by_one = () => {
    printl"checking 2+2"
    $expect add(2 2) =? 5, "two and two"
}
```

The report has everything needed to start fixing it: the file and line, the condition underlined, your message, and a `note:` with the value of each side that is not a literal. What the test printed comes first; output from passing tests is not shown. The exit status is the number of failed tests, so a script or CI job can stop on it.

## Expectations return

A failed `$expect` returns from the function it is in. The test is marked failed and the runner goes on to the next one. Because the code after an expectation runs only if it held, it may rely on it, and the compiler uses it the way it uses an `if`: `$expect value is? int` narrows `value` for the rest of the test.

<!-- dewy-example: {"mode": "test", "file": "parse.dewy", "stdout": "..\n2 passed\n"} -->
```dewy
$test
parses_a_number = () => {
    let value = to_int("42")
    $expect value is? int, "not a number"
    $expect value + 1 =? 43
}

$test
rejects_words = () => {
    let value = to_int("forty-two")
    if value is? int { $fail "parsed {value}" }
}
```

Without the first expectation, `value + 1` would not compile: `to_int` may fail, and the compiler makes you deal with that. `$fail message` always fails. Use it on a branch that must not be taken, or as a placeholder for a test not written yet.

### Helpers

Checks you repeat can go in a helper. Expectations belong in functions that give no value: a test, or a helper it calls. A failure in a helper returns from the helper, so the test continues and is marked failed:

<!-- dewy-example: {"mode": "test", "file": "lists.dewy", "exit": 1, "stdout": "F\n--- FAIL lists\nlists.dewy:2:5: expectation failed: empty list\n        $expect xs.length >? 0, \"empty list\"\n                ^~~~~~~~~~~~~~\nnote: xs.length is 0\nthe test goes on\n1 failed, 0 passed\n"} -->
```dewy
starts_with_seven = (xs:array<int>) => {
    $expect xs.length >? 0, "empty list"
    $expect xs[0] =? 7
}

$test
lists = () => {
    starts_with_seven([7 1])
    starts_with_seven([])
    printl"the test goes on"
}
```

The second expectation in the helper is safe to write: `xs[0]` runs only once the length check has passed. A function that returns a value cannot contain an expectation; return the value and let the test check it.

## One test, many cases

`$test(cases=…)` runs a test once per case. A tuple passes each value as the one argument; an array of objects passes each object's fields by name. Each case is reported as `name[index]`:

<!-- dewy-example: {"mode": "test", "file": "cases.dewy", "exit": 1, "stdout": "...F..\n--- FAIL doubles[1]\ncases.dewy:7:22: expectation failed: doubling 2\n    doubles = (x:int) => $expect add(x x) =? 3 * x, \"doubling {x}\"\n                                 ^~~~~~~~~~~~~~~~~\nnote: add(x x) is 4\nnote: 3 * x is 6\n1 failed, 5 passed\n"} -->
```dewy
add = (a:int b:int) => a+b

$test(cases=[[a=1 b=2] [a=(-3) b=4]])
commutes = (a:int b:int) => $expect add(a b) =? add(b a)

$test(cases=(0 2))
doubles = (x:int) => $expect add(x x) =? 3 * x, "doubling {x}"

$test(cases=(1 2))
adds_zero = (x:int) => $expect add(x 0) =? x
```

`doubles` has a bug in the test itself: `3 * x` should be `2 * x`. Case `[0]` passes by luck, since zero is its own double, and case `[1]`, the value 2, shows the bug. The message interpolates the argument, so the report says which value failed.

A module constant array works as cases too, which keeps a long table of examples out of the test's header.

## Running some of the tests

Words after the file name select the tests whose names contain any of them. The rest are counted as not run:

<!-- dewy-example: {"mode": "test", "file": "shapes.dewy", "args": ["area"], "stdout": "..\n2 passed (1 not run: their names do not match)\n"} -->
```dewy
Rect:type = [w:int h:int]
area = (r:Rect):>int => r.w * r.h
perimeter = (r:Rect):>int => 2 * (r.w + r.h)

$test
square_area = () => $expect area(Rect[3 3]) =? 9

$test
empty_area = () => $expect area(Rect[0 5]) =? 0

$test
square_perimeter = () => $expect perimeter(Rect[3 3]) =? 12
```

The other options work the same way on any file:

```sh
dewy test game_tests.dewy              # every test in the file
dewy test --release game_tests.dewy    # test the optimized build
dewy test --watch game_tests.dewy wall # rerun the wall tests after every edit
dewy test --json game_tests.dewy       # one JSON object per test, for tools
dewy test                              # every file with tests under this directory
```

The VS Code extension runs the same command, with a **Run test** code lens above each `$test`.

## Testing a game without a window

A game is easiest to test when its rules do not touch the screen. The paddle example splits into three files: [`paddle_model.dewy`](https://github.com/david-andrew/dewy-lang/blob/master/examples/paddle_model.dewy) holds the rules, [`paddle.dewy`](https://github.com/david-andrew/dewy-lang/blob/master/examples/paddle.dewy) draws them, and [`paddle_tests.dewy`](https://github.com/david-andrew/dewy-lang/blob/master/examples/paddle_tests.dewy) tests them. The model is plain data and one function that advances it; it takes the time step and the pointer position as arguments instead of reading the mouse:

<!-- dewy-example: {"mode": "check"} -->
```dewy
# paddle_model.dewy (excerpt): the whole game state is one record
Point:type = [x:float64 y:float64]
World:type = [position:Point velocity:Point paddle:float64 score:int64 misses:int64]

fresh = ():>World => World[Point[640.0 220.0] Point[180.0 240.0] 640.0 0 0]
```

`advance(@world dt pointer)` moves the ball, bounces it off the walls and the paddle, and counts a miss when it falls past the bottom. The game file, `paddle.dewy`, only connects it to the frame loop: its `update` calls `advance(@world min(dt 0.05) mouse_pos().x)` and its `draw` reads the world.

The tests import the same model, set up a situation directly, step it once, and check the result:

<!-- dewy-example: {"mode": "test", "file": "paddle_tests.dewy", "fixtures": {"paddle_model.dewy": {"repo": "examples/paddle_model.dewy"}}, "stdout": "...\n3 passed\n"} -->
```dewy
from p"paddle_model.dewy" import fresh, advance

$test
fresh_world = () => {
    let world = fresh
    $expect world.score =? 0 and world.misses =? 0
    $expect world.position.x =? 640.0
}

$test
side_wall_bounce = () => {
    let world = fresh
    world.position.x = 1259.0
    advance(@world 0.1 640.0)
    $expect world.position.x =? 1260.0
    $expect world.velocity.x <? 0.0
}

$test
miss_resets_the_ball = () => {
    let world = fresh
    world.position.y = 759.0
    advance(@world 0.1 80.0)
    $expect world.misses =? 1 and world.score =? 0
    $expect world.position.x =? 640.0 and world.position.y =? 220.0
}
```

`dewy test` never runs a game's callbacks or opens a window, so these tests run in a terminal or on a CI machine with no display. They do not need a frame rate or a fake mouse either: a test is the pointer, and `0.1` is the frame time.

## Each test runs on its own

On native hosts every test runs in its own process. Changes a test makes to globals stay in that test, and a test that ends the program, through `exit`, a panic or a failed `$runtime_assert`, is reported as aborted while the rest still run:

<!-- dewy-example: {"mode": "test", "file": "abort.dewy", "exit": 101, "stdout": "F.F\n--- FAIL quits\nabout to exit\nthe test called exit(3) before its end\n--- FAIL todo\nabort.dewy:11:14: expectation failed: not written yet\n2 failed, 1 passed (1 aborted)\n"} -->
```dewy
$test
quits = () => {
    printl"about to exit"
    exit(3)
}

$test
still_runs = () => $expect 1 + 1 =? 2

$test
todo = () => $fail "not written yet"
```

An abort sets the exit status to 101, and a file that does not build gives 102, so a script can tell "tests failed" from "the tests could not run".

Files, processes and other effects outside the program are shared between tests, so a test that writes a file should use a name of its own.

## Testing code that uses time

Time is where tests most often go wrong: a test that reads the clock gives a different answer on every run. A clock that tests can set and advance is designed but not built yet, so for now the approach is to keep the clock out of the logic.

**Pass time in as a value.** A function that takes the current `Instant` as an argument, rather than calling `now`, can be tested at any moment you like, written as a literal:

<!-- dewy-example: {"mode": "test", "file": "sessions.dewy", "stdout": "..\n2 passed\n"} -->
```dewy
Session:type = [started:Instant ttl:Duration]

expired = (s:Session at:Instant):>bool => at - s.started >=? s.ttl

$test
lasts_its_ttl = () => {
    let s = Session[instant"2026-11-27T09:00:00Z" 30minute]
    $expect not expired(s instant"2026-11-27T09:29:59Z")
    $expect expired(s instant"2026-11-27T09:30:00Z")
}

# A daily job at 02:30 in New York, a time that does not exist on the day clocks spring forward.
run_at = (day:Date):>ZonedDateTime =>
    day.at(time_of_day"02:30").in_zone(zone"America/New_York" gap='next' fold='earlier')

$test
daily_job = () => {
    $expect "{run_at(date"2026-11-27")}" =? "2026-11-27T02:30:00-05:00[America/New_York]"
    $expect "{run_at(date"2026-03-08")}" =? "2026-03-08T03:00:00-04:00[America/New_York]"
}
```

The program itself calls `expired(session now.nominal)`. The test can reach the daylight-saving edge case directly instead of waiting for March. The zone and its rules are part of the code, not the machine: Dewy ships its own time zone data, so this test gives the same answer on every computer.

**Check durations with bounds.** When the code under test really does wait, check a bound, never an exact time. `time.elapsed(@f)` measures a call on the monotonic clock, and `within(limit @f)` gives `f`'s result or `Timeout`:

<!-- dewy-example: {"mode": "test", "file": "timing.dewy", "stdout": "..\n2 passed\n"} -->
```dewy
import time

pause = ():>void => { sleep(20ms); }
slow = ():>int => { sleep(200ms); 42 }
quick = ():>int => 7

$test
waits_at_least = () => {
    let took = time.elapsed(@pause)
    $expect took >=? 20ms, "slept only {took}"
}

$test
deadlines = () => {
    $expect within(50ms @slow) is? Timeout
    $expect within(1s @quick) =? 7
}
```

A lower bound on a sleep always holds. An upper bound depends on how busy the machine is, so keep the limits generous, as `1s` is for `quick`.

## Not built yet

The design also has fixtures with teardown, documentation tests, generated cases with shrinking, a settable test clock, and running tests in parallel. The [reference](/reference/testing.html) has the complete rules for what exists today.
