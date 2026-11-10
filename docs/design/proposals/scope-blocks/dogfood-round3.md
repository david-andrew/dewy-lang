# Dogfood, round 3

Scores are obvious, discoverable, concise, safe by default, complete. A 5 means that column needs no change. Every Dewy score under 5 names a line. These are the last round's scores. None of them is a contradiction left in the rules. Each one is a fact the rules keep.

Floor is **4**.

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 REPL | 5 4 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 2 3 3 3 | 4 3 4 3 4 | 2 2 2 3 2 |
| 02 shell | 5 4 5 5 4 | 4 4 4 4 4 | 4 3 3 4 4 | 3 3 3 4 3 | 4 3 4 3 3 | 2 2 2 3 2 |
| 03 save on Ctrl-C | 4 4 5 5 5 | 4 4 3 4 4 | 4 3 3 4 4 | 3 3 3 4 4 | 4 3 3 3 4 | 2 2 2 3 3 |
| 04 early return | 4 4 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 4 4 4 5 4 | 3 3 3 4 3 | 4 3 4 4 4 |
| 05 nested catch | 5 5 5 5 5 | 5 4 4 4 5 | 3 3 3 4 3 | 3 2 3 3 3 | 4 3 3 3 4 | 2 2 2 3 2 |
| 06 game loop | 4 4 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 4 3 3 | 3 2 3 3 3 |
| 07 server flush | 4 4 4 5 5 | 4 3 3 4 4 | 4 3 3 4 4 | 3 3 3 4 4 | 4 3 3 3 4 | 2 2 2 3 3 |
| 08 CLI throw | 4 4 5 4 5 | 5 5 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 4 3 4 4 4 |
| 09 break | 4 4 5 5 5 | 5 5 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 3 3 3 4 3 |
| 10 bracket | 5 5 4 5 5 | 5 5 5 4 5 | 4 4 4 3 4 | 4 4 3 5 4 | 4 3 3 3 4 | 4 4 4 4 4 |
| 11 calling | 5 4 5 5 5 | 5 5 5 5 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 4 3 4 4 4 |
| 12 dashboard | 4 4 5 5 5 | 4 3 4 4 3 | 4 3 3 4 4 | 3 3 3 4 3 | 4 3 4 3 3 | 2 2 2 3 2 |
| 13 expressions | 5 4 4 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 3 3 4 | 3 3 3 4 3 |
| 14 comprehension | 4 4 4 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 3 3 3 | 3 3 3 4 3 |
| 15 two libraries | 4 4 4 5 5 | 4 4 3 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 3 3 4 | 3 3 3 4 3 |
| 16 return replaced | 4 4 5 4 5 | 4 4 4 4 4 | 3 3 3 4 3 | 4 3 3 5 4 | 3 3 3 4 3 | 4 3 4 4 4 |
| 17 failing close | 4 4 5 4 5 | 4 4 4 4 4 | 4 4 4 3 4 | 4 4 3 5 4 | 4 3 3 3 4 | 4 4 4 4 4 |

## Lines under 5

**01, discoverable 4, line 8.** `??<Interrupted>` does not say the catcher is why this press is `Interrupted` and not `Canceled`. Console reads are `Interrupted` whenever a catcher is up. That is the existing console rule. Putting `Interrupted` on `input` only inside the brace would make the operation's type depend on the caller.

**02, discoverable 4 and complete 4, line 2.** SIGINT to the foreground child is only that comment. There is no spelling for the process group. A press during `child.wait` is not drained: a queued press does not become the next `Interrupted`, so a drain would not change the rule. Python's `subprocess` call does not show the signal either.

**03, obvious 4 and discoverable 4, line 25.** The match has `<Timeout>` on line 24 and `<Canceled>` on line 25. A deadline is the `Timeout` arm only when the shield's own reason fired. `save` can still return `Canceled`, and the type is not narrowed, so both arms stay. The line does not say which `Canceled` is which.

**04, obvious 4 and discoverable 4, line 27.** `Canceled or_throw` reads as `find` returning `Canceled`. If the group is failing fast and the parent is not canceled, that fresh `Canceled` becomes `WalkError` as the call's result, because the reason is the group's state. The value has no origin to show. The signature lists both.

**06, obvious 4 and discoverable 4, line 12.** `<ctrl_c.CtrlC>` is the qualified arm because `select` has two sources. Program 12 line 8 is `<CtrlC>` because it matches one `ctrl_c.next`. v6 already has both spellings. This round does not merge them.

**07, obvious 4 and discoverable 4, line 34. Concise 4, line 31.** `return` leaves `serve` and stops `accept` before the join. The stop is not written on the line. Writing it out would bring the hang back for every `return` that forgot it. Line 32's `or_throw` leaves `serve` on a file error. The `??<Timeout>` on line 33 sees only the shield's call. Lines 31–34 are three scopes because the server is a catcher, a group, and a deadline. The flush is back in the arm.

**08, obvious 4, discoverable 4, and safe 4, line 22.** The arm is `<FileNotFound> => return Missing`. `Missing` is kept. `warm`'s `FileNotFound` is not reported. One function returns one failure. An error with a cause is the open cleanup point, not a channel this call can grow. There is no `done` channel. Line 17 is the missing argument, which returns `Missing` before a child exists.

**09, obvious 4 and discoverable 4, line 15.** `probe(port) or_throw` adds `FileNotFound | Canceled` to `serve_until`. At run time a deadline `Canceled` becomes the call's `Timeout`, and line 18 continues the port loop. A file error leaves `serve_until`. Line 16's `continue` and line 17's `break` leave that loop. The two outcomes of one `or_throw` are the scope's state, not two spellings.

**10, concise 4, line 24.** `bracket(@open_log(p"app.log") @close_log) with log` is longer than Python's `with open(...) as log`. A shorter resource form is the cleanup decision this round does not make.

**11, discoverable 4, line 19.** `body:scope(:>R)` reuses the function result mark. It is easy to read `:>R` as only `calling`'s result. It is the block's result, and `calling` is checked once against that parameter. Line 28's `return` and line 29's `break` leave `load` and its loop. A callback would have kept them. A helper that runs the block again is a different parameter.

**12, obvious 4 and discoverable 4, line 8.** `<CtrlC>` is the single-source arm. It does not say why program 06 spells the same press `<ctrl_c.CtrlC>`. Same v6 rule as 06.

**13, discoverable 4, line 20. Concise 4, line 19.** Line 20's `or_throw` targets `total_size`. Line 21's `??<Timeout>` handles only the shield's call. They sit on one `if` and look like one handler. `do` is what makes the brace the call's. Line 34 discards the task handle. The block's one value is the `0` on line 35. Line 24 is `with` on its own line, not `do with`.

**14, obvious 4 and discoverable 4, line 16. Concise 4, line 15.** `continue` on line 16 and `??<Timeout> continue` on line 18 both skip the element. Nothing on line 16 names the comprehension. That is the plain-block rule, and a `$label` already exists when the target should be written. Line 27 is rejected: "return cannot leave a parallel body." Line 34 is rejected: "group belongs to this tasks block and cannot be used from a parallel body." A blocking call inside `parallel` is allowed.

**15, obvious 4 and discoverable 4, line 53. Concise 4, line 44.** `return -1` leaves `crawl`. `page` is never `-1`. An assignment does not catch `return`, same as a plain block. Line 44 is `span` around `interruptible` around the loop: `quit` runs those defers, and the call does not list them. `group` is spawned on line 47. `ctrl_c` is read on line 48. `interruptible` is `<R E>` and `Tasks<E>`, so `note`'s failure is `E` on `crawl`.

**16, obvious 4 and discoverable 4, line 16. Safe 4, line 28.** `return 0` does not leave `replaced` when the join fails. Line 20 warns, because `??<WalkError>` defaults a call whose brace returns without a failure, and `code` becomes `-1`. The return line itself still reads as an exit. Line 28 returns `Missing`, which is kept, and the same `WalkError` is dropped. Matching `job.wait` does not clear the group. The `<void>` arm is on line 18, so the match covers `void | WalkError | Canceled`. `wait` returns `WalkError` here because `boom` has finished.

**17, obvious 4 and discoverable 4, line 29. Safe 4, line 37.** `append_file(...) or_throw` leaves `replaced` with `FileNotFound` or `Canceled`. Line 31's `??<FileNotFound>` does not catch that `or_throw`. It catches the close, which is `bracket`'s defer, and then line 30's `return 1` is dropped and `code` is `-1`. Line 37's `return Missing` is kept, so the close's `FileNotFound` is dropped. The close is `return FileNotFound`, a member, not the family `FileError`.

## Why the floor stays

The 5s are the cases round 2 left open and this round closes. Program 07's flush is in the arm, and `return` stops `accept`. Program 08 does not add a channel. Program 11's `return` and `break` need the scope parameter. Program 14 writes both rejected `parallel` forms. Program 02 does not drain a press. Program 04's fresh `Canceled` is replaced from the group's state, and `find` lists `WalkError` and `Canceled`. Program 09 and program 17 use one rule: `or_throw` in the brace targets the function that wrote it, and a handler on the call sees only the call. Program 13's `spawn` is discarded, and the block contributes one value.

No further round fixes a 4 without breaking one of those rules, or without a decision this round was told not to take: a new error-with-a-cause, a new process-group spelling, one tag spelling for `CtrlC`, or a resource form shorter than `bracket`.
