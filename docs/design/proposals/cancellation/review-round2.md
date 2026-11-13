# Review, cancellation round 2

Reviewed: `round2.md`, `programs-r2/`, `dogfood-round2.md` (read after grading), against `review-round1.md`, `soundness-round1.md`, `brief.md`, decisions.md batches 3–10, D40–D42, LANGUAGE.md 3580–4150 and the v5 task proposal.

**Count: 3 must-fix, 7 should-fix, 6 notes.**

Round 2 is a real improvement. One rule ("`Canceled` is control, not data") closes every soundness hole from round 1. Batch 9 is now kept as decided, and the incidental trigger is limited to owning blocks. What remains:

- `Task.wait()` was swept into "joins", which makes a timed wait cancel the task it waits on.
- Program 12's "finish the current job" idiom cuts off every job after 30 s, signal or not.
- Q2's cost is reported as "rare" without testing the patterns it actually hits.

## Part 1: are the round 1 must-fixes resolved?

### My review

| Finding | Resolved? | Notes |
|---|---|---|
| M1: two kinds of `Canceled` | **Yes**, if Q2 is taken | One kind. No constructor, no storage, and requests give `Closed<…>`. Both of my scenarios are now errors at the store. |
| M2: one body vs layout and generics | **Yes**, if Q2 is taken | The §2.10 table is right. Two gaps (multiple result values, reads from inside a `parallel` item) are in S4. If Q2 is rejected, round 2 states the fallback (two bodies with a warning). |
| M3: incidental closure breaks signal-only `race`/`within` | **Yes** | The trigger applies only at owning `parallel` blocks; `race`, `within`, `first_ok` and protection are transparent. |
| M4: batch 9 not reproduced | **Yes** | Signal closure still gives `Closed<E>`, and code after the loop runs normally. The `or_throw` refinement for marked items is listed in Q7. |
| M5: a loser's cleanup failure replaces success | **Yes**, through Q6 | Q6 itself is weighed in Part 3. Programs 03 and 04's types are now true. |

### Soundness check

| Finding | Resolved? | Notes |
|---|---|---|
| M1: one bit can't describe aggregates or callables | **Yes**, if Q2 is taken | `pack` and `capture` are errors in their cancellable instances, so the bit is a complete description. |
| M2: separate origins | **Mostly** | Foreign requests give `Closed`, and nothing can construct or store a `Canceled`. One path is left: `Task.wait()` on a task that a group canceled, when the waiter isn't that group (MF1). |
| M3: one body changes generic behaviour | **Yes**, if Q2 is taken | `count_alternatives(wait_value)` is an error in its cancellable instance. |
| M4: dynamic incidental shutdown | **Yes** | Nothing becomes incidental dynamically except batch 9's signal waits, which give `Closed`. Winner-selecting groups are transparent. |
| S2: joins and cleanup transfers | **Partly** | Group joins now drain before returning. `Task.wait()` was wrongly included (MF1). |
| N1 specimens | **One claim is wrong** | §5 says every specimen types as the check expected. The generic-forwarding specimen `identity(sleep(0ns))` is now a compile error in its `parallel` item: passing a value that may be `Canceled` is banned. That is fine, but it is a cost of Q2 and should be counted as one (MF3). |

## Part 2: must-fix

### MF1. `Task.wait()` is treated as a group join, so a timed wait stops the task it waits on

**Rule involved.** §2.1(3) lists "calling `Task.wait()`" among the joins. When the joiner's request closes, a join "closes its children's requests at once; it then drains". The waited task is not the waiter's child: it belongs to `app` (`BackgroundTasks`) or a `Tasks` group.

```dewy
main = (app:BackgroundTasks) => {
    let indexer = app.spawn(@build_index(p"docs"))       # meant to run for minutes
    match within(2s @indexer.wait()) {                    # "finished within 2 s?"
        <Timeout> => printl"still indexing; continuing"
        _ => printl"index ready"
    }
    serve_requests() or_throw
}
```

Read literally, `within`'s deadline closes the waiter's request. `.wait()` then closes the *indexer's* request and drains it. The indexer is stopped, and `main` blocks until it finishes. v5 gave `.wait()` none of this: it reports the waiter's own cancellation and leaves the task alone.

**A second gap: no rule for an unrelated waiter.** Task handles can be copied. Round 2 handles a `Canceled` caused by `stop()` (consumed), but not a task canceled by its *group*, when the waiter is a different task. Example: two children of a `Tasks` group are canceled after a sibling fails, and a third task holds one handle. The waited task's `Canceled` would then reach a task whose request never closed. That is the foreign `Canceled` the round exists to remove.

**Fix.** `Task.wait()` is an ordinary standard wait:

- A canceled waiter gets its own `Canceled` at once, and the task keeps running.
- The waited task's own `Canceled` is never reported, whoever caused it. `.wait()` gives `void | E`, and `.running` (or a stop flag) tells "stopped" from "finished", as program 13 already does.

List the change in Q7 against v5.

### MF2. `protect_from_cancel`'s limit starts at entry, so program 12 cuts off every job after 30 s

**Rule involved.** v5 defines the limit as "the scope's own deadline", established when the scope is entered. Round 2 doesn't change it: §2.1(4) only says "a `protect_from_cancel` deadline passes".

**Program 12 lines 7–8** use protection as the regrade's "finish the current job" fix:

```dewy
check_cancel() or_throw
protect_from_cancel(30s @run_job(file)) or_throw     # a started job gets up to 30 s
```

Protection is entered when each job starts, with no SIGTERM involved. So every job longer than 30 s is canceled at 30 s. `Timeout` comes back, the `or_throw` leaves `process_queue`, and the item's `or_throw` then leaves `main`. The queue processor dies on its first long job in normal operation.

- The program's comment (line 2: "finishes the job in progress (up to 30 s)") assumes the limit counts from the cancellation.
- So does dogfood-round2's reading ("still running 30 s after SIGTERM").
- §5 presents this as the resolution of my regrade finding.

**Fix.** Round 2 already made cleanup's grace "start only when the owning task's request is already closed, or closes during cleanup" (§2.5), and calls cleanup shielding "`protect_from_cancel` with the grace deadline". So make protection the same: the limit starts when the parent's request closes, or at entry if it is already closed. Then the shield, cleanup and "finish the current job" share one rule, and program 12 is correct as written.

This changes D41 Q2's contract. D41 Q2's own example (a save run after Ctrl-C) behaves the same either way. List it in Q7. An "entry deadline" is already spelled `within`.

### MF3. Q2's cost is reported as "rare" without testing what it actually rejects

**Rule involved.** §2.2 says the cost is "a fix-it at the rare places where code passes a possible `Canceled` along as a value. Two such places are in the design docs today." The 13 programs don't exercise the patterns the rule actually hits. These are common in code that is cancellable, and under "every `parallel` item counts", every item is cancellable:

| Pattern | Status under §2.2 | Fix-it |
|---|---|---|
| `[parallel u in urls [url=u page=fetch(u)]]`: pairing an input with its result, the most common comprehension shape | error: a field may hold `Canceled` | `page=fetch(u) or_throw<Canceled>` in every such element |
| `let pages = [loop u in urls fetch(u)]` inside an item | error: a sequential collector | `fetch(u) or_throw<Canceled>` |
| `xs.map(@fetch)`, `sorted(key=@remote_rank)`, a user `memoize(f)` | error **inside the library's or helper's body** (its cancellable instance stores `f`'s result), reported far from the call | every higher-order function that stores a callback's result must write `or_throw<Canceled>` on it |
| `printl"{r}"` or `log(r)` while debugging a result | error: passing, interpolation included | `r or_throw` first, or a `c:Canceled` arm |
| `e:exception => report(e)` catch-all arms | error | add a `c:Canceled =>` arm before it |
| `identity(sleep(0ns))` and any generic wrapper of a wait's result | error (soundness N1's specimen) | forward first |

Each fix is mechanical, and in non-cancellable instances it is a no-op. But David's question about Q2 ("is it rare?") can't be answered from this dogfood. AGENTS.md requires a design to be dogfooded before it reaches open_decisions.md.

**Fix.**

- Before Q2 goes to David, add at least five programs that hit these rows: a record-pairing comprehension, a sequential collector in an item, a `map` over a waiting callback, a user-written higher-order helper, and logging.
- Grade them, and report the floor.
- Say where the higher-order-function error is reported. It should be reported at the user's call, naming the helper, not inside the library body.
- Put the "higher-order functions forward `Canceled` before storing a callback's result" rule in the library style guide.

## Part 3: the three points the coordinator asked to weigh

### Is "control, not data" an exception, and does it earn its keep?

**It is an exception.** Every other failure in Dewy is an ordinary value: it can be built, stored in a list, passed to a logger, interpolated and written in a type. Under Q2 `Canceled` can be none of those. That is a rule no other type has.

**It doesn't contradict what David said today, but it narrows it.** He said `Canceled` "ought to behave uniformly under `??` / `or_throw`". Round 2 keeps that exactly: `??`, `??<~Canceled>`, `or_throw`, `match`, `is?`, `&` and `as` treat it like any failure. What changes is the other half of "a regular error type": it stops being *storable* data. Q2 must say this in its first line, in his terms: "`Canceled` still works with `??` and `or_throw` like any error, but it can't be kept: not in a list, a field, a log call or a closure." Today Q2 leads with the permissions.

**Does it earn its keep against the soundness check's alternatives?** Yes, on balance. The alternatives are context-indexed result schemes for every aggregate, closure and generic, plus a run-time origin token on each `Canceled`. They make storage legal, but then:

1. **Two kinds of one value come back.** A stored `Canceled` from another task must not be dropped by a group that sees it. So the type system has to carry "ambient" versus "independent" `Canceled` internally, and hover has to show the difference. Round 1's M1, which both reviews flagged, returns in a more principled form.
2. **David's own core proposal weakens.** Once `Canceled` can be stored, `main`'s types can mention it (`status: string | Canceled`), and "`Canceled` only where something can cancel" stops being true of data.
3. **The machinery is larger:**
   - schemes through records, arrays, closures and module interfaces;
   - two bodies wherever layout, a generic argument or type inspection differs, with a warning;
   - origin tokens and their lifetime.
4. **What it buys is narrow.** Keeping a `Canceled` as data is almost never the goal. Every row in MF3's table *wants* to forward or handle the cancellation, not keep it. The rows are friction because the program wants to keep the *other* results.

So the restriction is unavoidable for this design's guarantees, and it earns its keep, provided MF3 shows the friction is what the table suggests: one `or_throw<Canceled>` per pattern.

**Is there a smaller rule that is still sound?** The ban has two separate jobs:

- **Origin (no foreign `Canceled`).** This needs no constructor, no send, no store into anything another task can read (outer variables written from an item, mutexes, atomics, fields of escaping values), and no capture by an escaping closure. These can't be relaxed without origin tokens.
- **One body.** This needs no possible `Canceled` in a type argument, a stored layout or a type operator. The ban could be replaced by "two bodies plus a warning" here. That is a compile-size trade, not a soundness one, and the friction is the same in practice: a value with `Canceled` in it would then be legal in some places and not others.

One targeted relaxation is sound and would remove MF3's first row, the most common one:

> A `parallel` item's own result value may hold its item's `Canceled` in fields and elements, and the join removes `Canceled` from the element type.

- **Sound for origin.** An item whose request closed either never publishes its result (an early exit skips the code that would read it) or makes the whole join give `Canceled`.
- **Sound for one body.** Item bodies have a single instance (always cancellable), so their layout is fixed. The join's narrowed type is a static view of that layout, provided failure-carrying unions reserve a `Canceled` tag, as §2.10 already does for top-level results.
- **Exclusions.** It must *not* extend to `within` or `protect_from_cancel` children: a child that handles its cancellation keeps its value, so a nested `Canceled` would reach the caller.

It is a special case on a special case, so it should be a separate question with a dogfood comparison. My recommendation: take Q2 as is, run MF3's dogfood, and add the relaxation only if record pairing scores under 5.

### Q6 against D42 Q1 and D40 Q1

**Against D40 Q1** ("a cleanup failure is the function's result"): consistent. The failure *is* the loser's result, and `race`/`first_ok` exist to discard loser results.

**Against D42 Q1** ("a failure part disappears only through an action that names it"): consistent only by extension, and that extension must be written down.

- D42 Q1's consuming actions are `is?`, `match` arms, `or_throw<E>`, `??<E>` and `;`. The bare catch-alls (`??`, `;`) are allowed because they visibly consume *everything*.
- `race` discards a loser's result with nothing at the call site. Q6's "race is the action that names it" holds only if D42 Q1's list is amended to include "the losers of `race` and `first_ok`, whose whole results are discarded".
- With hover listing what is discarded, that meets D40 Q1's condition, "hover shows … which failures it can add". It is not "lost silently" in source, but it is invisible at run time in release builds.

**Two corrections to Q6:**

1. **Keep `$__abandon__` failures.** A failed close or temp-file removal describes work nobody wanted. A failed rollback (`RollbackFailed`, D40 Q4's `$__abandon__`) means effects of the loser's work may persist in shared state. The program declined the loser's *answer*, not the knowledge that its undo failed. Let abandon failures replace the result, as D40 Q1 does elsewhere. They are rare, and serious when they happen.
2. **Fix the strict-mode check.** Putting it in `$explicit_cancellation` mixes two subjects: that tag is about handlers consuming `Canceled`. The fix-it "handle it inside the work" is also not actionable in program 11 (lines 17–18). The removal happens inside the library's atomic `write_bytes`, which `backup_to` can't reach. Either give the strict check its own tag in `$bulletproof`, with a fix-it the program can apply, or state that racing such work is unsupported in certifiable mode.

## Part 4: should-fix

### S1. Q2's framing for David

Lead with what is lost, not the permission list (open_decisions format), and quote his "uniform under `??`/`or_throw`" as kept (Part 3). Q2 also changes D42 Q3's "storing `Canceled` in a collection isn't consuming it, so collectors need nothing". Name that.

### S2. "A lock held across a wait is already an error" is true only under `$no_deadlocks`

§2.7 cites it to dismiss the marked-item wedge from my round 1 S6. LANGUAGE.md 4146 is in the deadlock-certificate section. In default mode the checks only reject "holding a lock while joining … work [that] takes it".

```dewy
parallel {
    $until_others_finish loop true { let g = @(stats.lock); sleep(1s) or_throw; g.count += 1 }
    { let g = @(stats.lock); report(g) }      # blocks on lock (not a wait) while the marked item sleeps
}
```

The essential item is blocked on `lock`, not parked, so the block's essential work is never done, and the marked item's sleep is never canceled. Either add a default-mode error for "lock held across a wait in a marked item", or drop the claim.

### S3. Spawned background helpers can no longer be marked

Round 1 allowed `group.spawn(() => { $incidental heartbeat() })`. Round 2 allows the marker only on a `parallel` block item, and keeps the trigger only at `parallel` blocks.

So a heartbeat or metrics task spawned into `task.tasks` keeps the group alive forever, and a normal body return then never completes. Program 09's shape with a stats reporter is the case:

```dewy
serve = (listener) => task.tasks((group:Tasks) => {
    group.spawn(@report_stats_every(10s))     # never ends: tasks never returns after the drain
    race(@accept_all(listener group) @signals.sigterm.next) or_throw;
})
```

Say whether `task.tasks` is an owning group for the trigger (batch 9 said "nearest running group"), and give spawned work a way to be non-essential. Either allow the marker on a spawn call (`$until_others_finish group.spawn(...)`, prefix form), or make the body's normal return cancel marked children.

### S4. Two gaps in what §2.2 counts as storage

1. **Multiple result values.** Dewy functions can express several values (`pair = () => { 1 2 }`, `:>(int64 int64)`), and `add(f)` spreads them into parameters. A possible `Canceled` in one of several values is neither a "top-level result alternative" nor in the ban list. State that `Canceled` may only be a function's whole, single result. Otherwise it is collecting.
2. **Items reading the enclosing function's locals.** "Block items share the function's variables" (v4/v5). `let r = sleep(1s)` in the enclosing function, then an item that reads `r`, moves a possible `Canceled` across tasks without capture or storage. It is sound in practice: if `r` is `Canceled`, the parent's request is closed, so the item's is too. But the rule should say so, or count the read as capture. Today it is in neither list.

### S5. `& no blocks` over-excludes

A callback that waits but handles its own cancellation (`() => sleep(1s) ?? void`) never returns `Canceled`. It still can't be typed as such in a written function type, because `& no blocks` forbids waiting itself. Calls through such a field get `| Canceled` at every cancellable call site.

Acceptable for now, but note it. A precise row member for "never passes on cancellation" would be new syntax for David.

### S6. D42 Q2's replacement is an error, not the warning D42 Q2 proposed

§3 extends `select`'s progress rule to a `??` fallback on a wait in a loop, as an error where the wait is visible. That is stricter than the open D42 Q2 (a warning, "a hint, not a proof"), and it catches today's closed-channel `jobs.receive ?? continue` too. That is good, but it is a change in strength. List it in Q7.

### S7. A small poll gap in program 08's level-3 idiom

Line 12, `job.cancel.receive(timeout=0s) is? Closed`, gives the worker's *own* `Canceled` when the worker is canceled (own request has priority, §2.6). `is? Closed` is then false, so the worker starts the codec for one more job before line 14's `select` breaks.

Either teach `?? break`/`or_throw` on that poll, or note it.

## Part 5: notes

- **N1. The Zig citations aren't verified.** §2.2 and §2.9 cite Zig std.Io wording and issue numbers (#31340, #35564) "as quoted for this round; not re-checked here". Verify them, or drop them, before a document for David relies on them.
- **N2. "When the task ends, its request also reads as closed" (§2.1).** This merges "the caller gave up" with "the caller finished". It is right for program 08, where the caller only ends after its reply. Say it in the `CancelRequest` docs, since a worker can't tell the two apart.
- **N3. A second SIGTERM is swallowed during program 12's drain.** The SIGTERM view stays attached until the block ends, so during up to 30 s of draining a second SIGTERM is intercepted and ignored. Under batch 9 this is correct, but an operator's "send it again to force" is lost. The escalation is SIGKILL. Say so in §2.8, beside the three-press removal.
- **N4. Debug-only logging of discarded failures (Q6) is the only build-mode-dependent behaviour in the design.** Fine, but list it.
- **N5. §5's claim about the soundness check's N1 specimens is inaccurate.** See Part 1: generic forwarding is now an error.
- **N6. Program 03's comment justifies `race` for an NXDOMAIN answer, but a transport failure also races.** A resolver that fails fast with "network unreachable" beats a slower success just the same. That is the program's choice, not the design's. `first_ok` would be the safer example.

## Verdict on "control, not data"

- **It is an exception** to Dewy's errors-are-values rule. It is compatible with David's statement as he worded it (`??` and `or_throw` stay uniform), but not with a fully regular error type.
- **It is the smallest rule** that gives one `Canceled`, one body and no origin tracking together. Only its one-body half could be traded for compile size, and only one targeted relaxation (an item's own result) is sound.
- **It earns its keep** against context-indexed schemes plus origins, which reintroduce two kinds of `Canceled` and put `Canceled` back into `main`'s types.
- **Recommendation: take it,** but only after MF3's dogfood shows the friction honestly, and with Q2 rewritten to lead with what David gives up.
