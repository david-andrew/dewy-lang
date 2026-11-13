# Cleanup round 5: the review findings fixed

**Verdict: keep `defer` narrowly; resources clean themselves up.** Keep `defer` only for one-off actions such as printing "done". It stays checked: non-failing, `void`, and no control transfer. Owners whose cleanup can fail (files, temp entries, terminal modes, transactions, child processes) and lock guards are **held to the end of their block**. Owners whose release cannot fail (memory, sockets, tickers, spsc ends, textures) are released at their last use, as today. A cleanup failure is an ordinary result of the enclosing function. Cleanup only cleans up: **nothing publishes from a drop hook**. A transaction rolls back unless the program calls `tx.commit()`; a child process is stopped unless the program waits for it. The round-4 `successful:bool` hook parameter is withdrawn. A cleanup failure paired with `Canceled` still counts as cancellation. There is no new block syntax and no callback scope, and `return`, `break` and `or_throw` act on the enclosing function. The one new name is a hook marker, `$__abandon__`. It has not been cold-read yet.

This is a paper design. Nothing here was compiled or measured. Programs are in `programs-r5/` and grades in `dogfood-round5.md`.

## Before and after

### File write whose final flush fails

Before:

```dewy
save = () => {
    let out = open(p"/dev/full" 'w') or_throw
    defer out.close()                 # a defer cannot fail: the flush error is lost
    out.write_bytes([1 2 3]) or_throw;
}
```

After:

```dewy
save = () => {
    let out = open(p"/dev/full" 'w') or_throw
    out.write_bytes([1 2 3]) or_throw;
}   # out flushes and closes here; the flush's FileError is save's result
main = () => save() or_throw
```

Hover on `save`: `void | FileError | Canceled | CleanupError`. The `FileError` line says "includes out's flush at line 4, returned as itself when nothing failed before". A pair appears only when two failures coincide.

### TCP early return

Before:

```dewy
let s = net.tcp_connect("127.0.0.1" 8080) or_throw
defer net.tcp_close(s)
let reply = net.tcp_receive(s)
if reply is? none return
printl((reply or_throw).length)
```

After:

```dewy
let s = net.tcp_connect("127.0.0.1" 8080) or_throw
let reply = net.tcp_receive(s)
if reply is? none return
printl((reply or_throw).length)
```

The stream's release cannot fail, so it happens after the stream's last use, on every exit.

### Single-producer channel

Before:

```dewy
produce = (q:Channel<int64>) => {
    defer q.close()
    loop n in [0..10) { q.send(n) or_throw }
}
```

After:

```dewy
produce = (out:SpscSender<int64>) => {
    loop n in [0..10) { out.send(n) or_throw }
}   # dropping the sender closes the queue; the receiver drains, then sees Closed
let [tx rx] = spsc<int64 16>.split
```

Shared `Channel` and `mpmc` keep explicit close (program 14).

### Mutex region with `return` and `break`

Before (today's rule: the guard is released at the place's last use):

```dewy
loop amount in amounts {
    let book = @(ledger.lock())
    if book.balance + amount <? 0 break
    book.balance += amount                    # last use: unlocked here
    append_file(journal "{amount}\n") or_throw;   # unprotected: journal order can differ
}
```

After:

```dewy
loop amount in amounts {
    let book = @(ledger.lock())
    if book.balance + amount <? 0 break       # unlocks, then leaves the loop
    book.balance += amount                    # last use of book
    append_file(journal "{amount}\n") or_throw;   # still locked: journal order = ledger order
    if amount >? limit return TooLarge        # unlocks, then returns from the function
}                                             # unlocks at the end of each iteration
```

To release earlier, end the block sooner with braces. Today the same region needs a helper function, and a helper cannot `break` the caller's loop or return from the caller.

### Transaction

Before:

```dewy
let tx = db.begin(p"ledger.sqlite") or_throw
defer tx.rollback_unless_committed()          # forget it and the connection stays locked
tx.execute(debit) or_throw;
let target = tx.find_account(to) ??<none> return none
tx.execute(credit(target)) or_throw;
tx.commit() or_throw
```

After:

```dewy
let tx = db.begin(p"ledger.sqlite") or_throw
tx.execute(debit) or_throw;
let target = tx.find_account(to) ??<none> return none   # rolls back
tx.execute(credit(target)) or_throw;
tx.commit() or_throw                          # the only way anything is published
```

### One-off "done"

Before and after are the same; this is what `defer` remains for:

```dewy
scan = (rows:array<string>) => {
    defer printl"done"
    loop row in rows { if row =? "bad" return Invalid }
}
```

## Rules

1. **Owners.** A value whose type has a `$__drop__` hook (or its `$__abandon__` form, rule 6) owns its cleanup. Moving it transfers the duty. A returned owner belongs to the receiver once the hand-off succeeds. A whole-value operation (`write_bytes`, `copy_to`, `run`, `capture`) completes its own owners before it returns.
2. **Two lifetimes.**
   - A *release owner* has a zero-argument, non-failing hook and is not a lent guard. It is released after its proven last use, as today.
   - A *held owner* is held to the end of the innermost block that holds its binding. Three kinds are held owners:
     - an owner whose hook can fail (`void | E`);
     - the guard that a place-lending method keeps (`@(m.lock())`, `lock_all`, `try_lock` in a `match` arm);
     - a record, array, union or closure that contains a held owner.
   - The innermost block means a function body, loop body, branch or arm, or plain braces. Some bindings have other limits:
     - an inline `f(@(m.lock()))` holds its guard only for its statement;
     - a `let` lifted out of a `parallel` block is held to the end of the block around the `parallel`;
     - an item's own locals end with that item.
   - Braces shorten any hold.
3. **The category is fixed by the concrete type.** For a union, the most conservative alternative decides, and narrowing does not change that. Optimization never changes a category. Hover, generated docs and inlays show the category for each instance, with the exact block end and any failure kinds.
4. **Completion failures are function results.**

   | Requested exit | Completion succeeds | Completion fails with F |
   |---|---|---|
   | Return or fall through with success R | R | F replaces R; a withheld owning R is completed too |
   | Return or `or_throw` a failure E | E | `CleanupError[primary=E cleanup=F]` |
   | End of an inner block | Continue after the brace | Return F from the function |
   | `break` or `continue` crossing held owners | Take the jump | Return F from the function |

   Nothing resumes after a failed exit. To recover locally, call the owner's consuming `close` before the brace and handle its result. Several failures fold in execution order. A failure with nothing pending is returned **as itself**, never wrapped.
5. **`CleanupError`** is an ordinary error: `type of error & [primary:exception cleanup:exception message:string="cleanup also failed"]`. Each pair also carries one bit saying whether either cause is, or carries, `Canceled`. Rule 7 says what that bit does.
6. **Abandoning owners.** A type whose drop discards unfinished work marks its hook `$__abandon__` instead of `$__drop__`. The lifecycle is the same as a drop hook; only the warnings differ. Examples are rolling back a transaction, and stopping and reaping a child process. The work takes effect only through an explicit consuming method (`tx.commit()`, `child.wait`, `child.stop()`). The compiler warns in two cases:
   - no path consumes the owner;
   - a success-shaped exit leaves after a mutating use without consuming the owner. Success-shaped exits are return of a value, fallthrough, `break`, `continue` and `exit(0)`. Failures, `none` and paths that call the explicit `tx.rollback()` do not warn.

   Drop hooks take no outcome parameter.
7. **Cancellation travels inside pairs.** Wherever bare `Canceled` passes through without being defaulted, a pair that carries it passes through too, whole:
   - `??`, `?? void`, `?? return/break/continue`;
   - `??<E>` without `Canceled`;
   - collectors.

   `??<Canceled>` covers bare `Canceled` only. `??<Canceled | CleanupError>` covers a carrying pair. `or_throw<Canceled>` forwards both. `is? error` and `error` arms treat a carrying pair as they treat `Canceled`. `$explicit_cancellation` reports these places with its existing fix-it. A carrying pair that reaches `main` reports both causes and exits with the cleanup failure's code.
8. **Grace.** Cleanup on a normal exit has no deadline. Once the task is canceled, before or during cleanup, the rest of that unwind shares **one** 100 ms grace. When the grace expires:
   - unfinished completions fail with `Canceled`, and those failures pair;
   - immediate local releases still run;
   - nothing is detached or retried.

   `exit` and panic run the same cleanup plan. A completion failure during `exit(0)` makes the exit status a failure.
9. **Mutation and hand-off.** Replacement owns the new value, completes the old one, and publishes the new value *before* forwarding the old one's failure. A pending returned owner is completed if another cleanup fails before the hand-off.
10. **`defer` stays narrow.** It must be non-failing and `void`, with no `return`, `break`, `or_throw`, panic or exit inside. It runs before the local owners complete (LIFO). Library resources never depend on a `defer`.
11. **Channels.** Dropping an spsc end closes the queue, as decided. Shared `Channel` and `mpmc` keep explicit close.

## Review findings and how each is resolved

### M1: cancellation hidden in CleanupError

The fix is rule 7. Each pair carries a cancellation bit, and every rule that keeps `Canceled` from being defaulted applies to a carrying pair. That covers `??`, `?? void`, `?? return/break/continue`, `??<E>` without `Canceled`, collectors, `is? error` narrowing, `error` arms and `$explicit_cancellation`. The static summary of each `CleanupError` alternative records whether it can carry `Canceled`. Hover on a `??` lists what it covers and what it forwards, so `$explicit_cancellation` diagnoses the place without scanning user records.

The review's case, in program 22:

```dewy
save = (path:Path text:string) => {
    let out = files.open(path 'w') or_throw
    out.write_text(text) or_throw;
    check_cancel() or_throw          # Ctrl-C: Canceled is leaving
}                                    # flush fails: CleanupError[primary=Canceled cleanup=FileError]
main = () => {
    save(p"/dev/full" "text") ?? void    # forwards the pair, as or_throw would
    printl"saved"                        # not reached
}
```

Without Ctrl-C, the `??` defaults the plain flush `FileError` as usual. Under `$explicit_cancellation` the `??` line is an error with the existing fix-it, `save(...) or_throw<Canceled> ?? void`.

A handler consumes a carrying pair only by naming both kinds, `??<Canceled | CleanupError>`. It then holds a value with both causes, which it can report. The task stays canceled, so its next cancellation point gives `Canceled` again. `??<Canceled>` alone covers only bare `Canceled`. That keeps program 07's stop-and-wait pattern from mistaking a failed cleanup for a clean stop.

The relaxed alternative would let `??` default carrying pairs. It is rejected because it breaks batch 4's "Ctrl-C must never become a default value".

### M2: transactions committed on any non-failing exit

The fix is rule 6. **Cleanup and publication are separate.** A drop hook never commits. Rollback is the transaction's cleanup, and `tx.commit()` is the operation's own explicit step. Forgetting the commit is safe, because nothing is published, and the compiler warns. Programs 10, 20 and 24 show this. The exits the review asked about:

| Exit before `tx.commit()` | Result | Warning |
|---|---|---|
| `return none` / `??<none> return none` | rolled back | none (absence is not success) |
| `return InsufficientFunds`, `or_throw` | rolled back | none |
| successful early `return value` after a change | rolled back | "this return rolls back tx after a change; commit, or call tx.rollback() to mean it" |
| `break` / `continue` crossing tx | rolled back | same, naming the jump |
| `exit(0)` | rolled back | same; an explicit `tx.rollback()` documents a dry run |
| `Canceled`, panic | rolled back within the grace | none |
| no path commits at all | rolled back | "tx is never committed" at `db.begin` |

A failed rollback is a completion failure: it replaces success, pairs with a failure, or turns `exit(0)` into a failure. `commit` consumes `tx`. If COMMIT fails, `commit`'s own exit drops the transaction it still owns, which rolls back, and a rollback failure pairs there. A connection lost during COMMIT gives `CommitUnknown`, and nothing retries.

**The `successful:bool` parameter is dropped.** Transactions no longer need it. Child processes don't either. Their drop stops and reaps the child: it closes stdin, requests a stop, waits within the grace, kills and reaps. `child.wait`, which already exists and gives the status, consumes the child, and so does `child.stop()`. A child that no path waits for or stops gets the same warning (program 23). Waiting on drop would need the outcome bit and would hang on a failure exit with a long-running child. Stopping on drop is the safe default. The status is a result the program needs anyway, and `run`/`capture` already wait as whole-value operations.

Removing the bool also removes the outcome-aware hook contract, the hook-before-fields publication problem (S4), and "success" as a category that `none`, `exit(0)` or `break` could fall into.

The marker is new. It is needed because no existing construct separates "dropping discards work" (a transaction) from "dropping completes work" (a file). Both have a consuming method (`commit`, `close`), so warning on every unconsumed owner would flag every file. `$__abandon__` is a compiler-only hook name in the `$__drop__` family. Only library authors write it, and it is **not yet cold-read**. Other candidates for that reading are `$__discard__` and `$__rollback__`.

### S1: locks

The fix is rule 2's guard clause. **This changes the decided loan rule.** Today a lending method's kept locals are "kept until the place's last use" (LANGUAGE.md 1115–1118, ownership.md 246 and 395). They are now kept to the end of the block holding the `let`. The *place* still ends at its last use for aliasing, so after that point the receiver can be passed whole, and only the guard is still held. Inline `f(@(m.lock()))` is unchanged (statement), and a `match @(m.try_lock())` arm holds to the end of the arm. Program 04 shows a protected region with an enclosing `break` and `return`.

Costs, stated plainly:

- **Hold time and contention.** Code written as `let a = @(m.lock()); a += 1; long_work()` now holds the lock through `long_work`. Braces release it earlier.
- **Deadlock checks** (LANGUAGE.md 3586–3595) cover the whole held interval. A second `lock` of the same mutex, joining work that takes it, or opposite-order locking anywhere before the block end is an error, where today the interval ends at the last use.
- **Warnings.** A blocking wait (`sleep`, channel, join, another lock) after the place's last use and before the block end warns: "ledger's lock is held past its last use (line N) across a wait; end the block after line N". I/O past the last use gets an editor hint marking the held region, and is reported under `$no_hidden_costs`. It is not a default warning, because protected tail I/O is exactly the case S1 asked for.
- No runtime cost beyond the longer hold: no registration, and no counter.

Owners that only hold storage (memory, sockets, spsc ends, textures) keep last-use release.

### S2: lifetime category visible for generic instances

Rule 3. The concrete instantiated type's conservative summary decides the category; for a union it is fixed by the type, not by narrowing. Hover on an owning parameter lists one line per instance the program uses: "released after its last use (line 6)" or "held to the end of first_chunk (lines 8–9); completion may give FileError". Generated docs do the same for documented instances. The generic itself never guesses for unseen types. A callable keeps the instance's full result union, and converting it to a function type that drops `FileError | CleanupError` is an error. A held owner that is never read is kept and gets no "remove unused binding" fix. A release owner that is never read warns "released right after it is made". Program 18 shows the generic with two instances (plus a union instance), the callable, a never-read owner, and this diagnostic on a declared result:

`source's close can fail while read_bytes's FileError is leaving; the pair CleanupError is not in :>array<uint8> | FileError | Canceled (source owned from line 11)`.

The category is shown as information; it is not a performance warning.

### S3: bindings lifted out of `parallel`

Rule 2's lifted-`let` clause. A top-level `let` in a `parallel` block belongs to the block that encloses the `parallel`. An item's own locals and temporaries complete when that item finishes, before the join. The cleanup edge is generated at the enclosing block's exit before dependency analysis, so the hook's effects are ordered after every later use. An item's `or_throw` keeps its decided target (the enclosing function). Program 19 traces three cases:

- an item fails before acquisition, so the binding is never initialized and nothing completes;
- an item fails after acquisition, so the binding is completed on the way out and a flush failure pairs;
- the acquisition itself fails, so the sibling's own locals complete inside it.

### S4: dependent fields under an outcome-aware hook

Gone with M2's fix. No hook publishes, so the order of fields cannot publish early. A record that owns a transaction and an audit file publishes through its own `$__consume__` method, in the order it chooses: close the audit first, then commit (program 24). If it never publishes, the fields drop in reverse order: the audit flushes and the transaction rolls back. Two such records are independent, and there is no atomicity across them or across the file and the database.

### S5: D4 rewrite

Program 21 is D4's capture program, rewritten:

- `defer net.tcp_close(stream)` is removed; the stream is a release owner.
- `defer completed.close()` and the explicit close are removed; the queue is `spsc<Path 4>.split`. The once-run lambda `app.spawn(() => progress(reports))` moves the receiver into the task, which avoids partially applying an owner.
- The sender is a release owner, so it drops after the loop, its last use. That closes the queue before `reporter.wait()` joins.
- A failing fetch leaves `main`. The sender drops and closes the queue, and `main`'s return stops and joins the program-owned reporter.
- D4's `fetch` returned `write_bytes`'s byte count, which does not fit a `Path` queue, so the rewrite returns `output`.

In D4's first program, `ticks_with_autosave` drops `defer tick.stop()`. The ticker is a release owner whose last use is the loop:

```dewy
ticks_with_autosave = (group:Tasks) => {
    let saver = group.spawn(@autosave)
    let tick = ticker(500ms)
    loop i in [0..4) tick.next or_throw;
    saver.stop()
}
```

The chat and command `Channel` closes in D4 stay as written (the shared-channel carve-out).

### S6: program 09

Program 09 is marked **blocked** on the separate encapsulation question; its header says so. It is graded K2 (blocked) and is not counted as a solved case. The rest of the design does not depend on it.

### S7: the approval delta

See "Semantic changes for David" below. Each item is marked as a change to a decided rule or a detail that was unspecified before. The documents to update are listed after it.

### N4: a real temp-file owner

Program 06 now has `stage` (a temp directory) and `archive` (a temp file inside it, `stage.temp_file(...)`). Each has its own fallible removal duty. The program publishes atomically with `write_bytes` and traces the order: `archive` completes before `stage`. It also traces the four failure combinations and Ctrl-C. A copied `Path` never carries deletion authority.

### Cold-read lesson: is the flush error `save`'s own result?

Rule 4 now says it in one line: a failure with nothing pending is returned as itself. Three places show it:

- The result type in hover lists each kind's sources, e.g. `FileError: open, write, or out's flush at line 4 (as itself when nothing failed before)`.
- An inlay at each exit that completes a held owner reads "out completes here: may give FileError".
- The `CleanupError` line in hover reads "only when an earlier failure is already leaving".

Program 01 states the contract.

## Semantic changes for David

Each item is one sentence. **[change]** alters a decided rule; **[new]** settles something that was unspecified.

1. **[change]** `$__drop__` hooks may return `void | E`, where ownership.md and LANGUAGE.md now require non-failing `void`.
2. **[change]** An owner whose hook can fail is held to the end of its block instead of released at its proven last use.
3. **[change]** A lending method's kept locals (lock guards) are held to the end of the block holding the place instead of until the place's last use; the place's aliasing limits still end at its last use.
4. **[new]** A completion failure replaces a success; it pairs with a failure that is already leaving; and when it fails on a `break`/`continue` or at an inner block's end, it returns from the function. Nothing resumes.
5. **[new]** `CleanupError` with `.primary` and `.cleanup` holds two failures, folded in execution order. A lone completion failure is returned as itself.
6. **[change]** A `CleanupError` carrying `Canceled` passes through `??`, collectors and `?? return/break/continue` as `Canceled` does. Only `??<Canceled | CleanupError>` consumes it, and `$explicit_cancellation` reports it.
7. **[new]** A hook marked `$__abandon__` discards unfinished work. The compiler warns when no path consumes such an owner, and when a success-shaped exit abandons it after a change.
8. **[new]** A transaction's drop rolls back and only `tx.commit()` publishes, on every exit including `none`, early return, `break`, `continue` and `exit(0)`.
9. **[new]** A `Child`'s drop stops and reaps it, and `wait` or `stop()` consumes it.
10. **[change]** The 100 ms cleanup grace (LANGUAGE.md 3655) applies only once the task is canceled. It is shared by the whole unwind, and normal-exit cleanup has no deadline.
11. **[new]** `exit` and panic run the same cleanup plan. A completion failure during `exit(0)` makes the exit status a failure.
12. **[new]** Replacing an owner through a place publishes the new owner before forwarding the old owner's completion failure. The mutation is not undone.
13. **[new]** A returned owner whose hand-off is blocked by another cleanup failure is completed, and its failures join the same pair.
14. **[new]** A `let` lifted out of a `parallel` block is held to the end of the block around the `parallel`; an item's own locals complete in the item.
15. **[new]** Hover and generated docs show each owner instance's category, its block end and its failure kinds; a union takes its most conservative alternative.
16. **[change]** `defer` stays, restricted to non-failing `void` actions with no control transfer, and no library resource relies on it. This replaces batch 7's "stays for now".
17. **[unchanged, stated]** Shared `Channel` and `mpmc` keep explicit close; only spsc ends close on drop.

Withdrawn from round 4: the `successful:bool` hook parameter, and commit-on-success.

### Documents to update once accepted

- **LANGUAGE.md**, sections:
  - places and locks, 1110–1161 and 3571–3587: the held-to-block rule and the `lock_all` comment;
  - "Records and collections", 2090–2200: fallible hooks, `$__abandon__`, held versus release owners, lifting the container no-fail restriction;
  - cancellation, 3653–3670: grace and carrying pairs;
  - `??`, 4693–4707: carrying pairs;
  - errors: completion failures and `CleanupError`;
  - files, processes and networking, 4350–4410: stream owners, `Child` drop, no mandatory closes.
- **docs/design/ownership.md**: "Drop hooks cannot forward errors" (around line 87), and the loan sections around lines 246 and 395.
- **docs/design/user_managed_storage.md**: the non-failing drop requirement, around line 40.
- **open_decisions.md D4**: the two programs above.
- **decisions.md**: when accepted, record this as David's with its date and supersede batch 7's cleanup direction.

## Names

- `CleanupError`, `.primary` and `.cleanup` passed a cold read (3 of 3 readers).
- `$__abandon__` is new and **not yet cold-read**; run the kit before it reaches open_decisions.md.
- The library members in the programs are sketches of library contracts, not a naming ballot: `db.begin`, `tx.commit()`, `tx.rollback()`, `child.stop()`, `files.open`, `files.temp_dir`, `stage.temp_file`. `Child.wait` and `spawn` already exist.

## Cost

- **Release owners** cost what they cost today.
- **Held owners** add a branch at each exit, and a failure merge only where a reachable hook can fail. There is no heap registration per owner.
- **Pairs** allocate only when two failures coincide, under the existing allocation-failure policy, with a non-allocating emergency report path.
- **Lock guards** add only hold time.
- **Warnings** fire for:
  - material retention;
  - waits past a guard's last use;
  - a foreign completion that may run past the grace;
  - pair storage under `$no_hidden_costs`.
- **Compiler.** Lifecycle summaries are cached per concrete type. Cleanup edges are generated before result-type inference. The added work is linear in the live cleanup actions, plus a monotone union of failure sets over reachable call edges. Analysis runs only where a type has a hook.
- **Measurement.** Nothing has been measured. An implementation must pass the flagship instruction-count panel and the full, bootstrap and fixed-point gates before it lands.
- **Acceptance tests** to write:
  - return, break, continue and fallthrough with failing completion;
  - a carrying pair through `??`, collectors and `$explicit_cancellation`;
  - the transaction exit table;
  - a guard held past its last use with a wait warning;
  - a lifted parallel binding;
  - a generic with two instances.
