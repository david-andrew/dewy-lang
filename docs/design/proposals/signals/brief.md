# Design round: Ctrl-C and other signals as events, handled in parallel with the work

You are designing one piece of the Dewy programming language. Write the design, dogfood it, and iterate until it is good. You may read anything in `~/dev/dewy-lang` (read-only: change nothing in that checkout). Write only under `~/dev/tmp/par8/signals/`.

## Where this stands

Earlier proposals for catching Ctrl-C used a callback (`task.catch_ctrl_c((ctrl_c) => { ... })`), then a new block syntax (`task.catch_ctrl_c inline { ... }`, see `docs/design/proposals/scope-blocks/`). David, who owns the language, rejected both:

> I feel like you all have just been inventing new syntax without really trying to think about something that works largely within the existing design, utilizes dewy's strengths and style. For example, why cannot catching ctrl-c literally just be something you do in parallel with your regular work?

```dewy
parallel {
    regular_work()
    whatever_ctrl_c_handler()
}
```

> e.g. it could look like this: (note this is notional, don't necessarily copy this exactly)

```dewy
main = parallel {
    loop {
        do_work()
    }

    loop {
        signals.interrupt.next()
        printl"Ctrl+C received"
    }
}
```

> (e.g. there probably needs to be a better mechanism for the interrupt handler to stop looping when the regular work is done. also I'm not necessarily sold on those exact names/shapes of the members like `interrupt`/`next()`. But this gives a taste of what I think plays to dewy's strengths without just inventing new syntax)
> I think perhaps a repl example might look like this:

```dewy
repl:type = [
    alive:bool = true
    run = () => loop true {
        let line = readl(">>> ") ?? (alive=false break)  #presuming readl returns `none` on ctrl-d
        printl"you said {line}"
    }
    run() # start the repl as soon as an instance is constructed
]

main = () => parallel {
    r = repl

    loop r.alive {
        signals.ctrl_c.next()
        printl"KeyboardInterrupt"
    }
}
```

> And I think this also indicates a very straightforward approach for handling any types of external signals the program might receive (an approach that works within the existing dewy constructs, and (I presume?) leaves nothing to be desired)

His sketches are notional: keep the idea (signals are event sources; handling them is ordinary concurrent code), not necessarily the exact names or shapes.

## The rule for this round

**Start from what Dewy already has, and add nothing until you have shown that the existing constructs fail.** Existing pieces to compose: `parallel { }` blocks and comprehensions, event sources like `ticker` with `.next`, channels, `select` (arms match by type; source-qualified arms like `<heart.Tick>`), `merged`, `race` (cancels the losers), `first_ok`, `within`, `Task` handles (`spawn`, `.stop()`, `.wait`), `check_cancel()`, `Canceled` as a value, `or_throw`, `??`, records/types with members, `@` handles and partial application, metatags. If a case truly needs something new, write the program with existing constructs first, show where it fails, and keep the addition minimal; the comparison goes in the design. A new member name is fine when needed, but every new name will be cold-read.

## What to read first

- `docs/design/open_decisions.md` D4 (the concurrency design; Q4 is this item) and `docs/design/decisions.md` batches 3–8 (binding; batch 8 records David's direction above and Q6: metatags prefix what they attach to).
- `docs/design/proposals/concurrency/unified/proposal-v5.md` (search `catch_ctrl_c`, `protect_from_cancel`, `Interrupted`): the semantics the earlier designs kept (default Ctrl-C cancels the root and exits 130; three rapid presses force exit; console reads; child processes in the foreground process group). `select-v6-round11.md` for `select`/`race`/`merged`.
- `docs/design/proposals/scope-blocks/summary.md` and its reviews, for the problems the rejected design had to solve (they still need answers: cancellation of the work, saving on Ctrl-C under a deadline, task groups, early exit).
- `docs/LANGUAGE.md`: "Parallel CPU work", "Channels", "Errors as values", "Loops, text and optional values", "Files, paths and processes", "Records and collections" (types with members). Check what a type whose body calls `run()` does when constructed.
- Before proposing any name, search `resources/discussion_points.md` (David's own notes; use `/usr/bin/grep`, since plain `grep` skips files).

## What the design must settle

- **The signal sources:** what `signals` is, how Ctrl-C (SIGINT), SIGTERM, SIGHUP, SIGWINCH, SIGUSR1/2, and Windows console events (Ctrl-C, Ctrl-Break, close) appear, and what each `next` returns. Value-returning zero-argument calls drop `()` (`tick.next`); void ones keep it.
- **What Ctrl-C does with and without a listener.** Default with nobody listening (cancel the root, exit 130). What makes a press go to the program's handler instead, and for how long: a task waiting in `next`? the source being held? Presses that arrive while the handler is busy (queued, coalesced, or default?). Three rapid presses. Two listeners. Make the rule something a reader can predict from the code.
- **Stopping the handler when the work is done**, with existing constructs (`race`, `select` with a done channel, the parallel block's own rules, a `while` condition like `loop r.alive`), and which one is idiomatic.
- **The REPL:** what an in-progress `readl`/`input` does when Ctrl-C arrives (Python clears the line and reprompts); EOF; `quit`. Write David's REPL so it actually works, and say what (if anything) in his sketch needs to change and why.
- **Cancelling work on Ctrl-C** and saving under a deadline (the old `protect_from_cancel` case): e.g. a long search that saves its best result when interrupted, and exits 130.
- **Task groups and protection:** do `task.tasks` and `task.protect_from_cancel` still need any special form once Ctrl-C is an event source? Prefer existing constructs (`parallel`, `spawn`, `@` handles such as `protect_from_cancel(5s @save(best))`). Say what remains.
- **Child processes** (a shell running a child that should get the Ctrl-C), servers with graceful shutdown on SIGTERM, a game loop, terminal resize.

Dewy conventions: arguments are space-separated, `=?` is equality, `@f` is a function handle, `$name` is a metatag (prefixing what it attaches to), `or_throw` forwards an error, `??` substitutes a default. Strings are formatted only with `fmt`: `printl'result is {fmt'.2f'x}'`, never `{x:.2f}`. Imports use `.dewy` files. Unsafety is opt-in.

## Deliverables (all under `~/dev/tmp/par8/signals/`)

1. `round1.md`: the design. Lead with David's REPL and parallel examples written the way the design says, then the rules, then each case above, then "what is new" (ideally only library members) with the existing-construct comparison for each addition, then what you considered and rejected.
2. `programs/NN_name.dewy`: at least 12 realistic programs (REPL; long search that saves on Ctrl-C; server with SIGTERM graceful shutdown; game loop with Ctrl-C to pause/quit; shell running children; terminal resize; two listeners; handler busy when a second press arrives; a task group whose work ends early; a CLI that just wants the default; a Windows close event; a library that installs a handler without hijacking the program's).
3. `dogfood.md`: grade each program 1–5 on obvious, discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and Swift, naming the line for every score under 5. Be honest: earlier authors graded everything 5 and independent graders found 2s. Iterate (round2.md, round3.md as new files; never rewrite an earlier round) while anything under 5 is fixable, up to three rounds.
4. `names.txt`: every new name, one per line, as a short usage example, for a cold read.
5. `summary.md`: the final rules on one page, what changes from v5/v6 and earlier decisions, floors and why, new names.

Final message: the last round's path, floor and why, and new names. Budget: about three hours.
