# Dogfooding time, units, formatting and UI

Programs are in `~/dev/tmp/dogfood-1107/b/`. They were run on master `d0f9714ef` on the desktop with `DISPLAY`, `WAYLAND_DISPLAY` and audio off. UI programs were type-checked (`dewy check`) against the round-1 stub (`ui_clean.dewy`). The `*_t.dewy` files are those programs after `typed.py` adds `<Pick>` to each widget, which works around the G1/G2 gaps. **Stub** means a small local definition of something a design adds. Each stub is marked in the file.

## Programs

| # | File | What it does | Designs | Status |
|---|---|---|---|---|
| 1 | `p01_meeting.dewy` | Weekly 09:00 New York stand-up shown in London and Tokyo across both 2026 DST changes; flags hours outside 08–18 | time, D35 | Compiled and ran (D35 stubbed) |
| 2 | `p02_logs.dewy` | ISO and Apache log stamps, request pairing, durations, slowest and mean | time, D31 | Compiled and ran (stub for `zoned(text pattern)`) |
| 3 | `p03_bench.dewy` | Benchmark (min, median, mean, runs per second) and a lap stopwatch | time | Compiled and ran |
| 4 | `p04_birthdays.dewy` | Ages, next birthdays, days to go, a 29 February friend | time, D29 | Compiled and ran (stub for a date from numbers) |
| 5 | `p05_recurring.dewy` | "Every second Tuesday", both meanings | time v5 §6, D29 | Partly compiled: the by-hand version ran; `recurrence` is paper only |
| 6 | `p06_space.dewy` | Voyager light time, command arrival, leap second, years −584 and +12026, sub-ns carrier | time | Compiled and ran; `time.science` lines are paper only |
| 7 | `p07_insulation.dewy` | House heat loss: R in series, U-factor windows, BTU/h, W, furnace kW | D34, D36 | Compiled and ran (D34 and D36 names stubbed) |
| 8 | `p08_bill.dewy` | Electricity bill: kW × hours → kWh, tiers, demand charge, tax | D36 | Compiled and ran with `days = 30`; the `Date − Date` form panics the compiler (`p08_crash_repro.dewy`) |
| 9 | `p09_student.dewy` | Unit homework: mph, lb, psi, kcal, hp, a falling stone, kinetic energy | units | Compiled and ran (9 missing units stubbed) |
| 10 | `p10_game_menus.dewy` | Pause menu, settings, inventory grid, controls rebinding | D28, D11b | Partly compiled: pause, settings and inventory check clean (`p10_*_t.dewy`); rebinding is paper only |
| 11 | `p11_melody.dewy` | Melody player: a constant tune, a typed tune, progress | D11a | Compiled and ran with `$runtime_checks`; the `Melody` shape lines are paper only |
| 12 | `p12_expenses.dewy` | Desktop expense tracker: form, sortable table, total, delete | D28 | Checked clean (`p12_expenses_t.dewy`) |
| 13 | `p13_report.dewy` | Sales report: aligned columns, thousands separators, %, a computed width | D19e | Compiled and ran (`fmt` stubbed) |
| 14 | `p14_debug_overlay.dewy` | FPS, frame-time graph in a reserved box, tuning sliders | D28 | Checked clean (`p14_debug_overlay_t.dewy`) |
| 15 | `p15_sensors.dewy` | Compact stamps, per-minute buckets, a retry helper taking a function | D30, D31 | Compiled and ran |
| 16 | `p16_billing.dewy` | Billing on the 31st, clamp vs next, a period as a range, proration, a reminder at 09:00 local | D29, D31 | Compiled and ran |

## Scores

O = obvious, D = discoverable, C = concise, S = safe by default, X = complete. 5 is best.

| # | O | D | C | S | X |
|---|---|---|---|---|---|
| 1 meeting | 4 | 4 | 3 | 3 | 3 |
| 2 logs | 3 | 3 | 2 | 4 | 2 |
| 3 bench | 5 | 4 | 3 | 5 | 2 |
| 4 birthdays | 3 | 3 | 3 | 4 | 2 |
| 5 recurring | 2 | 2 | 2 | 2 | 1 |
| 6 space | 4 | 4 | 4 | 3 | 3 |
| 7 insulation | 4 | 4 | 3 | 3 | 4 |
| 8 bill | 4 | 4 | 4 | 3 | 3 |
| 9 student | 4 | 3 | 5 | 4 | 2 |
| 10 menus | 4 | 3 | 3 | 3 | 2 |
| 11 melody | 4 | 4 | 4 | 3 | 2 |
| 12 expenses | 4 | 3 | 3 | 3 | 2 |
| 13 report | 4 | 3 | 4 | 3 | 3 |
| 14 overlay | 5 | 4 | 4 | 5 | 3 |
| 15 sensors | 4 | 3 | 3 | 5 | 3 |
| 16 billing | 4 | 4 | 4 | 3 | 4 |

**What already works well:**
- `now - start`.
- `zoned"…"` literals that fail at compile time.
- `1day` versus `24hour`, with a good error for `age / 1day`.
- `age(born on=…)` and `leap_day=`.
- The reading-versus-difference error on temperatures.
- `{x:,.2f}`, `{share:.1%}` and grapheme-aware padding.
- Picks typed against a union, and `back='resume'`.
- `@volume` sliders, which match Dear ImGui line for line.
- The bare function-type hint (D30).
- The melody error text.

## Friction, program by program

Each item gives the line, why it isn't a 5, and a fix. **(new)** marks a fix that needs a new spelling, which would go to the owner.

### 1. Meeting scheduler
- `slot.nominal.in_zone(p.zone)`: the obvious `slot.in_zone(z)` is missing. **Fix:** D35, as recommended.
- `at.in_zone(p.zone)` gives `ZonedDateTime | OutsideCoverage` on every call. That forced this inside a lambda:
  ```
  let there = at.in_zone(p.zone)
  there is? ZonedDateTime and working(there)
  ```
  - Coverage is only a real question far outside the pack's years, and TZif already has a footer rule for every later year.
  - **Fix:** make `in_zone` total, using the footer rule forward and local mean time back. Keep `OutsideCoverage` only under a `$time.require_*` tag.
- `local"2026-11-02T00:00".in_zone(ny) + 9hour` (probe): on 1 November this gives **08:00**. The design is right that `hour` is elapsed time. But "midnight plus nine hours" is the natural way to build a time of day, and nothing points away from it.
  - **Fix:** add `zoned.at(time_of_day"09:00")`, as `Date.at` already exists, and teach it in the zoned section.
  - Temporal has `withPlainTime` and jiff has `with().hour(9)`.
- `"{slot.format("EEE d MMM")}"`: see the D31 notes on pattern letters below.

### 2. Log timestamps
- `instant(text) or_throw` inside `:>Instant|ParseError` is a compile error. The failure is `ParseError | InvalidFields | OffGrid | OutsideCoverage`, so the obvious signature is wrong, and the fix-it asks for a five-member union.
  - **Fix:** make the four members children of one family **(new name, for example `TimeError`)**, or make them children of `ParseError` when the text came from parsing.
- No `zoned(text pattern)`: Apache's `07/Nov/2026:05:15:31 -0500` needed a 13-line hand-written offset parser.
  - `XXX` exists for writing only, and `XX`/`Z` are not letters at all.
  - **Fix:** a pattern overload of `zoned` that reads `XX`, `XXX` and `VV`, giving `ZonedDateTime | ParseError`.
- `printl"mean: {total / took.length}"` printed `5771/3ms`.
  - `Duration / int` gives an exact quantity, and an integer-origin fraction prints as `n/d`.
  - **Fix:** a time quantity always prints as a decimal, using the repeating rule (`1923.(6)ms`). Also make `mean(times)` work on durations. Today it fails with an error from `lib/std/nd.jo` that suggests the Jo syntax `if x is int:`.
- `1650ms`, `91750ms`: see the Duration display item under 3.
- Python: `datetime.strptime(s, "%d/%b/%Y:%H:%M:%S %z")` does this in one line.

### 3. Benchmark and stopwatch
- **Duration display, a must-fix.** `min 7251832ns median 7670403ns`, `load 1466340ns`, and Voyager's `1551762261s`.
  - The rule "largest unit that keeps a whole count" makes every measured time print in nanoseconds.
  - Go and Rust print `7.251832ms`, which is exact too.
  - **Fix:** an exact decimal in the largest unit not above the value, for example `7.251832ms`, `1.65s` and `91.75s`. Above an hour, a composite such as `431045h4m21s` (Go) or `17960d 5h04m` is optional.
  - This is a display rule only. The value is unchanged.
- `let mean = total // runs ?? 0s` and `let per_s = 1s / mean ?? 0`. With `runs:int64<(>? 0)>`, `//` still gives `Duration | OutOfRange`. Dividing by a positive count can't overflow.
  - **Fix:** use the refinement, so a proven-nonzero divisor gives a plain `Duration`.
- `{elapsed / 1ms as float64:.2f} ms`: acceptable, but every stopwatch writes it.
  - **Fix:** `{elapsed as ms:.2f}`, through the same `as unit` that other quantities have.
- `sleep(500ms)` must be handled (`Canceled`), so a plain `play_tune(...)` call needed `or_throw` too (program 11). This is fair under D4. A script's first `sleep` still costs a compile error.
- Python: `time.perf_counter()` plus `timeit`. A `bench(name runs f)` helper with min, median and mean would be **nice to have**.

### 4. Birthdays
- **No date from numbers.** `date(2026 3 15)` is the first thing anyone types. The stub built text and parsed it.
  - **Fix:** `date(year month day)` giving `Date | InvalidDate`, folded for constants. `civil.date_of` already exists but isn't exported.
- `date_of(y m d) ?? (date_of(y 3 1) or_throw)`: the obvious `a ?? b or_throw` is a type error, because `??` needs a plain value on the right.
  - **Fix:** let a fallible right side give its own union, so `a ?? b ?? c` chains as it does in JavaScript.
- Next birthday, including the 29 February rule, took 4 lines and needed the leap-day convention by hand.
  - **Fix:** `born.next_anniversary(after=today leap_day=…)` **(new)**, to match `age`. Temporal has `PlainMonthDay`.
- `(next - on).total_days` and `(next - on) / 1day` are two ways to do one thing. Both are documented. That is fine, but the docs should name one first.

### 5. "Every second Tuesday"
- **`weekday` 0 = Monday (D29), a must-fix.** `date"2026-11-10".weekday =? 2` prints `false` for a Tuesday, silently.
  - Python's `weekday()` is 0 = Monday, but its `isoweekday()`, Temporal, ISO and jiff are 1 = Monday, and JavaScript and Swift are 0 or 1 = Sunday. Every reader brings a different guess.
  - **Fix:** `d.weekday` gives a union `'monday' | … | 'sunday'`, so `=? 2` is a compile error and `=? 'tuesday'` reads itself. Keep a number only as `d.iso_weekday` (1–7), if anyone needs one. Both are **(new)**.
  - `weekday_name` then becomes `"{d.weekday}"` plus capitalizing. Both names should go through the cold test.
- **No recurrence.** v5 §6 has `recurrence(… every=2week)`, but no spelling for "the nth weekday of the month". The by-hand version needed `(TUESDAY - first.weekday + 7) % 7`.
  - **Fix:** finish recurrence, with selectors such as `on=[2 'tuesday']` or `nth=2 weekday='tuesday'` **(new)**.
  - Python's `rrule(MONTHLY, byweekday=TU(2))` and jiff's `nth_weekday(2, Tuesday)` are the bar.
  - Also add `d.next('tuesday')`.
- The phrase itself is ambiguous. A recurrence API that has both `every=2week` and the nth-weekday form makes the writer choose.

### 6. Spacecraft
- `quantize(light rounding='nearest_even')` reported a loss of `31768077/67108864ns`, the float's binary fraction.
  - **Fix:** a loss from a float input prints as a float (`0.473ns`).
- `date"12026-01-01"` is rejected; `date"+12026-01-01"` works.
  - **Fix:** the error should say "years past 9999 take a sign: `+12026-01-01`".
- `date"-0584-05-28"` is the proleptic Gregorian 28 May. The eclipse of Thales is dated 28 May **Julian**, which is 22 May Gregorian. Astronomers and historians write Julian dates before 1582, so this is a silent wrong answer.
  - **Fix:** a warning on a `date"…"` before 1582-10-15 with no `$calendar` in scope, naming `Julian`. Then build `Julian`.
- `time.science` (Julian Date, TDB, mission elapsed time) is paper only. The core instants and durations handled 1977–2026 to the nanosecond and the leap second exactly.

### 7. Insulation
- **D34's own example doesn't compile as written.** `rise = 70°F - 30°F` is an exact `rational*Temperature`, and a parameter annotated `float64*…` rejects it: "argument 'rise' expects float64 * Temperature, found rational * Temperature".
  - A `let` with the same annotation rounds once, so arguments should do the same.
  - **Fix:** an exact quantity passed to a float parameter rounds once, as the annotation does on a `let`. Without that, users drop the annotation, which happens to keep the reading check but loses the documentation.
- `let wall_r:float64*ThermalResistance = …` is long, but D36's names fix the worst of it (`Area`, `Power`). Add `ThermalResistance` to the D36 list so all the names live together.
- `Assembly["windows" 120ft^2 1/window_u]` was a "may panic" division error until `let` became `const`. A `let` holding a nonzero literal that is never reassigned should count as known nonzero.
- `rise as °C` prints `325/9°C`.
  - **Fix:** the decimal-with-repeat rule for temperatures, `36.(1)°C`.

### 8. Electricity bill
- `printl(1392kWh)` prints `5011200kJ`, and `3.0kWh` prints `10800kJ`. Pint and Swift's `Measurement` keep the unit the value was written in.
  - **Fix:** add `kWh` and `MWh` to the energy chooser, or let a literal's written unit act as an implicit `as` until arithmetic changes the dimension.
- Money is a plain `rational`: `const TIER_1 = 0.12/kWh`. It works and is exact. Currency safety (`USD` and `EUR` as dimensions) is **nice to have**.
- **Compiler panic:** with `days = (date"2026-12-01" - date"2026-11-01").total_days`, the checker panics with "the dictionary has no entry for this key" (`dewy_direct.jo:153`, `decimal_check_body`). `days = 30` works.

### 9. Student conversions
- **Missing units:** `lb`, `oz`, `gallon`, `mph`, `psi`, `kPa`, `atm`, `bar`, `cal`, `kcal`, `hp`, `knot`, `acre`, `hectare`, `eV`, `Wh`, `mAh`. Each was stubbed. Pint has all of them, and a student hits this in the first exercise.
  - **Fix:** add them, with US and imperial gallons named apart (`gallon_us`).
- `{t:.2f}` printed `3.03` and `{v:.1f}` printed `29.7`, dropping the unit. Pint's `f"{q:.2f~P}"` keeps it.
  - **Fix:** a precision keeps the unit (`3.03s`), and `{t/s:.2f}` gives the bare number.
- `ke` printed `125/216MJ`: the same fraction display issue as above.
- `printl"{200hp as kW:.0f}"` without importing `kW` says "unknown type 'kW'". After `printl(1kWh)` it says "unknown name 'kWh' (a unit of the library: `from units import kWh`…)".
  - **Fix:** use the second message in both places.

### 10. Game menus (D28, D11b)
- **`choice("Difficulty" DIFFICULTIES @difficulty_index)` takes an index into an array of strings**, while the game already has `Difficulty:type = 'easy'|'normal'|'hard'`. This is the `window`-returns-`void` slip: the widget hands back the wrong thing.
  - Program 12 then needed `CATEGORIES.get(category_index) ?? "other"`, because the index can't be proven in range.
  - **Fix:** `choice("Difficulty" @difficulty)`, with options from `members(Difficulty)` and an optional `labels=`. egui's `selectable_value` and SwiftUI's `Picker` over a `CaseIterable` enum do this.
- **`slider` takes only `float64`.** FOV is a whole number, and `{fov as int64}` was a compile error ("cannot prove `fov` is a number within the int64 range").
  - **Fix:** a generic numeric slider for `int64`, floats and quantities (`@mouse_speed` in `°/s`).
  - Also have the slider show its value, `slider("FOV" @fov 60 120 suffix="°")`, as ImGui's format string and egui's `.suffix` do. Today a `text("{fov:.0f}°")` has to sit beside it.
- `let old_full = fullscreen … if fullscreen not=? old_full set_fullscreen(fullscreen)`: reacting to a change takes two extra lines.
  - **Fix:** `changed("Full screen")` **(new)**, next to `clicked`.
- **Rebinding has no API in D11b.**
  - The program needed `input_pressed`, `input_name`, `save_bindings`, `default_controls` and `[pressed input.binds[a][1..]...]`. None is in the proposal, though most exist in `lib/game/controls.jo`.
  - **Safety:** the Enter or A press that chooses "rebind Jump" is down in the same frame, so a naive capture binds Jump to Enter. The old library guards this with `__ctl_done_frame`; the proposal doesn't mention it.
  - **Fix:** name the companions before approving `Controls<A>` as the replacement:
    - `ui_controls(@input)` (proposed in passing);
    - `input.rebind(action slot to)`, giving any conflicting action;
    - `save_controls` and `load_controls`, giving unknown names;
    - `input_name(b)`;
    - a rule that the capture skips the confirming press.
- `text(a.capitalize …)`: union members have no display names (`'move_left'` → "Move left").
  - **Fix:** a library `label(x)` that turns `_` into spaces and capitalizes, overridable.
- Four pick unions with an `if … else if` chain each are fine, and `match picked` reads better. In a `match`, `'on' =>` must be `<'on'> =>`, and an assignment arm needs braces. The errors say so, but a UI dispatch hits both on its first try.
- `update = (dt:float64)`: game time is a bare float while the rest of Dewy has `Duration` and `s`. **Nice to have:** `dt:float64*Time`, so `1/dt as Hz` and `dt as ms` work in program 14.

### 11. Melody player (D11a)
- Today `melody(notes bpm)` with runtime text is a "may panic" compile error, and with `$runtime_checks` the typed `C4 Q9` panics. D11a's `if typed is? Melody` / `Melody(typed) ?? …` fixes exactly this, and the error text is the best in this review.
- **`play(...)` gives an `int` id, not a handle,** the same class as `window`. `is_playing(id)` stayed true forever with no audio device (`4.5 / 3.0 s`), so the loop needed a time bound.
  - **Fix:** `play` gives `Playing` **(new)** with `.stop`, `.is_playing`, `.wait` and `.position:Duration`. With no device, playback ends on schedule.
- `duration(tune)` is a float of seconds, and `tone(440.0 0.5)` takes bare floats for hertz and seconds.
  - **Fix:** `Duration` and `Hz`: `tone(440Hz 500ms)`.
- The melody string has no note lengths beyond `-` holds, so a dotted rhythm can't be written. **Nice to have:** `C4/8`-style lengths inside the shape.

### 12. Expense tracker (D28)
- There is no typed field. A date and an amount go through `text_field` and then a hand parse.
  - `rational(text)` gives `none` on failure while `date(text)` gives a `ParseError`: two failure shapes for one job.
  - **Fix:** `field("Amount" @amount)` **(new)** for any type with a parser, which shows the parse or shape error under the field (D11a shapes make this general). Also make `rational(text)` give a `ParseError`.
- Right alignment: `text("{e.amount:>10,.2f}")` pads with spaces, which don't line up in a proportional font.
  - **Fix:** `text(… align='right')` inside a fixed-width cell, plus a small `table(columns rows sort=@sort_by)` helper. ImGui's `BeginTable` has sort specs, and SwiftUI's `Table` has `sortOrder`.
- Sorting descending is the `-e.amount` trick, which is impossible for strings.
  - **Fix:** `sorted(key=… descending=true)`.
- `c:Column => …` in `match` doesn't narrow, and `picked is? Column` is rejected as "never a 'on' | …" (compiler bug). Four literal arms replaced one.
- `expenses.remove_at(i)`: the error says "use `remove(i)`", and `remove(i)` then says "an array removes by position with pop". The two hints contradict each other.

### 13. Report table (D19e)
- **Rec (a) loses compile-time checking of format specs.**
  - `{x:.2f}` sees the spec and the value's type at one site.
  - `fmt'.2f'` must return a function before the value's type is known, so a bad spec, or `.2f` applied to a string, becomes a run-time failure.
  - The stub needed `$runtime_checks`: "calling `format` may panic … numeric flags and precision need a number".
  - Making `fmt` check would need either compiler magic or an inferred generic closure, and the language has neither.
  - **Fix:** take (b). `{x:.2f}` stays the checked everyday form, and `fmt` serves computed specs (`fmt'<{w}'`), with its spec as a shaped string (D11a) so at least its grammar is checked.
- `sales.map(...).max` and `.sum` over a constant 4-element array each needed a proof: nonempty, and fits `int64`.
  - **Fix:** `map` keeps the length fact, and add a `T | none` form for maxima of possibly empty arrays (`xs.max ?? 0`) **(new if a new name)**.

### 14. Debug overlay (D28)
- Matches ImGui's `SliderFloat` and `Checkbox` one for one, which is very good.
- The frame graph took a reserved `box`, `rect_of`, `if r is? Rect2` and a draw loop.
  - **Fix:** `plot(values width height)` **(new)**, like ImGui's `PlotLines`. `lib/game/chart.jo` already exists.
- `frame_ms.pop(0)` on a 120-entry history is O(n). **Nice to have:** a fixed ring.

### 15. Sensors (D30, D31)
- `read:(():>float64|SensorError)`: the grouped function type reads well. D30's bare form was right to stay off.
- `let [minute _] = quantize(r.at as Instant rounding='floor' tick=1minute) or_throw`: three pieces of ceremony for "floor to the minute". A floor can't land off a constant grid.
  - **Fix:** `t.floor(1minute)`, `t.round(1s)` and `t.ceil(…)` **(new)**, giving the value. Keep `quantize` for when the loss matters (Temporal `.round`, jiff `.round`).
- **`Name<option=N>` leaks.**
  - `let x:int64 = small` reports "found OutOfRange | Instant_width_64".
  - `Instant<width=32>` reports "unknown type 'Instant_width_32'", a name the user never wrote.
  - **Fix:** messages and hover print `Instant<width=64>`, and an unknown option says "Instant takes width=64 or width=128".
- `per_minute[key] = (per_minute.get(key) ?? []) + [r.celsius]` gave a good error ("`+` does not join arrays"). Grouping still takes a spread line, where Python has `defaultdict(list)`; `group_by` exists and should be shown with dictionaries.

### 16. Billing (D29, D31)
- **Clamp drift:** `d = d.add(1month overflow='clamp')` in a loop goes 31 Jan → 28 Feb → 28 Mar → 28 Apr. The natural loop is the wrong one.
  - **Fix:** document `start.add(i*1month …)` as the pattern, and have recurrence's `anchor='month_end'`.
  - A lint for "reassigning a clamped month step in a loop" is **nice to have**.
- **`Range.last` on a half-open range.** `[2027-02-28..2027-03-31)` gives `.last = 2027-03-31` and `2027-03-31 in? period = false`. "Last" reads as the last member.
  - **Fix:** `.start`/`.end`, as in Rust and Python's `stop`, with `.includes_end` **(new; cold-test first)**. The cold test read the names in isolation, not beside `in?`.
- `30*used/days` needed a guard on `days`. Acceptable.

## Compared with what programmers bring

| They expect | From | Dewy today |
|---|---|---|
| `date(2026, 3, 15)`, `.replace(year=)` | Python, Temporal, jiff | Missing |
| A weekday enum (`Weekday.TUESDAY`, `TU(2)`) | chrono, jiff, dateutil | `int64` with 0 = Monday |
| `7.251832ms` | Go, Rust | `7251832ns` |
| `strptime` with `%z` | Python | No offset parse by pattern |
| `%H:%M` (letters can't be confused) | strftime | TR35 `HH:MM` silently prints the month |
| `.round(smallestUnit)` | Temporal, jiff | `quantize` pair plus `or_throw` |
| `rrule`, nth weekday | dateutil, jiff | Not built |
| The unit you wrote, kept in `f"{q:.2f}"` | pint | Unit dropped; kJ for kWh |
| `lb`, `psi`, `mph`, `kcal` | pint | Missing |
| A value-based `Picker` or `ComboBox` | SwiftUI, egui | Index-based `choice` |
| `SliderInt`, `.suffix("°")` | ImGui, egui | `float64` only, no value shown |
| `PlotLines`, sortable `Table` | ImGui, SwiftUI | Missing |
| A sound handle | Godot, Bevy | `int` id |

Where Dewy is ahead:
- Compile-time-checked literals.
- Monotonic `now - start`.
- `1day` versus `24hour`.
- Typed picks, where a typo is a compile error.
- Exact money arithmetic.
- The temperature reading/difference check.
- The leap-second-correct axis.
- Melody shapes.

## Ranked list

### Must fix before the owner decides
1. **D29 `weekday`:** 0 = Monday is a silent wrong answer for most newcomers. Use a weekday union, with an ISO number as a separate member.
2. **D31 pattern letters:** `HH:MM` prints the month as minutes and `hh` without `a` prints 09 for 21, both silently.
   - Make each a compile error with a fix-it.
   - Add named presets (`'iso'`, `'date_long'`).
   - Teach interpolation of named fields, `"{d.weekday_name} {d.day} {d.month_name}"`, as the first way to write a date.
3. **D19e:** rec (a) turns spec errors into run-time failures. Change the rec to (b), or show how `fmt` keeps the compile-time check without compiler magic.
4. **D34:** its example doesn't compile, because an exact difference is rejected by a `float64` annotation. Round exact arguments into float parameters once.
5. **D28 `choice` and `slider`:** `choice` binds a value of the union, not an index. `slider` is generic over ints, floats and quantities and can show its value.
6. **D11b rebinding:** name the rebind, save and load, conflict and display-name companions, and the confirming-key rule, before approving the replacement of `ui_controls`.
7. **D31 `Name<option=N>`:** messages must print the spelling the user wrote. **D31 `Range.last`** on half-open ranges: rename (cold test) or document next to `in?`.

### Should fix (these will reach the owner as slips)
- Duration display as an exact decimal in the largest unit; time quantities print as decimals (`5771/3ms`, `1551762261s`); `mean` over durations.
- `date(year month day)`; `zoned.at(time)`; `zoned(text pattern)` with offsets; `next_anniversary`.
- `in_zone` made total, with `OutsideCoverage` only under a strict tag; one family for time parse errors.
- `t.floor`, `t.round` and `t.ceil` beside `quantize`.
- Units: the missing common units; precision keeps the unit; written units kept for display (kWh); decimals rather than fractions for quantities.
- A sound handle and units in audio (`Playing`, `tone(440Hz 500ms)`); `is_playing` ends with no device.
- A typed UI field driven by shapes; `changed(id)`; right-aligned text; `plot`; a sortable `table`.
- Language-wide slips hit along the way:
  - top-level `or_throw` is rejected ("requires an enclosing function"), so every script needs a `main`;
  - `??` can't take a fallible right side;
  - `.max`, `.sum` and `max_by` need proofs over constant arrays and have no `T | none` form;
  - `sorted(descending=)`;
  - `rational(text)` gives `none` where other parsers give `ParseError`.

### Nice to have
- Recurrence with nth-weekday selectors.
- A `Julian` calendar and a warning on pre-1582 literals.
- Game `dt` as a time quantity.
- A ring buffer.
- `bench` statistics.
- Melody note lengths.
- A currency dimension.
- A clamp-drift lint.
- `label(x)` for union members.

## Ready or not

| Item | Verdict | Why |
|---|---|---|
| D11a string shapes | **Ready** | `Melody` covers the melody program's typed and constant paths, and the error text is excellent. Only `ShapeError` is provisional. |
| D11b `Controls<A>` | **Another iteration** | Rebinding companions and the confirming-key hazard are missing (must-fix 6). |
| D11c physics `get`/`has` | Not exercised | No program used physics. |
| D28 UI | **Another iteration** | The core (value tree, picks, `back=`, `@` places, `show`) is ready. `choice`, `slider`, typed fields, `changed`, alignment and `plot` are not. |
| D19e | **Another iteration** | Rec (a) loses compile-time spec checks. Recommend (b). |
| D29 | **Another iteration** | `weekday`. `$error_if`, `$check_constant`, `overflow='next'` and `leap_day=` are ready. |
| D30 | **Ready** | Leave bare off; the hint today is exactly right. |
| D31 | **Another iteration** | Pattern letters, `Name<option=N>` in messages, `Range.last`. `$time.rules`, `local"…"`, `time_of_day"…"`, `fold='later'`, `d.at(t)` and `Box<T=int64>` are ready. |
| D32 | Not a usability question | Rec (a) is unaffected. |
| D33 | Not exercised | |
| D34 | **Another iteration (small)** | Its example must compile: exact-to-float arguments. The names `ThermalResistance`, `r_value_us` and `TemperatureDifference` read well in use. |
| D35 | **Ready** | Program 1 needed exactly this. |
| D36 | **Ready** | Add `ThermalResistance` to the same list. |

## Outside scope (found while compiling, not acted on)
- **Compiler panic:** `p08_crash_repro.dewy`, the checker's `decimal_check_body` → "dictionary has no entry".
- `picked is? Column`, where `Column` is a literal-union alias inside a larger union, is rejected as "never" (program 12).
- The `remove_at` → `remove` → `pop` hints contradict each other.
- `mean(array<Duration>)` reports an error from inside `lib/std/nd.jo` using Jo syntax.
- `docs/LANGUAGE.md` line 2887 shows top-level `solve(...) or_throw`, which today's compiler rejects at top level.
