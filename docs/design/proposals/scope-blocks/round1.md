# Scope blocks

A call may take a **scope block**: braces that run as part of the caller, not as a function. `return`, `break`, `continue`, and `or_throw` inside the braces target the enclosing function and its loops, exactly as they do in a `{ ... }` block written in that function. The called function still runs its setup before the block and its `defer`s on every way out, including `return` and `or_throw`, before that exit completes. `task.catch_ctrl_c`, `task.tasks`, and `task.protect_from_cancel` are ordinary functions with a scope parameter, so any library can define its own scope the same way. A value the block receives is named with `with` between the call and the brace. The braces are the whole extent of the policy: a Ctrl-C listener or a task group cannot be used after them.

```dewy
import p"@lib/std/tasks.dewy" as task

task.catch_ctrl_c { ... }                    # no borrowed name
task.catch_ctrl_c with ctrl_c { ... }        # ctrl_c is this block's listener
task.tasks with group { ... }                # group joins before the call is over
task.protect_from_cancel(5s) { save(best) }  # ordinary arguments, then the block
```

## Rules

### The call

A scope parameter is a parameter whose type is `scope` or `scope(...)`. It is not a function value. The call writes the block after its ordinary arguments. `with` and a pattern bind the values that invocation passes in; the pattern is whatever `let` allows (`ctrl_c`, `[a b]`, `(a b)`).

```dewy
catch_ctrl_c = (body:scope(ctrl_c:CtrlCListener)) => {
    let frame = push_catcher()
    defer pop_catcher(frame)
    body(frame.listener)
}
```

`body(frame.listener)` runs the caller's block once, here, on this task. It is not a call through a function value: `body` cannot be stored, copied with `@`, or passed to an ordinary function parameter. It can be passed on to another scope parameter, and the block's `return` still targets the function that wrote the braces. A library may invoke the block more than once (`retry` does). Each invocation is synchronous, on the calling task, and finished before the scope function returns. Invoking it from a spawned task, or after the scope function has begun to return, is a compile error.

Omitting `with` discards the values the block is passed. Hover on the call says what was discarded and shows `with ctrl_c`. A block that is given nothing has no `with`.

The block is not an argument expression. It does not run before the call, and it is not a closure: writes to the enclosing function's locals are writes, with no `$capture`. A `{` after `;`, or a `{` that opens the next statement, is an ordinary block.

The scope function itself is not a value. `@task.catch_ctrl_c` is an error: "call catch_ctrl_c with its block". The compiler specializes each call to the block's result (one specialization per block type at that site, including a call in a loop). Programs that never call a scope function pay nothing.

### Control flow

Code written in the scope function is ordinary. Its `return` returns from that function, which is the value of the call. Code written in the braces belongs to the caller:

| Written in the block | Target |
|---|---|
| `return` / `return v` | the enclosing function |
| `break` / `continue`, including `break $label` | the enclosing loop, the same one a block in that function would reach |
| `or_throw` | the enclosing function, as a returned failure |
| a normal result | the value of that invocation, which the scope function receives |

A scope block is part of the enclosing function for loop labels, the same-function rule on source-qualified `select` arms, and borrow checking.

`defer` inside the block runs when that invocation ends, before the scope function's own `defer`s. Both run on a normal result and on `return`, `break`, `continue`, and `or_throw`, before the exit leaves the scope function. Order is the usual one: inner defers first, each list in reverse.

A `defer` in the scope function may `or_throw`. That failure becomes the call's result, and a pending successful exit (`return`, `break`, `continue`, or a normal value) is dropped, so the caller of `task.tasks` still sees a child failure. A `Canceled` injected because this group is failing fast is the same: the child failure replaces it, so a failed child is not reported as a bare `Canceled`. Any other `or_throw` the block already started is kept; the defer still runs, and its failure does not replace that error. Cleanup that succeeded is not rolled back.

The call's result is the scope function's result, with the block's value count preserved. A block that expresses nothing is void. A useful value is bound or discarded with `;`. Child failures and `Timeout` are results of the call, not a second channel.

### Borrow

Values passed into the block are borrowed for that invocation. The extent is the brace, not the last read. Storing one in an outer binding, returning it, or capturing it in a closure is an error naming the scope ("ctrl_c belongs to this catch_ctrl_c block"). After the brace there is no handle and no `Closed`: the v6 rule that `task.CtrlCListener` is borrowed, and has no `Closed`, stands. The same rule applies to the `Tasks` group.

### Ctrl-C, groups, protection

The behavior of the three scopes is unchanged except for one spelling of the protection deadline, stated below. In particular:

- Default Ctrl-C still requests root cancellation. Unhandled, that `Canceled` exits 130. The next press, and three presses within one second while a catcher or a shield is up, still force exit 130.
- `catch_ctrl_c` routes presses to the innermost catcher on the foreground task for the brace's lifetime, then restores the previous route. It does not mask `Task.stop`, sibling failure, deadlines, or any other cancellation. A waiting console read (`input`, `input_int`, `input_float`, `read_line`, stdin lines) receives `Interrupted` and consumes that press; those functions' types always include `Interrupted`. Otherwise the press is available from `ctrl_c.next`, including `@ctrl_c.next` inside `select`, and presses coalesce. A press queued for `.next` does not later become `Interrupted`. A child in the terminal's foreground process group still receives SIGINT. Calling `catch_ctrl_c` off the foreground task is a compile error naming the foreground context; a helper that calls it carries the same requirement.
- `tasks` opens a fresh fail-fast group, runs the block on the caller, and joins before the call returns and before a `return` or `break` from the block leaves. The block's value is the call's value when the join succeeds. A child failure or parent `Canceled` is the call's result instead. An owner `stop` is normal shutdown, not a child failure.
- `protect_from_cancel` runs the block once under a fresh cancellation scope even if the parent is already canceled, with a required cooperative deadline, then restores the parent without clearing it. There is no cancel thrown at the caller afterwards. The next checkpoint sees a still-pending parent request. Nested protection does not extend an outer shield's deadline. The call's result is the block's result plus `Timeout`.

**Deadline spelling.** While a shield is up, an operation canceled by that shield's deadline returns `Timeout`, not `Canceled`. A genuine `Canceled` (a stopped child, an explicit `Canceled`, a parent cancel observed outside the shield) stays `Canceled`. v5 rewrote a deadline `Canceled` into `Timeout` only as the callback's result crossed the wrapper. A block's `or_throw` does not stop at the scope function, so the operation that observes the deadline is where `Timeout` appears. Inside and outside the brace it is the same value.

Illustrative library shape (the `push_` / `pop_` / `join` names are internal):

```dewy
catch_ctrl_c = (body:scope(ctrl_c:CtrlCListener)) => {
    let frame = push_catcher()          # requires the foreground task
    defer pop_catcher(frame)            # restore the previous route
    body(frame.listener)
}

tasks = (body:scope(group:Tasks)) => {
    let group = open_group()
    defer join(group) or_throw          # failure replaces a successful exit
    body(group)
}

protect_from_cancel = (limit:Time body:scope) => {
    let shield = push_shield(limit)     # masks the parent; deadline observes as Timeout
    defer pop_shield(shield)            # parent request left as it was
    body()
}
```

`check_cancel()` is not a scope. It remains one checkpoint.

### Diagnostics

- A lambda passed where a scope block belongs: "this block is part of the caller, so `return` leaves this function. Write `task.catch_ctrl_c { ... }`."
- A listener or group stored past the brace: "ctrl_c belongs to this catch_ctrl_c block."
- `catch_ctrl_c` off the foreground task: "Ctrl-C catching runs on the foreground task" (naming the helper chain).
- `@task.tasks`, or a scope parameter passed as a function value: "call it with its block."
- `break` / `continue` with no enclosing loop: the ordinary error.

### Cost

The check runs only at a scope call. It is linear in the block plus the scope function's body, the same work as typechecking that body in the caller: exits, borrows, and defers. No pass looks at a function that has no scope call. The call is direct, or inlined; it does not allocate a closure. Qualified `select` arms keep today's same-function check, with the block counted in that function.

## The three scopes

```dewy
import p"@lib/std/tasks.dewy" as task

repl = () => {
    task.catch_ctrl_c {
        loop true {
            let line = input("> ") ??<Interrupted> { printl(""); continue } ?? break
            if line =? "quit" return
            printl"you said {line}"
        }
    }
    printl"end of input"
}

run_jobs = () => {
    task.tasks with group {
        let saver = group.spawn(@autosave)
        let tick = ticker(500ms)
        defer tick.stop()
        loop i in [0..4) tick.next or_throw;
        saver.stop()
    } or_throw
}

keep = (best:int) => {
    match task.protect_from_cancel(5s) { save(best) } or_throw<Canceled> {
        saved:Path => printl"saved to {saved}"
        <Timeout> => printl("save deadline expired" file=stderr)
        problem:error => printl("save failed: {problem}" file=stderr)
    }
}
```

`quit` returns from `repl`. The line after the brace runs only when the loop `break`s (end of input). `break` and `continue` in the `??` fallbacks target that loop. `saver.stop()` is a void call, so it keeps `()`. `tick.next` gives a value, so it does not.

## A prompt with its own Ctrl-C behavior

```dewy
# Ctrl-C during input clears the line. quit returns from repl.
# End of input ends the loop, prints, and then leaves repl.
import p"@lib/std/tasks.dewy" as task

repl = () => {
    task.catch_ctrl_c {
        loop true {
            let line = input("> ") ??<Interrupted> { printl(""); continue } ?? break
            if line =? "quit" return
            printl"you said {line}"
        }
    }
    printl"end of input"
}
main = () => {
    repl() or_throw
    # The catcher ended with the block, whether quit returned or input ended.
    printl"normal Ctrl-C behavior restored"
}
```

## Save on Ctrl-C

Normal cancellation stops the search. The save runs under its own deadline, then `main` preserves `Canceled` (exit 130). `save` returns the path it wrote; `write_text` itself returns a byte count.

```dewy
# Ctrl-C requests ordinary cancellation. Save, then preserve exit status 130.
import p"@lib/std/tasks.dewy" as task

search = (@best:int):>void | Canceled => {
    loop n in [0..1_000_000_000) {
        check_cancel() or_throw
        if n % 7919 =? 0 best = n
    }
}
save = (best:int) => {
    p"best.txt".write_text("{best}\n") or_throw;
    p"best.txt"
}
main = () => {
    let best:int = 0
    search(@best) ??<Canceled> {
        match task.protect_from_cancel(5s) { save(best) } or_throw<Canceled> {
            saved:Path => printl"saved to {saved}"
            <Timeout> => printl("save deadline expired" file=stderr)
            problem:error => printl("save failed: {problem}" file=stderr)
        }
        return Canceled
    }
    save(best) or_throw;
}
```

`return Canceled` is outside the shield, in `main`, so the exit stays 130. A `return` written inside the shield would also leave `main`, after `pop_shield`. Falling out of the `??<Canceled>` arm instead of returning keeps the partial result and exits 0. The shield does not swallow a file error: it is the block's value, and the `problem:error` arm reports it.

## Cleanup, later

This round does not choose how files, locks, or tickers are cleaned up. The scope block is the piece a region-shaped answer would use, and it leaves the binding-shaped answer alone.

A library that acquires, uses, and releases is a scope function. The use is the caller's block, so `return` and `or_throw` still release, and the caller does not write a second `defer`:

```dewy
bracket = <T E>(open:():>T | E close:(handle:T):>void | E body:scope(handle:T)) => {
    let handle = open() or_throw
    defer close(handle) or_throw
    body(handle)
}

bracket(@open_log(p"app.log") @close_log) with log {
    log.write(line) or_throw
    if line =? "quit" return
}
```

That is the shape of `defer <expr> { ... }`: the call's ordinary arguments acquire, the brace uses, the scope function's `defer` releases. `open(path) with file { ... }` is the same pattern when the region should be smaller than the function.

A binding whose lifetime is the cleanup, with no extra indent over the rest of the function, stays a move-only value with `$__drop__`. The hook already runs on `return`, `break`, and `or_throw`. That matches the "cleanup tied to the variable" note, and it is not implicit C++ destruction of copies: the type is move-only, the hook is a method, and an alias does not create a second owner. Scope blocks do not replace that. A ticker can keep `defer tick.stop()` until that round. `@(m.lock())` can keep lending until last use.

A failing `close` uses the exit rule above. On a successful `return` it becomes the call's result, so the failure is not dropped. On an `or_throw` the original error keeps going after `close` runs.

## Considered and rejected

- **A callback `(ctrl_c) => { ... }`.** `return` and `break` stay in the callback, and `or_throw` stops at it. The block has to pass them along by hand. That is the shape this round replaces. Swift's trailing closure has the same local `return`.
- **`{ ctrl_c in ... }` or `(ctrl_c) =>` as the header.** It reads as a closure, so `return` looks local. The braces are a block; the borrowed name stays outside them, next to the call.
- **`let ctrl_c` as the binder.** `let name` with no value is already an uninitialized binding. `let` in this position would be that declaration.
- **`as ctrl_c`.** `as` is conversion: `text as array<uint8>`, `x as int64`.
- **A leading `with` statement**, as in Python. The call is already the region. A statement in front of it adds a keyword, and `with task.catch_ctrl_c as ctrl_c` needs `as`. David's objection to `with` for files is the forced indent around a value whose lifetime should be the binding; this design does not make resources use that indent. `with` here only names the borrowed value of a scope the braces already delimit.
- **Three keywords, or a metatag on a block.** A keyword per policy is not something a library can define, so `bracket` and `retry` could not exist. A metatag does not change a type, and it does not take a runtime duration or return `Timeout`. Catching and protection are operations.
- **`let ctrl_c = task.catch_ctrl_c` until drop.** Aliases hide the extent. The policy would last until the last owner, which is the objection that removed the activating guard. Drop hooks remain for values that should work that way.
- **Making the scope function's own `return` leave the caller.** A `return` in `catch_ctrl_c`'s body returns the call's result. Only the brace uses the caller's control flow. Kotlin's inline lambdas are the prior art for that split; Dewy does not use an arrow to get it.
