# Dogfood 3: independent ergonomics check of the integrated design (2026-11-07)

- **What was tested:** `conventions.md` (C1–C18), `amendments.md` and `open-items.md`, over parallel-v4, safety-round3, time-units-format, ui-strings and the stem, with LANGUAGE.md and decisions.md for today's language.
- **Programs:** 16 new ones in `~/dev/tmp/int-1107/dogfood3/`, none of them on tasks in dogfood-1107/a, dogfood-1107/b or rev-1107/dogfood2. All are paper (the block form, receipts, shapes and the new readers don't compile today). Each program's header carries its grades. Comments marked `# !` show where the design or library failed me, at the line where it happened.
- **Axes:** O obvious, D discoverable, C concise, S safe by default, X complete, Y consistent. Each is graded against what Python, Go, Rust, TypeScript and Swift give for the same program.

## Scores

| # | Program | O | D | C | S | X | Y | Main reason it's below 5 |
|---|---|---|---|---|---|---|---|---|
| 01 | File-sync daemon | 5 | 4 | 4 | 5 | 3 | 3 | `modified` is a `Date`; `tick.receive` needs `;`; `Ticker.wait` means the opposite of what's expected |
| 02 | Text adventure | 5 | 4 | 4 | 5 | 5 | 5 | Dictionary-key proof on `here:string`; the reader's message is thrown away |
| 03 | Budget tracker | 4 | 4 | 4 | 3 | 3 | 3 | USD + EUR adds silently; `fmt` rounds money ties-to-even, against the decided half-away rule; two step spellings |
| 04 | Rhythm game | 4 | 4 | 5 | 5 | 3 | 4 | No input event timestamps: frame-time judging is wider than the "perfect" window |
| 05 | Job API over channels | 4 | 4 | 4 | 5 | 3 | 5 | One failed job fails the whole group; reply channels by hand |
| 06 | Markdown → HTML | 5 | 4 | 4 | 4 | 4 | 5 | No HTML-safe text type; the regex replace API is unspecified |
| 07 | Sensor logger | 4 | 3 | 4 | 4 | 3 | 3 | `/ unit` and `is_close` break on temperature points |
| 08 | Tower-defense waves | 5 | 5 | 5 | 5 | 4 | 5 | No deque or priority queue (library) |
| 09 | Shell with processes | 3 | 3 | 4 | 4 | 2 | 4 | Ctrl-C can't be handled; `start_process` has no cwd, env, pipes or `ExitStatus` members |
| 10 | iCalendar export | 3 | 3 | 3 | 5 | 2 | 3 | `fmt` can't write basic ISO (`20261110T090000Z`), though the readers accept it |
| 11 | Parallel prime sieve | 5 | 4 | 5 | 5 | 5 | 4 | `[a,b..c)` for integers but `.every(step)` for dates |
| 12 | Settings form | 4 | 3 | 4 | 4 | 3 | 3 | `input_field` shows programmer text (`720hour`); no cross-field slot; `Port(text)` undefined |
| 13 | Countdown across DST | 4 | 4 | 4 | 5 | 4 | 4 | `;` after a one-wait `select`; a dropped sound at the end of a CLI program is unspecified |
| 14 | Dice bot | 4 | 3 | 4 | 4 | 4 | 3 | `secure_random` gives a secret for public values; a user type can't declare `T(text)` |
| 15 | Thumbnailer UI | 4 | 4 | 4 | 5 | 4 | 4 | A failed background task closes the window |
| 16 | Unit-converter CLI | 3 | 3 | 4 | 5 | 2 | 3 | No reader for a quantity of unknown dimension; no unit lookup at run time |

- Only 08 and 11 come close to full marks. None of the 16 reaches 5 on every axis.
- The core of the integrated design holds up: the block form, `?? void`, receipts, shapes, `fmt` words, the three clocks and ranges. Most of what's missing is at the edges where a program meets the outside world: signals, processes, end users typing into fields, external formats, and money.
- **Verdict:** not ready to go to the owner as it stands. Eight design problems (P1–P8) block specific items. Most have a one-paragraph fix, and none reopens a core decision.

## Design problems, ranked

### P1. Ctrl-C can't be handled at all (D4, C3)
- **Where:** `09_shell.dewy:39` and `:53`.
  - A shell, a REPL, an editor or a TUI game needs Ctrl-C to clear a line or stop the foreground child, not to end the program.
  - Under v4, the first Ctrl-C cancels `main`'s scope, and cancellation is level-triggered (amendments §5 relies on this).
  - So even `input("$ ") ??<Canceled> continue` doesn't help: every later wait gives `Canceled` at once, and the loop spins or leaves.
  - A child started by `start_process` gets SIGINT from the terminal too, so the shell and its child both die.
- **Others:** Python catches `KeyboardInterrupt`, Go has `signal.Notify`, Rust has `ctrlc` or tokio's `signal::ctrl_c()`, Node has `process.on('SIGINT')`, Swift has `DispatchSource` signals. Every one of them lets the program take over.
- **Fix:** add a handle, for example `let ctrl_c = listen_for_interrupt` (cold read pending).
  - While it is held, Ctrl-C is delivered to it as an event (`select` on it, or call `.next`) instead of canceling `main`.
  - A second press within one second still ends the process.
  - Dropping the handle restores the default behavior.
  - This keeps C3: `??` still never swallows a cancellation, because no cancellation happens.
  - It also needs process groups for job control: `start_process(… new_group=true)` and foreground hand-off. That is library work, but the semantics have to be stated.

### P2. A failed background task takes down the program group (D4 Q2, D28)
- **Where:**
  - `15_thumbnailer_ui.dewy:45`: a missing folder fails `make_thumbs`, which fails the program group, which closes the window with an error report;
  - `05_job_api.dewy:28`: one bad job ends the API.
- v4 §6 says "`.wait` … never [gives] the task's value or error; a failure already fails the group". That fits scoped `tasks(…)`. It's wrong for a group that lives as long as the program, which is exactly what D4 Q2 adds.
- **Others:** Erlang supervisors, Go (errors are values; only panics kill), Trio and Swift `TaskGroup` (the error is seen when the group is awaited, but an app keeps a long-lived group per feature), and Rust's `JoinHandle` (the error is returned to whoever joins).
- **Fix:** `group.spawn(@f keep_failure=true)` (name pending). It gives a `Task<E>` whose `.wait` gives `void | E | Canceled`, and the group doesn't fail.
  - As an alternative, make that the default for the program's own group only, with `.failed`/`.error` on `Task`.
  - The common UI case is then `if job.failed is? error note = "{job.failed}"`.

### P3. The writer can't produce what the reader accepts: ISO basic form (D37)
- **Where:** `10_ical_export.dewy:7–14`.
  - iCalendar, ISO file names, AWS signatures and HTTP `Date` caches all use `20261110T090000Z`.
  - time-units §2.5 says plain `instant(text)` *reads* it, and that "a pattern needs something between its fields". `year month day` writes `2026 11 10`, and the padding rule only covers `- / . :`.
  - The only way is to interpolate members padded with `fmt'02d'`, which also means converting to a zone first. That is ten lines where Python needs one: `strftime('%Y%m%dT%H%M%SZ')`.
- **Fix:**
  - (a) An empty quoted literal `""` joins two fields with nothing between them and pads like `-` (`fmt'year""month""day"T"hour""minute""second"Z"'`).
  - (b) Better: one word for the whole form, `fmt'iso_basic'`, plus `t.iso(basic=true)`.
  - Take (b), and (a) for custom compact stamps. Both are new spellings, so they need the cold read.
- Also missing here, as a library item: emitting `VTIMEZONE` from the zone data.

### P4. Temperature points break two unit idioms (D34, D36)
- **Where:** `07_sensor_logger.dewy:31` and `:35`.
  - D36 teaches "`x / unit` gives the bare number". For a temperature *point*, `r.t / 1°C` is scaling a point, which the offset-unit decision makes a compile error. There is no stated way to get "21.4" from a reading. `(r.t - 0°C)/1K` works, but nobody will find it.
  - `a.is_close(b abs=)` defaults `abs=` to "the zero of `a`'s type". For a point, that zero is absolute zero, which isn't a tolerance. The tolerance of a point is a difference.
- **Fix:**
  - `t.number_in(°C)` (or `t / °C` defined on points as "the reading on that scale"; pick one and cold-read it);
  - `is_close` on points takes `abs:TemperatureDifference`, defaulting to `0K`.
  - Both go in D34's semantics.

### P5. Users can't follow the reader convention for their own types (C7, D11 Q2, D28)
- **Where:**
  - `14_dice_bot.dewy:8–13`: C7 says every reader is `T(text)`, and `input_field` relies on readers, but nothing says how `Roll(text)` is declared for a user record. I fell back to `parse_roll`.
  - `12_settings_form.dewy:11`: whether a refinement alias (`Port:type = int64<(1 <=? x <=? 65535)>`) gets `Port(text)` is unstated, and so is whether `input_field("Port" @s.port)` works.
- **Others:** Swift `init?(_ description:)` / `LosslessStringConvertible`, Rust `FromStr`, Python `__init__` from text.
- **Fix:**
  - (a) A refinement or shape alias gets `T(text)` automatically: the base type's reader, then the predicate, which gives `ValidationError` with the refinement's text ("must be 1 to 65535").
  - (b) A record declares its reader as an ordinary overload member, for example `Roll:type = [… $read = (text:string):>Roll | ValidationError => …]`, and `Roll(text)` and `input_field` find it.
  - (b) is new surface and goes to the owner with a recommendation; (a) is a natural extension.

### P6. `input_field` speaks programmer text to end users (C8 against D28)
- **Where:** `12_settings_form.dewy:40`.
  - C8 makes display text Dewy text (`720hour`, `36.(1)°C`, `0.(3)`), and makes `label(x)` (`"30 days"`, `"⅓ cup"`) end-user text that "isn't read back".
  - `input_field` "uses exactly these readers" (C8), so a retention field shows `720hour` and rejects "30 days" or "1h 30m".
  - `keep=30day` is refused as a `Duration` (calendar periods are decided), which is right for programmers but has no answer for a settings screen.
- **Fix:**
  - `input_field` shows `label(x)`, and its default reader accepts Dewy text plus the label forms (`30 minutes`, `1h 30m`, `1 ½ cups`, `36.1 °C`).
  - Name that reader something like `read_label` and keep it distinct from `T(text)`, so programs and JSON stay strict.
  - For durations a person types "30 days" meaning 720 hours, so the label reader may read `day` as 24 hours. Say so explicitly.

### P7. Rounding: the integration silently overrides a decided rule twice (D31, D37)
- **Where:** `03_budget.dewy:22`.
  - decisions.md: "human-oriented types (rational, decimal, int division results) round half away from zero … Both take `ties=` to override".
  - time-units §2.2: `fmt'.2f'` on a `rational` "rounds once from the exact value, ties to even". A budget then prints `0.125` as `0.12`, where a person, Excel and Python's `Decimal(ROUND_HALF_UP)` give `0.13`.
  - C15 renames `ties=` to `rounding=`. It's a good change, but neither D31 nor D37 states it as a change to a decided rule.
- **Fix:**
  - `fmt` on exact values follows the decided per-type default (half away for `rational`, ties-to-even for floats);
  - D31 lists "`rounding=` replaces your `ties=` (2026-10-2x)" as a decided-rule change for the owner to confirm.

### P8. Handle verbs don't fit `Ticker`, and waiting on a tick needs `;` (C1, C5)
- **Where:** `01_file_sync.dewy:42` and `13_countdown_dst.dewy`.
  - `tick.receive or_throw` as a statement expresses a `ClockReading`, so it needs `;`. Receipts don't cover it, since the amendments list `ticker(…)` and readers as non-receipts.
  - Under C1, `tick.wait` means "wait until the ticker *ends*". That never happens unless it's stopped, and it's the opposite of what anyone reading `tick.wait` in a loop expects.
- **Fix:** `Ticker` has `.next` (wait for the next tick; a receipt) and `.stop`/`.running`, but no `.wait`. State the exception in C1.

### Smaller design items (should-fix; each names its item)
- **D10, files:** `p.modified` is a `Date` (LANGUAGE.md), which a sync tool can't use (`01_file_sync.dewy:13`). It should be an `Instant`, as in C16's spirit of "units all the way through".
- **D10, C6:** what `remove_file` and `remove_dir` return isn't stated. Recommend the removed path, as a receipt.
- **D10 Q6, processes:** before `start_process`/`Process` is named, specify the rest: `cwd=`, `env=`, `stdin=`/`stdout=`/`stderr=` (inherit, null, pipe, a file), piping one process into another, and `ExitStatus` (`.success`, `.code`, `.signal`) (`09_shell.dewy:53–65`). Go's `exec.Cmd`, Rust's `Command` and Python's `subprocess` all have these, so the surface isn't complete without them.
- **D10 Q2, randomness:** `secure_random(range)` gives `secret<int64>` (`14_dice_bot.dewy:27`). Prize draws, shuffles and lottery picks are unpredictable but public, so every use writes `.reveal`, and the type tells readers the value is sensitive when it isn't. Recommend that `secure_random` gives a plain value, while `secure_token` and `secure_random_bytes` stay secrets (they make keys).
- **D10/C18, secrets on disk:** `to_json(x secrets='reveal')` then `write_text` creates a world-readable file (`12_settings_form.dewy:59`). Recommend that `secrets='reveal'` gives a `secret<string>`, and `write_text` of a `secret` defaults to `permissions=0o600`.
- **D28 and C4, frame code and waits:** "frame code never waits" (C4) doesn't say whether a file write in `draw` (`12_settings_form.dewy:50`) is an error. If it is, saving a form needs a spawn plus a channel back. Recommend:
  - file and terminal I/O in frame code compiles, with a hover note;
  - waiting on a channel or task is the error.
- **D28, ids:** `valid("Port")` and `changed("Full screen")` use title strings. Check them while compiling against the tree, as picks are checked (`12_settings_form.dewy:43`).
- **D28, cross-field validation:** add `input_field(… problem=expr)`, which shows `expr`'s text under the field and makes `valid(id)` false. Without it, every save button repeats each condition by hand.
- **C2, unheld sounds at exit:** `play(tone(…))` on `main`'s last line (`13_countdown_dst.dewy:28`). "Plays to the end" conflicts with the process exiting. Recommend that an unheld `PlayingSound` belongs to the program group, so exit waits for it (bounded by its length), and Ctrl-C stops it.
- **D29 against today's language, step spellings:** integer ranges step with `[a,b..c)` (LANGUAGE.md:835), while date ranges use `.every(1month)` (`03_budget.dewy:36`, `11_prime_sieve.dewy:21`). `.every` is justified for calendar steps, since `+1month` isn't a constant difference. Recommend `.every(step)` on every discrete range, ints included, with `[a,b..c)` kept as the decided arithmetic form, and state the relation in D29.
- **D29:** `.next(weekday)` and `.at(time)` exist on `Date` and `ZonedDateTime` respectively. Moving a zoned time to the next Friday (`10_ical_export.dewy`) needs `z.date.next('friday')` and then a zoned `at`. Recommend `z.next('friday')`, which keeps the time and zone.
- **D36, quantities at run time:** C8 promises "what prints reads back", but only when the dimension is known while compiling. A converter (`16_unit_cli.dewy:9–14`) needs:
  - `Quantity(text)`, a dimension-erased value with `.dimension`;
  - `Unit(text)`, a unit looked up by its written name;
  - `q.as_unit(u)`, giving `Quantity | DimensionMismatch`.

  Python's `pint` and Swift's `Measurement`/`UnitConverter` have this.
- **D36 (§7.4 floor), money:** a budget is an ordinary program. The floor "money is a `rational`" lets USD + EUR compile silently (`03_budget.dewy:7`, S3). Recommend user-declared base dimensions (`USD:unit = base_unit("USD")`) as a named next item, so `5USD + 3EUR` is a compile error and `fmt',.2f'` prints `1,234.50USD`. Not a blocker for D36, but it needs an item, not a floor.
- **Error context (cross-cutting):** `03_budget.dewy:13–17` repeats `?? return Bad[n "…"]` and throws away the reader's own `ValidationError` message to add a line number. Rust's `anyhow::Context`, Go's `%w` and Python's `raise … from` cover this. Recommend `x or_throw Bad[line=n]`, which wraps with `cause=` (new syntax, to the owner), or a library `with_context`. It's the commonest validation-pipeline friction left.

## Library floors (not design problems)
- HTTP client and server (05), file-change notification (01), serial ports (07), image decoding and resizing (15), and `which`/`find_program` (09).
- Regex captures and `replace_all` with groups (06, 14); an HTML-escaping text type, or a typed `Html` interpolator (06; ui-strings §2.8 already scopes injection safety as its own design).
- A string builder (09: O(n²) concatenation by interpolation), a deque and a priority queue (08), `isqrt` (11), a character boundary at or before n bytes (10), `split_once` (07), and `VTIMEZONE` emission (10).
- An audio file loader (`load_sound`) next to `melody` and `tone` (04).

## Notes on scores under 5 not covered above

Scores not listed here follow from P1–P8 and the smaller items, at the lines cited there. D10 Q4 and D31 Q5 weren't exercised, so they stand as written.

- **01 D4 (line 16):** a `progress=` lambda that adds to a local needs `$capture @stats`, and nothing in the `copy_to(progress=)` text shows it. Fix: the design's example shows the capture, and the error's fix-it inserts it.
- **02 D4 (line 17):** `g.rooms[g.here]` needs a membership proof. The fix is a `RoomId` union with `totaldict`, which is today's language and documented, but no error message would point a beginner there. Fix: the fix-it suggests a literal-union key.
- **02 C4 (line 35):** `Verb(words[0]) ?? { … }` loses "did you mean 'take'?". Fix: a block fallback may bind the failure, `?? (e) => { printl(e.message); continue }`. It's new syntax and small. The other way, writing `match`, costs four lines.
- **04 X3 (line 34):** add `input.pressed_at(action):>ClockReading?` and `PlayingSound.position_at(reading)` to D11b, so rhythm, fighting and music games judge by event time. SDL, Unity's Input System and the Web's `event.timeStamp` all give this.
- **04 Y4 (line 61):** `label(x?)` should give `""` for `none`.
- **05 C4 and O4 (lines 24–33):** matching a union of records inside `select`'s named record repeats each record type. Naming the request kinds as types fixes most of it. The one-shot reply channel per request is Go's idiom too, so it's accepted.
- **06 C4 (line 26):** a local helper that closes over two places needs `$capture @open @out`. That's the decided closure rule, so it's accepted.
- **06 S4:** links in Markdown need URL and attribute escaping. That's a library floor, but it caps S.
- **07 X3:** a reader that's lenient about `21.4C` and `21.4 °C`. P6's label reader would cover it.
- **11 D4 (line 21):** whether `m - lo` is proven in bounds depends on the prover seeing `start >=? lo` through a ceiling division. That's proof engineering, not design.
- **13 C4:** the `;` after the one-wait `select`. P8's `.next` doesn't cover a wait with a deadline. Recommend `tick.next(timeout=at)`.
- **13 O4:** the error from `zoned(… fold='reject' gap='reject')` is a union, and one `??` can't say which case it was, while a `match` takes four lines. That's acceptable.
- **14 D3 (line 20):** building a record with refined fields from run-time numbers is an obligation, and there's no "construct or `ValidationError`" form. Fix: `Roll(count=… sides=…)` as a checked constructor giving `Roll | ValidationError` (with P5).
- **15 O4 and C4:** P2. `job.stop` on a `Task?` is also unclear: does a member call forward `none`?

## Per-item verdict (open_decisions items in open-items.md)

| Item | Verdict | Must-fix list |
|---|---|---|
| **D4** parallel v4 | **Must fix** | P1 (interrupt handle); P2 (failure policy for the program's group and `Task`); P8 (`Ticker.next`, no `.wait`); state which calls count as "waits" in frame code; unheld sounds at exit |
| **D10** safety defaults | **Must fix** | `modified` → `Instant`; the full `start_process` surface (cwd, env, stdio, pipes, `ExitStatus`); `secure_random` gives a plain value; a revealed secret stays secret until written at 0o600; `remove_*` results |
| **D11** shapes, actions, audio | **Must fix** | P5 (how a user type declares `T(text)`; refinement aliases read automatically); `load_sound`; D11b event timestamps (should-fix) |
| **D22** delete `$parallel_safe` | **Ready** | — |
| **D28** UI | **Must fix** | P6 (`input_field` shows and reads end-user text); `problem=` for cross-field validation; ids checked while compiling; P2 as it applies to the window |
| **D29** dates | **Ready after one edit** | State how `.every(step)` relates to `[a,b..c)`; add `z.next(weekday)` (should) |
| **D31** time spellings | **Must fix (text only)** | P7: list `rounding=` replacing the decided `ties=` as a change to confirm |
| **D33** self-length alias | **Ready** | Not exercised by these programs |
| **D34** temperature difference | **Must fix** | P4: the bare number of a point; `is_close` tolerance on points |
| **D35** `in_zone` | **Ready** | — |
| **D36** dimensions and units | **Must fix** | P4's `/ unit` on points; `Quantity(text)`/`Unit(text)` at run time (or state it as a floor with a named next item); money as a named next item, not a floor |
| **D37** `fmt` | **Must fix** | P3 (basic ISO and adjacent fields); P7 (exact values round by their type's decided default) |

## The 17 owner questions: should any change?
- **D4 A (`??` never defaults `Canceled`):** keep. Add one line: "a program that wants Ctrl-C for itself holds `listen_for_interrupt`" (P1). Without that, the question invites the objection "then a shell can't survive Ctrl-C".
- **D4 Q1 (`or_throw_only<E>`):** keep. It was used naturally in 05 and 13.
- **D4 Q2 (`main = (app:Tasks)`):** keep the surface, but **change the text** to include the failure policy (P2). As written, a typo in a background task closes the user's window.
- **D4 Q8 (`.stop`/`.wait` as shared verbs):** **change.** Exempt `Ticker` from `.wait` and give it `.next` (P8).
- **D10 Q1 (tag names):** keep.
- **D10 Q2 (random and secure names):** **change.** `secure_random(range)` gives a plain value; the names themselves are fine.
- **D10 Q3 (path names):** keep. `FileName(name)` was the honest fix in 09, and `relative_to` read well in 01.
- **D10 Q5 (receipts):** keep. They removed every `;` on `make_dirs`, `write_text`, `play`, `spawn` and `append_text` in these programs. Add `Ticker.next` to the receipt list. The only `;` left was on a `select` used as a timed wait.
- **D10 Q6 (library renames, `start_process`/`Process`):** keep the names, but say in the text that the process surface (cwd, env, stdio, `ExitStatus`) is specified before landing.
- **D10 Q7 (float extras):** **change.** `is_close`'s `abs=` default on points (P4).
- **D11 rule narrowed (literal unions must be proven):** keep. `Verb(words[0]) ?? …` and `Dir(arg) ?? …` were natural in 02.
- **D11 Q1 (`check=`):** keep `check=`. It read naturally in 12 and 14.
- **D11 Q2 (`ValidationError`):** keep, and **add** the user-reader spelling (P5) as its own question, with a recommendation.
- **D11 Q3 (audio, controls names):** keep. Add `load_sound` and `pressed_at` (cold read pending).
- **D31 Q1 (compatible gap/fold default):** keep. 13 used `fold='reject' gap='reject'` with input from outside, and it was one argument away, as promised.
- **Missing question to add:** "`rounding=` replaces your decided `ties=`, with the five policies everywhere" (P7).

## What worked (no change needed)
- Receipts. `out.make_dirs or_throw`, `write_text` returning the path (`06_markdown.dewy:63`) and `play(...)` read like Python and stay checked.
- The block form and `[parallel …]` with `check_cancel` (11), `partition_failures` (03, 15), and `?? void` on `try_send` (15).
- `fmt` words for dates and durations (`fmt'month_name year'`, `fmt'minute:second.millisecond'`). Readers taking the writer's pattern (`rational(text ',.2f')`, `date(text 'year-month-day')`) were the best part of 03.
- The three clocks: `timeout=at` with an `Instant` (13), `update(dt:Duration)` (04, 08), and `ceil(1s)` for countdowns.
- Path safety: `glob[…]`, `list` giving `FileName`s, `f.name` joins (15) and `relative_to` (01) needed no confinement. The one place the compiler would object (`09_shell.dewy:25`) was a real bug.
- `main = (app:Tasks)` plus `ch.drain` made the UI-with-background-work program (15) short and obvious, apart from P2.
