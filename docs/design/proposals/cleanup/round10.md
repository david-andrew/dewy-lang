# Cleanup round 10: closing round 9's holes

A delta over [round 9](round9.md), after its [review](review-round9.md) and
[cold read](cold-read-round9.md). Changed and new programs: [programs-r10/](programs-r10/).
Programs not listed there are as in [programs-r9/](programs-r9/README.md).

## Summary

1. (g) stands as the direction: what a value owes is in its type, one `defer` per value, nothing
   that runs implicitly can fail, nothing joins automatically. Round 10 adds three rules and one
   law; none adds syntax.
2. **A failure can't replace a value that owes.** If an exit carries an owing value out (a
   `return`, a block's value, a lazy body's item), no defer that can fail may still be live
   there. The fix is to finish the other values first. This closes the dropped-writer hole.
3. **Failure exits don't publish.** A cleanup hook may only end the value's own fields; new work
   such as program 11's footer goes in a `$__consume__` method, and calling one decides the value
   so `$__abandon__` doesn't run after it.
4. **Removing unpublished bytes is an undo.** A temporary file's or directory's failed removal is
   a new leaf, `TempRemoveFailed`, in D44's `UndoFailed` family, so `first_ok` can't discard it.
   A raced body may not hold a `FileWriter` across a cancellation point.
5. **The leftover tier is dropped.** Once removals are undos, no standard type needs a
   warning-only strength, and both names tested for it failed the cold read.
6. **Stack law:** `is?` and `or_throw<E>` look inside a stack as they look inside `&`; `??<E>`
   and an arm `c:E` never take a stack; only a handler that names `ErrorStack<…>` consumes one,
   and only when every element fits. A fold at an exit appends to a stack already leaving.
7. **The defer sentence, fixed:** a failing defer replaces the exit's success value with its
   failure. It can't swap one success value for another and can't remove a failure.
8. **Nonlocality, honestly:** (g) matches David's timing, but it doesn't pass a text-only
   reading. A `return` line doesn't show that a close may replace its value, and one `defer`
   spelling covers three different sets of exits depending on what later consumes the value.
9. **Regraded with no credit for editor hints:** 50 of 65 grades are 5. Obvious is 4 in 11
   programs, all for those two reasons.
10. **Names:** the cold read borderlines `ErrorStack`, so this round recommends `ErrorList` for D42
    Q4 (still untested). The three error messages passed, and Error 2 now says that
    `finish_sending()` consumes `conn`.

## Recommendation

(g) as in round 9, with these changes:

1. **Exits that carry an owing value.** At an exit that carries a value whose type owes out of
   its scope, no defer whose action can fail may be live. Error, naming both values, with the
   fix "finish *x* before this exit".
2. **Hooks.** In `$__drop__` and `$__abandon__`, a call that can fail is allowed only if it ends
   one of the value's fields through that field's own cleanup (`drop(f)`, or the method its type
   assigns to its hook, such as `close` or `rollback`). Anything else is an error that offers a
   `$__consume__` finishing method.
3. **Deciding.** Calling a `$__consume__` method decides the value: its `$__abandon__` doesn't
   run afterwards. That is how a user type gets `commit`- or `finish`-like methods.
4. **Undos.** Removing temporary storage fails with `TempRemoveFailed`, an `UndoFailed`.
5. **Raced bodies.** A function that `race` or `first_ok` may cancel and discard can't own a
   `FileWriter` across a cancellation point; it writes through a temporary file.
6. **No leftover tier.** Every fallible cleanup is unfinished work or an undo, and must be
   handled. `$no_discarded_failures` also rejects a written discard (`defer out.close();`).
7. **Stacks:** the law in §3, with a warning when a union handler covers every element type of
   a stack it can receive but doesn't name the stack.
8. **The defer rule, stated once:** a defer runs after its scope's exit value is computed; if it
   fails, its failure replaces a success value or joins a failure already leaving. It can't
   `return`, `break`, change a success value into another, or remove a failure.

## 1. A deferred failure replacing a value that owes

The review's case:

```dewy
handoff = (dir:Path) => {
    let receipt = files.open(p"{dir}/r.txt" 'w') or_throw
    defer receipt.close() or_throw
    let body = files.open(p"{dir}/body.txt" 'w') or_throw
    body.write_text("x") or_throw;     # also an error in round 9: body is open if this fails
    body                               # round 9 treated this as a move
}   # receipt's close fails: body never moves, and its flush is lost
```

The checker counted `body` as moved at the `return`; the move happens only if the defers
succeed. Two fixes were weighed:

| | Reject the exit | Fold the value's own cleanup |
|---|---|---|
| What happens | error at `body`: "receipt's deferred close can still fail after this, and body would be dropped unfinished; close receipt first" | `body` is cleaned up by its hook and its failure joins the stack |
| Cost | the rare function that returns an owner while holding another writes one explicit close | none |
| Fit | every failure still has a written source | `body`'s flush runs on a path no line names: the implicit, fallible cleanup (g) removed |

**Picked: reject.** It applies wherever an exit carries a value out of its scope:

- a `return` or a function body's last value;
- a block's value (`let w = { …; defer a.close() or_throw; make_writer() }`);
- an item from a lazy body when the item is the value of a scope that has its own defer (a defer
  in the loop body of `lazy loop`). A defer in the lazy body's *outer* scope is not affected: the
  item is handed over at the suspension, and the outer defer runs later.

A value whose own failure-exit cleanup is a release (a `Socket`, which aborts) may be replaced:
nothing is lost. The fixed `handoff`, in
[programs-r10/14_handoff.md](programs-r10/14_handoff.md):

```dewy
handoff = (dir:Path) => {
    let receipt = files.open(p"{dir}/r.txt" 'w') or_throw
    defer receipt.close() or_throw
    let body = files.open(p"{dir}/body.txt" 'w') or_throw
    defer body.close() or_throw        # failure exits only: the return below moves body
    body.write_text("x") or_throw;
    receipt.close() or_throw           # finished here: its defer is off, and if it fails, body's defer closes body
    body
}
```

None of round 9's programs hit this: in 06 and 11 the only live defers belong to values the
return moves.

## 2. Failure exits don't publish, and undos aren't discarded

### Hooks may only end fields

Program 11's `$__drop__` wrote the archive's footer, so `defer drop(archive)` after a failed
`add` published a partial archive with a count. Rule 5 checked `defer` lines but not hooks. Now
a hook may only end the value's fields through their own cleanup; the footer is new data, so it
is an error there:

```text
error: Archive's $__drop__ runs on failure exits, and index.write_text (line 9) writes new data.
       Move it into a finishing method:   $__consume__ finish = () => { … }
       and close the fields without it:   $__abandon__ = () => { … }
```

Flushing what a field already holds is that field's own cleanup, so `FileWriter`'s hook (and any
hook that closes a writer field) stays legal. The standard library's primitive hooks (the native
flush) are where the rule bottoms out.

`Archive` becomes a type with unpublished work: `finish` writes the footer and closes,
`$__abandon__` closes without it, and calling `finish` decides the archive so the abandon doesn't
run after it. This uses LANGUAGE.md's existing `$__consume__` marker; the one new piece is that a
consuming call counts as the decision that batch 9's `$__abandon__` waits for. Forgetting
`finish` is rule 5's usual error. [programs-r10/11_wrapper_type.md](programs-r10/11_wrapper_type.md).

This also answers round 8's "a `$__drop__` that commits": it can't.

### Removing unpublished bytes is an undo

`backup_to` wrote `defer tmp.discard() or_throw`, passed the check, and `first_ok` then threw
away a failed removal, leaving the temporary file and its bytes on disk with no word. Removing a
temporary file or directory undoes its creation, and a failure leaves the effect in place, which
is D44's definition of `UndoFailed`. So `TempFile.discard()`, `TempDir.remove()` and their
abandons fail with a new leaf:

```dewy
TempRemoveFailed:type = type of FileError & UndoFailed
```

A plain `files.remove(p)` keeps `FileRemoveFailed`: it isn't an undo. Under D44 Q6, `first_ok`
can't discard a loser's `TempRemoveFailed`; the loser handles it, as for a failed rollback
(program 10).

### Raced bodies don't hold final-path writers

The other half of the review's race case: a loser writing a `FileWriter` to its final path is
canceled, and the half-written file stays whatever its flush does. Round 9 left a lint out of
scope; it is a rule now:

```text
error: first_ok can cancel copy_to (line 12) while it holds out (FileWriter, line 3).
       A canceled copy would leave /mnt/b/backup.bin half written, and first_ok discards its result.
       Write through a temporary file:  files.temp_beside(path) … persist(path)
```

Only values the raced function *owns* count; a log it borrows belongs to someone outside the
race. The check is a per-function bit, "owns a `FileWriter` across a cancellation point",
computed only for functions reachable from a `race` or `first_ok` argument. `parallel` siblings
are unaffected: their failures are kept (D44 Q8), not discarded.

### The leftover tier

Round 9's only leftovers were temporary removals. With those classed as undos, no standard type
needs a warning-only strength. Both names the cold read tried (`Leftover`, `CleanupLeftover`)
failed, 0 of 3. **Dropped.** David's idea of a weaker, warning-only obligation stays available
if a real type ever needs it; it would get a name and a cold read then.

## 3. The handler law for a mixed stack

Round 9 put unlike failures in one ordered stack (`ErrorStack[Declined RollbackFailed]`) without
saying how handlers see it, which broke the taken rule that `is?` sees a part. The law, keeping
D42 Q6's binding rule:

| Form | On a stack |
|---|---|
| `x is? E` | true when some element is an `E`, at any depth (as for `&` parts) |
| `x or_throw<E>` | forwards the stack whole when some element is an `E` (it selects, as `is?` does) |
| `x ??<E> v`, with `E` naming failure kinds | never consumes a stack; the stack is forwarded (D42 Q6) |
| `x ??<ErrorStack<A \| B>> v` | consumes the stack when every element is an `A` or a `B` |
| `match` arm `c:E` | never receives a stack, so `c.path` is always one path |
| `match` arm `s:ErrorStack<A \| B>` | receives a stack whose every element is an `A` or a `B` |
| `x as E?` | the element that is an `E` when exactly one is, else `none`; `x as E` (no `?`) is a compile error on a stack, which can't prove uniqueness |
| `x.$parts` | the elements, in order |
| `Canceled` | never in a stack; beside it: `Canceled & ErrorStack[…]` (D44) |

Selecting (`is?`, `or_throw<E>`) looks inside because it loses nothing; consuming (`??`, arms)
needs the stack named, because a handler written for one failure must not swallow a second.
[programs-r10/15_mixed_stack.md](programs-r10/15_mixed_stack.md) runs program 04's low balance
plus failed rollback through each form:

```dewy
let r = transfer(db req from to 500)
if r is? Declined printl"declined"                       # true for [Declined RollbackFailed]
r ??<Declined> 0                                          # doesn't consume it: forwarded
r ??<ErrorStack<Declined | RollbackFailed>> 0             # consumes it
```

Today's `Declined & RollbackFailed` behaves the same for the first two forms (the narrow rule
forwards the pair); the difference is that the order is kept and the type doesn't grow as 2ⁿ.

**Nesting.** A fold at an exit appends: if the failure leaving is already a stack (a callee
returned one) and a defer fails, the defer's failure is appended to it, so `export_all`'s type
stays `ErrorStack<FileWriteFailed | FileCloseFailed>` rather than a stack of stacks. A stack a
program builds and keeps as a value may still nest (D42, taken).

## 4. The defer rule, the three exit sets, and nonlocality

**The sentence.** Round 9 said both that a failing defer replaces a success value and that a
defer "can't change a success value". The first is the rule; the second meant that a defer can't
produce a different success value. Stated once in the recommendation, point 8.

**One spelling, three exit sets.** The review asked to show it on one program. In
[programs-r10/14_handoff.md](programs-r10/14_handoff.md):

```dewy
settle = (db:Db dir:Path) => {
    let log = files.open(p"{dir}/settle.log" 'a') or_throw
    defer log.close() or_throw          # (1) every exit: nothing consumes log
    let tx = db.begin() or_throw
    defer tx.rollback() or_throw        # (2) failure exits: every success path must consume tx
    let report = files.open(p"{dir}/report.txt" 'w') or_throw
    defer report.close() or_throw       # (3) failure exits here: the return moves report out
    …
    tx.commit() or_throw
    log.close() or_throw                # §1: no fallible defer may be live where report is returned
    report
}
```

The same words on each line mean "end this value on any exit where it is still mine", and which
exits that is depends on what the rest of the function does with the value. A reader has to look
down for `commit` and for the return. Go programmers will read (2) correctly (`Rollback` after
`Commit` is a no-op there) and (3) wrongly, as closing the returned file.

**Against David's test.** His criterion was plain code in ordinary control flow, with nothing
nonlocal. (g) matches the timing he wrote down. It does not pass a reading of the text alone:

- `return i` (01) and `return summarize_empty(dir)` (13) can come back as a failure, and nothing on
  those lines says so; the `or_throw` is on an earlier line that didn't run when it was passed.
- A `continue` (07) can leave the function from the loop body's defer.
- A move or consuming call turning a defer off (above) is a second rule the line doesn't show.

What keeps it bounded: every outcome-changing defer says `or_throw` on its own line, in the scope
it affects; the live defers at an exit are those written above it for values not yet consumed;
and a defer can't do anything its line doesn't say. That is the trade any `defer` makes. The
fully local alternative is round 8's explicit finish at each exit, which costs a line per exit
and leaves failure exits to automatic joining or to a `defer` anyway. **An editor hint at each
exit helps but is not counted in the grades.**

**Tried and not taken: `errdefer`.** A second keyword would make (2) and (3) readable on their own
lines. It doesn't remove the rule, since a plain `defer` on a moved value must still be turned
off, and it is new syntax. Not proposed; noted for David as the option if he prefers visible
intent to one keyword.

## 5. The type split's remaining gaps

| Gap | Rule |
|---|---|
| Pipes and a child's stdin | `spawn(… stdin='pipe')` gives a `Child` whose `stdin` is a pipe writer that owes its flush and close. `wait()` closes it first (the child needs end-of-file before it can finish) and includes that failure in its result. Program 12. |
| Receiving while the sending side is owed | A `Socket` reads and writes freely until it is finished, so SMTP-style exchanges work; owing affects only exits. `split()` is for sending and receiving in parallel. |
| TLS over another stream | `tls.wrap(stream)` gives a type whose own finish sends `close_notify` and which holds the inner stream as a field, so it owes both by the field rule. |
| A run-time open mode | `files.open(path mode)` with a non-literal mode gives a `File`, which owes as a writer. |
| A connection's abandon | Resetting the connection on a failed upload is a protocol choice: it discards the buffered tail on purpose, so the peer sees a truncation. The failure path owes an abort that can't fail; it isn't a claim that closing can't fail. |

## 6. Smaller gaps

- **`defer out.close();`** is a written discard: allowed by default, an error under
  `$no_discarded_failures`.
- **Overwriting an owing field** (`pair.main = w`) is an error, as for elements; finish the old
  value first (`drop(pair)` and rebuild, or a method on the record type).
- **A field ended separately.** `defer pair.main.close() or_throw` and `defer drop(pair) or_throw`
  together: on a path where `main` was consumed, `drop(pair)` ends only the fields still owned,
  which the cleanup plan already tracks per field. Nothing closes twice.
- **Storage no exit covers.** An owing value always lands in some owner: a local, a field, an
  element, a channel's receiver, a task. Global owners are unsupported (LANGUAGE.md), so the
  chain ends at a function's or task's exits.

## 7. Names and messages

- **`ErrorStack`:** 2 of 3 cold readers took it for a cause chain or traceback. The stack is now
  a flat, ordered list of sibling failures, which is what `ErrorList` says. D42 Q4 already offers
  both; this round recommends `ErrorList`, pending a cold read of it (it wasn't in this one).
  `ErrorBundle` loses the order. The programs keep `ErrorStack` until David picks.
- **Leftover marker:** dropped with the tier (§2).
- **`TempRemoveFailed`:** new, untested; it needs the kit before reaching open_decisions.md.
- **`FileReader`, `FileWriter`, `SocketReader`, `finish_sending`, `drop(x)`:** passed (5, 5, 5, 4
  and 4 confidence, all read correctly).
- **Error 2**, revised as the cold read suggested:

  ```text
  error: conn (Socket, line 3) has an unfinished sending side where upload ends (line 11).
         Finishing it can fail with SocketSendFailed | SocketCloseFailed.
         Finish it:  conn.close() or_throw
         or, to read a reply:  let replies = conn.finish_sending() or_throw   (consumes conn)
  ```

## 8. Regrade

No credit for editor hints. Obvious is graded on what a reader gets from the text and the
language's rules as written; a rule the line doesn't show costs a point.

| Program | Obvious | Discoverable | Concise | Safe by default | Complete | Why not 5 |
|---|---|---|---|---|---|---|
| 01 buffered writes | 4 | 5 | 5 | 5 | 5 | `return i` may come back as a failed close |
| 02 temp file | 4 | 5 | 4 | 5 | 5 | `defer tmp.discard()` above a `persist` that turns it off; the early exit says `discard` twice |
| 03 partial read | 5 | 5 | 5 | 5 | 5 | holds while the library finishes the query's send, which the type shows and the function can't |
| 04 transaction | 5 | 5 | 4 | 5 | 5 | the replay exit rolls back explicitly; Go readers read the deferred rollback correctly |
| 05 acquisitions | 4 | 5 | 5 | 5 | 5 | no `defer` on `conn` looks like a leak until the abort rule is known |
| 06 moved owners | 4 | 5 | 5 | 5 | 5 | a `defer` above the returned `shards` reads as closing it |
| 07 loop exits | 4 | 5 | 5 | 5 | 5 | `continue` can leave the function |
| 08 generators | 4 | 5 | 5 | 5 | 5 | a mid-stream drop runs the body's `defer` |
| 09 own or borrow | 4 | 5 | 5 | 5 | 5 | `report`'s `defer` is turned off by the move into `finish_report` |
| 10 parallel, race | 4 | 5 | 5 | 4 → 5 | 5 | `backup_to`'s `defer` above `persist`; safe fixed by §2 |
| 11 wrapper type | 4 | 5 | 4 | 5 | 4 → 5 | `defer drop(archive)` above `finish`; the constructor is two bindings; complete fixed by §2 |
| 12 process, scratch | 4 | 5 | 4 | 5 | 5 | `defer tail.stop()` then `tail.stop()` reads as stopping twice |
| 13 three writers | 4 | 5 | 5 | 5 | 5 | `return summarize_empty(dir)` may come back as a failure |

**50 of 65 are 5** (round 9 reported 60; the review's spot check found 54, and regrading every
cell found more of the same). Eleven of the fifteen 4s are obviousness, from exactly the two
rules in §4. Iterations:

1. **Obvious, move-cancel.** Tried `errdefer` (§4): it fixes 02, 04, 06, 09, 10, 11 and 12 at the
   cost of a keyword, and leaves the rule in place for plain `defer`. Not taken; offered.
2. **Obvious, return replacement.** Tried requiring a mark at each `return` in a scope with a
   fallible defer: new syntax on the most common line, to restate what the `defer` line says.
   Not taken. Python's `with` has the same property (an `__exit__` exception replaces the value)
   and indents the region, which is why its readers see it; that is the honest gap.
3. **Concise 02, 04, 11, 12:** unchanged from round 9; the repeats are the forgotten-commit
   check's price, and 11's two-binding constructor is §1's rule's price.
4. **Safe 10, complete 11:** fixed by `TempRemoveFailed`, the raced-writer rule and the hook
   rule. → 5.

No further iteration reaches 5 on obviousness without a keyword or a mark at returns.

The two new programs: [14](programs-r10/14_handoff.md) (replaced owner, three exit sets) grades
4/5/4/5/5 for the same two reasons; [15](programs-r10/15_mixed_stack.md) (the stack law) grades
5/4 → 5/5/5/5, discoverable fixed by a compiler warning when a union handler covers every element
type of a stack in its input without naming the stack.

## 9. Compile-time cost of the additions

- §1: at each value-carrying exit, check whether the value's type owes and whether any live
  defer can fail: both facts are already in the per-exit plan. O(1) per exit.
- §2 hooks: one scan of each hook body when the type is checked.
- §2 raced bodies: one bit per function, computed on demand for functions passed to `race` or
  `first_ok` and their callees; cached.
- §3: handler checks gain a stack case; no new analysis.

Nothing is measured.

## 10. Consequences for open decisions

- **D40 Q1:** (g) with this round's rules. Still not a decision until David sees §4's
  nonlocality plainly.
- **D40 Q5:** `defer` stays and may fail; `errdefer` is the noted alternative.
- **D42 Q4:** recommendation moves to `ErrorList`, pending a cold read.
- **D42 Q6:** replaced by §3's law; unlike kinds share the ordered stack, and `&` stays for
  combinations people write and for `Canceled`.
- **D42, taken rule "`is?` is true when some part matches":** extended to stack elements, not
  broken.
- **D44 Q6:** `TempRemoveFailed` joins `UndoFailed`; the raced-writer rule is new.
- **Batch 9 (`$__abandon__`):** a `$__consume__` call decides the value; hooks may only end
  fields.

## 11. For David

**D40 Q1.** Turn this on, and closing a reader, aborting a connection or unlocking can never fail
and never appears. Anything whose cleanup can fail (a writer's flush, a transaction, a running
child, a temporary file) must be accounted for on every exit, or the program doesn't compile. The
usual way is one `defer` under the value; finishing or handing the value off turns that `defer`
off on that path.

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw     # runs after the result is computed; a failed close replaces it
    out.write_bytes(data) or_throw;
}
```

What you should know before deciding: the `return` line doesn't show that a close can replace its
value, and the same `defer` line covers all exits, or only failure exits, depending on whether
the value is later committed or returned. `errdefer` would make the second visible, at the cost of
a keyword.

- **Rec:** yes, without `errdefer`.
- **Reversible:** before release. Errors can become warnings later without breaking anything;
  making a release fallible later breaks callers.
- **You give up:** release errors entirely; a line per writer; repeating an abandon at an early
  success exit; returning an owner while another value's close is still pending (finish it first).

**D42.** Turn this on, and a cleanup failure joins another failure only where a written
`defer … or_throw` says so. One failure comes back bare; several from one exit come back as one
ordered list. `is?` and `or_throw<E>` look inside the list; `??<E>` doesn't, so a handler for one
failure never swallows a second.

```dewy
let r = transfer(db req from to 500)      # low balance, then the rollback fails too
if r is? Declined printl"declined"        # true
r ??<Declined> 0                          # not consumed: the failed rollback is forwarded with it
```

- **Rec:** yes, explicit, with the list named `ErrorList` (D42 Q4).
- **Reversible:** adding automatic joining later breaks no program; the reverse would.
- **You give up:** 12 lines over 13 programs; `&` across kinds for cleanup failures (it stays for
  combinations you write).

## Limits

Paper programs, not compiled; this round's own grades. Still needed before a decision: an
independent review of rounds 9–10 together, cold reads of `ErrorList` and `TempRemoveFailed`, and
a cost check on the flagship panel. The citation repairs from round 9 were not re-checked.
