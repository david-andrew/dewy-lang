# Decisions waiting on David

- **Only open items.** Once you answer one, it moves to [decisions.md](decisions.md), with what was considered and why, and is removed from here.
- **Answering:** reply per item, e.g. "D6 a, D9 yes, C3 a". Anything you skip stays pending. "Take the recs for the rest" is a valid answer.
- **Order:** priority order. P1 items block work that is happening now.
- **Example conventions:**
  - Arguments are space-separated, `=?` is equality, and zero-argument calls drop their parentheses.
  - `or_throw` forwards an error to the caller, `??` substitutes a default for any error or `none`, and `??<E>` does so only for error type `E`.
  - `@f` is a handle to function `f`, and `$name` is a metatag.

---

## P1: blocking current work

### D4. One unified `parallel` surface
- **What this is:** the cohesive redesign you asked for. It was drafted by Opus, checked for soundness by Sol, and revised after a Grok review. Full proposal with more examples: `docs/design/proposals/concurrency/unified/proposal-v2.md` (about 3,000 words).
- **The model in 5 bullets:**
  - **One keyword.** `parallel` means "these items start together, and the construct ends when they all end". It has three shapes:
    - loop: `parallel x in xs { … }`;
    - comprehension: `[parallel x in xs f(x)]`;
    - block: `parallel { let a = f()  { … } }`.
  - **Waiting is allowed.** Items may wait, even on each other. The compiler picks how to run them from what the body may wait on:
    - a chunked CPU pool;
    - a bounded window of tasks;
    - one task per item.
  - **No tags.** Editor hover and `explain` show which strategy was chosen.
  - **Removed:** the `concurrent` and `spawn` keywords, `concurrent g {…}`, `spawn(g)`, `cancel(g)`, and `parallel_map`, `parallel_range` and `parallel_update`.
  - **Added, as library calls with no new grammar:**
    - `tasks(body)` for work that outlives a function;
    - `select(ops)` + `match`;
    - looping over channels.
  - **One failure rule.** Errors stay per-item values. `or_throw` inside an item cancels the siblings and leaves the function with that error.
- **Answer the big-picture questions B1–B8 first.** They come from a step-back round (Astra, Sol and Grok on your 80/20 framing), synthesized in `docs/design/proposals/concurrency/big-picture/synthesis.md`, which has the ladder, the prior-art table and examples. B2 settles C1. C4 and C7 get revised after B.

- **B1. Do pure bulk operations go wide automatically, with no keyword?**
  - Rec: yes.
  - All three reviewers agree. It's the biggest lever for lazy programmers.
- **B2. May `parallel` items wait on *each other*?**

  ```dewy
  let ch = channel<int>(1)
  step = (i:int) => if i =? 0 (ch.receive or_throw) else { ch.send(42) or_throw; 0 }
  let r = [parallel i in [0..2) step(i)]
  ```

  - **(a) Yes.** This matches your reading ("they run at the same time"). The cost: the compiler can't bound memory when it can't tell which items wait on which, so it uses a task per item and `explain` warns on large or unknown counts. That's Astra's position.
  - **(b) No.** A wait on a sibling is a compile error that names the call; use explicit channels between `tasks` instead. This is Chapel `forall` and Grok's position: memory stays bounded and strategies stay simple, but your example becomes an error.
  - Rec: (a), since it's the reading you gave and the warning covers the cost. Sol notes that (a) means `$window` must be rejected when it conflicts with a sibling wait.
- **B3. Is concurrent I/O fan-out spelled with the same `parallel`?** (Grok wants a separate `tasks.over(urls @fetch)`.)
  - Rec: same word. One concept, "these at the same time"; the strategy is a representation.
- **B4. GPU:** explicit placement (`$device = 'gpu'` or `xs.to(dev)`) first; automatic offload only later, behind a cost and residency model.
  - Rec: yes.
- **B5. Float reductions:** sequential order by default; a tree only when requested (`sum(xs 'tree')`). Integers may use a tree when proven equivalent.
  - Rec: yes.
- **B6. Refinements are metatags or context, not new constructs.** Approve the direction, with `$grain`, `$window`, `$layout`, `$device`, `$cores`, `$scheduler` and `$sequential` as proposals.
  - Rec: yes.
- **B7. `explain` and actionable "why not" diagnostics** are a language deliverable, shipped before more concurrency surface.
  - Rec: yes.
- **B8. Keep the block form `parallel { let a = f()  { … } }`** for running different things at once, e.g. producer plus consumer. It replaces `concurrent {}` + `spawn`. Grok calls it a third construct.
  - Alternative: `tasks` only.
  - Rec: keep. It's the same word and replaces two keywords.

- **Then C1–C11,** the details. Or say "D4: take the recs".

**C1. Can `parallel` items wait, including on each other, with the execution strategy inferred?**
```dewy
step = (ch:Channel<int> i:int) => if i =? 0 (ch.receive or_throw) else {
    ch.send(42) or_throw
    0
}
main = () => {
    let ch = channel<int>(1)
    printl"{[parallel i in [0..2) step(ch i)]}"   # [42 0]: item 0 waits for item 1
}
```
- **v1 (Claude):** any `blocks` in the body gives one task per item, unbounded. A separate concurrency cap was deferred.
- **Grok:** that costs a stack per item, flips on harmless I/O, and drops GPU offload. Use three strategies keyed on "may park or unknown", with a default window.
- **Recommendation:** Grok's three strategies (proposal-v2.md §1), surfaced in hover and `explain`, with no required tag. A cap metatag is deferred until a program needs one; the window covers the common case.
- **Spellings:** none new. This retires "a `parallel` body must not block".

**C2. How are items written in the block form?**
```dewy
f = (n:int) => n + 1
g = (s:string) => s.length
main = () => {
    parallel {
        let a = f(1)
        let b = g("hi")
        { printl"two"  printl"lines, in order" }
    }
    printl"{a} {b}"
}
```
- **v1 (Claude):** every top-level statement is an item.
- **Grok:** then braces stop meaning "in order", and a stray statement silently becomes a racing item. Make each item a `let` or a `{…}` group, with a fix-it on a bare expression.
- **Recommendation:** Grok's rule.
  - Braces keep meaning "sequential", and items are marked visibly.
  - `let` items bind after the join; reading another item's `let` is an error naming both.
  - Wrapping everything in braces (`parallel { {a} {b} }`) would hide the `let` results inside their inner blocks.
- **Spellings:** adds the block shape. Removes the keywords `concurrent` and `spawn`.

**C3. Are failures per-item values unless `or_throw`, with `or_throw` aborting the construct?**
```dewy
check = (n:int) => if n =? 2 Timeout else n
main = () => {
    let each = [parallel n in [1 2 3] check(n)]           # [1 Timeout 3]: nothing canceled
    let all = [parallel n in [1 2 3] check(n) or_throw]   # leaves main with Timeout; siblings canceled
}
```
- **Options:** (a) per-item values unless `or_throw`; (b) always fail-fast.
- **Recommendation:** (a). The error that escapes is the first in time (both reviewers agree).
- **Spellings:** none.

**C4. Does a compute-only `parallel` stop early when canceled?**
```dewy
heavy = (xs:array<int>):>array<int> | Canceled => [parallel x in xs x*x]
main = () => {
    let xs = [parallel i in [0..1000000) i]
    let r = within(1ms @heavy(xs))          # chunks stop at the deadline: Timeout
}
```
- **Options:**
  - (a) it runs to completion (v1);
  - (b) it always stops, adding `Canceled` to every enclosing function, which is noise for every caller;
  - (c) it checks at chunk boundaries and stops only where the enclosing result type already carries `Canceled`.
- **Recommendation:** (c). Grok asked for boundary checks, and (c) keeps them without adding new outcomes. A sibling's `or_throw` always stops chunks.
- **Spellings:** none.

**C5. Should `select` be a library function over operation values, used with `match`?**
```dewy
main = () => {
    let inbox = channel<int>(1)
    let out = channel<string>(1)
    match select(inbox.receiving  out.sending("ping")  timeout(1s)) {
        n:int => printl"got {n}"
        s:Sent => printl"sent"
        u:Unsent<string> => printl"not sent: {u.reason}"
        c:Closed => printl"inbox closed"
        t:Timeout => printl"nothing within 1s"
        c:Canceled => printl"canceled"
    }
}
```
- **Tie-break, v1 (Claude):** the earliest argument wins, giving priority and deterministic tests.
- **Tie-break, Grok:** priority starves a later op that is always ready, so choose fairly.
- **Recommendation:** `select` + `match`, with a **fair** random choice. The test runner fixes the seed. When priority is needed, call `try_receive` first.
- **Spellings:** adds `select`, `Op<T>`, `.receiving`, `.sending(v)`, `timeout(d)` and `Sent` (on `Channel`, the `spsc` ends and `mpmc`). Removes the `select { x = … => … }` grammar.

**C6. Does `op.then(f)` ship now?**
- Example: `dispatch` in proposal-v2.md §3, which needs it to tell `control` closing from `jobs` closing.
- **v1 (Claude):** defer it until a program needs it.
- **Grok:** ship it now, because same-typed results and two `Closed`s are otherwise indistinguishable.
- **Recommendation:** ship it now. Without it, two channels can't both be selected safely.
- **Spellings:** adds `.then` on `Op`.

**C7. Can receivers be loop sources, and what do those loops give?**
```dewy
main = () => {
    let numbers = channel<int>(4)
    let total = 0
    parallel {
        {
            loop i in [0..10) { numbers.send(i) or_throw }
            numbers.close
        }
        { loop n in numbers { total += n } or_throw }
        # parallel n in numbers { … } would start one item per value, windowed
    }
    printl"{total}"
}
```
- **v1 (Claude):** `loop x in rx` stops on `Canceled` with nothing to show for it, and `parallel x in rx` is uncapped.
- **Grok:** that reports success after a partial consume, and an uncapped accept loop has no bound.
- **Recommendation:** Grok's version.
  - `loop x in rx` gives `void` at `Closed` and `Canceled` on cancel.
  - `parallel x in rx` is windowed.
- **Spellings:** adds iteration over receivers, and a receiver loop's value (`void | Canceled`).

**C8. Do long-lived groups move to the library: `tasks(body)`, `Tasks`, `g.spawn(@f(x))`, `g.cancel`?**
- Example: autosave in proposal-v2.md §4.
- **Options:** keep `concurrent g {…}` + `spawn(g)`; use other names (`scope`, `nursery`).
- **Recommendation:** `tasks`. Both reviewers agree.
- **Spellings:** adds `tasks`, `Tasks`, `.spawn` and `.cancel`. Removes `concurrent g`, `spawn(g)`, `cancel(g)` and `TaskGroup`.

**C9. Does task admission failure follow the allocation policy?**
```dewy
work = (n:int) => n * 2
let doubled = [parallel n in [1 2 3] work(n)]   # no OutOfMemory in the type
```
- **Options:** (a) the allocation policy: the process ends, or `OutOfMemory` under `$explicit_allocation_failure`; (b) `OutOfMemory` in every spawn's type, as today.
- **Recommendation:** (a).
- **Spellings:** none.

**C10. Should `parallel_map`, `parallel_range` and `parallel_update` be removed?**
```dewy
let sums = [parallel row in [[3 1] [4 2]] sum(row)]   # was parallel_map
```
- **Recommendation:** remove them, since the `parallel` forms cover them.
- **Spellings:** removes the three functions.

**C11. Should `$parallel_safe` mean race-free only?**
```dewy
$parallel_safe
apply_all = (xs:array<int> f:(x:int):>int) => [parallel x in xs f(x)]
```
- **Recommendation:** yes. Waiting no longer disqualifies a callback; its cost shows in hover, and `& no blocks` locks it out.
- **Spellings:** none.

### D6–D9: time design core
- **Context:** the time system is a draft (`docs/design/proposals/time/time-design-v5.md`) and its implementation is on hold until these decisions are made.
- **Already settled by you:**
  - `Instant` is an exact integer count of nanoseconds since the 1977 standards epoch.
  - `now` takes no parentheses.
  - `@f()` with no arguments warns.

### D6. Storage width for `Instant` and `Duration`
- **Options:**
  - **a)** 128-bit nanoseconds: 16 bytes, range ±5×10²¹ years.
  - **b)** 64-bit nanoseconds: 8 bytes, but the range is only **1685–2269**. That's a new "year 2038" problem, and it can't hold ancient astronomy.
- **Cost of (a):** add and subtract take 2 instructions instead of 1, and arrays of timestamps use twice the memory. There's no heap and no bigint.
- **Compact form under (a):** `Instant<width=64>` is available for huge timestamp arrays and rejects out-of-range values.

```dewy
let t = instant"2026-11-01T12:00:00Z"         # 16 bytes
let log:array<Instant<width=64>> = []         # compact column, years 1685–2269 only
```

- **Rec:** (a). Your 10,000-year priority rules out (b) as the default.

### D7. `now - start` measures elapsed time on the monotonic clock
- **`now`** returns a `ClockReading`, a 32-byte, pointer-free pair of samples (wall clock and monotonic clock).
- **Proposed operators:**
  - `now - start` is elapsed time from the monotonic clock. It is never wrong when NTP adjusts the wall clock.
  - `now + 5s` is a monotonic deadline.
  - `.nominal` is the wall-clock `Instant`.
- **v4 had** subtraction use wall time, which lies whenever the wall clock is adjusted mid-measurement.

```dewy
let start = now
work
printl"took {now - start}"             # e.g. "took 125ms"; monotonic
let deadline = now + 5s                # monotonic deadline
loop now <? deadline { poll }
let stamp = now.nominal                # wall-clock Instant, for logs and storage
let dt = (now - start) / 1s as float64 # float seconds for game/physics code, always explicit
```

- **Prior art:** Go uses the monotonic clock but hides it inside one type, a known bug source. Here the switch to wall time is visible: `.nominal`.
- **Rec:** yes.

### D8. Time literals are checked at compile time and can't fail
- **What gets checked:** `date"…"`, `zoned"…"`, `instant"…"` and `zone"…"` with literal text are validated at compile time against the timezone data pinned for the build.
  - The result is a plain value with no `or_throw`.
  - A literal that lands in a DST gap or repeated hour without a policy is a **compile error** with a fix-it.
  - Runtime strings stay fallible.
- **What "can't fail" means:**
  - A compiled literal is a frozen snapshot: if a government later changes DST law, it doesn't silently move.
  - A stored *appointment* keeps its local intent ("09:00 New York") and is re-resolved through an explicit migration.

```dewy
let meeting = zoned"2026-10-26T09:00[America/New_York]"              # no or_throw
let later = zoned("2026-11-01T01:30[America/New_York]" fold='later')  # 01:30 happens twice that night
let feb = date"2027-01-31".add(1month overflow='clamp')              # 2027-02-28
let text = read_line ?? ""
let typed = zoned(text zone=zone"America/New_York") or_throw          # user text: fallible
```

- **Before and after:** the same §5 example had about a dozen `or_throw`s in v4. It now has one, on the user input.
- **Rec:** yes.

### D9. `1day` and `1week` are calendar periods, not durations
- **Today:** `month` and `year` are already calendar-only (your decision). This extends the same rule to `day` and `week`.
- **Why they can't be durations:** if `1day` were a duration it would equal `24hour`, so `meeting + 1day` couldn't mean "same local time tomorrow" without breaking the rule that equal values behave the same.

```dewy
let m = zoned"2026-10-31T09:00[America/New_York]"
m + 1day        # 2026-11-01T09:00 local: 25 real hours (DST ends that night)
m + 24hour      # 2026-11-01T08:00 local: exactly 24h
sleep(1day)     # compile error, fix-it: sleep(24hour)
```

- **New metatags:** `$time.gap = 'next'` and `$time.fold = 'earlier'` set the default policy for a scope, so `+ 1day` doesn't need it spelled at every call.
- **Rec:** yes.

---

## P2: unblocks safety work or common friction

### D10. Opt-out tags for `$bulletproof` (#108)
- **Context:** `$bulletproof` is the strictest, certifiable mode. Every place Dewy *trusts* something needs a tag that demands real proof instead. These 8 cover what is still trusted. Most of them only matter inside `$bulletproof`.
- **D10a. Library-trust namespace.** Recommended spelling: `$library.require_*`. A bare member turns the obligation on, and `=false` turns it off, the same style as `$time.require_*`.

| Member (old name) | Trusted today | With the tag on |
|---|---|---|
| `$library.require_asserts` (`$no_trusted_library_asserts`) | Library `assert`s never count as "may panic" | `graphemes(text)` errors: "cannot prove library assertion"; validate the UTF-8 first |
| `$library.require_checks` (`$no_implicit_library_checks`) | Library code keeps hidden runtime bounds checks | The library must prove its internal indexes or return failures; your code is unchanged |
| `$library.require_memory` (`$no_trusted_library_memory`) | Library raw-memory code is assumed not to keep arena storage | `printl(xs)` inside an arena block errors; print after the block |
| `$library.require_drop_hooks` (`$check_library_drop_hooks`) | Library cleanup (e.g. releasing a lock) is assumed infallible | `@(m.lock())` errors until the library's release hook is proven |

- **D10b. `$prove_finite_inputs`** (was `$no_assumed_finite_inputs`). Under `$no_inf`, incoming floats are currently assumed finite; with the tag, callers must check them first.

```dewy
same = (x:float64) => {
    $no_inf
    $prove_finite_inputs
    x
}
accept = (x:float64) => if -1e300 <? x <? 1e300 same(x) else 0.0   # the check discharges it
```

- **D10c. `$verify_protocols`** (was `$verify_certified_protocols`). `serve`/`pipeline` (request/reply servers) are trusted to be deadlock-free under `$no_deadlocks`; with the tag they need a checked proof. Your call sites don't change.
- **D10d. Keep `$explicit_environment_failure`.** With it, end of input becomes a value instead of ending the program.
  - `input_int("count? ")` returns `int | EndOfInput | FileError | Canceled`.
  - `EndOfInput` is a new error type.
- **D10e. Drop `$explicit_runtime_failure`.** It lumps together allocation failure (already covered by `$explicit_allocation_failure`), runtime-core correctness and stack overflow. A narrower switch can come later.
- **D10f. Unconfined paths become an error under `$bulletproof`** (today a warning; it stays a warning elsewhere). This changes a decided warning.

```dewy
let f = p(args[0])                      # path from the command line
let root = p"/srv/data"
if not root.contains(f) return          # this check satisfies it
printl(f.exists)
```

- **D10g. `$waits.require_proofs`** (new, part of `$bulletproof`). It rejects `$audited_wait`, the human "I reviewed this blocking FFI call" claim.

```dewy
nap = () => {
    $audited_wait
    $unsafe usleep(1000)   # rejected under the tag; fix: sleep(1ms)
}
```

- **D10h. Very large `parallel` ranges.** A range of 2^63 or more values is silently capped today. Rather than a new tag, the existing `$no_assumed_bounds` should reject it unless the size is proven, e.g. `if hi >? 1000000 return`.
- **Rec:** approve all of D10a–h.

### D11. Game library calls that crash today (#131–#133)
- **Context:** with no-traps by default, every library call that can panic forces games to opt into `$runtime_checks`. These three changes give each one defined behavior instead.
- **D11a. A menu left open.** `ui_begin` panics after 3 frames without a matching `ui_end`.
  - **Rec:** the next `ui_begin` closes the open menu itself, with a debug warning.
  - **Alternative:** a scoped form, `ui_menu("pause" vec2(640 340)) { … }`.

```dewy
ui_begin("pause" vec2(640 340))
if ui_button("Resume") return      # early exit skips ui_end
ui_end
```

- **D11b. Removed physics bodies.** Using a handle after its body was removed panics today.
  - **Rec:** treat it like removed joints, which are already a no-op: reads return a defined value, and writes do nothing.
  - **Alternative:** reads return `vec2 | none`.

```dewy
let w = physics.World
let ball = w.add_circle(vec2(0 0) 8)
w.remove(ball)
let p = w.pos(ball)                # today: panic
```

- **D11c. Undeclared action names; melody strings.**
  - **Undeclared action:** `action_pressed("jmup")` with a name never declared via `action(...)` panics today. Rec: return `false`.
  - **Melody literals:** `melody("C4 E4 G9x")` with a bad note fails at runtime today. Rec: check literal note strings at compile time, as format strings already are.
- **Rec:** as stated in each sub-item.

### D12. Writing to a copied loop element is an error (#139)
- **The bug:** `loop x in xs` gives a *copy* of each element, so writing to `x` is silently lost.
- **Proposal:** make that write an error that names `loop @x in xs` (which iterates by place).

```dewy
Enemy:type = [hp:int]
let enemies = [Enemy[10] Enemy[20]]
loop e in enemies { e.hp -= 1 }     # error: e is a copy; write `loop @e in enemies`
loop @e in enemies { e.hp -= 1 }    # changes the array
```

- **Status:** it's being implemented provisionally.
- **Rec:** yes.

### D13. `[]` as an empty dictionary when the type says so (#141)
- **Today:** there's no empty-dict literal. `[:]` doesn't exist, and `[]` is always an array.
- **Proposal:** `[]` becomes an empty `dict` when the expected type is a dict. This is a typing rule, not new syntax.

```dewy
count_words = (counts:dict<string int>) => counts.length
count_words([])                          # empty dict
let seen:dict<string int> = []
```

- **Rec:** yes.

### D14. `?? return x` / `?? break` / `?? continue` for one-line early exits (#142)

```dewy
let n = to_int(text) ?? return 0          # leave the function with 0 if text isn't a number
loop line in lines {
    let v = to_int(line) ?? continue      # skip bad lines
    total += v
}
```

- **Today** you'd need a two-line `let` plus an `if`.
- **Rec:** yes. It's new surface, but it only lets jumps appear where an expression was already allowed.

---

## P3: lower stakes (the default would be taking the rec)

### D15. Time, remaining choices
- **`today` returns a plain `Date`.** `today_support` reports when the date is ambiguous (the clock's uncertainty spans midnight), and strict mode (`$time.require_clock_accuracy`) forces you to handle it.
  - Rec: yes.
- **Edition spelling.** Editions let a future Dewy change defaults (e.g. the default calendar) without changing old code: edition E keeps the default, E+1 warns, E+2 changes it, and only for code that opts into E+2.
  - **a)** `$edition = 2026` at the top of each module.
  - **b)** `$build.edition = 2026`.
  - Rec: (a). `$build` settings are program-wide and set in the main file, but an edition is per module.
  - A module with no edition gets the 2026 baseline plus a warning.
- **Calendar name.** The arithmetic calendar used by default, extended backwards before 1582, is spelled `Gregorian` (rec, shorter) or `ProlepticGregorian`. Real historical adoption lives in separately named calendars, e.g. `British` (with 1752's skipped days).
- **`age` default.** `date"2000-02-29".age(on=date"2027-02-28")` gives 26, because a Feb-29 birthday counts on March 1 in non-leap years. Strict mode makes you state the rule, and `legal_age` always takes a jurisdiction.
  - Rec: yes.
- **Timezone rules source.** Use the host's zone *name* (e.g. "America/New_York") but the rules pinned in the build, for reproducible results. Use the OS rules only with `$time.zone_source = 'host'`. When they disagree, `ZonePackStale` is a status, not a failure.
  - Rec: yes.
- **Rule-data selection in source.** `$time.rules = rules_2026`, where `rules_2026` is a constant declared in a `.dewy` file. Transition tables can themselves be generated `.dewy` source, so there are no lockfiles.
  - Rec: yes.
  - This is the same in-source idea that could answer packages (D21).
- **Carried over from v4:**
  - relative waits (`sleep`, timeouts) count time while the machine is suspended, with `clocks.active` to exclude it;
  - intervals default to half-open `[a b)`;
  - separate `Appointment`, `Occurrence`, `Event` and `Observation` records;
  - the 17 `$time.require_*` strict-mode names plus `$time.strict`, included in `$bulletproof`.

  Rec: yes to all.
- **New names in v5:** `UtcLabel`, `ClockObservation`/`observe`, `Resolution`, `ClockDiscontinuity`, `today_support`, `OffGrid`, `ZonePackStale`, `Coordinate<Scale>`, and `instant(text)` replacing `parse_instant`. The full list is in v5 §14.
  - Rec: approve as provisional.

### D16. Write to a tuple slot at a runtime index (#137)

```dewy
let t:[int64 int64] = [0 0]
let i = pick_side            # runtime 0 or 1
t[i] += 1                    # today an error (reads like t[i] already work)
```

- **Rec:** allow it when every position has the same type.

### D17. An array whose elements must be valid indexes of that same array (#138)
- **The need:** union-find, tries and entity arrays store indexes into the same array. A refinement saying "every element is less than my own length" would remove their runtime bounds checks.

```dewy
let parent:array<int64<(<? parent.length)>> = [0]   # each entry indexes parent itself
parent.push(parent.length)                          # still valid: arrays only grow
```

- **Rec:** design note first, covering grow-only arrays plus self-length refinements. This is hard to reverse once programs use it.

### D18. `from` becomes a contextual keyword (#144)
- **Today:** `from` is reserved everywhere because of `from units import m, km`, so `let from = 3` is an error.
- **Proposal:** make it a keyword only inside imports.
- **Rec:** yes. Re-reserving it later would break code.

### D19. Formatting
- **D19a. `pad_center` (#134).** Add it beside the existing `pad_start`/`pad_end`, e.g. `"hi".pad_center(6)` gives `"  hi  "`.
  - Rec: yes.
- **D19b. Python-style nested width `"{x:<{w}}"` (#135).** Today this is a clear error pointing to `format(x "<{w}")`.
  - Rec: no; keep the error.
- **D19c. Width-only format on an exact rational (#136).** `"{x:>7}"` with `x` the rational 120 prints `    120`, not `  120.0`.
  - Rec: yes.
- **D19d. Confirm: decimal-text rationals print as decimals.** `rational("19.99")` prints `19.99`, not `1999/100`, like a decimal literal does.
  - Rec: confirm.

### D20. `if let e = f(x) …` (#143)
- **Today:** two lines, `let e = f(x)` then `if e isnt? none { … }`, and `e` is already narrowed inside the `if`.
- **Rec:** no; the current form is enough.

### D22. `$parallel_safe` on a function with several callbacks (#145)
- **Today (built 11-02):** the tag requires *every* callback parameter to reach parallel code.
- **Question:** should one parallel callback be enough, so a function can also take a sequential callback and still carry the tag?

```dewy
$parallel_safe
let apply_then_report = (xs:array<int> f:<(int):>int> report:<(array<int>):>void>) => {
    let ys = [parallel x in xs f(x)]   # f must be parallel-safe
    report(ys)                         # report runs once, sequentially
}
```

- **Options:**
  - **a) Every callback (built).** The tag above is an error, because `report` never reaches parallel code.
  - **b) At least one.** The tag above is accepted; only `f` is pinned.
- **Rec:** (a). It keeps the tag's meaning simple: every callback the function takes is checked for parallel use.
- **Spellings:** none new.
- **Reversible:** yes, a one-loop change.

### D23. `spsc` details built provisionally (#146)
- **Today (built 11-02):** `spsc<T N>` works as decided on 2026-11-01 (see decisions.md). Six smaller calls were made along the way and are all reversible.

```dewy
Message:type = [id:int64 body:string]
let [tx rx] = spsc<Message 64>().split
tx.send(Message[1 "hi"]) or_throw
let m = rx.receive or_throw
printl"{m.body}"
```

- **The calls, each with the rec "keep":**
  1. A value type parameter is a plain `<T N>`: a parameter given an integer becomes a value. No `<T N:int64>` annotation (it could be added later).
  2. Dropping an end closes the queue: the receiver drains what was sent, then sees `Closed`.
  3. The end types leave out the capacity: `SpscSender<T>` and `SpscReceiver<T>`, so functions taking an end don't name `N`.
  4. `.split` is built on a compiler-only tag `$__consume__` (like `$__drop__`) that makes a method take ownership of its receiver. Users don't write it.
  5. A spawned task now owns the move-only values it captures, so an end can be moved into a task.
  6. `spsc`'s `try_receive` returns `T | Empty | Closed | Canceled`, with no `Busy`, since a single consumer can't collide.
- **Spellings:** `$__consume__` (compiler-only).
- **Reversible:** yes, each one.

---

## P4: open-ended

### D21. Packages (#78), which you're still thinking about
- **Today:** Dewy programs can't use third-party packages. Only Sloppy's `build:` block can declare them. The fetch/lock/cache machinery exists (`pkg.jo`).
- **Constraint you gave:** everything lives in `.dewy` source, and you're unsure about `.lock` files.
- **Shape consistent with that** (and with D15's rule selection):

```dewy
# main.dewy
$package(shapes url='https://github.com/someone/shapes' ref='v1.2.0' digest='sha256:9f2c…')
import shapes
let c = shapes.Circle[radius=2]
```

- **Pinning:**
  - The `digest` *is* the lock: the exact bytes are pinned in source, so no `dewy.lock` file is needed.
  - Upgrading rewrites that line, e.g. a `dewy update shapes` tool command edits the source.
  - A local checkout can use `path='../shapes'` instead.
- **Open questions:**
  - Transitive dependencies: does each package's own `$package` lines pin its deps (nested), or does the root re-pin everything?
  - Where the fetched source is cached.
  - Whether a registry name (`shapes@1.2`) is ever allowed, or URLs only.
- **Rec:** when you're ready, approve this "digest in source" direction and I'll run a short design round on transitive dependencies.
