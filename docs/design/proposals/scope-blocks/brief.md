# Design round: Ctrl-C and the other scopes as ordinary blocks

You are designing one piece of the Dewy programming language. Write the design, dogfood it, and iterate until it is good. You may read anything in `~/dev/dewy-lang` (read-only: change nothing in that checkout). Write only under `~/dev/tmp/par7/blocks/`.

## The problem

The current concurrency design (v6) has three library calls that take a callback and run it as a scope:

- `task.catch_ctrl_c((ctrl_c) => { ... })`: while the callback runs, Ctrl-C presses arrive as events on `ctrl_c` (and as `Interrupted` from console input), not as cancellation.
- `task.tasks((group:Tasks) => { ... })`: a task group that joins before returning.
- `task.protect_from_cancel(5s () => save(value))`: runs work despite a pending cancel.

David (who owns the language) rejected the callback shape for Ctrl-C:

> I see generally you've made them into functions that take a callback, but I'm not sure if that is the right thing. I like the idea of it being more direct e.g. like a block so you can call return or throw and it doesn't need to be passed along to some outer calling thing, it just works like usual.

So: inside the scope, `return` must return from the enclosing function, `break`/`continue` must act on the enclosing loop, and errors must forward (`or_throw`) to the enclosing function, exactly as in a plain `{ ... }` block. Design how these scopes are written.

## What to read first

- `docs/design/open_decisions.md`, section D4 (the current design and its examples, including "A prompt with its own Ctrl-C behavior" and "Save on Ctrl-C").
- `docs/design/proposals/concurrency/unified/proposal-v5.md` (the Ctrl-C and protection semantics; search `catch_ctrl_c`) and `v5-dogfood.md`.
- `docs/design/decisions.md`, batches 3 to 6 (David's decisions; they bind you).
- `docs/LANGUAGE.md`: "Functions and values", "Parallel CPU work", "Errors as values", "Loops, text and optional values", "Directives". Also search it for `$__drop__` (Dewy already has drop hooks) and `defer`.
- Before proposing any spelling, search `resources/discussion_points.md` (David's own notes; use `/usr/bin/grep`, plain `grep` skips files).

## Constraints

- Keep the semantics of the three scopes as they are (what Ctrl-C does while caught, three rapid presses force exit, protection is cooperative, groups join before returning, and so on). Only how they are written, and how control flow leaves them, is being designed. If a semantic change is genuinely needed, say why.
- Prefer one general mechanism that libraries can use over three compiler special cases. David's principles: orthogonal features, no context sensitivity without good reason, as little compiler magic as possible (comptime/library-backed mechanisms that userspace could replicate are preferred), the right design rather than what exists today. A small number of genuinely new surface forms is fine if they earn it.
- Candidates to weigh (not a closed list): a library function that takes a block argument whose control flow is the caller's (Kotlin inline lambdas, Ruby/Swift trailing blocks); a scoped-value form (Python `with`); a statement form; making the listener an ordinary value whose lifetime is the scope. Explain how the block names the Ctrl-C listener or task group.
- David also raised cleanup: `defer` works for now, but he doesn't want correctness to rely on remembering a second step, and wondered about `defer <expr> {...}`, or a value that knows how to clean itself up (RAII-like, though Jonathan Blow dislikes RAII; Python's `with` is familiar to him). Cleanup is **not** being decided in this round, but your mechanism must not preclude a good answer, and a short section should say how it would extend to scoped resources (a file, a lock, a ticker) if it naturally does.
- Dewy conventions: arguments are space-separated, `=?` is equality, zero-argument calls that return a value drop `()` but void zero-argument calls keep `()`, `@f` is a function handle, `$name` is a metatag, `or_throw` forwards an error, `??` substitutes a default. Strings are formatted only with `fmt`: `printl'result is {fmt'.2f'x}'`, never `{x:.2f}`. `&` on types is intersection. Imports in examples use `.dewy` files (`import p"@lib/std/tasks.dewy" as task`), never `.jo`.
- Unsafety is opt-in: the default must be safe.

## Deliverables (all under `~/dev/tmp/par7/blocks/`)

1. `round1.md`: the design. Lead with what it does in one paragraph, then the rules, then the three scopes rewritten, then the cleanup extension sketch, then what you considered and rejected and why. Show the "prompt with its own Ctrl-C behavior" and "save on Ctrl-C" examples from D4 rewritten.
2. `programs/NN_name.dewy`: at least 10 realistic programs using the design (a REPL that clears the line on Ctrl-C and returns from the enclosing function on `quit`; a shell running children; a long search that saves on Ctrl-C; a task group whose body returns early; nested catchers; a game loop; a server with a protected flush; a CLI that throws out of a scope; a loop that `break`s out of a scope; a generic library helper that defines its own scope with the same mechanism; and so on).
3. `dogfood.md`: grade each program 1–5 on obvious, discoverable, concise, safe by default, and complete, against Python, Go, Rust, TypeScript and Swift, with the lines that cost points. Be honest: an inflated grade wastes a round. Anything under 5 means iterate: revise the design (write `round2.md`, `round3.md` as new files; never rewrite an earlier round) and regrade, up to three rounds.
4. `names.txt`: every new spelling the final round introduces, one per line, as a short usage example (for a cold-read test by context-free readers).

Your final message: the last round's file path, the floor grade and why, and the list of new spellings. Budget: about two hours.
