# Dogfood of the v5 parallel surface

Programs: `~/dev/tmp/par5/dogfood/`. Eleven scenarios. Scores are obvious, discoverable, concise, safe by default, complete, consistent (1–5). A 5 means nothing in that column needs a change. Lines and fixes below are for Dewy scores under 5. The other columns are the same six scores for the usual idiom: Python asyncio, Go, Rust (scoped threads or Tokio), TypeScript, Swift structured tasks.

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 shell | 4 3 4 5 4 3 | 4 4 4 4 4 4 | 3 3 3 4 3 3 | 3 3 3 5 3 3 | 4 4 4 4 3 4 | 4 3 3 5 4 4 |
| 02 chat | 4 4 4 5 5 5 | 4 4 3 4 5 4 | 5 5 5 4 5 5 | 4 4 4 5 5 4 | 4 4 3 4 5 4 | 4 4 3 5 5 4 |
| 03 download | 4 4 5 5 4 5 | 4 4 4 4 5 4 | 4 4 4 4 5 4 | 4 4 4 5 4 4 | 4 4 4 4 5 4 | 4 4 4 5 5 5 |
| 04 search | 5 4 5 5 5 5 | 4 4 3 4 5 4 | 5 5 4 4 5 5 | 4 4 4 5 5 5 | 4 4 3 4 5 4 | 5 5 5 5 5 5 |
| 05 checkpoint | 5 4 4 5 5 5 | 4 4 3 4 5 4 | 4 4 4 4 5 4 | 4 4 3 5 5 4 | 4 4 3 4 5 4 | 4 4 4 5 5 4 |
| 06 radar | 5 4 5 5 5 5 | 3 3 3 3 4 3 | 3 3 3 4 4 3 | 3 3 3 4 4 3 | 4 4 4 4 5 4 | 4 4 4 5 5 4 |
| 07 checksum | 5 5 5 5 5 5 | 5 5 4 4 5 5 | 5 5 4 4 5 5 | 4 4 4 5 5 4 | 5 5 4 4 5 5 | 5 5 4 5 5 5 |
| 08 laptop/server | 4 3 5 5 5 4 | 5 5 5 4 5 5 | 4 4 4 4 5 5 | 4 4 4 5 5 5 | 5 5 5 4 5 5 | 4 4 4 5 5 5 |
| 08 dispatch | 3 3 4 5 4 2 | 5 5 5 4 5 5 | 5 5 5 4 5 5 | 5 4 4 5 5 5 | 5 5 5 4 5 5 | 5 4 4 5 5 5 |
| 09 pool | 5 4 5 5 5 5 | 4 4 4 4 5 4 | 5 5 5 4 5 5 | 4 4 4 5 5 4 | 4 4 4 4 5 4 | 5 5 4 5 5 5 |
| 10 race | 4 4 3 5 4 4 | 4 4 4 4 5 4 | 4 4 4 4 5 4 | 4 4 4 5 5 4 | 4 4 4 4 5 4 | 5 4 4 5 5 5 |

## What already meets the bar

- `check_cancel() or_throw` is a checkpoint with no lifetime. `04_search.dewy:5`. Nothing to turn on, nothing to drop.
- `catch_ctrl_c((ctrl_c) => …)` and `protect_from_cancel(2s () => write_checkpoint(count))` are ordinary calls. The `=>` makes a callback `return` local. That rule should stay. The extra parentheses in `5s (() => …)` are not needed; `05_checkpoint.dewy:15` is the spelling to teach.
- `select([said=@lines.receive] [typed=@ops.receive] timeout=60s)` tells two `Channel<string>` values apart, and the `match` arms repeat the field names. Keyword arguments would have been a second namespace. Keep the records.
- `main = (jobs:BackgroundTasks args:array<string>)` in `07_checksum.dewy:22`. Names and order are swapped on purpose. The types are the whole rule. This file does not import the task module: the group arrives as a parameter. `06_radar.dewy` is the same. That is the answer to “where do background tasks come from?” for a frame loop and a CLI.
- Idle `timeout=60s` inside `02_chat_server.dewy`’s loop is the right relative timeout. The race uses one saved deadline (`10_race.dewy:27`). Both are already specified.

## Scores under 5

- **01 shell, obvious 4, concise 4, complete 4, consistent 3, discoverable 3.** `01_shell.dewy:45` returns from the `tasks` callback after storing the exit code, and `:79` returns that code from the `catch_ctrl_c` callback. `catch_ctrl_c` and `protect_from_cancel` keep the callback’s value; `tasks` drops it, so `:22` has `$capture @code`. Fix: `tasks` returns the callback’s value after it joins. A void callback stays void. Discoverable 3 is that gap: nothing at the call says the inner `return` is discarded. Complete 4 is `:1`: process groups are a library, and the catcher docs should say so. The import on `:2` (`…/tasks.jo as tasklib`) exists to avoid `tasks.tasks`. Fix: the module is `task`, and the calls are `task.tasks`, `task.catch_ctrl_c`, `task.protect_from_cancel`.
- **02 chat, obvious 4, discoverable 4, concise 4.** `:39` parsed on the second reading: each bracket is a one-field record, and `@` is the handle (`lines.receive` would call it). Fix: a named argument other than `timeout` or `ties` errors with “write `[said=@lines.receive]`”. `:45` and `:46` are two `Closed` arms, easy to skip. Fix: hover offers those arms, plus `Timeout` when a timeout is set. Do not let `or_throw` see through the record. `:31` swallows `Canceled` on accept so `/quit` does not fail the group while it joins. Fix: say that a child ending `Canceled` because its group is stopping is not a failure. `.wait()` still reports `Canceled`.
- **03 download, obvious 4, discoverable 4, complete 4.** `:36` puts `$parallel.max_concurrent=4` inside the brackets, before `parallel`. It looks like a collected value, and the same tag on the line above the `let` would now be an error. Fix: keep the prefix rule, and make that error say “move this inside the brackets, before `parallel`”. Complete 4 is raw HTTP. The fix is a client library, not this surface.
- **04 search, discoverable 4.** `:14` stops the hunter and `:20` prints `best`. That is right only if an owner `.stop()` does not fail the group. Fix: say so next to `.stop()`. Self-stop is already normal completion; an owner stop is the same, and `.wait()` returns `Canceled`.
- **05 checkpoint, discoverable 4, concise 4.** `:21` `return Canceled` sits outside the lambda. That is correct, and deleting it exits 0 after a good save. Fix: teach the two endings side by side. `return Canceled` keeps exit 130. Falling out of the `??<Canceled>` block keeps the partial result and exits 0. A `return Canceled` inside the lambda is the callback’s result; `:15` `or_throw<Canceled>` forwards it. `:19` matches `error`, so a catch-all `exception` arm cannot swallow that `Canceled`.
- **06 radar, discoverable 4.** `:11` returns from `main`; `:16` `update` and `:13`’s task keep going. Fix: the `BackgroundTasks` docs say the group outlives `main` until the window closes. `:6` ends `wire` with `Canceled` on that close. Same sentence as search: do not print it as a task error.
- **08 laptop/server, obvious 4, discoverable 3, consistent 4.** `08_laptop.dewy:1` imports `MiB`, and `:3`–`:6` prefix `main`. v5 places a module header before imports, where `MiB` is not in scope. Fix: a header may follow imports and must precede declarations. A `$program` tag directly before the entry `main` is the separate-file form.
- **08 dispatch, obvious 3, discoverable 3, concise 4, complete 4, consistent 2.** `:6`–`:9` and `:11`–`:14` use the same prefix position as `$parallel.off`, and as the laptop file’s tag on `main`. On `laptop` and `server` the tag seals the process for the rest of the run, forbids a second call, and is an error if reached late. Fix: do not give `$program.*` a second meaning on ordinary functions. Separate entry files are the form to teach. One file can pass a record into `cache.run`; process caps stay on that file’s `main`.
- **09 pool, discoverable 4.** `:32` `$explicit_cancellation` applies to `run` only. A tag in the middle of today’s file covers the whole scope. Fix: hover says “applies to `run` only; put it at the top to cover the module.”
- **10 race, obvious 4, discoverable 4, concise 3, complete 4, consistent 4.** The program I wanted was `within(800ms @race(@fetch(8080 key) @fetch(8081 key)))`. A fast `NetError` would beat a slow good answer, so `:16`–`:52` is a channel `select` with one deadline. Fix: `race` returns the first success and cancels the rest; if every attempt fails, return those failures. `within` should take a zero-argument callback, and `@fetch(port key)` stays legal as that callback. `:27` is one deadline because a fresh `timeout=800ms` on each miss would start over. The chat’s relative `timeout=60s` is the other loop, and it is right there. Fix: show the two loops side by side.

## Focus

- The callbacks are pleasant. Callback `return` should not leave the enclosing function. The pain is `tasks` discarding a value the other two scopes keep.
- `select`’s records are the right way to tell same-typed waits apart. The call is noisy until the diagnostic and the hover exist.
- Prefix tags match labels. The comprehension site and a `$program` tag on a function other than `main` are the two surprises.
- `tasklib` should not appear in the guide. `check_cancel` is already an unqualified checkpoint; the three scope calls should live on a module named `task`.

## Verdict

Not ready. Must-fix:

1. `tasks` returns the callback’s value after joining, same as `catch_ctrl_c`.
2. `$program.*` on an ordinary function is not a prefix tag. Keep per-environment entry files. One file passes a value; it does not seal the process from a function that looks callable.
3. A module header may follow imports, so `$program.max_memory=512MiB` can name `MiB`. The tag directly before the entry `main` is that form.

Top 3 changes, in that order: those three. Leave `select`’s records, callback `return`, `check_cancel`, and `main`’s two parameters as they are.
