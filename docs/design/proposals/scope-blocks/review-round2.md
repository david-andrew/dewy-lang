# Correctness review: scope blocks, round 2

Round 2 fixes most of round 1. The `do`/`with` marker removes the parse that depended on the callee. Operation types are stable again. `tasks` stops its group before joining on an early exit. `scope(... :> R)` is typed, and the block runs at most once. Four problems remain, and each is a must-fix:

1. **Provenance is defined by the `Canceled` value**, and the round-2 programs throw a fresh `Canceled`, which loses it.
2. **The group's error type `E` can't be inferred** from the signature as written.
3. **Some types are subtracted per call site**, and that is unsound.
4. **The defer rule's wording** turns `break` in a loop body into "carry on".

I agree with the dropped-return rule ("resume after the call") for scope functions, with two conditions given at the end.

Abbreviations as in round 1: **R2** `round2.md`, **P/NN** `programs-r2/NN_*.dewy`, **L** `docs/LANGUAGE.md`, **DEC** `docs/design/decisions.md`, **DP** `resources/discussion_points.md`, **V5** `docs/design/proposals/concurrency/unified/proposal-v5.md`.

## Status of round 1's must-fixes

| # | Status | Note |
|---|---|---|
| M1 parse | **Resolved.** The parser decides without knowing the callee. | `do` and `with` aren't identifiers in any `.dewy` file. Neither is in `juxt_keywords` (`compiler/juxtapose.dewy:16`), the Dewy reader, LANGUAGE.md or DP. The only hits are the Jo parser's Python-habit errors (`compiler/parse.jo:109`, `:151`), which are Jo-only. Wording issues: S1, S5, S6. |
| M2 `Timeout` on operations | **Resolved** for operation types. | The static typing of the replacement is new must-fix N3. |
| M3 stop then join | **Resolved** for non-normal exits. | A normal result that is a failure value doesn't stop the group, which is a V5 regression (S3). |
| M4 library shape | **Partly resolved.** The value-based defer rule and the `join` grace exemption are right. | Provenance (N1) and the defer rule's wording (N4) are new must-fixes. |
| M5 `scope` typing | **Resolved** for `R`. | Unresolved for `tasks`' `E` (N2). |
| M6 at most once | **Resolved.** | Small points under Nits. |

## New must-fix

### N1. Provenance must belong to the scope's state, not the `Canceled` value

R2:139–143 replaces "a pending `Canceled` that this scope originated" and keeps one that "the block observed from a child it stopped itself" or that came from `return Canceled`. That makes provenance a property of the value. P/04 and P/16 then defeat it:

- **P/04:23–26** does `match hits.receive { … <Canceled> => Canceled or_throw }`. When `scan` fails with `WalkError`, the fail-fast group cancels the body's `receive`. The arm then throws a **fresh** `Canceled` that this scope didn't originate. It isn't replaced, so `find` returns `Canceled` and `main` exits 130 for a walk error. That is exactly what round 1's M4 was meant to prevent.
- **P/16:14–17 and :25–28** have the same problem. Also, under level-triggered cancellation (L:3457: "every later blocking operation in that scope returns `Canceled`"), `job.wait` after the group's fail-fast is a blocking wait in a canceled scope. It may return `Canceled` (V5:266, "it also reports cancellation of the waiter") instead of `WalkError`. So the `<WalkError> => return 0` arm that P/16 relies on is a race, not the deterministic path its header claims.

V5:211 says "provenance" without defining it, and `Canceled` is a unit exception value (L:3456), so the value has nowhere to carry an origin.

**Simplest fix:** "When a cancel scope closes because of its own reason (the shield's deadline fired, or the group is failing fast) and the parent hasn't been canceled, a pending `Canceled` exit is replaced by that reason." This matches how cancellation is already level-triggered per scope, works however the block re-spells `Canceled`, and needs no value metadata. A child the block stopped itself doesn't put the scope in a canceled state, so its `Canceled` still stays `Canceled`. The only behavior lost is that a deliberate `return Canceled` written inside a scope whose own reason has fired becomes that reason, which is harmless. Then define `wait` on a child that has finished: return its result even in a canceled scope. Otherwise P/16's arms are timing-dependent.

### N2. `E` for `tasks` can't be inferred from the signature as written

R2:196 `tasks = <R E>(body:scope(group:Tasks :> R)) :> R | E` has `E` only in the result. R2:147 says `E` is "inferred at the call from those spawns". But no parameter type mentions `E`, so the generic check of `tasks` can't type `join(group) or_throw`. Callers can't infer `E` through a wrapper either:

- **P/15:13** `interruptible = <R>(body:scope(ctrl_c:task.CtrlCListener group:task.Tasks :> R)) :> R | Canceled` passes `group` to the outer block.
- **P/15:39** then has `crawl`'s block spawn into it (via `group`, unused here, but legal).
- The inner `task.tasks` call's `E` comes from spawns that `interruptible` can't see, and its declared result drops `E`.

That is unsound, or uncheckable "once".

**Simplest fix:** make `E` part of the group type: `Tasks<E>`, `body:scope(group:Tasks<E> :> R)`, `join:(Tasks<E>):>void | E`. Then `E` is inferred from the constraints `group.spawn(f)` places on the block, as V5:274 already intended. A helper that takes `group:Tasks<E>` carries `E`. A wrapper is written `<R E>(body:scope(… group:Tasks<E> :> R)) :> R | E | Canceled`.

### N3. The type rules subtract alternatives at each call site, which is unsound

Two rules remove alternatives the call can still produce:
- R2:147: "minus a `Canceled` this scope replaced".
- R2:131: "A block whose every exit already carries a failure does not add [the defer's failure]".

Neither is a static fact:
- **03.** In P/03:22 / R2:276, `save`'s type is `Path | FileError | Canceled`, so `R` statically contains `Canceled`. Nothing proves every `Canceled` came from the shield: `save` could `return Canceled`, or stop a child of its own. The match covers it only if `problem:error` catches `Canceled`, and V5:222 warns against relying on a broad error arm for that.
- **07.** P/07:21–24: in `flush`, the brace's `write_text(...) or_throw;` forwards `FileError | Canceled` to **`flush`**, whose result is `void | FileError`. The `Canceled` is replaced at run time only if it is the deadline's, so statically `flush` must list `Canceled`.
- **16.** P/16:22 `kept:>Missing | Canceled`. Its block can forward `Canceled` while the group is failing fast. Under N1 that becomes `WalkError`, which `kept`'s type lacks.

**Simplest fix:** no subtraction anywhere.
- The call's type is the scope function's declared result (`R | Timeout`, `R | E`, `R | E` for `bracket`).
- A block's `or_throw` adds what it forwards to the enclosing function, as written.
- At run time some of those exits become the call's result instead, and the call's type already covers that.

The consequence is that `flush` lists `Canceled`, `kept` lists `WalkError`, and 03 keeps `or_throw<Canceled>` (or a `<Canceled>` arm). That is honest, and it is what V5's examples wrote.

### N4. "Resumes at the scope that owns the defer" breaks `break` in a loop body

R2:120 makes the defer-failure rule cover "every `defer`" (good: orthogonality, DEC:484). But it says execution "resumes at the scope that owns the defer, with the failure as that scope's result". R2:112 treats defers as block-scoped (the brace's defer runs when that invocation ends). So for a defer in a loop body or a plain block, the owning scope is that block:

```dewy
loop x in xs {
    defer log(x) or_throw
    if x =? 0 break
}
```

If `log` fails during the `break`, the `break` is dropped, the loop body's result is the failure, and the loop **continues** with the failure as a collected iteration value (L:274–276, loop capture). A `return` in a plain `{ … }` would likewise fall through to the code after that block.

**Simplest fix:** "A defer's failure is an `or_throw` from the **function** that wrote the defer." For an ordinary function, a failing defer during `return 5` returns the failure from that function. For a scope function, the function is the scope function, so the caller resumes after the call with the failure as the call's result. That is exactly R2's rule for scope calls, and it adds no new control-flow concept. It is also what `or_throw` already means at that position (L:3779: `or_throw` "returns an encountered exception" from the enclosing function).

## Should-fix

- **S1. The unmarked-brace warning fires on ordinary code.** R2:50 warns on "a `{` on the same line after a call that has no marker". Every `if ready(x) { … }`, `loop it.has_next { … }` and `match parse(text) { … }` is a call followed by a same-line `{`. Limit the warning to statement position, outside `if`, `loop`, `match` and `else` heads and `??<E> {` handlers.
- **S2. A dropped `return` deserves a warning, not just hover.** R2:129 only adds hover. A `return`, `break` or `continue` with no failure, in a brace whose call is then defaulted (`?? x`, `??<E> x`) or discarded (`;`), means code the author made unreachable runs. P/17:27–31 is exactly this. Warn, with a fix-it to `or_throw` or an explicit match. That is the "Python exceptions become proofs" stance applied to a contradiction the author wrote.
- **S3. A failure-valued normal result doesn't stop the group.** R2:153 and R2:203–205 set `finished = true` for any normal result. V5:275 stopped the other children on "an ordinary callback/child failure". With R2's shape, `task.tasks with g { g.spawn(@server); load_config() }` hangs when `load_config()` gives a `FileError` value. Fix: `finished = result is? not error` (value-based, like the defer rule).
- **S4. Waiting inside `parallel`.** R2:114 says "A blocking scope call inside a `parallel` body is rejected the way any blocking call is". DEC:433 (batch 3, C1) accepted "items may wait". Drop the sentence. The real rule is only the one about the borrowed listener or group.
- **S5. One spelling, and a cold-read risk.** `do with pattern { }` (R2:39) is a second spelling of `with pattern { }`. Its only use, P/13:20–21, is unnecessary because R2:41 already allows a newline before `with`. Drop it (no extra spellings without reason). The cold read of `task.tasks with group { … }` must specifically ask whether `group` is **bound** or **passed in**. Python readers know `with X as y`, and "`f with group`" reads naturally as "using the existing `group`". Keep `with` only if the readers answer "bound".
- **S6. Say where the marker attaches.** It is a postfix at member/call precedence (L:1415 row). It applies to the last call in a postfix chain, whose callee must be a statically named scope function or method. `f(1)(2) do { }` and `@f do { }` are "call it with its block". `??`, `or_throw` and binary operators apply outside. R2:62 says this for `??`/`or_throw` only.
- **S7. Program bugs that the dogfood should have caught.**
  - **P/16:14, :25.** `match job.wait` has no arm for the success alternative of `void | WalkError | Canceled` (V5:266), so it doesn't compile. The `WalkError` arm is a race (N1).
  - **P/13:9–11, :30.**
    - It spawns `size_of`, which returns `int`. Children keep the `void | E` contract (V5:276), so `job.wait` gives no `int`.
    - At :30, `group.spawn(...)` with no `;` makes the block express the `Task` handle and `0`, two values. R2:166 has the `;`; the program doesn't.
  - **P/17:26–30.** `replaced:>int` has a brace that does `append_file(...) or_throw;`, forwarding `FileError` to `replaced`, which can't accept it. The `??<FileError> -1` on the call does not catch the brace's own `or_throw`. That is a trap worth one sentence in R2: handlers on a scope call see only the call's result, never the brace's `or_throw`.
  - **Missing `Canceled`.** Helpers that read files omit `Canceled`, which file operations include (L:3458): P/08:9 `warm`, P/13:5 `size_of`, P/07:21 `flush`. P/08:12 also forwards a send failure that `warm`'s type lacks.
  - **P/17:12** `return FileError`: `FileError` is a family of `FileNotFound`, `FileAccessDenied`, and so on (L, "Files, paths and processes"). Construct a member.
  - **P/15.** `id`, `ctrl_c` and `group` are bound and never used, which warns. `next_span_id` is undeclared.

## Nits

- R2:72: "`inc{10}` is still the call in discussion_points.md:601". Today `f{1}` is an error ("'f' needs arguments"); I checked in round 1. Say "would be".
- Spell the function types as LANGUAGE.md does, `scope(ctrl_c:CtrlCListener:>R)` and `):>R | E =>`, without spaces around `:>`.
- **M6 checking.** The at-most-once check is the move checker's job: treat `body` as a move-only value consumed by its invocation, and the success-path rule as "consumed on every success path". Then nothing new is needed.
- **M6 at the caller.** On the call's failure path, a move in the brace is "maybe moved" (treated as moved), and a `let` assigned there is not definitely initialized. Say so next to R2:87.
- R2:120: "Its failure is not reported". A lost cleanup failure behind an earlier failure is defensible (first failure wins), but V5 asked that save failures be reported. Mention it under Cleanup as an open point.
- R2:215: "`E` is the error alternatives of `open` and `close`". That is a general generic-inference rule (splitting `T | E` against a union by family). State it as one, not as a `bracket` fact.
- R2:93 keeps the name `scope`. That's fine, but `(scope:scope(:>R))` is now legal next to `lib/prelude/time.dewy:63`. Leave it to the cold read.

## Verdict on the dropped-return rule

For scope functions, **the replaced exit should resume after the call, with the failure as the call's result**, as R2 says. The reasons:

1. **It follows from what is already there.** The failing `defer` is code in the scope function, and `or_throw` there returns from the scope function, whose return is the call's value. Nothing new is invented.
2. **It is the mainstream semantics.** In Python, a `with` block's `__exit__` that raises during a `return`, or in Java a `finally` that throws, cancels the return. The failure surfaces at the construct, and an enclosing handler resumes after it.
3. **It is typed and visible.** The failure is in the call's declared type, and Dewy already refuses to leave a `void | E` or `R | E` statement unhandled (L:305–310). So the caller decides whether to forward it (`or_throw`, the usual case: the function is still left, now with the failure) or to handle it locally.

The alternatives are worse:
- **Turning the replaced exit into a `return` of the failure from the enclosing function** makes the scope function's own `or_throw` target the caller's function, which breaks orthogonality. It skips the handlers the caller wrote on the call. It has no meaning for `break` or `continue` other than escalating them into a function exit. And it forces every enclosing function whose brace has a `return` to list the cleanup failure.
- **Keeping the exit and dropping the failure** (Go-style) silently loses close and join failures, against "errors are values" and safe by default.

There are two conditions:
1. **N4:** the general wording must be "an `or_throw` from the function that wrote the defer", not "the scope that owns the defer". Otherwise loop-body and plain-block defers turn `break` into "carry on".
2. **S2:** defaulting or discarding a call whose brace has a `return` with no failure warns. That is the one place "resume after the call" can run code the author wrote off as unreachable.
