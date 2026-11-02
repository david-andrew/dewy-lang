# Critique of time-design-v4

Read-only review. v4 is the draft under `docs/design/proposals/time/time-design-v4.md`. David's notes after v4 are closed: `Instant` is an integer tick count, the epoch is J0 (`e = 0`), `now` is lightweight and written without parentheses, and empty `@f()` partials are pointless. The committed direction in `docs/design/time.md` is only the one-timeline sketch; this review judges v4.

Numeric checks below were done with exact rationals. Binary64 is the wrong tool for these constants: `32.184 * 1e9` in float64 prints `32183999999.999996`.

## BLUF

- Plain `Instant` is a signed **128-bit count of nanoseconds** since J0 (`1977-01-01T00:00:32.184 TT`, `e = 0`). The meaning is that integer. It does not hide a rational, and it does not grow a denominator.
- `1ns/3`, NTP binary fractions, PTP's fractional-nanosecond correction, and TT↔TCG leave that grid. They stay on their own tick or on a science `Coordinate<Scale>`. They never widen `Instant`.
- `now` returns a **32-byte reading with no pointers**. `now - start` is monotonic elapsed (one `int64` subtract). Wall time is `.nominal`. A leap offset is one cached integer. No zone table, estimate, or ephemeris is touched.
- Literal calls `instant"…"`, `date"…"`, `zoned"…"` are checked at compile time and are infallible when the value is unique. Gaps, folds, and unknown runtime strings stay fallible. `or_throw` belongs on that boundary, not on every civil line.
- The default calendar changes by **edition**. Public signatures spell `Date<Gregorian>`. `$calendar` overrides one scope. Stored dates name their calendar. The epoch, the nanosecond, and the TT-rate axis are not versioned.
- A negative leap is a skipped label in the UTC segment table, the same shape as a spring-forward gap. No separate feature. The 27 historical positive leaps stay. Continuous UTC from **20 May 2027** is one more segment.
- `1day` / `1week` / `1month` / `1year` are calendar periods. Fixed lengths are `24hour` and `168hour`. `sleep(1day)` is a type error.
- Keep v4's scale/realization split, UTC segments, Period vs Duration, pinned packs, and the refusal to guess a fold. Rewrite v4's BLUF: it still says rationals, `now()`, and the Apollo epoch.
- Several later rules (dense axis, cross-tick hashing, "no next instant") describe a rational `Instant`. On a 1 ns grid they are false.
- No new keywords. New surface is library names, the `$calendar` metatag, and an edition key in the project file.

## Retain from v4

These are right and should survive the rewrite:

- Scale, realization, epoch, representation, and format are independent. `Instant` is an ideal TT-rate axis, not a claim about realized TAI, proper time, or simultaneity.
- UTC is a versioned segment table: pre-1972 rates, integer leaps, then continuous UTC. No `if year >= 2027`.
- `Period` is a calendar recipe. `month` and `year` never become durations. RFC 5545 is a profile, not the core.
- Folds and gaps are not repaired unless a named policy says so. Abbreviations are candidates. Locale is not a location.
- Packs are immutable and pinned. Kernel pools and tzdata are not process-global mutable state.
- `sleep` / `within` use a monotonic domain. Wall steps are not clamped. Test clocks advance a captured provider.
- The 17 `$time.require_*` obligations are a sound inventory for `$bulletproof`, provided they are compile-time flags with zero cost when absent.
- Exact affine definitions (TT↔TCG, TCB↔TDB, including the inverse divisors) stay in the science layer.

---

## Critique

### 1. Plain `Instant` is still specified as a rational

**Problem.** §1 says a value "means exact rational seconds" stored as `n × τ`, and that plain `Instant` "admits every finite rational" by minting a tick `1s/D`. That is a rational with a variable denominator. David closed this: an `Instant` is an integer count of ticks, not a rational. The BLUF, the tick section, decision 8, and the acceptance line about `1ns/3` all still describe the rejected type.

**Why it matters.** Performance is the first priority. A variable-denominator instant allocates, makes equality and hashing non-uniform, and pulls big-integer division into `now - start`. It also fails least surprise: `instant + 1ns/3` would silently change the result's tick, so two instants that look like the same type would not share a register layout. C++ `duration<Rep, ratio>`, `java.time.Instant`, and Temporal's nanosecond instant all picked a fixed integer quantum for this reason. Nobody who has operated a civil time library kept a rational as the default instant.

**Fix.**

- `Instant` means `Instant<tick=1ns width=128>`: one signed integer `n`, meaning `n` nanoseconds after J0.
- Width and tick are independent parameters, but every tick has a default width. Rule: use 64 if the half-range is at least 10^6 years, otherwise 128.

| Form | Half-range |
|---|---|
| `int64` × 1 ns | ±292 years (about 1685..2269). This is the next year-2038. |
| `int128` × 1 ns | ±5.4×10^21 years |
| ±10,000 years at 1 ns | 70 bits. `int64` cannot. `int128` can. |
| ±10^6 years at 1 ns | 76 bits. Still `int128`. |
| `int64` × 1 µs | ±2.9×10^5 years, but it throws away POSIX nanoseconds. |

- Do not store plain `Instant` as Dewy's unbounded `int`. The ABI is 16 bytes, inline, no heap, overflow is `OutOfRange`. Unbounded `int` reintroduces a tag and a hidden allocation on the type everyone passes around.
- `Instant<tick=1ns width=64>` is an explicit packed form for arrays of contemporary timestamps. Storing year −500 in it is `OutOfRange`.
- Hash and `=?` inside one tick are integer operations. Two ticks are two types. Cross-tick `=?` is an exact `as` when the source quantum lands on the destination quantum. There is no shared rational hash. v4's "equivalent coordinates hash identically regardless of tick" is the rational design coming back through the hash table.
- A femtosecond or hybrid tick (`1s / (2^32 × 5^9)`, which can hold both nanoseconds and NTP's 32-bit fraction) was considered and rejected. Femtoseconds still cannot hold `1ns/3`, NTP's `2^−32`, or `L_G`. A hybrid quantum is unreadable and still cannot hold TT↔TCG. Native ticks belong on the codec types.

```dewy
let t:Instant = instant"2026-10-30T20:00:00Z"   # infallible; n × 1ns
let packed:Instant<tick=1ns width=64> = t as Instant<tick=1ns width=64>
let ancient = instant"-2000-06-15T12:00:00Z"    # fits in 128 bits; not in 64
```

### 2. `now - start` is specified as wall time, and the value is too fat

**Problem.** The trivial example is elapsed time ("took 125ms"), but §7 and the `WallTime` arithmetic define `reading − reading` as a difference of **nominal** coordinates. `ClockReading` also carries source identity, an acquisition bracket, a correlation edition, an `Estimate`, and display context. `ZonedDateTime` keeps a resolution trace. v4's "pay only for what you use" is a comment on top of a fat object. `let deadline = now + 5s` is defined as a wall target.

**Why it matters.** `now` is the most common call, and games are a primary customer (`docs/GOALS.md`). A heap estimate or a zone pointer on that path loses to a C `timespec` before any algorithm runs. Go already learned the semantic half: `Time.Sub` uses the monotonic sample when both sides have one, and the bugs are all from that fact being **invisible** (`Add`, JSON, and `==` strip it). v4 copies the bug and skips the fix. A wall difference across an NTP step lies about elapsed work. A wall `now + 5s` fires early or late across suspend and across a step.

**Fix.**

- `ClockReading` is 32 bytes, inline, no pointers, no estimate, no zone, no locale:

  - `nominal: int128` — TT nanoseconds since J0
  - `mono: int64` — ticks of the captured monotonic provider
  - `generation: uint32`
  - `status: uint8` — synced, slew, step, holdover, stale, unsynced, accuracy unknown

- One sample pairs wall and mono (the Go runtime's offset technique: one monotonic read plus a cached wall offset). Already-captured readings keep their mono counts.
- `now - start` subtracts `mono` when generations match, and returns `DomainMismatch` when they do not. The result is an unboxed integer duration. For two readings in one boot it fits in `int64`.
- `now.nominal - start.nominal` is the wall difference on the TT axis. It is allowed to be negative.
- `now + 5s` is a **monotonic deadline**. A wall appointment is `now.nominal + 5s` or a zoned literal.
- Printing a reading shows the wall label, plus `~` / `?` from the status byte. The contract, stated in the trivial tier, is: it prints as wall time; differences measure elapsed time. The type change at `.nominal` is what Go never showed.
- `reading.estimate` and `reading.detail` build a science object on demand from the provider's current error bound. They are not stored in the reading.
- A deserialized timestamp is an `Instant` or a `ZonedDateTime`, never a `ClockReading`. Elapsed subtraction cannot silently become wall subtraction after a round trip.
- `time.elapsed(@job)` stays, as the closure form of the same mono subtract. It is not the only way to spell elapsed time.
- `today` returns a `Date` from the nominal instant in the captured zone. Ambiguous civil midnight is a status query, `today.support`. `$time.require_clock_accuracy` is what forces the union. A healthy program does not match on `AmbiguousToday`.
- `TemporalContext` is an integer handle. Locale, calendar, and zone packs are not loaded to construct it.
- Do not acquire clocks at process entry. First `now` or `sleep` opens the provider and caches it. A pure program links none of this. v4's "validate at entry" and "pay only for what you use" currently contradict each other. `$time.require_context` is the mode that moves the failure to entry.

```dewy
let start = now
work
printl"took {now - start}"          # mono int64; prints 125ms
let deadline = now + 5s              # monotonic deadline, not a wall target
let wall = now.nominal + 5s          # TT-axis instant; NTP can move this
sleep(300ms)
printl"today is {today}"
```

`ZonedDateTime` is `Instant` plus a `uint32` zone id plus the resolved offset in seconds (or nanoseconds). The transition table lives in the pinned pack, not in the value. Copy is a register move. jiff's `Zoned` is not `Copy` because it owns a `TimeZone`; do not inherit that layout.

### 3. Off-grid math has nowhere honest to go once `Instant` is an integer

**Problem.** v4 keeps exactness by refining the tick (`1ns/3` becomes a finer rational instant; an epoch shift may leave the binary grid). After note 1 that escape hatch is gone, and v4 never says what the operations return instead. §3 also says the axis is dense, so there is no next instant and a closed end cannot be rewritten as half-open by adding one nanosecond. That is true of a rational and false of a 1 ns grid.

**Why it matters.** This is the whole of David's first note: `1ns/3`, epoch shifts, codecs, range versus width, and `Instant<tick=…>`. Getting the default integer right and leaving the operations unspecified just moves the rational into every conversion.

**Fix.** See note 1 for the full table. The type rules:

- A duration whose magnitude is an integer number of the destination tick adds exactly: `300ms`, `1hour`, `1ns`, `24hour`.
- A duration that is not on the grid is a compile error when the remainder is a constant (`1ns/3`, `1s/3`), with a fix-it pointing at `quantize`. A runtime remainder returns `OffGrid`. The result type does not change tick.
- Science conversions that are exact rationals but not on the nanosecond grid return `Coordinate<Scale>`, a rational seconds count **branded with the scale**, used only from the science module. `as Instant` is exact when the rational is an integer number of nanoseconds; otherwise it is `quantize` or `OffGrid`.
- On `Instant`, the successor exists: `next(t) = t + 1` tick. Half-open `[a, b)` and closed `[a, b]` are different spellings of the same set of instants only after that successor rewrite, and that rewrite is legal. It stays illegal for `Coordinate` and for calendar days. v4's "no next instant" paragraph must be restricted to those two.
- Default interval convenience stays half-open. Store endpoint flags when the element type is dense or calendar-based. For `Interval<Instant>`, flags are optional sugar over integer endpoints.

```dewy
let t = now.nominal
let ok = t + 300ms                          # exact: 300ms is 3×10^8 ns
# t + 1ns/3                                 # compile error: OffGrid
let exact = (t as Coordinate + 1ns/3) as Instant<tick=1ns/3>
let [near loss] = exact.quantize(tick=1ns rounding='nearest_even')
```

`exact` is the sum on a tick the caller named, and it is not an `Instant`. `quantize` then lands on the nanosecond grid and reports the signed loss.

### 4. Literal civil time is specified as a runtime parse

**Problem.** §5's worked block ends almost every line in `or_throw`, including `date"2027-01-31"`, `age` of two dates, and a zone id that is a constant. v4 mentions compile-time discharge in one bullet and then does not use it. Dewy already checks literal `regex` patterns at compile time (`docs/design/decisions.md`). Time literals are the same situation and a worse ergonomic failure, because they are the common case.

**Why it matters.** David ranked ergonomics second. `or_throw` does aggregate errors, and that is the right tool for a line of user input. It is the wrong tool for a meeting that is a constant in the source. Programmers will wrap the whole program in `or_throw` and stop seeing the failures that are real.

**Fix.** See note 5 for the inherent-versus-artifact split and the recommended defaults. The short version: a delimited call with a literal argument is a constant, infallible when unique, and a compile error when it is a gap or a fold and no policy is written. Policies that make the result unique remove the error. Runtime strings stay `T | error`.

### 5. The default calendar has no versioning story that survives a reform

**Problem.** Decision 5 freezes "generic `Date` means proleptic Gregorian with a year zero" as a source default, and `$time.require_calendar` only forces the caller to be explicit. Nothing says what happens when a later Dewy release changes that default, or how a stored `Date` knows which calendar it was. `$calendar` alone does not do this: a metatag is not versioned with the dependency graph, and a global flip reinterprets old source.

**Why it matters.** This is David's fourth note, and it is the 10,000-year problem in miniature. The axis must not move. The *unqualified spelling* will move, or Dewy will be stuck spelling Gregorian forever under another name.

**Fix.** See note 4. The load-bearing constraint: editions change what a bare name means in new source. They do not change bytes, public type identity, or the nanosecond.

### 6. Negative leaps are specified as their own behavior

**Problem.** §4 gives negative leaps a paragraph, a synthetic-history requirement, and an acceptance bullet, parallel to positive leaps. A negative leap has never been inserted. CGPM Resolution 5 (2026) makes continuous UTC effective 20 May 2027 and sets `|UT1−UTC| ≤ 3600 s`, specifically because a first negative leap was a live operational risk. The CCTF statement of 15 October 2026 says that risk is why the date was brought forward.

**Why it matters.** A dedicated path will be tested, documented, and then copied into codecs, smears, and `TimeOfDay` markers for an event that civil time is about to make impossible. That is cost against a closed door. Dropping the *general* ability to skip a label would also be wrong: the segment table needs it for synthetic packs, for pedagogy, and in case a leap is announced before the cutoff.

**Fix.** See note 3. One sentence in the UTC section, one synthetic test, no type name, no trivial-tier branch, no clamp of `:60` to `:59`.

### 7. `1week` and `1day` look like durations

**Problem.** v4 writes `every=1week` and `add(1month …)` as if those were juxtaposed units. In Dewy, juxtaposed units are exact quantities (`300ms =? 3s/10`). A week is not `168hour` once DST, leaps, or a date-line crossing exist. The standing decision already says `month` and `year` combine only with dates. `day` and `week` are the same kind of trap and are more tempting, because `86400s` looks obvious.

**Why it matters.** `sleep(1day)` meaning 24 hours, and `meeting + 1day` meaning "same local time tomorrow", will both get written. They differ by an hour twice a year in `America/New_York`. This is the iCalendar / Python `timedelta` bug.

**Fix.** `1day`, `1week`, `1month`, and `1year` are `Period` literals, type-directed, legal only where a period is expected. `sleep(1day)` is a type error whose fix-it is `24hour`. `Instant + 1day` is a type error whose fix-it is a zoned add or `24hour`. `ZonedDateTime + 1day` keeps the local time and applies the scope's gap/fold policy (see note 5).

### 8. Strictness can allocate on the path it is meant to protect

**Problem.** §12 records "every convenience used" in an assumption trace "shared by reference". Combined with `Estimate` identity, that is a pointer and a graph on values that should be integers. Seventeen metatag names are fine. Seventeen runtime checks, or a trace node per `now`, are not.

**Why it matters.** `$bulletproof` is how the hardest programs opt out. If opting out allocates, the strict lane cannot be used in the programs that need it (`$no_hidden_costs` forbids the allocation). The obligations then get ripped out of the hot path later, which is how strictness rots.

**Fix.** The metatags are compile-time. The default path records nothing. A strict context stores one integer id. Evidence graphs, dependence tracking, and `X − X = 0` live in `Coordinate` / `Estimate`, constructed when that module is used. A pinned context does not imply its bytes are mapped; mapping happens on first civil or science call, as v4's layering already says, and the type/module cut must make the linker enforce it (note 2 and the brainstorm).

### 9. `now` must not walk a leap table or apply `L_G`

**Problem.** If `nominal` is TT-rate nanoseconds, a careless reading of §1 runs the SOFA-shaped conversion on every sample: POSIX → leap table → TAI → × `(1 − L_G)`. v4 does not require that, but it also does not forbid it, and the fat `Estimate` encourages it.

**Why it matters.** After 20 May 2027, `TAI − UTC` is a constant between the last leap and forever, under the current resolution. Even before that, it is a constant between announced leaps. `clock_gettime` is a vDSO read. A table walk or a 10^19-denominator multiply misses "as cheap as C" by orders of magnitude and loads data `now` does not need.

**Fix.** At the first `now`, cache one `int64`: the current nominal `TAI − POSIX` offset from the pinned pack. `nominal = mono_paired_unix_ns + cached_offset − J0_OFFSET_NS`, in `int128`. Do not multiply by `L_G`. That factor is TCG, and it is off-grid (note 1). Historical parses and dates before the cached segment load the segment table. The cache is invalidated by an explicit pack update, not by a clock read. State in the `now` contract that this nominal value is **not** a POSIX count and **not** realized TT to metrological accuracy. The status byte says which clock convention was identified; an unidentified convention is `UnknownClockConvention` at acquisition, once, not per read.

The 1970-01-01T00:00:00 UTC event is an exact integer on this axis (derivation in note 1). Adding `N × 10^9` to that integer is **not** the POSIX conversion. POSIX days omit leaps. The cached offset is what carries the current leap; the segment table is what carries the old ones.

### 10. Host tzdata and the compiled-in pack are unspecified as a pair

**Problem.** v4 pins packs and also captures the host zone. It does not say which transition table `today` uses when the host's `/usr/share/zoneinfo` and Dewy's pinned pack disagree. jiff reads the system database so governments can change DST without a recompile. chrono-tz embeds the database and goes stale. Both are real failures.

**Why it matters.** A test that passes on Monday and fails on Tuesday because a distribution updated tzdata is a trap. A civil program that ignores an urgent DST cancel because it linked last year's IANA snapshot is also a trap. Reproducibility and freshness both have to be spelled.

**Fix.** The captured context stores the host **zone name** (`America/New_York`), read once. Rules come from the pinned pack. Divergence is a queryable status (`ZonePackStale`), not a silent override and not a failure of `today`. `zone_source='host'` is the explicit opt-in that resolves rules from the OS database. Updating Dewy's pack is an explicit operation, and it produces the migration preview v4 already describes for future appointments. Past `Instant`s do not move.

---

## Answers to David's notes

### 1. Representation

**Epoch.** J0 with `e = 0` is the right zero, and it is better than v4 admitted when it recommended Apollo.

At that origin the TT label is `1977-01-01T00:00:32.184 TT`, so the nominal TAI label is `1977-01-01T00:00:00 TAI`. The stored integer **is** nominal TAI-compatible nanoseconds since that midnight. `32.184 s` appears in documentation of the TT label and in science conversions to a geocentric coordinate. It does not appear in add, subtract, or `now`.

`32.184 s = 32184000000 ns` exactly (`4023/125` seconds). Do not compute it in binary64.

Exact `int128` nanosecond coordinates of named events, relative to J0. Re-derive against the USNO TAI−UTC table before any wire format is frozen:

| Event | Nanoseconds |
|---|---|
| J0 itself | `0` |
| 1970-01-01T00:00:00 UTC | `−220924791999918000` |
| Apollo 11 conventional UTC instant, v4's fraction | `−235107732425406200` |
| GPS epoch 1980-01-06T00:00:00 GPS (= TAI−19 s) | `+95040019000000000` |
| J2000 `2000-01-01T12:00:00 TT` | `+725803167816000000` |

Unix derivation, so it can be checked: `TAI−UTC` at MJD 40587 is `4.2131700 s + 1461 × 0.002592 s = 8.000082 s = 8000082000 ns`. From that UTC event to J0 is `2557 × 86400 s − 8.000082 s`. The `32.184 s` cancels. `2557 = 7 × 365 + 2` (1972 and 1976).

Apollo's published fraction has denominator `5000000` and looks like evidence for a rational instant. Divided into nanoseconds the remainder is 0. Dropping Apollo as the **zero** does not make that instant unrepresentable. It removes a constant from every stored integer. J0 also matches the TT/TCG origin coincidence, so science code is not forever subtracting an Apollo offset before applying `L_G`.

**Default tick.** `1 ns`, because that is the quantum of POSIX `timespec`, PTP's integer field, `java.time`, Go, C++ `nano`, and Temporal, and because every decimal fraction of a second with at most 9 digits lands on it. `1 µs` fits in `int64` for geological time and loses the OS quantum. The caesium period `1s/9192631770` does not divide a nanosecond (`9192631770 = 2 × 3² × 5 × 7² × 47 × 44351`; `gcd` with `10^9` is 10).

**`1ns/3` and exact epoch shifts.**

- `300ms`, `1ns`, `1hour`, `32.184s`, and `TDB0 = −6.55×10^−5 s = −65500 ns` are on the grid.
- `1ns/3` and `1s/3` are not. Constant uses are compile errors. `Instant<tick=1ns/3>` exists for callers who want that grid. Default `Instant` does not become it.
- Epoch shifts that are an integer number of nanoseconds are exact `as` conversions: GPS, J2000 TT, CCSDS 1958-01-01 TAI, the Apollo label, and the single Unix **event** above.
- A POSIX count is not an epoch shift. NTP's `2^−32` second is `0.232… ns`, not an integer. TT↔TCG multiplies by `1 − L_G = 1 − 6969290134/10^19` and leaves the grid for a general input.
- Exact off-grid results return `Coordinate<Scale>` (rational, science module) or `Instant<tick=…>` when the caller names the destination tick. `quantize(tick rounding)` returns the rounded instant and the signed loss. `as` is only the exact case, matching Dewy's existing `as` rule.

**Codecs.** Decode to the codec's own tick, in the codec's declared domain. Cast to plain `Instant` only when every represented value of that tick is an integer number of nanoseconds, or when this particular value is and the cast is checked.

| Codec | Lands on 1 ns? |
|---|---|
| POSIX `timespec`, PTP seconds+nanoseconds, FILETIME (`100 ns`), CDS milliseconds and microseconds, RFC 3339 with ≤9 fractional digits | Yes, exactly. Leap/smear/era semantics are still a separate question. 32-bit `time_t` overflow is `OutOfRange`. |
| RFC 3339 with ≥10 fractional digits, CDS picoseconds | No. Keep `Instant<tick=1s/10^k>` or a remainder. Do not truncate. |
| NTP `2^−32` or `2^−64`, CCSDS CUC `2^(−8f)`, SPICE ET binary64, two-part JD doubles | No. Native tick, or `quantize` with the input quantum recorded. |
| PTP correction field (`2^−16 ns`) | No. Keep it beside the instant as its own integer. Folding it in is `OffGrid`. |
| GPS week + TOW | The TOW quantum usually fits. The week width does not identify the era. Refuse the conversion without external era evidence. |

**Range versus width.** Tick is the quantum. Width is the bit count of `n`. Range is `±2^(width−1) × tick`. v4's sentence "a tick does not imply 64-bit storage" is true as a parameter list and misleading as a default: the product is the actual type. Default pairing is the rule in critique §1. `OutOfRange` is the overflow value. There is no wrap, and there is no promotion to a heap integer on the default ABI.

**`Instant<tick=…>` interaction.**

- Same tick: add and subtract are integer operations and stay in the type.
- Different tick: exact `as` when the source tick is an integer multiple of the destination tick, or when this value's count makes the conversion divide evenly (checked, `OffGrid` otherwise).
- A `Coordinate` converts onto a tick the same way.
- Equality across ticks is that conversion, not a third canonical rational.
- The parameter never changes scale, epoch, or realization. `Instant<tick=1us>` is still TT-rate nanoseconds-worth of time since J0, quantized to microseconds only if the caller built it that way; constructing it from a non-multiple is `OffGrid` or `quantize`, picked by the operation, never by the type argument alone.
- `width=` defaults by the range rule. `Instant<tick=1s/2^32 width=64>` covers only about ±68 years and must not be what a codec silently picks.

**Wire identity.** Interchange already carries epoch, scale, and tick tags in v4 §11. Those tags are mandatory. An edition must not reinterpret old bytes. The payload for plain `Instant` is the `int128` two's complement count.

### 2. Trivial tier

The shape (one captured context, total reads, status instead of an error branch, `Duration` from a subtract, uncertainty visible when printed) is right. Two changes, both closed by David, plus the arithmetic fix from critique §2.

**Lightweight.** `now` returns the 32-byte `ClockReading`. The common subtract uses the `int64` mono field and does not read the `int128`. `Instant` itself is 16 bytes. `ZonedDateTime` is the instant, a zone id, and a cached offset. Anything with an `Estimate`, a string, or a pointer is a different type, built when asked for.

**Spelling.** Idiomatic zero-argument calls omit parentheses (`docs/design/decisions.md`: a bare name calls; `@fn` is the handle; parentheses may be included but are not the idiom). `LANGUAGE.md` matches: `add(pair)` calls, and a zero-argument method is called on access. Rewrite every example.

| v4 | Idiomatic |
|---|---|
| `now()`, `today()` | `now`, `today` |
| `work()`, `fetch()` | `work`, `fetch` |
| `time.elapsed(@work())` | `time.elapsed(@work)` |
| `within(2s @fetch())` | `within(2s @fetch)` |
| `measure(@work())` | `measure(@work)` |

`sleep(300ms)` and `within(2s @fetch)` keep their parentheses because they take arguments. `@fetch(url)` is a real partial and stays.

**Also change the arithmetic, or the trivial tier teaches the wrong clock.** `now - start` and `now + 5s` are monotonic. Wall is `.nominal`. `today` returns `Date`. Entry does not open a clock unless the program uses one or `$time.require_context` is set. Reads stay total: a dead clock returns a stale reading with a status, once acquisition has succeeded. Acquisition failure is the first-use error, forwarded with `or_throw` if the caller cares, not a branch on every later read.

```dewy
let start = now
work
printl"took {now - start}"
sleep(300ms)
printl"today is {today}"
let deadline = now + 5s
within(2s @fetch) or_throw
let t = instant"2026-10-24T12:00:00Z"
printl"{t + 90minute}"
```

`90minute` is on the nanosecond grid. `instant"…"` is infallible (note 5). `within` stays fallible because the fetch can time out.

### 3. Negative leaps

Keep the general mechanism. Do not keep a negative-leap feature.

- **History.** No negative leap has been inserted. Positive leaps from 1972 through 2016 are real archive data and stay valid labels, including `23:59:60`.
- **Law.** Continuous UTC is effective 20 May 2027 (CGPM Resolution 5, 2026), with `|UT1−UTC| ≤ 3600 s`. That is a new segment with an inherited offset, not a hardcoded `37 s` and not a deleted history. A December 2026 leap is the last slot the old rule could still use; the model does not assume one.
- **Tests and generality.** A transition that removes a label is the same shape as a DST gap: the local (or UTC) label is missing, and the neighboring labels are known. DST already forces that code. One synthetic pack with a skipped second belongs in the acceptance list. It does not need a `NegativeLeap` type, a smear variant, or a trivial-tier branch.
- **Cost of a special case.** Every codec, `TimeOfDay` marker, and doc page grows a path nobody can hit on real UTC after the cutoff. jiff implemented leaps, found they infected arithmetic, and ripped them out, clamping `:60` to `:59`. That clamp is a silent lie. Dewy avoids both the infection and the clamp: `Instant` is continuous TT-rate, so a leap never changes `Instant` arithmetic; the UTC label layer accepts `:60` where the segment table says it existed, and rejects it otherwise.
- **Do not** promise a future leap-hour mechanism. The resolution explicitly does not specify one. A later standard is a new segment.

### 4. Default calendar evolution

Use all three mechanisms, for three different jobs. Any one of them alone fails.

**Edition (the release-level change).** A project file names an edition. The stdlib has a table:

```dewy
# project file, not language syntax
edition: "2026"
```

| Edition | Bare `Date` / `date"…"` / `today` |
|---|---|
| `"2026"` | `Date<ProlepticGregorian>`, astronomical years, year zero |
| a later edition | whatever replaced it, after one deprecation edition |

The deprecation edition warns on bare `Date` and names the explicit spelling. Old editions keep compiling and keep meaning what they meant. Changing the default is one row in that table. This is the mechanism David asked for. It does not exist elsewhere in Dewy yet; time should be its first client, and the key should be the language's edition key rather than a time-only fork.

**Explicit type (the stable surface).** `Date<Gregorian>` means proleptic Gregorian in every edition. Stdlib and library signatures use the explicit parameter from day one, so an edition bump does not rewrite their types. Bare `Date` is for application source. Two editions' bare dates are different types and do not unify without a conversion. That is what makes the flip safe.

**`$calendar` (the local override).** A scope metatag selects the calendar for bare names in that scope. The inferred type is still the specific calendar (`Date<Hebrew>`), not a bare `Date` whose meaning depends on the caller's flags. A Mars habitat or a liturgical module sets `$calendar` (or the manifest) without waiting for Earth to change editions. `$calendar` does not version dependencies and must not be the only story.

**What is frozen forever, versus what is a pack.**

| Frozen | Versioned by packs or editions |
|---|---|
| J0, `e = 0`, tick `1 ns`, TT-rate axis, `int128` layout | Which bare `Date` means |
| Integer meaning of stored instants | UTC segments, leap rules, tzdb, legal calendars |
| `Date<Gregorian>` arithmetic | Jurisdictional reforms, era names, week rules |
| | New scales (TCL, Mars, a post-2030 realization note) |

A calendar reform in one jurisdiction is a segment of that jurisdictional calendar. It is not a mutation of `ProlepticGregorian`, which remains a pure arithmetic calendar and still does not claim historical adoption (v4 is right about this). British 1752 and Swedish `1712-02-30` stay in named historical calendars.

**The 2030 second.** CGPM Resolution 4 (2026) asks for a new definition of the second, aimed at the 2030 CGPM, based on optical standards, with continuity as a requirement. A continuous redefinition does not renumber ticks. A future redefinition that introduces a step is a new scale, not a rewrite of `Instant`. Say this in the epoch section. v4 does not mention it, and it is the actual near-term standards change, closer than any calendar reform.

**Off-Earth.** `today` on Mars is the habitat's captured context, not a different meaning of Earth's `Date`. A sol, a Darian date, and lunar TCL are other types and other packs. `StandardNotDefined` for operational LTC stays. Do not add a mode switch that makes `hour` mean a Martian hour. A Mars hour is a field of that clock, and it is not `3600s`.

**10,000 years of unknown standards.** New information arrives as a pack with an effective interval, or as a new type parameter. Old values keep their old pack ids. Future appointments re-resolve under an explicit migration. The edition table is how *source* moves. Nothing in this scheme requires predicting the reform.

### 5. Fallibility ergonomics

Not every line should be fallible. v4's `or_throw` block mixes three things Dewy already knows how to separate: constants, branded values, and real partial functions.

**Inherent (a typed value can still fail).**

- A local time in a gap or a fold.
- A calendar field that does not exist (`2027-02-31`, 31 January plus one month with no policy, Swedish 30 February outside that calendar).
- An observational event with no solution (polar sunset, unpublished crescent).
- A runtime zone name that is absent from the pack.
- Missing pack bytes, expired coverage, contradictory evidence.
- Off-grid quantization the caller did not ask for.
- Mono readings from different generations.

**Artifacts of strings (a typed value cannot fail this way).**

- Syntax, truncated input, wrong digit shapes.
- Unknown zone **text**, ambiguous abbreviations (`CST`), two-digit years, MDY versus DMY.
- A leap label `:60` on input that has not been checked, as distinct from a typed UTC label already validated against the segment table.
- Offsetless text presented as an instant. That text is a `LocalDateTime`, and the parse should return that type rather than fail a guess. Failure is the wrong product; the wrong type is the bug.

**Recommendations.**

1. **Literal delimited calls are compile-time checked**, same rule as `regex`. Unique success is infallible. A known gap or fold without a policy is a compile error with a fix-it, not `or_throw`. A policy literal that makes it unique is infallible. Unknown zone literals are compile errors against the pinned pack.

2. **No new literal syntax is required.** `printl"hi"` and `p"…"` already use a delimited argument. `instant"…"`, `date"…"`, `zoned"…"`, and `zone"…"` are ordinary calls. The new claim is the infallibility rule, which needs David's approval as semantics, not as a keyword.

3. **Brands.** `Zone`, `Date`, and `Instant` are only built by validators. Once the program holds a `Zone`, "unknown zone" is gone. Gaps and folds remain. A total policy (`fold='later' gap='next'`) on a branded zone and a branded local time is infallible against a pinned pack. Missing data is an acquisition failure of the pack, once, not a member of every call's result.

4. **Refinement discharges the rest.** `delay:Duration<(>=? 0s)>` already matches v4's strict example. Extend that idiom: a `Zone` parameter, a `Date` known not to be 29 February, a literal policy. Do not invent a general "timezone context monad". The captured pack id plus branded arguments is enough. `$time.require_*` demands the evidence at the context boundary; it should not add a parameter to `now`.

5. **Defaults for conventions, never for folds.** A fold has two true answers. Guessing is a trap (Python `fold=0`, java.time `SMART`, Temporal and jiff clamping `:60`). A leap-day birthday has a conventional anniversary rule. Those are different.
   - `age` defaults to completed calendar years with `leap_day='march_1'`. This is a `$time.require_profile` assumption: under that metatag, a 29 February birthday requires the argument. A literal birthday that is not 29 February never requires it. `legal_age(jurisdiction=…)` is the separate function and stays data-dependent.
   - `ZonedDateTime + 1day` defaults to "same local fields tomorrow", and names the gap/fold policy from the scope, defaulting to `reject` so a gap is still visible. `$time.require_profile` makes the policy argument required. This is the one place a default policy is justified: the operation's meaning is civil, and silence about *which* civil policy is the assumption.
   - `Date + 1month` on a literal 31st that does not exist is a compile error until `overflow=` is written. There is no innocent default. Clamp, spill, and reject disagree on the date the user sees.
   - Runtime strings and runtime local times in unknown seasons stay fallible. One `or_throw` or `??` at the parse boundary is the idiom. `??<NoOccurrence>` stays as v4 wrote it: narrow defaults do not swallow missing data.

6. **`or_throw` aggregates.** Keep it for I/O, `within`, pack fetch, and dynamic text. The type of a constant meeting is `ZonedDateTime`, not `ZonedDateTime | ParseError | UnknownZone | Gap | Ambiguous`. If the happy path still mentions `or_throw`, the API took a string it should have taken a typed value.

```dewy
let meeting = zoned"2026-10-26T09:00[America/New_York]"
let later = meeting + 1hour
let repeated = zoned("2026-11-01T01:30[America/New_York]" fold='later')
let jan = date"2027-01-31"
let feb = jan.add(1month overflow='clamp')
let age = date"2000-05-12".age(on=date"2026-10-24")
let text = zoned(input zone=zone) or_throw
```

`meeting`, `later`, `jan`, `feb`, and `age` have no error alternative. `repeated` has a policy, so it does not either. `text` is the fallible boundary.

### 6. Redundant partial application

Agreed. `@f()` with no new arguments is `@f`, and it should warn. The warning is a language lint, not a time-library special case: the empty call adds nothing and looks like a call someone forgot to finish. Generated code can silence it by writing `@f`.

v4 sites to rewrite: the trivial `within(2s @fetch())`, `time.elapsed(@work())`, §7's `measure` / `fetch_with_limit` / `measure(@work())`, and `within(5s @work())`. The prose that says "`@work()` is a partial application, not an eager call" should say "`@work` is the handle; the parentheses would call."

`within` still receives a handle because it must call later, under the deadline. That is a real `@`. The redundancy is only the empty argument list.

### 7. Examples

Proposed names follow this critique. Each one is a motivating program, not a test list.

**1. Elapsed work.** Mono subtract, status-free happy path, no zone data.

```dewy
let start = now
compile
printl"compiled in {now - start}"
```

Exercises: `ClockReading` layout, monotonic difference, printing a duration through the existing unit chooser.

**2. Game frame.** Fixed step, no allocation, no civil module.

```dewy
loop true {
    let frame = now
    draw
    let spent = now - frame
    if spent <? 16ms { sleep(16ms - spent) }
}
```

Exercises: inline readings, `int64` elapsed, `sleep` on the monotonic domain, suspend-inclusive default, the loop form.

**3. Timeout.** Cancellation is the task's, not a discarded error.

```dewy
let page = within(2s @fetch) ??<Timeout> cached
```

Exercises: `@` handle, `??<E>` leaving other errors alone, monotonic deadline inside `within`.

**4. A meeting across a DST boundary.** Literal infallibility, fixed duration versus civil period.

```dewy
let meet = zoned"2026-10-26T09:00[America/New_York]"
let ends = meet + 90minute
let next_week = meet + 1week
```

Exercises: compile-time zone resolution, `90minute` on the nanosecond grid, `1week` as a period that keeps 09:00 local rather than adding `168hour`.

**5. A daily alarm through a fold and a gap.**

```dewy
$calendar = gregorian
let alarm = recurrence(
    zoned"2026-03-01T01:30[America/New_York]"
    every=1day
    fold='earlier'
    gap='preserve_displacement')
let next = alarm.next(after=now.nominal) ??<NoOccurrence> none
```

Exercises: policies only where a transition needs them, native recurrence leaving an uncovered occurrence unresolved, nominal key versus resolved time.

**6. Billing a shift that crosses the fall-back hour.**

```dewy
let shift = zoned("2026-11-01T00:30[America/New_York]" fold='earlier')
let done = zoned("2026-11-01T03:30[America/New_York]")
let worked = done.nominal - shift.nominal
let credited = shift.credited_until(done rules=payroll)
```

Exercises: fold choice changes the instant, elapsed TT nanoseconds are not "three hours" of pay, credited time is a rule pack. The classic failure is billing `done - shift` as a civil subtraction.

**7. Logs.** An instant, a UTC label, no location pointer.

```dewy
let stamp = now.nominal
log.write("{stamp} request {id}")
```

Exercises: formatting `Instant` does not load a zone; the log stays comparable across hosts; a later pack update does not rewrite the line.

**8. User-facing display.** Lossy, localized, not legal time.

```dewy
printl(meeting.display(locale='fr' profile='nominal') or_throw)
```

Exercises: display may drop the offset and the zone id and must say so in a loss report; the stored `meeting` is unchanged; locale does not select the zone.

**9. Invoice dates.** Anchor versus clamp, the case with no innocent default.

```dewy
let jan = date"2027-01-31"
let clamped = jan.add(1month overflow='clamp')
let end = date"2027-01-31".add(1month anchor='month_end')
```

Exercises: `clamped` is 28 February; `end` is the last day of February by anchor, still the 28th, but March's anchor stays the 31st of the following month where that exists. Repeated clamp from 31 January drifts. `Period` order is part of the value.

**10. The 2016 leap second, archived.**

```dewy
let before = utc"2016-12-31T23:59:59"
let leap = utc"2016-12-31T23:59:60"
let after = utc"2017-01-01T00:00:00"
printl"{after.nominal - before.nominal}"   # 2s
printl"{posix(after) - posix(before)}"      # 1s, and the codec says so
```

Exercises: `:60` is a real UTC label in that segment and `OffGrid` / invalid elsewhere; `Instant` difference counts the inserted second; the POSIX adapter does not, and cannot be used as a sneaky `as`.

**11. A Babylonian eclipse, long before the epoch.**

```dewy
let when = instant"-0584-05-28T12:00:00Z"
let tt = when as Coordinate<TT>
let delta_t = iers.delta_t(tt model='morrison_2004') or_throw
let moon = de440.position("moon" at=tt frame='geocentric') or_throw
```

Exercises: `int128` range (this instant is not representable in `int64` nanoseconds), proleptic Gregorian as a label rather than a claim about the Babylonian calendar, ΔT as a model with coverage, ephemeris as a pack. Year −584 is astronomical numbering for 585 BCE.

**12. Eclipse predictor.** A sketch of the science layer, not a new calendar.

```dewy
let window = interval(date"2026-01-01" date"2028-01-01" calendar=gregorian)
let events = astronomy.eclipses(window body='moon' model=de440)
loop event in events {
    printl"{event.kind} {event.when} {event.where}"
}
```

Exercises: a calendar window is not a TT interval until a zone or a TT noon convention is applied; the search is bounded by the window; the result is an instant plus a geometry, and "where" can be empty (the shadow misses the Earth). This is the program that justifies `Coordinate`, and it must not be linked into example 2.

**13. A command to a rover.**

```dewy
let onboard = sclk"1/1465644281.0" clock=mission.rover
let received = onboard.correlate(kernel=mission.sclk) or_throw
let send_by = signal.latest_send(
    execute=received
    sender=mission.station
    receiver=mission.rover
    model=mission.light_time) ??<NoFeasibleWindow> none
```

Exercises: SCLK ticks are not SI seconds; correlation keeps the raw count; uplink and downlink are separate legs; half the round trip is not the one-way delay; the kernel is pinned to the mission context, not a global SPICE pool.

**14. Two habitats and a ship.**

```dewy
let earth = zoned"2027-03-01T09:00[UTC]"
let mars = mars_clock(earth.nominal site=jezero convention='mtc')
let ship = ship.elapsed(since=launch.nominal)
```

Exercises: one nominal instant, three clocks; MTC is a Mars mean-solar phase, not an offset from UTC; a ship proper time is an integral along a worldline. `mars_clock` without a `convention` argument is a compile error. There is no `mars.now`.

**15. A GPS week that has rolled over.**

```dewy
let sample = gps(week=1023 tow=0s width=10)
let fixed = sample.resolve(era=1) or_throw
# sample as Instant
```

Exercises: a 10-bit week does not name an era; the cast without `resolve` is rejected; 1999 and 2019 stay distinct. The same pattern covers a truncated CUC epoch and a 13-bit GPS week.

### 8. Prior art

**java.time / JSR-310.** Split `Instant`, `LocalDate`, `LocalDateTime`, `OffsetDateTime`, `ZonedDateTime`, and `Period` versus `Duration`. Injectable `Clock`. Resolver styles, of which `SMART` silently adjusts invalid fields. Lessons: the split is right; a smart resolver is a trap; `Instant` as seconds plus nanoseconds is right and a single millisecond `long` (pre-JSR-310 `Date`) was wrong; java.time's instant does not model leaps, so science and POSIX get conflated. **v4 handles** the split, the injectable context, and the refusal to be SMART. **v4 misses** the weight: `java.time.Instant.now` does not allocate a chronology or an estimate. Our default reading must be at least that cheap. Chronology-on-every-date is the JSR-310 complexity Dewy should keep off bare `Date` by using a type parameter with a default, not a runtime strategy object.

**Joda-Time.** Calendar chronology baked into a millisecond instant. It lost to java.time because the chronology was always in the way and the millisecond grid was the wrong core. **Handled** by keeping calendars off `Instant`.

**Noda Time.** The explicit lesson is to make the wrong conversion hard: `LocalDateTime` plus a zone returns a resolution; `InZoneLeniently` is the named trap; `Period` is not `Duration`; the clock is an interface. **v4 handles this.** Keep `choose` as a free function so a method's `or_throw` cannot skip the ambiguous branch. That is a Dewy-specific addition Noda does not need, and it is right.

**JavaScript `Date`.** One mutable object, milliseconds since 1970, local zone by default, month numbers starting at 0, implementation-defined parsing, DST arithmetic that depends on the host, no leaps. It failed because every distinct concept was the same value. **Temporal** fixes the split (`Instant`, `PlainDate`, `PlainTime`, `ZonedDateTime`, `Calendar`, `TimeZone`) and uses a bigint nanosecond count. Its `Duration` mixes months and seconds in one value, which is the footgun v4's `Period` split avoids. `Temporal.Now` re-reads the system zone. Leap seconds are clamped (`:60` becomes `:59`). **v4 handles** the type split and is better on periods and on capture-once. **v4 misses** Temporal's actual representation lesson: the instant is an integer number of nanoseconds, not a rational. Do not copy the bigint (allocation) or the clamp.

**Python `datetime`.** Naive and aware values share a type; comparing them is a long-standing trap. `fold` defaults to 0, which silently picks one side of a fold. `timedelta` is a fixed duration, so "add a day" across DST surprises people. `timestamp()` is a POSIX float. `zoneinfo` is IANA and still does not make `datetime` arithmetic zone-aware in the way users expect. Microseconds are the stored resolution. **v4 handles** separate types and the refusal to default `fold`. **Miss:** a float quantity added to an instant must be `OffGrid` or `quantize`, because the language already has `float64 * Time` and someone will add `0.1s`. Also do not store `fold` as a boolean on the value; store the resolved instant and the policy in the trace, or keep the unresolved union.

**Rust `chrono`.** `DateTime<Utc>` versus `FixedOffset` versus `Local`, with `Local` reading the ambient zone. Real IANA support is an extra crate (`chrono-tz` embeds the database; `tzfile` reads the OS). Optional leap seconds complicate `Duration`. The old `time` 0.1 crate had soundness bugs from unsafe timestamp conversions; there is nothing to copy from that. **v4 handles** ambient-zone capture and "leap policy is not the duration type". **Miss:** the embedded-versus-OS split, answered in critique §10.

**Rust `jiff`.** Written against chrono's gaps: DST-safe civil addition, spans versus timestamps, and a single zone-database story. BurntSushi tried leap seconds, found they infected the API, and removed them; parsing `:60` clamps to `:59`, with a TZif escape hatch for TAI. `Zoned` is not `Copy` because it owns zone data. The design prefers the system tzdb so a DST law change does not wait on a crate update. **v4 handles** span-versus-duration and DST as data. **Disagree with jiff** on three points, on purpose: do not clamp leaps; do not put the transition table in the value; do not read OS rules by default (critique §10). **Agree with jiff** that adding a civil day to a zoned value should be the obvious spelling (note 5), which v4 currently makes too heavy.

**Rust `time` and `hifitime`.** `time` shows that a small duration type is the product users want, with calendars layered on later. That supports the module cut. `hifitime` shows why a continuous atomic scale makes leap-second durations fall out of subtraction, and its examples use float seconds for those durations. **Take the continuous scale. Do not take float storage.**

**Go.** `time.Time` stores wall, a monotonic extension, and a location pointer. `Sub` uses mono when both sides have it. `Add`, rounding, JSON, and `==` drop mono, so equality and subtraction disagree after a round trip. This is the main lesson for the trivial tier, and **v4 misses it** by defining the easy subtract as nominal. The fix is critique §2: same subtract behavior, visible in the type, no pointer.

**C++ `<chrono>`.** `time_point<Clock, Duration>` puts the clock in the type. `duration<int64_t, nano>` is an integer count of a compile-time tick. That is David's model, in the standard since C++11. `duration_cast` **truncates**. `system_clock` is POSIX (no leaps), `utc_clock` has leaps, and `tai_clock`, `gps_clock`, and `file_clock` are different types. **v4 handles** the split in prose and then blurs it by letting plain `Instant` be a rational. **Miss:** name the POSIX adapter so a `clock_gettime` difference is not spelled `as Instant`. Silent truncation is the bug `OffGrid` exists to prevent.

**Erlang time warp.** The VM grew `no_time_warp`, `single_time_warp`, and `multi_time_warp` because a global time base changed under existing timestamps. Libraries assumed different modes. **v4 handles this** by putting the provider generation in the captured reading and by using test clocks as contexts. Do not add a process-wide warp flag later. A flag is how Erlang got here.

**SOFA / ERFA.** Two-part Julian dates, because one binary64 cannot hold a JD and a fraction of a second. Integer status returns. A leap table compiled into the library goes stale. TT↔TCG is an exact affine map, including the inverse, and it is not an ephemeris call. **v4 handles** the math and the two-part codec. **Miss:** say that `now` is the cached-offset integer in critique §9, so an implementer does not "correct" it by calling `iauTaitt`.

**Skyfield.** Timescales as an object (`utc`, `tt`, `tai`) and float64 Julian dates for array speed, with documented precision loss around tens of microseconds. **v4 handles** named scales. **Miss:** a packed `array<Instant>` (`int128` lanes) and an explicit float export with a recorded quantum. Skyfield's storage must not become Dewy's.

**astropy `Time`.** Scales and formats are required, location matters for some transforms, internal representation is two doubles, and the leap table ships with the package. Scale-as-a-string is easy to mix up. **v4 handles** scale as a type/domain and location as an explicit argument. **Miss:** the same bulk layout as Skyfield. A million observation times are an array of integers, not an array of estimates.

**SPICE.** `ET` is TDB seconds past J2000 as a double. The global kernel pool means loading a file changes unrelated computations. SCLK partitions, and light time is an iteration over moving endpoints. **v4 handles** pinned contexts, raw SCLK identity, and the one-way-versus-round-trip distinction. Keep ET as a `Coordinate<TDB>` codec with the input quantum recorded, not as an `Instant`.

**iCalendar / RFC 5545.** Floating times versus UTC versus `TZID`; `DATE` versus `DATE-TIME`; all-day `DTEND` treated as exclusive (the end date is the next day) which is a permanent off-by-one; `VTIMEZONE` copies that diverge from IANA; `RRULE` interaction with gaps; `COUNT` versus `UNTIL`; `UNTIL` required to be UTC; `RDATE` / `EXDATE` / `RECURRENCE-ID`; `THISANDFUTURE`; renamed TZIDs; vendors disagreeing. **v4 handles** the profile, stable occurrence keys, embedded `VTIMEZONE` identity, and explicit-versus-generated gap rules. **Miss:** state DTEND exclusivity in the profile, and state `THISANDFUTURE` as a migration of the series from one occurrence forward, using the same cutover as a pack update. Floating `DATE-TIME` is the itinerary appointment v4 already has; say that in the profile so it is not reinvented as a nullable zone.

**Bug classes, scored.**

| Class | v4 | After this critique |
|---|---|---|
| DST gap/fold | Refuses to guess. Examples still parse at runtime. | Literal unique times are infallible. Literal folds without a policy are compile errors. |
| Leap seconds | Segment table, positive and negative both featured. | Positive history stays. Negative is just a gap. No clamp. `Instant` arithmetic ignores leaps. POSIX is an adapter. |
| Year 2038 | "ABI overflow is `OutOfRange`". Rational core dodges it. | `int128` nanoseconds dodges it. `int64` nanoseconds recreates it in the year 2269 and must not be the default. 32-bit POSIX stays `OutOfRange`. |
| GPS rollover | Era evidence required. | Unchanged. Example 15. |
| tzdb churn | Pins, aliases, migration preview. | Plus the host-name versus pinned-rules split. Stored instants do not move. |
| Mono versus wall | Both exist. The easy operator is wall. | The easy operator is mono. `.nominal` is wall. Deserialized values have no mono field. |
| Float time | Core is exact. | Also forbid implicit float duration addition, and forbid computing epoch constants in binary64. |
| Naive versus aware | Separate types. | Unchanged. Do not add a kind flag. |
| 0-based months, mutable instants | Absent. | Keep them absent. |

---

## Brainstorm

- **The reading is two integers and a status, and the type system is the documentation.** Elapsed, wall, and civil are three types you can see. Go hid the good behavior. Python hid the bad behavior. Dewy can make the conversion between them a different type, which is the cheapest explanation a language can offer.
- **Compile a constant timestamp down to the integer.** `zoned"2026-10-26T09:00[America/New_York]"` lowers to an `int128` and a zone id. No parse, no table walk, no failure. The pinned pack is a compile-time input for literals and a runtime input only for runtime strings. That is the regex rule applied to the hottest data in the library.
- **Module cut the linker can check.** `time` exports `Instant`, `now`, `sleep`, `elapsed`, `within`. `time/civil` exports dates, zones, periods. `time/science` exports `Coordinate`, ephemerides, light time. A program whose source never names civil or science does not link them and does not map their packs. "Pay for what you use" should be a dependency fact, not a promise in a BLUF. This is also the compile-speed rule: hello-world does not tokenize the ephemeris.
- **Zone id is 32 bits.** The pack is append-only and content-addressed. Values from last year's pack still resolve. A tzdata update returns a preview of future occurrences that changed, and applying it is a commit. That preview is the feature calendar libraries keep rebuilding in application code. It falls out of packs plus appointments if `expand` can run twice and diff nominal keys.
- **`array<Instant>` is a packed `int128` column.** Astronomy and logs get vector loads. Float64 TT seconds is an export with a named quantum, for codes that want Skyfield's speed on purpose. The export is not the storage.
- **Ask "what time is it there?" only with a convention.** `mars.now` is not a function. `mars_clock(at convention site)` is. The missing argument is the simultaneity convention, and the type checker asks for it. The same shape covers lunar TCL versus operational LTC: unavailable LTC is `StandardNotDefined`, not an approximate microseconds-per-day constant.
- **The optical second is a realization note.** When the 2030 definition lands, the pack records the resolution and the continuity statement. Ticks do not change. If a future standards body ever inserts a step, that step is a new scale with an explicit transform, and old `Instant`s remain J0 nanoseconds. Adaptability is new packs and new type parameters, not a migration of the integer.
- **Off-grid is a fix-it, not a numeric-tower surprise.** `t + 1ns/3` names the tick and the rounding, or it names `Instant<tick=1ns/3>`. The compiler already does this for integer narrowing. Time should feel like that, not like a rational that silently grew a denominator and then could not be stored.
- **A discrete successor is a feature.** Timeouts, half-open buckets, and "the next representable instant" are well-defined on `Instant` and deliberately undefined on `Coordinate`. v4 spent effort forbidding the successor because it had only one axis. Two axes let systems code have `next` and let relativity keep density.
- **Edition row as the whole calendar-reform plan.** Humanity changes the civil default once a millennium, maybe. Dewy changes one table row, deprecates for one edition, and keeps `Date<Gregorian>` exact forever. No flag day, no reinterpretation of stored integers, no `$calendar` left on in a dependency the caller did not read.

## New spellings proposed

No new keywords. Each of these needs David's approval. Names already listed in v4 §14 are not repeated unless this critique changes their meaning.

| Spelling | Kind | Recommendation |
|---|---|---|
| `Instant<tick=1ns width=128>` | type parameters `tick`, `width` | Approve. Plain `Instant` means this pair. |
| `Coordinate<Scale>` | type | Approve for the science layer. Rational seconds, branded. Not an `Instant`. |
| `OffGrid` | error | Approve. Exact op would leave the tick or the width cannot be proved. Distinct from `OutOfRange` and from `quantize`'s loss report. |
| `instant"…"`, `date"…"`, `zoned"…"`, `zone"…"`, `utc"…"` | delimited calls | Approve as library functions. Literal argument ⇒ compile-time check. Unique ⇒ infallible. |
| `$calendar` | metatag | Approve. Scope-local bare-name override. Inferred type stays parameterized. |
| `edition` | project-file key | Approve as the language edition key, first used by the calendar default. Not a keyword. |
| `.nominal` | member | Approve. The wall/TT instant inside a reading. |
| `1day`, `1week`, `1month`, `1year` | period literals | Approve only as `Period`, legal where a period is expected. `month` and `year` are already decided. `day` and `week` need the same decision. They are not `Time` quantities. |
| `leap_day='march_1'` | policy default | Approve as the `age` default, opt-out `$time.require_profile`. |
| `zone_source='host'` | context policy | Approve as the explicit OS-tzdb opt-in. Default is the pinned pack plus the host zone name. |
| `ZonePackStale`, `NoFeasibleWindow` | errors | `NoFeasibleWindow` is already in v4. `ZonePackStale` is new. Approve as a status, not a failure of `today`. |
| empty `@f()` | lint | Warn. Not a spelling. |

Rejected spellings, so they are not "also available":

- A `NegativeLeap` type or `:60` clamp.
- `mars.now`, or `hour` meaning a Martian hour.
- A process-wide time-warp flag.
- `day` as `86400s`.
- Any new keyword for literals, editions, or clocks.
