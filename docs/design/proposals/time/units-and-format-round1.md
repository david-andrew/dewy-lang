# Time, units and formatting: revision round (D29, D31, D33, D34, D35, D36, and `fmt`)

Inputs: `docs/design/time.md`, `proposals/time/time-design-v6.md` (and v5 §12), `lib/units.dewy`, `lib/time/*.dewy`, the open items as they stand, `~/dev/tmp/dogfood-1107/time-ui.md` (programs 1–9, 13, 15, 16), `consistency-audit.md` findings 3, 7, 8, 12, 14, 15 and 17, and the owner's formatting decision (D19e: `fmt` only). Coordinated with `ui-strings.md` (shapes, §2) and `safety-round3.md` (§2, §12: tags never change result types; the `strict_` prefix).

Programs: `~/dev/tmp/rev-1107/time/` holds twelve rewritten programs in the proposed surface. `time/stubs/` holds three that **run on master `d0f9714ef`** with the new library pieces stubbed in Dewy, so their printed output is real. `time/probe/` holds the one-line checks quoted below. Every program ran on the desktop with `DISPLAY`, `WAYLAND_DISPLAY` and audio off.

**Tested** means I ran it on today's compiler. **New** means it needs the owner's approval of a spelling. All names here are provisional until the cold read (table at the end).

## BLUF

- **`fmt` has one pattern language per kind of value, and the pattern picks the type.** Python's number patterns cover numbers, widths, alignment and separators. Plain words cover dates and times: `fmt'weekday day month_name'`, `fmt'hour:minute'`. Each kind is a string shape, so `fmt'.2f'` returns a function over numbers and `fmt'hour:minute'` returns one over times. A mismatch is a compile error, and so is a TR35 or strftime pattern, which gets a fix-it with the words.
- **`HH:MM` can't print the month any more.** Fields are words, `month` and `minute` can't be confused, `hour12` without `am_pm` is a compile error, and padding follows what people write by hand (`07/11/2026`, `9:05 PM`, `Saturday 7 November`). **Tested:** 13 of 13 patterns print the intended text (`stubs/t_patterns.dewy`).
- **A computed width is just an interpolated pattern:** `fmt'<{w}'`. This needs one shape extension that the strings revision doesn't have yet: holes that are counts.
- **Units stay on:** `fmt'.2f't` prints `3.03s`, and `t/s` gives the bare number. `x as km/hour` picks the unit. A quantity prints in the unit it was written in, so `1392kWh` stays `1392kWh`. Exact values print as decimals: `36.(1)°C`, not `325/9°C`.
- **Durations read like Go's:** `7.251832ms`, `1.65s`, `90minute`, and `fmt'hour:minute:second'`. **Tested** against the stub.
- **`weekday` is a name:** `d.weekday =? 'tuesday'`, while `=? 2` is a compile error. **Tested.** `iso_weekday` gives 1–7, and `d.next('friday')`, `d.nth_weekday_of_month(2 'tuesday')` and `date(2026 3 15)` are added.
- **No metatag changes a result type in time.** I decided the five cases the safety reviser passed on:
  - zoned arithmetic always gives a `ZonedDateTime`, with Temporal's "compatible" policy by default;
  - `in_zone` is total;
  - strict tags point to `strict_` companions;
  - `checked_add` becomes `strict_add`;
  - `$time.no_unchecked_today` is the one name for strict `today`.
- **Consistency findings:**
  - `Instant<width=64>` becomes an ordinary type parameter, with no `Instant_width_64`;
  - a range of dates with nothing inside it is empty;
  - range bounds are `.start` and `.end`;
  - the zone and rule settings become program settings, `$program.time_zone` and `$program.time_rules`;
  - `rounding=` is used everywhere;
  - `$check_constant` and `$error_if` leave the time design.
- **Units:** about 40 common units are added (`lb`, `psi`, `mph`, `kcal`, `hp`, `gallon_us`, `bar`, `eV`, `mAh`, …), with SI prefixes generated. `MB` means 10⁶ bytes and `MiB` 2²⁰, over a new base dimension `Information`. `10min` gets a fix-it to `10minute`, and nothing prints a unit you can't write back. D34's example compiles: an exact value rounds once into a float parameter, as on a `let`. D36's names default to `float64`, so `area:Area` is the whole annotation.

## 1. Every finding and what happened to it

| Source | Finding | Done | Where |
|---|---|---|---|
| time-ui must 1 | `weekday` 0 = Monday, silent | `Weekday` names; `iso_weekday` | §4 |
| time-ui must 2 | `HH:MM`, `hh` without `a` | Word patterns; TR35 removed | §2.4 |
| time-ui must 3 / owner | D19e | Decided by the owner; pattern language designed | §2 |
| time-ui must 4 | D34 example doesn't compile | Exact rounds once into float parameters; bare `Area` | §7.3 |
| time-ui must 7 | `Name<option=N>` leaks; `Range.last` | Ordinary parameter; `.start`/`.end` | §6, §5 |
| time-ui should | Duration display, `5771/3ms`, `mean` over durations | Display rule; `mean` on durations | §3 |
| time-ui should | `date(y m d)`, `zoned.at`, `zoned(text pattern)` with offsets, `next_anniversary` | All added | §4, §2.5 |
| time-ui should | `in_zone` total; one parse-error family | Total plus `strict_in_zone`; `ParseError` children | §8.1, §4.4 |
| time-ui should | `t.floor/round/ceil` | Added beside `quantize` | §4.3 |
| time-ui should | Missing units; precision keeps unit; kWh; fractions | All | §7, §3 |
| time-ui should | Positive divisor still gives `OutOfRange` | Refinement used | §4.3 |
| time-ui nice | Pre-1582 literal warning, year sign hint, float loss as float | Taken | §4.5 |
| time-ui nice | Recurrence nth-weekday | Not designed here: outside these items; a one-line hook given | §4.2 |
| time-ui nice | Currency dimension | Not done: needs user-declared dimensions; listed | §7.4 |
| parallel reviser | `10min` resolves to `min` | Fix-it; display never prints `min` | §7.2 |
| parallel reviser | `MB` vs `MiB` | SI and IEC both, distinct | §7.2 |
| safety §2 | Five time tags change types | Decided each | §8 |
| safety §12 | `strict_` vs `checked_` | `strict_` everywhere | §8.2 |
| ui-strings §10 | `int * 1ms` gives `OffGrid \| Duration` | On-grid rule for integer multiples | §4.3 |
| audit 3 | Empty discrete ranges reported nonempty | Successor-aware `is_empty` | §5 |
| audit 7 | `Name<option=N>` | Ordinary type parameters | §6 |
| audit 8 | Time literals through shapes | Exact requirements, S1–S10 | §9 |
| audit 12 | `$time.zone` scope | Program setting; one class per tag | §10 |
| audit 14 | Which format entry survives; pattern loss policy | `fmt` only; loss via `.local`/strict tag | §2.7 |
| audit 15 | `ties=` vs `rounding=` | `rounding=` for all time and numeric rounding | §4.3 |
| audit 17 | D34 imports | Every identifier imported | §12 |
| dogfood (mine) | Civil fields carry no ranges | `day`, `month`, `hour` refined | §4.1 |

## 2. `fmt`: the pattern language

### 2.1 The rule

`fmt` takes one pattern string and returns a function. The pattern's **kind** is a string shape, and each kind is an overload of `fmt` whose returned function accepts exactly the values that kind can write. This is ui-strings.md §2.4 rule 3: a literal picks the overload whose shape it fits. Nothing in the compiler knows about patterns.

```dewy
TextPattern:type = string<shape=@text_pattern_error>         # '<10'  '^20'  '*>8'
NumberPattern:type = string<shape=@number_pattern_error>     # '.2f'  ',d'  '+.1%'  '08.3e'
IntegerPattern:type = string<shape=@integer_pattern_error>   # 'x'  '#06b'  ',d'
DatePattern:type = string<shape=@date_pattern_error>         # 'weekday day month_name year'
TimePattern:type = string<shape=@time_pattern_error>         # 'hour:minute'  'minute:second.millisecond'
DateTimePattern:type = string<shape=@date_time_pattern_error>  # 'year-month-day hour:minute'
ZonedPattern:type = string<shape=@zoned_pattern_error>       # '… offset'  '… zone'

fmt = ((p:TextPattern):>((x:Display):>string) => …)
    & ((p:NumberPattern):>((x:Real):>string) => …)           # numbers and quantities of them
    & ((p:IntegerPattern):>((x:Integer):>string) => …)
    & ((p:DatePattern):>(((d:Date):>string) & ((l:LocalDateTime):>string) & ((z:ZonedDateTime):>string) & ((t:Instant):>string)) => …)
    & ((p:TimePattern):>(((t:TimeOfDay):>string) & ((d:Duration):>string) & ((l:LocalDateTime):>string) & ((z:ZonedDateTime):>string) & ((t:Instant):>string)) => …)
    & …                                                      # DateTimePattern, ZonedPattern alike
```

- **The kinds are disjoint.**
  - A text pattern is only fill, alignment and width.
  - A number pattern has at least one of a sign, `#`, `0`, grouping, a precision or a style letter.
  - An integer pattern has an integer style (`d x X b o`) or `#`.
  - A date or time pattern contains field words. Which words appear decides between date, time, date-time and zoned.
  - One literal fits one shape, so resolution is never ambiguous.
- **What each kind accepts:**
  - `Real` is every number type and quantities of them: machine integers, `int`, floats, `rational`, `Duration`.
  - `Integer` is every integer type and quantities of them.
  - `Display` is anything that prints.
  - A text pattern aligns the value's ordinary display, unit included.
  - An `Instant` formats in UTC, as it prints.
- **The idiom is to build once.** `const money = fmt'>12,.2f'` is folded while compiling (ui-strings §2.4 rule 5). `money(x)` then costs one call.
- **Juxtaposition:** `fmt'.2f'x` is the owner's spelling. Today only `fmt'.2f'(x)` parses: the juxtaposed form reads as two expressions, inside interpolation and outside it (`probe/p5.dewy`). That is a parser fix, listed in §15. The examples use `fmt'.2f'x` for a bare name, and parentheses for anything longer (`fmt'.1f'(v as km/hour)`).

```dewy
const f2 = fmt'.2f'
let x = 3.14159
printl'result is {fmt'.2f'x}, again {f2(x)}'      # result is 3.14, again 3.14
f2("hi")                                          # error: fmt'.2f' formats numbers; found string
fmt'hour:minute'(date"2026-11-07")                # error: fmt'hour:minute' formats times; a Date has no hour
fmt'.2q'                                          # error: 'q' is not a number style: f e E g G % d x X b o
fmt'HH:mm'                                        # error: 'HH' is not a field. Did you mean fmt'hour:minute'?
```

**Tested (stand-ins):**
- A runtime `fmt` stub returning a typed function works in interpolation, pre-built and as a `map` argument: `probe/p1.dewy` prints `result is 3.14`, `again 3.14 and      3.14|`, `["1.5" "2.2"]`.
- ui-strings.md tested a literal choosing the returned function's input type, and the mismatch error, with singleton literals (`check_literal_picks_result.dewy`).

### 2.2 Numbers and text

- **Grammar:** `[[fill]align][sign][#][0][width][grouping][.precision][style]`. This is Python's mini-language and today's `format` spec, so it needs no new letters.
  - **Align:** `<`, `>`, `^`, with one fill character before it (`*>8`).
  - **Sign:** `+`, `-` or a space.
  - **Grouping:** `,` or `_`.
  - **Styles:** `f`, `e`/`E`, `g`/`G` and `%` for any real; `d`, `x`/`X`, `b` and `o` for integers.
- **Width** counts grapheme clusters, unit included, so columns of quantities line up.
- **Exact values format exactly:**
  - `fmt'.2f'` on a `rational` rounds once from the exact value, ties to even, with no `.to_float64()` first. Today that conversion is required.
  - For another rounding, round first: `fmt'.2f'(round(x 0.01 rounding='nearest_away'))`.
- **`%`** multiplies by 100. On a quantity with a dimension it is a compile error.
- **Precision alone** (`.2`) means fixed decimals, as today. `g` gives significant digits.
- **Text truncation** isn't a pattern. Slicing is explicit (`name[0..10)`), which is today's rule.

### 2.3 Units: kept, and chosen by `as`

- **A number pattern on a quantity writes the number and then its unit:** `fmt'.2f'(3.0303s)` is `3.03s`, and `fmt'>10,.1f'(1392kWh)` is `  1,392.0kWh`.
- **The display unit** comes from §3: the unit you wrote, else the one set by `as`, else the chooser. `fmt'.1f'(60mph as km/hour)` is `96.6km/hour`.
- **The bare number:** divide by the unit, which already gives a plain number. `fmt'.2f'(t/s)` is `3.03`.
- **A pattern can't name a unit** (`fmt'.1f km/hour'`). Units are names in scope, and a validator only sees text. `as` already does the job with checking.

### 2.4 Dates, times and durations: words, not letters

A date or time pattern is a sequence of **field words**. Spaces and the punctuation `- / . : , ( )` stand as themselves, and any other literal text goes in double quotes (`"at"`). Every word is a member of the value, written as a label.

| Word | Writes | Example |
|---|---|---|
| `year` | The year; four digits at least, signed past 9999 or before 1 | `2026`, `+12026`, `-0584` |
| `month` | The month number | `11` |
| `month_name`, `month_short` | Its name | `November`, `Nov` |
| `day` | The day of the month | `7` |
| `weekday`, `weekday_short` | The weekday | `Saturday`, `Sat` |
| `hour` | 0–23 | `21` |
| `hour12`, `am_pm` | 1–12, and `AM`/`PM`; each needs the other | `9`, `PM` |
| `minute`, `second` | 0–59 (60 in a leap second) | `05` |
| `millisecond`, `microsecond`, `nanosecond` | Fraction digits: 3, 6 or 9 | `250` |
| `offset` | The UTC offset | `-05:00` |
| `zone` | The IANA name | `America/New_York` |
| `zone_short` | The abbreviation, for writing only | `EST` |

- **Padding follows handwriting.**
  - A number joined to another field by `-`, `/`, `.` or `:` is two digits (`07/11/2026`, `09:05`, `07/Nov/2026`, `00:07.250`).
  - A number on its own is as short as it can be (`Saturday 7 November`, `November 7, 2026`).
  - `hour12` is never padded (`9:05 PM`), `year` is at least four digits, and fractions have their fixed width.
  - **Tested:** `stubs/t_patterns.dewy` prints all 13 forms in §11 correctly. To get another padding, interpolate the members with a number pattern: `'{d.day}.{d.month}.{d.year}'` is `7.11.2026`.
- **Patterns can't be confused:**
  - The words for month and minute differ, so there's no `MM`/`mm` or `%m`/`%M` trap.
  - `hour12` without `am_pm`, or `am_pm` without `hour12`, is a compile error: "a 12-hour hour needs am_pm: write `hour12:minute am_pm`, or use `hour`".
  - A field the value lacks is a compile error (`hour` on a `Date`).
  - Any other word is a compile error. The validator recognizes TR35 (`yyyy-MM-dd`, `HH:mm`, `EEE`) and strftime (`%Y-%m-%d`, `%H:%M`) and offers the translation as a fix-it, so programmers who know either get there in one step.
- **Durations use the time words.** In `fmt'hour:minute:second'(d)`, the first field counts everything above it, so `431045:04:21` and `00:07` both work. A stopwatch is `fmt'minute:second.millisecond'`. A negative duration takes a leading `-`. Days, months and years aren't Duration fields, because they're calendar periods (decided earlier). That rule reaches the display too.
- **The defaults need no pattern:** `"{d}"`, `"{t}"` and `"{z}"` print ISO 8601 / RFC 3339, which is what most logs want.
- **Removed:** TR35 letters and `x.format("…")`. There are no users, so nothing is migrated.

### 2.5 Reading uses the same words

```dewy
const APACHE = 'day/month_short/year:hour:minute:second offset'
let t = instant("07/Nov/2026:05:15:31 -0500" APACHE)       # an Instant: both arguments constant, folded
let d = date(read_line ?? "" 'day/month/year')            # Date | ParseError
let l = local(text 'year-month-day hour:minute')          # LocalDateTime | ParseError
let z = zoned(text 'year-month-day hour:minute zone')     # ZonedDateTime | ParseError
```

- `instant(text pattern)` and `zoned(text pattern)` are **new** overloads. A pattern for `instant` must contain `offset` or `zone`. One for `zoned` without either is a compile error pointing to `local` or a `zone=` argument.
- **Reading is lenient where nothing is ambiguous:**
  - numbers read one or two digits whatever the padding;
  - names read in any case;
  - `offset` reads `Z`, `±HH:MM`, `±HHMM` and `±HH`.
- **Reading is strict where something is ambiguous:**
  - `zone_short` can't be read, since `CST` is three zones: a compile error naming `offset` or `zone`;
  - a two-digit year doesn't read;
  - all of the text must be consumed.
- Compact ISO (`20261107T051531Z`) is read by plain `date(text)` and `instant(text)`, which accept ISO 8601's basic format too. A pattern needs something between its fields.
- With a constant pattern, the pattern is checked while compiling. With constant text too, the call folds to a value: a dependent shape, ui-strings §2.1.

### 2.6 Computed widths and runtime patterns

- **Computed width or precision:** `fmt'<{w}'`, `fmt'>{w},.2f'` and `fmt'.{p}f'`. A hole must be a count (`int64` at least 0, which `.length` and literals prove). The pattern's literal part fixes the kind, and so the returned function's input type, while compiling, and nothing is checked at run time.
  - This needs shape requirement **S8** (§9), which ui-strings.md doesn't cover yet: there, "an interpolated string with holes is not a constant".
  - **Tested** with a runtime stub: `fmt'>{w}.2f'(x)` prints `     3.14` (`probe/p1.dewy`).
- **Holes of any other type** are a compile error: "a hole in a pattern takes a count; found string". A whole pattern known only at run time, from a config file for example, is converted explicitly: `fmt(NumberPattern(text) or_throw)` or `DatePattern(text) ?? …` (ui-strings §2.7). That keeps the input type static and the failure a value. `fmt(text)` on a plain `string` is the ordinary obligation, with those fix-its.
- **Date patterns take no holes,** since a field is a word. A computed field list is a runtime pattern, as above.

### 2.7 Loss and strictness (audit 14)

- `fmt` returns text. time.md's "display returns text plus declared losses" goes. A pattern that leaves the zone out is a choice the pattern states.
- Under **`$time.no_dropped_zone`** (row 15, §8.3), writing a `ZonedDateTime` or an `Instant` with a pattern that has neither `offset` nor `zone` is a compile error. Fix-its: add `offset`, or write `fmt'…'(z.local)` to say you mean local text. The result type doesn't change.

## 3. Display without `fmt`

- **The unit you wrote is the unit printed.**
  - A literal's unit acts as an `as`, carried through scaling and sums of the same unit, as `as` already is, until a product or quotient changes the dimension. Then the chooser picks.
  - So `printl(1392kWh)` is `1392kWh` (today `5011200kJ`), and `let total = 0kWh; total += e` keeps kWh. Pint and Swift's `Measurement` do the same.
  - A sum of two different written units goes to the chooser.
- **Exact quantities print as decimals.**
  - A terminating decimal is written as one (`1.65s`).
  - A repeating one shows its repeating digits in parentheses when there are at most six of them (`36.(1)°C`, `1.923(6)s`, `578.(703)kJ`).
  - Otherwise it prints as a fraction (`1/97m`).
  - Every form is exact. Plain `rational` numbers keep `n/d`: this rule is about quantities, where a fraction reads as a bug.
- **Durations and time quantities:**
  - A whole number of hours prints in `hour`, and a whole number of minutes in `minute`.
  - Anything else prints as an exact decimal in the largest of `s`, `ms`, `µs` and `ns` not above it.
  - So `7251832ns` is `7.251832ms`, `1650ms` is `1.65s` and `91750ms` is `91.75s`; `90minute` and `169hour` are unchanged in substance. **Tested** with the stub: 8 of 8 (§11).
  - The display only changes how a value prints, never its value. The printed text is always valid Dewy, as the rest of printing is: `minute` and `hour` in place of today's unwritable `min` and `h` (`probe/p2.dewy` prints `90min` today).
  - Long durations read best through a pattern: `fmt'hour:minute:second'`.
- **A float loss prints as a float:** `quantize`'s loss from a float input is `0.473ns`, not the binary fraction `31768077/67108864ns`.
- **`mean` works on durations and time quantities,** with the same empty-array rule as numbers. Today it fails inside `lib/std/nd.jo` with Jo syntax in the message.

## 4. Dates (D29)

### 4.1 Fields

```dewy
Weekday:type = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday'
```

- **`d.weekday` gives a `Weekday`.**
  - `d.weekday =? 2` is a compile error. **Tested** on a stub; the message needs the hint "a Weekday is a name: write 'tuesday'".
  - `=? 'tusday'` is a compile error listing the seven. **Tested.**
  - It prints as `tuesday`. `label(d.weekday)` (ui-strings §6) and the pattern word `weekday` give `Tuesday`.
- **`d.iso_weekday`** gives 1–7 from Monday, for arithmetic and ISO week numbers. The name says which convention it is.
- **`weekday_name` is removed.** `month_name` stays, since `month` is a number (1–12 is universal).
- **Civil fields carry their ranges:** `day:int64<(1 <=? day <=? 31)>`, `month` 1–12, `hour` 0–23, `minute` 0–59. Then `d - (d.day - 1)*1day` needs no proof. Today it does: `stubs/t_weekday.dewy` needed `$runtime_checks` for exactly this.

### 4.2 Building and stepping

```dewy
date(year month day)                 # Date | InvalidDate; constant arguments fold, and a bad one is a compile error
time_of_day(hour minute second=0)    # TimeOfDay | InvalidFields, the same
d.next(w)                            # the first `w` after d (strictly after)
d.nth_weekday_of_month(n w)          # n from 1 to 4, or -1 for the last: a Date; n = 5 or -5 gives Date | InvalidDate
born.next_anniversary(after=on leap_day='march_1')   # the next birthday on or after `on`; leap_day as `age`
z.at(t)                              # same date and zone, time of day `t`: a ZonedDateTime
```

- **`date(2026 3 15)`** is the first thing anyone types. It is a shaped dependent overload (ui-strings §2.1): constants fold, and `date(2026 2 30)` is a compile error, "February 2026 has 28 days".
  - A refinement overload for `month` 1–12 and `day` 1–28 returns a plain `Date` for any year. So `date(y 3 1)` needs no handling, and `date(y 2 29) ?? date(y 3 1)` is a `Date`. That removes the case that made the dogfood chain `??` onto a fallible right side.
- **`d.nth_weekday_of_month(2 'tuesday')`** is Patch Tuesday, and `-1 'friday'` is the last Friday.
  - The result type comes from a refinement on `n`. **Tested** as a stub on master: it printed the five correct second Tuesdays, November 2026 to March 2027.
  - It is also the hook recurrence needs: `every=1month` plus a function from each month to its day. Recurrence itself (v5 §6) is outside these items, so it's listed for the next time round.
- **`z.at(t)`** replaces "midnight plus nine hours", which gives 08:00 on a DST day. It follows §8.1's policy, so it gives a plain `ZonedDateTime`.
- **Next anniversary:** `born.next_anniversary(after=today)` replaces 4 lines and the hand-coded leap-day rule.
- **Two ways to count days:** the docs lead with `(b - a) / 1day`. `.total_days` stays as the field it decomposes into.

### 4.3 Rounding and grids

- **`t.floor(tick)`, `t.ceil(tick)` and `t.round(tick rounding='nearest_even')`** on `Instant`, `Duration` and `ZonedDateTime` give the value. `round` takes the nearest modes (`'nearest_even'`, `'nearest_away'`), and its default matches numeric `round`'s. `quantize` stays for when the loss matters. These are Temporal's and jiff's `.round(unit)`, using Dewy's rounding vocabulary.
- **Plain results:**
  - A constant tick that is a whole number of nanoseconds can't land off the grid, so these give the value.
  - `width=64` adds `OutOfRange`, as all its arithmetic does.
  - `quantize(... tick=1s)` on a stored value also loses its `OffGrid` member for a constant valid tick: it is a shape on `tick` (ui-strings §2.9).
- **Integer multiples stay on the grid.** `n*1ms` with `n` an integer is a `Duration`, because an integer times an on-grid constant is on the grid. ui-strings.md found `int * 1ms` giving `OffGrid | Duration`.
- **A proven-nonzero divisor gives a plain value:**
  - `total // runs` with `runs:int64<(>? 0)>` is a `Duration`;
  - `1s / mean` is a `rational`, and needs `| OutOfRange` only when `mean` may be zero.
- **Vocabulary (audit 15):** every rounding in time and numbers is `rounding=` with `'nearest_even' 'nearest_away' 'floor' 'ceil' 'toward_zero'`. `ties=` is left only to `select` fairness, and `grouping=` to reductions.

### 4.4 One error family for reading

- Every text reader (`instant`, `utc`, `date`, `local`, `zoned`, `time_of_day`, with or without a pattern) gives `T | ParseError`. So `:>Instant|ParseError` is the obvious signature, and `or_throw` in it compiles.
- `InvalidFields` (a February 30, a `25:00`, a leap second that never happened) is a child of `ParseError`, so `??<InvalidFields>` still selects it.
- Text that is off the nanosecond grid or outside the UTC table's coverage is a `ParseError` whose message says so. The arithmetic types `OffGrid` and `OutsideCoverage` stay separate, for arithmetic and `strict_in_zone`.

### 4.5 Literals

- `date"12026-01-01"`: the error says "years past 9999 take a sign: `+12026-01-01`".
- `date"-0584-05-28"` and any other `date"…"` before 1582-10-15, with no `$calendar` in scope, warns that this is the proleptic Gregorian calendar and that historical dates are usually Julian. `Julian` is v5 work and unbuilt, so the warning names `$calendar = Gregorian` to silence it until then.
- `$error_if` and `$check_constant` are gone from the time design. Literals are shaped overloads that fold, and `sleep(1day)` and `instant + 1day` are refused through `@refuse("…")` shapes (ui-strings §2.6, §2.9). The messages are unchanged.

## 5. Ranges (audit 3, D31 `Range.last`)

- **Fields:**
  - `Range<T>` holds `.start`, `.end`, `.includes_start` and `.includes_end`: the written bounds, with no claim that they are members.
  - Arrays' `.first`/`.last` are members, so the old names meant two things.
  - `IntRange` takes the same bound names. Its `.first`/`.last` stay as members, since an integer range is a sequence. That is a natural extension, flagged.
- **Emptiness uses the domain:**
  - A type with `next_up` is discrete. Dates step by `+1day`, an `Instant` or `Duration` by its tick, a float by `next_up` (the D10 name). A range of it is empty when no value lies inside it: `(date"2027-03-01"..date"2027-03-02")` is empty, and so is `[a..a.next_up)` minus its start.
  - A type without `next_up` (`rational`, text) is dense, and keeps today's rule.
  - The flags print and compare as written, and are never normalized.
  - `lib/ranges.dewy`'s `is_empty` gains one overload. `contains` is already right.
- **Prints as written,** `[2027-02-28..2027-03-31)`, as today.

## 6. `Instant<width=64>` without a naming convention (audit 7)

```dewy
Instant:type = <width:(64|128)=128 tick=1ns>(if width =? 64 core.Instant64<tick> else core.Instant128<tick>)
let small:Instant<width=64> = convert<Instant<width=64>>(t) ?? fallback
```

- **Ordinary parameters:** `width` and `tick` are value parameters with defaults, as `Box:type = <T=int64>[v:T]` has a type parameter. The alias body is a compile-time expression over constant parameters, using "comptime, not macros" and no name lookup.
- **Messages print what you wrote:** `found Instant<width=64>`, and "Instant's width is 64 or 128", which comes from the parameter's type.
- **The compiler needs:** constant value parameters on a type alias (`tick=` needs this already) and an `if` or `match` over them in an alias body, evaluated while compiling. It is a general facility, also wanted for `uint<bits>`-style families, and it is flagged as such.
- **Fallback, if that facility is refused:** two ordinary names, `Instant` and `CompactInstant` (likewise `CompactDuration`). Those would need the cold read.
- `Instant_width_64`, `Duration_width_64` and the dewy_reader rule at `compiler/dewy_reader.dewy:10113` go.

## 7. Units (D34, D36, the student list)

### 7.1 Added to `units`

| Kind | Added |
|---|---|
| Mass | `lb`/`pound`/`pounds` (0.45359237 kg exactly), `oz`/`ounce`, `stone`, `short_ton`, `long_ton`, `tonne` |
| Length | `nmi`, plus SI prefixes on `m` (`µm`, `nm`, …) |
| Area | `acre`, `hectare`/`ha` |
| Volume | `gallon_us`, `gallon_uk`, `quart_us`, `pint_us`, `pint_uk`, `fl_oz_us`, `cup_us` |
| Speed | `mph`, `knot` |
| Pressure | `kPa`, `MPa`, `hPa`, `bar`, `mbar`, `atm`, `psi`, `mmHg`, `inHg` |
| Energy | `Wh`, `kWh` (exists), `MWh`, `GWh`, `cal`, `kcal`, `eV`, `BTU` (exists), `therm` |
| Power | `hp` (550 ft·lbf/s), `mW`, `MW`, `GW` |
| Force | `lbf`, `kN`, `standard_gravity` |
| Charge, electric | `C`, `Ah`, `mAh`, `mA`, `mV`, `kV`, `Ω`, `kΩ`, `F`, `µF`, `H` |
| Frequency, rotation | `kHz`, `MHz`, `GHz`, `rpm` |
| Information | `bit`, `B`/`byte`; `kB MB GB TB`; `KiB MiB GiB TiB`; `kbit Mbit Gbit` |

- **SI prefixes are generated** for every SI named unit (`q` to `Q`). They are ordinary constants, and each loads only when imported. The owner's notes (discussion_points.md "units … dynamic lookup over combinations") went this way, and generating them needs no lookup magic.
- **US and imperial volumes are named apart.** There is no bare `gallon`: its error lists `gallon_us` and `gallon_uk`. Same for `pint`.
- **Tested** (`stubs/t_units.dewy`, the units as exact Dewy constants on master):
  - 60 mph = 96.561 km/h;
  - 150 lb = 68.039 kg;
  - 32 psi = 220.632 kPa = 2.177 atm;
  - 250 kcal = 1046 kJ;
  - 200 hp = 149.140 kW;
  - 15 US gallons = 56.781 L, and 15 UK gallons = 68.191 L;
  - 1 acre = 0.405 ha.

### 7.2 `MB` and `MiB`, and `min`

- **`Information` is a ninth base dimension, counted in bits, with `B = 8bit`.** Joining the compiler's list of eight, it needs no new syntax.
- **`MB` is 10⁶ bytes and `MiB` is 2²⁰.** That is SI, IEC and Kubernetes (`M` vs `Mi`).
  - `$program.max_memory = 512MB` means 512,000,000 bytes, and hover shows `488.28125MiB`.
  - `KB`, `Kb` and `mb` aren't defined. Each error offers `kB` (1000) or `KiB` (1024), and `mb` names `MB` or `Mbit`.
  - Computed sizes print through the SI chooser (`1.5MB`), as every other dimension does, and a written `MiB` stays `MiB` (§3).
  - **Tested:** `512MB` is 512000000 and `512MiB` is 536870912.
- **`10min`:** today it says "'min' needs arguments" (`probe/p2.dewy`).
  - The new error: "`min` is the function min, not a unit: write `10minute`".
  - `min` and `h` stay unwritable. `min` is a prelude function, and `h` would be the only one-letter unit in the prelude, colliding with the most common height variable. The long forms are already the written ones.
  - The display stops printing them (§3).
  - **Name question:** none needed, since nothing new is spelled. Short `min` is rejected for the collision.

### 7.3 Annotations: bare dimension names, and exact into float (D34, D36)

- **D36 names default to `float64`.** `Area:type = <T=float64>(T * Length^2)`, the same pattern as LANGUAGE.md's `Duration<T>`. So `area:Area` is a float area and `Area<rational>` an exact one. This is today's default type parameter, with no new feature.
  - **Tested:** the explicit generic form works today, `f = <T>(a:Area<T>) => a*2`: `probe/p4.dewy` printed `4645152/78125m^2` and `59.4579456m^2`. A bare generic alias without the default is rejected ("expects 1 type argument"), which is why the default matters.
- **An exact value rounds once into a float parameter,** as it already does into a float `let`. D34's `heat_loss(a rise wall)` with `rise = 70°F - 30°F` then compiles. Today it is "expects float64 * Temperature, found rational * Temperature".
- **The D36 list:**
  - `Area`, `Volume`, `Speed`, `Acceleration`, `Force`, `Energy`, `Power` and `Pressure`;
  - plus `ThermalResistance` (D34) and `Information`;
  - plus `Frequency`, `Charge`, `Voltage`, `Resistance`, `Density` and `Torque`. The last six weren't in D36. They follow the same pattern and need the cold read.
- **Program 7's "may panic" `1/window_u`:** a `let` that holds a nonzero literal and is never reassigned should count as known nonzero. That belongs to the facts owner, and is listed in §15.

### 7.4 Not done

A currency dimension (`USD` beside `kWh`) needs user-declared base dimensions. Money as an exact `rational` works today and formats exactly. This is a nice-to-have for whoever owns units next.

## 8. Strictness: no tag changes a type (safety §2)

### 8.1 The five cases, decided

| Case | Decision |
|---|---|
| `$time.gap`/`$time.fold` decide whether `zoned + 1day` is a union | `+`, `z.at(t)`, `l.in_zone(z)` and `zoned(text)` always give a `ZonedDateTime`. The default is Temporal's "compatible": a gap moves forward by its length (`'preserve_displacement'`) and a fold takes `'earlier'`. The tags only pick other policies from that set (`'next'`, `'later'`). Explicit arguments may still pick `'reject'`, `'all'` or `'skip'`, and those overloads return their unions. A literal that hits a gap or fold warns, naming what the default chose and the argument that silences it. Under `$time.no_assumed_policy` (row 4), an unstated policy is a compile error whose fix-it writes the arguments. **Changes time.md's "native resolution never guesses", so it needs the owner (§12, D31).** |
| `in_zone` and `OutsideCoverage` | `t.in_zone(z)` is total. Beyond the pack's last transition it follows the zone's TZif footer rule, and before its first it uses local mean time, both from the data itself. `t.strict_in_zone(z)` gives `ZonedDateTime \| OutsideCoverage` when the answer depends on that extension. `$time.no_assumed_extrapolation` (row 13) makes `in_zone` an error pointing to it |
| `$time.require_range` | `t + d` stays `Instant`. `$time.no_assumed_range` makes an unproven `+` an error pointing to `t.strict_add(d)` (renamed from `checked_add`) |
| `$time.require_clock_domain` | `reading - reading` stays `Duration`. `$time.no_assumed_clock_domain` makes it an error pointing to `strict_elapsed(start end)`, which gives `Duration \| ClockDiscontinuity \| DomainMismatch` |
| `$time.require_resources` | Loaders keep their types. `$time.no_assumed_resources` makes each loading call an error pointing to its `strict_` companion (`strict_zone(name)` and so on) |
| `today` | Stays `Date`. `$time.no_unchecked_today` makes `today` and `age`'s default `on=today` an error pointing to `strict_today` (decided, D15e). One name: it replaces `$time.handle_uncertain_today`, whose verb is outside the tag grammar (`$no_`, `$prove_`, `$explicit_`, `$assume_`, `$allow_`) |

### 8.2 One prefix

`strict_` is used everywhere for "the same call, with its failures as values": `strict_today` (decided), `strict_add`, `strict_in_zone`, `strict_elapsed` and `strict_zone`. Rust's `checked_add` precedent loses to one Dewy word. One risk for the cold read: in Rust, `strict_add` panics.

### 8.3 The other strict tags

- **Rename the rest** in the same grammar: `$time.require_X` becomes `$time.no_assumed_X` for v5 §12's rows 1–5, 7–14, 16–17 and the range row. Row 6 is `$time.no_unchecked_today`, and row 15 is `$time.no_dropped_zone` (§2.7).
- **Each now follows the rule:** it makes a convenient call a compile error with a fix-it to an explicit argument or a `strict_` companion, and never changes a type.
- `$time.strict` enables them all, and `$bulletproof` includes it, both unchanged.

## 9. What shapes must support for time and formats (audit 8)

Checked against ui-strings.md §2. Only S8 is missing.

| # | Requirement | Time and format use | ui-strings.md |
|---|---|---|---|
| S1 | A shape on any type, not just `string` | `tick:(rational*Time)<shape=@tick_error>` | §2.1 ✓ |
| S2 | A shape naming sibling parameters | `date(text pattern)`, `zoned(text zone fold gap)`, `date(year month day)` | §2.1 ✓ |
| S3 | Constants include metatag-read defaults and folded shaped results | `fold=$time.fold`, `zone=zone"…"` | §2.2 ✓ |
| S4 | A literal picks the overload, and so the result type | `fmt`'s seven kinds; `date"…"` infallible | §2.4 rules 1–4 ✓ |
| S5 | A passing call with constant inputs folds to a record or function value | Literals cost nothing; `const f = fmt'…'` | §2.4 rule 5 ✓ |
| S6 | Refusal with a message for every call of an overload | `sleep(1day)`, `instant + 1day` | §2.6 ✓ |
| S7 | The compile-time evaluator runs library parsers over `$include_bytes` data, memoized per input tuple | Zone literals read the rule pack while compiling | Implied by §2.2 and §2.10; to be stated |
| S8 | **Count holes:** an interpolated string whose holes are all counts (`int64` at least 0) is checked while compiling against a shape that opts in. The validator receives the literal text with each hole written `{}` and accepts only if every count there gives text of the shape. The value then has the shape, with no run-time check. Other holes keep it an ordinary runtime string. A shape opts in so that a validator that ignores braces can't vouch for counts it never saw | `fmt'<{w}'`, `fmt'.{p}f'` (owner's requirement) | **Missing**: §2.2 says "an interpolated string with holes is not a constant". The opt-in spelling is the strings reviser's to choose |
| S9 | `T(text)` gives `T \| ShapeError` | `NumberPattern(text)`, `DatePattern(text)` | §2.7 ✓ |
| S10 | Errors print the shaped type's own name and its validator's text | "fmt'.2f' formats numbers"; "'HH' is not a field" | §2.3 ✓ |

## 10. Setting scopes (audit 12)

| Class | Tags | Rule |
|---|---|---|
| Program setting | `$program.time_zone`, `$program.time_rules`, `$program.time_zone_source` (renamed from `$time.zone`, `$time.rules` and `$time.zone_source`) | Set once in the main file. Anywhere else it is a compile error naming the main file. A library never sets one: it takes `zone=` arguments, whose defaults read the program's zone at the call site |
| Scoped setting | `$time.gap`, `$time.fold`, `$calendar` | Lexical, and read at the call site through parameter defaults |
| Scoped strictness | `$time.no_*`, `$time.strict` | Lexical, like the other `$no_` tags |
| Module version | `$dewy.version` | Per module, never inherited; generics use their definition site's |

- This removes the exception audit 12 found. Today a main-file `$time.zone` forbids module settings, while a main file that sets none lets modules choose, so a library could compile alone and fail when imported.
- No program needs a library-chosen zone. A report "in Tokyo" passes `zone"Asia/Tokyo"` or calls `t.in_zone(…)`.
- **Narrows D15a** (the module and scope clause goes), and the renamed spellings follow the stem's `$program.*` rule. Both go to the owner (§12, D31).

## 11. Dogfood re-run

### Tested on master (stubs)

`stubs/t_patterns.dewy` printed:

```text
2026-11-07               year-month-day
07/11/2026               day/month/year
11/07/2026               month/day/year
07.11.2026               day.month.year
Saturday 7 November 2026 weekday day month_name year
November 7, 2026         month_name day, year
Tue 10 Nov               weekday_short day month_short
21:05                    hour:minute
9:05 PM                  hour12:minute am_pm
21:05:09.250             hour:minute:second.millisecond
Saturday at 21:05        weekday "at" hour:minute
07/Nov/2026:21:05:09 -05:00   day/month_short/year:hour:minute:second offset
2026-11-07 21:05 America/New_York   year-month-day hour:minute zone
7.251832ms  1.65s  91.75s  90minute  169hour  1551762261s  125ms  0s     (Duration display)
```

- The first padding rule printed `7/Nov/2026`, joining only number to number. I widened "joined" to any neighboring field, and Apache's form came out right. That is the rule in §2.4.
- `stubs/t_weekday.dewy` printed the Tuesdays of program 5 and `is 10 Nov a Tuesday? true`. `stubs/t_units.dewy` printed §7.1's figures.

### Programs, re-graded

O = obvious, D = discoverable, C = concise, S = safe by default, X = complete.

| # | File | What changed | O | D | C | S | X | Before (O D C S X) |
|---|---|---|---|---|---|---|---|---|
| 1 | `p01_meeting.dewy` | D35, total `in_zone`, `z.at`, word patterns | 5 | 5 | 5 | 5 | 5 | 4 4 3 3 3 |
| 2 | `p02_logs.dewy` | `instant(text APACHE)`, one `ParseError`, decimal durations, `mean` | 5 | 5 | 5 | 5 | 5 | 3 3 2 4 2 |
| 3 | `p03_bench.dewy` | Durations print `7.251832ms`; positive divisor plain; `as ms` | 5 | 5 | 5 | 5 | 5 | 5 4 3 5 2 |
| 4 | `p04_birthdays.dewy` | `date(y m d)`, `next_anniversary`, `weekday` pattern | 5 | 5 | 5 | 5 | 5 | 3 3 3 4 2 |
| 5 | `p05_recurring.dewy` | `Weekday`, `nth_weekday_of_month`, `next` | 5 | 5 | 5 | 5 | **4** | 2 2 2 2 1 |
| 6 | `p06_space.dewy` | Duration patterns, float loss, `round`/`floor`, literal hints | 5 | 5 | 5 | 5 | **4** | 4 4 4 3 3 |
| 7 | `p07_insulation.dewy` | D34, bare D36 names, units kept, decimal °C | 5 | 5 | 5 | 5 | 5 | 4 4 3 3 4 |
| 8 | `p08_bill.dewy` | `kWh` kept, bare names, `fmt` | 5 | 5 | 5 | 5 | **4** | 4 4 4 3 3 |
| 9 | `p09_student.dewy` | All units present, unit kept, `10min` hint | 5 | 5 | 5 | 5 | 5 | 4 3 5 4 2 |
| 13 | `p13_report.dewy` | `fmt` only; `fmt'<{w}'`; mismatch errors | 5 | 5 | 5 | 5 | 5 | 4 3 4 3 3 |
| 15 | `p15_sensors.dewy` | `Instant<width=64>` messages, `t.floor` | 5 | 5 | 5 | 5 | 5 | 4 3 3 5 3 |
| 16 | `p16_billing.dewy` | `.start`/`.end`, discrete emptiness, default policies | 5 | 5 | 5 | 5 | 5 | 4 4 4 3 4 |

**Floors:**
- **5 X = 4:** "every second Tuesday" as a recurrence object (`every=1month` plus the nth-weekday hook) isn't designed here. v5 §6 is outside these seven items. The program needs only `nth_weekday_of_month`, which is here.
- **6 X = 4:** `time.science` (Julian Date, TDB) and the `Julian` calendar are v5 §10 work. The warning that points at them is here.
- **8 X = 4:** a currency dimension needs user-declared base dimensions (§7.4).

**Paper, by necessity:** the twelve programs use spellings that don't exist yet. What runs is the three stubs and the probes, whose outputs are quoted. Grades for C and O rest on reading the programs against Python, Go, Rust, Temporal/jiff, pint and Swift. Each line that used to need a workaround now has a one-call form (for example program 2's 13-line offset parser becomes the `APACHE` constant).

## 12. Replacement text for open_decisions.md

D19e is decided and gone (the coordinator's `d19e.py`). The pattern language below is new surface, so it gets a new item, D37. D29 and D31 keep the rest.

### D29. Dates: weekday names, dates from numbers, stepping (all reversible)
Turn this on and a weekday is a name, so comparing it with a number is a compile error, and a date can be built from three numbers.

```dewy
$program.time_zone = 'Europe/London'
let d = date(2026 11 10)                                   # a Date; constants are checked: date(2026 2 30) is a compile error
let born = date"2000-02-29"
printl(d.weekday =? 'tuesday')                             # true; `d.weekday =? 2` is a compile error
printl'{d.iso_weekday} {d.next('friday')} {d.nth_weekday_of_month(2 'tuesday')}'   # 2 2026-11-13 2026-11-10
printl(born.next_anniversary(after=d))                     # 2027-03-01, the same leap-day rule as `age`
printl'{d.add(1month overflow='next')} {age(born on=d leap_day='february_28')}'
```

- **Common path:** `date(y m d)`, `d.weekday =? 'tuesday'`, `fmt'weekday day month_name'd`.
- **To adjust:**
  - `d.iso_weekday` gives a number;
  - `date(y m d) ?? …` handles a run-time date that may not exist (with `month` 1–12 and `day` 1–28 there is nothing to handle);
  - `nth_weekday_of_month(5 …)` gives `Date | InvalidDate`.
- **Semantics taken:**
  - civil fields carry their ranges (`day` 1–31);
  - `weekday_name` goes, replaced by `label(d.weekday)` and the pattern word `weekday`;
  - `overflow='next'` and `leap_day=` stay as built;
  - `$error_if` and `$check_constant` leave the user-facing design, replaced by string shapes (D11).
- **Names for you** (rec: yes; the cold read is pending): `Weekday` and its seven members, `iso_weekday`, `d.next(w)`, `nth_weekday_of_month`, `next_anniversary(after=)`, `date(year month day)`, `time_of_day(hour minute second=0)`.
- **Reversible:** yes.

### D31. Time spellings: zoned defaults, rounding, ranges, compact instants (all reversible)
Turn this on and adding a day to a zoned time always gives a zoned time, a range's ends are `.start` and `.end`, and `Instant<width=64>` is an ordinary type parameter.

```dewy
$program.time_zone = 'America/New_York'                    # a program setting: main file only
$program.time_rules = 'urgent.bin'                         # a rule pack beside the main file
Box:type = <T=int64>[v:T]                                  # bare Box means Box<int64>
let b:Box = Box[1]
let meet = zoned"2026-10-31T09:00[America/New_York]"
printl(meet + 1day)                                        # a ZonedDateTime: a gap moves forward, a fold takes the earlier
printl(meet.add(1day gap='reject' fold='reject'))          # ZonedDateTime | Gap | Ambiguous, when you ask
printl(meet.at(time_of_day"09:00"))
let t = instant"2026-01-01T00:00:00.7Z"
printl'{t.floor(1s)} {t.round(1s)} {quantize(t rounding='floor' tick=1s)}'
let small = convert<Instant<width=64>>(t) ?? t             # errors print `Instant<width=64>`
let r = [date"2026-01-01"..date"2026-02-01")
printl'{r.start} {r.end} {r.includes_start} {r.includes_end} {(date"2026-01-01"..date"2026-01-02").is_empty}'   # … true
let l = local"2026-11-01T01:30"
printl(l.in_zone(zone"America/New_York" fold='later'))
```

- **Common path:**
  - zoned arithmetic, `at`, `in_zone` and `zoned(text)` give plain values;
  - `t.floor(1minute)` buckets;
  - `.start`/`.end` read as bounds.
- **To adjust:**
  - pass `gap=`/`fold=`, or set `$time.gap`/`$time.fold` for a scope;
  - `quantize` gives the loss;
  - `strict_in_zone` and `strict_add` give failures as values;
  - `$time.no_assumed_policy` makes every unstated policy an error.
- **Semantics taken:**
  - a range of a discrete type is empty when nothing lies inside;
  - `t.in_zone(z)` is total (the zone's own footer rule forward, local mean time back);
  - an integer times an on-grid tick is on the grid;
  - a proven-nonzero divisor gives a plain value;
  - every text reader gives `T | ParseError`, with `InvalidFields` a child;
  - no tag changes a result type; strict tags point to `strict_` functions;
  - `$time.require_*` becomes `$time.no_assumed_*`, `checked_add` becomes `strict_add`, and `$time.handle_uncertain_today` becomes `$time.no_unchecked_today`.
- **Questions for you:**
  - **Q1 (semantics; changes the accepted time design):** default gap and fold policies (Temporal's "compatible") in place of "never guesses". A literal that hits a gap or fold warns. Rec: yes. It is what Temporal, Python's `zoneinfo` and jiff do by default, and the union stays one argument away.
  - **Q2:** `$program.time_zone`, `$program.time_rules` and `$program.time_zone_source` replace `$time.zone`, `$time.rules` and `$time.zone_source`, and only the main file sets them. This narrows D15a. Rec: yes. It follows the `$program.*` rule and stops a library from compiling alone and failing when imported.
  - **Q3:** `.start`/`.end`/`.includes_start`/`.includes_end` replace `.first`/`.last`/`.includes_first`/`.includes_last` on `Range<T>`. Rec: yes. Arrays' `.first`/`.last` are members, and a half-open range's `.last` isn't one.
  - **Q4:** `Instant<width=64>` as a value parameter whose alias body is computed while compiling. Rec: yes. The fallback is `CompactInstant`.
- **Names for you** (cold read pending): `t.floor`, `t.ceil`, `t.round`, `z.at`, `strict_add`, `strict_in_zone`, `strict_elapsed`, the `$time.no_assumed_*` family, `$time.no_unchecked_today`, `$time.no_dropped_zone`. Tested before and kept: `time_of_day"…"`, `local"…"`, `fold='later'`, `d.at(t)`, the rounding names.
- **Reversible:** yes.

### D33. A type alias that names itself in a self-length refinement
Turn this on and a function can return a self-length array, which has no type name to write today.

```dewy
Parents:type = array<int64<(<? Parents.length)>>
make_parents = (n:int64<(>? 0)>):>Parents => {
    let p:Parents = [0]
    loop p.length <? n { p.push(p.length) }
    p
}
let tree = make_parents(5)
printl'{fmt'<8'"parents"} {tree}'                         # parents  [0 1 2 3 4]
```

- **Common path:** the alias, as a result type.
- **To adjust:** today the same contract works on a `let`, a parameter or a record field, so a function can fill one given by `@` or return it inside a record.
- **Semantics taken:** only a self-length refinement may refer to its own alias. Any other self-reference stays an error.
- **Rec:** add it when returning these arrays matters. It would be the first alias allowed to refer to itself this way. No new names.
- **Reversible:** yes.

### D34. A temperature difference type
Turn this on and passing a reading where a difference belongs is a compile error naming the fix, instead of silently counting from absolute zero.

```dewy
from units import ft, °F, °C, BTU, r_value_us, Area, ThermalResistance, TemperatureDifference
heat_loss = (area:Area rise:TemperatureDifference r:ThermalResistance) => area*rise/r
const wall = 25.0r_value_us
let rise = 70°F - 30°F                                      # a TemperatureDifference
printl'{fmt'.1f'(heat_loss(8ft*40ft rise wall) as BTU/hour)}'   # 512.0BTU/hour
printl(rise as °C)                                          # 22.(2)°C
printl(heat_loss(8ft*40ft 70°F wall))                       # compile error: 70°F is a reading; a difference is `70°F - 30°F` or `20K`
```

- **Common path:** bare dimension names, and exact values passed straight in.
- **To adjust:** `Area<rational>` keeps a value exact, and `20K` is a difference with no offset.
- **Semantics taken:**
  - an exact value rounds once into a float parameter, as it already does into a float `let`. Without that, this example doesn't compile;
  - D36's names default to `float64`;
  - a temperature difference prints as a decimal.
- **Rec:** add `TemperatureDifference`, and rename `RValue`, `R` and `RSI` to `ThermalResistance`, `r_value_us` and `r_value_si`. All four names were tested cold (2026-11-07), and the old ones failed.
- **Reversible:** yes.

### D35. `in_zone` on a zoned time, and a total `in_zone`
Turn this on and a zoned time shows the same moment in another zone directly, and showing a moment in a zone can't fail.

```dewy
$program.time_zone = 'America/New_York'
let slot = zoned("2026-11-01T09:00" zone=zone"America/New_York")
let berlin = slot.in_zone(zone"Europe/Berlin")             # a ZonedDateTime
printl'{fmt'weekday_short hour:minute zone'berlin}'        # Sun 15:00 Europe/Berlin
printl(slot.nominal.strict_in_zone(zone"Asia/Tokyo"))      # ZonedDateTime | OutsideCoverage, for the strict
```

- **Common path:** `slot.in_zone(z)`, with no union to handle.
- **To adjust:** `strict_in_zone` reports when the answer extends the zone's data past its last transition or before its first, and `$time.no_assumed_extrapolation` requires it.
- **Semantics taken:** `in_zone` uses the zone's TZif footer rule forward and local mean time back, both from the data itself.
- **Names:** `zoned_time.in_zone(zone)` was tested cold (all three correct). `strict_in_zone` is pending.
- **Rec:** add both.
- **Reversible:** yes.

### D36. Unit dimensions and the missing common units
Turn this on and `units` names the common dimensions and has the units a student or engineer reaches for first.

```dewy
from units import kW, kWh, lb, psi, mph, kcal, MB, MiB, Power, Energy, Information
Appliance:type = [name:string power:Power]                   # float64 power, any unit of power
let kettle = Appliance["kettle" 2.2kW]
let used:Energy = 1392kWh
printl'{used} {fmt'.1f'(150lb as kg)} {fmt'.0f'(32psi as kPa)} {fmt'.1f'(60mph as km/hour)}'   # 1392.0kWh 68.0kg 221kPa 96.6km/hour
let cap:Information = 512MiB                                 # 2^20 bytes each; 512MB is 10^6 each
```

- **Common path:** import a unit by its usual name. A value prints in the unit you wrote, and `fmt` keeps it.
- **To adjust:**
  - `x as unit` picks another unit;
  - `x / unit` gives the bare number;
  - `Area<rational>` keeps a value exact.
- **Semantics taken:**
  - the units in the list below;
  - SI prefixes on every SI unit, generated;
  - `Information` as a ninth base dimension, with `B = 8bit`;
  - `MB` means 10⁶ and `MiB` 2²⁰;
  - a quantity keeps its written unit;
  - nothing prints a unit you can't write: `minute` and `hour`, never `min` and `h`;
  - `10min` is an error naming `10minute`.
- **Names for you** (rec: yes; the cold read is pending except `Power` and `Pressure`):
  - **Dimensions:** `Area`, `Volume`, `Speed`, `Acceleration`, `Force`, `Energy`, `Power`, `Pressure`, `ThermalResistance`, `Information`, `Frequency`, `Charge`, `Voltage`, `Resistance`, `Density`, `Torque`.
  - **Units:** `lb oz stone short_ton long_ton tonne nmi acre hectare ha gallon_us gallon_uk quart_us pint_us pint_uk fl_oz_us cup_us mph knot kPa MPa hPa bar mbar atm psi mmHg inHg Wh MWh GWh cal kcal eV therm hp lbf standard_gravity C Ah mAh rpm bit B byte kB MB GB TB KiB MiB GiB TiB kbit Mbit Gbit`.
- **Reversible:** yes.

### D37. `fmt` patterns for dates, times, durations and units
Turn this on and a date or time pattern is written in words, so `hour:minute` can't print the month, and a number pattern keeps a quantity's unit. Each pattern is checked while compiling and decides what its function accepts.

```dewy
$program.time_zone = 'America/New_York'
const when = fmt'weekday day month_name, hour12:minute am_pm'     # formats dates with times
const money = fmt'>12,.2f'                                        # formats numbers
let meet = zoned"2026-11-07T21:05[America/New_York]"
let names = ["North" "Île-de-France"]
let w = max(names[0].length names[1].length)
printl'{when(meet)}'                                              # Saturday 7 November, 9:05 PM
printl'{fmt'year-month-day hour:minute offset'meet}'              # 2026-11-07 21:05 -05:00
printl'{fmt'<{w}'(names[0])}|{money(1234.5)}'                     # a computed width
printl'{fmt'.2f'(3.0303s)} {fmt'minute:second.millisecond'(91750ms)}'   # 3.03s 01:31.750
let stamp = instant("07/Nov/2026:05:15:31 -0500" 'day/month_short/year:hour:minute:second offset')
printl(stamp)                                                     # 2026-11-07T10:15:31Z
money("x")                                                        # compile error: fmt'>12,.2f' formats numbers; found string
fmt'HH:mm'                                                        # compile error: 'HH' is not a field. Did you mean fmt'hour:minute'?
```

- **Common path:**
  - `fmt'…'` once in a `const`, then call it;
  - the ISO default needs no pattern at all;
  - reading takes the same pattern as writing.
- **To adjust:**
  - interpolate members for an unusual padding (`'{d.day}.{d.month}.{d.year}'`);
  - divide by a unit for a bare number;
  - convert a pattern known only at run time with `DatePattern(text)` or `NumberPattern(text)`, which give the failure as a value.
- **Semantics taken:**
  - number patterns are Python's mini-language, as `format` had;
  - a number joined to another field by `- / . :` is two digits;
  - `hour12` needs `am_pm`;
  - `zone_short` writes but doesn't read;
  - the first field of a duration counts everything above it;
  - a hole in a pattern must be a count;
  - TR35 letters, `x.format(…)` and `format(x spec)` are gone;
  - `$time.no_dropped_zone` makes writing a zoned value without `offset` or `zone` an error.
- **Names for you** (rec: yes; the cold read is pending):
  - **Fields:** `year`, `month`, `month_name`, `month_short`, `day`, `weekday`, `weekday_short`, `hour`, `hour12`, `am_pm`, `minute`, `second`, `millisecond`, `microsecond`, `nanosecond`, `offset`, `zone`, `zone_short`.
  - **Kinds:** `TextPattern`, `NumberPattern`, `IntegerPattern`, `DatePattern`, `TimePattern`, `DateTimePattern`, `ZonedPattern`.
- **Reversible:** yes.

## 13. New or changed names, for the cold read

| Name | Intended meaning | Replaces |
|---|---|---|
| `Weekday`, `'monday'` … `'sunday'` | A day of the week as a name | `weekday` as `int64` from 0 |
| `d.iso_weekday` | 1–7, Monday first | |
| `d.next(w)` | The first given weekday strictly after `d` | |
| `d.nth_weekday_of_month(n w)` | The nth given weekday of `d`'s month; -1 is the last | |
| `born.next_anniversary(after=)` | The next birthday on or after a date | |
| `date(year month day)` | A date from numbers | |
| `time_of_day(hour minute second=0)` | A time of day from numbers | |
| `z.at(t)` | Same date and zone, another time of day | |
| `t.floor(tick)`, `t.ceil(tick)`, `t.round(tick)` | Round a time to a grid, giving the value | (`quantize` stays) |
| `strict_add`, `strict_in_zone`, `strict_elapsed`, `strict_zone` | The same call, with its failures as values | `checked_add` |
| `$time.no_unchecked_today` | `today` is an error; use `strict_today` | `$time.handle_uncertain_today` |
| `$time.no_assumed_*` (16 rows) | That assumption is a compile error demanding an explicit choice | `$time.require_*` |
| `$time.no_dropped_zone` | Writing a zoned time without offset or zone is an error | `require_loss` |
| `$program.time_zone`, `$program.time_rules`, `$program.time_zone_source` | Program-wide zone, rule pack, zone data source; main file only | `$time.zone`, `$time.rules`, `$time.zone_source` |
| `Range` `.start`, `.end`, `.includes_start`, `.includes_end` | The written bounds of a range and whether each is in it | `.first`, `.last`, `.includes_first`, `.includes_last` |
| `Instant<width=64>` | A 64-bit instant (ordinary parameter) | `Instant_width_64` |
| `CompactInstant`, `CompactDuration` | Fallback only, if Q4 is refused | |
| Pattern fields (§2.4) | Date and time fields in `fmt` patterns | TR35 letters |
| `TextPattern`, `NumberPattern`, `IntegerPattern`, `DatePattern`, `TimePattern`, `DateTimePattern`, `ZonedPattern` | The pattern kinds | `format` spec, `date_pattern_error` |
| `Information`, `bit`, `B`, `byte`, `kB` … `TB`, `KiB` … `TiB`, `kbit` … `Gbit` | Data sizes, SI and binary | |
| D36 dimensions and §7.1 units | As listed | `RValue`, `R`, `RSI` |

## 14. Changes for whoever lands this

- **time.md:**
  - Formats: replace with §2.
  - Zones: §8.1, §10.
  - Width: §6.
  - Intervals: §5.
  - Strictness: §8.3.
  - Remove "display returns text plus declared losses", `Name<option=N>` and the `$check_constant`/`$error_if` paragraphs inherited from v6 §3.
- **LANGUAGE.md:**
  - "Physical quantities": display (§3), `as`, units (§7).
  - Time: weekday, patterns, `in_zone`, rounding.
  - The `format` paragraph at line 4757 goes; `fmt` replaces it.
- **open_decisions.md:** §12's texts. Drop `$error_if` and `$check_constant` from D29.
- **lib:**
  - `lib/time/format.dewy` becomes the word validators and renderers. The stub in `time/stubs/fmtstub.dewy` shows the padding rule in 20 lines.
  - `lib/units.dewy` gets the additions.
  - `lib/ranges.dewy` gets the renames and `is_empty`.
  - The chooser in `lib/rational.dewy` gets the decimal rule.

## 15. Outside scope: bugs and gaps in today's compiler

1. **`fmt'.2f'x` doesn't parse:** the juxtaposed call reads as two expressions, both inside interpolation ("expected one interpolation expression") and outside it ("'s' needs arguments"). Repro: `time/probe/p5.dewy`, and `p1.dewy` before its edit. The interpolation error also still suggests `format(value ".2f")`.
2. **`10min` gives "'min' needs arguments: call it":** it should say `min` isn't a unit and name `10minute`. Repro: `time/probe/p2.dewy` with `let a = 10min` restored.
3. **The display prints units you can't write:** `printl(90minute)` prints `90min`. Repro: `time/probe/p2.dewy`.
4. **Comparing a union of strings with an integer** says "cannot compare string with int (text is not a number…)", suggesting `to_int`. For a literal union the message should list the members. Repro: `time/probe/p3.dewy` with line 6 restored to `=? 2`.
5. **`d.day`, `d.weekday` and the civil fields carry no ranges,** so `_DAYS[d.weekday]` and `d - (d.day-1)*1day` need `$runtime_checks`. Repro: `time/stubs/t_weekday.dewy` without its `$runtime_checks` lines.
6. **A bare generic alias in a parameter is an error** ("type 'Area' expects 1 type argument(s), got 0") even where a default would serve. Repro: `time/probe/p4.dewy` with `g = (a:Area) => a*2`.
7. **Already reported, still open:**
   - the checker panic on `(date"2026-12-01" - date"2026-11-01").total_days` (`~/dev/tmp/dogfood-1107/b/p08_crash_repro.dewy`);
   - `mean(array<Duration>)` errors from inside `lib/std/nd.jo`;
   - top-level `or_throw` is rejected;
   - `xs.map(…).max` over a constant array needs a nonempty proof (`time/p13_report.dewy` assumes the dogfood's fix, that `map` keeps the length, which belongs to whoever owns arrays).
