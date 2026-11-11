# Dogfooding D4, D10, D22, D26 and D27 (2026-11-07)

Fourteen programs a working programmer would write, using the proposed spellings, graded on five axes. I compiled them on master (d0f9714ef) where I could, and stubbed only what the designs add. Programs: `~/dev/tmp/dogfood-1107/a/` (`*_today.dewy` are the compiled variants; `probe/` holds one-line checks).

## Status

| # | Program | Status |
|---|---|---|
| 01 | Sum numbers from stdin and a file | **Compiled, ran** |
| 02 | Folder of CSVs → summary file | **Compiled, ran** (4 workarounds) |
| 03 | Fetch many URLs, 8 at a time, timeouts | Paper-only (no HTTP client, no `$parallel.*`) |
| 04 | Worker pool over a job queue | Paper-only |
| 05 | Collector loop with `select` | Paper-only |
| 06 | Pipeline over 50M lines | **Partly compiled** (`06_pipeline_today` ran with n=200k) |
| 07 | Cancelable search, Ctrl-C | Paper-only |
| 08 | Game frame, particles + bodies | **Partly compiled** (AoS step compiles; SoA step rejected) |
| 09 | Reset token + level seed | **Compiled, ran** (with today's `crypto.random_bytes`) |
| 10 | Bisection, Welford, float constants | **Partly compiled** (blocked by `$finite_floats` obligations) |
| 11 | `$bulletproof` settings loader | Paper-only (probe: `printl(1)` fails) |
| 12 | Single-core batch job | Paper-only |
| 13 | Block-form asset loading + autosave task | Paper-only |
| 14 | Interactive prompt with retries | **Compiled, ran** |

## Grades

O = obvious, D = discoverable, C = concise, S = safe by default, X = complete.

| # | O | D | C | S | X | Weakest point |
|---|---|---|---|---|---|---|
| 01 | 4 | 4 | 4 | 3 | 3 | `to_float("nan")` succeeds; `error: FileNotFound` gives no path |
| 02 | 3 | 4 | 3 | 4 | 3 | `endswith`, `make_dirs` returns `true`, a false confinement warning |
| 03 | 4 | 3 | 4 | 4 | 2 | No HTTP client; the reach of a scoped tag is unclear |
| 04 | 3 | 4 | 4 | 4 | 4 | Where `or_throw` binds after a loop |
| 05 | 4 | 4 | 3 | 3 | 3 | `<Canceled>` arm every time; idle timeout only, no ticker |
| 06 | 4 | 3 | 3 | 4 | 2 | `?? void` can't count what it dropped; no parallel group or count |
| 07 | 3 | 3 | 4 | 3 | 2 | The first Ctrl-C looks ignored; saving after cancel |
| 08 | 4 | 3 | 4 | 4 | 2 | `parallel i in [0..n) { xs[i] … }` rejected |
| 09 | 4 | 4 | 3 | 3 | 3 | Secret `=?` takes variable time; no URL-safe token helper |
| 10 | 3 | 3 | 2 | 5 | 3 | `let x = 1.5` is rational; field reads under `$finite_floats` |
| 11 | 3 | 2 | 3 | 5 | 2 | `printl(1)` is an error; bundle not restated with tested names |
| 12 | 4 | 3 | 5 | 4 | 3 | `max_cores` vs `max_threads` vs `$parallel.threads` |
| 13 | 3 | 4 | 5 | 4 | 3 | Block `let`s leak out of braces; `group.spawn` returns nothing |
| 14 | 4 | 4 | 5 | 5 | 4 | `return printl(...)` accepted in one function, rejected in another |

No program scored all 5s.

---

## 01: numbers from input and a file (compiled, ran)

```dewy
let v = to_float(text) ?? { t.bad.push(text); return }
if not is_finite(v) { t.bad.push(text); return }
...
let text = p(argv[1]).read_text or_throw
```

- **`to_float("nan")`, `"inf"` and `"1e400"` all succeed.** With no `is_finite` line, one stray "nan" in the file silently turns the total into NaN. I only caught it because I knew to look. *(S)*
  - Fix: `to_float` rejects `nan`, `inf` and overflow by default, and an argument turns them back on. Python is no better here; Go's `ParseFloat` returns `ErrRange` on overflow.
- **`error: FileNotFound`, exit 2, with no path.** Python prints the file name; Go's `*PathError` carries it. *(X)*
  - Fix: file errors carry `path`, and the report from `main` prints it.
- **Two spellings of end-of-input.** `read_line` gives `none`, but `input` gives `EndOfInput`, so a program that uses both handles end of input two ways. *(O)*
  - Fix: `read_line` gives `EndOfInput` too. `if line is? exception break` still works.
- **There's no stdin iterator.** Python has `for line in sys.stdin`; here it takes a `loop true` with a `break`. *(X)*
  - Fix: `loop line in stdin.lines`, with the same failure rules as a channel loop (C7).
- **Good:** the `?? { …; return }` block fallback compiled and reads naturally.

## 02: folder CLI (compiled, ran)

```dewy
out.make_dirs or_throw;                          # gives `true`, so `;` is required here
loop name in (input.list or_throw) {             # parens needed
    if not name.endswith(".csv") continue        # `ends_with` is rejected
    lines.push(summarize(p"{input}/{name}") or_throw)
}
report.write_text("{lines.join("\n")}\n") or_throw;
```

- **`name.ends_with(".csv")` is rejected with "write `name.endswith(...)`".** Every other Dewy name is snake_case (`with_suffix`, `read_text`, `max_exact_int`), and Rust, Swift and TS users all type `ends_with` or `endsWith`. Only Python has `endswith`. *(O)*
  - Fix: `starts_with` and `ends_with`.
- **`make_dirs` gives `true` and `write_text` gives a byte count**, so either one as a statement before a `return` forces `;` ("this expresses a value before the function's end"). This is the `window`-returns-`void` slip in reverse: a meaningless result where a useful one belongs. *(C)*
  - Fix: `make_dirs` and `mkdir` return the `Path`, so `let out = p(argv[2]).make_dirs or_throw` works. `write_text` returns `void`, since `.size` gives the count when it's wanted.
- **`loop name in input.list or_throw {` fails with "a loop used as a value".** C7's trailing `loop … { } or_throw` made `or_throw` before `{` ambiguous, and everyone will type this form. *(O)*
  - Fix: before `{`, `or_throw` binds to the iterable; failing that, the error offers the parenthesized fix-it.
- **Joining names from `input.list` warns** "`file` may escape its base". Under D10 Q3 (a) this, the most common safe folder loop, becomes a **compile error**. The fix-it also names `root.confine(file)`, but there is no `root` here; the base is `input`. *(D, S)*
  - Fix: `list` yields refined components (one part, no `/`, never `.` or `..`), so `p"{dir}/{name}"` is a `SafePath`; also add `dir.entries`, giving `SafePath`s. The fix-it should name the actual base expression.
- **`+` on text is rejected.** The error is good, but Python, TS, Swift, Go and Java users all write `a + "\n"`. That's a deliberate decision; I note it only because it came up in the first 30 lines.
- **There's no `join`/`/` on paths.** Interpolation works, but pathlib and Rust users will look for `dir / name` or `dir.join(name)`. A hover on `Path` saying "join by interpolation: `p"{dir}/{name}"`" would cover it.

## 03: fetch URLs (paper)

```dewy
$parallel.max_concurrent = 8
fetch_all = (urls:array<string>) => {
    [parallel u in urls { let r = fetch_one(u); match r {...}; r }]
}
let results = within(60s @fetch_all(urls)) or_throw
```

- **The library has no HTTP client.** `net` is raw TCP. "Fetch many URLs" is the canonical concurrency demo, and every comparison language ships one (Go `net/http`, Python `urllib`, JS `fetch`). *(X)*
  - Fix: `http.get(url)` giving a response with `status` and `body`, with `NetError | Timeout | Canceled`.
- **`$parallel.max_concurrent = 8` covers the whole body,** including a `parallel` inside `fetch_one` if there is one. Is that lexical or dynamic? To limit one construct you wrap it in a block. *(D)*
  - Fix: allow the tag on the line above a single construct, as function contracts already work, and have hover say which constructs it reaches.
- **A failed item's error doesn't say which URL failed.** You have to keep `u` beside it. That's fine in the loop form, but awkward after collecting. *(X, nice to have)*
- **Better than the comparisons:** one line instead of Go's `errgroup.SetLimit`, Python's `Semaphore`, or JS's `p-limit`. Results stay in input order, and a batch deadline cancels the in-flight fetches.

## 04: worker pool (paper)

```dewy
{ loop i in [0..1000) jobs.send(Job[i "doc/{i}.txt"]) or_throw; jobs.close }
{ parallel w in [0..4) { let conn = connect_db(...) or_throw; loop job in jobs {...} or_throw }; results.close }
loop d in results { total += d.words } or_throw
```

- **(A) `loop i in r jobs.send(x) or_throw`**: does `or_throw` go with the send or the loop? C7 puts it after the loop. *(O)*
  - Fix: a brace-less loop body takes the whole rest of the line, and the C7 form requires braces. State this in D4.
- **(B) Every channel loop ends in `} or_throw`.** What happens if I forget it? The loop's `void | Canceled` would join the function's value silently. *(S)*
  - Fix: a discarded `Canceled` from a loop is an error, with the `or_throw` fix-it.
- **(C) Where does `$parallel.max_concurrent` go inside a block?** Does a tag statement count as an item? Same fix as in 03.
- **`total.add(j*2);` needs `;`, and atomic `add` panics on overflow today**, so it needs `$runtime_checks`. Batch 2 trusts a 64-bit counter growing by a bounded step. *(C, S)*
  - Fix: atomics follow the same counter rule.
- **Good:** the close-races-the-sends error with "put item 2 in item 1's `{ }`" is better than Go's runtime panic on a closed channel. Per-worker state (`conn`) fits naturally in `parallel w in [0..4)`.

## 05: `select` server loop (paper)

```dewy
match select(command=@commands.receive  reading=@data.receive  timeout=1s) {
    [reading:Reading] => ...
    [command:'flush'] => flush(@buffer out) or_throw
    <Timeout> => flush(@buffer out) or_throw
    <Canceled> => return flush(@buffer out)
}
```

- **`timeout=1s` restarts on every call**, so under steady traffic the timed flush never happens. Go programs use a `Ticker` for this. *(X)*
  - Fix: let `timeout=` also take a deadline (`now + 1s` is already a monotonic deadline), and add `ticker(1s)`, whose `@tick.receive` goes in `select`.
- **Every `select` needs a `<Canceled>` arm**, and plain `or_throw` can't be used because `Timeout` is an exception too. Today the fix is `match select(...) ??<Canceled> return Canceled {`, which is legal but ugly. *(C)*
  - Fix: either `or_throw<Canceled>` (new syntax, mirroring `??<E>`), or document the `??<Canceled>` form in the D4 example.
- **Saving the buffer on cancel fails:** cancellation is level-triggered, so `flush`'s file write gives `Canceled` inside that arm. Data is lost unless the save is in a `defer`. *(S)* See 07.
- **Going from one channel to two changes every arm's shape** (`r:Reading` becomes `[reading:Reading]`, as in 05b). *(O)*
  - Fix: allow names in the one-wait form, so starting named costs nothing, and the overlap error suggests them.
- **`[command:'flush']`**, a literal pattern inside a tagged record, must work. Unions of anonymous records don't match yet (v3 §6, `s2.dewy`).
- **Good:** handles plus names read well, `Sent` is clear, and fair ties are the right default.

## 06: pipeline (partly compiled)

```dewy
let entries = [parallel i in [0..n) parse(synth(i)) ?? void]
let bad = n - entries.length                     # the only way to count them
let total_bytes = sum([parallel e in entries e.bytes])
```

- **Dropping failures loses their count and their reasons**, and every real pipeline reports "N bad lines". *(X)*
  - Fix: `let [ok bad] = results.partition_errors` (spelling for review), or document keeping the per-item values and filtering twice.
- **Each reduction builds a 50M-element array**, unless `sum([parallel …])` is fused. Rayon streams `par_iter().map().sum()`. *(X)*
  - Fix: guarantee fusion when a collector is consumed only by a reduction (an internal matter), and say so in hover.
- **`to_int` gives arbitrary-precision `int`, so an `int64` field fails** ("cannot prove `bytes <=? 9223372036854775807`"). *(C)*
  - Fix: a fixed-width parse whose out-of-range result is a value, offered by the fix-it.
- **`by_status.items` fails with an error that suggests `m["items"]`.** Python users will type `.items`. *(D)*
  - Fix: the error should say `loop [k v] in by_status`.
- **There's no parallel `group_by` or `count_by`.** The sequential `group_by` works. *(Nice to have)*

## 07: cancelable search, Ctrl-C (paper)

```dewy
if start % 100_000 =? 0 check_cancel or_throw
defer save(best)
match within(10min @search(@best 1_000_000_000)) { <Timeout> => ... <Canceled> => ... }
```

- **`10min` fails with "'min' needs arguments".** `min` the function wins over the unit. *(D)*
  - Fix: the error suggests `10minute`.
- **For a compute-only program, the first Ctrl-C appears to do nothing**, because compute runs to completion by default. Users will think the program hung and press it again. Python interrupts at once. *(O, S)*
  - Fix: on the first Ctrl-C, print to stderr "canceling at the next `check_cancel`; Ctrl-C again to stop now".
- **After `<Canceled>` in `main`, every later file operation gives `Canceled`.** Saving progress must go in `defer`, which has a 100 ms grace, too short to write a checkpoint. v3 §5 defers Zig's `CancelProtection` "until a program needs it", and this program needs it. *(X, S)*
  - Fix: a shielded block or a program-wide grace setting (new spelling, for review).
- **The exit code after a handled Ctrl-C isn't specified.** The shell convention is 130, with no `error: Canceled` report when the user asked to stop.
- **Good:** level-triggered cancellation plus `check_cancel or_throw` is cleaner than Go's `ctx.Done()` plumbing, the `AtomicBool` most Rust programs pass around, or Python's `KeyboardInterrupt` landing anywhere.
- **`check_cancel` without `or_throw` must be an error** naming the fix. Today a bare value statement does give the "expresses a value" error, so it's probably covered; state it.

## 08: game frame (partly compiled)

```dewy
parallel i in [0..s.x.length) { s.x[i] += s.v[i] * dt }      # rejected
```

- **The indexed parallel loop is rejected.** The index isn't even proven `>= 0` (the sequential `loop` proves the same range fine), and indexed writes are rejected outright. This is the dominant game and HPC idiom: Unity's `IJobParallelFor`, OpenMP, Rayon's `(0..n).into_par_iter()`. With `$memory.layout = 'soa'` on offer, it's the loop SoA code needs. *(X)*
  - Fix: carry the range facts into `parallel` bodies, and accept writes to `xs[i]` where `i` is the loop's own index.
- **`step(@ps dt)` makes `ps[0]` unprovable afterwards** ("ps.length may have changed"), though `step` only writes elements through `parallel @p`. *(C)*
  - Fix: infer "doesn't change length" for a function that only writes elements.
- **`let xs = [1.0 2.0]` is `array<rational>`**, so `par_step(@xs …)` fails with "`@` parameters need an exact match". *(D)*
  - Fix: the error says the literals are exact and offers `let xs:array<float64> = …`.
- **There's no float in a range.** `random()` is `[0, 1)` only, so `random(-50.0 50.0)` doesn't exist; Python has `random.uniform(a, b)`. `random_int(lo hi)` already contradicts D15d ("anything taking an interval uses range syntax"). *(X)*
  - Fix: `random([lo..hi))` for ints and floats alike.
- **Good:** `parallel { particles; bodies; heat }` with `& no blocks` reads as what it is, and `.copy` makes the snapshot cost visible.

## 09: tokens and seeds (compiled with today's names)

- **Secret comparison takes variable time** (LANGUAGE.md: "constant-time comparison is planned"). Checking a reset token with `=?` is a timing leak the user must know to avoid. *(S)*
  - Fix: make `=?` on `secret<T>` constant-time before D10's random names ship.
- **Name swap trap:** today `crypto.random_bytes` is the secure one; under D10 a bare `random_bytes` is the insecure one. Code written against the old name, or tutorials trained on it, will silently lose security. *(S)*
  - Fix: remove `crypto.random_bytes` in the same commit, so old code fails to compile instead of losing security.
- **There's no URL-safe token.** `base64_encode` gives `+/=`, with no hex or base64url. Python has `secrets.token_urlsafe(32)` and Go has `rand.Text()`. *(X)*
  - Fix: `secure_token(32)` giving `secret<string>`, URL-safe (spelling for review).
- **Secure bytes aren't secret by default.** Fix: `secure_random_bytes` returns `secret<array<uint8>>`, or the token helper does. *(S)*
- **Seed:** `rng(random_int(0 int64.max))` works but is clumsy. `seed_random(n)` and `rng(seed)` are two ways to do it. *(C)*
  - Fix: `rng` with no argument draws its own seed and exposes `.seed`, so the game can show it.

## 10: numeric (partly compiled)

- **`let x = 1.5; x.next_up` fails with "rational has no field 'next_up' (did you mean 'next_u64'?)".** Decimal literals are exact by design, but the error should say so. *(D)*
  - Fix: "`x` is an exact rational because 1.5 is exact; write `let x:float64 = 1.5`".
- **Under `$finite_floats`, every field read needs its own guard.** In a Welford record, `s.mean` and `s.m2` each need `.is_finite`, then `x - mean` "may overflow" and needs a range guard. Welford in a record took 3 extra lines and still doesn't compile. *(C)*
  - Fix: a finiteness refinement on fields (`m2:float64<finite>`, spelling for review), or treat fields of a record declared in the scope as covered.
- **Good, and the docs are stale:** `x.is_finite` already works as a guard (ran), while round2 §6 says it isn't recognized. D10's example should use it instead of `float64.most_negative <=? x <=? float64.max same(x)`, which no newcomer will write.
- **`float64.most_negative` next to `int64.min` breaks generic `T.min`.** Fix: keep `.min` as a compile error whose fix-it names `most_negative` and `smallest_normal`, so people who type the C or Rust name get led to the right one. *(D)*
- **There's no `is_close`/`approx_equal`** (Python `math.isclose`). *(X, should)*
- **Good:** `next_down` is there beside `next_up`, and `max_exact_int` was read correctly.

## 11: `$bulletproof` module (paper)

- **`$bulletproof` then `main = () => printl(1)` is an error**: "allocation exceeds the contract (its row excludes it)". The strict lane can't print a number. *(X, D)*
  - Fix: printing a scalar or a literal doesn't allocate, and the error names the fix (`& allocates` on `main`).
- **D10 doesn't restate the bundle with the tested names.** Round 2's bundle lists `$no_nan_or_inf`, `$no_unconfined_paths`, `$explicit_local_panics`, `$prove_size_bounds`, `$prove_library` and `$explicit_graphics_failure`. Batch 3 removed the last one, and the tested names differ for all the others. *(D)*
- **`$prove_no_counter_overflow` covers only counters.** Round 2's `$prove_size_bounds` also covered array sizes and parallel range sizes, which batch 2 assigned to `$no_assumed_bounds`. Now no tag clearly owns ranges of 2^63 or more.
- **Library errors under `$no_trusted_library` can't be fixed by the user.** Fix: hover marks which library functions are clean, plus a `dewy check` listing. *(D)*

## 12: single core (paper)

- **Three unit names for one resource:**
  - `$program.max_cores` (D4 and names.md);
  - `$program.max_threads` (names-round1.md, 3/3);
  - scoped `$parallel.threads`.

  Fix: `$program.max_threads` with `$parallel.threads`, keeping "cores" for pinning (`$placement.cores = [0 1]`).
- **`$parallel.off` overlaps with `max_cores = 1`**, and it's rejected exactly where it would help debugging (items that wait). Two ways to do almost one thing. *(O)*
- **`512MB`**: decimal or binary? Fix: accept `MiB`, and document `MB` as 10^6.
- **The program can't read its core budget** to size a pool. Go has `runtime.NumCPU` and Rust `available_parallelism`. *(X)*
- **`DEWY_THREADS` (env) still exists beside the tag.** Operators do need a run-time cap (`GOMAXPROCS`, `RAYON_NUM_THREADS`). Keep it as a cap below the tag, documented, so there's one rule.

## 13: block-form loading and tasks (paper)

- **`let`s inside `parallel { }` are visible after the closing brace.** Nowhere else in Dewy, or in any comparison language, do braces leak bindings, and a nested `{ }` item presumably doesn't leak. *(O)*
  - Fix: keep it (it's what makes the block useful), but flag it in D4 as a decision. Offer `let [map sounds] = parallel { … }` as the alternative, since the block already gives its values in order.
- **`group.spawn(@autosave)` returns nothing**, so you can stop the music task but not autosave only by giving each its own group. This is the `window`-returns-`void` class. *(X)*
  - Fix: `spawn` returns a handle that can only `.cancel` and be queried (no join, no move out of the group), so the lifetime guarantee holds.
- **`spawn` means two things:** a task in a group, and `spawn(program args)` → `Child` for processes.
  - Fix: rename the process one (`start(program args)`) now that the task keyword is gone.
- **D26 contradicts D4.** In v3's own examples, block items write enclosing locals (`loop n in numbers { total += n }`), ordered by waits. D26 makes the same write from a task a compile error, because tasks snapshot. The rule must be stated per construct: block items share and are ordered, loop bodies are race-checked, and `group.spawn` lambdas snapshot. D26's and D27's examples use `concurrent`/`spawn`, which batch 3 removed.
- **Case 1 (`printl"done"` printing first)** surprised me even though I'd read about it. Hover only helps when you look. *(O)*
  - Fix: a note (not an error) when the last item is a `printl` with no data link.

## 14: interactive prompt (compiled, ran)

- **`return printl(...)`**: accepted in 01's `main`, rejected in 14's ("this function does not return a value"). The two differ only in an earlier `?? return`. *(O)*
- **At end of input the prompt is left without a line break.** *(Nice to have)*
- **Good:** `input_int` retries with a clear message, and `?? return` gives a clean exit at end of input. This is better than Python's `int(input())` crash.

---

## Cross-cutting slip classes

- **A handle replaced by nothing or `true`:** `group.spawn`, `make_dirs`/`mkdir`, and `write_text`'s count, which forces `;`.
- **Missing companions:** `random_float`, `$allow_unproven_narrowing`, snake_case `ends_with`, a `select` ticker, stdin lines, a fixed-width parse.
- **Two ways to do one thing:**
  - `none` vs `EndOfInput` at end of input;
  - `seed_random` vs `rng`;
  - `$parallel.off` vs `max_cores = 1`;
  - `DEWY_THREADS` vs the tag;
  - `strict_today` vs `$time.handle_uncertain_today`;
  - `$panic_on_unproven` (D11c) vs `$allow_unproven`.
- **Records disagree:**
  - `max_cores`/`max_threads`;
  - `$memory`/`$storage.layout`;
  - `grouping=`/`order=`;
  - `Iterable<T>` vs David's `iterable<T>` (discussion_points.md:3749).
- **Collisions with common variable names:**
  - `tasks`, the commonest list name in a to-do program;
  - `window`, as in `let window = window(...) or_throw`;
  - `p(text)`, where a `p` loop variable turns the call into multiplication (today it warns);
  - `min` vs the `10min` unit;
  - `args`.

  Fix: `path(text)` for the call, and test `tasks` and `window` cold beside a same-named variable.
- **Tag verbs outside the grammar:** `$time.handle_…` and `$count_…`. `$count_local_asserts_as_panics` was read correctly only "roughly, 2/3", below the bar.

## Ranked fixes

**Must fix before David decides:**

1. **D26 vs D4:** state the write-sharing rule per construct (block item, loop body, `group.spawn` lambda), and restate D26 and D27 in v3 terms. D27 is moot for block items, since `or_throw` already leaves the function there.
2. **`$program.max_cores`/`max_threads`/`$parallel.threads`:** pick one unit. Also reconcile `$memory`/`$storage` and `grouping`/`order` across D4, names.md and v3.
3. **`group.spawn` returns a cancel-only handle**, so a single background task can be stopped.
4. **Ctrl-C:** feedback on the first press, exit code 130, and a way to save after cancel (a shielded block or a grace setting). The current flag is incomplete.
5. **D10 restates the `$bulletproof` bundle with the tested names**, says which tag owns range and size bounds, and swaps `$panic_on_unproven` to `$allow_unproven` in D11c.
6. **D10 Q3 (a) only after** `list` names are proven components and the fix-it names the real base. Otherwise the commonest safe folder loop becomes a compile error.
7. **Constant-time `=?` on secrets, and remove `crypto.random_bytes`,** before the random-name swap ships.
8. **`parallel i in [0..n) { xs[i] … }`:** carry the range facts and accept own-index writes. D4 sells `$memory.layout = 'soa'`, which needs this.

**Should fix:**

9. `select`: a deadline or `ticker`; a documented answer to the `<Canceled>` arm; names allowed in the one-wait form.
10. Where `or_throw` binds after `loop x in f() or_throw {`, and the brace-less C7 form. A forgotten `} or_throw` on a channel loop is an error.
11. `to_float` rejects `nan`/`inf`/overflow by default; file errors carry their path.
12. `make_dirs`/`mkdir` return the `Path`; `write_text` returns `void`.
13. `starts_with`/`ends_with`.
14. `random([lo..hi))` for ints and floats, per D15d.
15. A finiteness refinement on fields, so `$finite_floats` is usable on records.
16. Rational-literal errors name `:float64`; `float64.min` gets a fix-it naming both meanings.
17. A scoped tag can sit on the line above one construct; hover shows its reach.
18. An HTTP client.
19. `partition` of results; guaranteed fusion of `sum([parallel …])`.
20. `$allow_unproven_narrowing`; a replacement for `$count_local_asserts_as_panics`, which scored only 2/3.
21. `printl` of scalars inside `$bulletproof`.

**Nice to have:**

22. `secure_token(n)` → `secret<string>`, URL-safe; `rng` with no argument exposing `.seed`.
23. `stdin.lines`; `read_line` gives `EndOfInput`.
24. `is_close`; parallel `group_by`/`count_by`; retry helpers.
25. Rename the process `spawn` to `start`; `path(text)` for `p(text)`; `10min` suggests `10minute`; `.items` on a dict suggests `loop [k v] in d`.
26. Reading the core budget from the program; `MiB`.

## Readiness of the open items

| Item | Verdict | What's missing |
|---|---|---|
| D4.1 `check_cancel` | **Ready** | State that a bare `check_cancel` is an error naming `or_throw` |
| D4.2 `select(...)` | Another iteration | Deadline/ticker, the `<Canceled>` arm, shape change, literal patterns |
| D4.3 metatags | Another iteration | cores vs threads; `$memory` vs `$storage`; `$parallel.off` overlap; per-construct placement |
| D4.4 `sum(xs grouping='tree')` | **Ready** | Fix v3's text, which still says `order=` |
| D4.5 `Iterable<T>` | Nearly ready | Case: David's notes say `iterable<T>` |
| D4 flagged: Ctrl-C | Another iteration | Must-fix 4 |
| D4 flagged: block values in order | Ready, but add the `let` leak as a flagged item | |
| D10 Q1 tag names | Another iteration | Missing narrowing companion; 2/3 name; new verbs; bundle; D11c's old name |
| D10 Q1 float constants | **Ready** | Add a `.min` fix-it; use `x.is_finite` in the example |
| D10 Q1 random names | Ready with conditions | Must-fix 7 |
| D10 Q3 | (a) is right; not ready | Must-fix 6 |
| D22 delete `$parallel_safe` | **Ready (all 5s)** | Make sure printed signatures and docs show the inferred requirement, not just hover |
| D26 | Another iteration | Contradicts the v3 block rule; examples use removed syntax |
| D27 | Close as moot, or restate | `spawn { }` is gone; `group.spawn(() => …)` lambdas already infer |
