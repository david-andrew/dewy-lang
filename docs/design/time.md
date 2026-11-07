# Time, dates, clocks and calendars

The accepted design. Its history and reasoning are in [proposals/time/](proposals/time/): [v6](proposals/time/time-design-v6.md) holds the latest decisions, and [v5](proposals/time/time-design-v5.md) holds the full treatment of the application layers (recurrence, institutions, science, codecs), which stands except where this file differs. Items marked **(provisional)** are still open in [open_decisions.md](open_decisions.md) and are built to be easy to change. [LANGUAGE.md](../LANGUAGE.md) says what exists today.

> **BLUF:**
> - **One axis, one integer.** An `Instant` is a signed 128-bit count of nanoseconds since J0 on the ideal TT-rate axis. It takes 16 bytes and never allocates.
> - **The common path costs what C costs.** `now` is two clock reads, and `now - start` is monotonic elapsed time. Programs pay for zones, calendars and science only if they use them.
> - **Constants are free; input is checked once.** Literals are verified at compile time and folded to values. `or_throw` appears only where failure is real.
> - **Nothing is guessed.** Gaps, folds, missing coverage and off-grid values are compile errors or visible values, and a missing zone is a warning naming what is assumed.
> - **Built to outlast its standards.** The epoch, tick and axis never change. Rules change through pinned data. Defaults change only through `$dewy.version`.

## Vocabulary

| Term | Meaning |
|---|---|
| **Scale** | A coordinate and its rate convention (TT, TAI, UTC, TCB) |
| **Realization** | Physical clocks that estimate a scale (TAI, UTC(k)) |
| **Nominal** | The exact coordinate a label or reading names, with no claim that it was measured there |
| `Instant` | 128-bit ns since J0 on the TT-rate axis |
| `Duration` | 128-bit ns difference |
| `ClockReading` | What `now` returns: nominal wall `Instant`, monotonic sample, provider token, status |
| `MonoPoint` | A point on one monotonic provider's clock, such as a deadline |
| `Period` | A calendar recipe (`1day`, `1month`), not a number of seconds |
| `OffGrid` / `OutOfRange` | Not a multiple of the destination tick / does not fit the width |

## Everyday use

```dewy
let start = now
work
printl"took {now - start}"          # took 125ms: monotonic
sleep(300ms)
printl"today is {today}"            # today is 2026-10-24
let deadline = now + 5s             # a monotonic deadline
loop now <? deadline { poll }
let page = within(2s @fetch) ??<Timeout> cached or_throw
let t = instant"2026-10-24T12:00:00Z"
printl"{t + 90minute}"              # 2026-10-24T13:30:00Z
let typed = instant(read_line ?? "") or_throw
let dt = (now - start) / 1s as float64
```

`today` warns unless a zone is in scope (see Zones).

## The coordinate core

- **The axis.** `Instant` lies on the ideal TT-rate axis, a mathematical convention. It does not move when metrologists improve a realization.
- **Epoch J0.** `1977-01-01T00:00:32.184 TT`, nominal TAI `1977-01-01T00:00:00`. The stored integer is nominal TAI-compatible nanoseconds since 1977 TAI midnight, and `32.184s` appears only in TT labels and science conversions.
- **Reference integers,** re-derived by the test suite:

  | Event | ns from J0 |
  |---|---|
  | `1970-01-01T00:00:00 UTC` | `−220924791999918000` |
  | `1969-07-20T20:17:40 UTC` | `−235107732425406200` |
  | `1980-01-06T00:00:00 GPS` | `95040019000000000` |
  | `2000-01-01T12:00:00 TT` | `725803167816000000` |

- **Width.** Plain `Instant` and `Duration` hold 128 bits. `Instant<width=64>` is the compact form for huge columns; it covers September 1684 to April 2269 and halves the memory. Width never depends on tick. It is a type of its own, declared as `Instant_width_64`, which is what `Name<option=N>` means for a library type.
- **Representation.** A record of a signed high word and an unsigned low word, written in Dewy. It can become a builtin later with no source change. Add and subtract take about five instructions with no call. Multiply, divide and formatting go through `int`.
- **Overflow.** Plain arithmetic has no error branch. Leaving the 128-bit range (±5.39×10²¹ years) ends the task with a report, as other environmental failures do. This is a named assumption, and `$time.require_range` removes it. `t.checked_add(d)` gives `Instant | OutOfRange`. `width=64` arithmetic gives the value or `OutOfRange`, since 2269 is reachable.
- **Time quantities.** `300ms`, `2s`, `0.1s` and `1ns/3` remain exact quantities, and a `Duration` is the on-grid stored form. They mix directly: `t + 90minute`, `d <? 5s`, `d / 1s`. `(now - start) / 1s` is a `rational`.
- **Off the grid.** A constant off-grid quantity meeting a `Duration` or `Instant` is a compile error with fix-its (`quantize`, a caller-named tick, `time.science`). At run time `convert<Duration>(q)` gives `Duration | OffGrid | OutOfRange`. `quantize(tick=… rounding=…)` gives `[value loss]`. A float enters only through `quantize`, and NaN and infinities never become counts.
- **`as`** does only unique, exact conversions. Rounding, context selection and interpreting measured events are named operations.
- **Other ticks.** `Instant<tick=1ns/3>` is the same axis and epoch with a finer count. Comparing across ticks is exact.

## Literals

| Call | Gives |
|---|---|
| `instant"2026-10-24T12:00:00Z"` | `Instant`. An offset is required; without one it is a compile error with a fix-it to `zoned`. |
| `date"2027-01-31"` | `Date<Gregorian>` (the module's calendar) |
| `zone"America/New_York"` | `Zone` |
| `zoned"2026-10-26T09:00[America/New_York]"` | `ZonedDateTime` |
| `utc"2016-12-31T23:59:60"` | `UtcLabel`, which keeps `:60`; `.nominal` gives the `Instant` |

- **Ordinary delimited calls.** There is no new syntax. The same function on runtime text returns the union with its failures (`Instant | ParseError | …`).
- **The primitive.** A library function declares a validator run on constant arguments, as `regex` does. Text back is a compile error at the argument. None drops the exception members, and a plain record result is folded to its value. A user library gets the same treatment by declaring the same thing.
- **When a literal is infallible.** Every input is frozen and the result is identified with its rule pack, within its coverage, unique (or a written policy resolves it), on the grid and in range. Anything else is a compile error with a fix-it. Nothing depends on the compiling host.
- **What a literal proves.** A numeric interpretation under the pinned rules, not future law. A 2035 meeting compiled in 2026 stays reproducible. An `Appointment` keeps local intent and re-resolves through explicit migration.

## UTC

- **A segment table** relating UTC labels to the axis, shipped in the rule data:
  - **Before 1961:** outside coverage. An ancient `Z` is invalid, and ancient astronomy uses TT labels.
  - **1961–1971:** fractional offsets with rate adjustments, by the dated formula. A label can land off the ns grid.
  - **1972 onward:** integer leap steps; twenty-seven so far.
  - **From 20 May 2027:** continuous UTC. It is one more segment with an inherited offset.
- **Leap labels are validated.** `utc"2016-12-31T23:59:60"` is valid; `utc"2015-12-31T23:59:60"` is a compile error. Dewy never clamps `:60`. Negative leaps use the general skipped-label mechanism.
- **Arithmetic ignores leaps.** From `2016-12-31T23:59:59` to the next midnight is `2s`.
- **Display.** An `Instant` prints as RFC 3339 UTC within coverage, with the fraction only when nonzero. Outside coverage it prints a TT label (`-0584-05-28T12:00:00 TT`), never an invented `Z`.

## Civil time

| Type | Contents | Size |
|---|---|---|
| `Date<C>` | Day ordinal in calendar C | 8 bytes |
| `TimeOfDay` | ns since local midnight | 8 bytes |
| `LocalDateTime<C>` | Date and time of day; no zone | 16 bytes |
| `Offset` | Fixed UTC offset, to the second | 4 bytes |
| `Zone` | Handle to a zone in a pinned pack | 4–8 bytes |
| `ZonedDateTime` | `Instant`, zone handle, resolved offset | 32 bytes |
| `Resolution` | Local fields, policies, pack identity, trace | Heap; opt-in |

- **`Gregorian`** is the arithmetic proleptic Gregorian calendar with astronomical years, including year zero. It claims no historical adoption; `British` and `Swedish` are separately named. Bare `Date`, `date"…"` and `today` take their calendar from `$dewy.version` (`Gregorian`), and `$calendar` overrides it lexically. Public signatures say `Date<Gregorian>`.
- **Periods.** `1day`, `1week`, `1month` and `1year` are `Period`s, ordered recipes that need an anchor to become elapsed time.

  | Expression | Result |
  |---|---|
  | `zoned + 1day` | Same local time tomorrow, under the scope's gap and fold policy |
  | `zoned + 24hour` | Exactly 24 hours later |
  | `date + 1day` | The calendar successor |
  | `date + 1month` | Calendar month; overflow (the 31st) needs `overflow=` |
  | `instant + 1day`, `sleep(1day)` | Compile error; fix-it `24hour` (or a zoned add) |

- **Differences.** `zoned - zoned` is an elapsed `Duration`. `date - date` is a `Span`, a `Period` that knows its anchor **(provisional)**: `.total_days` counts calendar successors, so `a + (b - a) =? b` always holds; `.years`, `.months` and `.days` decompose it by completed anniversaries and months; `(b - a) / 1day` is the count of days.
- **Ages (provisional).** `age(born on=today)` counts completed anniversaries, never elapsed seconds over a year. A 29 February birthday counts on 1 March in common years (`leap_day='march_1'`), a convention `$time.require_profile` makes you state. `legal_age` always takes a jurisdiction.

## Zones

- **A zone** is an identity plus a versioned transition relation. Offsets can be any size, DST is metadata, and synthetic histories can give more than two candidates.
- **`$time.zone`** is chosen at compile time. A name (`'America/New_York'`) pins the whole program to one zone, `'system'` is the zone of the machine running the program, read once by name, and `'build'` pins the zone of the machine building it. Set in the main file, it holds in every module, and a different setting in an inner scope or another module is a compile error naming both. A program whose main file sets none may set zones in its modules and scopes. Rules come from the pinned pack, unless `$time.zone_source = 'host'`, so a test cannot change with a distribution's tzdata.
- **No zone to read.** `'system'` reads the TZ variable, then where `/etc/localtime` points or `/etc/timezone`; Windows' zone name, through CLDR's table in the pack; a page's browser zone. A machine with nothing to read, or a name the pack does not know, reads as UTC, and the program says so once on standard error when it first needs the zone.
- **The assumed zone.** An operation that needs a zone and has none warns, per site, naming what it assumes:

  ```text
  warning: `today` has no time zone here, so it assumes the zone of the machine it runs on.
    say so with `$time.zone = 'system'`, or name one: `$time.zone = 'America/New_York'`
  ```

  `zoned(s)` on text known only at run time warns the same way and reads the running machine's zone; a call settled at compile time has nothing to assume, so it does not warn.
  A literal cannot assume, so `zoned"2026-10-26T09:00"` without a zone, or with `'system'`, is a compile error.
- **Resolution policies.** Native resolution never guesses. `earlier`, `later`, `all`, `reject`, `skip`, `preserve_displacement` and `next` are named. A missing 02:30 in a one-hour gap becomes 03:30 under `preserve_displacement` and 03:00 under `next`.
- **Scope defaults.** `$time.gap = 'preserve_displacement'` and `$time.fold = 'earlier'` set lexical defaults. Without them, a civil add on a runtime zoned value gives `ZonedDateTime | Gap | Ambiguous`. A literal operand is proved at compile time.
- **Reading a caller's settings.** A metatag read in a parameter's default is read at the call site: `today = (scope=$time.zone) => …`. A caller can always pass the argument.

## Rule data

- **Default.** The data a Dewy version ships is what that version means: zone rules and the UTC table, in `lib/time/rules/`. There is no name to write. The artifact records the pack's identity.
- **Which version.** A module's `$dewy.version` selects the pack its literals fold against, and the main module's selects the one used at run time. A tagged release keeps every earlier release's pack.
- **`$time.rules`** is the override, for urgent law changes or test data: `$time.rules = 'urgent.bin'` at the top of the main file names a pack beside it, made with `tools/time/gen_rules.py` (a path for now, not v6's descriptor constant, which needs a metatag value that is not text). `$time.zone_source = 'host'` follows the host's database at run time, and a literal cannot fold against that.
- **Format.** Bytes reached through `$include_bytes` from a `.dewy` descriptor and read by library code, at compile time and at run time. Only a program that reaches a zone operation links them.
- **Staleness.** `ZonePackStale` is a status, never a failure of `today`.

## `$dewy.version`

- **`$dewy.version = '0.1.0'`,** at the top level of a module, says which Dewy the module's bare names mean. It is per module and never inherited, and generics and plugins use their definition site's.
- **The promise starts at the first release.** From then on a program tagged with a version always compiles with that version or any later compiler, and all future compilers know how all past versions worked. There are no breaking removals. If an old version turns out to have a serious security problem, the program still compiles, with a very obvious warning and the steps to fix it. Before the first release, the no-legacy rule stays.
- **No declaration** compiles as the current version, with a warning and a fix-it that inserts one, on a tagged toolchain. A development toolchain does not warn and accepts any well-formed version; a tagged one refuses a version newer than itself, naming both.
- **Evolution.** A version defines a default, a later one warns on bare uses whose meaning will change and offers the explicit spelling, and a later one still may change the default, only for modules declaring it. An old version keeps its meaning.
- **Never versioned:** J0, tick meaning, the axis, count meaning, wire identity of plain `Instant`.

## Clocks and waits

- **`now`** returns a `ClockReading`: 32 bytes, 16-byte aligned, no pointers. It holds the nominal wall `Instant`, a monotonic sample, a provider token and a status.
  - `reading - reading` is monotonic elapsed `Duration`. An NTP step cannot affect it.
  - `reading + Duration` is a `MonoPoint`; `reading <? point` compares monotonic samples.
  - `.nominal` is the wall `Instant`, and the only way to wall time. Persist that; a reading has no codec.
- **`monotonic`** is the monotonic sample alone. **`today`** is the nominal `Date` in the scope's zone. What replaces v5's `today_support` is open (D15e): a query named `possible_todays`, or `strict_today`, the union `Date | AmbiguousToday | UnknownToday` that `today` gives under `$time.require_clock_accuracy`.
- **Providers are acquired at entry, only if reached.** Failure is reported once before dependent user code runs, and reads after that are total. A pure program acquires nothing. Losing wall sync changes the status; elapsed time still works.
- **Monotonic continuity is a named assumption.** A provider that loses continuity ends the task with a report and never returns a compatible-looking reading. `$time.require_clock_domain` removes the assumption.
- **Relative waits count actual time.** `sleep`, `within`, TTLs and `reading + Duration` use suspend-inclusive monotonic time, so an hour with the lid closed counts as an hour. `clocks.active` excludes suspension and is explicit. Where a platform cannot give suspend-inclusive time, that is an entry failure, never a silent substitution. Wall steps never move a monotonic deadline. `sleep(1day)` is a compile error.
- **Contexts.** A `TemporalContext` holds provider handles, zone, calendar, rules and policies. Closures and tasks keep the context they captured. `time.with_context` installs one for tests; advancing a test clock affects those who captured it, and resetting it mints a new generation.

## Intervals

Anything taking an interval uses range syntax: `[a..b)`, `[a..b]`, `(a..b)`. Over anything ordered that is not an integer it is a `Range<T>` (lib/ranges.dewy), which is general, not special to time: its ends and which of them it includes. There is no `interval` function, so the bounds are always written. The flags stay as written and are never normalized away, and an unknown end is not an infinite end. Interval operations (Allen relations, measure, sets) are functions on ranges, per v5 §3.

## Formats

- **By a pattern.** `x.format("yyyy-MM-dd")` and `date(text "d/M/y")` use Unicode's date pattern letters (TR35), in English for now; a locale and declared losses are still to come.
- **Parsing never guesses.** Each parse names its grammar, result type and locale. Offsetless text gives local fields. Ambiguous numeric dates give candidates unless a profile supplies a convention.
- **Display** returns text plus declared losses. `$time.require_loss` makes accepting them explicit.
- **Codecs** decode exactly on their own tick and origin; conversion to `Instant` is a separate checked step. A `ClockReading` and a process-local handle are never on the wire. See v5 §11.

## Modules

| Module | Contents | Data it may map |
|---|---|---|
| `time` | `Instant`, `Duration`, `ClockReading`, `MonoPoint`, clocks, waits, the UTC table, RFC 3339 and POSIX/NTP/PTP codecs | ~40-row UTC table |
| `time.civil` | Dates, zones, periods, `today`, recurrence, appointments, localization | Zones reached |
| `time.science` | Scales, `Coordinate`, `Estimate`, `observe`, ephemerides, signals, Mars, CCSDS/SPICE/JD codecs | Named kernels |

The prelude offers `now`, `monotonic`, `sleep`, `within`, `today`, `age` and the literal calls, each loaded only when named. Everything else is qualified. A stopwatch reaches only the core; a program that uses none of this pays nothing.

## Strictness

Every convenience assumption has a named `$time.require_*` opt-out (`$time.explicit_*` if D10 is taken) that demands an explicit choice or evidence: the seventeen in v5 §12 plus `require_range` for 128-bit overflow. `$time.strict` enables them all, and `$bulletproof` includes it. They are compile-time and free when unused.

## Applications

Recurrence and `Appointment`/`Occurrence`/`Event`/`Observation` (v5 §6), sunset and publication calendars (§8), institutions and bitemporal records (§9), science, signals and Mars (§10) stand as written in v5, with intervals as ranges and `$dewy.version` in place of `$edition`.
