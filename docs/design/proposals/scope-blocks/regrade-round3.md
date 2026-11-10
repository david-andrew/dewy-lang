# Independent regrade of round 3 (scope blocks)

Read: round3.md, summary.md, programs-r3/01-17, my round-2 regrade, LANGUAGE.md (error kinds at :3984, Canceled at :3468). dogfood-round3.md not read.

## 1. Round-2 must-fixes

| # | Status | Evidence |
|---|---|---|
| N1 brace `or_throw`: leaves function or call result | Resolved | round3.md "Control flow": brace `or_throw` always targets the writing function; only a failing defer or a closing cancel scope turn an exit into the call's result. 17 line 29-31 and 09 line 15-17 are now consistent, and 17's `replaced` type lists `FileNotFound | Canceled`. Open edge: M2 below. |
| N2 `E` of `tasks` | Resolved | `Tasks<E>`, `body:scope(group:Tasks<E>:>R)`; 15 line 21-22 wrapper `<R E>(...):>R | E | Canceled`, and `group.spawn(@note(url));` at line 52 is typed through it. |
| N3 child failure dropped | Acknowledged, not fixed | 08 line 24-27, 16 line 28, 17 line 37. Now an explicit "open under cleanup" item with the reason (one function returns one failure). I accept it as a deliberate trade, with David told (see section 5). |
| N4 value count | Resolved | "What a statement contributes"; `;` restored at 04 line 24, 07 line 31, 13 line 17 and 28, 15 line 52. |

## 2. The six dodged programs

| Program | Tests its case now? |
|---|---|
| 07 | Yes. Flush is back in the `select` arm (line 29-31) inside `tasks` inside `catch_ctrl_c`, with `return` after it (line 34). |
| 08 | Yes. No channel; `return Missing` after `warm` failed (line 24-27) and the dropped `FileNotFound` is stated in the header. |
| 11 | Mostly. `calling` now has `return ""` and `break` out of the block inside a `loop` (line 29-31), which a plain function cannot do. The repeat-the-block case (`retry`) is gone for good, by decision. |
| 14 | Partly. `rejected_return` and `rejected_spawn` are code, but `rejected_return` (line 29) has no scope block in the `parallel` body, so "including when that body is a scope block or contains one" is untested, and the allowed "blocking protect inside parallel" is only in the header. |
| 02 | Partly. The drain is gone, but nothing in the program reads the queued press (no `ctrl_c.next`), so the header claim at line 4-5 is a statement, not a test. |
| 04 | Yes. `<Canceled> => Canceled or_throw` (line 28) is the case, and the header says the group's state turns it into `WalkError`. That rule has a hole (M1). |

## 3. New must-fixes

- **M1. `tasks` as written cannot do what 04 claims.** round3.md says a pending `Canceled` becomes the group's `E` when the group is failing fast, and also says a pending failure is kept over a defer's failure (`Canceled` is an `exception`, a failure). The `tasks` library body (`defer { ...; join(group) or_throw }`) applies only the second rule, so in 04 the `join`'s `WalkError` would be dropped and `find` returns `Canceled`. Only `pop_shield` is said to "apply the state rule". Say where the group's state rule runs and in what order against the defer rule.
- **M2. The shield's `Timeout` never fires in the case 03 exists for.** Rule: the `Canceled` becomes `Timeout` only "when the parent has not been canceled". But the shield exists to run while the parent is already canceled (03 line 19-21: the `??<Canceled>` handler runs because the parent was canceled, and `protect_from_cancel` leaves it pending). When the 5 s deadline fires there, the parent has been canceled, so the `Canceled` stays `Canceled` and 03 line 22 `<Timeout> => printl("save deadline expired" ...)` is unreachable; the program falls into `<Canceled> => Canceled or_throw` silently. Deadline-fired must win over a masked parent cancel inside the shield (the parent's cancel is masked there by definition).

## 4. Should-fix (not blocking)

- **S1. Programs do not type-check against LANGUAGE.md:3984-3987.** `write_text`/`read_text` can also fail with `IsDirectory`, `FileExists`, `FileError`; `or_throw` forwards all of them, so lists such as 03 line 14 `Path | FileNotFound | FileAccessDenied | Canceled`, 07 line 25, 08 line 18, 13 line 12, 14 line 16 and 17 line 19 are incomplete. Leave the type inferred or list every kind.
- **S2. The "failure-free return" warning fires on correct code.** round3.md: warn on `??` or `;` over a call whose brace has a failure-free `return`/`break`/`continue`. 09 line 18 `??<Timeout> continue`, 14 line 17, 15 line 56 and 13 line 17 would all warn, though `protect_from_cancel` has no failing defer (its type is `R | Timeout`). The text names "a defer in tasks"; make the trigger the scope function's possible defer failure.
- **S3. `??<E>` after a brace that forwards `E`.** 17 line 31-34: `append_file(...) or_throw` and the close's `FileNotFound` are the same type through two routes, and `??<FileNotFound> -1` catches one. Hover or a warning is needed ("this handler sees only the call's failures").
- **S4. `<void> =>` arm (08 line 26, 16 line 25, 30) is not an existing spelling** (no `<void>` in LANGUAGE.md); say how a `void | E` success is matched.
- **S5. 14 and 02 headers claim cases the code does not exercise** (section 2).

## 5. Grades (O D C S F)

| # | Program | O | D | C | S | F | Floor |
|---|---|---|---|---|---|---|---|
| 01 | repl | 4 | 4 | 4 | 5 | 4 | 4 |
| 02 | shell | 4 | 3 | 4 | 4 | 3 | 3 |
| 03 | search_save | 3 | 3 | 3 | 3 | 2 | 2 |
| 04 | early_return | 3 | 3 | 4 | 4 | 3 | 3 |
| 05 | nested_catch | 4 | 4 | 4 | 5 | 4 | 4 |
| 06 | game_loop | 4 | 4 | 4 | 4 | 4 | 4 |
| 07 | server_flush | 3 | 3 | 3 | 4 | 3 | 3 |
| 08 | cli_throw | 4 | 3 | 4 | 3 | 4 | 3 |
| 09 | break_loop | 3 | 3 | 4 | 4 | 3 | 3 |
| 10 | bracket | 4 | 4 | 3 | 4 | 4 | 3 |
| 11 | calling | 4 | 4 | 4 | 4 | 3 | 3 |
| 12 | dashboard | 4 | 4 | 5 | 4 | 4 | 4 |
| 13 | expr_value | 3 | 3 | 3 | 4 | 3 | 3 |
| 14 | parallel_comprehension | 3 | 3 | 3 | 4 | 3 | 3 |
| 15 | two_libraries | 3 | 3 | 3 | 4 | 3 | 3 |
| 16 | return_replaced | 3 | 3 | 4 | 3 | 3 | 3 |
| 17 | failing_close | 3 | 3 | 4 | 3 | 3 | 3 |

Floor: **2** (03, complete), because of M2.

## 6. Lines under 5

01. O4 line 8-11 one `??<Interrupted> {...} ?? break` for three jobs. D4 line 8 `Interrupted` only because a catcher is up. C4 15 lines against Python's `try/except KeyboardInterrupt`. F4 no Ctrl-C outside `input`.
02. O4 line 14 `do {` around a shell loop. D3 line 2-5: SIGINT-to-child and the stale press only in comments. C4. S4 `spawn` failure. F3 line 4: claim not exercised, no foreground-group spelling.
03. O3 line 22-25 four arms for one save. D3 line 23 `<Canceled> => Canceled or_throw` next to `<Timeout>`: reader cannot tell which one the parent cancel reaches. C3 lines 21-27 against Python's `finally: save()`. S3 line 14 incomplete error list. F2 line 22: `<Timeout>` unreachable when the parent was canceled (M2).
04. O3, D3 line 28: a fresh `Canceled` turns into `WalkError` by hidden state. C4. S4. F3: M1.
05. O4 line 6, 19: `do {` with `return` in it. D4 inner catcher wins in comments only. C4. F4 outer catcher's restore is a comment.
06. O4, D4 line 11 `<ctrl_c.CtrlC>` against 12's `<CtrlC>`. C4. S4 line 7 `or_throw` on a genuine `Canceled` leaves `main`. F4.
07. O3 line 34: `return` also stops `accept`, invisible. D3 same. C3 lines 28-35: catcher, group, shield, select, `return`, in 8 nested lines. S4. F3 line 25 incomplete error list; accept hang still depends on M1-style rules for `or_throw`.
08. O4. D3 line 24: `<FileNotFound> => return Missing` drops the cause; reader must know the join's `FileNotFound` is lost. C4. S3 same line (N3 accepted). F4 line 26 `<void>` (S4).
09. O3 line 15: `probe(port) or_throw` leaves for a file error and becomes `Timeout` for a deadline. D3 same. C4. S4 line 12 `check_cancel` needed. F3 line 18 correct code would warn (S2).
10. O4. D4 line 24 `@open_log(p"app.log")` partial application plus `<T E R>`. C3 line 24 against Python `with open_log(path) as log`. S4 line 27 a failing close replaces `return` silently. F4.
11. O4. D4 line 19 `scope(:>R)`. C4. S4. F3: the generic repeat helper the original `retry` represented is gone.
12. O4. D4 line 8 `ctrl_c.next(timeout=2s)` against 06's `ctrl_c.next`. S4. F4.
13. O3 line 19-22: shield, block, `??<Timeout> {}` in one unbraced `if`. D3 line 25-31 `with` on its own line. C3. S4. F3 line 12 list incomplete (S1).
14. O3 line 18-20: two `continue`s, same loop. D3. C3 lines 15-20. S4. F3 line 28-30: scope-in-parallel not written (section 2).
15. O3 line 55-58 `return -1` three scopes deep. D3 line 35-40 `ctrl_c.next(timeout=0s)` is used only so the listener is used. C3 lines 46-62. S4. F3.
16. O3 line 15-17 `return 0` that the join turns into `-1`. D3 line 28 `return Missing` kept. C4. S3 line 16: the author wrote `return` and the function continued, and a matched failure still fails the group. F3 line 20 warning is the only signal (S2).
17. O3 line 30-33: `return 1` becomes `-1`. D3 line 33: two `FileNotFound` routes, one `??` (S3). C4. S3 line 37. F3.

## 7. summary.md's claimed floor 4

Not supported. 03's `<Timeout>` arm cannot fire in the program's own scenario (M2), 04's claim is not backed by the `tasks` library (M1), and most programs do not type-check on their error lists (S1). Several 4s are in the "Floors" list for programs whose own lines are 3s (07, 08, 09, 13, 15, 16, 17 all have O or D 3 above).

## 8. The remaining 4s listed in summary.md

- 01:8, 06:12, 12:8 (`Interrupted`, qualified/plain `CtrlC`): inherent, v6 surface. Accept.
- 02:2 (no spelling for the foreground group): inherent until a process API exists. Accept.
- 03:25 (`<Timeout>` and `<Canceled>` both stay): not inherent as written; it is M2. Not acceptable until fixed.
- 04:27 (state decides `WalkError`): deliberate trade, I accept, once M1 says where the rule runs.
- 07:34 (`return` stops `accept`): deliberate trade, same as `concurrent`. Accept.
- 08:22, 16:28, 17:37 (failure dropped for a pending failure): deliberate trade pending cleanup. I accept it for now; David should be told that a child's failure can vanish behind `return Missing`.
- 09:15, 13:20, 17:29 (brace `or_throw` leaves; `??` does not see it): deliberate and consistent with a plain block. Accept, with S3's hover.
- 10:24 (`bracket` longer than Python `with`): inherent until cleanup. Accept.
- 11:19 (`scope(:>R)`): acceptable naming; the lost repeat helper is a decided cut.
- 14:16, 15:53: inherent plain-block rules. Accept.
- 16:16 (`return` resumes after the call): accept, S2 fixes the noisy warning.

## Round 4 confirm

Read: round4.md, summary-final.md, programs-r4/03, 04, 16 (and review-round3.md for X1/X2). dogfood-round4.md not read.

| Item | Status | Evidence |
|---|---|---|
| M1 (where the group-state rule runs) | Resolved | round4.md "Where the group-state rule runs": brace defers, then the cancel scope closes and rewrites a pending `Canceled` to `E`, then the scope function's defers run and keep that `E`. 04 header says so; `find` returns `WalkError`. |
| M2 / X1 (shield `Timeout` unreachable under a parent cancel) | Resolved | "A shield's deadline": the shield hides the parent cancel, so the deadline is always `Timeout`. 03 line 23 `<Timeout>` is reachable in the Ctrl-C scenario. The `<Canceled>` arm (line 24) is now only a `Canceled` the block produced itself. |
| X2 (`isnt? exception` counted `none`) | Resolved | "What a failure is": a failure is `error` or `Canceled`; `finished = result isnt? error and result isnt? Canceled`; `return none` is not a pending failure. |
| 16 `<void>` arm (S4) | Resolved | 16 lines 15-18, 26-29 use `is? WalkError` / `is? Canceled`, no `<void>` arm. |

Regrade (O D C S F):

| Program | O | D | C | S | F | Floor | Line |
|---|---|---|---|---|---|---|---|
| 03 search_save | 3 | 3 | 3 | 4 | 4 | 3 | O/C line 22-27: four arms for one save; D line 24: why `<Canceled>` stays beside `<Timeout>` is only in the header; against Python `finally: save()`. |
| 04 early_return | 3 | 3 | 4 | 4 | 4 | 3 | O/D line 28: `<Canceled> => Canceled or_throw` reads as forwarding `Canceled`; the `WalkError` comes from a rewrite invisible at the line. |
| 16 return_replaced | 3 | 3 | 4 | 3 | 4 | 3 | O line 16 `return 0` and S line 15: the author wrote `return`, the function continued with `-1`, and an observed failure still fails the group; D line 27: `return Missing` kept. |

Floor of 03, 04 and 16: **3**. Each remaining 3 is a stated trade (provenance as scope state, one failure per function), not an unresolved must-fix. No new must-fix found in these three.
