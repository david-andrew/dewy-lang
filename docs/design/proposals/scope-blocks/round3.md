# Scope blocks, round 3

A call takes a scope block only when the call site says so: `do { }` when nothing is bound, `with pattern { }` when something is. The brace runs as part of the caller. `return`, `break`, `continue`, and `or_throw` target the function that wrote the brace, and the loop a plain block in that position would reach. The callee is an ordinary function with a `scope(…:>R)` parameter. It runs the block at most once, on its own task, and its `defer`s run on every way out. `task.catch_ctrl_c`, `task.tasks`, and `task.protect_from_cancel` are three such functions. A listener or a group passed into the brace cannot be used after it.

Round 2 marked the brace at the call and kept operation types stable. It still treated provenance as a property of the `Canceled` value, inferred a group's `E` from a result position that does not mention `E`, and removed alternatives at each call. This round stops doing those three things. A defer's failure is an `or_throw` from the function that wrote the defer. For a scope function, that means the caller resumes after the call with the failure as the call's result.

## Rules

### Where the brace attaches

`do` and `with` are keywords. A `{` is a scope block only when one of them stands between the call and the brace.

```dewy
task.catch_ctrl_c do { printl"ready" }
task.catch_ctrl_c with ctrl_c { ctrl_c.next }
task.tasks with group { group.spawn(@work); }
task.protect_from_cancel(5s) do { save(best) }
```

`do { }` binds nothing. `with pattern { }` binds. There is no second spelling: `do with pattern { }` is not a call. A newline may sit between the call and `with`, and between the marker and `{`, because a newline does not end a statement.

```dewy
task.catch_ctrl_c
    with ctrl_c {
        ctrl_c.next
    }
```

The marker is a postfix at member and call precedence (LANGUAGE.md:1415). It applies to the last call in a postfix chain. That callee must be a statically named scope function or method. `f(1)(2) do { }` and `@f do { }` are "call it with its block". `??`, `or_throw`, and binary operators apply outside the brace. `g() do { }` and `g do { }` are the same call. A scope call is not a zero-argument call: `catch_ctrl_c do { }` does not write `()`.

`if`, `loop`, and `match` do not take a brace the marker has consumed. The head's body is the statement that remains.

```dewy
if verbose task.protect_from_cancel(1s) do { write(total) } ??<Timeout> { printl"log skipped" }
loop port in ports task.protect_from_cancel(2s) do { if ready break }
match task.protect_from_cancel(5s) do { save(best) } {
    saved:Path => printl"saved to {saved}"
}
```

If the marker consumes the only brace and the head has no body, the error is "these braces belong to protect_from_cancel; the if needs a body. Parenthesize the call or bind it first." The same sentence is used for `loop` and `match`.

A `{` with no marker is a block, as today. `if f(x) { … }`, `loop it.has_next { … }`, `match parse(text) { … }`, an `else` body, and a `??<E> { }` handler are not warnings. A `{` in statement position, on the same line after a call that has no marker and is not one of those heads, warns: "this block is a separate statement; put it on its own line."

An overload set may mix a scope variant and a non-scope variant of the same arity. The marker selects the scope variant. Methods use the same marker: `m.locked with v { }`. A `{` juxtaposed as a value argument is not a scope block. `inc{10}` would be the call in discussion_points.md:601, with the block's value evaluated first. Today `f{1}` is an error ("'f' needs arguments").

The pattern after `with` is one `let` pattern. `with ctrl_c` binds one value. `with (ctrl_c group)` and `with [ctrl_c group]` are that one pattern (LANGUAGE.md:2601). `with ctrl_c group` is not a pattern. The names are bound by the call, from the values the scope function passes in. They are not names the caller already has. Omitting `with` when values are passed discards them, the way `_` discards a binding. `;` discards a result.

### The parameter

```dewy
body:scope(ctrl_c:CtrlCListener:>R)
body:scope(group:Tasks<E>:>R)
body:scope(:>R)
```

`R` is the block's one normal result, inferred, and a type parameter of the scope function. The scope function is checked once. A scope parameter is not a value. `@task.catch_ctrl_c`, storing `body`, or passing it to an ordinary function parameter is "call it with its block". Passing it on is `inner(body)`, where `inner` takes the same `scope` type. The block's `return` still targets the function that wrote the brace.

The block compiles to a non-escaping local function whose result is an exit: a normal value, `return v`, `break` or `continue` with its label, or a forwarded failure. `body(…)` either returns the value or starts that exit through the scope function's defers. The call site dispatches the exit. Inlining is an optimization. The per-site cost is the block.

`body` is move-only. The at-most-once check is the move check: the invocation consumes it, and a success path must have consumed it. A path that returns a success without consuming it is an error. A path that cannot run the block returns a failure, as a failed `open` does. On the call's failure path, a move inside the brace is treated as moved, and a `let` assigned inside the brace is not definitely initialized. On the success path the brace is straight-line: one move, one initialization, and a `+= literal` counts as once (LANGUAGE.md:335–337).

The block runs on the scope function's own task, synchronously. `group.spawn` of the block, a `parallel` item, a `race` or `within` thunk, and any `@` handle that captures `body` are "a scope block runs on this task".

A repeated block is not this parameter. A later form that runs a block several times needs its own marker and is checked at the caller like a loop. discussion_points.md:2774 (`#insert body(break=…)`) is the shape of that marker. It is not this round, and `retry` is not a scope function.

`scope` is also a cancel scope (LANGUAGE.md:3457), a metatag scope, and a value parameter (`lib/prelude/time.dewy:63`). Those are value positions. `(scope:scope(:>R))` is a legal type next to that parameter. `block` would collide with the blocks effect. The name stays.

When a type parameter is constrained by `T | E` against a concrete union, `E` takes the error alternatives and `T` the rest. `T = Log | FileNotFound, E = never` does not win. That is generic inference, not a rule about `bracket`.

### What a statement contributes

A scope block follows the same rules as a function body written `:>R` (LANGUAGE.md:280–310, :1387).

- A statement without `;` contributes every value it expresses.
- A void statement contributes nothing.
- `;` discards everything the statement expresses, including failures.
- `R` is one value: the last contribution, and the only one. An earlier statement that contributes a value is an error: "this block expresses 2 values; the scope result is 1." It is not a tuple and not a second result.
- `group.spawn(…)` expresses a task handle. Without `;` that handle is one of the block's values.

The call's result is the scope function's declared result (`R | E`, `R | Timeout`), one value. It does not grow a second value from an earlier statement.

### Control flow

Code in the scope function is ordinary: its `return` is the value of the call. Code in the brace belongs to the caller.

| Written in the brace | Target |
|---|---|
| `return` / `return v` | the function that wrote the brace, or its generator once generators exist |
| `break` / `continue`, including `break $label` | the loop a plain block in that position would reach |
| `or_throw` | that same function, as a returned failure |
| a normal result | the one value `R` the scope function receives |

An assignment does not catch `return`. `let x = task.tasks with group { return 1 }` stops and joins the group; if that join succeeds, the enclosing function returns `1` and `x` is never bound. The enclosing result must accept `1`. This is what a plain block already does: `let x:int = { if c return 1; 5 }` returns `1` from the enclosing function.

discussion_points.md:455, that a `return` runs until an assignment or a function, is about generator literals (`A1:int={return 1}`). It is not the rule for a block in a function. Line 465 is a `return` inside an assigned `[loop …]` and it "breaks out of function". Line 502: returns stop at functions and generators. A scope block is neither.

A future `yield` in a scope block belongs to the enclosing generator. `express` (discussion_points.md:481) is not decided.

`or_throw` inside the brace is the same as `or_throw` in a plain block. It targets the function that wrote the brace. A `??`, a `match`, or an `or_throw` written on the call sees only the call's result. It does not catch the brace's `or_throw`.

Two runtime cases turn a pending exit into the call's result instead. Both are an `or_throw` from the scope function, whose return is the call's value, so the caller resumes after the call. The call's declared type already includes that failure. Nothing is removed from the type at the call site.

1. A defer in the scope function fails while the pending exit carries no failure. See below.
2. A cancel scope closes because of its own reason, and the parent has not been canceled. A pending `Canceled` exit is replaced by that reason. See below.

Statically, the brace's `or_throw` still adds every alternative it forwards to the function that wrote the brace. `probe(port) or_throw` in program 09 adds `FileNotFound | Canceled` to `serve_until`. At run time a deadline `Canceled` becomes the call's `Timeout`, `??<Timeout>` handles it, and that path does not leave `serve_until`. A `FileNotFound` does leave. The signature lists `FileNotFound` and `Canceled`. It does not drop `Canceled` because a deadline might replace it.

`append_file(…) or_throw` in program 17 adds `FileNotFound | Canceled` to `replaced`. The `??<FileNotFound>` on the call does not catch it. The close's `FileNotFound` is a defer in `bracket`, so that one is the call's result, and `??` does catch it.

`defer` inside the brace runs when that invocation ends, before the scope function's own defers. Inner first, each list in reverse. Both lists run on a normal result and on `return`, `break`, `continue`, and `or_throw`.

`return` and `break` inside a `parallel` body are still illegal, including when that body is a scope block or contains one: "return cannot leave a parallel body." `parallel` stays a keyword because its items are not one synchronous invocation on the caller. Items may wait (decisions, batch 3). A blocking scope call inside a `parallel` body is allowed on that rule. A listener or group borrowed by the brace cannot be used from a `parallel` body: "group belongs to this tasks block and cannot be used from a parallel body". The brace runs on this task; a `parallel` body does not.

### Defer failures

`defer` is not in the front end yet. Scope exits need one rule, and it is about every `defer` (DEC:484), not a special case for scope functions.

A defer's failure is an `or_throw` from the function that wrote the defer (LANGUAGE.md:3779). It replaces a pending exit that carries no failure: a normal success value, `return` of a non-failure, `break`, or `continue`. A pending failure is kept (`return Missing`, a normal result that is an error or an exception, an `or_throw` already started). The defer still ran. Its failure is not reported. One function returns one failure. Reporting both, or an error with a cause, is open. v5 wanted a save failure reported; this round does not add that channel. Cleanup, below, records the open point.

For an ordinary function, the `or_throw` returns from that function. A failing `defer log(x) or_throw` during `break` leaves the function with the failure. It does not resume the loop, and it does not become the loop body's value.

```dewy
loop x in xs {
    defer log(x) or_throw
    if x =? 0 break
}
```

For a scope function, the function that wrote the defer is the scope function. The caller resumes after the call, and the failure is the call's result. `let code = task.tasks with group { return 0 } ??<WalkError> -1` binds `-1` when the join fails. The function does not return `0`.

A `??` or a `;` that defaults or discards a call whose brace contains a failure-free `return`, `break`, or `continue` warns: "this return does not leave the function if a defer in tasks fails; execution continues after the call with that failure." The same sentence is used for `break` and `continue`. The fix-it is to forward with `or_throw`, or to match the call.

### Cancel scopes

Operation types do not change with the caller (proposal-v5.md:192). Inside a shield, a canceled operation is `Canceled`, the same as outside. `Canceled` is a unit value (LANGUAGE.md:3456). It has nowhere to carry an origin. Provenance is the scope's own state.

When a cancel scope closes because of its own reason, and the parent has not been canceled, a pending `Canceled` exit is replaced by that reason, and that reason is the call's result. The exit may be `or_throw` of a fresh `Canceled`, `return Canceled`, or a normal result whose value is `Canceled`. Spelling a new `Canceled` does not keep it.

- The shield's deadline fired: the reason is `Timeout`.
- The group is failing fast: the reason is the first child failure, `E`.
- The parent has been canceled: the `Canceled` stays, and it leaves the function that wrote the brace.
- A child the block stopped itself does not put the group into the failing-fast state. Its `Canceled` stays `Canceled`.

`.wait` on a child that has already finished returns that child's result (`void | E`), even if the waiting scope is canceled. A wait on a child that has not finished is still level-triggered: a canceled waiter gets `Canceled` (LANGUAGE.md:3457, proposal-v5.md:266).

The call's type is the scope function's declared result. Nothing is subtracted at the call site. `protect_from_cancel` is `R | Timeout`. `tasks` is `R | E`. A `Canceled` the brace forwards is also on the enclosing function, because the type is the plain union.

`E` is part of the group: `Tasks<E>`, `body:scope(group:Tasks<E>:>R)`, `join:(group:Tasks<E>):>void | E`. `E` is inferred from the constraints `group.spawn` places on the block, which is what proposal-v5.md:274 already says. A helper that takes `group:Tasks<E>` carries `E`. A wrapper is `<R E>(body:scope(ctrl_c:CtrlCListener group:Tasks<E>:>R)):>R | E | Canceled`. It is checked once. It is not a template.

Waiting for children inside `join` is not bounded by the 100 ms cleanup grace (LANGUAGE.md:3472). The children's own cleanup is.

### `tasks`

A non-normal exit (`return`, `break`, `continue`, `or_throw`) stops the group, then joins. A normal result that is a failure value (an `error` or an `exception`) stops, then joins. A normal success joins and does not stop. This is v5's rule for an ordinary callback failure (proposal-v5.md:275) plus the early-exit rule `concurrent` already has (LANGUAGE.md:3445–3446). A persistent child that should outlive a normal success must be stopped by the block. An owner `stop` is normal shutdown, not a child failure.

The flag lives in the library. The call site does not write a stop.

```dewy
catch_ctrl_c = <R>(body:scope(ctrl_c:CtrlCListener:>R)):>R => {
    let frame = push_catcher()
    defer pop_catcher(frame)
    body(frame.listener)
}

tasks = <R E>(body:scope(group:Tasks<E>:>R)):>R | E => {
    let group = open_group()
    let finished = false
    defer {
        if not finished group.stop()
        join(group) or_throw
    }
    let result = body(group)
    finished = result isnt? error and result isnt? exception
    result
}

protect_from_cancel = <R>(limit:Time body:scope(:>R)):>R | Timeout => {
    let shield = push_shield(limit)
    defer pop_shield(shield)
    body()
}
```

`pop_shield` applies the state rule. `join(group) or_throw` is the defer's `or_throw` from `tasks`.

```dewy
bracket = <T E R>(
    open:():>T | E
    close:(handle:T):>void | E
    body:scope(handle:T:>R)
):>R | E => {
    let handle = open() or_throw
    defer close(handle) or_throw
    body(handle)
}
```

### Borrow, tags, and the three behaviors

Every value passed into the brace is borrowed for the brace, including a plain record. The extent is the brace, not the last use. Storing one, returning it, or capturing it is "ctrl_c belongs to this catch_ctrl_c block". Passing it to a helper parameter is legal for that call. `CtrlCListener` has no `Closed`.

A `select` of several sources uses the qualified arm, `<ctrl_c.CtrlC>` and `<frames.Tick>`. A match on one `ctrl_c.next` uses `<CtrlC>`. That is v6, unchanged.

The rest of the three scopes is unchanged. Default Ctrl-C still cancels the root and, unhandled, exits 130. The next press, and three presses within one second while a catcher or a shield is up, still force exit 130. `catch_ctrl_c` routes presses to the innermost catcher on the foreground task, then restores the previous route. It does not mask `Task.stop`, sibling failure, deadlines, or any other cancellation. A waiting console read receives `Interrupted` and consumes that press. Otherwise the press is available from `ctrl_c.next`, and a press queued for `.next` does not later become `Interrupted`. A child in the terminal's foreground process group still receives SIGINT. `catch_ctrl_c` off the foreground task is "Ctrl-C catching runs on the foreground task". `protect_from_cancel` runs despite a pending parent cancel, with a required cooperative deadline, then restores the parent without clearing it. Nested protection does not extend an outer deadline. `check_cancel()` is not a scope.

### Diagnostics

- A lambda where a scope block belongs: "this block is part of the caller, so `return` leaves this function. Write `task.catch_ctrl_c do { … }`."
- A `{` in statement position on the same line after a call with no marker: warning, "this block is a separate statement; put it on its own line." Not on `if`, `loop`, `match`, `else`, or a `??<E> { }` handler.
- A head left without a body: "these braces belong to protect_from_cancel; the if needs a body. Parenthesize the call or bind it first."
- A second invocation, or a call from another task: "a scope block runs at most once" / "a scope block runs on this task".
- A listener or group stored past the brace, or used from a `parallel` body: "ctrl_c belongs to this catch_ctrl_c block".
- `@task.tasks`, or a callee that is not a named scope function: "call it with its block."
- `return` or `break` leaving a `parallel` body: "return cannot leave a parallel body."
- A block that contributes the wrong number of values: "this block expresses 2 values; the scope result is 1."
- A `??` or `;` on a call whose brace has a failure-free `return`, `break`, or `continue`: warning, "this return does not leave the function if a defer in tasks fails; execution continues after the call with that failure."

### Cost

The scope function is checked once. Each site checks its block. No pass looks at a function that has no scope call. The call does not allocate a closure.

## The three scopes, and D4

```dewy
repl = () => task.catch_ctrl_c do {
    loop true {
        let line = input("> ") ??<Interrupted> { printl""; continue } ?? break
        if line =? "quit" break
        printl"you said {line}"
    }
}

save = (best:int):>Path | FileNotFound | Canceled => {
    p"best.txt".write_text("{best}\n") or_throw;
    p"best.txt"
}

main = () => {
    let best:int = 0
    search(@best) ??<Canceled> {
        match task.protect_from_cancel(5s) do { save(best) } {
            saved:Path => printl"saved to {saved}"
            <Timeout> => printl("save deadline expired" file=stderr)
            <Canceled> => Canceled or_throw
            problem:error => printl("save failed: {problem}" file=stderr)
        }
        return Canceled
    }
    save(best) or_throw;
}
```

`save`'s `or_throw` targets `save`. The block's value is `Path | FileNotFound | Canceled`, so the call's result is that union plus `Timeout`. The `<Canceled>` arm stays: the type is not narrowed when a deadline happens to become `Timeout`. The `<Timeout>` arm is that deadline, and only when the shield's own reason fired. `write_text` returns a byte count; `save` discards it and returns the path.

D4's prompt breaks the loop on `quit`, as above, and then the line after the call runs. Program 01 uses `return`, so that line is skipped. The north-star group's call is:

```dewy
task.tasks with group {
    let saver = group.spawn(@autosave)
    let tick = ticker(500ms)
    defer tick.stop()
    loop i in [0..4) tick.next or_throw;
    saver.stop()
} or_throw
```

The loop finishes with a success, so the join does not stop `saver`. The block stops it. `tick.next or_throw;` forwards `Canceled` and discards the tick. `spawn` without `;` would contribute the task handle; the `let` binds it, so the statement contributes nothing further.

## Cleanup, not decided

A binding-shaped cleanup is `#on_cleanup` (discussion_points.md:1193). A region-shaped cleanup is a scope call, which is `bracket`. Neither is chosen here.

`scope` is not the `Code` snippet in discussion_points.md:2760–2790. `Code` is a first-class unevaluated snippet you store and `#expand`. `scope` is not a value, runs at most once, and the names in the brace are the caller's. A repeated block, if it comes, is a different marker in the direction of `#insert body(break=…)`.

Open: when a defer fails and the pending exit is already a failure, the defer's failure is dropped. v5 wanted a save failure reported. An error with a cause, or a second reported failure, is a cleanup decision, not a second rule for scope calls.

## Rejected

- Callee-directed braces, and `do with` as a second spelling of `with`.
- An assignment that catches `return`.
- Provenance stored on the `Canceled` value, and any rule that removes `Canceled` or `E` from the type at a call site.
- `Timeout` on the operation's type.
- "Resumes at the scope that owns the defer." That continues a loop whose `break` a failing defer interrupted.
- A scope function that invokes the block more than once.
- Rejecting a blocking call inside `parallel`. Batch 3 lets items wait.
- Naming the parameter `Code`.

## Programs

`programs-r3/`. 07 puts the flush back in the `select` arm. 08 returns `Missing` after a child has already failed, and does not add a channel to hide that. 11 is a once-only helper whose `return` and `break` leave the caller. 14 writes the rejected `parallel` forms as code. 02 does not drain a press the rule already keeps off the next `input`. 04 throws a fresh `Canceled`; the group's state, not the value, decides whether that becomes `WalkError`.
