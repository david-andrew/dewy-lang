# Cross-design conventions (integration pass, final, 2026-11-07)

These rules apply to `parallel-v4`, `safety-round3`, `time-units-format` and `ui-strings` together, and they win where one of those files says otherwise. `amendments.md` lists every section each convention changes, and `changes-2.md` lists what round 2 changed. Every name here went through the final cold read (round 7, `new-names.md`). A † marks the few that read weakly or weren't tested, and a ? marks a question for the owner.

## Things that run

1. **One set of handle verbs.** Anything that starts and keeps running (`Task`, `PlayingSound`, `Process` and a task group) has:
   - `.stop`: ask it to end; returns at once; safe to repeat;
   - `.wait`: wait for the end;
   - `.running`: true until it has ended, so a paused thing is still running.

   What `.wait` gives:
   - a `Task<E>` gives `void | E | Canceled`, and `.error` gives the `E` or `none`;
   - a `Process` gives its `ExitStatus`.

   `.pause`, `.resume` and `.paused` exist only on `PlayingSound`.
   - **A source of events has `.next`, not `.wait`.** This applies to `Ticker` and the Ctrl-C listener (`catch_ctrl_c`). `.next` waits for the next event and is a receipt, while `.wait` would mean "until it ends", which a source never does.
   - **How each thing ends after `.stop`:** a sound and a ticker at once, a task at its next cancellation point, and a process when it handles the signal (`.kill` ends it at once).

   `music.stop; music.wait or_throw` · `tick.next or_throw` · `tick.next(timeout=at)`
2. **Dropping a handle never stops what it started.**
   - A task belongs to its group.
   - A sound nobody holds belongs to the program's group: the program waits for it at exit, a looping one stops at exit, and Ctrl-C stops it.
   - A `Ticker` nobody holds has no receiver, so whether it still ticks can't be observed.
3. **`Canceled` passes through anything that doesn't name it.** `??`, `?? void`, `?? return/break/continue`, `??<E>` (unless `E` names `Canceled`) and collectors forward it, as `or_throw` would.
   - **To take Ctrl-C yourself, hold `let ctrl_c = catch_ctrl_c`.** While you hold it, Ctrl-C cancels nothing:
     - each press is an event (`ctrl_c.next`, or `@ctrl_c.next` in `select`);
     - a console read in progress gives `Interrupted`;
     - a child process still gets the terminal's signal itself.
     - `ctrl_c.discard_pending`† forgets presses not yet handled.
   - Three presses within one second end the process anyway, so a stuck program can always be stopped. Dropping the handle restores the default.

   `let line = input("$ ") ??<Interrupted> continue ?? break`
4. **Long-lived background work lives in the program's group.** `main = (app:BackgroundTasks) => …`? gets a group that lasts as long as the program. In a UI or game program, that is until the window closes. The group is then stopped and joined.
   - **Failure policy:** a failed task here doesn't fail the group. Its error is printed once on stderr, naming the task, and kept on its handle (`job.error`, `job.wait`).
   - In a scoped `tasks(…)` group, a failure still fails the group, as decided (C3).
   - **Frame code** (`update`, `draw`) may do file and terminal I/O (hover notes it), but waiting on a channel, a task, `sleep` or `select` there is a compile error. It reads channels with `ch.drain` and spawns into the program's group.

## Values and text

5. **Receipts: a useful result you may drop.** A result is a receipt when:
   - the function is tagged `$discardable_result`?;
   - it is a handle to something that keeps running (rule 1);
   - it is an event from `.next`;
   - it is an inferred result that ends in a receipt on every path.

   A receipt is kept wherever a value is taken (a binding, an argument, a collector, an inferred body's last line) and dropped silently elsewhere. Its failure still needs handling.
   - **Categories, not a list:** handles; file-system writes and removals returning their path (the library gate checks this); `Atomic.add`; `rebind`.
6. **Results carry something useful.** A call that starts something gives its handle, and a write or removal gives the path. A failed wait or send keeps its payload.
7. **Reading text: `T(text)` gives `T | ValidationError`.** Every reader is named for what it builds: `date`, `instant`, `Duration`, `Mass`, `int`, `float64`, `rational`, `FileName`, `Action`, `NumberPattern`, `from_json<T>`.
   - A refinement or shape alias reads automatically, through its base reader and then its check. For example, `Port(text)` says "must be 1 to 65535".
   - A record or other user type declares its reader as `__read__ = (text:string):>Roll | ValidationError => …`?, and then `Roll(text)`, `input_field` and union readers find it.
   - `Roll(count=n sides=s)` is the checked constructor: it gives `Roll | ValidationError` where `Roll[…]` needs proof.
8. **Two kinds of text, and each reads back.**
   - **Programmer text** is display, Dewy text, read strictly by `T(text)`: `90minute`, `250g`, `36.(1)°C`, `2026-11-07`. A `fmt` pattern reads back through the same pattern.
   - **People's text** is written by `label(x)` and read by `T.parse_human(text)`, which also accepts common forms such as `1h 30m`, `30 days`, `1 ½ cups` and `21.4C` (where the dimension decides `C`). For a duration, a person's "30 days" means 720 hours, and this is said in the docs. `"1 month"` is refused, because a month has no fixed length.
   - `input_field` shows `label(x)` and reads with `parse_human`, while JSON and code stay strict.

## Time

9. **Three clock types, never mixed.**
   - `now` is a `ClockReading`.
   - `now + 1s` is a `MonoPoint`, a deadline.
   - `.nominal` is the wall-clock `Instant`.

   Where they are used:
   - `timeout=` and `sleep(until=…)` take a `MonoPoint` or an `Instant`.
   - `ticker(1s).next` gives `ClockReading`s.
   - Waits accept any time quantity and round up to the tick.
   - `p.modified` is an `Instant`.
10. **A pattern prints an `Instant` in the program's zone** (D15a's rule for an unstated zone). The default `"{t}"` stays ISO UTC with `Z`, and `fmt'iso_basic'`? writes `20261110T140000Z`, which `instant(text)` reads.

## Checking and settings

11. **One literal-validation mechanism: shapes.**
    - `Sku:type = string<check=@sku_problem>`? (the keyword is the owner's: `check=` or `valid_if=`).
    - The validator returns `none` or what is wrong. `@forbid("…")` refuses an overload.
    - A validator overload on a `CountHoleTemplate`† lets `fmt'<{w}'` be checked while compiling.
12. **One prefix for the same call with its failures as values: `strict_`?** These are `strict_today`, `strict_add`, `strict_in_zone`, `strict_elapsed`, `strict_zone` and `$time.only_strict_today`.
    - No prefix reads well on every function in the cold reads: two of three readers took `strict_in_zone` for "strictly inside a zone".
    - The prefix is therefore the owner's to confirm (D31 Q6): `strict_` (rec), `try_`, or a name chosen per function.

13. **A metatag never changes a type.**
    - A strict tag makes the lax call an error naming the strict one.
    - `$finite_floats` asks for proofs; a signature that promises finiteness writes `Finite`.
    - `$explicit_allocation_failure` is the one flagged exception.
    - `$program.*` settings go in the main file only. `$parallel.*` settings are lexical; as the first line of a `parallel` body, a tag governs that construct. A tag that governs nothing is an error.

## Shared vocabulary

14. **Intervals are ranges** (D15d): `slider(… [0.0..1.0])`, `plot(range=…)`, `random([0ms..250ms))`.
    - Bounds are `.start` and `.end`.
    - A range of a discrete type loops; `r.step(s)` sets the step for any discrete range, ints included. `[a,b..c)` stays the arithmetic form for numbers, and `.step` is the only form for calendar steps (`.step(1month)`).
    - A type is discrete when it has `next_up`, and dense when it is declared `$no_next_value`†. Discreteness is never inferred from a missing member.
15. **Each keyword has one meaning.**
    - **Rounding:** exact values round half away from zero and floats half to even, as you decided, and this includes `fmt`. One keyword, `rounding=`, replaces your `ties=`? and also takes the directed modes.
    - `grouping=` is a reduction's association, and `ties=` (if `rounding=` is taken) is only `select`'s fairness.
    - `style=` is how a widget looks, and `descending=` reverses an order.
16. **Units go all the way through.**
    - File sizes are `DataSize` quantities.
    - `update` takes `dt:Duration`.
    - `MB` is 10⁶ bytes and `MiB` is 2²⁰.
    - JSON writes a quantity as its printed text.
    - **Temperature points:** `t.value_in(°C)` gives the bare reading, since `/ unit` would scale a point. `t.is_close(u abs=0.5K)` requires a difference tolerance and has no `rel=`.
    - **At run time:** `Quantity(text)`, `Unit(text)` and `q.to(u)` serve tools like converters.
17. **`fmt` kinds can't overlap.**
    - An integer style (`d x X b o`) makes an `IntegerPattern`, and any other number option a `NumberPattern`.
    - Fill, alignment and width alone make a `TextPattern`, and field words make a date or time pattern.
    - `""`? joins two fields with nothing between them and pads as `-` does: `fmt'year""month""day'` writes `20261110`.
    - Build a pattern once and pass it as a value (`value_text=fmt'.0%'`).
    - A duration's first field is unpadded: `fmt'minute:second'(65s)` is `1:05`.
18. **Secrets and paths.**
    - `input(prompt hidden=true)` and `input_field(… hidden=true)` give `secret<string>`.
    - `to_json(x secrets='reveal')` gives a `secret<string>`, and `write_text` of a secret creates the file `0o600`.
    - `secure_token` and `secure_random_bytes` are secrets, while `secure_random(range)` gives a plain, unpredictable value.
    - `list` gives `FileName`s, and `.name` and `.stem` of a `SafePath` are `FileName`s.
    - `relative_to` gives a `SubPath`, which joins to any base safely.
    - `sanitize_file_name` is derived from the target's own check.
