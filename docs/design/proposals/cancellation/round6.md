# Cancellation, round 6: D44, final

### D44. Cancellation: `Canceled` only where something can cancel

A wait returns `Canceled` only where something can cancel the work: inside `race`, `first_ok`, `within`, `protect_from_cancel`, `parallel`, `task.tasks` and spawned tasks, and everything they call. Elsewhere, including `main`'s own waits, it never does, and Ctrl-C keeps its OS default unless a `signals.ctrl_c` item handles it. The group that cancels work consumes the `Canceled` it caused; these questions settle how that looks in source.

#### Q1 (a). Cancellation is inferred, never written in a result type

```dewy
fetch_text = (url:string):>string | HttpError => http.get_text(url)
main = () => {
    let home = fetch_text("https://example.org")            # string | HttpError
    parallel { printl(fetch_text("https://example.org/news") ?? "no news")   # inside: string | HttpError | Canceled
    printl(home ?? "offline") }
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
    protect_from_cancel(1s () => save(r));      # error: carries it into fresh work; pass `r is? Canceled`
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
fastest = (args:array<string>) => race(@run_tool("rg" args) @run_tool("grep" args))
# error: a loser's ProcessStopFailed (an UndoFailed) can't be discarded; handle it in run_tool
```

Should `race` and `first_ok` discard their losers' whole results, cleanup failures included, with one exception? The exception is a failed undo whose effects persist: an `UndoFailed`, such as `RollbackFailed` or `ProcessStopFailed` (`RollbackFailed:type = type of DbError & UndoFailed`; `ProcessStopFailed` likewise under `ProcessError`). The work must handle that itself.

- **Rec:** yes. `UndoFailed` is a new error family, cold-read. It is a family: a failure type joins it by being declared `type of … & UndoFailed`, beside its own parent. Hover on the call lists what is discarded. **Reversible** before release.
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
| After its deadline, `within` (and protection) gives `Timeout`, unless the child's value came from a branch that names `Canceled` | `<Canceled> => return best` keeps `best`; `?? none` gives `Timeout` | `within`; batch 10's uniform `??`: a plain `??` still consumes `Canceled` in the child, but `within` then gives `Timeout` |
| Cleanup's grace starts at cancellation; its expiry gives the work's `Canceled` | a slow final flush in `main` completes | cleanup |
| A sibling canceled by an early exit keeps what it forwarded, and its cleanup failures, beside the exit | a job cut off after SIGTERM becomes `main`'s result | C3, D40 Q1 |
| The error stack may hold any exception except `Canceled` | `ErrorStack[Stopped[1] Stopped[2]]` | batch 10 (the stack was an error); D42 Q6 |
| A marked item's `or_throw` of its block's `Canceled` ends only that item | `$until_others_finish { sleep(1s) or_throw }` | C3 |
| `select`'s progress rule also covers a `??` fallback on a wait in a loop: an error where the wait is visible | `jobs.receive ?? continue` | LANGUAGE.md's `select` progress rule; replaces the open D42 Q2 |
| The three-press forced exit goes | the REPL survives repeated Ctrl-C | signals |
| Unhandled Ctrl-C keeps the OS default; `.observe` never cancels | Ctrl-C ends a program with no handler | signals |

- **Rec:** accept all. Each is **reversible** before release.
- **You give up:** what the "Against" column names: in each, a documented rule changes to the one in the row.

Dogfooded in 26 programs over five rounds, with three independent reviews; the names in Q3, Q4, Q6 and Q7 were read correctly cold.

---

### Knock-on edits (with D44)

- **D40 Q4:** "`$__abandon__` is for a value whose cleanup throws its work away. A failure it returns counts as a failed undo only when it is an `UndoFailed` (`RollbackFailed:type = type of DbError & UndoFailed`, `ProcessStopFailed:type = type of ProcessError & UndoFailed`, or a user type declared `type of … & UndoFailed` beside its own parent). A staging file's failed removal is ordinary cleanup, whichever hook removes it."
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

### What changed since round 5

1. `within`'s named-branch rule now reads: "Whether a value was returned from a branch that names `Canceled` is decided at the return site; the runtime records which kind of return ended the child. That is request state, not a tag on values." Programs 23 and 24, and Q8's `within` row, agree with it.
2. Q8: the stack row's Against names batch 10, the `within` row's Against explains batch 10's uniform `??`, and the `??`-loop row is restated as an extension of `select`'s progress rule that replaces the open D42 Q2.
3. Q1's example now type-checks: the `parallel` item prints its fetch with a `??` default, and `main` still calls `fetch_text` directly.
4. Q6 races two tools (`ProcessStopFailed`), shows `UndoFailed` as a second parent beside `DbError` and `ProcessError` (and the D40 Q4 edit says so), and records that the name was cold-read (3/3 correct, at 4/4/4).
5. Q2's layout is tidied: a blank line before the Rec bullets, and `;` after the `protect_from_cancel(…)` line.
