# Amendments to the four revisions (integration pass, final, 2026-11-07)

Each revision file plus this page is the full design. The open-item texts are in `open-items.md`. Where this page and a revision disagree, this page wins. The rules are numbered as in `conventions.md` (C1–C18), and † marks a name that still needs a cold read.

## Renames applied everywhere (name picks, rounds 4–5)

| Was | Now |
|---|---|
| `Information` | `DataSize` |
| `ShapeError`, `ParseError`, `TextError` | `ValidationError` (C7). The `ParseError` merge is new in this pass |
| `shape=@x_error` | `check=@x_problem` (keyword still the owner's: `check=` or `valid_if=`) |
| `capture` (rebinding) | `listen_for_press` |
| `field` | `input_field` |
| `Playing`, `.playing` | `PlayingSound`, `.running` (plus `.paused`) |
| `Selectable<R>` | `Waitable<R>` |
| `Sort` | `TableSort` |
| `$program.time_rules` | `$program.time_zone_rules` |
| `$time.no_unchecked_today` | `$time.only_strict_today` (round 6; the owner's `strict_` prefix kept) |
| `shielded(d @f)` | `protect_from_cancel(d @f)` |
| `to_file_name` | `sanitize_file_name` |
| `checked_add` (time library) | `strict_add`; the prefix is `strict_` everywhere (round 6: `checked_today` read as "checked today") |
| `Task.cancel`, `group.cancel` | `.stop` (C1) |
| `Child` | `Process`† |
| `x or_throw<E>` | `x or_throw_only<E>`† (all three readers read `or_throw<E>` as "throw an `E`") |
| `to_int(text)`, `to_float(text)` | `int(text)`, `float64(text)` (C7; owner question, as it renames a decided spelling) |
| `plot(kind=)` | `plot(style=)` (C15) |
| `slider(@v low high)`, `plot(low= high=)` | `slider(@v [low..high])`, `plot(range=[…])` (D15d) |

## parallel-v4

- **§4 `?? void`, filter set F:** F never includes `Canceled` (C3). "`?? void` follows `if` without `else`" stands.
- **§4, add: collectors and `Canceled`.** A collector's element type never includes `Canceled`. A `Canceled` contribution leaves the function as `or_throw` would, and in `[parallel …]` the other items are canceled and joined (C3, and narrows C3 of batch 3). `partition_failures` therefore splits only real failures.
- **§5, add: `??` and cancellation.** `??`, `?? return/break/continue` and `??<E>` without `Canceled` in `E` forward `Canceled`.
  - Where a function's result is written and lacks `| Canceled`, it is a compile error with two fix-its: add `| Canceled`, or default it on purpose with `??<Canceled …>`.
  - Exactly what changes in the decided rules:
    1. the 2026-10-23 line "`??` defaults any exception value as well as `none`" gains "except `Canceled`";
    2. "`??<E>` defaults only the listed types" is unchanged, and `Canceled` must be listed to be covered;
    3. D14's `?? return/break/continue` follow 1;
    4. C3's "errors stay per-item values" gains "except `Canceled`".
  - With level-triggered cancellation, this is what stops `loop { let m = ch.receive ?? "" }` from spinning after Ctrl-C.
- **§5 `shielded`** is now `protect_from_cancel(d @f)`.
- **§6 `Task`:** `.stop`, `.wait`, `.running` (C1).
  - A task that ends because of `.stop` doesn't fail its group.
  - `Tasks` gains `.stop`: it stops every task, and `tasks(…)` then returns normally.
  - New warning (dogfood F42): when a body ends while a task waits on a channel that nothing else will send to or close, it says "the group waits for `writer`, which waits on `out`; stop it or close `out`".
- **§6, add: the program's group (C4).**
  - `main` may declare one parameter of type `BackgroundTasks`†. It is the program's group: tasks spawned into it live until the program ends. For a frame program, that is when the window closes, after the last `update`/`draw`. The group is then stopped and joined.
  - Failure policy (round 2): a failed task there doesn't fail the group. Its error prints once on stderr, naming the task's function, and stays on its handle (`.error`, `.wait`).
  - Frame hooks reach it through a module binding assigned in `main` (the decided "module-level `let x:T` assigned by `main`").
  - This is ordinary structure: the group's lifetime is the program's. It isn't new syntax, but it is new surface on `main`, so it is an owner question (D4 Q).
- **§6, add: `ch.drain`** (F7). `loop m in inbox.drain` visits the values buffered now, without waiting, and ends on `Empty` or `Closed`. `Busy` retries inside. It isn't a cancellation point.
- **§7 `select`:**
  - `timeout:Duration | MonoPoint | Instant | none` (C9). A `MonoPoint` is a monotonic deadline (`now + 1s`), and an `Instant` is a wall-clock deadline.
  - `ticker(1s)` delivers `ClockReading`s, and `Ticker` gains `.stop` and `.running`.
  - The protocol is `Waitable<R>`.
  - The one-wait idiom is `match select(…) or_throw_only<Canceled> { … }`. If the spelling is refused, it is the one arm `<Canceled> => return Canceled`.
- **§7, add: waits take any time quantity** (F22). `sleep`, `within`, `timeout=` and `ticker` accept `rational*Time` and round up to the tick. `sleep(until=t)`† takes a `MonoPoint` or an `Instant`.
- **§9, add (F33):** a `$parallel.*` tag that governs no construct is an error. As the first line inside a `parallel` loop or comprehension body, it governs that construct.
- **§11:** D22, D26 and D27 are unchanged in substance. `music.cancel` in §6 becomes `music.stop`.
- **§17 notes:**
  - The `;` friction is settled by receipts (C5).
  - The process call is `start_process` → `Process`.
  - `Atomic.add` follows the counter rule (safety §4).

## safety-round3

- **§2 sweep, current names:**
  - `strict_add` (renamed from `checked_add`);
  - `$time.no_assumed_range`, `$time.no_assumed_policy` (replaces `$time.require_profile`), `$time.no_assumed_clock_domain` → `strict_elapsed`;
  - `$program.time_zone` (replaces `$time.zone`);
  - `$time.no_dropped_zone` (replaces `$time.require_loss`; display returns text only).
  - The "checked and conforming" row drops `$time.zone` and `$time.require_loss`.
- **§2 and §5, `$finite_floats`** (recheck 4): the tag never changes a declared type.
  - In its scope, every float produced must be proven finite where it is stored, passed, returned, compared, converted or printed, and a guard on a local discharges its arithmetic.
  - A reader may rely on a field, parameter or result being finite only if its type says so: `Finite`† (`<T=float64>T<(is_finite)>` in the prelude).
  - Welford keeps "compute, guard once, commit", with fields typed `Finite`.
  - The "a refinement is a subtype, so not a type fork" sentence goes.
- **§3:**
  - `FileName` is `string<check=@file_name_problem>`, and `FileName(text)` gives `FileName | ValidationError`.
  - `sanitize_file_name(text)` replaces every character and form the build target's `file_name_problem` rejects. On Windows that is `\ / : * ? " < > |`, control characters, a trailing dot or space, and the reserved names `CON PRN AUX NUL COM1–9 LPT1–9`, which take a `_` suffix. Empty, `.` and `..` become `_`. Its test asserts that `file_name_problem(sanitize_file_name(x))` is `none` for fuzzed `x` (recheck 9).
  - `.name` and `.stem` of a `SafePath` are `FileName`s (F26).
  - `f.relative_to(base)` on a `SafePath` under `base` gives a `SubPath`†, a sequence of `FileName`s that joins to any base with no confinement (F1).
  - `dir.glob["*.jpg" "*.png"]` takes several literal patterns through the approved `f[…]` call (F27). A computed pattern gives plain `Path`s.
- **§6:** `random(range)` takes any type with a sampler: integers, floats, quantities, `Duration` and `Date` (F32).
- **§7 → receipts (C5):** this replaces "dropped before the end of a body".
  - A receipt is kept wherever a value is taken: a binding, an argument, a collector, or the last line of an inferred-result body. It is dropped silently elsewhere, including on `main`'s last line and anywhere in a written `:>void` body.
  - Inference: a function whose inferred result is a receipt on every path is itself one (F48: `log = (m) => file.append_text(m) or_throw`).
  - Tagged by category: handle types (`Task`, `PlayingSound`, `Process`), file-system writes returning their path (gate-enforced), `Atomic.add`, `Controls.rebind`, and `Process.wait` (the `ExitStatus`).
  - Not receipts: `xs.pop`, `d.pop(k)`, `window(…)`, `ticker(…)`, `try_send` (its `Unsent` is a failure: `?? void` or `;`), and every reader.
  - **Fallback if declined:** keep the path and handle results and write `;`. The `void` fallback is withdrawn (stem rule; recheck 6).
- **§8:**
  - **Readers:** `int(text)` and `float64(text)` replace `to_int` and `to_float`, with `max_digits=` and `allow_nonfinite=` kept. All readers give `ValidationError` (C7).
  - **Process:** `start_process(program args)` gives a `Process`† with `.stop` (polite), `.kill`, `.wait` (`ExitStatus | Canceled`, a receipt), `.running` and `.id`.
  - **Added (F25):** `config_dir(app)`, `data_dir(app)`, `cache_dir(app)`, `home_dir` and `temp_dir`, each giving `Path | Missing` and each a confinement base.
  - **Added (F2):** `copy_to(target progress=@f)`, with `f:(chunk:DataSize :>void)` called after each chunk is copied.
  - **Added (F3):** `p.size` gives `int64*B`, a `DataSize`.
  - **Added (F35):** `write_bytes` and `write_text` take `permissions=`, and the file is created with that mode before the atomic rename.
  - **Added (F36):** `input(prompt hidden=true)` gives `secret<string> | EndOfInput | Canceled`.
  - **Added (F38):** `loop line in p.follow_lines`† tails a growing file. It yields whole lines only and is a cancellation point.
- **§8, add (F34):** `to_json` of a type containing `secret` fields is a compile error unless `secrets='reveal'`†. `from_json` fills `secret` fields.
- **§5:** `a.is_close(b rel= abs=)`, where `abs=` defaults to the zero of `a`'s type, so quantities need no `abs=` (F45).
- **§13 D10** is replaced by `open-items.md` D10.

## time-units-format

- **§2.1:**
  - **Kinds** (recheck 1):
    - `IntegerPattern` is any number pattern whose style is `d x X b o`;
    - `NumberPattern` is any other pattern with a sign, `#`, `0`, grouping, a precision or a style;
    - `TextPattern` is fill, alignment and width only;
    - date and time kinds contain field words.

    The validators are written to be exclusive, and the library test checks overlap witnesses (`,d`, `#06b`, `,`, `+`, `08.3e`, `>8`).
  - **Zones (C10):** "an `Instant` formats in UTC" holds only for the default `"{t}"`. A pattern with date or time-of-day fields formats an `Instant` in `$program.time_zone`, under D15a's decided rule for an unstated zone, which warns when the program sets none.
- **§2.4 (F52):** a duration's first field is unpadded (`1:05`, `61:31.750`). Clock times keep two digits (`09:05`).
- **§2.5, readers:** `date`, `instant`, `local`, `zoned` and `time_of_day` give `T | ValidationError`. `InvalidFields` is a child of `ValidationError`.
- **§2.6, count holes:** these use `CountHoleTemplate`†, a library record `[parts:array<string>]`.
  - A shape opts in when its validator has an overload taking one. The compiler calls it with the literal's text pieces when every hole is a count (`int64` ≥ 0). If it passes, the value has the shape.
  - Otherwise the string is an ordinary run-time string.
  - No keyword is involved: overload resolution is the opt-in. This is S8, now specified in ui-strings §2.2.
- **§3, add (F28, F37, C8):** `Duration(text)` and a reader per dimension name (`Mass(text)`, `Temperature(text)`, `Mass<rational>(text)`), each `T | ValidationError`.
  - They read exactly what display writes, repeating decimals and fractions included.
  - `15m` as a duration names `15minute`.
  - JSON writes a quantity as its display text and reads it back.
  - `label(q)` gives end-user text: long names, plurals, and common fractions within 1% ("⅓ cup", "1 ⅓ cups", "9 minutes") (F29).
- **§4.2:**
  - Ranges of a discrete type loop, stepping by the type's unit, and `r.step(s)` gives another step on any discrete range, ints included (F9). `[a,b..c)` stays the decided arithmetic form.
  - `days_of_week`† is the ordered array Monday…Sunday (F13).
  - `d.floor(1month)`, `d.floor(1week)` and `d.floor(1year)` on `Date` (F20).
- **§4.3 (recheck 10):** `round` on time takes all five `rounding=` policies, and its default matches numeric `round`.
- **§5 (recheck 8):** emptiness uses a declared capability.
  - A type is discrete if it has `next_up` (dates, instants, durations, integers, floats, and strings, where `s.next_up` is `s` followed by NUL).
  - It is dense if it is declared `$no_next_value`†, as `rational` is.
  - Otherwise `is_empty` on an open bound is a compile error naming both.
- **§7.1 (F30):** add `tbsp_us`, `tsp_us`, `tbsp` and `tsp` (metric 15 mL and 5 mL), and `stick_butter_us`.
- **§7.2:** `Information` becomes `DataSize`.
- **§8.1–8.3:** the prefix is `strict_` (C12; unchanged from the revision), `$time.only_strict_today` names the strict `today`, and `$program.time_zone_rules` names the rule pack.
- **§12** is replaced by `open-items.md` D29, D31 and D33–D37.

## ui-strings

- **§2:** the keyword is `check=` (owner question) and validators are named `…_problem`.
  - §2.2 gains the `CountHoleTemplate` opt-in (above).
  - §2.7: `T(x)` gives `T | ValidationError` for text and for other values alike, so one type covers both. The "not a `ParseError`" paragraph goes.
- **§2.5 (recheck 5, F49):** the `fmt` example uses `DatePattern` and words: `fmt'weekday day month_name'`. `DateFormat` and `LocalPattern` go, and the kinds are time's seven (§2.1 there).
- **§2.9:**
  - `date(text "d/M/y")` becomes `date(text 'day/month/year')`.
  - `DateText` and `DatePattern` keep their roles.
  - Ported validators are renamed `…_problem`.
- **§3:** `Action(s)` gives `Action | ValidationError`.
- **§4 audio:**
  - `play` gives a `PlayingSound`, a receipt, with `.stop .wait .running .paused .pause .resume .position .volume`. `.playing` goes, and `loop p.running` is the poll.
  - `tone(440Hz 500ms)` and `Sound.length` are unchanged.
- **§5:**
  - `input.save(path)` gives the path (a receipt).
  - `rebind` gives `Action | none` (a receipt).
  - `listen_for_press` replaces `capture`, with `.next`.
- **§6.3 slider:** `slider(title @v range step= …)`.
  - The range is the interval (D15d), and a two-thumb slider binds `@band:Range<T>` over a range.
  - A descending slider passes `descending=true`.
  - `value_text=` takes a function, and the idiom is `value_text=fmt'.0%'` (F50).
- **§6.4:** `input_field` replaces `field`.
  - Readers are C7's.
  - `read=` takes `(text:string):>T | ValidationError`.
  - `hidden=true` binds a `secret<string>`.
- **§6.5, add (F11):** `checkbox(title checked=expr)` shows a derived state. Read the click with `changed(title)`.
- **§6.6:** `TableSort<C>` (`by`, `descending`).
- **§6.7:** `plot(values range=[0.0..1.0] style='line'|'bars')`. `kind=` and `low=`/`high=` go (C14, C15).
- **§6.8 table:** the tabs, segments and `style=` rows are unchanged, and `plot`'s row reads `style=`.
- **Game hooks (F15):** `update = (dt:Duration) => …`. The physics example drops `dt * 1s`. A `float64*Time` view is `dt as float64*s` where float speed matters. Flagged in D28, not a question (no legacy, and both tests pass).
- **§8** is replaced by `open-items.md` D11 and D28.

---

## Round 2 (after dogfood3 and the round-6 cold read)

Round-6 renames, applied above and everywhere:

| Was | Now |
|---|---|
| `weekdays` | `days_of_week` |
| `RelativePath` | `SubPath` |
| `r.every(step)` | `r.step(step)` |
| `refuse` | `forbid` |
| `$dense` | `$no_next_value` (pending) |
| `p.follow` | `p.follow_lines` (pending) |
| `CountTemplate` | `CountHoleTemplate` (pending) |
| `main = (app:Tasks)` | `main = (app:BackgroundTasks)` (pending) |

The prefix stays `strict_`.

### parallel-v4
- **§5, add: `catch_ctrl_c`** (P1). It gives an interrupt listener.
  - While any listener is held, a Ctrl-C press cancels nothing. The press is queued on the listener: `.next` waits for one, `@ctrl_c.next` is a `Waitable` for `select`, and `.discard_pending` forgets queued presses (name untested).
  - A console read in progress (`input`, `read_line`, `stdin_lines`) gives `Interrupted` (a failure value, not `Canceled`), and that takes the press.
  - Three presses within one second end the process with 130 and the "cleanup skipped" report, whether or not a listener is held.
  - Dropping the last listener restores the default.
  - Child processes in the same process group still receive the terminal's SIGINT. Job control (`start_process(… new_group=true)` and handing the terminal to a foreground group) is library work, and its semantics are stated here.
  - C3 is unchanged: no cancellation happens, so there's nothing for `??` to swallow.
- **§6 `Task`, revised** (P2): `group.spawn(@f)` gives `Task<E>`, where `E` is `f`'s failure set.
  - `.wait` gives `void | E | Canceled` in every kind of group, which replaces v4's "never the task's value or error". `.error` gives `E | none`.
  - In a scoped `tasks(…)` group, a failure also fails the group, as before.
  - In the program's group (`BackgroundTasks`), it doesn't: the error prints once on stderr, naming the task's function, and stays on the handle.
  - `BackgroundTasks` has the `Tasks` API. Its own type exists for the different failure policy and so that the lifetime is visible at the declaration.
- **§6 sources** (P8): `Ticker` has `.next` (wait for the next tick; gives `ClockReading | Closed | Canceled`; a receipt), `.next(timeout=…)`, `.stop` and `.running`. It has no `.wait`, and `@tick.next` replaces `@tick.receive` in `select`. The interrupt listener has the same shape.
- **§6, frame code:**
  - In `update`, `draw` and helpers reached only from them, these are compile errors: waiting on a channel (`receive`, `send` that may block), a task's `.wait`, `sleep`, `select`, `within`, and a `.next` on a source. The error names `drain`, `try_send` or `app.spawn`.
  - File, terminal and process-start calls compile, with a hover note, so a settings screen saves in one line.
- **§6, unheld sounds:** a `PlayingSound` whose handle is dropped is adopted by the program's group.
  - Exit waits for it to end, bounded by its length; a looping one is stopped at exit.
  - Ctrl-C stops it.
  - This also covers `main`-only programs: the runtime has a program group even when `main` doesn't take it.

### safety-round3
- **§6:** `secure_random(range)` gives a plain value, `T | NoEntropy`. `secure_token` and `secure_random_bytes` stay secrets.
- **§8, files:**
  - `p.modified`, `p.created` and `p.accessed` give `Instant`s.
  - `remove_file` and `remove_dir` give the removed path, which is a receipt.
  - The progress example shows the capture: `progress=(chunk $capture @stats) => stats.bytes += chunk`. The missing-capture error's fix-it inserts it.
- **§8, processes:** `start_process(program args cwd=Path env=dict<string string> stdin= stdout= stderr= new_group=false)`.
  - Each stream is `'inherit'` (the default), `'null'`, `'pipe'`, a `Path`, or another process's pipe, so `a | b` is `let a = start_process(… stdout='pipe')` followed by `start_process(… stdin=a.stdout)`.
  - With `'pipe'`, `.stdout` and `.stderr` are line and byte streams, and `.stdin` is a writer.
  - `ExitStatus` is `[success:bool code:int64? signal:int64?]`.
  - `set_current_dir(path)` gives the previous folder (a receipt).
- **§8, secrets:** `to_json(x secrets='reveal')` gives `secret<string>`. `write_text` and `write_bytes` of a secret create the file `0o600` unless `permissions=` says otherwise, and `.reveal` on the text gives ordinary text that is written with ordinary permissions.
- **§5, `is_close`:** on temperature points (and any offset dimension), `abs=` is required and is the difference type. `rel=` is a compile error there.

### time-units-format
- **§2.2 and §4.3, rounding (P7):** exact values (`rational`, decimals, integer-division results, `Duration`, `Instant`) round half away from zero, and floats half to even. These are the decided defaults, and `fmt`, `round`, `t.round` and `quantize` all follow them. The "ties to even" sentence in §2.2 is withdrawn.
  - Override keyword: owner question D31 Q5. The recommendation is `rounding=` with nine values, which takes over the decided `ties=` values `'away' 'even' 'zero' 'up' 'down'` as `'nearest_away' 'nearest_even' 'nearest_toward_zero' 'nearest_up' 'nearest_down'`, and adds `'floor' 'ceil' 'toward_zero' 'away_from_zero'`.
- **§2.4, compact forms (P3):**
  - A pattern may join two fields with `""`, an empty quoted literal that pads like `-`.
  - The word `iso_basic` is the whole basic-format form for each kind:
    - `Instant` → `YYYYMMDDTHHMMSSZ`;
    - `ZonedDateTime` → `…±HHMM`;
    - `LocalDateTime` → `…THHMMSS`;
    - `Date` → `YYYYMMDD`.
  - Fractions appear only when nonzero, as `.fff…`.
  - The §2.5 reader takes the same pattern. "A pattern needs something between its fields" now counts `""` as something.
- **§3, add (P4):**
  - `q.value_in(unit)` gives the bare number of any quantity in that unit. For a temperature point, that is the reading on that scale.
  - `/ unit` on a point is a compile error with that fix-it.
- **§3, add (P6), two text forms:**
  - `T(text)` reads programmer text strictly.
  - `T.parse_human(text)` reads people's text. It accepts:
    - everything `T(text)` accepts;
    - `label` output (long names, plurals, common fractions);
    - spaced and short forms (`1h 30m`, `36.1 °C`, `21.4C` when the target dimension decides `C`).
  - For `Duration`, "N days" and "N weeks" read as 24-hour days.
  - Months and years are refused, naming the calendar types.
  - Ambiguous units (`cup`) are refused, naming the choices.
- **§3, add (D36): run-time quantities.**
  - `Quantity(text)` reads any quantity into a value whose dimension is known only at run time (`q.dimension`).
  - `Unit(text)` looks a unit up by its written name, through a table that links only when used.
  - `q.to(u)` gives `Quantity | DimensionMismatch`.
  - `Quantity` prints like any quantity and converts to a static dimension with `q as Mass` (an obligation) or `Mass(q)` (`Mass | DimensionMismatch`).
- **§4.2 (D29):**
  - `z.next(w)` on `ZonedDateTime` keeps the time of day and zone, resolving gaps and folds by the §8.1 default.
  - `r.step(s)` works on every discrete range.
- **§7.4:** money becomes a named next item, user-declared base dimensions, rather than a floor.

### ui-strings
- **§2.7 and §6.4, readers (P5):**
  - A refinement alias (`Port:type = int64<(1 <=? x <=? 65535)>`) and a shape alias get `T(text)` and `T.parse_human` automatically: the base type's reader, then the predicate or validator. The failure is a `ValidationError` whose message prints the refinement ("must be 1 to 65535").
  - A record or other user type declares `__read__ = (text:string):>T | ValidationError => …` (owner question D11 Q3). `T(text)`, `T.parse_human` (unless a separate `__parse_human__` is given), `input_field` and union readers use it.
  - `T(field=…)` with named arguments is the checked constructor, giving `T | ValidationError`, while `T[…]` stays the proven literal.
- **§4, add:** `load_sound(path)` gives `Sound | ValidationError | FileNotFound` (wav, ogg, flac).
- **§5, add:** `input.pressed_at(action)` gives `ClockReading?`, the press's own timestamp, and `sound.position_at(reading)` gives the song position at that reading.
- **§6.4 `input_field` (P6):** it shows `label(x)` and reads with `T.parse_human`.
  - `error=expr` (`string | none`) shows the text under the field and makes `valid(id)` false, for cross-field checks.
  - Ids passed to `valid`, `changed` and `committed` are checked while compiling against the titles and `id=`s of trees built in the same function. A typo is a compile error.
- **§6.5:** a plain variable passed to `checkbox(… checked=x)` gets a hint, "to let the checkbox change `x`, write `@x`", because the round-6 readers took `checked=` for a binding.
- **`label(none)`** is `""`.

---

## Round 7 renames (final cold read; names only, no design change)

| Was | Now | Note |
|---|---|---|
| `listen_for_interrupt` | `catch_ctrl_c` | 5/4/3 against 4/3/3 |
| `ProgramTasks` | `BackgroundTasks` | 4/3/4 against 3/2/3 |
| `task.failure` | `task.error` | Read slightly better |
| `T.from_label` | `T.parse_human` | `from_label` read as enum-variant lookup. The protocol hook is `__parse_human__` |
| `input_field(problem=)` | `input_field(error=)` | |
| `q.number_in(u)` | `q.value_in(u)` | |
| `q.as_unit(u)` | `q.to(u)` | 5/4/5 |
| `listener.clear` | `listener.discard_pending` | `.clear` read 3/3 as "remove registered handlers". **The new name is untested** |

- **Weak, kept and flagged in the items** (library-author or niche names):
  - `$no_next_value`: it and `$no_successor` both read as "may take a next value without proof".
  - `CountHoleTemplate`: it and `CountedPattern` both failed.
  - `input.pressed_at` and `sound.position_at`: mediocre.
- **The prefix:** round 7 read `strict_in_zone` 2 of 3 times as "strictly inside a zone". The prefix is an owner question again (D31 Q6), and the recommendation is to keep `strict_`.
