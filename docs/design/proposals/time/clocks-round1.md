# Clocks for a scope: awake time, test clocks and fine-tick display (round 1)

Inputs: [time.md](../../time.md) "Clocks and waits" (accepted); [v5](time-design-v5.md) §7 (providers, capture, test clocks, suspension); the three gaps the last implementation round reported; batch 9's settings scoped to a function and [runtime-settings/summary.md](../runtime-settings/summary.md). Open item: D47 in [open_decisions.md](../../open_decisions.md). Programs: [clocks-programs-r1/](clocks-programs-r1/).

## BLUF

- **The gaps.** The time core is built except three things the design names but never spelled: choosing awake-only time for a scope (v5's `clocks.active`), a test clock a program can construct and drive, and how an instant on a tick like `1ns/3` prints.
- **Both clock choices are settings, like the zone.** `$time.monotonic = 'awake'` at the top of a function makes its waits, deadlines and elapsed times count only time the machine is awake. `$time.clock = time.test_clock()` puts a function, its calls and its tasks on a virtual clock. They are scoped, inherited and captured by the rules `$time.zone` already follows, and every clock call also takes them as arguments (`sleep(30s monotonic='awake')`), as `today` takes the zone. This replaces v5's `time.with_clocks(clocks.active @job)` and `time.with_context(test.context @job)`, which needed a named function per scope and which cold readers took to mean "the clocks currently active".
- **The implementation round's question answers itself.** An awake scope keeps the wall clock in force, because the setting selects only the monotonic clock. `today` and `.nominal` never change.
- **The two monotonic clocks can't be mixed by accident.** A reading's clock is part of its type, so subtracting an awake reading from a continuous one is a compile error. `r.elapsed` and `d.remaining` measure on the reading's or deadline's own clock, and a deadline is accepted wherever a timeout is.
- **A test clock moves only when nothing else can happen.** When every task under it is waiting on it or on each other, it jumps to the next deadline, so a retry loop with 1s, 2s and 4s of backoff finishes at once and `now - start` is exactly 7s. Tasks under it run one at a time in a fixed order, so equal deadlines wake in a chosen, repeatable `wake_order`. `time.advance(5s)` checks a moment; `time.simulate_suspend`, `time.simulate_wall_step` and `time.simulate_monotonic_reset` reach the clock events v5 promises tests can reach.
- **Fine ticks print exactly (taken).** An instant on a decimal tick (`1ns/4`) prints exact RFC 3339 with more digits. One on a tick with no finite decimal (`1ns/3`) prints exactly as an instant plus a remainder, `2026-10-24T12:00:00Z + 1/3ns`; anything that promises RFC 3339 to another program asks for `.round(1ns)`.
- **Dogfooded** (34 programs, three iterations; §7) **and names tested cold** (six rounds; §6).

## 1. What exists and what is missing

| Design says | Built | Missing |
|---|---|---|
| Relative waits count suspend-inclusive time; `clocks.active` excludes suspension and is explicit (time.md) | The continuous clock (`CLOCK_BOOTTIME` and peers) | Any way to select the awake clock |
| `TemporalContext` captured at entry, inherited by closures and tasks; `time.with_context` installs one for tests (time.md, v5 §7) | Settings scoped to a function, inherited by calls and tasks, captured at `@` (batch 9) | A test clock: no constructor, no driver, no wake order for equal deadlines |
| Instants print as RFC 3339 (time.md "UTC") | Nanosecond instants | Instants on caller-chosen rational ticks print as raw records |

Since v5 was written, everything else a `TemporalContext` held has become a setting: the zone (`$time.zone`), the calendar (`$calendar`), the gap and fold policies (`$time.gap`, `$time.fold`). A library reads them as parameter defaults (`today = (scope=$time.zone) => …`). The clock is the last member left, and the same mechanism fits it, so this design has no `TemporalContext` value and no `with_context`.

## 2. Awake time: `$time.monotonic = 'awake'`

```dewy
lock_when_idle = (session:Session) => {
    $time.monotonic = 'awake'                 # a closed lid doesn't count toward the 5 minutes
    loop true {
        match session.input.receive(timeout=5minute) {
            <Timeout> => { session.lock(); return }
            <Closed> => return
            key:Key => session.handle(key)
        }
    }
}
```

**Rules.**

- **Values.** `'continuous'` (the default, decided in time.md: an hour with the lid closed counts as an hour) and `'awake'` (only time the machine is awake: Linux `CLOCK_MONOTONIC`, macOS `mach_absolute_time`, Windows unbiased interrupt time). Awake time is not CPU time; process and thread CPU clocks stay separate.
- **What it changes,** in its scope, its calls and the tasks they start: the monotonic sample in `now`, `monotonic`, `sleep`, `within`, `receive`/`send(timeout=)`, `select(… timeout=)`, `ticker`, `reading + d` deadlines and `time.elapsed`.
- **What it never changes:** `.nominal`, `today`, `strict_today` and anything else on the wall clock. That answers the implementation round's question (does an awake scope keep the captured wall provider?): yes, by construction, with no clock set to rebuild.
- **Placement, inheritance and capture** are `$time.zone`'s ([runtime-settings/summary.md](../runtime-settings/summary.md)): a policy setting starts at its line and covers the rest of its function or block, its calls and the tasks started there. A function value captures the setting only if one is written in force at its `@`; one made where none is written (a module-level `@fetch_page`) follows whoever runs it. A block scopes one wait: `{ $time.monotonic = 'awake'; sleep(30s) }`.
- **Per call.** Every clock operation takes `monotonic=`, defaulting to the setting, as `today` takes the zone: `now(monotonic='continuous')`, `sleep(1hour monotonic='awake')`, `ticker(1s monotonic='awake')`, `within(d @f monotonic='awake')`, `c.receive(timeout=d monotonic='awake')`. A library that defaults to awake but lets its caller choose writes a parameter: `idle_watch = (limit:Duration mode:'awake' | 'continuous' = 'awake') => { $time.monotonic = mode … }`.
- **A run-time value** (`$time.monotonic = if prefs.pause_on_sleep 'awake' else 'continuous'`) compiles the rest of the scope once per clock, as `$fast_math = flag` does, so the readings inside keep a static clock; a reading that leaves such a scope has the union type.

**Readings and deadlines know their clock.**

- **The clock is in the type.** `now` in an awake scope gives `ClockReading<monotonic='awake'>`; elsewhere plain `ClockReading`, which means `monotonic='continuous'`. `MonoPoint` likewise. The parameter is inferred and written only where readings are stored. `-`, `<?` and `+` between the two clocks are compile errors, reported at the line that brings them together (a method's caller, not the method). A record that serves either clock is generic: `Limiter:type = <M:'awake' | 'continuous' = 'continuous'>[sent:array<ClockReading<monotonic=M>> limit:int]`.
- **`r.elapsed` and `d.remaining`.** `r.elapsed` is the time since reading `r` on `r`'s own clock; `d.remaining` is the time left until deadline `d` on `d`'s own clock, `0s` once it has passed. They never mismatch, need no narrowing (even for a union reading), and replace `now(monotonic=…) - r`: `if sent[0].elapsed >? 1minute { sent.remove(0) }`.
- **A deadline goes wherever a timeout goes.** `timeout=` and `within` accept a `MonoPoint` as well as a `Duration`, and the wait uses the deadline's clock whatever the scope says. Two clocks in one wait compose with calls that exist: a paid session's continuous deadline around an awake idle timeout is `within(paid_until @idle_loop(input))`. `MonoPoint - ClockReading` gives a `Duration`, as the library already does.
- **Across boundaries the compiler can see** (a module-level `STARTED = now` read in a test-clock scope, a deadline passed as an argument into an awake scope), a mix is a compile error naming both settings. One that arrives through a channel or a stored structure is the existing named clock-domain assumption: the task ends with a report, and under `$time.require_clock_domain` `-` gives `Duration | ClockDiscontinuity | DomainMismatch` and `<?` gives `bool | ClockDiscontinuity | DomainMismatch` (a different clock is a mismatch; the same clock after a reset is a discontinuity).
- **Platforms.** A target with no awake clock fails at entry, only if the program reaches the setting, as the continuous clock already does.
- **Cost.** A program that never writes `$time.monotonic` pays nothing. One that does reads one task-local word per clock operation, as `today` reads the zone. The type parameter costs nothing at run time.

**Considered.**

- *v5's `time.with_clocks(clocks.active @job)`.* Each awake scope needs a named function and a handle, `with_clocks` raises the very question this round was asked (what happens to the wall clock), and cold readers took `clocks.active` to mean "the clocks currently in force".
- *A per-call argument only.* Every wait in a session's code repeats it, and a forgotten one silently counts suspended time. The setting reaches helpers and tasks the author didn't write; the argument stays for one-off waits.
- *Mixed clocks as a run-time report only* (round 1 of this design). A shared rate limiter used from an awake loop and a continuous one compiled and then ended the task, and a continuous deadline turned into an awake `timeout=` was a silent bug. The typed reading and deadline-as-timeout rules removed both; Swift's typed instants are the same idea.
- *The name `'active'`* (v5's) was read as CPU time or "while the program runs". `$time.waits = 'awake'` lost one reader, and the setting covers elapsed time, not only waits.

## 3. Test clocks: `$time.clock = time.test_clock()`

```dewy
import time

fetch_with_retry = (url:string):>Page | GaveUp => {
    loop attempt in [0..3) {
        match http.get(url) { page:Page => return page; _ => sleep(1s * 2^attempt) }
    }
    GaveUp
}

$test
gives_up_after_three_tries = () => {
    $time.clock = time.test_clock()
    let start = now
    $expect fetch_with_retry("https://unreachable.test") is? GaveUp
    $expect start.elapsed =? 7s               # 1s + 2s + 4s of backoff, in no real time
}
```

**Rules.**

- **Construction.** `time.test_clock(start=instant"2030-01-01T00:00:00Z" wake_order='oldest_first' seed=0)` gives a `TestClock`. Its wall clock starts at `start`; its continuous and awake clocks start at zero. Its readings are synchronized and exact, so they print without `?` and `strict_today` gives a `Date`. The default start is a fixed instant, never the real time, so a test reads the same every run.
- **Installing it.** `$time.clock = c` makes `now`, `monotonic`, `today`, `sleep`, `within`, timeouts, tickers, deadlines and `time.elapsed` in its scope, its calls and the tasks they start use `c`. The default is `time.system_clock`, which a scope can write to opt back into real time. Placement, inheritance and capture are as in §2. `$time.monotonic = 'awake'` under a test clock selects the test clock's awake count.
- **Time moves only when nothing else can happen.** When every task under the test clock is waiting on that clock (a sleep, timeout, ticker or deadline), waiting on another such task (a channel, lock or join) or finished, the clock jumps to the earliest pending deadline. A wait on the outside world (a file, socket, process, signal or stdin) holds time still, so its timeout never fires early. If every task waits and no deadline is pending, that is the ordinary deadlock report. This is Go's `testing/synctest` rule: since nothing could happen before the next deadline anyway, jumping there changes only how long the test takes.
- **One task at a time, in a fixed order.** Tasks under a test clock run one at a time, each until it waits. Runnable tasks run in the order they were started (`parallel` items in source order, `group.spawn` in call order), and a woken task joins the end. CPU-only `parallel` loops, which never wait, still use every core. So the schedule, and with it every timer-driven interleaving, is the same on every run.
- **Equal deadlines** wake one at a time in `wake_order`: `'oldest_first'` (the wait that started first, the default), `'newest_first'`, or `'shuffled'` with `seed=`, which also shuffles the start order. Each woken task runs until every task waits again before the next wakes, so a race between a reply and a timeout due at the same instant has a chosen, repeatable winner, and eight seeds explore eight orders in no real time. A failing `'shuffled'` test prints its seed.
- **`time.advance(d)`** lets `d` pass. It is `sleep(d)`, except that it wakes last among everything due at its instant, so when it returns every wait due by then has run. It is how a test checks state at a moment ("not yet timed out at 4.999 s"). `time.advance(0s)` lets everything runnable now run until all wait: Go's `synctest.Wait`.
- **`time.simulate_suspend(d)`:** the machine sleeps for `d`. The wall clock and the continuous clock jump by `d`; the awake clock does not. Continuous waits that fell due during it wake at resume, in deadline order, and the call returns after they have run, as `advance` does. A ticker that missed several ticks ticks once, since a tick nobody waited for is dropped.
- **`time.simulate_wall_step(d)`:** the wall clock steps by `d`, forward or back, as an NTP correction or a user's change does. Monotonic clocks don't move, so deadlines are unaffected; `now.nominal` and `today` see the step, and readings after it carry the stepped status.
- **`time.simulate_monotonic_reset()`:** the monotonic clocks lose continuity, as after a snapshot restore: they start a new generation, and readings and deadlines from before can no longer be subtracted (the clock-domain assumption ends the task; under `$time.require_clock_domain` the result is `ClockDiscontinuity`).
- **Grace periods** (cleanup's 100 ms, `protect_from_cancel` limits) count test-clock time.
- **The controller calls read the clock in force.** `advance` and the three `simulate_` calls take `clock:TestClock = $time.clock`, the way `today` takes the zone. Where no test clock is in force they are compile errors ("`time.advance` needs a test clock in force: write `$time.clock = time.test_clock()` at the top of this scope"), so they can never touch a real clock. A helper writes the same parameter, `(clock:time.TestClock = $time.clock)`, checked at each call site, or passes it: `time.advance(1s clock=clock)`.
- **Mixing** a test-clock reading with a system one: a compile error where visible, the clock-domain assumption otherwise (§2).
- **Cost.** Nothing unless named: the test clock and its scheduler hook link only into programs that call `time.test_clock`.

**Considered.**

- *A controller with a `context` member* (`time.with_context(clock.context @job)`), as the implementation round suggested. Every scenario becomes a named function, and readers didn't know what `context` holds (confidence 2/5 each).
- *A handle-only controller* (`let c = time.test_clock()` then `c.advance(5s)`). Installing `c` then needs a block, because a setting that reads a local starts at its line and warns about the call above it. The in-force calls are a line shorter in every test and match tokio's `time::advance` and Vitest's `vi.advanceTimersByTime`; `clock=` keeps the handle form for helpers.
- *Manual advance only* (Jest, swift-clocks). Tests of backoff and polling then spell out every step and break when the code under test changes its delays.
- *Free-running threads under a test clock* (round 1 of this design). "The wait that started first" then depended on which `parallel` item reached its wait first, so the default order was not reproducible, and one dogfood test passed or failed by luck.
- *Names* that failed cold: `reset_clock` ("restore the default"), `suspend_machine` (really suspends), `set_wall` and `step_wall` (feared to set the real clock), `simulate_restore`, `simulate_discontinuity` and `simulate_clock_reset` (vague, or a wall-clock reset). `ties=` read correctly; `wake_order=` says more.

## 4. Fine-tick display (taken)

```dewy
const t = instant"2026-10-24T12:00:00Z"
let quarter = t as Instant<tick=1ns/4>
printl(quarter + 1ns/4)                   # 2026-10-24T12:00:00.00000000025Z
let third = t as Instant<tick=1ns/3>
printl(third + 1ns/3)                     # 2026-10-24T12:00:00Z + 1/3ns
printl(third + 3 * (1ns/3))               # 2026-10-24T12:00:00.000000001Z
to_json(third + 1ns/3)                    # compile error: JSON needs RFC 3339; round it: `.round(1ns)`
```

- **Decimal ticks.** An instant whose tick has a finite decimal expansion (in seconds, a denominator with only the factors 2 and 5) prints exact RFC 3339 everywhere, with as many fraction digits as the value needs. RFC 3339 allows any number.
- **Other ticks print exactly.** Printing, interpolation and `as string` on an instant whose tick has none (`1ns/3`, `1s/7`) give RFC 3339 of the whole nanoseconds, rounded down, then the remainder as an exact time quantity, `… + 1/3ns`; a value on the nanosecond grid prints as plain RFC 3339. So a generic logger, or a debug print of a record with such a field, works for every tick. Cold readers read the spaced form as "an instant plus a third of a nanosecond" (3/3); `Z+1/3ns` unspaced was read once as a zone offset.
- **What promises RFC 3339 to another program** (JSON and other codecs) takes only decimal ticks: a non-decimal tick there is a compile error, decided by the type, with the fix-it `.round(1ns)` (D31 Q7's provisional spelling; today `quantize(t tick=1ns rounding='nearest_even')`). `t.round(step)` with a whole-nanosecond step gives a plain `Instant`.
- **Durations** are unaffected: `1/3ns` is already an exact quantity.
- **Taken under the two tests:** nanosecond instants (the common path) are untouched, nothing is lost or guessed, and a codec that needs RFC 3339 is one call away. Considered: a compile error for every display of a non-decimal tick (the implementation round's suggestion; it made a generic logger and a debug print of a record fail to compile), and silent rounding (loses information without a word).

## 5. Prior art

| | Awake-only time | Test clock | Moves on its own | Test chooses equal-deadline order |
|---|---|---|---|---|
| Python | Whatever the platform's monotonic clock does; not selectable | freezegun, time-machine (wall time only); trio `MockClock` | trio `autojump_threshold` | No |
| Go | Whatever the runtime's clock does; not selectable | `testing/synctest` bubbles | Yes: when every goroutine is durably blocked | No |
| Rust | `Instant` is platform-dependent; crates for boot time | `tokio::time::pause` / `advance` | Yes, when the runtime is idle | No |
| TypeScript | `performance.now`, unspecified during sleep | Jest/Vitest fake timers | No (`runAllTimers`, `advanceTimersByTime`) | No |
| Swift | `SuspendingClock` vs `ContinuousClock`, typed instants, passed explicitly | swift-clocks `TestClock`, injected by parameter | No (`advance`, `run`) | No |

Dewy's choice is explicit and the same on every platform, typed like Swift's, reaches code it doesn't own without parameters (Swift needs a clock parameter on every function), jumps on its own as Go and tokio do, and is the only one where a test chooses the order of equal deadlines.

## 6. Cold reads

Six rounds, three fresh readers each (Sonnet, Haiku, Fable), given the lines shuffled with a short context and asked what each does, whether it is safer, and their confidence.

| Name | Readers right | Kept |
|---|---|---|
| `$time.monotonic = 'awake'`, `'continuous'` | 3/3 | yes |
| `now(monotonic='continuous')`, `sleep(30s monotonic='awake')`, `ClockReading<monotonic='awake'>` | 3/3 | yes |
| `r.elapsed`, `d.remaining` | 3/3 | yes |
| `c.receive(timeout=paid_until)`, `within(paid_until @fetch)` (a deadline) | 3/3, one finding `timeout=` taking a point odd | yes |
| `$time.clock = time.test_clock()`, `start=`, `TestClock` | 3/3 | yes |
| `wake_order='oldest_first' \| 'newest_first' \| 'shuffled'`, `seed=` | 3/3 | yes |
| `time.advance(5s)`, `time.simulate_suspend(1hour)` | 3/3 | yes |
| `time.simulate_wall_step(-1hour)` | 3/3 | yes |
| `time.simulate_monotonic_reset()` | 3/3 | yes |
| `time.system_clock` | 3/3 | yes |
| Display `2026-10-24T12:00:00Z + 1/3ns` | 3/3 | yes |
| `$time.monotonic = 'active'` | 1/3 (CPU time, running time) | no |
| `$time.waits = 'awake'` | 2/3 | no |
| `time.with_clocks(clocks.active @job)` | 0/3 ("the clocks currently in force") | no |
| `time.with_context(clock.context @job)` | vague, 2/5 each | no |
| `time.reset_clock()` | 0/3 ("restore the default") | no |
| `time.simulate_clock_reset()` | 0/3 (a wall-clock reset) | no |
| `time.suspend_machine(1hour)` | 1/3 (really suspends) | no |
| `time.set_wall(…)`, `time.step_wall(…)` | 3/3, but two feared the real clock | no |
| `time.simulate_restore()`, `time.simulate_discontinuity()` | 0/3, vague | no |
| Display `…Z+1/3ns` unspaced; `….000000001Z - 2/3ns` | 2/3; 1/3 | no |

## 7. Dogfood

One agent wrote 34 programs in [clocks-programs-r1/](clocks-programs-r1/) (13 awake-time, 14 test-clock, 7 display: idle locks, play-time, watchdogs, rate limiters, a kiosk session, a pomodoro timer, a backup scheduler, retry with backoff and jitter, a circuit breaker, a token bucket, cache TTLs, debounce, leases, a daily job across a DST change, timeouts, equal deadlines, ticker flushes, PTP and JSON logs), graded each 1–5 on obvious, discoverable, concise, safe by default and complete against the best of Python, Go, Rust, TypeScript and Swift with their usual test tooling (freezegun, trio `MockClock`, Go `testing/synctest`, `tokio::time::pause`, Vitest fake timers, swift-clocks), then regraded after each revision. The programs were read and traced against the design, not compiled.

| Proposal | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| Awake time | 3.85 | 4.80 | 4.94 |
| Test clocks | 4.45 | 4.79 | 4.96 |
| Display | 4.00 | 4.66 | 4.97 |

What each revision took from the grades:

- **Round 2:** typed readings (a shared limiter mixed clocks and failed at run time); `monotonic=` on every clock call (a helper per clock); deadlines as timeouts (a continuous deadline turned into an awake timeout was a silent bug); one task at a time under a test clock (the default wake order depended on thread timing); capture only where a setting is written (a module-level `@loader` pinned the system clock in tests); the suspend, ticker, grace and `advance(0s)` rules; exact printing of non-decimal ticks (a generic logger and a record's debug print didn't compile).
- **Round 3:** `r.elapsed` and `d.remaining` (a union reading needed a five-line `match` to measure); compile errors for visible cross-clock boundaries (a module-level reading in a test died at run time); the generic-record pattern written down.

**Grades still under 5 after round 3,** all inherent:

- A library that defaults to awake overrides a caller's `$time.monotonic` silently (`a11_idle_library.dewy:10`). That is the price of having no "was it set" query; the default is in the signature.
- A captured clock can't be seen at the call (`a12_captured_job.dewy:28`). Dynamic scope is the design; hover on a function value should show its captured clock and monotonic setting.
- Exact expectations at a shared instant take a scheduler trace in your head (`b12_ticker_flush.dewy:39`). One task at a time makes the trace derivable, which is the best exactness allows.
- A test helper passes `clock=clock` on to `time.advance` (`b13_helpers_and_restore.dewy:18`), since its body can't prove its caller's clock.
- A printed `… + 1/3ns` can reach a log another program parses as RFC 3339 (`c04_generic_logger.dewy:7`). The alternative, refusing to print, failed worse; an RFC 3339 accessor for log libraries belongs to the format design (§8).

## 8. Outside this design (found while dogfooding)

- **A wall-clock wait.** Nothing waits until a wall instant (`sleep_until(instant)`), so a daily 09:00 job polls or drifts after a wall step. time.md and v5 §6 describe arming wall appointments but spell no call. The test clock's `simulate_wall_step` is what exposed it.
- **A per-test time limit** (`$test(time_limit=20s)` on real awake time) and a report naming the outside wait that holds a test clock still; a failed `$expect` inside a `parallel` item should cancel the test's other tasks rather than leave a deadlock report.
- **Codecs and formats:** a rounding option on JSON export, a digit cap for decimal ticks (eleven fraction digits are valid RFC 3339 but lose precision in many parsers), fixed-digit `format` patterns (D37), parsing text back onto a tick, and `5/4ns` printing as `1.25ns`.
- **The public status member** of a reading (to assert "stepped" in a test).
- **User clocks:** a pausable or scaled clock that can drive `sleep` and `ticker`, for games and media players (v5's "game time" note).
- **Small test conveniences:** `$test(seeds=8)` in place of listing seeds as cases.
