# Review: cleanup round 9, design (g)

**Verdict.** (g) is the right shape for David's notes (obligation on the type, one `defer` per value, no fallible implicit cleanup, no automatic join). It is not ready to adopt as the D40 Q1 and D42 text. Three holes change behavior: a deferred failure can drop an owing return value; a drop hook can publish on a failure exit, and a race still throws away a failed removal of unpublished bytes; a mixed `ErrorStack` has no law for `??<E>`, `or_throw<E>`, or `is?`, and breaks the taken `is?` rule. The write-up also says a defer both replaces a success and "can't change a success value," and it grades editor hints as obviousness.

Read: `answers-r8.md`, `round8.md`, `review-round8.md`, D40 and D42, `round9.md`, all of `programs-r9/`. Paper programs only.

## 1. Soundness

The per-exit check is the right check, and it holds on the paths the programs actually write: conditional move (`rotate`), loop `break`/`continue` (07), a generic drop of `T` (03, 08), a generator suspension whose body has `defer` (08), a closure or task that takes a moved owner (10), a field consumed inside `$__drop__` (11), and a later `open` failing before a single bottom `defer` exists (06, 13A).

It does not hold for these:

**A defer replaces an owing value.** Defers run after the exit value is computed, and a failure replaces a success (13, the David box). The replaced value is "dropped."

```dewy
handoff = (dir:Path) => {
    let receipt = files.open(p"{dir}/r.txt" 'w') or_throw
    defer receipt.close() or_throw
    let body = files.open(p"{dir}/body.txt" 'w') or_throw
    body.write_text("x") or_throw;
    body                                  # move: body is accounted for by the return
}                                         # receipt.close fails: body is dropped, flush and all
```

The checker saw a move, so it required no `defer` on `body`. The move does not happen. Implicit cleanup cannot fail, so the flush is gone and the obligation has left the check. The same hole is a block value, a `yield` of a writer while another defer is live, and `return summarize_empty(dir)` when that call returns a writer or a record that holds one. Folding a failure into a failure is specified; folding a failure over an owing success is not. D42's narrow rule already drops a combination that was the result. Say so, and reject an exit whose value owes if any live defer can fail ("close `body` before this return").

**A hook can publish on the way out.** Rule 5 forbids `defer tx.commit()` because commit publishes. `defer drop(archive)` is the recommended form, and program 11's `$__drop__` writes the footer and then closes. `pack`'s `add` fails, the defer runs, and a partial archive gains `count N`. The checker only sees that the fields were consumed. Round 8's "drop hook that commits" is still open: rule 5 does not look inside `$__drop__`. A publishing call inside a drop or abandon hook has to be an error. The footer belongs in a `finish` that a defer cannot call.

**Race losers still lose a real failure.** `backup_to` writes `defer tmp.discard() or_throw`, so the check is satisfied. `first_ok` then discards the loser's result (D44 Q6). A failed removal is `FileRemoveFailed`, a leftover, not `UndoFailed`, so the discard is legal and silent: no warning, the defer was present, the temp file and its bytes remain. That is the case round 8 asked to be named. Program 02's warning covers only a missing defer. Classifying "removal of unpublished bytes" as `UndoFailed`, or not discarding leftovers that are undos, closes it. A final-path `FileWriter` in a raced body is the same discard; the lint being out of scope does not make the loss sound.

Smaller gaps, not the top three. `defer out.close();` meets the check and drops the flush; `$no_discarded_failures` is not said to reject it. Overwriting a collection element is an error; overwriting a field, and `defer p.main.close()` versus `drop(p)`, are unspecified (double close or a missed field). A one-bit "may drop `T`" is sound and conservative. An owing value moved into storage no function exit covers is not discussed.

## 2. Nonlocality

David's test was the text alone, ordinary control flow. (g) fails that test in two places the write-up calls successes. It does match the timing he wrote down in `answers-r8.md`. Those are different claims. Do not tell him it passes.

**The return line.** `return summarize_empty(dir)` and `return i` (01) can come back as `FileCloseFailed` or an `ErrorStack`. Nothing on those lines says so. The `or_throw` sits on an earlier `defer`, which did not run when execution passed it. An editor hint is how the study lifts 13 from obvious 4 to 5, and how it excuses 08 staying at 4 ("naming it in the text would need new syntax"). The hint is not in the text. Python's `with` indents the region; `defer` does not.

**A move turns the defer off.** In `open_shards` the defer is directly above `shards`, the value returned. A reader who knows Go will think the function closes the files it returns. The cancellation is a second, unwritten rule, and it is load-bearing: it is why one defer works for constructors and why a transaction defer is `errdefer` with no keyword. File writers, transactions, and returned owners share one spelling and three sets of exits. You cannot see which from the defer line. `continue` in 07 can leave the function for the same reason; 07 calls that "the visible exit D40 Q6 asked for," but the `continue` line is still a continue.

There is also a contradiction in the recommendation itself. Summary §6 and recommendation point 5: a defer "can't change a success value." §3, program 13, and the David box: a failure replaces that value. The second is the real rule. The first will be implemented by someone.

## 3. Type split

Separate types at construction fix the round-8 hole the programs hit. `FileReader` owes nothing, `FileWriter` and `'a'` owe a flush, `'rw'` is a `File` that owes as a writer, `finish_sending` consumes a `Socket` and returns a `SocketReader`. Generic code sees a bit, not a mode. Typestate stays rejected for the right reason.

It does not yet cover the rest of that hole:

- Pipes and a child's stdin are absent. `wait` consumes a `Child` (12) with nothing said about flushing the write end. A pipe writer is the review's case, not a file opened `'w'`.
- A live `Socket` owes a finish even when nothing was sent (`headlines` calls `finish_sending` for an empty send). That is the cost of skipping typestate, and it is honest. The programs never read before the finish. SMTP-style interleaving is impossible unless `Socket` can receive while it still owes, which is unstated; `split` covers only the parallel case.
- TLS `close_notify` is part of `Socket`, not of a wrapper. A `Tls` over some other stream owes only if its type says so. The field/hook rule can express that; nothing shows it.
- A dynamic open mode has no type. Fine if the mode is always a literal.

Ergonomics are acceptable for files and for a connect/send/finish/read upload (05). They are not yet a library model. `'rw'` always paying a writer close is the right conservative default.

Abandon-as-RST on a failed upload is a protocol choice, not a missed check: the failure path owes an infallible abort, so there is no flush error to report. The buffered tail is discarded on purpose. Don't blur that into "close can't fail."

## 4. One failure, or an `ErrorStack`

Bare singleton, ordered stack for two or more, `Canceled` beside the stack: that matches David's sketch and avoids D42's 2ⁿ shapes. `??<FileCloseFailed>` taking one close and forwarding two is still Q6, and it is the right default so `c.path` stays a single path.

The new part is that unlike kinds share that stack. Today a body failure and a cleanup failure are `Declined & RollbackFailed`, and the taken rule is that `is? Declined` is true when any part matches, while `??<Declined>` forwards the pair. Under (g), program 04's low balance plus a failed rollback is `ErrorStack[Declined RollbackFailed]`.

```dewy
transfer(db req from to amount) ??<Declined> (d) => "balance {d.balance}" or_throw
```

Q6 says a handler does not look inside a stack, so this arm does not run. `is? Declined` is not defined for stack elements. If it does not look inside, the decline disappears from the test the caller already knows how to write. The spelling Q6 told people to use, `??<FileCloseFailed | ErrorStack<FileCloseFailed>>`, does not match `ErrorStack<FileWriteFailed | FileCloseFailed>` either. `or_throw<Declined>` selects an `E` part; a stack is not one.

So the D42 change is not "Q6, but ordered." It deletes `&` as the way unlike cleanup failures combine, and it does not replace the matching rule. Flatten versus nest when the body already returned a stack is also unstated, against the taken "a stack may nest."

Settle the law before this is a D42 recommendation. The smallest law that keeps Q6's binding rule: `is?` sees stack elements the way it sees `&` parts; `??<E>` and `or_throw<E>` still consume only when every element is needed to make `E`, so a mixed stack is forwarded whole; an arm `c:FileCloseFailed` never receives a stack. Order stays. `c.path` stays safe. Without that paragraph, (g) is a silent change to a taken rule.

## 5. Grades

The arithmetic is real: five 4s (02 and 04 and 12 concise, 08 obvious, 11 concise), so 60 of 65 cells are 5. The spot check does not support the 5s.

| Program | Cell | Claim | Reading |
|---|---|---|---|
| 01 | obvious 5 | `return i` then the close | same replacement as 13, which was a 4 before the editor hint |
| 05 | obvious 5 | no defer on `conn` | looks like a leak until the abort rule is known |
| 07 | obvious 5 | `continue` | can leave the function; the line still says `continue` |
| 10 | safe 5 | `first_ok` | loser's `FileRemoveFailed` is discarded with the defer present |
| 11 | complete 4→5 | hook consumes fields | footer still runs after a failed `add` |
| 13 | obvious 4→5 | exit hint | the hint is not the language; 08 was refused this move |

02, 04, and 12 at concise 4 are fair. 06's discoverable 4→5 is fair: the error names `main` at the second open. 03's 5s hold only while `db.scan` really finishes its send inside the library; the user's function cannot show that. A recount of the six cells above is 54 of 65, and that is only the spot check.

## 6. Simpler, or better

(g-auto) is the simpler variant already measured (12 fewer lines). It puts a flush or a rollback on a failure exit that does not mention it. That is the obscurity David flagged. It is also the reversible direction the wrong way: adopting it first means later explicitness rejects programs. Keep it as the alternative in the question, not as the recommendation.

Do not add `errdefer`. The move-cancels rule can stay; the recommendation has to show, on one program, the three exit sets of one spelling.

The design to take forward is (g) plus three constraints, not a new mechanism: no failing defer on a scope whose exit value owes; no publishing call in a drop or abandon hook; stack matching specified as in §4, or unlike kinds stay `&` and the stack is only for duplicates. The second of those keeps today's handlers and drops order. David asked for order. Give him the matching law, not `&` again.

## What must change first

1. **Replaced values.** A deferred failure may replace a success only when that value owes nothing. Otherwise the program is an error, or the value's own cleanup joins the stack. Specify this for `return`, block values, and `yield`.
2. **Failure exits must not publish, and must not swallow an undo.** A publishing call inside `$__drop__` or `$__abandon__` is an error (11's footer moves to `finish`). A failed removal of unpublished bytes is an `UndoFailed`, so `first_ok` cannot discard it.
3. **The handler law for a mixed stack,** in the form in §4, written against `??<E>`, `or_throw<E>`, and `is?`, before D42 Q6 is edited. While that is open, (g) is not a D42 recommendation.

Also, before it is shown as decided: fix the "can't change a success value" sentence; stop counting editor hints as grades; cold-read the new names, as the study already says. The citation repairs in §1b were not re-checked here.

Not ready to bring to David as the decision. Ready to bring as the direction, with these three still open.
