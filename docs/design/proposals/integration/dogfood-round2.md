# Independent dogfood, round 2 (2026-11-07)

Designs under test: `parallel-v4.md`, `safety-round3.md`, `time-units-format.md`, `ui-strings.md`, with `stem.md`, `decisions.md` and `LANGUAGE.md` as the current language. Seventeen new programs in `~/dev/tmp/rev-1107/dogfood2/`, written before opening the revisers' programs or grade tables. All are paper: nearly every construct they use is unbuilt. Nothing was run, so nothing opened a window or played sound. Each friction point is marked `# F<n>` in the source, and the catalogue in §3 explains it and gives the fix.

Axes: O obvious, D discoverable, C concise, S safe by default, X complete, K consistent (do the four designs read as one language?).

## BLUF

- **No design is ready.** Each has 2 to 4 must-fixes. Most of them sit at the seams between designs, which the revisers' self-grades of about 5 couldn't see, since each design was graded alone.
- **The worst seam is a silent-wrong-behavior bug:**
  - `??`, `?? void` and `partition_failures` all swallow `Canceled`, and cancellation is level-triggered.
  - So after the new Ctrl-C notice, `loop { let m = ch.receive ?? "" … }` spins.
  - `input_int("n? ") ?? 0` gives 0.
  - `[parallel f in files work(f) ?? void]` returns a short list, and the program carries on and exits 0.
- **Next worst:**
  - Handle verbs differ: `Task.cancel` vs `Playing.stop`, `.running` vs `.playing`, and a `Ticker` you stop by dropping it.
  - The UI's frame callbacks have no place for structured background tasks.
  - Six failure shapes for "this text didn't read".
  - Two clocks are both called `Instant`.
  - ui-strings still teaches TR35 patterns that the time design makes a compile error.
- **What already works well, and should be kept:**
  - `fmt` as a value you build once and pass on (`value_text=fmt'.0%'`).
  - Words in date patterns.
  - `$program.*` settings.
  - `or_throw<Canceled>`.
  - `partition_failures`.
  - `FileName` from `list`.
  - `shielded`.
  - D26 steering servers toward owner tasks.
  - A generic `slider` with units.
  - `Weekday` as names.
  - Duration display.
  - Total `in_zone` and `z.at`.
- One program (11, stopwatch) scored 5 on every axis.

## 1. Programs and grades

| # | Program | Designs mixed | O | D | C | S | X | K |
|---|---|---|---|---|---|---|---|---|
| 01 | Backup: changed files, progress, Ctrl-C | safety, parallel, units, fmt | 4 | 4 | 4 | 5 | 3 | 3 |
| 02 | Chat client: UI, TCP, timestamps | ui, parallel, time | 3 | 3 | 4 | 3 | 3 | 3 |
| 03 | Habit tracker: streaks, calendar, table | time, ui, fmt | 4 | 4 | 4 | 5 | 4 | 4 |
| 04 | Physics sandbox: gravity slider in m/s² | ui, units, parallel | 4 | 5 | 4 | 5 | 4 | 3 |
| 05 | CSV to monthly report | fmt, time, parallel, safety | 4 | 4 | 4 | 4 | 4 | 3 |
| 06 | Token-bucket rate limiter | parallel, time, units | 4 | 4 | 4 | 5 | 4 | 3 |
| 07 | Job runner across time zones | time, parallel | 5 | 4 | 5 | 4 | 4 | 4 |
| 08 | Settings with tabs and keybindings, saved | ui, safety, fmt | 5 | 4 | 4 | 5 | 4 | 4 |
| 09 | Parallel image resizer | parallel, safety, units | 4 | 4 | 4 | 3 | 4 | 4 |
| 10 | Recipe scaler: cups, grams, °F | units, fmt, safety | 4 | 3 | 4 | 5 | 2 | 4 |
| 11 | Stopwatch with laps | time, ui, fmt | 5 | 5 | 5 | 5 | 5 | 5 |
| 12 | Downloader: retries, backoff, timeout | parallel, safety, time | 5 | 4 | 4 | 5 | 4 | 4 |
| 13 | Password vault CLI | safety, time | 4 | 4 | 4 | 3 | 3 | 4 |
| 14 | Log tailer with filtering | time, safety, fmt | 4 | 4 | 4 | 4 | 3 | 4 |
| 15 | Multiplayer lobby with countdown | parallel, time, fmt | 4 | 4 | 4 | 5 | 5 | 4 |
| 16 | Signal pipeline with tolerances | safety, units, parallel, fmt | 5 | 5 | 4 | 5 | 4 | 4 |
| 17 | Kitchen timers with alarms | ui, audio, parallel, time | 4 | 4 | 4 | 5 | 4 | 2 |

Averages: O 4.2, D 4.1, C 4.2, S 4.5, X 3.8, K 3.6. **Consistency is the weakest axis,** as expected when four designs are revised in parallel.

Comparison in one line each:
- **Python:** wins on missing pieces: `shutil.copytree`, `getpass`, `platformdirs`, `follow` recipes, `pint` parsing, `dateutil.rrule`. Dewy wins on everything checked.
- **Go:** `ticker.Stop`/`timer.Stop`/`ctx` give one stop vocabulary, and `time.ParseDuration` exists. Dewy's `select` is better typed.
- **Rust:** `JoinHandle.abort`/`is_finished` vs Dewy's three spellings. Rust is far noisier for the same programs.
- **TypeScript:** `toLocaleTimeString` formats local time, where Dewy's `fmt'hour:minute'` on an `Instant` formats UTC.
- **Swift:** `Measurement` and `MeasurementFormatter` give "⅓ cup", while Dewy prints `0.(3)cup_us`. Swift's `Task.cancel` sits beside `AVAudioPlayer.stop`, the same split as Dewy's.

## 2. Each score under 5: line, reason, fix

Fixes refer to the catalogue in §3.

**01 backup**
- O4 `01:14`, `01:30`: `f.relative_to(src)` has no stated type, so I can't tell whether joining it to `dst` needs `confine`. → F1.
- D4/C4 `01:39`: to cap one comprehension, the tag goes in a wrapping block. Inside the body, where you'd first put it, it silently governs nothing. → F33.
- C4 `01:16–17`: `copy_to` now gives a `Path`, so progress re-stats the file. → F2.
- X3 `01:35`, `01:42`: sizes are `int64`, so `total_bytes as MB` is an error, while `$program.max_memory = 512MiB` is a quantity. → F3. Also F1 and F2.
- K3: F3 (units vs files) and F33 (the scope of `$parallel` vs `$program`).

**02 chat**
- O3/D3/X3 `02:27–30`: there's nowhere to put `tasks` in a frame-driven program. `update` and `draw` run after `main` returns, so the group has ended. `run_frames` is invented. → F6.
- C4/D3 `02:35–40`: draining a channel per frame is a 6-line `loop`/`match`/`break` that lumps `Empty`, `Closed`, `Busy` and `Canceled` together. → F7.
- C4 `02:50`: `try_send(...)` needs `;`, the same noise as before `$discardable_result`. → F8.
- S3 `02:14`: `fmt'hour:minute'(m.at)` on an `Instant` prints UTC, with no warning. Everyone outside UTC sees the wrong time. → F5.
- K3: F6 (UI × parallel), F8.

**03 habits**
- O4 `03:49`: a checkbox for "today is in `h.days`" has no place to bind. → F11.
- D4/K4 `03:56`: `choice("Rest day" @rest)` lists friday, monday, saturday… because `members` is in text order. → F13.
- C4/X4 `03:27`: `Range<Date>` can't be looped, so I build 35 days by index. → F9.
- C4 `03:37`: the per-column `match` for sort keys. This is the floor ui-strings already states; accepted.

**04 physics sandbox**
- O4/C4/X4/K3 `04:18`, `04:30`: `update(dt:float64)` hands a unit-aware program unitless seconds, so it writes `dt * 1s` by hand. ui-strings deferred this. → F15.
- K3 `04:39`: `plot(low= high=)` and `slider(@g low high)` take two numbers, while `random([lo..hi))` takes a range. → F17.
- X4 `04:26`: no ring buffer. This is a collections item outside these four designs, so no fix here.

**05 CSV report**
- O4/S4/K3 `05:15`: `rational(text)` gives `none`, so the reason is lost. `date(text pattern)` gives `ParseError`. → F18.
- D4 `05:29`: no month bucket for a `Date`. `date(d.year d.month 1)` works but is hard to find. → F20.
- C4 `05:28`: the idiom is "build once in a `const`", but a computed width can't be `const`. The docs should show `let pad = fmt'<{w}'`. A doc fix.
- X4: currency is the time design's stated floor; accepted.

**06 rate limiter**
- O4/K3 `06:6`: the type of `now`, a monotonic reading, has no name. parallel-v4 calls `now + 1s` an `Instant`, which is the wall-clock type. → F21.
- C4/X4 `06:17`: `(1 - tokens)/rate` is `rational*Time`, and `sleep` takes only a `Duration`. → F22.
- D4: finding `mutex` and `@(b.lock)` took reading two documents. No fix proposed.

**07 scheduler**
- D4/S4/X4 `07:34–36`: there's no `sleep_until(Instant)`. `sleep(due - now.nominal)` drifts after a suspend or a clock step. → F24.
- K4: F21 again. `Instant` names both clocks.
- X4: a recurrence object, the time design's floor; accepted.

**08 settings**
- D4/X4 `08:21`: no per-user config folder. → F25.
- C4/K4 `08:25`, `08:54`: `input.save(...) or_throw` and `play(tone(...))` as statements need `;`, because neither is on safety's `$discardable_result` list. ui-strings' own D11 example has the same problem. → F8.

**09 resizer**
- O4 `09:11`: it isn't stated that `f.stem` of a `glob` result is a `FileName`. → F26.
- D4/C4 `09:19`: there's no glob alternation. `*.{jpg,png}` collides with interpolation braces. → F27.
- S3 `09:30`: after Ctrl-C, every file not yet started is reported "skipped: Canceled". Then the summary prints and the exit status is 0. With `?? void` it would even be silent. → F4.
- X4/K4 `09:33`: F3.

**10 recipe**
- D3/X2 `10:14`: no function reads `"250g"` into a quantity, although `field(@mass)` has such a reader inside. → F28.
- O4/X2 `10:20`: prints `0.(3)cup_us`. → F29.
- X2 `10:27`: no `tbsp_us` or `tsp_us`. → F30.
- K4: F28 (the UI can read quantities, the text API can't).
- Good: scaling `oven` is a compile error, because a temperature reading is a point. No other language catches it.

**12 downloader**
- D4/X4 `12:21`: can `random([0ms..250ms))` take a range of durations? → F32.
- C4/K4 `12:33`: F33.
- X4: no HTTP client, as both revisers say.

**13 vault**
- S3/X3 `13:16`, `13:20`: `to_json` of a `secret<string>` field is unspecified. It either leaks or writes `<redacted>`, which destroys the vault. → F34.
- S3 `13:21`: `write_bytes`, then `set_permissions(0o600)`, leaves a window where the file has default permissions. → F35.
- S3/K4 `13:26`: no hidden console input, while the UI has `field(hidden=true)`. → F36.
- X3 `13:10`: F25.

**14 tailer**
- D4/X3 `14:11`: there's no `duration(text)`, so `--since 15minute` can't be read. That breaks the units design's own promise that printed text is valid Dewy. → F28.
- C4/X3 `14:18–21`: following a growing file means `read_at` polling by hand, and lines split across chunks. → F38.
- O4/S4 `14:27`: `hm(bucket)` would print UTC. → F5.

**15 lobby**
- O4 `15:20`: without `writer.cancel`, the client task hangs. The body ends, and the group waits forever on a writer looping over `out`. → F42.
- D4/C4 `15:30–33`: arms like `[event:[join:string]]` match a union inside a named wait. They work, but read heavily. Doc idiom: `[event:e] => match e {…}`.
- K4: `ticker` gives an `Instant` (F21).

**16 science**
- C4 `16:15–20`: unzipping rows into two arrays. Language-level, outside these four designs.
- X4/K4 `16:41`: `is_close(... abs=0.0)` defaults to a dimensionless zero, so a quantity needs `abs=` every time. → F45.
- X4 `16:45`: how `to_json` writes a quantity is unspecified. → F46.

**17 kitchen timers**
- K2 `17:30`, `17:38`: `Playing.stop`/`.playing`, `Task.cancel`/`.running`, a `Ticker` you stop by dropping it, and `Child.wait`. Four handles that start something, each with its own vocabulary. → F47.
- O4/K2 `17:5`: F21. The type of `now + 9minute` has no name.
- D4/X4 `17:16`: what does `field(@new_length)` accept: `9minute`, `9:00`, `9m`? → F28.
- C4 `17:30–31`: `;` after `remove(i)`. A language rule, accepted.

Markers F10, F12, F14, F16, F19, F23, F31, F39–F41, F43 and F44 turned out to be non-issues or outside these four designs.

## 3. Catalogue of findings and fixes

**Must-fix**

- **F4. `??`, `?? void` and `partition_failures` swallow `Canceled`.**
  - Decided: `??` defaults any exception, and `Canceled` is one. LANGUAGE says cancellation is level-triggered: every later wait returns `Canceled`.
  - v4's own `sleep(1ms) ?? void` and LANGUAGE's `input_int("n? ") ?? 0` swallow Ctrl-C.
  - A receive loop with `?? ""` spins at 100% CPU after the "stopping" notice. The user presses again, and cleanup is skipped. That defeats v4 §5.
  - **Fix:** `Canceled` passes through `??`, `?? void` and `partition_failures` unless named: `??<Canceled>`, or `match`. They forward it as if `or_throw<Canceled>` were written. Python's `except Exception` skips `KeyboardInterrupt` for the same reason, and Trio's `Cancelled` is never caught by accident.
  - This also shortens v4's `select` idiom. Owner: parallel, since the `??` semantics are decided and this narrows them.
- **F5. `fmt'hour:minute'(instant)` formats UTC with no warning** (time §2.1: "an `Instant` formats in UTC").
  - **Fix:** a pattern with time-of-day fields and no `offset` or `zone` doesn't accept an `Instant`. It's a compile error with three fix-its:
    - `t.local`, in `$program.time_zone`;
    - `t.in_zone(z)`;
    - add `offset`.
  - This makes `$time.no_dropped_zone`'s check the default for `Instant` only. A `ZonedDateTime` already carries its zone, so it keeps today's rule. Date-only patterns on an `Instant` have the same problem, since the date flips at midnight UTC, and get the same rule.
- **F6. A UI or game program has no scope for background tasks.**
  - `tasks(body)` blocks, and `main` must return before `update`/`draw` run.
  - **Fix (parallel × ui):** `main` may take the program's group: `main = (app:Tasks) => { app.spawn(@pump_in(sock)) }`. Its tasks live until the window closes, then they're canceled and joined before exit.
  - This is ordinary structure (the group's lifetime is the program's), needs no new syntax, and covers non-game servers too.
- **F8. `$discardable_result` is a hand-kept list, and it's already incomplete.**
  - Missing: `play`, `Controls.save`, `rebind`, `start_process`, `image.save`, `copy_to`'s siblings. ui-strings' own D11/D11b examples fail as written.
  - It also doesn't reach wrappers. `log = (m) => file.append_text(m) or_throw` infers a `Path` result, so every `log("x")` needs `;` (F48).
  - **Fix:**
    1. State the rule, not a list: a call that starts something (gives a handle) or writes (gives back its path) is marked, and the library lint enforces the category.
    2. A function whose every result path ends in a marked call is itself discardable, inferred.
    3. Also mark `try_send`, whose `Unsent` is the payload you chose to drop. `try_send` is borderline, so recommend it to the owner with that question.
- **F18. Six failure shapes for "this text didn't read":**
  - `ParseError` (time readers);
  - `ShapeError` (`Action(s)`, `FileName(s)`, `NumberPattern(s)`);
  - `TextError` (`from_json`);
  - a specific kind (`to_int`);
  - `none` (`to_float`, `rational(text)`);
  - `EndOfInput`, which is fine, being a different event.

  `??<ParseError>` doesn't do what a reader expects, and `field(read=)` has to list `ParseError|ShapeError`.
  - **Fix:** one parent, `ParseError` (`message`, with optional `line`/`column`). `ShapeError`, `TextError` and `to_int`'s kinds become its children. `to_float` and `rational(text)` give `ParseError` ("`nan` needs `allow_nonfinite=true`") instead of `none`.
  - ui-strings' objection, that shapes also guard quantities, is met by the children: `ShapeError` stays the name for those.
- **F21. The monotonic reading has no type name, and v4 calls it `Instant`.**
  - v4 §7 says `timeout:Duration | Instant`, "a monotonic deadline (`now + 1s`)", and that `ticker` delivers an `Instant`. LANGUAGE says `now` is a monotonic sample and `.nominal` is the `Instant`.
  - **Fix:** time names the reading type (candidate `Reading`, for the cold read). `timeout:` and `ticker` use it, and `Instant` is only ever the wall-clock axis.
- **F28 / F37. No text readers for quantities or durations,** though `field` has both inside, and the units design promises printed text is valid Dewy.
  - **Fix:** `duration(text)` and `quantity<D>(text)` (or `Mass(text)` through the dimension name), each giving `T | ParseError`. They read exactly what printing writes (`90minute`, `1.65s`, `250g`, `36.(1)°C`), with a fix-it for `15m` ("minutes is `15minute`; `m` is metres"). `field` uses the same readers.
- **F47. Handles to running things use four vocabularies.**
  - **Fix:** one handle protocol for anything started that can be stopped (`Task`, `Playing`, `Ticker`, `Child`):
    - `.stop` asks it to end, returns at once, and can be repeated;
    - `.wait` waits until it has ended and gives `void | Canceled`;
    - `.running` gives a `bool`.

    Extras stay per type: `Playing.pause/resume/position`, and `Child.status` after it ends.
  - `.stop` over `.cancel`, because:
    - "cancel the sound" reads wrong;
    - Go uses `Stop` for tickers and timers;
    - `Canceled` stays the outcome's name.
  - `Ticker` gains `.stop`, so dropping isn't the only way. v4 13's `music.cancel` and ui's `p.stop` then mean the same thing, as they should, since they're the same job.
- **F49. ui-strings still teaches TR35** (`fmt'EEEE d MMMM'`, §2.5 and the D11 example) and names `DateFormat`/`LocalPattern`. The time design makes TR35 a compile error and names `DatePattern`/`DateTimePattern`.
  - **Fix:** use the word patterns and the time design's kind names in ui-strings §2.5, §2.9 and D11.
- **F15. Game `dt` is `float64`.** In a units-first language, the physics example converts `dt * 1s` by hand.
  - **Fix:** `update(dt:Duration)`, or `float64*s` if float speed matters. ui-strings deferred this because "D28 doesn't own the hooks". Someone must own it before D28 goes to the owner.

**Should-fix**

- **F1.** `f.relative_to(base)` on a `SafePath` under `base` gives a relative path whose parts are each a `FileName`. That joins to any base with no confinement. Mirroring a tree (backup, sync, deploy) is the most common file-tool shape.
- **F2.** `copy_to(target progress=@f)` with `f:(done:Information):>void`, or a byte-counting stream copy. The `Path` result stays.
- **F3.** `p.size` gives an exact `Information` quantity (`int64*B`), so `size as MB`, `fmt'.1f'(size as MiB)` and download rates in `MB/s` work. It matches `$program.max_memory = 512MiB` and the units design's own `MB`/`MiB` work.
- **F7.** `loop m in inbox.ready` visits what is buffered now, without waiting, and ends on `Empty`. `Busy` retries inside. This is for frame loops and polling.
- **F9.** A discrete `Range` iterates: `loop d in [start..end)` steps a `Date` by `1day`, using the same discreteness test the time design already defines for `is_empty`. `step=` takes other steps.
- **F11.** `checkbox(title checked=expr)` with `changed(id)` handles derived state that has no place.
- **F13.** time exports `weekdays`, an ordered array starting Monday, and the `choice` docs point to it for `Weekday` and other ordered unions.
- **F17.** UI intervals take ranges, as D15d says for anything taking an interval: `slider("Volume" @v [0.0..1.0] step=0.05)` and `plot(values range=[0.0..1.0])`.
- **F20.** `d.floor(1month)`, `d.floor(1week)` and `d.floor(1year)` on `Date`, mirroring `t.floor(tick)` on instants.
- **F22.** `sleep`, `within`, `timeout=` and `ticker` accept any time quantity and round up to the clock tick, since a wait is never exact anyway.
- **F24.** `sleep(until=t)` for a wall-clock `Instant`, which wakes correctly across a suspend or a clock step. Go and Python both lack it, and Dewy shouldn't.
- **F25.** Per-user folders: `config_dir(app)`, `data_dir(app)`, `cache_dir(app)`, `home_dir`, `temp_dir`. Each gives a `Path` and is a base for confinement.
- **F26.** `.name` and `.stem` of a `SafePath` are `FileName`s. State it.
- **F27.** Glob alternation without braces, e.g. `glob"*.(jpg|png)"`, or `glob["*.jpg" "*.png"]`. A computed glob pattern gives plain `Path`s.
- **F29.** End-user unit text. `label(q)` (ui's existing `label`) gives "⅓ cup", "1 ⅓ cups" and "9 minutes". A fraction style such as `fmt'/8'` rounds to the nearest eighth. Programmer printing stays as Dewy text.
- **F30.** Add `tbsp_us`, `tsp_us`, `tbsp` and `tsp` (metric 15 mL and 5 mL), and `stick_butter`.
- **F32.** `random(range)` over any type with a sampler: integers, floats, quantities, `Duration`, `Date`.
- **F33.** A `$parallel.*` line that opens a `parallel` body applies to that construct. Today it would apply to nothing inside it, silently. Otherwise it should be an error pointing to the wrap form.
- **F34.** `to_json` of a type containing `secret` fields is a compile error unless `secrets='reveal'`, and `from_json` fills `secret` fields.
- **F35.** `write_bytes(data permissions=0o600)` creates with that mode, beside the atomic rename.
- **F36.** `input(prompt hidden=true)` gives `secret<string>`, the same word as `field(hidden=)`.
- **F38.** `loop line in p.follow` tails a growing file, whole lines only, and is a cancellation point.
- **F42.** `group.cancel` belongs in v4's `Tasks` API. A body that ends while a sibling waits on a channel no one else holds should warn ("the group waits for `writer`, which waits on `out`").
- **F45.** `is_close`'s `abs=` defaults to the operand type's zero.
- **F46.** `to_json` of a quantity writes its printed text (`"0.42mV"`), and `from_json` reads it back through F28.
- **F50.** Teach `value_text=fmt'.0%'`, not `(v:float64) => '{fmt'.0%'v}'`. `fmt` already returns the function. `choice(labels=)` works the same way.
- **F52.** A duration's first field is unpadded, like `hour12`: `fmt'minute:second'(65s)` is `1:05`, as timers show it. Clock times keep `09:05`.

## 4. Seams between the designs, ranked by harm

1. **`Canceled` × `??` (parallel × decided semantics × every safety idiom), F4.** The only seam that gives wrong behavior silently. Every "`?? default` for outside data" idiom the safety design teaches becomes a Ctrl-C bug.
2. **Handles (parallel `Task`, ui `Playing`, parallel `Ticker`, safety `Child`), F47, plus discardability, F8.** The same job (play music in the background, stop it later) is `group.spawn` + `.cancel` in one design and `play` + `.stop` in another. Whether you need `;` after starting it depends on which list the function is on.
3. **Frame callbacks × structured concurrency (ui × parallel), F6; and `dt` × units (ui × units), F15.** The two halves of every game or tool program don't fit together.
4. **Text readers (safety × ui × time × units), F18, F28.** Six failure shapes, and UI readers that the text API doesn't expose.
5. **Two clocks called `Instant` (parallel × time), F21, F22, F24.**
6. **Formatting leftovers (ui × time), F49, F5, F50.** TR35 in the owner-facing D11 text, `Instant` printing UTC, and the lambda-wrapped `fmt`.
7. **Ranges.**
   - UI's `low`/`high` vs `random([lo..hi))`; F17.
   - `Range<Date>` can't be looped; F9.
   - `IntRange` keeps both `.first`/`.last` and `.start`/`.end`. That is acceptable, and `.start`/`.end` everywhere else was consistent in every program.
8. **Sizes as `int64` vs `Information` (safety × units), F3.**
9. **Scope of metatags (parallel), F33.** By contrast, `$program.time_zone` and `$program.max_cores` read as one family. That works.
10. **`strict_`:** consistent across time and safety in every place I met it. The only risk is the cold read (Rust's `strict_add` panics). Keep it.
11. **`hidden=` (ui) vs no hidden console input (safety), F36.** Small, but exactly the "same word for the same idea" test.

Seams checked and found sound:
- `or_throw` before `{` in both designs;
- `rounding=`/`grouping=`/`ties=`, each with one meaning;
- `fmt` patterns choosing the input type, as both designs specify;
- the trailing `;` after a call that returns a useful value, in every case `$discardable_result` covers.

## 5. Per design: ready or not

**parallel-v4: not ready.** Must-fix:
1. F4: `??`, `?? void` and `partition_failures` must forward `Canceled`.
2. F21: `timeout=` and `ticker` use the monotonic reading type, not `Instant`.
3. F6 (with ui): a program-lifetime group for UI, game and server programs.
4. F47: `Task` takes the shared handle verbs.

Should-fix: F7, F22, F33, F42. The block form, D26, `select` typing, `or_throw<E>`, `shielded`, `partition_failures` and the core inventory held up in every program that used them (06, 09, 12, 15).

**safety-round3: not ready.** Must-fix:
1. F8: discardability by stated rule, inferred through wrappers.
2. F18: one reader-failure family; `to_float` and `rational` give `ParseError`.

Should-fix: F1, F2, F3, F25, F26, F27, F32, F34, F35, F36, F38, F45. `FileName` from `list`, `to_file_name`, secure tokens and constant-time `=?` worked first time in 01, 09, 12 and 13.

**time-units-format: closest; not ready.** Must-fix:
1. F5: `Instant` must not format a time of day silently in UTC.
2. F28/F37: `duration(text)` and quantity readers that round-trip printed text.
3. F21: name the reading type.

Should-fix: F9, F13, F20, F24, F29, F30, F46, F52. Word patterns, `Weekday`, Duration display, `z.at`, total `in_zone`, `$program.time_zone` and unit-keeping `fmt` scored 5 wherever they appeared. Programs 07 and 11 were the cleanest of the set.

**ui-strings: not ready.** Must-fix:
1. F49: remove TR35 and the old kind names.
2. F15: `dt` as a time.
3. F6 (with parallel).
4. F8: `play`, `save` and `rebind` discardable, or the examples rewritten.
5. F47: `Playing` takes the shared handle verbs.

Should-fix: F11, F17, F29 (`label` for quantities), F50, and readers shared with F28. Generic `slider` with units, value-binding `choice`, `table`/`Sort`, `committed`, `controls_editor` and `const` subtrees read naturally in 03, 04, 08, 11 and 17.

**Cross-design gate before any of these reaches the owner:** one short shared table of handle verbs, reader errors and time types, signed off by all four revisers, followed by a re-run of programs 02, 09, 10 and 17. Those four broke on seams, not on single designs.
