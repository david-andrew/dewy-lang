# Design round: cleanup without a remembered second step (should `defer` go?)

You are designing one piece of the Dewy programming language. Write the design, dogfood it, and iterate until it is good. You may read anything in `~/dev/dewy-lang` (read-only: change nothing in that checkout). Write only under `~/dev/tmp/par9/cleanup/`.

## The question

David, who owns the language:

> do we need `defer`? I get it's a common thing newer low level languages are adding, but to me it just feels like another case of expecting the programmer to remember some second step of ceremony every time or things break.

> can you look into if defer should go, or if we should keep it for extremely narrow cases, or some other construct would work better.

Earlier he floated `defer <expr> {...}`, a value that cleans itself up (RAII-like, though he notes Jonathan Blow dislikes RAII), and Python's `with` (familiar to him). Decisions batch 7 records: "`defer` stays for now. A later design pass looks for cleanup that doesn't rely on remembering a second step." This is that pass.

The case for `defer` we gave him, which your design must answer case by case:

1. Cleanup on every exit path (`return`, `or_throw`, `break`, a failure value, cancellation) written once, next to the acquire.
2. One-off actions that aren't resources: closing a channel to signal "no more items", resetting a flag (`held = false`), restoring terminal mode, printing "done". A type with a `$__drop__` hook for each is heavier than one line.
3. Timing at scope end. Dewy owners drop at their proven last use, not at block end (`docs/LANGUAGE.md` near line 3999), so a guard never touched again would release at once. Defers are shielded from cancellation with a 100 ms grace (near line 3653).
4. Raw C/OS handles with no wrapper type yet.

And his objection: `defer` is still a step you can forget, and nothing tells you that you forgot. All three uses in the current D4 examples look like they could be self-cleaning: `defer tick.stop()` (a ticker that stops when dropped), `defer net.tcp_close(stream)` (a stream that closes when dropped), `defer completed.close()` (a channel that closes when its last sender is dropped, as Rust's do and Go's don't).

## The rule for this round

**Start from what Dewy already has, and add nothing until you have shown the existing constructs fail.** David rejected an earlier proposal for inventing syntax "without really trying to think about something that works largely within the existing design". Existing pieces: drop hooks (`$__drop__`), ownership with moves by liveness, `@` places and methods that lend a place (whose locals are kept until the place's last use), types with members, `&` intersection, `parallel`/`spawn`/task groups, channels, `or_throw`, `??`, errors as values, metatags (prefixing what they attach to, batch 8), comptime/library-backed mechanisms over compiler magic. If something new is truly needed, write the program with existing constructs first, show where it fails, and keep the addition minimal. Removing `defer` entirely is a legitimate outcome; so is keeping it narrowly; so is something else. Decide on what is right for Dewy, not on what other languages do or what exists today (there are no users; no migration concerns).

## What the design must settle

- **Resources that clean themselves up:** which standard library values own cleanup (files, sockets, tickers, channels, locks, processes, temp files, terminal raw mode, GPU/audio handles), and what drop does for each. Channel close: on last sender drop? what does a reader see?
- **Fallible cleanup:** a file flush or close that fails on drop. Where does the error go? (Silently lost is not acceptable by default; Rust loses it, Python's `with` raises.) Can the program see it on the normal path without a second step? What happens when the block is already leaving with a failure?
- **Timing:** a guard or lock that must live until the end of a region even though it isn't read again. Does Dewy need a way to say "keep this alive until block end", or does drop-at-last-use plus something existing (a lending method, a scope, a block value) already give the right answer? Be concrete about what a reader sees.
- **One-off actions** (point 2 above): how a program writes "on every way out of this block, do X" without `defer`, or why `defer` remains the right tool for exactly these, and how narrow that is. If something is kept, can the compiler at least catch the forgotten case (e.g., a type that must be explicitly consumed, a warning)?
- **Cancellation and tasks:** cleanup in a task that's canceled; the 100 ms grace; a resource moved into a spawned task; a resource returned from a function (moved out, so not cleaned up there).
- **Resources in collections and records**, early `return` from loops, `break`, and errors forwarded with `or_throw`.
- **C/FFI handles** and how a library author wraps one (how much ceremony is that).
- **Cost:** what drop/cleanup costs at run time and in the compiler; anything that could be a hidden cost gets a warning (David: remove friction even if the compiler works harder, but warn on performance cost).
- **What changes** in the docs: LANGUAGE.md sections that mention `defer`, D4's examples in `docs/design/open_decisions.md` (lines ~80–185), and earlier decisions.

## What to read first

- `docs/LANGUAGE.md`: search `defer`, `__drop__`, "Records and collections" (drop hooks, move-only owners), the ownership/liveness section near line 3999, cancellation near line 3653, "Errors as values", "Files, paths and processes", "Channels", "Parallel CPU work".
- `docs/design/decisions.md` batches 3–8 (binding; batch 7 has the cleanup direction).
- `docs/design/open_decisions.md` D4 (current concurrency design and its `defer` uses).
- `docs/design/proposals/scope-blocks/summary.md` (a rejected design that touched cleanup; read for the problems, not the syntax).
- Before proposing any name, search `resources/discussion_points.md` (David's notes; use `/usr/bin/grep`, plain `grep` skips files).

Dewy conventions: arguments are space-separated, `=?` is equality, `@f` is a function handle, `$name` is a metatag, `or_throw` forwards an error, `??` substitutes a default. Value-returning zero-argument calls drop `()`; void ones keep it. Strings are formatted only with `fmt`: `printl'result is {fmt'.2f'x}'`. Imports use `.dewy` files. Unsafety is opt-in.

## Deliverables (all under `~/dev/tmp/par9/cleanup/`)

1. `round1.md`: the design. Lead with the verdict on `defer` (go / keep narrowly / replace) in one paragraph and a minimal before/after example, then the rules, then each case above, then "what is new" (ideally nothing, or only library members) with the existing-construct comparison for each addition, then what you considered and rejected (including `defer`, `defer <expr> {...}`, `with`, linear/must-consume types, errdefer, Swift/Go/Zig/Rust/Python/C# approaches).
2. `programs/NN_name.dewy`: at least 12 realistic programs: file copy with a flush error; TCP client with early return; a producer/consumer whose channel must close; a mutex guard held across a region; terminal raw mode restored on Ctrl-C; temp directory removed on every exit; a task holding a socket that gets canceled; a game loading GPU/audio handles; a C library handle wrapped by a library author; a transaction that commits on success and rolls back otherwise; a lock-free "print done on every way out" one-off; resources stored in an array and dropped together.
3. `dogfood.md`: grade each program 1–5 on obvious, discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and Swift, naming the line for every score under 5. Be honest: earlier authors graded everything 5 and independent graders found 2s; all-5s without cited lines will be sent back. Iterate (`round2.md`, `round3.md` as new files; never rewrite an earlier round) while anything under 5 is fixable, up to three rounds.
4. `names.txt`: every new name or spelling, one per line, as a short usage example, for a cold read (empty if none).
5. `summary.md`: the final rules on one page, what changes from earlier decisions and the docs, floors and why, new names.

Final message: the last round's path, the verdict on `defer`, floor and why, and new names. Budget: about three hours.
