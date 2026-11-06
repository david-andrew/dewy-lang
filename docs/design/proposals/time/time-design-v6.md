# Time, dates, clocks and calendars (v6)

v6 applies David's batch 2 decisions ([decisions.md](../../decisions.md)) to v5 and closes what v5 §14 and the reviews left open. It lists only what changes: every v5 section not named here stands as written, with the renames below applied. The accepted text is [docs/design/time.md](../../time.md).

> **BLUF:**
> - **Decided by David:** 128-bit time by default with `width=64` as the compact form (D6); `ClockReading` with monotonic `-` (D7); compile-time literals (D8); `1day` and `1week` are `Period`s, with errors pointing to the right form (D9); `Gregorian`; `$dewy.version` replaces `$edition`; default rule data pinned to the Dewy version, `$time.rules` as the override; relative waits count actual time; a warning names the assumed zone.
> - **Also decided (D15a, b, d):** `$time.zone = 'America/New_York' | 'system' | 'build'` with `$time.zone_source = 'host'` as the opt-in to host rules; what `$dewy.version` promises; intervals as ranges.
> - **Provisional (D15c, D15e, D10):** `age` and `Date - Date`, the name of the careful `today`, and `$time.explicit_*` for `$time.require_*`: §2.
> - **Decided here under the two tests:** 128-bit overflow, the `Duration` carrier, how a literal becomes a value, `Date - Date`, how a library reads a caller's settings, and the shape of the rule data. §3 gives each with its reason.

## What changed from v5

| # | Area | v5 | v6 |
|---|---|---|---|
| 1 | Source version | `$edition = 2026`, E / E+1 / E+2 by year | `$dewy.version = '0.1.0'` per module; evolution contract restated on versions; no `$edition`, no alias |
| 2 | Rule data | `$time.rules = rules.iana_2026c`, required for literals | Default data pinned to the Dewy version; `$time.rules` only overrides; no `rules_2026`-style names |
| 3 | Zone | Host name captured; `$time.zone_source = 'host'` | `$time.zone = 'America/New_York' \| 'system' \| 'build'`, chosen at compile time; `$time.zone_source = 'host'` stays |
| 4 | No zone | Silently the host's | Warning names the assumed zone |
| 5 | `age` | `born.age(on=…)` | `age(born on=today)` (provisional) |
| 6 | `date - date` | A count of successors, unnamed type | A `Period` with `.years` and `.total_days` (provisional) |
| 7 | Intervals | `interval(a b)`, half-open | Dewy ranges `[a..b)`; `interval` dropped |
| 8 | Instant / Duration | "int128" | A two-word record, library-defined; layout unchanged (16 bytes, no heap) |
| 9 | Overflow | Unproved narrowing is a compile diagnostic | Plain 128-bit overflow is a reported environmental failure under a named assumption; `width=64` overflow is a value |
| 10 | Rejected | | `$edition`, `$build.edition`, `rules_2026`, `interval`, `.age(on=)` |

## 1. Applied decisions

### `$dewy.version`

- **Spelling.** `$dewy.version = '0.1.0'`, a statement at the top level of a module. As with every metatag, a statement sets it and an expression reads it. `$dewy` is a namespace, so later members can join it.
- **Scope.** Each module has its own. It is never inherited from an importer, and generics and plugins use their definition site's. The toolchain's version is what compiles; the module's version is what its bare names mean.
- **Form.** Three dotted decimal numbers in quotes. Anything else is a compile error at the value.
- **A newer version than the toolchain** is a compile error naming both, on a tagged toolchain. A development toolchain has no version of its own to compare, so it accepts any well-formed version.
- **Governs:** bare `Date`, `date"…"` and `today`'s calendar (`Gregorian` in every version so far); convention defaults such as the leap-day rule of `age`; the default rule data (below).
- **Never versioned:** J0, the meaning of a tick such as `1ns`, the TT-rate axis, integer-count meaning, and the plain `Instant` alias's wire identity.
- **Evolution contract.** A version V defines a default. A later version warns on every bare use whose meaning will change and offers the explicit spelling. A version after that may change the default, only for modules that declare it. At least one published version intervenes; the deprecation period is never inferred from years. There are no breaking removals: every later toolchain compiles every earlier version, as that version. If an old version turns out to have a serious security problem, the program still compiles, with a very obvious warning and the steps to fix it.

### Rule data

- **Default.** The data a Dewy version ships is what that version means: zone rules and the UTC segment table, generated source and bytes in `lib/time/rules/`. A program has no name to write for it. The artifact records the pack's identity.
- **Which version.** A module's own `$dewy.version` selects the pack its literals fold against. At run time the program uses its main module's. A tagged release keeps every earlier release's pack, so a stated version keeps meaning the same rules; packs are loaded on demand and shared where the data did not change. Before the first tagged release there is one pack.
- **Override.** `$time.rules = <descriptor>` names a pack declared in `.dewy` source, for urgent law changes or test data. `$time.zone_source = 'host'` follows the host's database at run time; a literal cannot fold against that, so it is a compile error naming the fix.
- **Unchanged from v5:** packs are immutable and identified, resolved values are frozen, appointments migrate explicitly, `ZonePackStale` is a status.

### Waits

Relative waits count actual time. `sleep`, `within`, TTLs and `reading + Duration` use suspend-inclusive monotonic time, so a laptop lid closed for an hour counts as an hour. `clocks.active` is the explicit alternative. This is v5 §7; only the wording of the choice changes.

### The assumed zone

An operation that needs a zone and has none (no argument, no `$time.zone` in scope) warns once per site, naming what it assumes:

```text
warning: `today` has no time zone here, so it assumes the zone of the machine it runs on.
  say so with `$time.zone = 'system'`, or name one: `$time.zone = 'America/New_York'`
```

With `$time.zone = 'Asia/Tokyo'` in scope the operation uses Tokyo and does not warn. `$time.zone = 'system'` says the same assumption out loud, and `$time.zone = 'build'` pins the zone of the machine doing the build. A compile-time literal cannot assume anything, so `zoned"2026-10-26T09:00"` with no zone in the text or the scope, or with `'system'` in scope, is a compile error.

## 2. Decided since the brief, and still provisional

Recorded on master after this round started, and applied here:

- **D15a.** The zone is chosen at compile time: a name pins the whole program, `'system'` is the zone of the machine running it, `'build'` pins the zone of the machine building it. Set in the main file, it holds in every module, and a different setting in an inner scope or another module is a compile error naming both. That reads "pins the whole program" literally, and rejecting is the easier one to loosen later. A program whose main file sets none may set zones in its modules and scopes. Rules are pinned at build unless `$time.zone_source = 'host'`. Unspecified means the running machine, with a warning naming the assumption.
- **D15b.** Once Dewy has settled and has a first release, a program tagged with a version always compiles with that version or any later compiler. Before that, the no-legacy rule stays. A version with a serious security problem still compiles, with a very obvious warning and the steps to fix it; there are no breaking removals, and nothing can be flagged until a version exists. No declaration compiles as the current version, with a warning and a fix-it. The warning is on where the toolchain's version is a tagged one and off on `-dev`, since until then there is no version to insert.
- **D15d.** Anything taking an interval uses range syntax, `[a..b)`.

Still open in [open_decisions.md](../../open_decisions.md), so built to be easy to change:

| # | Choice | Built as | To change it |
|---|---|---|---|
| D15c | `age(born on=today)`, and `Date - Date` gives a `Period` with `.years` and `.total_days` | A prelude function and an operator overload returning a `Span` | Replace those declarations |
| D15e | What replaces `today_support`, and its name: `possible_todays` (a query for the dates the clock allows) or `strict_today` (the union `today` gives under strict settings, the shape open_decisions.md recommends) | Not built, so neither shape nor name is depended on | Pick one when built |
| D10 | `$time.explicit_*` in place of `$time.require_*` | Neither is built yet; this file says `require` as v5 did | Rename when decided |

## 3. Decided here under the two tests

Each passes both tests of AGENTS.md rule 6: the common path is easy and fast, and adjusting is straightforward.

**128-bit overflow.** No program reaches ±5.39×10²¹ years by accident, and the library has no range facts about two record words. v5's compile diagnostic would fire on every `t + d`. So `Instant` and `Duration` arithmetic never carries an error branch: leaving the 128-bit range ends the task with a report, the path of other environmental failures, and is listed as an assumption. `$time.require_range` (row 18, in `$time.strict`) removes it, and `t.checked_add(d)` gives `Instant | OutOfRange` anywhere. `Instant<width=64>` is different, since 2269 is reachable: its arithmetic returns the value or `OutOfRange`, and conversion to it is `convert<Instant<width=64>>(t)`.

**The carrier.** The language has no `int128` and needs none. `Instant` and `Duration` are records of a signed high word and an unsigned low word, written in Dewy, with the layout v5 specified. Add and subtract are a word add, a carry compare and a second add, about five instructions rather than two: still one basic block, with no call and no allocation. Multiply, divide and formatting go through `int`, which stays in a word for the ranges they usually see. This is an internal representation, so it can move to a builtin later without a source change.

**`Duration` and time quantities.** Existing time quantities (`300ms`, `2s`, `0.1s`, `1ns/3`) stay exact quantities. A `Duration` is the on-grid stored form. A quantity meets a `Duration` or an `Instant` directly: `t + 90minute`, `d <? 5s`, `d / 1s`. A constant off-grid quantity in that position is a compile error with fix-its. A runtime one goes through `convert<Duration>(q)`, which gives `Duration | OffGrid | OutOfRange`. A float time enters by `quantize`. `(now - start) / 1s` is a `rational`, and `as float64` is one conversion.

**How a literal becomes a value.** `instant"…"`, `date"…"`, `zone"…"`, `zoned"…"` and `utc"…"` use the mechanism `regex` already uses: a function states a validator, and a constant argument runs it at compile time. Text back is a compile error at the argument; none drops the exception members from the result type. v6 adds one step: a call that passed and returns a plain record is folded to its value, so the literal costs nothing at run time. The library's own parser is the only parser. A mission's `sclk"…"` gets the same treatment by declaring the same thing.

**Interim until string shapes (D11).** The validator check is the interim mechanism for the literals: [string-shapes/round1.md](../string-shapes/round1.md) proposes `string<shape=@date_error>` to replace it, and that waits on David, so it is not built here. `date_error`, `instant_error`, `utc_error` and `zone_error` already have the contract that proposal asks for, `(text:string):>string?`: none when the text is fine, otherwise what is wrong. They read bytes in a loop, since `text.split` does not run at compile time yet. Porting means replacing each `$check_constant` line with a shaped overload (`date = ((t:DateText):>Date=>…) & ((t:string):>Date|ParseError=>…)`) and leaving the validators alone. Until then a runtime string reaches `date` as a `string` and gets `Date | ParseError`, which is the same result the `string` overload would give. In `.dewy` the attribute is spelled `$check_constant validator(text) "message"`, library-facing and removed with the port. The extensions time needs (several parameters, closed non-string arguments, folding a plain record, `$error_if`) are not part of that proposal: the port has to keep or replace each one.

**`Date - Date`** is a `Span`, a `Period` that knows its anchor: `.total_days` counts calendar successors, so `a + (b - a) =? b` always holds and a British-calendar difference skips what the calendar skips, and `.years`, `.months`, `.days` decompose it by completed anniversaries and months (a 29 February start counts on 1 March, as `age` does). `(b - a) / 1day` is the integer count of days.

**Reading a caller's settings.** `$time.gap`, `$time.fold`, `$time.zone` and `$calendar` belong to the code calling a library, which has its own scope. The rule: a metatag read in a parameter's default is read at the call site. `today = (scope=$time.zone) => …` is an ordinary function. A caller can always pass the argument. This is a reusable primitive, so nothing here is special to time.

**Rule data format.** A pack is bytes reached through `$include_bytes`, read by library code at compile time and at run time. Only a program that reaches a zone operation links them. A stopwatch or a date-only program pulls in none. Generated `.dewy` tables were the alternative, but a 600-zone table would be parsed on every build that names one zone.

**Errors that point to the right form.** `sleep(1day)` and `instant + 1day` must be compile errors with a fix-it, and no overload should quietly accept them. A declared overload carrying `$error_if true "…"`, the sibling of `$warn_if`, says so in the library. Resolution picks it, and the checker reports the message at the call.

**`Duration` printing** uses the rule of the unit chooser (`125ms`, `90min`, `169h`, `0s`), reimplemented over the two words because the chooser works on quantities.

## 4. Spelling inventory changes

**New in v6:** `$dewy.version`, `$time.zone`, `$time.require_range`, `checked_add`, `Span` with `.total_days`, `.years`, `.months`, `.days`, `$error_if` and a Dewy spelling of `$check_constant` (library-facing), `'system'` and `'build'` as values of `$time.zone`.

**Removed:** `$edition`, `$build.edition`, `interval`, `.age(on=)`, every `rules_YYYY` and `iana_YYYYx` name in examples.

**Now settled (no longer proposals):** `Gregorian`, `ClockReading`, `width=`, the literal calls, `Period`, `1day`, `1week`, `$time.rules`, `$time.gap`, `$time.fold`.

**Still provisional, per the decisions:** `UtcLabel`, `ClockObservation`, `observe`, `Resolution`, `ClockDiscontinuity`, `OffGrid`, `ZonePackStale`, `Coordinate<Scale>`, `instant(text)`, and the rest of v5's inventory not listed above.

## 5. Examples changed from v5

```dewy
# §5: age and differences (D15c, provisional)
let years = age(date"2000-05-12" on=date"2026-10-24")   # 26
let leap = age(date"2000-02-29" on=date"2027-02-28")    # 26 (the march_1 rule)
let gap = date"2026-12-25" - date"2026-10-24"           # 62day
printl"{gap.total_days} days to go"                     # 62 days to go
let since = date"2027-02-28" - date"2000-02-29"
printl"{since.years} {since.total_days}"                # 26 9861

# §6, Examples 3 and 13: intervals are ranges
let window = [instant"2027-01-01T00:00:00Z"..instant"2028-01-01T00:00:00Z")
let season = [instant"2026-03-01T00:00:00Z"..instant"2026-12-01T00:00:00Z")

# Example 10: an override instead of a named default
import p"urgent_rules.dewy" as urgent
$dewy.version = '0.1.0'
$time.rules = urgent.brazil_2027      # only because of an emergency law change
```

## 6. Order of delivery

1. `$dewy.version`.
2. Core: `Instant`, `Duration`, the UTC segment table, literals, arithmetic, RFC 3339 display.
3. Civil: `Date<Gregorian>`, `TimeOfDay`, `LocalDateTime`, `Offset`, `Period`, `age`.
4. Zones: `Zone`, `ZonedDateTime`, the rule pack, gaps and folds, the zone warning.
5. Clocks: `ClockReading`, `MonoPoint`, `now`, `monotonic`, `today`, waits, replacing the old prelude `Date` and `now()`.
6. Formatting and parsing beyond RFC 3339.
7. Ranges as intervals, recurrence, `$time.require_*`, `time.science`: later runs.
