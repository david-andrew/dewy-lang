# Time and Dates

> [Generated coverage](/status/#ref-time-and-dates) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Time needs no import. The prelude provides the clocks (`now`, `monotonic`, `today`), `sleep` and `within`, the types `Instant`, `Duration`, `Date` and the zoned and local times, and the literal forms `instant"…"`, `date"…"`, `zoned"…"`. Time quantities such as `300ms` are covered in [Physical Quantities](physical-quantities.md).

## Clocks

`now` is two clock samples: a monotonic one and the wall clock.

- `now - start` is elapsed time on the monotonic clock, which a wall-clock step cannot move.
- `now + 5s` is a deadline on that clock; `now <? deadline` compares monotonic samples.
- `now.nominal` is the wall-clock `Instant`. Keep that one: a reading has no meaning in another run.
- `monotonic` is the monotonic sample alone.
- `today` is the date in the scope's zone (see [Zones](#zones)). It warns when no zone is set. `strict_today` is `Date | AmbiguousToday | UnknownToday`, for a clock whose error bound spans midnight or is unknown.
- After `import time`, `time.elapsed(@work)` calls a zero-argument procedure once and returns the monotonic `Duration` it took.

`sleep`, `within` and deadlines count actual time, including time the machine is suspended. `sleep` can be cut short by cancellation, so its result is handled or discarded with `;`. `within(limit @f)` gives `f`'s result or `Timeout`.

<!-- dewy-example: {"mode":"run","stdout":"true\ntrue\ntrue\ntrue\ntrue\n"} -->
```dewy
import time
pause = ():>void => { sleep(20ms); }
slow = ():>int => { sleep(200ms); 42 }
main = () => {
    let start = now
    sleep(10ms);
    printl(now - start >=? 10ms)
    let deadline = now + 30ms
    loop now <? deadline { sleep(5ms); }
    let seconds = (now - start) / 1s as float64
    printl(seconds >? 0.03)
    printl(now.nominal >? instant"2026-01-01T00:00:00Z")
    printl(time.elapsed(@pause) >=? 20ms)
    printl(within(50ms @slow) is? Timeout)
}
```

The program checks each clock provider at entry, and only when it reaches a clock operation. A lost wall synchronization shows in a reading's status: printing it adds `? (unsynchronized)`. An unknown accuracy adds `?`, and a failed later wall read keeps the last sample and prints `? (stale)`.

## `Instant` and `Duration`

An `Instant` is a count of nanoseconds on one continuous axis, held in 128 bits: it reaches any date anyone needs (±5.39×10²¹ years). A `Duration` is the difference of two.

- `+` and `-` take durations and time quantities: `t + 90minute`, `d <? 5s`. Comparing with an exact quantity never rounds it: `d <? 1ns/3` is exact.
- A constant time is a `Duration` where one is wanted: `let total:Duration = 0s`, `f(90s)`, `totals.get(k) ?? 0s`. A value known only at run time goes through `convert<Duration>`.
- `d/1s` is an exact `rational`; `d/3` is an exact quantity; `d//7` is a `Duration`. A runtime divisor may be zero, so that result can also be `OutOfRange`; a constant zero is a compile error.
- A constant quantity off the nanosecond grid (`t + 1ns/3`) is a compile error. At run time such a sum is `Instant | OffGrid`.
- `t.checked_add(d)` gives `Instant | OutOfRange`. Plain arithmetic that leaves the 128-bit range ends the program with a report.

<!-- dewy-example: {"mode":"run","stdout":"2026-10-24T13:30:00Z\n90 3/14min 12857142857ns\n90s true\n"} -->
```dewy
let t = instant"2026-10-24T12:00:00Z"
printl"{t + 90minute}"
let el:Duration = 90s
printl(el/1s el/7 el//7)
let total:Duration = 0s
total = total + 90s
printl(total total >? 1ns/3)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"off the nanosecond grid"} -->
```dewy
let t = instant"2026-10-24T12:00:00Z"
let u = t + 1ns/3
```

### Ticks and widths

A stored time can name its own positive, exact tick: `Instant<tick=1ns/3>` counts thirds of a nanosecond from the same epoch, and `Duration<tick=1ns/3>` stores differences on that grid. Equivalent ticks name the same type. Comparisons across grids are exact.

`width=64` selects an eight-byte count: `Instant<width=64>` covers September 1684 to April 2269. Its arithmetic gives the value or `OutOfRange`.

- `as` converts when the value or the source type proves it fits (`packed as Instant` widens).
- `convert<T>(x)` checks at run time and gives `OffGrid` for a fractional count or `OutOfRange` for one beyond the width. For a constant, a failure is a compile error.

<!-- dewy-example: {"mode":"run","stdout":"1/3ns\ntrue\n2026-10-24T12:00:00Z\n"} -->
```dewy
const t = instant"2026-10-24T12:00:00Z"
let start = t as Instant<tick=1ns/3>
let finish = start + 1ns/3
printl(finish - start)
printl(convert<Instant>(finish) is? OffGrid)
printl(convert<Instant<width=64>>(t))
```

### Rounding to a grid

`quantize(x rounding=… tick=…)` puts a time on a grid and returns `[value loss]`, where the original is the value plus the signed loss. `rounding` is `'nearest_even'`, `'nearest_away'`, `'floor'`, `'ceil'` or `'toward_zero'`; the tick is `1ns` unless given. A float time enters only through `quantize`, with `OutOfRange` for NaN and the infinities.

`t.ticks(tick)` counts down to a grid: `[count remainder]`, with the remainder at least zero and below the tick.

<!-- dewy-example: {"mode":"run","stdout":"0s 1/3ns\n[2026-10-24T12:00:00Z 750ms]\n-1 750ms\n"} -->
```dewy
let [d lost] = quantize(1ns/3 rounding='nearest_even')
printl(d lost)
printl(quantize(instant"2026-10-24T12:00:00.75Z" rounding='floor' tick=1s))
let span:Duration = -0.25s
let [count rest] = span.ticks(1s)
printl(count rest)
```

An `Instant` tick above a second counts on the UTC clock, so `tick=1minute` lands on `:00`.

## Literals and Parsing

`instant"…"`, `utc"…"`, `date"…"`, `time_of_day"…"`, `local"…"`, `zone"…"` and `zoned"…"` with constant text are checked while compiling. A date that does not exist, a leap second that never happened, or a local time in a daylight-saving gap or repeated hour is a compile error that says what to write. A passing literal is a plain value.

<!-- dewy-example: {"mode":"reject","diagnostic":"not a date: 2026-02 has no day 30"} -->
```dewy
let d = date"2026-02-30"
```

The same calls on runtime text return the failure as a value: `instant(text)` is `Instant | ParseError | InvalidFields | OffGrid | OutsideCoverage`.

<!-- dewy-example: {"mode":"run","stdout":"2026-10-24T13:00:00Z\ncannot read 2026-13-01T00:00:00Z: month 13 is not 1 to 12\n"} -->
```dewy
show = (text:string):>void => match instant(text) {
    t:Instant => printl(t + 1hour)
    e:ParseError => printl("cannot read {text}: {e.message}")
    _ => printl("cannot use {text}")
}
main = () => {
    show("2026-10-24T12:00:00Z")
    show("2026-13-01T00:00:00Z")
}
```

`Duration(text)` reads one number and one unit, as a duration prints or a time literal is written (`90s`, `250ms`, `1.5hour`), giving `Duration | ValidationError`. A day is a calendar period and is refused.

<!-- dewy-example: {"mode":"run","stdout":"90min 250ms\nis a calendar period, whose length depends on the date: give hours, like 24hour\n"} -->
```dewy
printl(Duration("1.5hour") Duration("250ms"))
let r = Duration("1day")
if r is? ValidationError { printl(r.message) }
```

`utc"…"` keeps a `:60` label; `.nominal` gives its instant. A UTC label before 1961 is outside coverage, and such an `Instant` prints as a TT label.

## Calendar Periods

`1day`, `1week`, `1month` and `1year` are calendar periods, not lengths of time: they need a date or a zoned time.

- `date + 1day` is the next calendar day.
- `date + 1month` is `Date | InvalidDate`, since not every month has a 31st. `.add(1month overflow='clamp')` takes the month's last day; `overflow='next'` the first of the next month.
- `date - date` is a `Period`. Its `.total_days` is an exact `int`; `.years`, `.months` and `.days` count completed anniversaries and months.
- `age(born on=date)` counts completed anniversaries, to `today` when `on` is left out. A 29 February birthday counts on 1 March in a common year, or pass `leap_day='february_28'`.
- Mixed periods compose in order: `1month + 2day` and `2day + 1month` are different recipes.
- On a zoned time, a period keeps the local time; an exact length of time (`168hour`) keeps the elapsed time.

<!-- dewy-example: {"mode":"run","stdout":"2027-02-01 2027 Sunday\n2027-02-28 2027-03-01 true\n62\n9916 27 1 23\n26\n2026-11-02T09:00:00-05:00[America/New_York]\n2026-11-02T08:00:00-05:00[America/New_York]\n169h\n"} -->
```dewy
let d = date"2027-01-31"
printl"{d + 1day} {d.year} {d.weekday_name}"
printl(d.add(1month overflow='clamp') d.add(1month overflow='next') (d + 1month) is? InvalidDate)
printl((date"2026-12-25" - date"2026-10-24") / 1day)
let p = date"2027-03-15" - date"2000-01-20"
printl(p.total_days p.years p.months p.days)
printl(age(date"2000-02-29" on=date"2027-02-28"))

const meet = zoned"2026-10-26T09:00[America/New_York]"
printl(meet + 1week)                         # the same local time
printl(meet + 168hour)                       # exactly 168 hours
printl((meet + 1week).nominal - meet.nominal)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"a day or week is a calendar period"} -->
```dewy
sleep(1day);
```

## Zones

A `ZonedDateTime` is an instant with a zone. It reads as `.date`, `.time_of_day`, `.local`, `.year`, `.month`, `.day`, `.hour`, `.minute`, `.second`, `.nanosecond`, `.weekday` (0 is Monday) and `.offset`, a fixed UTC offset to the second. `t.in_zone(z)` shows an `Instant` in a zone.

A `TimeOfDay` (`time_of_day"09:30"`) and a `LocalDateTime` (`local"2026-11-01T01:30"`, `d.at(t)`) have no zone and so no moment yet. `l.in_zone(z …)` gives the moment.

<!-- dewy-example: {"mode":"run","stdout":"2026-10-24T14:00:00+02:00[Europe/Paris]\n2026-10-24T09:30:00\n2026-11-01T01:30:00-05:00[America/New_York]\n"} -->
```dewy
let paris = zone"Europe/Paris"
printl(instant"2026-10-24T12:00:00Z".in_zone(paris))
printl(date"2026-10-24".at(time_of_day"09:30"))
printl(local"2026-11-01T01:30".in_zone(zone"America/New_York" fold='later'))
```

### Gaps and repeated hours

A local time in a daylight-saving gap or repeated hour, or a zoned add that lands in one, gives `ZonedDateTime | Gap | Ambiguous`. Naming the policies makes it a plain `ZonedDateTime`:

- `fold='earlier'` or `'later'` for a repeated hour; `fold='all'` returns every reading, in instant order.
- `gap='preserve_displacement'` (02:30 in a one-hour gap becomes 03:30), `'next'` (03:00), or `'skip'` (`none`).

Policies are arguments (`zoned(text zone=z fold='later')`) or settings for a scope: `$time.fold`, `$time.gap`, `$time.zone`.

<!-- dewy-example: {"mode":"run","stdout":"2026-11-01T01:30:00-04:00[America/New_York]\n2026-03-08T03:00:00-04:00[America/New_York]\n[2026-11-01T01:30:00-04:00[America/New_York] 2026-11-01T01:30:00-05:00[America/New_York]]\n"} -->
```dewy
resolve = (text:string):>void => {
    $time.zone = 'America/New_York'
    $time.fold = 'earlier'
    $time.gap = 'next'
    printl(zoned(text))
}
main = () => {
    resolve("2026-11-01T01:30")
    resolve("2026-03-08T02:30")
    printl(zoned("2026-11-01T01:30" zone=zone"America/New_York" fold='all'))
}
```

### The scope's zone

`$time.zone = 'America/New_York'` at the top of the entry file sets the default zone. At the top of a function or block it sets the zone for that scope's calls and tasks, and the caller's policy returns afterwards. `'system'` reads the machine's zone when the program runs; `'build'` pins the zone of the machine building it. `today` and `zoned(text)` on text with no zone use the scope's zone, and with none set each warns, naming what it assumes. A machine with no zone to read reads as UTC, and the program says so once.

Zone rules are not the machine's: each Dewy version ships its own IANA data, so a program means the same thing anywhere, and links them only if it reaches a zone operation. `$time.rules = 'urgent.bin'` names a rules pack beside the entry file, and `$time.zone_source = 'host'` follows the machine's zone files instead.

## Formats

`x.format(pattern)` writes a value by Unicode's date pattern letters, in English: `y` year; `M`, `MM`, `MMM`, `MMMM` month; `d` day; `EEE`, `EEEE` weekday; `H` hour; `h` and `a` twelve-hour hour and AM/PM; `m`, `s`; `S` fraction digits; on a zoned time `XXX` and `XXXXX` offset and `VV` zone name. Other letters go in quotes (`'T'`). A letter the value has no field for is an error, at compile time for a constant pattern. An `Instant` writes in UTC.

`date(text pattern)`, `time_of_day(text pattern)` and `local(text pattern)` read all of the text by the same letters, with no guessing: `yy` is not a form.

<!-- dewy-example: {"mode":"run","stdout":"Sunday 31 January 2027\n2026-10-24\n21:05:00\n"} -->
```dewy
printl(date"2027-01-31".format("EEEE d MMMM y"))
printl(date("24/10/2026" "d/M/y"))
printl(time_of_day("9:05 PM" "h:mm a"))
```

## Intervals

An interval is a range: `[a..b)`, `[a..b]`, `(a..b]`, `(a..b)`. Over an `Instant`, a `Date` or another ordered non-integer type it is a `Range<T>` holding its two ends as written, with `.first`, `.last`, `.includes_first`, `.includes_last` and `.is_empty`. `x in? r` tests it.

A `Date` range loops by calendar days (provisional). Other ordered ranges cannot be walked. `ranges.intersection`, and `intervals.measure`, `intervals.same_set`, `intervals.union` and `intervals.difference` for `Range<Instant>`, come from `p"@lib/ranges.dewy"` and `p"@lib/time/intervals.dewy"`.

<!-- dewy-example: {"mode":"run","stdout":"2024-02-28 2024-02-29 2024-03-01 \ntrue\n"} -->
```dewy
loop d in [date"2024-02-28"..date"2024-03-02") { print"{d} " }
printl()
printl(instant"2026-10-24T12:00:00Z" in? [instant"2026-01-01T00:00:00Z"..instant"2027-01-01T00:00:00Z"))
```

## Not Built

The accepted design (`docs/design/time.md`) also has a `time.civil` layer with recurrence and appointments, a `time.science` layer for scales, ephemerides and codecs, and strictness settings such as `$time.strict` that remove each convenience assumption. None of these is built yet.
