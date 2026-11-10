# Scope blocks, round 2

A call takes a scope block only when the call site says so, with `do` or `with` before the brace. The brace runs as part of the caller: `return`, `break`, `continue`, and `or_throw` target the enclosing function and its loops, exactly as they do in a plain `{ ... }` block. The callee is an ordinary library function with a `scope(... :> R)` parameter. It runs its setup, invokes that block at most once on its own task, and runs its `defer`s on every way out before the exit completes. `task.catch_ctrl_c`, `task.tasks`, and `task.protect_from_cancel` are three such functions. Any library can write another. A listener or a group passed into the brace cannot be used after it.

Round 1 left the brace attached by the callee's declaration, rewrote operation results inside a shield, and let `tasks` join a still-running child on `return`. This round marks the brace at the call, keeps operation types stable, stops a group before an early join, types `scope` with a result, and runs the block at most once. `retry` does not survive.

## What the reviews asked for

Must-fixes, all taken:

| # | Decision |
|---|---|
| M1, regrade 1 | The brace attaches only at `do` or `with`. The parser does not look up the callee. |
| M2 | Inside a shield, a canceled operation is still `Canceled`. The shield's own `Canceled` becomes `Timeout` when that shield closes. |
| M3, regrade 3 | A non-normal exit from `tasks` stops the group, then joins. A normal result joins without a stop. Program 07 does not hang. |
| M4, regrade 5 | Two general rules. A defer failure replaces a pending exit that carries no failure. A cancel scope, as it closes, replaces a `Canceled` it originated with its own reason, and that reason is the call's result. `join` is not cut off by the 100 ms cleanup grace. |
| M5, regrade 4 | `scope(ctrl_c:CtrlCListener :> R)` and `scope(:> R)`. The scope function is generic in `R` and checked once. |
| M6 | The block runs at most once. `retry` is withdrawn. |
| Regrade 2 | `return` from an assigned scope call leaves the enclosing function. Citations below. |
| Regrade 6 | A scope call used as a statement follows the existing void rules (LANGUAGE.md:305–310, :1387). |

Should-fixes taken: S1 (the return readings and the citations), S2 (the defer rule is about every `defer`, and a replaced `return` resumes after the call), S3 (a real `break` and `continue` from inside the brace; 07; 09's signature; no `retry`), S4 (David's `Code` note and `#on_cleanup`), S5 (the block runs only on this task, not merely "not on a spawn"), S6 (`parallel` stays a keyword). From the regrade: multi-value `with`, newlines, and `??` / `or_throw` precedence; the v6 tag spelling; `break` / `continue` against a comprehension and against `parallel`; `do` / `with` as the visible marker; `or_throw<Canceled>` only where a genuine `Canceled` is still in the result; `Closed` matched, not thrown; a failing close; a child that has already failed while the block returns.

Should-fixes not taken: callee-directed attachment (the review's smallest text for M1; it is the context sensitivity DEC:485 is about). Reading B, where the assignment catches `return`. A repeatable block, including a generic `retry`, this round. Putting `Timeout` on operation types. Calling the parameter `Code`.

## Rules

### Where the brace attaches

`do` and `with` are keywords. Neither is an identifier today, and `with` is not in `juxt_keywords`. A `{` is a scope block only when one of those keywords stands between the call and the brace:

```dewy
task.catch_ctrl_c do { printl"ready" }
task.catch_ctrl_c with ctrl_c { ctrl_c.next }
task.tasks with group { group.spawn(@work) }
task.protect_from_cancel(5s) do { save(best) }
```

`do` is the marker when nothing is bound. `with` is the marker when a pattern is bound. `do with pattern { }` is the same call as `with pattern { }` and is not required. `g() do { }` and `g do { }` are the same call. A scope call has the block as its argument, so it is not a zero-argument call: `catch_ctrl_c do { }` does not write `()`.

The parser applies this without knowing the callee. After a call, `do` or `with` continues that call. `with` requires one pattern, then `{`. `do` requires `{`, or `with` and then `{`. Newlines and comments may sit between the call and the marker, and between the marker and `{`, because a newline does not end a statement and the marker has already continued the call. The suffix ends at the matching `}`.

```dewy
task.catch_ctrl_c do
    with ctrl_c {
        ctrl_c.next
    }
```

A `{` with no `do` or `with` before it is a separate block, as today. `if c h() { printl"after" }` still runs the block when `c` is false. A `{` on the same line after a call that has no marker warns: "this block is a separate statement; put it on its own line."

`if`, `loop`, and `match` do not take the brace once a marker has consumed it. The head's body is the statement that remains, which may be the scope call itself.

```dewy
if verbose task.protect_from_cancel(1s) do { write(total) } ??<Timeout> printl"log skipped"
loop port in ports task.protect_from_cancel(2s) do { if ready break }
match task.protect_from_cancel(5s) do { save(best) } {
    saved:Path => printl"saved to {saved}"
}
```

`do` takes the first brace. `??` and `or_throw` sit outside that brace and apply to the whole call. The match's arms are the next brace. When `verbose` is false the call does not run, and neither does `??`.

If the marker consumes the only brace and the head then has no body, the error names the call: "these braces belong to protect_from_cancel; the if needs a body. Parenthesize the call or bind it first." The same sentence is used for `loop` and `match`, with that keyword in place of `if`. Parentheses give the head a body:

```dewy
if (task.protect_from_cancel(1s) do { ping() }) { printl"answered" }
```

An overload set may mix a scope variant and a non-scope variant of the same arity. The marker selects the scope variant. A call with no marker selects the other. Methods use the same marker: `m.locked with v { }`.

A `{` juxtaposed as a value argument is not a scope block. `inc{10}` is still the call in discussion_points.md:601, and the block's value is evaluated first.

The pattern after `with` is one `let` pattern. `with ctrl_c` binds one value. `with (ctrl_c group)` and `with [ctrl_c group]` are the same pattern (LANGUAGE.md:2601) and bind a product. `with ctrl_c group` is not a pattern. Omitting `with` when the scope parameter passes values discards them, the way `_` discards a `let` binding. `;` is the other way around: it discards a result (decisions, batch 4). Hover on a discarded parameter names it and shows the `with`.

### The parameter

```dewy
body:scope(ctrl_c:CtrlCListener :> R)
body:scope(:> R)
```

`R` is inferred from the block's normal result and is a type parameter of the scope function. The scope function is checked once, generically, not once per call site and not as a template. A scope parameter is not a value. `@task.catch_ctrl_c`, storing `body`, copying it with `@`, or passing it to an ordinary function parameter is "call catch_ctrl_c with its block". Passing it on is `inner(body)`, where `inner` takes the same `scope` type. The block's `return` still targets the function that wrote the brace.

The block compiles to a non-escaping local function whose result is an exit: a normal value, `return v`, `break` or `continue` with its label, or a forwarded failure. `body(...)` either returns the value or starts that exit through the scope function's defers. The call site then dispatches the exit. Inlining is an optimization. The per-site cost is the block. A scope function that calls itself is an ordinary recursive call, each activation with its own block, not an expansion.

The block is invoked at most once. The check is in the scope function: no path invokes it twice, and a path that returns a success has invoked it. A path that cannot invoke it returns a failure, as a failed `open` does. The caller treats the brace as straight-line code on the success path. A `let` assigned in the brace is initialized after a successful call. A move in the brace is one move. A `+= literal` in the brace counts as once for the integer-domain rule (LANGUAGE.md:335–337).

`retry` is withdrawn. A second run would be a second initialization, and the caller would have to trust the library about the count. A later form that runs a block several times needs its own marker and is checked at the caller like a loop body. David's `#insert body(break=…)` (discussion_points.md:2774) is the shape of that marker. It is not this round.

The block runs on the scope function's own task, synchronously, and finishes before that function returns. `group.spawn` of the block, a `parallel` item, a `race` or `within` thunk, and any `@` handle that captures `body` are "a scope block runs on this task".

`scope` is also the word for a cancel scope (LANGUAGE.md:3457), a metatag scope (LANGUAGE.md:701), and a value parameter (`lib/prelude/time.dewy:63`, `scope:string|none`). Those are value positions. This `scope` is a parameter type. `block` would collide with the blocks effect. The name stays.

### Control flow

Code in the scope function is ordinary: its `return` is the value of the call. Code in the brace belongs to the caller.

| Written in the brace | Target |
|---|---|
| `return` / `return v` | the enclosing function, or the enclosing generator once generators exist |
| `break` / `continue`, including `break $label` | the loop a plain block in that position would reach, including a comprehension's loop |
| `or_throw` | the enclosing function, as a returned failure, unless a rule below replaces that exit |
| a normal result | the value of the invocation, which the scope function receives |

An assignment does not catch `return`. `let x = task.tasks with group do { return 1 }` stops and joins the group; if that join succeeds, the enclosing function returns `1` and `x` is never bound. The enclosing result must accept `1`. This is the reading the compiler already implements for a plain block: `let x:int = { if c return 1; 5 }` returns `1` from the enclosing function.

discussion_points.md:455 says a `return` goes "up until the nearest thing that catches it, which could be an assignment, or it could be a function boundary." That sentence is about generator literals, and about whether `A1:int={return 1}` can stay as a uniform spelling. It is not the rule for a block in a function. The next example, at line 465, is a `return` inside an assigned `[loop …]` and the note there is that it "breaks out of function". Line 502 names the boundaries: "`returns` stop at certain boundaries", and those boundaries are functions and generators, the same way a `return` stops at a nested function. A scope block is neither. Reading B, where the assignment catches the `return` and `x` becomes `1`, is the context sensitivity DEC:485 is about, and it is the callback shape v5 used for `let answer = task.tasks(...)`. It is rejected.

A future `yield` in a scope block belongs to the enclosing generator, as `return` does. Giving one value out of the middle of a block without leaving the function is the `express` question (discussion_points.md:481), which this round does not decide.

`defer` inside the brace runs when that invocation ends, before the scope function's own defers. Inner first, each list in reverse. Both lists run on a normal result and on `return`, `break`, `continue`, and `or_throw`.

`return` and `break` inside a `parallel` body are still illegal, including when the `parallel` body is a scope block or contains one. The error is the existing one: "return cannot leave a parallel body." A scope block does not open a hole through `parallel`. `parallel` stays a keyword because its items are not one synchronous invocation on the caller (decisions, batch 3, the `parallel` item note; DEC:434). They may run on other threads, so the caller's `return` cannot mean one exit. A scope block is one synchronous run, so `return` works. A blocking scope call inside a `parallel` body is rejected the way any blocking call is: "protect_from_cancel may block; a parallel body cannot". A listener or group borrowed by the brace cannot be used from a `parallel` body: "group belongs to this tasks block and cannot be used from a parallel body".

### Defer failures, for every defer

`defer` is not in the front end yet, and this round does not decide cleanup. Scope exits need one rule, and the rule is about every `defer`, not a special case for scope functions (orthogonality, DEC:484). It is decided by the value, so `return Missing` and `Missing or_throw` behave the same. Both carry a failure (LANGUAGE.md:3743, errors are values).

A defer that produces a failure replaces a pending exit that carries no failure: a normal value, `return` of a non-failure, `break`, or `continue`. That `return`, `break`, or `continue` is dropped. Execution resumes at the scope that owns the defer, with the failure as that scope's result. For a scope function, the caller resumes after the call and must handle the failure. A `return` of a failure, and an `or_throw` already started, are kept. The defer still ran. Its failure is not reported.

```dewy
let code = task.tasks with group {
    group.spawn(@boom(path))
    return 0
} ??<WalkError> -1
```

If a child has already failed, `return 0` is dropped and `code` is `-1`. The function does not return `0`. Hover on a `??` or `or_throw` after a call whose brace contains `return` says: "this return is dropped if a defer in tasks fails; the call's result is that failure."

`return Missing` is kept, and a later defer failure is dropped. The author's failure is the one that stays. The defer's failure is part of the call's result only when the block has an exit that carries no failure. A block whose every exit already carries a failure does not add it, so `kept` in program 16 lists `Missing` and not `WalkError`.

Stopping a group on the way out cancels children that have not already failed. Their later result is an owner stop, which is normal shutdown, not a child failure. A child that has already failed stays the group's failure. `return` immediately after `spawn` does not wait to discover a failure the child has not produced yet.

### Cancel scopes, as they close

Operation types do not change with the caller (proposal-v5.md:192). `check_cancel`, `sleep`, file and stdin operations, and process waits return `Canceled` inside a shield, the same as outside. `within` already works this way: the scope reports `Timeout`, and the inner operation reports `Canceled` (LANGUAGE.md:3465).

When a cancel scope opened by a scope function closes, a pending `Canceled` that this scope originated is replaced by the scope's reason, and that reason is the call's result. It does not keep propagating as `Canceled`. Provenance is the one v5 already uses (proposal-v5.md:211). The same rule covers `within`, `race`, `tasks`, and `protect_from_cancel`.

- A shield's deadline becomes `Timeout`.
- A fail-fast group's first child failure becomes that failure.
- `return Canceled`, and a `Canceled` the block observed from a child it stopped itself, were not originated by this scope. They stay `Canceled`.

`protect_from_cancel`'s own result is `R | Timeout`. It does not add `Canceled`. Parent cancellation is masked for the brace and is not cleared; the next checkpoint after the call still sees it. A `Canceled` the block forwards that this shield did not originate is still in the call's result, and the caller handles it with `or_throw<Canceled>` or a match. The save example has no such value: `write_text`'s deadline `Canceled` becomes the `<Timeout>` arm, and a file error is the `problem` arm.

The call's result is `R`, plus the failures the scope function itself adds (`Timeout`, the group's `E`), plus failures the block forwards, minus a `Canceled` this scope replaced. `E` for `tasks` is the failure `join` reports for the children this block spawned. It is a type parameter, inferred at the call from those spawns. The library is still checked once.

Waiting for children inside `join` is not bounded by the 100 ms cleanup grace (LANGUAGE.md:3472). The children's own cleanup is.

### `tasks`, stop then join

A non-normal exit from a `tasks` block (`return`, `break`, `continue`, a forwarded failure) stops the group and then joins it. A normal result joins and does not stop. This is a semantic change from v5's "stop persistent children explicitly." It is the rule `concurrent` already has: returning early from the body cancels and joins its children (LANGUAGE.md:3445–3446). Without it, `return` from a server loop joins an `accept` loop that nobody stops, and the call hangs. A persistent child that should outlive a normal fall-through must be stopped by the block, as in v5. An owner `stop` is normal shutdown, not a child failure.

### Statements and void

The call's result is the scope function's result. The existing void rules apply, with no extra case (LANGUAGE.md:305–310, :1387).

- A void result is a statement.
- A value in a `:>void` body needs `;` (`xs.pop();`). `;` discards everything the call expresses, including `Timeout` and other failures. That discard is what the semicolon already means.
- `void | E`, or `R | E`, as the last statement of a body with that result is the result. Elsewhere it is an error unless it is propagated (`or_throw`), handled, or discarded with `;`.
- The usual statement that keeps the failure and drops the success is `or_throw;`. `or_throw` forwards the failure. `;` discards the success. One does not do the other's job.

```dewy
task.catch_ctrl_c do { printl"hi" }
task.tasks with group { group.spawn(@size_of(paths[0])); 0 } or_throw;
task.protect_from_cancel(5s) do { save(best) } or_throw;
```

The last line discards the path after forwarding `Timeout` and the file error. A match is how the caller tells those apart.

### Borrow

Every value passed into the brace is borrowed for the brace, deliberately, including a plain record such as `Log`. One rule. The extent is the brace, not the last use. Storing one in an outer binding, returning it, or capturing it in a closure is "ctrl_c belongs to this catch_ctrl_c block". Passing it to a helper's parameter (`serve(lines ctrl_c)`) is legal for that call. There is no handle after the brace and no `Closed` on `CtrlCListener`.

### Tags

Unchanged from v6, and restated so the programs are not two spellings of one event. A `select` of several sources uses the qualified arm, `<ctrl_c.CtrlC>` and `<frames.Tick>`. A match on one `ctrl_c.next` uses the type's own arm, `<CtrlC>`.

### What the three scopes still do

The rest of the behavior is unchanged.

- Default Ctrl-C still requests root cancellation. Unhandled, that `Canceled` exits 130. The next press, and three presses within one second while a catcher or a shield is up, still force exit 130.
- `catch_ctrl_c` routes presses to the innermost catcher on the foreground task for the brace, then restores the previous route. It does not mask `Task.stop`, sibling failure, deadlines, or any other cancellation. A waiting console read (`input`, `input_int`, `input_float`, `read_line`, stdin lines) receives `Interrupted` and consumes that press. Those functions' types always include `Interrupted`. Otherwise the press is available from `ctrl_c.next`, including `@ctrl_c.next` inside `select`, and presses coalesce. A press queued for `.next` does not later become `Interrupted`. A child in the terminal's foreground process group still receives SIGINT. `catch_ctrl_c` off the foreground task is "Ctrl-C catching runs on the foreground task", naming the helper chain.
- `tasks` opens a fresh fail-fast group and runs the block on the caller. The join rule is the one above.
- `protect_from_cancel` runs the block once under a fresh cancellation scope even if the parent is already canceled, with a required cooperative deadline, then restores the parent without clearing it. Nested protection does not extend an outer shield's deadline. There is no cancel thrown at the caller afterwards. `check_cancel()` is not a scope.

```dewy
catch_ctrl_c = <R>(body:scope(ctrl_c:CtrlCListener :> R)) :> R => {
    let frame = push_catcher()
    defer pop_catcher(frame)
    body(frame.listener)
}

tasks = <R E>(body:scope(group:Tasks :> R)) :> R | E => {
    let group = open_group()
    let finished = false
    defer {
        if not finished group.stop()
        join(group) or_throw          # wait is not under the 100 ms grace
    }
    let result = body(group)
    finished = true
    result
}

protect_from_cancel = <R>(limit:Time body:scope(:> R)) :> R | Timeout => {
    let shield = push_shield(limit)   # parent stays pending; operations still return Canceled
    defer pop_shield(shield)          # this shield's Canceled becomes Timeout
    body()
}
```

`bracket` is the same mechanism for a resource. `E` is the error alternatives of `open` and `close`, not `never` with those errors stuffed into `T`.

```dewy
bracket = <T E R>(
    open:():>T | E
    close:(handle:T):>void | E
    body:scope(handle:T :> R)
) :> R | E => {
    let handle = open() or_throw
    defer close(handle) or_throw
    body(handle)
}
```

### Diagnostics

- A lambda where a scope block belongs: "this block is part of the caller, so `return` leaves this function. Write `task.catch_ctrl_c do { ... }`."
- A `{` on the same line after a call with no marker: warning, "this block is a separate statement; put it on its own line."
- A head left without a body: "these braces belong to protect_from_cancel; the if needs a body. Parenthesize the call or bind it first."
- A second invocation, or a call from another task: "a scope block runs at most once" / "a scope block runs on this task".
- A listener or group stored past the brace, or used from a `parallel` body: "ctrl_c belongs to this catch_ctrl_c block".
- `catch_ctrl_c` off the foreground task: "Ctrl-C catching runs on the foreground task".
- `@task.tasks`, or `body` passed as a function value: "call it with its block."
- `return` or `break` leaving a `parallel` body: "return cannot leave a parallel body."
- `break` / `continue` with no enclosing loop: the ordinary error.

### Cost

The check runs only at a scope call. The scope function is checked once. Each site checks its own block: exits, borrows, the one invocation. No pass looks at a function that has no scope call. The call does not allocate a closure. Qualified `select` arms keep today's same-function check, with the brace counted in the function that wrote it.

## The three scopes

```dewy
import p"@lib/std/tasks.dewy" as task

repl = () => {
    task.catch_ctrl_c do {
        loop true {
            let line = input("> ") ??<Interrupted> { printl(""); continue } ?? break
            if line =? "quit" return
            printl"you said {line}"
        }
    }
    printl"end of input"
}

search = (@best:int):>void | Canceled => {
    loop n in [0..1_000_000_000) {
        check_cancel() or_throw
        if n % 7919 =? 0 best = n
    }
}

save = (best:int):>Path | FileError | Canceled => {
    p"best.txt".write_text("{best}\n") or_throw;
    p"best.txt"
}

main = () => {
    let best:int = 0
    search(@best) ??<Canceled> {
        match task.protect_from_cancel(5s) do { save(best) } {
            saved:Path => printl"saved to {saved}"
            <Timeout> => printl("save deadline expired" file=stderr)
            problem:error => printl("save failed: {problem}" file=stderr)
        }
        return Canceled
    }
    save(best) or_throw;
}
```

`write_text` returns a byte count. `save` discards it and returns the path, which is what the `saved:Path` arm matches. The deadline is the `<Timeout>` arm. A file error is `problem`. No `or_throw<Canceled>`: the only `Canceled` `save` can forward from inside the shield is the deadline, and the shield turns that into `Timeout`.

## D4, rewritten

A prompt with its own Ctrl-C behavior. `quit` breaks the loop, as in D4; the catcher then ends and the line after the call runs. Program 01 uses `return` instead, so that line is skipped.

```dewy
# Ctrl-C during input clears the line; EOF/quit leaves the visible scope.
import p"@lib/std/tasks.dewy" as task

repl = () => task.catch_ctrl_c do {
    loop true {
        let line = input("> ") ??<Interrupted> { printl(""); continue } ?? break
        if line =? "quit" break
        printl"you said {line}"
    }
}
main = () => {
    repl() or_throw
    printl"normal Ctrl-C behavior restored"
    sleep(100ms) or_throw
}
```

Save on Ctrl-C. Normal cancellation stops the search. The protected save handles its own errors. `return Canceled` then preserves exit 130.

```dewy
# Ctrl-C requests ordinary cancellation. Save, then preserve exit status 130.
import p"@lib/std/tasks.dewy" as task

search = (@best:int):>void | Canceled => {
    loop n in [0..1_000_000_000) {
        check_cancel() or_throw
        if n % 7919 =? 0 best = n
    }
}
save = (best:int):>Path | FileError | Canceled => {
    p"best.txt".write_text("{best}\n") or_throw;
    p"best.txt"
}
main = () => {
    let best:int = 0
    search(@best) ??<Canceled> {
        match task.protect_from_cancel(5s) do { save(best) } {
            saved:Path => printl"saved to {saved}"
            <Timeout> => printl("save deadline expired" file=stderr)
            problem:error => printl("save failed: {problem}" file=stderr)
        }
        return Canceled
    }
    save(best) or_throw;
}
```

The north-star prompt's group is the same spelling. The rest of that prompt is unchanged.

```dewy
task.tasks with group {
    let saver = group.spawn(@autosave)
    let tick = ticker(500ms)
    defer tick.stop()
    loop i in [0..4) tick.next or_throw;
    saver.stop()
} or_throw
```

The loop finishes normally, so the join does not stop `saver`. The block stops it. `tick.next or_throw;` forwards `Canceled` and discards the tick.

## Cleanup, not decided

This mechanism does not pick the resource design. Two extensions stay open, and neither is blocked.

A binding-shaped cleanup is David's `#on_cleanup` (discussion_points.md:1193): the cleanup is tied to the variable, and Python's `with` is more wrapping than he wants for a file. A region-shaped cleanup is a scope call, which is what `bracket` is. A ticker is `defer frames.stop()` inside the brace, which already runs on `return` and on `or_throw`.

The parameter is a restricted form of the code snippet in discussion_points.md:2760–2790, not that type. `Code` is a first-class unevaluated snippet: you store it and `#expand` it later, and it is hygienic. `scope` is not a value, runs at most once, is checked once, and the names in the brace are the caller's names. Sharing the word would make a stored snippet and a brace the same spelling. Jai's `#insert body(break=…)` remains the extension point if a block ever needs to run more than once.

## Rejected

- **Callee-directed braces.** `if c h() { }` would run the block conditionally or not depending on a declaration the parser, and the reader, cannot see. DEC:485. The marker is the reason we can do without that.
- **Reading B.** An assignment that catches `return` makes `return` mean two things, and it is the callback result David rejected.
- **`Timeout` on the operation.** The result of `read_text` would depend on the caller. proposal-v5.md:192.
- **`retry`, or any block that runs more than once.** The caller's initialization, moves, and integer domain would depend on the library body. M5 removes that analysis.
- **Three keywords, or making `parallel` a scope function.** `parallel` items are not one synchronous call on the caller.
- **An inline lambda whose `return` changes with the parameter.** The reader cannot see, at `=>`, which `return` it is. That is a worse context sensitivity than a callee-directed brace, and it is the callback look.
- **Naming the parameter `Code`.** Different thing, above.

## Programs

`programs-r2/`. 01–10 and 12 revise the round-1 programs. 11 replaces `retry` with a once-only `traced`. 13–15 are the regrade's edge programs, now with the marker and the rules. 16 is a failure-free `return` replaced by a child that has already failed, and a `return Missing` that is kept. 17 is a failing `close` on `return`.
