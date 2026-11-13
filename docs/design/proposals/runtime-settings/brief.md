# Design round: choosing settings by a value known only at run time

You are designing one piece of the Dewy programming language. Write the design, dogfood it, and iterate until it is good. You may read anything in `~/dev/dewy-lang` (read-only: change nothing in that checkout). Write only under `~/dev/tmp/par7/settings/`.

## The problem

Dewy has no environment variables or command-line flags for settings: settings are metatags in source (`$program.max_cores = 8`, `$program.max_memory = 512MiB`, `$runtime_checks`, `$time.zone = '...'`, `$parallel.max_concurrent = 4`, and so on). David decided (decisions.md, batch 5) that per-environment settings are written idiomatically either as a separate entry file per environment, or as **one entry file with a function per environment that sets the tags, where `main` calls the right one**:

```dewy
laptop = () => {
    $program.max_cores = 2
    run(...)
}

server = () => {
    $program.max_cores = 8
    run(...)
}

main = (argv:array<string>) => {
    if (argv.get(0) ?? "laptop") =? "laptop" laptop() else server()
}
```

The last proposal (D4 Q7 in `docs/design/open_decisions.md`) said the second idiom can't work, because `$program.*` settings are fixed at compile time and `main` chooses at run time; it recommended separate entry files for process settings. David's answer:

> why can't we support selecting between tags based on runtime values? For ergonomics, I generally want to be removing friction, so if there's something that seems like it could work, even if the compiler needs to work a bit harder, I think it's usually worth it (and if it also hurts performance, it ought to also come with a warning)

Design how settings chosen by a run-time value work, so his idiom compiles and does what it says.

## What to read first

- `docs/design/open_decisions.md`: D4 (especially "Source-defined environments", Q6 and Q7) and D31 Q2 (`$program.time_zone*` under the entry-point rule).
- `docs/design/decisions.md`: batches 3 to 6, especially the entry-point rule ("Program-wide settings ... may be set at the top of the entry file, or inside a `main` function in any file") and "Calling another file's `main`" (a conflicting inner `$program.*` tag is a compile error). These bind you unless you show that one must change, and why.
- `docs/LANGUAGE.md`: "Directives" (how settings are scoped today), "Parallel CPU work" (`$program.max_cores`), "Time and dates" (`$time.*`), "Run, check and build", "Modules and games".
- Search `docs/design/` for `$program.` and `$parallel.` to collect every setting that exists or is proposed.
- Before proposing any spelling, search `resources/discussion_points.md` (David's own notes; use `/usr/bin/grep`, plain `grep` skips files).

## What the design must settle

- **Classify every setting** by what changing it at run time would take: a run-time policy (a cap on worker threads, a memory limit, a time zone read when needed) can simply be applied for the dynamic extent of the call; a setting that changes generated code (`$runtime_checks`, `$parallel.off`, proof strictness) would need the code compiled in more than one variant and the variant chosen at the call; a few may be genuinely fixed for the whole build (the target). For each class say what happens, what it costs (binary size, compile time, run-time dispatch), and when the compiler warns. David's rule: make it work even if the compiler works harder; if it costs performance, warn.
- **What a settings tag on a function means**: does it apply for the call's dynamic extent (everything the function calls, including tasks it starts), or lexically? What happens with two calls in sequence (`laptop()` then `server()`), nested calls, tasks still running when the function returns, and a setting like `max_memory` that is already exceeded when a narrower cap starts.
- **Reconcile** with the entry-point rule and the "conflicting `main`" compile error, and with D4 Q6's proposal that settings prefix their target. Say exactly which earlier decisions change, if any.
- Whether any new surface is needed at all. Ideally the idiom above just works with no new syntax. If something new is needed (for example a way to say "these settings, chosen by this value"), keep it minimal.
- Dewy conventions: arguments are space-separated, `=?` is equality, zero-argument calls that return a value drop `()` but void zero-argument calls keep `()`, `@f` is a function handle, `$name` is a metatag, `or_throw` forwards an error, `??` substitutes a default. Strings are formatted only with `fmt`: `printl'result is {fmt'.2f'x}'`, never `{x:.2f}`. Imports in examples use `.dewy` files, never `.jo`. Metatags may be any meta functionality, and comptime/library-backed ones are preferred over compiler magic. No environment variables.

## Deliverables (all under `~/dev/tmp/par7/settings/`)

1. `round1.md`: the design. Lead with what it does in one paragraph, then the classification table, then the rules, then the costs and warnings, then what changes from earlier decisions, then what you considered and rejected.
2. `programs/NN_name.dewy`: at least 10 realistic programs (laptop/server caps chosen from argv; a test harness running the same code under `$runtime_checks` and without; a game picking a low-power profile from a config file; a server whose request handler runs under a tighter memory cap; a time-zone setting chosen per user; a benchmark comparing `max_cores` 1, 2, 4 in one run; tasks that outlive the call; a library that sets its own defaults; and so on).
3. `dogfood.md`: grade each program 1–5 on obvious, discoverable, concise, safe by default, and complete, against Python, Go, Rust, TypeScript and Swift, with the lines that cost points. Be honest: an inflated grade wastes a round. Anything under 5 means iterate: revise the design (write `round2.md`, `round3.md` as new files; never rewrite an earlier round) and regrade, up to three rounds.
4. `names.txt`: every new spelling the final round introduces (if any), one per line, as a short usage example.

Your final message: the last round's file path, the floor grade and why, and any new spellings. Budget: about two hours.
