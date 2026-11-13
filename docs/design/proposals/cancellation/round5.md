# Cancellation, round 5: last fixes, and D44 for David

This round amends round 4 and is the last fix round:

- **§1** gives the rule changes.
- **§2** is D44, written out in full for `docs/design/open_decisions.md`: self-contained, with no references to earlier rounds.
- **§3** resolves every finding of `review-round4.md`, `soundness-round4.md` and `regrade-round4.md`.

Programs are in `programs-r5/` (23 is revised; 24–26 are new), graded in `dogfood-round5.md`.

## 1. Rule changes (amending round 4)

1. **`within` and `protect_from_cancel` after their own deadline** (review MF1 and MF2, soundness S2). The two behave the same. When a deadline cancels the child, the result is `Timeout`, with the child's kept failures, unless the child's value came through a handler that names `Canceled`:
   - a `<Canceled>` or `c:Canceled` arm;
   - an `is? Canceled` test;
   - a `??<Canceled …>` handler.

   A value produced by a plain `??`, `?? void` or a catch-all gives `Timeout`, so a default can't hide a missed deadline (program 24). The work's request records whether its cancellation was handled by naming it. That is request state, not a tag on values.

   A child that wasn't canceled is published under the join's rule: as a narrowed view of the same value, whatever its type. So `within(2s @load_both)` compiles (program 25). Round 4's compile error at the call is withdrawn.

   The result is classified only after the child's cleanup and joins (soundness N6).
2. **Retained sibling failures** (review S2, soundness M1). A sibling canceled by a `parallel` early exit contributes what it *forwarded* (its `or_throw`) and its cleanup failures. A value it bound with `let`, or left as a statement value (C3), is dropped with bindings nobody will read.

   Several retained failures aggregate in the error stack, whose elements may now be any exception except `Canceled`: `ErrorStack[Stopped[1] Stopped[2]]` (program 26). A stack is an `error` when every element is one, and an `exception` otherwise. This is the one change to D42 Q6's stack.

   A catch-all arm in a `parallel` item that turns `Canceled` into another failure warns by default, because that failure would now join every early exit.
3. **The joined transfer into a closed parent** (soundness S1). This is named as the one exception to the publication rule. When a `parallel` block continues after its parent's request closed, each item's binding moves into the parent as it is, type and all.
   - It is legal only because the parent's request is already closed.
   - The value then counts as the parent's for every later confinement check.
   - It is not permission to write an outer place, a mutex or a background task.
4. **Persisting undos are classified by the failure** (review S1). A failure type is a persisting undo when it is an `UndoFailed`, a new error family: the library's `RollbackFailed` and `ProcessStopFailed`, plus any user type declared `type of UndoFailed`. Whatever hook returns it, `$__abandon__` or `$__drop__`, decides nothing:
   - a user's `$__abandon__ = () => remove(temp)` that fails with `FileRemoveFailed` is litter, exactly like the library's atomic write;
   - D40 Q4's text changes to match (§2, knock-on edits).
5. **`$origin`** (review S3, soundness S3).
   - Each returned `Canceled` has the origin of the cancellation point that returned it, and a captured value keeps its own.
   - A `Canceled` made by an adapter takes the boundary that reported it. The case is cleanup whose grace ran out in a body that never waited.
   - `$trace` likewise. `$parts` lists one cancellation facet.
6. **Descendant input** (soundness N1). The rule 4 exemption follows cancellation-propagating ancestry, not lexical nesting. Work behind a shield is not a descendant, and a `Tasks` passed in is checked by its actual group.

## 2. Questions for David

---

### D44. Cancellation: `Canceled` only where something can cancel

A wait returns `Canceled` only where something can cancel the work: inside `race`, `first_ok`, `within`, `protect_from_cancel`, `parallel`, `task.tasks` and spawned tasks, and everything they call. Elsewhere, including `main`'s own waits, it never does, and Ctrl-C keeps its OS default unless a `signals.ctrl_c` item handles it. The group that cancels work consumes the `Canceled` it caused; these questions settle how that looks in source.

#### Q1 (a). Cancellation is inferred, never written in a result type

```dewy
fetch_text = (url:string):>string | HttpError => http.get_text(url)
main = () => {
    let home = fetch_text("https://example.org")            # string | HttpError
    parallel {
        let news = fetch_text("https://example.org/news")   # string | HttpError | Canceled
        show(home) or_throw
    }
}
```

Should `Canceled` appear in a result only at call sites that something can cancel, added by the compiler, like the inferred `blocks` effect, and never written in a result type?

- **Rec:** yes. A written type then stays the same however a function is called, and hover shows the added `| Canceled`. **Reversible** before release.
- **You give up:** writing `| Canceled` in a result type, which becomes an error with a fix-it.

#### Q2 (a). `Canceled` stays inside the work it belongs to

```dewy
probe = (host:string failures:Mutex<array<exception>>) => {
    let r = net.ping(host)                      # Duration | NetError | Canceled, as a parallel item
    printl"{host}: {r}"                         # fine: logging, locals, helpers, catch-alls
    @(failures.lock).push(r)                    # error: failures outlives this item; handle Canceled first
    protect_from_cancel(1s () => save(r))       # error: carries it into fresh work; pass `r is? Canceled`
    if r is? Canceled return Failed and [cause=r]   # error: write `r and Failed`, keeping it a facet
    if r is? Canceled return Canceled           # error: only the runtime makes one; `return r`
    r
}
```

Should a value that may hold `Canceled` work like any failure inside its own work, while these four are errors?

- making a `Canceled`;
- storing one where it outlives the work (an outer variable from a `parallel` item, a mutex, an atomic, a channel, a global);
- putting one inside another failure's fields;
- carrying one into protected, cleanup or background code.

- **Rec:** yes. It is the smallest rule that keeps `Canceled` only where something can cancel: every `Canceled` stays with the work that was canceled, and that work's group consumes it. `??` and `or_throw` treat it like any failure. **Reversible** before release.
- **You give up:** creating a `Canceled` yourself, and keeping one past the work that was canceled.

#### Q3 (b). `$until_others_finish` marks work that shouldn't keep its group alive

```dewy
count_with_spinner = (path:Path) => {
    parallel (
        $until_others_finish spin("counting")      # canceled once count_lines is done
        let n = count_lines(path)
    )
    n
}
```

Should a `parallel` item, or a `group.spawn(…)` statement in `task.tasks`, prefixed with `$until_others_finish` be canceled once nothing but such work and signal waits remains? That is the trigger that already closes signal listeners.

- **Rec:** yes. Readers got the name right cold. **Reversible:** the spelling, freely; the rule, before release.
- **You give up:** in a marked item, binding names used outside it, and holding a lock across a wait. Its tail runs canceled, so a marked signal listener may lose a pending notification.

#### Q4 (c). Handing your cancellation to another task

```dewy
thumbnail = (jobs:Channel<Job> path:Path) => {
    let reply = channel<Reply>(1)
    jobs.send(Job[path reply task.cancel_request]) or_throw
    (reply.receive or_throw).result
}
serve_jobs = (codec:Codec jobs:Channel<Job>) => loop job in jobs or_throw {
    let done = codec.start(job.path)
    match select(@done.receive @job.cancel.receive) {
        reply:Reply => job.reply.send(reply) ?? void
        <Closed<task.CancelRequest>> => codec.abort()   # the caller was canceled, or has ended
        <Canceled> => return                            # this worker's own group stopped it
    }
}
```

Should a task pass its cancellation on as `task.cancel_request`, a `task.CancelRequest` whose `receive` gives `Closed<task.CancelRequest>` once the task is canceled or ends?

- **Rec:** yes. Both names read correctly cold. **Reversible.**
- **You give up:** nothing checks that a caller passes it, and a worker can't tell "gave up" from "finished".

#### Q5 (a). A loop over a source ends when its task is canceled

```dewy
total_of = (numbers:Channel<int>) => {
    let total = 0
    loop n in numbers { total += n }       # canceled: the loop ends here, quietly
    printl"total {total}"                  # still runs, in the canceled task
    total
}
total_or_stop = (numbers:Channel<int>) => {
    let total = 0
    loop n in numbers or_throw { total += n }   # canceled: leaves total_or_stop with Canceled
    total
}
```

Should a loop over any source (a channel, a `merged` inbox or a signal) end when its task is canceled, as signal loops already do, with `or_throw` after the source to leave the function instead?

- **Rec:** yes. It replaces `merged`'s "one `Canceled` item, then end" rule with the signal rule. **Reversible** before release.
- **You give up:** a loop ended by cancellation looks like one that ran out of input, and the code after it runs. Write `or_throw` where that code publishes a result.

#### Q6 (a). `race` and `first_ok` discard their losers, but never a failed undo

```dewy
backup_to = (dir:Path data:array<uint8>) => p"{dir}/backup.bin".write_bytes(data)
save_once = (data:array<uint8>) => first_ok(@backup_to(p"/mnt/a" data) @backup_to(p"/mnt/b" data))
# a loser's failed close or stray temporary file goes with its result
migrate = () => race(@apply_on(primary) @apply_on(replica))
# error: a loser's RollbackFailed (an UndoFailed) can't be discarded; handle it in apply_on
```

Should `race` and `first_ok` discard their losers' whole results, cleanup failures included, with one exception? The exception is a failed undo whose effects persist: an `UndoFailed`, such as `RollbackFailed` or `ProcessStopFailed`. The work must handle that itself.

- **Rec:** yes. `UndoFailed` is a new error family, not yet cold-read. Hover on the call lists what is discarded. **Reversible** before release.
- **You give up:** a report, at run time, of a loser's failed close or stray temporary file. Hover shows it, and Q7's tag forbids it.

#### Q7 (c). A strict tag against discarding losers' cleanup failures

```dewy
main = () => {
    $no_discarded_failures
    let data = p"state.bin".read_bytes or_throw
    first_ok(@backup_to(p"/mnt/a" data) @backup_to(p"/mnt/b" data)) or_throw;
}   # error: a loser's cleanup failure would be discarded; handle it inside backup_to
```

Should `$no_discarded_failures`, in `$bulletproof`, make it an error for `race` or `first_ok` to discard a loser's cleanup failure? A loser's main result stays discardable.

- **Rec:** yes. Readers got the name right cold. **Reversible.**
- **You give up:** nothing by default. Under the tag, each raced piece of work handles its own cleanup failures.

#### Q8 (a). What changes in documented behaviour

```dewy
main = () => {
    let quote = within(2s @fetch_quote("ACME"))    # rational | HttpError | Timeout: no Canceled in main
    sleep(1s)                                      # void: nothing here can cancel
}
```

Should these changes be accepted together?

| Change | Example | Against |
|---|---|---|
| `select` gives `Canceled` only where something can cancel | `select(@a.receive)` in `main`: `int \| Closed<int>` | batch 7 |
| A canceled send gives `Canceled`, dropping its payload; `reserve` keeps it | a canceled `out.send(conn)` closes `conn` | Channels |
| `try_send` and `try_receive` aren't cancellation points | `q.try_receive` gives `Empty`, never `Canceled` | Channels |
| `Task.wait()` is an ordinary wait that never reports the task's own `Canceled` | `within(2s @indexer.wait)` leaves the indexer running | task API |
| `protect_from_cancel`'s limit starts at cancellation | `protect_from_cancel(30s @run_job(f))`: no limit until a stop | D41 Q2 |
| After its deadline, `within` (and protection) gives `Timeout`, unless the child's value came from a branch that names `Canceled` | `<Canceled> => return best` keeps `best`; `?? none` gives `Timeout` | `within` |
| Cleanup's grace starts at cancellation; its expiry gives the work's `Canceled` | a slow final flush in `main` completes | cleanup |
| A sibling canceled by an early exit keeps what it forwarded, and its cleanup failures, beside the exit | a job cut off after SIGTERM becomes `main`'s result | C3, D40 Q1 |
| The error stack may hold any exception except `Canceled` | `ErrorStack[Stopped[1] Stopped[2]]` | D42 Q6 |
| A marked item's `or_throw` of its block's `Canceled` ends only that item | `$until_others_finish { sleep(1s) or_throw }` | C3 |
| A `??` that falls back round a loop on a closed wait is an error where the wait is visible (it was a warning) | `jobs.receive ?? continue` | D42 Q2 |
| The three-press forced exit goes | the REPL survives repeated Ctrl-C | signals |
| Unhandled Ctrl-C keeps the OS default; `.observe` never cancels | Ctrl-C ends a program with no handler | signals |

- **Rec:** accept all. Each is **reversible** before release.
- **You give up:** what the "Against" column names: in each, a documented rule changes to the one in the row.

Dogfooded in 26 programs over five rounds, with three independent reviews; the names in Q3, Q4 and Q7 were read correctly cold, and `UndoFailed` hasn't been cold-read yet.

---

### Knock-on edits (with D44)

- **D40 Q4:** "`$__abandon__` is for a value whose cleanup throws its work away. A failure it returns counts as a failed undo only when it is an `UndoFailed` (`RollbackFailed`, `ProcessStopFailed`, or a user type declared `type of UndoFailed`). A staging file's failed removal is ordinary cleanup, whichever hook removes it."
- **D41:**
  - *Intro:* "A group cancels its unfinished work when it ends early: `race` or `first_ok` has its answer, a `parallel` item leaves the function, a deadline passes, or only `$until_others_finish` work is left. Ctrl-C cancels only through a `signals.ctrl_c` item; with none, it ends the process."
  - *Q1:* the example runs under `within(3s @count_primes(n))`, and the comment reads "stops here once its group cancels it". Add: "where nothing can cancel the loop, `check_cancel()` warns".
  - *Q2:* "`protect_from_cancel(limit @work)` runs `work` on a fresh request. The limit starts when the caller is canceled, or at entry if it already was. A deadline from entry is `within`. Nothing that may hold `Canceled` can be carried into `work`." The "exits 130" sentence goes.
  - *Q3:* "The body and every spawned task are cancellable. A child failure, or the body failing, cancels the rest, keeping their forwarded and cleanup failures. A normal return joins them, then cancels `$until_others_finish` tasks."
- **D42:**
  - *Q1:* add to the consuming actions: "the losers of `race` and `first_ok`, and `first_ok`'s earlier failures, discarded whole, except an `UndoFailed`". Under `$no_discarded_failures`, losers' cleanup failures no longer count as consumed.
  - *Q2:* withdrawn. The `select` progress rule covers a `??` fallback on a wait in a loop, as an error where the wait is visible.
  - *Q3:* "`$explicit_cancellation` (in `$bulletproof`): in cancellable code, a handler that can consume `Canceled` must name it. Where nothing can cancel, it asks nothing."
  - *Q6:* the stack's elements may be any exception except `Canceled`, and the stack is an `error` when they all are.
  - *Q7:* drop the Ctrl-C example and its 130 rationale: `Canceled` never reaches `main`. Q7 is only about ordinary combinations.
  - *Q8:* add "`$origin` and `$trace` of a `Canceled` are the cancellation point that returned it; `$parts` lists one cancellation facet".
- **LANGUAGE.md:**
  - Tasks:
    - replace "level-triggered" with "a closed request stays closed";
    - "include it in their result type" becomes "where something can cancel them";
    - `within`: the deadline rule (Q8);
    - "checking a blocking operation such as `sleep(0ns)`" becomes `check_cancel()`;
    - "A `Canceled` from a wait never reaches `main`."
  - Errors as values: Q2's four rules.
  - Collectors: delete "A `Canceled` contribution leaves the enclosing function".
  - Channels:
    - "a canceled send gives `Canceled`";
    - drop `Canceled` from `Unsent`'s reasons;
    - `try_*` aren't cancellation points.
  - Signals:
    - delete the observer's root cancellation and the three-press exit;
    - add "`$until_others_finish` items don't keep the group alive; the same trigger cancels them".
  - `select`: "plus `Canceled` where something can cancel".
  - `merged`: Q5.
  - Written results such as `:>void | DuplicateLock | Canceled` drop `| Canceled` (Q1).
- **Library:**
  - `lib/std/signals.dewy`: `next` drops its written `| Canceled`, and forwards the runtime's own `Canceled` instead of `return Canceled`.
  - The files module removes an atomic write's temporary file in its drop hook.

---

## 3. Resolution of every finding

**`review-round4.md`**

| Finding | Resolution |
|---|---|
| MF1: `?? default` in a `within` child hides a missed deadline | Only a branch naming `Canceled` keeps a value; otherwise `Timeout` (§1.1; program 24). |
| MF2: compile error rejects never-canceled children | Withdrawn. Uncanceled children are published under the join's rule (§1.1; program 25). |
| S1: persisting undo by hook kind contradicts D40 Q4 | Classified by the failure, through the `UndoFailed` family; D40 Q4 amended (§1.4, knock-on edits). |
| S2: C3 boundary of sibling retention; catch-all warning | Only forwarded and cleanup failures are kept; bound values are dropped. A default warning on catch-alls that turn `Canceled` into another failure (§1.2). |
| S3: `$origin` points at the first cancellation | Per returned value (§1.5). |
| S4: Q8's `within` row | Updated (Q8). |
| Part 4: readiness table | Every question in D44 has an example with its enclosing function (Q1 calls from `main` and from an item), a one-sentence question, a Rec with reversibility, and "You give up". Q8's tables are merged. |
| N3: the Python and Trio analogy | Dropped. |

**`soundness-round4.md`**

| Finding | Resolution |
|---|---|
| M1: repeated non-error exceptions have no aggregate | The stack takes any exception except `Canceled` (§1.2; program 26), listed in Q8 and D42 Q6. |
| S1: closed-parent transfer contradicts the publication ban | Named as the one exception, with its conditions (§1.3). |
| S2: protection's answer after handling | Uniform with `within` (§1.1). |
| S3: diagnostic origin for descendants and cleanup-only cancellation | Per-value origin; adapter-made cancellations take the reporting boundary (§1.5). |
| N1: descendant means cancellation ancestry | Stated (§1.6). |
| N2–N5 | Confirmed; rules unchanged. |
| N6: classify after cleanup | Stated (§1.1). |

**`regrade-round4.md`:** the floor is 3, at 08 only, and it is unchanged (`dogfood-round5.md`).
