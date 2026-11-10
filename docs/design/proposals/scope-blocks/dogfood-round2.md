# Dogfood, round 2

Scores are obvious, discoverable, concise, safe by default, complete. A 5 means that column needs no change. Dewy is graded against the rules in `round2.md`. A score under 5 cites the line. Nothing here is fixed by another round: each one is a rule this round kept on purpose, or a fact the language already had.

Floor is **4**.

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 REPL | 5 4 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 2 3 3 3 | 4 3 4 3 4 | 2 2 2 3 2 |
| 02 shell | 5 4 5 5 4 | 4 4 4 4 4 | 4 3 3 4 4 | 3 3 3 4 3 | 4 3 4 3 3 | 2 2 2 3 2 |
| 03 save on Ctrl-C | 5 4 5 5 5 | 4 4 3 4 4 | 4 3 3 4 4 | 3 3 3 4 4 | 4 3 3 3 4 | 2 2 2 3 3 |
| 04 early return | 4 4 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 4 4 4 5 4 | 3 3 3 4 3 | 4 3 4 4 4 |
| 05 nested catch | 5 5 5 5 5 | 5 4 4 4 5 | 3 3 3 4 3 | 3 2 3 3 3 | 4 3 3 3 4 | 2 2 2 3 2 |
| 06 game loop | 5 5 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 4 3 3 | 3 2 3 3 3 |
| 07 server flush | 4 4 5 5 5 | 4 3 3 4 4 | 4 3 3 4 4 | 3 3 3 4 4 | 4 3 3 3 4 | 2 2 2 3 3 |
| 08 CLI throw | 5 4 5 5 5 | 5 5 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 4 3 4 4 4 |
| 09 break | 4 4 5 5 5 | 5 5 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 3 3 3 4 3 |
| 10 bracket | 5 5 4 5 5 | 5 5 5 4 5 | 4 4 4 3 4 | 4 4 3 5 4 | 4 3 3 3 4 | 4 4 4 4 4 |
| 11 traced | 5 5 5 5 5 | 5 5 5 5 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 4 3 4 4 4 |
| 12 dashboard | 5 5 5 5 5 | 4 3 4 4 3 | 4 3 3 4 4 | 3 3 3 4 3 | 4 3 4 3 3 | 2 2 2 3 2 |
| 13 expressions | 5 5 4 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 3 3 4 | 3 3 3 4 3 |
| 14 comprehension | 4 4 4 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 3 3 3 | 3 3 3 4 3 |
| 15 two libraries | 4 4 4 5 5 | 4 4 3 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 3 3 4 | 3 3 3 4 3 |
| 16 return replaced | 4 4 5 4 5 | 4 4 4 4 4 | 3 3 3 4 3 | 4 3 3 5 4 | 3 3 3 4 3 | 4 3 4 4 4 |
| 17 failing close | 4 4 5 4 5 | 4 4 4 4 4 | 4 4 4 3 4 | 4 4 3 5 4 | 4 3 3 3 4 | 4 4 4 4 4 |

## Lines under 5

**01, discoverable 4, line 8.** `input("> ") ??<Interrupted>` does not say why this press is `Interrupted` rather than `Canceled`. The catcher is why. That is the existing console rule, and putting `Interrupted` on `input` only inside the catcher would make the operation's type depend on the caller, which is the same hole M2 closed for `Timeout`.

**02, discoverable 4 and complete 4, line 2.** The child getting SIGINT is stated only in that comment. Line 18 drains a queued press, so that half is in the code. There is no spelling for "this child is in the foreground process group." Python's `subprocess` call doesn't show it either. This round does not invent a process API.

**03, discoverable 4, line 15.** `write_text(...) or_throw` is a `Canceled` in `save`'s type. The match on line 24 has `<Timeout>` and no `Canceled` arm. The shield turns its own deadline into the call's `Timeout` when it closes. `save` cannot return `Timeout` itself, because `write_text`'s type does not change inside the shield (M2). The match is the call's result. The line inside `save` still reads as a failure that leaves `main`.

**04, obvious 4 and discoverable 4, line 26.** `<Canceled> => Canceled or_throw` reads as `find` returning `Canceled`. When that `Canceled` is the group's fail-fast, closing the group replaces it with `WalkError` and that is the call's result. A parent `Canceled` stays. The arm cannot say which, because the split is provenance. Lines 24 and 25 do what they look like: a path and `Closed` return from `find`, and the group is stopped before the join.

**07, obvious 4 and discoverable 4, line 36.** `return` leaves `serve`, and it also stops `accept` before the join. A plain block does not stop a task. The stop is the M3 rule that keeps this program from hanging. Writing `group.stop()` on this line would make the stop visible and would bring the hang back for every `return` that forgot it.

**08, discoverable 4, line 22.** `done.receive or_throw` looks like any `Canceled` from `receive` leaving `load`. A `Canceled` the group originated becomes `warm`'s `FileError` at the join. The header says that. The line does not. `return Missing` on line 23 really does return: `Missing` is a failure, and `warm` has already finished.

**09, obvious 4 and discoverable 4, line 14.** `probe(port) or_throw` does not leave `serve_until` when the `Canceled` is the shield's deadline. That exit becomes the `<Timeout>` handled by `continue` on line 17. A file error does leave. Lines 15 and 16 are the `continue` and `break` the round-1 program only claimed: both leave the port loop. Line 12 is the parent-cancel checkpoint between shields, so a pending parent cancel is not hidden for the whole loop.

**10, concise 4, line 24.** `bracket(@open_log(p"app.log") @close_log) with log` is the general helper, and it is longer than Python's `with open(...) as log`. A shorter resource form is the cleanup question this round does not decide. `#on_cleanup` stays the binding-shaped answer. The `quit` on line 27 returns from `dump` after the brace's defer and then `close_log`.

**13, concise 4, line 15.** One unbraced `if` body is the shield, its block, a `??<Timeout>` handler, and `or_throw`. `do` tells the parser the brace is not the `if` body. The ordinary spelling is a braced `if`. This program exists so the unbraced form is defined, not so it is the one to write.

**14, obvious 4, discoverable 4, and concise 4, lines 16 and 18.** `continue` inside the shield and `??<Timeout> continue` both skip the element. Nothing on either line says they are the same loop. That is the plain-block rule: a comprehension has one loop, and a scope block does not add another. A `$label` can name it (LANGUAGE.md:4569) when a reader wants it written down. Requiring the label on every such `continue` would be a new constraint. Line 15 is the whole comprehension, which is why concise is 4.

**15, obvious 4 and discoverable 4, line 38. Concise 4, line 34.** `return -1` leaves `crawl`. `page` is never `-1`, and line 41 does not run. The header says so. The line is still an assignment of a call whose block contains `return`, which is the reading round 1 left unstated. It matches a plain block, and an assignment does not catch `return`. Making the assignment catch it is reading B. Line 34 is `span` around `interruptible` around `protect_from_cancel`: the `quit` path runs those defers, and the call site does not list them. That is what a library function is.

**16, obvious 4 and discoverable 4, lines 15 and 26. Safe 4, line 15.** `return 0` carries no failure. The child has already failed, so the join replaces that return and line 18 binds `code` to `-1`. The function does not return 0. `return Missing` on line 26 does return, because `Missing` is a failure and a defer does not replace one. The two returns look the same. The `??<WalkError>` is why this is not a silent fall-through, and it is also why safe stays at 4: the author wrote `return` and the function continued. Not replacing a failure-free `return` would contradict M4. Replacing `return Missing` as well would contradict it the other way.

**17, obvious 4 and discoverable 4, line 29. Safe 4, line 36.** `return 1` is replaced by the failing close, and `code` is `-1`. `return Missing` is kept, so the close's `FileError` is dropped. The close did run. The caller sees `Missing` and not the broken trailer. One failure is what Dewy returns. Reporting both would be a new error-aggregation rule, and this round's rule is the value-based one: a pending failure stays.

## Why this is the last round

The 5s are the cases the marker and the result type actually settle. `do` / `with` is visible at the call (05, 06, 11, 12, and the structure of 13). `scope(:> R)` on line 18 of program 11 is the function-type result spelling, so it is not a point off. `break` and `continue` in 09 leave the outer loop. Program 07's `return` joins a stopped `accept`, so it does not hang. `Closed` is matched in 04. The deadline arm in 03 is `Timeout` on the call, and `or_throw<Canceled>` is gone there because the shield does not leave a `Canceled` behind.

The 4s are the rules that replaced round 1's undefined behavior. Changing them would undo a must-fix: operation types that depend on the caller, a `return` that does not stop children, a defer that replaces an error the user already wrote, or an assignment that catches `return`. No round 3.

## Other languages

Python's `with` is the one place a comparison is shorter, and that is program 10. Go's `errgroup` and `signal.NotifyContext` make the early return and the Ctrl-C path callbacks again, which is the shape this design leaves. Rust's `CancellationToken` and drop guards are safe and longer. TypeScript has neither task groups nor a Ctrl-C scope. Swift's `taskGroup` and `withTaskCancellationHandler` are the closest block form, and they still don't take `return` out of the enclosing function.
