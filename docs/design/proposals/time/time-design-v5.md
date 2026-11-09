# Time, dates, clocks and calendars (v5)

v5 merges the v4 review round (the v4 critique, the representation review, the correctness review) with David's fixed decisions. Names are proposals unless §14 lists them as settled.

## What changed from v4

| # | Area | v4 | v5 |
|---|---|---|---|
| 1 | `Instant` | Exact rational, stored as a count of a rational tick | Signed int128 count of nanoseconds; 16 bytes; no heap (David) |
| 2 | Epoch | Apollo recommended | J0 = `1977-01-01T00:00:32.184 TT`, `e=0` (David) |
| 3 | `Duration` | Rational | int128 ns like `Instant`; `width=64` is an explicit compact form |
| 4 | Off-grid values | A finer rational tick absorbed them | `OffGrid`: compile error for constants, a value at runtime; fixed by `quantize`, a caller-named tick, or a science `Coordinate<Scale>` |
| 5 | `now` | `now()`, a heavy envelope with an estimate | `now`: two clock samples in a 32-byte, pointer-free `ClockReading` |
| 6 | `now - start` | Nominal wall difference | Monotonic elapsed time; `.nominal` asks the wall question; `now + 5s` is a monotonic deadline |
| 7 | Acquisition | Every provider at entry | At entry, but only providers the program statically reaches |
| 8 | `today` | A `Date` / `AmbiguousToday` / `UnknownToday` union | `Date`; ambiguity is a query; the union appears only under `$time.require_clock_accuracy` |
| 9 | Literals | Runtime parse plus `or_throw` on every line | `instant"…"`, `date"…"`, `zoned"…"`, `zone"…"`, `utc"…"`: checked at compile time, infallible under a frozen-snapshot contract |
| 10 | `day`, `week` | Used loosely | `1day`, `1week`, `1month` and `1year` are calendar `Period`s; `sleep(1day)` is a compile error |
| 11 | Default calendar | Fixed proleptic Gregorian | Per-module edition; `$calendar` lexical override; public types say `Date<Gregorian>` |
| 12 | Rule data | Pinned packs; host database unspecified | Host zone *name* plus pinned rules; `$time.rules` selects data in source; `zone_source='host'` opt-in |
| 13 | Negative leaps | A featured path | One skipped-label mechanism; tests kept |
| 14 | Modules | A layering list | `time`, `time.civil`, `time.science`; a program links only what it reaches |
| 15 | Strictness | Runtime assumption trace | Compile-time obligations; zero runtime records on the default path |
| 16 | Partials | `@work()` | `@work`; empty `@f()` warns (David) |
| 17 | New sections | — | Examples (15 programs), prior art, a fuller decision list |

---

> **BLUF:**
> - **One axis, one integer.** `Instant` is a signed 128-bit count of nanoseconds since J0 on the ideal TT-rate axis. J0 is nominal TAI midnight, 1 January 1977. Add and subtract are two machine instructions, and nothing allocates.
> - **The common path costs what C costs.** `now` is two clock reads into a 32-byte value. `now - start` is elapsed time on the monotonic clock. Zones, calendars and science are paid for only by programs that use them.
> - **Constants are free; input is checked once.** Time literals are verified at compile time against pinned rules, so `zoned"2026-10-26T09:00[America/New_York]"` is a plain value. `or_throw` appears only where failure is real: user text, I/O, missing data, a runtime gap or fold.
> - **Nothing is guessed.** Gaps, folds, unknown accuracy, missing coverage and off-grid values are compile errors or visible values, never silent repairs.
> - **Built to outlive its standards.** The epoch, the tick and the axis never change. Rules change through pinned data selected in source. Source defaults change through per-module editions, with a deprecation edition in between.
> - **Strictness is opt-in and free.** Each convenience has a `$time.require_*` opt-out that demands a proof instead. `$time.strict` enables all of them, and `$bulletproof` includes it.
> - **No new syntax or keywords.** Everything is library names, metatags and existing operators.

## Vocabulary

| Term | Meaning |
|---|---|
| **Scale** | A coordinate and its rate convention (TT, TAI, UTC, TCB, …) |
| **Realization** | Physical clocks and observations that estimate a scale (TAI, UTC(k), TT(BIPM)) |
| **Epoch** | The chosen zero. Dewy's is J0. |
| **Tick / width** | The quantum a count is in (default `1ns`) / the bits in the count (default 128) |
| **Nominal** | The exact coordinate a label or reading names. It does not claim the event was measured there. |
| `Instant` | int128 ns since J0 on the ideal TT-rate axis |
| `Duration` | int128 ns difference |
| `ClockReading` | What `now` returns: a nominal wall `Instant`, a monotonic sample, provider identity and a status |
| `MonoPoint` | A point on one monotonic provider's clock, e.g. a deadline |
| `Period` | A calendar recipe (`1day`, `1month`), not a number of seconds |
| `Coordinate<Scale>` | An exact rational science coordinate (opt-in; may allocate) |
| `Estimate<T>` | A set of admissible values, with identity so shared error cancels |
| `OffGrid` / `OutOfRange` | Not a multiple of the destination tick / does not fit the width |

Scale, realization, epoch, representation and format are independent: a TAI label can be a scalar, TT can be written as calendar fields, and a Julian date still needs a scale.

**Reading guide:**
- **Core:** the trivial tier, §1 (coordinates), §5 (civil), §7 (clocks), §11 (source settings), Examples and §14.
- **Supporting:** §2–§4 (uncertainty, intervals, UTC) and §6 (recurrence).
- **Applications:** §8–§10, §12–§13, prior art. Skim these.

---

## Trivial tier

> **BLUF:** Ordinary programs use `now`, `monotonic`, `sleep`, `within`, `today` and the literal calls with no setup and no error branches. Subtracting readings measures elapsed time. The only `or_throw` is on user text.

```dewy
let start = now
work
printl"took {now - start}"
sleep(300ms)
printl"today is {today}"
let deadline = now + 5s
loop now <? deadline { poll }
let page = within(2s @fetch) ??<Timeout> cached or_throw
let t = instant"2026-10-24T12:00:00Z"
printl"{t + 90minute}"
let text = read_line ?? ""
let typed = instant(text) or_throw
let dt = (now - start) / 1s as float64
```

### What each line does

This assumes a healthy UTC host, a start at `2026-10-24T12:00:00Z`, and `work` taking 125ms.

| Line | What happens | Cost |
|---|---|---|
| `let start = now` | One wall read and one suspend-inclusive monotonic read, stored in a `ClockReading` | Two clock reads (vDSO on Linux); no zone, locale or allocation |
| `work` | Zero-argument call, no parentheses | — |
| `now - start` | Subtracts the monotonic samples and gives a `Duration`. Prints `took 125ms`. An NTP step during `work` can't affect it. | One int64 subtract |
| `sleep(300ms)` | Waits at least 300ms of monotonic time, including suspension; may wake late | One timer |
| `today` | The nominal `Date` in the captured host zone. Prints `today is 2026-10-24`. | Maps one zone's rules, lazily |
| `now + 5s` | A `MonoPoint` deadline; wall steps never move it | One add |
| `loop now <? deadline` | Compares monotonic samples | One compare per pass |
| `within(…) ??<Timeout> cached or_throw` | A timeout gives `cached`; any other fetch failure, or cancellation, is forwarded | Deadline scope |
| `instant"…"` | Checked at compile time and folded to an int128 constant; no parse at runtime, no error branch | None |
| `t + 90minute` | Integer add. Prints `2026-10-24T13:30:00Z`. | Formatting loads the UTC segment table, nothing else |
| `instant(text) or_throw` | Runtime text gives `Instant \| ParseError \| …`; one `or_throw` at the boundary | One parse |
| `(now - start) / 1s as float64` | Float seconds for physics, explicitly | One conversion |

- **`sleep` and cancellation.** `sleep` already returns `void | Canceled`. Script-level code drops it; inside a function body, forward it with `or_throw`. A clock failure never makes `sleep` return early.
- **Precedence of the last line.** `as` binds looser than `/`, so `(now - start) / 1s as float64` means `((now - start) / 1s) as float64`. The parentheses around the subtraction are required, since `-` binds looser than `/`. `let dt:float64 = (now - start) / 1s` is equivalent.
- **Floats never enter implicitly.** A float can't be added to an `Instant`. A float duration enters through `quantize` (§1).

### `ClockReading`

- **Layout (64-bit targets):** 32 bytes, 16-byte aligned, no pointers.

  | Bytes | Field |
  |---|---|
  | 0–15 | `nominal`: int128 ns since J0, from the wall sample |
  | 16–23 | Monotonic ns, normalized to `0..2^63−1` within the captured session |
  | 24–27 | Domain token: provider instance + reset generation + tick/suspend contract |
  | 28–31 | Status byte (fresh, slewing, stepped, holdover, stale, unsynchronized, accuracy unknown, convention identified) plus reserved bits |

- **Operators:**
  - `reading - reading` gives monotonic elapsed `Duration`. Readings from the same captured session carry a static same-session brand, so this needs no error branch. Runtime-mixed readings give `Duration | DomainMismatch`.
  - `reading + Duration` gives a `MonoPoint`. `reading <? mono_point` compares monotonic samples.
  - `.nominal` gives the wall `Instant`. `now.nominal + 5s` is a wall target, which NTP can move.
  - `=?` compares the semantic fields; wall equality is `a.nominal =? b.nominal`.
- **Two samples, not one.** The wall and monotonic samples are taken in the same operation but are not claimed simultaneous. Subtraction never estimates a wall offset.
- **No codec.** A `ClockReading` is never serialized or deserialized. Persist `.nominal` (an `Instant`) instead, so a round trip can't silently change what `-` means. A `MonoPoint` prints as an offset in its domain (`mono+12.5s`) and has no codec either.
- **No retrospective evidence.** The reading carries a status, not an estimate. An old reading never acquires an `.estimate` from today's calibration. Callers who need evidence use `time.science.observe`, which records the acquisition bracket when it reads (§7).

### Program entry and failure

- **Acquired at entry, only if reached.** At entry the runtime acquires the providers the program statically reaches: wall and monotonic for `now`, monotonic only for `monotonic` and `sleep`, the host zone name for `today`. A pure program acquires nothing.
- **Failure is reported once, before dependent user code runs.** Unavailable providers, unsupported suspend semantics and missing configuration are entry failures. Embedders handle that result or install a test context.
- **Reads are total.** After entry, a read always returns a reading.
  - Losing wall synchronization changes the status to holdover or stale. Elapsed time still works.
  - If no wall seed was ever acquired, entry fails; the runtime never invents epoch zero.
- **Monotonic continuity is an environmental assumption,** like ordinary allocation. If a provider loses continuity (a VM migrated without a continuity guarantee, a counter reset), the task ends with a report through the environmental-failure path. It never returns a reading that looks compatible, a successful zero elapsed time or an early successful sleep.
  - `$time.require_clock_domain` removes the assumption. Reading subtraction then returns `Duration | ClockDiscontinuity | DomainMismatch`, and waits include `ClockDiscontinuity`.
- **Captured providers stick.** Closures and async tasks keep the captured provider across migration and suspension (§7).

### Display

- **Readings** print their nominal wall label with `~` (measured): `~2026-10-24T12:00:00Z`. `?` is added when accuracy is unknown; a stale or holdover status is appended.
- **Instants** print without `~`, because a literal asserts an interpretation, not a measurement. The default format is RFC 3339 UTC within UTC's coverage. Outside it (before 1961) the default is a TT label such as `-0584-05-28T12:00:00 TT`, never an invented `Z`.
- **Durations** print through the existing unit chooser (`125ms`, `1h`).

### `today`

- **`today` returns `Date`:** the nominal date of the reading in the captured zone.
- **`time.civil.today_support`** returns the set of dates the clock's actual support spans. It is one date normally, several near midnight with a wide error, and unknown when accuracy is unknown. Any date boundary can be straddled, not only an ambiguous civil midnight.
- **Under `$time.require_clock_accuracy`,** `today` itself returns `Date | AmbiguousToday | UnknownToday`.

---

## 1. The coordinate core

> **BLUF:**
> - `Instant` is `Instant<tick=1ns width=128>`: a signed count since J0 on the ideal TT-rate axis.
> - Other ticks and widths are explicit types on the same epoch and axis. Width never depends on tick.
> - Arithmetic is exact. Intermediates widen; storage narrows only where proven.
> - An exact value off the destination grid is `OffGrid`. The fix is `quantize`, a caller-named tick or a science `Coordinate<Scale>`, never silent rounding.
> - `as` is only for unique, exact conversions.

### The axis

- **Points and differences.** `TimePoint<Domain>` is an affine point type. `Instant` is its terrestrial specialization on the ideal TT-rate axis.
- **Stable.** The axis does not move when metrologists improve a realization.
- **A convention.** It is mathematical. It is not every observer's proper time, nor a universal simultaneity.

### Epoch: J0 (settled)

- **The value.** J0 is `JD 2443144.5003725 TT`, whose TT label is `1977-01-01T00:00:32.184 TT`. Its nominal TAI-compatible label is `1977-01-01T00:00:00`. `e=0`.
- **Why it's clean.** The stored integer is nominal TAI-compatible nanoseconds since 1977 TAI midnight. `32.184s` appears only in the TT label and in science conversions, never in `now`, add or subtract. TT, TCG and TCB coincide at J0 by the standards' definition, so science code never subtracts an epoch offset before scaling.
- **Reference integers,** independently recomputed by two reviewers with exact fractions. They are re-derived again in the acceptance suite before the wire format freezes.

  | Event | ns from J0 |
  |---|---|
  | J0 | `0` |
  | `1970-01-01T00:00:00 UTC` (TAI−UTC = 8.000082s) | `−220924791999918000` |
  | Apollo 11, `1969-07-20T20:17:40 UTC` (TAI−UTC = 7.5745938s) | `−235107732425406200` |
  | GPS epoch `1980-01-06T00:00:00 GPS` (= TAI−19s) | `95040019000000000` |
  | J2000 `2000-01-01T12:00:00 TT` | `725803167816000000` |

- **Labels** defining origins use proleptic Gregorian fields. The digits are conventions, not observation accuracy.

### Defining constants (exact)

- `L_G = 6.969290134e-10`, `L_B = 1.550519768e-8`, `TDB0 = −6.55e-5s`, and the TAI-to-TT(TAI) offset `32.184s`.
- For each scale S, `x_S = (JD_S − J0) × 86400s`. Each JD belongs to its own scale; equal numbers in different scales do not identify the same remote event.
- With `e=0`: `x_TT = n × tick`, `x_TT = (1 − L_G) × x_TCG` and `x_TDB = (1 − L_B) × x_TCB + TDB0`. The inverses divide by `1−L`.
- **These maps live in `time.science`.** Their results are generally off the nanosecond grid, so they produce `Coordinate<Scale>` values. Neither equation supplies the geocentric-to-barycentric spacetime transformation (§4). Sources: [ERFA TT/TCG](https://raw.githubusercontent.com/liberfa/erfa/master/src/tcgtt.c), [ERFA TCB/TDB](https://raw.githubusercontent.com/liberfa/erfa/master/src/tcbtdb.c).

### Counts, ticks and widths

- **Spelling.** `Instant<tick=τ width=w>` and `Duration<tick=τ width=w>`. τ is a positive rational constant; w is a fixed width. Plain `Instant` and `Duration` mean `tick=1ns width=128`.
- **A tick is only a representation.** It never changes scale, realization, epoch or observer. `Instant<tick=1ns/3>` is still an `Instant` on TT/J0, just not the plain alias.
- **Width is independent of tick.** Changing the tick never changes the width; footprint never jumps at a range threshold. Ranges, with a Julian year of 31,557,600 s:

  | Form | Half-range | Bytes |
  |---|---|---|
  | int64 × 1ns | ±292.27 years (September 1684 to April 2269 from J0) | 8 |
  | int64 × 1µs | ±292,271 years, but loses nanosecond inputs | 8 |
  | int128 × 1ns | ±5.39×10²¹ years; ±10,000 years needs 70 bits, ±1M years 76 | 16 |

- **`width=64`** is the explicit compact form for bulk contemporary data: a million timestamps take 8 MB instead of 16 MB, and a cache line holds eight instead of four.
- **Costs (backend probes, not Dewy benchmarks).** int128 add and subtract are two instructions on x86-64 and AArch64 (`add/adc`, `sub/sbb`). Comparison is a few. General division calls `__divti3`; it appears in formatting and tick conversion, never in point arithmetic. Confirm with Dewy's instruction-count gates before landing.
- **No wrap, saturation or heap promotion,** ever.

### Exact arithmetic and narrowing

These are Dewy's existing fixed-width integer rules, applied through the time wrappers. Nothing here is time-specific.

- **Width constrains stored counts, not intermediates.** `max − min` of two int128 counts needs 129 bits. A bounded expression uses extra machine limbs without allocating.
- **Narrowing happens at annotated slots:** a binding, field, argument, return or conversion. An unannotated result keeps the wider representation its range needs.
- **An unproved narrowing is a compile diagnostic** by default and a check under `$runtime_checks`. It is not an `OutOfRange` value. `convert<T>(x)` is the value-returning boundary: it returns `OutOfRange` for an actual range failure.
- **Real bounds do the proving.** The OS adapter bounds `now.nominal`, so `now.nominal + 5s` is provable. Two unconstrained imported endpoints aren't. The counter-progress axiom does not extend to int128 timestamps.

### Off the grid

- **Definitions.** `OffGrid` means the exact value is not an integer multiple of the destination tick. `OutOfRange` means the count doesn't fit. An invalid leap label, a missing era or an absent model is neither.
- **Quantities stay exact.** `1ns/3` and `1s/3` remain legal exact time quantities; they just aren't plain `Duration`s. Unannotated `0.1s` is an exact decimal: exactly 100,000,000 ns, on the grid.
- **Constant off-grid uses are compile errors** with fix-its: `quantize` with a named rounding, a caller-named tick, or `Coordinate<TT>`.
- **Runtime off-grid values** go through `convert<T>`, which returns `T | OffGrid | OutOfRange`.
- **`quantize(tick=… rounding=…)`** returns `[value loss]`, where loss is original minus rounded. It can still fail on range. For example, `1ns/3` rounded nearest-even to `1ns` is `0ns` with loss `1ns/3`.
- **`x.ticks(tick)`** floors: `x − epoch = count × tick + remainder` with `0s <= remainder < tick`. `−0.25s` at `1s` gives count −1, remainder `0.75s`.
- **Floats.** A float duration enters only through `quantize`, or `convert` when its exact binary value is on the grid. NaN and infinities never become counts.

```dewy
let t = instant"2026-10-24T12:00:00Z"
let later = t + 0.1s                                # exact: 100000000ns
# t + 1ns/3                                         # compile error: OffGrid, with fix-its
let fine = (t as Instant<tick=1ns/3>) + 1ns/3       # caller-named tick
let [nearest loss] = fine.quantize(tick=1ns rounding='nearest_even')
let checked = convert<Instant>(fine)                # Instant | OffGrid | OutOfRange
let packed = t as Instant<width=64>                 # constant, so the range is proven
```

### Ticks meeting ticks

- **Same tick:** integer operations that stay in the type.
- **Different ticks:**
  - `as` converts when exactness and range are proven, for example when the source tick is a multiple of the destination tick.
  - Comparison is mathematically defined even when neither conversion fits: it uses widened scaled integers.
  - Hashing is per type. There is no shared rational hash; heterogeneous hash keys are deferred.
- **Successor.** On a tick grid, `t + tick` is the successor, except at the maximum. This does not erase interval endpoint flags (§3).

### Epoch shifts and foreign origins

- **Integer-nanosecond shifts are exact `as` conversions:** the GPS epoch, J2000 TT, CCSDS 1958-01-01 TAI, and the Unix-origin event.
- **A POSIX count is not an epoch shift.** POSIX days omit leap seconds. The UTC segment table carries old leaps, and the codec carries its leap behavior (§4, §11).
- **A native grid doesn't survive an epoch shift.** An NTP value on a binary grid relative to its own origin need not stay on that grid after shifting to J0. Codecs keep their native origin and tick (§11).

### Nominal vs realized time

- **`TAICompatible` is a nominal label:** the calendar number of an ideal TT coordinate, offset by `−32.184s`. It never claims to be published realized TAI.
- **Realized records keep their realization identity:** TAI, UTC(k), TT(BIPM edition), provisional products and clock correlations.
  - `TT(TAI) = TAI + 32.184s` is exact within that realization.
  - The mapping to ideal TT is an estimate.
- **Recalibration adds, never rewrites.** A new calibration produces a new event estimate and never changes a stored count.
- **Projection onto `Instant` is a named operation** that keeps its assumption. It is not `as`.

### What `as` may do

- **Allowed:** unique, exact, applicable conversions only, meaning units, frozen epochs, ticks with proven exactness, and definitionally related scales.
- **Named operations instead:** approximate models, context selection, civil inverses, rounding, and interpreting measured events.
- **Domains never become compatible through a cast:** unrelated devices, boots, observers and frames stay distinct.

### Science coordinates

- **`Coordinate<Scale>`** lives in `time.science`. It is a specialization of the `TimePoint<Domain>` machinery: exact rational seconds from a statically named origin.
- **Opt-in, with a stated cost.** It may allocate and has a variable denominator. Using `now`, `Duration` or `Instant<tick=1ns/3>` never loads it.
- **`Scale` names a complete domain definition,** not a string like `"TCB"`.
- **Fixed finer ticks often suffice.** An NTP fraction, a PTP correction, or an affine map with bounded denominators works without rationals. `Coordinate` is for runtime rational input, arbitrary model composition and exact scale maps.
- **Model-based transforms** return `Estimate<Coordinate<Scale>>` or bounded results, never a false exact value.

### The second and future standards

- **A redefinition is still a proposal.** CGPM Resolution 4 (2026) requests a proposal to redefine the second on optical standards, targeted at the 2030 CGPM. It is not adopted. [Resolution 4](https://www.bipm.org/en/cgpm-2026/resolution-4)
- **A continuous redefinition changes no counts.** It changes realization knowledge, recorded in packs.
- **A different rate convention** would be a new domain with an explicit transform. Old `Instant`s stay J0 nanoseconds.

---

## 2. Answers, estimates and evidence

> **BLUF:**
> - A lookup returns one answer, a set of candidates, a proved-empty result, or a *specific* unresolved outcome. It never guesses.
> - `Estimate<T>` (in `time.science`) is a set of admissible values with identity, so arithmetic tracks shared error (`X−X = 0`) and never assumes independence.
> - Ordinary values carry no estimate. Evidence is acquired on request and never reconstructed afterward.

### Kinds of answer

- **Civil outcomes:** `Gap` is an established missing civil span; `Ambiguous` carries every known alternative with its explanation.
- **Unresolved outcomes are distinct:** `MissingContext`, `MissingData`, `OutsideCoverage`, `Unknown`, `UnsupportedModel` and `InconsistentEvidence`. An absent provider never becomes an empty candidate set.
- **`Unspecified` vs `Unknown`:** information deliberately omitted vs sought but not known.

### `Estimate<T>`

- **Contents:** a stable variable identity, a domain, a support or constraints, evidence references, and an *optional* nominal representative. Two competing historical interpretations need no privileged midpoint.
- **Support** can be a singleton, a disconnected set, an interval set, a constrained symbolic object, or unknown.
- **Distribution and confidence** are optional extras. A 95% interval is not a guaranteed bound.
- **Error sources stay separately identified:** measurement, quantization, numerical error, model discrepancy, future-rule scenarios and source disagreement. Display precision is not accuracy.
- **Partial labels.** `YearMonth` is a partial label, not a uniformly distributed instant.

### Dependence and arithmetic

- **Joint, not marginal.** `X+d` translates every possible value; `Y−X` is evaluated on the same joint assignment.
- **Examples:**
  - `X−X` is exactly zero, even with unknown support.
  - With `X=10s+E` and `Y=13s+E`, where `E` is one calibration offset in `[0s,2s]`, `Y−X = 3s`.
  - With only marginal bounds `[10s,12s]` and `[13s,15s]`, subtraction gives `[1s,5s]`.
- **Copies keep their identity.** Independently imported equal bytes are not the same variable, and shared error is never inferred from identifiers an untrusted producer supplied.
- **Probability is opt-in.** `Var(Y−X) = Var(Y)+Var(X)−2Cov(X,Y)`. Root-sum-square needs a justified zero-covariance model, supplied explicitly and retained in the result.
- **Soundness over precision.** If dependence is forgotten, the result is a conservative enclosure; same-variable cancellation is still kept. A convex hull of disconnected possibilities is an explicitly lossy enclosure. If neither exact propagation nor a sound enclosure is possible, the result is `UncertaintyUnsupported`.
- **Contradictory evidence** gives an inconsistency, never an empty successful estimate. Adding evidence creates a new value and keeps the old evidence graph.

### Where evidence lives

- **Not on ordinary values.** `ClockReading`, `Instant` and `ZonedDateTime` carry no estimate and no evidence graph.
- **Acquired, not reconstructed.** `time.science.observe` returns a `ClockObservation` holding an acquisition bracket, the correlation revision and an `Estimate<Instant>`, all captured when it reads.
- **Older readings can't gain precision.** Asking an old compact reading for evidence gives `Unknown`. It never borrows today's error bound.

### Equality and ordering

- **Exact coordinates** have Boolean equality and order within a compatible domain. Identity is never inferred from coordinates: event identity, recurrence identity and original spelling are separate questions.
- **`compare_estimates(X Y)`** quantifies over the nonempty joint admissible set:
  - `Before`, `After` and `Same` hold only if true for *every* assignment.
  - `Same` needs shared identity or equal exact singletons; overlapping ranges are not enough.
  - Otherwise the result is `Indeterminate`, listing the possible relations. Unknown domains give `Incomparable`.
- **`certainly_before` and `possibly_before`** are derived queries. A proof-limited engine returns unknown with a reason, never false certainty.
- **Kept separate:** tolerance equality (not a hash equivalence) and causal comparison (vector-clock `Concurrent`, relativistic `Spacelike`). `if` still needs a Boolean.

---

## 3. Intervals and topology

> **BLUF:**
> - Intervals store explicit endpoint-inclusion flags. The convenience constructor `interval(a b)` is half-open `[a,b)`.
> - An unknown end is not an infinite end.
> - Allen's 13 relations classify endpoint geometry only; empty and point cases get their own tagged results.

### Representation and constructors

- **Contents:** domain, two bounds and inclusion flags. A bound is a finite coordinate, a known unbounded end, or an unknown endpoint with constraints.
- **"Until further notice"** has an unknown end. It does not assert that the activity never ends.
- **Checked construction.** Domains must match and endpoints must be ordered; an unresolved order gives a constrained interval or an unresolved result.
- **Constructors.** `interval(a b)` is `[a,b)`. Open and closed constructors always exist. Equal finite endpoints give a singleton only when both ends are closed; infinite endpoints are never members.

### Successors and density

- **Grids have successors.** On a tick grid, `[a,b]` and `[a, b+tick)` contain the same instants, but the flags are still kept: the rewrite fails at the maximum count and changes Allen endpoint geometry.
- **Calendars have successors by capability.** An ordered calendar can prove a successor; the British day after 1752-09-02 is 1752-09-14. Partial or observational calendars may not have one.
- **Science coordinates are dense.** `Coordinate<Scale>` has no successor, so a closed end cannot become half-open there.
- **Physical intervals and grids.** Projecting a physical uncertainty interval onto integer points needs a rounding or enclosure rule.

### Set operations and measure

- **Flags are respected** by union, intersection, difference, complement relative to a named universe, membership, containment and disjointness. Canonical interval sets merge only when the union adds no missing point.
- **Measure:**
  - A finite interval measures `b−a`, whatever its flags.
  - An unbounded interval has infinite measure, outside finite `Duration`.
  - An unknown endpoint gives an estimated or unknown measure.
- **A calendar span's length is not elapsed time.**

### Allen relations

For proper intervals A=(a,b), B=(c,d):

| Relation | Condition | Relation | Condition |
|---|---|---|---|
| before | `b<c` | starts | `a=c`, `b<d` |
| meets | `b=c` | during | `c<a`, `b<d` |
| overlaps | `a<c<b<d` | finishes | `c<a`, `b=d` |
| equals | `a=c`, `b=d` | | |

- **Inverses.** The other six relations are the inverses of the first six.
- **Geometry only.**
  - `[a,b)` meets `[b,c)` and is disjoint from it.
  - `[a,b]` meets `[b,c]` and intersects it at `b`.
  - `same_set` also compares topology.
- **Degenerate cases.**
  - Empty inputs give `EmptyOperand`.
  - Point vs point gives before/equal/after.
  - Point vs interval gives before/start/interior/end/after.
- **Uncertain endpoints** give the *set* of possible relations over the admissible joint assignments. Constraints narrow it, and a limited search returns a marked sound superset. Composition uses the standard Allen table.

---

## 4. Scale transformations and UTC

> **BLUF:**
> - Converting between scales uses declared, versioned transformations. Route choice is never silent.
> - UTC is a versioned segment table relating labels to realized atomic time. It includes continuous UTC from **20 May 2027**.
> - Leap seconds, smears, POSIX, FILETIME, JD/MJD and GNSS are adapters that keep their conventions.

### Transformations

- **Each declares:** source and target domains, the event position it needs, its model edition, data dependencies, applicable region, accuracy contract and algorithm. Composition keeps all of these.
- **No silent routes.** The context names a preferred route, or the alternatives are returned.

| Conversion | Nature |
|---|---|
| TT↔TCG, TCB↔TDB | Exact affine maps (§1); results are `Coordinate`s |
| TAI↔TT(TAI) | Exact offset within one realization |
| TCG↔TCB | Spacetime-event transform: location, Earth trajectory, potentials, a named approximation |
| TT↔TDB | Composes the above. A geocentre approximation names its location and error envelope; a scalar alone can't determine it. |
| Proper time | Integrates a worldline in a metric |
| UT1 | Measured or predicted Earth orientation; ΔT models before records |
| SCLK | Mission clock correlation |

### UTC

- **A versioned relation** to realized atomic labels, in segments:
  - **Before 1961:** outside coverage. An ancient `Z` label is invalid unless an explicit proleptic convention is selected; ancient astronomy uses TT or reconstructed UT1 (Examples 12).
  - **1961–1971:** fractional offsets with rate adjustments, using the dated formula. A `1ns` label step in the 1968 segment is `1.00000003ns` of atomic time, so sub-microsecond pre-1972 labels can be `OffGrid`.
  - **1972 onward:** integer leap steps. Twenty-seven positive leaps have occurred; none negative.
  - **From 20 May 2027:** continuous UTC with `|UT1−UTC| ≤ 3600s`. It is a new segment with an inherited offset from authoritative records, not a year test or a hardcoded `37s`. No leap-hour mechanism is specified. [CGPM Resolution 5](https://www.bipm.org/en/cgpm-2026/resolution-5)
- **The last possible leap is already ruled out.** IERS Bulletin C 72 (July 2026) announced no leap at the end of December 2026. [Bulletin C 72](https://datacenter.iers.org/data/16/bulletinc-072.txt)
- **Future amendments are new segments.** This is the current standard, not proof that UTC never changes again. Stored labels are never rewritten.

### Leap seconds

- **Positive leaps** validate the actual inserted label. `utc"2016-12-31T23:59:60"` is valid; `utc"2015-12-31T23:59:60"` is a compile error (`InvalidFields`, not `OffGrid`).
- **Arithmetic ignores leaps.** `Instant` is continuous TT-rate. From `2016-12-31T23:59:59 UTC` to the following midnight is `2s`.
- **No clamping.** Dewy never clamps `:60` to `:59`.
- **Negative leaps use the general skipped-label mechanism** in the segment table, the same machinery as a zone gap. There is no dedicated type or path.
  - A synthetic segment exercises label adjacency, the shortened UTC day, POSIX/NTP inversion and named smears.
  - The tests stay, because sharing lookup code does not make UTC codec behavior identical to a DST gap.
- **Standalone times of day** can carry an unresolved leap marker; validating it needs a date and a segment.
- **Old announcements.** An expired bulletin doesn't invalidate an established leap. An old pack can't certify new future policy.

### The live offset cache

- **What `now` adds.** `now` adds the current segment's TAI−UTC offset to the wall sample. It never walks the table or multiplies by `L_G`.
- **The cache knows its limits.** It records its validity interval and the next scheduled transition from the pinned pack. A process running across a pinned transition switches on time, with no pack update needed.
- **A wall jump re-checks the segment,** whether forward or backward.
- **Unknown smear or leap phase** is shown in the status bits, never labelled exact UTC.
- **This nominal value** is neither a POSIX count nor realized TT to metrological accuracy.

### Adapters and labelled numbers

- **POSIX and FILETIME** are adapters. A collapsed or repeated second can have several inverses, and a raw OS reading needs its leap behavior identified (`UnknownClockConvention` at acquisition, once).
- **Smears** are named profiles with window, formula, version and inverse multiplicity. An unknown smear can't resolve uniquely.
- **JD/MJD** need scale tags. `MJD = JD − 2400000.5`, which also moves the day boundary.
- **J2000** as this exact epoch is `JD 2451545.0 TT`, not automatically TDB or a frame.
- **GNSS** systems have distinct epochs, offsets, realizations and truncated eras. Era resolution needs external evidence, and correction conventions travel with navigation data.

---

## 5. Civil calendars, zones and arithmetic

> **BLUF:**
> - **Separate types.** Date, time of day, local date-time, offset, zone and zoned date-time are separate types. Resolved values are compact; intent is a separate, richer record.
> - **Literals are plain values.** A constant date, zone or zoned time is checked at compile time against pinned rules. A gap or fold with no policy is a compile error with a fix-it.
> - **Calendar periods aren't durations.** `1day`, `1week`, `1month` and `1year` are calendar `Period`s, so `meeting + 1day` keeps the local time and `sleep(1day)` is a compile error.
> - **The default calendar is `Gregorian`** (arithmetic, proleptic, year zero), chosen by the module's edition; `$calendar` overrides it lexically.
> - **No silent fixes.** Folds and gaps resolve only under a named policy.

### Types

| Type | Contents | Size |
|---|---|---|
| `Date<C>` | Calendar day ordinal in calendar C | 8 bytes (Gregorian) |
| `TimeOfDay` | ns since local midnight | 8 bytes |
| `LocalDateTime<C>` | Date + time of day; no zone | 16 bytes |
| `Offset` | Fixed UTC offset, to the second | 4 bytes |
| `Zone` | Handle to a zone in a pinned pack | 4–8 bytes |
| `ZonedDateTime` | `Instant` + zone handle + resolved offset | 32 bytes after alignment |
| `Resolution` | Original local fields, calendar, zone, policies, pack identity, trace | Heap; opt-in |

- **Nothing is hidden.** A date has no hidden hour, and a time has no hidden date or zone.
- **Compact vs faithful.** A `ZonedDateTime` answers "which instant, shown where". It does not remember repaired gap displacement or the original text. Code that must keep those asks for the `Resolution` record (`zoned(… keep='resolution')`), or stores intent as an `Appointment` (§6).
- **Handles are pack-scoped.** A zone handle refers to a pack the context keeps alive and is never reused while referenced. Wire formats carry the portable zone ID plus pack identity, never the process-local handle.

### Literals and their contract

- **The literal calls are ordinary delimited calls,** like `printl"…"` and `p"…"`, with no new parser syntax:
  - `instant"2026-10-24T12:00:00Z"` gives an `Instant`. An offset (`Z` or `±hh:mm`) is required; without one it's a compile error with a fix-it to `zoned`.
  - `date"2027-01-31"` gives `Date<C>`, with C from `$calendar` or the edition.
  - `zone"America/New_York"` gives a `Zone`.
  - `zoned"2026-10-26T09:00[America/New_York]"` gives a `ZonedDateTime`; so does `zoned("2026-10-26T09:00" zone=ny)`.
  - `utc"2016-12-31T23:59:60"` gives a `UtcLabel`, which keeps `:60`; `.nominal` gives its `Instant`.
- **The same function on runtime text is fallible,** which is the rule `regex` already follows: `zoned(text zone=ny)` returns `ZonedDateTime | ParseError | Gap | Ambiguous | UnknownZone | OutsideCoverage`. The literal form refines that to the success type.
- **When a literal is infallible.** A literal call drops its error alternatives only when every input is frozen and the result is:
  - **pack-identified:** resolved against the `$time.rules` selection, whose identity the compiled artifact records;
  - **within coverage** of that pack;
  - **unique:** no gap or fold, or a written policy resolves it;
  - **on-grid and in range** for the destination type.
- **Anything else is a compile error with a fix-it.** For a gap: add `gap=…`. For a fold: add `fold=…`. For an unsupported constant evaluation: use the runtime form deliberately. Nothing depends on the compiling host's zone, clock or network.
- **What a literal proves.** It proves a numeric interpretation under the snapshot, not future law or physical accuracy.
  - A 2035 meeting compiled in 2026 stays reproducible, but whether it matches 2035 law is unverified.
  - `$time.require_future_rules` demands an explicit scenario.
- **Resolved values are frozen; appointments stay live.** A resolved literal remains that snapshot's value even if a different tzdb is present at runtime. Showing it under other rules is a named operation. A *live appointment* keeps its local intent and re-resolves only through explicit migration (§6).
- **Pack bytes stay at compile time.** Bytes used only to fold a literal need not ship. Later civil arithmetic or display on the value may need them.

### Calendar periods

- **`1day`, `1week`, `1month` and `1year` are `Period` values,** legal only where a period is expected. `month` and `year` are already calendar-only (decided). `day` and `week` join them.
- **Why `day` can't be a `Duration`.** A Duration-typed `1day` would equal `24hour`. By substitution invariance, `meeting + 1day` and `meeting + 24hour` would then have to behave the same, and the calendar meaning would be lost. So the calendar meaning can't live on a `Duration`.
- **Meanings:**

  | Expression | Result |
  |---|---|
  | `zoned + 1day` | Same local time tomorrow, under the scope's gap/fold policy |
  | `date + 1day` | The calendar successor (British 1752-09-02 → 09-14) |
  | `1week` | Seven day successors; other cycles are explicitly named calendar periods |
  | `instant + 1day`, `sleep(1day)` | Compile error; fix-it `24hour` (or a zoned add) |
  | `date + 1month` | Calendar month; overflow (the 31st) needs `overflow=` |

- **The scope's policy.** `$time.gap = 'preserve_displacement'` and `$time.fold = 'earlier'` set lexical defaults.
  - Without them, a civil add on a *runtime* zoned value returns `ZonedDateTime | Gap | Ambiguous`.
  - A literal operand is proved at compile time.
  - Explicit `.add(1day gap=… fold=…)` always works.
- **`Period` is an ordered recipe.**
  - Composition keeps order and need not commute.
  - Structural equality, equality at an anchor and comparison at an anchor are separate operations; `1month` vs `30day` has no context-free order.
- **Elapsed vs civil differences.** `zoned − zoned` is elapsed `Duration`; `date − date` counts calendar successors. Calendar differences of other shapes are named operations with a decomposition convention.

### Calendars, `Gregorian` and `$calendar`

- **`Gregorian`** is the arithmetic proleptic Gregorian calendar with astronomical years, including year zero. It claims no historical adoption; jurisdictional histories are separately named calendars (`British`, `Swedish`, …). §14 asks David to choose this name or `ProlepticGregorian`. This document uses `Gregorian` throughout.
- **Bare `Date`, `date"…"` and `today`** take their calendar from the module's edition (§11): edition 2026 means `Gregorian`. The inferred type is always concrete (`Date<Gregorian>`).
- **`$calendar = Hebrew` is a lexical override** for the next declaration or block. It never changes a dependency's meaning, and the provider context must agree or convert explicitly.
- **Public and persisted types name the calendar:** library signatures say `Date<Gregorian>`, and stored dates carry the calendar's definition identity.
- **The calendar protocol** specifies field identities, validation, label↔ordinal relations, month sequences, era mapping and optional cycle membership.
  - Relations can be partial: multivalued, pending publication, or valid only within an evidence horizon.
  - Arithmetic calendars give total contracts.
  - A calendar needn't have 12 months, named months or 7 weekdays. Leap months have distinct identities.
- **Separately named implementations:** Chinese and Hebrew leap months; Islamic observation and calculation variants; Persian equinox variants; Japanese eras (including mid-year transitions and unpublished future names); Ethiopian, Coptic and Buddhist conventions. Religious and civil uses can select different authorities.

### Day boundaries and history

- **`DayBoundary`** connects a calendar day to physical events: zone midnight, local sunset, a body's solar phase, or a published schedule. Each needs a location, model and authority.
  - A boundary can be absent or ambiguous; a day then realizes to an interval set or unresolved support.
  - Unequal seasonal hours need a location and a solar model; they are not `hour`s.
- **Historical calendars** compose reforms, year-start changes, interrupted reforms, exceptional insertions and delayed local adoption.
  - British 1752: the day after September 2 is September 14.
  - Swedish `1712-02-30` is valid in its own sequence.
  - A historical gazetteer resolves changing places and borders.
  - Original transcription, Old Style/New Style and double dating stay attached to the value. Contradictory records stay unresolved.

### Zones and geography

- **A zone** is an identity plus a versioned transition relation. Offsets can be fractional hours and seconds.
  - Transitions can be any size, at any hour, any number per year.
  - DST is metadata, not the resolver.
  - Synthetic histories can produce more than two candidates.
- **Matching offsets don't mean the same zone.** Neither equal offsets nor equal current rules establish identity. Aliases keep the original key; `CST` gives candidates.
- **Location → zone** is a separate time-indexed spatial relation. Locale never supplies a location. Law and observed practice are separate assertions.
- **Travelers** use an itinerary, and ships may keep an operational clock. Crossing the date line changes labels without adding elapsed days.

### Resolution policies

- **Native resolution never guesses** a fold or repairs a gap.
- **Named policies:**
  - earliest, latest or all candidates;
  - reject or skip;
  - preserve displacement through the gap;
  - move to the next valid boundary.
- **Displacement vs boundary.** A missing 02:30 in a one-hour gap becomes 03:30 under preserve-displacement and 03:00 under next-boundary.
- **`choose`** takes the whole resolution union as a free function, so a forwarding method call can't bypass an ambiguity. Policy traces stay in `Resolution` records.
- **Overflow:** reject, clamp, or skip. Repeated clamping from January 31 differs from an anchored month-end series (§6).

### Anniversaries and `age`

- **`age` counts completed anniversaries** and is a date rule, never elapsed seconds divided by a year.
- **Default leap-day rule:** `leap_day='march_1'` (a 29 February birthday's anniversary in common years is 1 March). This is a convention default, recorded as an assumption of `$time.require_profile`, which makes the argument required for 29 February birthdays. Other birthdays never need it. §14 flags this default.
- **`legal_age`** always takes a jurisdiction; generic `age` is not legal advice.
- **The `on` date must be on or after the birth date.** That is a proven obligation, in Dewy's partial-operator idiom.

### `zoned` and dates in practice

Assumes the edition-2026 default calendar and a `$time.rules` selection covering these dates.

```dewy
let ny = zone"America/New_York"
let meeting = zoned("2026-10-26T09:00" zone=ny)
let repeated = zoned("2026-11-01T01:30" zone=ny fold='later')
let shifted = zoned("2026-03-08T02:30" zone=ny gap='preserve_displacement')
let next_week = meeting + 1week
let ends = meeting + 90minute
let jan = date"2027-01-31"
let feb = jan.add(1month overflow='clamp')
let age = date"2000-05-12".age(on=date"2026-10-24")
let leap_age = date"2000-02-29".age(on=date"2027-02-28")
let meeting_time = meeting.nominal

let text = read_line ?? ""
let entered = zoned(text zone=ny) or_throw
let next = appointments.next(after=meeting_time) ??<NoOccurrence> none
```

| Binding | Result |
|---|---|
| `meeting` | Monday 09:00 −04:00; no policy needed |
| `repeated` | The later 01:30, −05:00 |
| `shifted` | 03:30 −04:00 |
| `next_week` | Monday 2 November 09:00 −05:00, 169 elapsed hours later |
| `ends` | 10:30 −04:00 (an exact 90 minutes) |
| `feb` | 2027-02-28; without `overflow=` it's a compile error |
| `age`, `leap_age` | 26 and 26 (the default `march_1` rule) |
| `meeting_time` | The resolved nominal `Instant` |
| `entered` | User text: the one real fallible boundary |
| `next` | `??<NoOccurrence>` leaves missing data and pending publication visible |

---

## 6. Intent, recurrence and scheduling

> **BLUF:**
> - **Separate records.** What the user meant (`Appointment`) is stored separately from each resolved `Occurrence`, from what happened (`Event`) and from measurements (`Observation`).
> - **Recurrences** expand lazily within budgets and keep stable keys. Unresolved occurrences stay visible instead of being skipped.
> - **RFC 5545** is an opt-in compatibility profile.

### Records

- **`Appointment`** keeps what should stay fixed:
  - a coordinate;
  - local fields in a named zone;
  - floating fields (the same local time wherever used, or bound to an itinerary);
  - a physical condition.
- **`Occurrence`, `Event`, `Observation`.** An `Occurrence` is one resolution with its evidence and policies. An `Event` is what happened; an `Observation` is a measurement or reception.
- **Intent survives resolution.** A resolved `zoned` constant alone does not say whether a series preserves an instant or a local time; the recurrence keeps both the local fields and the chosen semantics.

### Recurrence

- **Pipeline:** nominal occurrence keys, then calendar candidates, then resolutions.
- **Retained:** anchor, calendar, zone behavior, rule profile, invalid-day/gap/fold choices, inclusions, exclusions, overrides, termination basis and data-update policy.
- **Identity.** The key is the series identity plus the original recurrence coordinate. Rescheduling changes the realization, not the key. Emitting both sides of a fold adds branch identities.
- **Selectors:** daily or weekly, nth or last weekday, month-end anchors, leap anniversaries, alternate-calendar dates, solar events and institutional sessions. Unions, intersections and exceptions have defined precedence and duplicate suppression.
- **Policies only where needed.** An occurrence that needs a policy the series lacks comes back unresolved, not as a construction error. Literal anchors are still checked at compile time.
- **Several zones.** Participants in different zones share one intent and project it independently.

### Expansion

- **Bounded and lazy.** Expansion is bounded by a window, a candidate-work limit, an output limit and cancellation. It returns outputs plus a resumable cursor.
- **Distinct outcomes:** `NoOccurrence`, `AwaitingPublication`, `OutsideCoverage` and `SearchBudgetExceeded`. There is no hidden unbounded search.
- **Counting and order.** Counts say whether they count nominal candidates or emitted occurrences. Output is ordered by nominal key or by resolved time, as stated.

```dewy
let weekly = time.civil.recurrence(zoned"2027-01-04T09:00[America/New_York]" every=1week)
let window = interval(instant"2027-01-01T00:00:00Z" instant"2028-01-01T00:00:00Z")
let [occurrences cursor] = weekly.expand(window limit=100)
let next = weekly.next(after=window.end) ??<NoOccurrence> none
```

- **Keeps Monday 09:00** across both DST transitions. It needs no gap or fold policy, because 09:00 is never in a New York transition under the pinned rules.
- **`expand` is total** for a covered window. Unfinished work comes back as the cursor, and unresolved occurrences come back in-band.

### RFC 5545 profile

- **Explicit vs generated values.**
  - An explicit DATE-TIME in a fold takes the first occurrence; one in a gap uses the pre-gap offset.
  - Generated invalid dates and nonexistent times are skipped and don't consume COUNT. Generated folds take the first occurrence.
  - So a New York 02:30 imported as an explicit DATE-TIME means 03:30, but is omitted when RRULE generates it.
- **Termination and ends.**
  - UNTIL's type follows DTSTART: DATE with DATE, floating local with local, UTC or TZID starts with UTC.
  - COUNT and UNTIL are exclusive.
  - An exclusive DTEND is intentional interval semantics, not an off-by-one.
- **Durations and alarms.**
  - `P1D` is nominal (a `Period`); `PT24H` is exact.
  - Component addition order is preserved.
  - VALARM triggers keep their start/end basis and repeats.
  - DATE events get their default duration.
- **Series edits.**
  - RDATE, EXDATE and RECURRENCE-ID keep their roles.
  - `THISANDFUTURE` orders by original recurrence IDs and shifts later starts by the same difference. It is not a rule-pack migration, though it can reuse that machinery.
- **Embedded VTIMEZONE** definitions keep their identity. Replacing one with a system zone is an explicit migration.
- **Export.** Exporting native policies that RRULE can't express gives a loss report or a bounded materialized expansion.
- Source: [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html).

### Execution and updates

- **What a scheduler adds:** durable occurrence IDs, cancellation, retries, duplicate handling, catch-up and lateness policies. Exactly-once effects need transactional or idempotent execution.
- **Arming a wall appointment.**
  - It is armed as a bounded monotonic wait.
  - It re-checks against an atomic snapshot of the wall correlation plus a change subscription with a sequence number, so a step, slew or leap-segment change can't slip between check and arm.
  - A lost or overflowed subscription forces a recheck.
- **Rule updates** create a migration preview of affected future occurrences. A chosen cutover freezes past materializations and re-resolves future intent. Pending and already-executing work gets an explicit disposition.
- **Restored schedules** recover intent and re-arm under the current clock domain. They never reuse an old boot's raw deadline.

---

## 7. Clocks, scopes and waits

> **BLUF:**
> - **Providers, not scales.** A clock is a provider. Its readings carry a domain token (provider instance, reset generation, tick and suspend contract) and a status.
> - **No mixing.** Monotonic points from different providers, generations or boots never mix.
> - **Capture once.** The context is captured at entry and inherited by closures and tasks.
> - **Relative waits** default to suspend-inclusive monotonic time; `clocks.active` is the explicit alternative.

### Providers and readings

- **Resolution is not accuracy.** A counter difference is exact in its counter coordinate, not a certified SI duration. Drift and calibration belong to `observe` (§2).
- **Monotonic means non-decreasing, not strictly increasing.** Zero and repeated counts are valid.
- **Distinct failures:**
  - An unidentified POSIX/UTC/smear convention gives `UnknownClockConvention`, once, at acquisition.
  - Unavailable, unsynchronized and untrusted sources are distinct.
  - NTP, PTP and GNSS provide evidence, not truth.
- **The domain token is no-ABA.**
  - It is a process-local `uint32`, never reused while a reading may survive; exhausting it is an explicit resource failure.
  - Two test clocks that both start at zero get different tokens.
- **Snapshot, restore, clone and migration.** A VM or process restore, or a cloned image, can resurrect a provider handle. The provider keeps the domain only if it attests continuity of rate, elapsed and suspend semantics; otherwise it mints a new generation.
  - A counter that never decreases doesn't prove continuity.
  - Undetectable hostile rollback needs an explicit trust assumption.
- **Session bound.** The monotonic field is a bounded session representation (292 years of uptime), not a ten-thousand-year promise. Raw-tick or long-lived providers use a specialized `MonoPoint`.
- **Strict correlation.** `time.science.observe` takes monotonic-before, wall, monotonic-after, plus a correlation revision, or a provider's paired sample. A changed revision gives an unresolved correlation, never a false small error.

### Capturing providers

- **`TemporalContext`** is immutable configuration: provider handles, calendar and zone selection, pinned rules, policies and budgets. Immutability freezes identity, not the passage of time.
- **Short calls resolve against the nearest captured scope.** `now`, `sleep`, `within` and `today` never use a process-global provider chosen afresh on each call.
- **Host settings are captured once at entry,** using platform-safe discovery that doesn't race other threads or FFI mutating the environment. Changing the host zone afterward needs a new context or an explicit update subscription.
- **Inheritance.** Closures capture their scope's context. Tasks inherit their creator's and keep it across suspension and thread migration. An explicit context overrides the captured one.

```dewy
measure = (job) => time.elapsed(@job)
fetch_with_limit = () => within(2s @fetch)
let simulated = time.with_context(test.context @measure(@work))
```

- **`@job` is the handle;** `@job()` would warn as a redundant partial. `@measure(@work)` is a real partial with an argument.
- **`time.elapsed`** brackets the job with one monotonic domain and reads one clock per endpoint.
- **`with_context` and `with_clocks`.** `with_context` installs a whole context; `with_clocks` replaces only the clock handles.

### Test clocks

- **Advancing** a virtual provider affects tasks that already captured it. Resetting it mints a new generation, so old points no longer subtract.
- **Deterministic wakeups.** Tests choose the wake order for shared deadlines.
- **Game time** that runs backward is a nonmonotonic domain and can't satisfy a monotonic deadline.

### Suspension and timers

- **Suspend-inclusive by default.** `sleep`, `within`, relative TTLs and `reading + Duration` use **suspend-inclusive monotonic time**.
  - A deadline can expire while the device is asleep. Its callback runs on resume; waking the device is a separate capability.
  - Where the platform can't provide suspend-inclusive time, that's an entry failure, never a silent substitution.
- **`clocks.active`** excludes suspension. It is not CPU time; process and thread CPU clocks are separate. Selecting it for a scope changes relative waits there and shows in deadline metadata.
- **Timers** round up to the available resolution, recheck before succeeding, and may wake late. A zero duration is immediately eligible; a negative duration is rejected.
- **`within` requests cancellation at expiry.** It can't force an uncooperative operation to stop. Races between completion and cancellation follow the scheduler's arbitration.
- **Wall steps never move a monotonic deadline.** Persisted TTLs need a reboot and recovery policy.

---

## 8. Worked example: a sunset and publication calendar

> **BLUF:** A community calendar whose months start on an authority's crescent publication, and whose days start at local sunset, is built from ordinary pieces. It needs no Gregorian fields and no universal midnight.

```dewy
let community = app.calendar("community/crescent-calendar") or_throw
let sunset = time.civil.day_boundary(kind='sunset' location=community.site
    model=time.science.solar horizon=community.horizon)
let gathering = time.civil.recurrence(calendar=community boundary=sunset
    selector=community.month_day(1) offset=30minute publication='require_authority')
let [known pending] = gathering.plan(window work=10000)
```

- **Two independent providers.** The authority's editions give the label↔ordinal mapping. Site, horizon and solar model give the day boundary. Neither supplies the other's information.
- **What `plan` returns.**
  - `known` holds resolved occurrences with their authority edition and boundary uncertainty.
  - `pending` holds resumable obligations such as `AwaitingPublication` or `NoBoundary`; polar latitudes have no sunset to fabricate.
  - The only `or_throw` is on loading the app's calendar.
- **Before publication,** a predictive profile can return candidate days, or `require_authority` leaves a cancellable publication wait.
  - A new signed publication creates a new pinned context and resumes the plan. The signature authenticates the source, not the sighting.
  - Corrections create revised mappings and migration decisions, never erasing past publications.
- **Other calendars.** The same protocol supports a colony calendar over a sol ordinal.

---

## 9. Institutions, persistence and distributed systems

> **BLUF:** Business calendars, legal deadlines, bitemporal records and distributed clocks use the same primitives. A timestamp never implies identity, causality, mutual exclusion or exactly-once delivery.

- **Institutional calendars** combine working-week history, holidays, bank days, exchange sessions, closures, fiscal years (4-4-5) and service days.
  - `25:30` is a service-day offset, not a time of day.
  - Business-day and working-time arithmetic use session interval sets with explicit roll and inclusion policies.
  - Payroll separates elapsed work from contractually credited time.
  - Day-count conventions and legal ages are named.
- **Deadlines** name jurisdiction, zone, calendar, inclusivity, holiday behavior and boundary meaning. "By midnight" and "end of day" are candidate intents until those are known. Display preferences never change legal time.
- **Bitemporal records** pair a valid-time interval with a knowledge interval.
  - A database commit sequence can be a truer transaction order than wall time.
  - Corrections append assertions with supersession links.
  - `as_of` takes both axes.
  - Late data never rewrites event time.
- **Distributed systems.**
  - Event IDs are independent of coordinates.
  - Lamport clocks give an administrative total order, not physical precedence; vector clocks express concurrency.
  - A hybrid-logical-clock counter is not extra precision.
  - Cross-machine physical order uses correlated estimate bounds; overlaps stay indeterminate.
- **Leases and expiry** need drift, network, failure and fencing assumptions that no timestamp library supplies. Expiry policy says whether to reject, permit or defer when trusted time overlaps the boundary.

---

## 10. Science, observers and space

> **BLUF:**
> - `Instant` is a convenient terrestrial axis, not a mandatory hub.
> - Proper time, signal paths, spacecraft clocks, Mars, lunar and interstellar time are model-driven with explicit coverage, in `time.science`.
> - An unavailable standard returns `StandardNotDefined`.

### General model

- **An event** has a time coordinate, a position or worldline point, a reference frame and model context.
- **Consistent transforms.** Coordinate transforms rescale ephemeris positions, velocities and gravitational parameters consistently. Relabeling TCB as TDB while keeping incompatible parameters is rejected.
- **Proper time** integrates a metric along a timelike worldline from an initial synchronization.
  - Different trajectories accumulate different proper durations, so a proper-time difference keeps its observer brand.
  - Weak-field approximations state their omitted orders.
- **Earth rotation.** UT1 uses IERS data and predictions. Ancient or future `ΔT = TT − UT1` needs a named reconstruction model with coverage and error.
- **Angles and phases.** Sidereal time, solar time, sunrise and sunset are angle or phase constructions; they can have no solution, and none of them redefines `hour`.
- **Causal queries** distinguish timelike or null precedence, spacelike separation and uncertainty. A remote "now" needs a simultaneity convention; signal reachability is a separate question.

### Signals and flight operations

- **Signal paths** separate emission, reception, turnaround and execution, with moving endpoints solved iteratively.
  - Profiles name light time, Shapiro delay, media and hardware corrections, convergence and residual.
  - Ordinary SPICE light-time modes are not a complete relativistic model.
- **Ranging.** Round-trip ranging solves separate legs plus turnaround; half the round trip isn't the one-way delay.
- **Command planning** works backward from an execution window through decode/queue delays, clock uncertainty, contacts and transmission time. It returns windows or `NoFeasibleWindow`; sending is separate.
- **SCLK** keeps the clock's identity, partition, native count and raw telemetry; its ticks need not be SI seconds. Correlation kernels give piecewise maps with coverage, and kernel pools are isolated behind pinned contexts.

```dewy
let onboard = mission.sclk"1/1465644281.0"
let execute_at = onboard.correlate(kernel=mission.clock_kernel) or_throw
let flight = mission.signal.solve(execute=execute_at sender=mission.station
    receiver=mission.rover tolerance=10ms) or_throw
let proper = time.science.proper_elapsed(mission.rover_worldline first_event last_event
    metric=mission.relativity) or_throw
```

- **`mission.sclk"…"`** is the mission's own delimited call, checked at compile time against its declared format. The count denotes an *execution* target.
- **Real failures.** Kernel coverage, solver convergence and metric coverage are genuine, so they keep `or_throw`. `10ms` requests an error budget; it never manufactures one.

### Bodies, settlements and distant models

- **Mars** distinguishes Mars Sol Date, Coordinated Mars Time (MTC, the prime-meridian mean solar time), local mean and true solar time, solar longitude, Mars-year conventions and mission sols.
  - Mars24 takes TT input. [Mars24](https://www.giss.nasa.gov/tools/mars24/help/algorithm.html)
  - MTC needs no site; LMST and LTST do.
  - A clock face is not a simultaneity convention, and a Mars hour is not `3600s`.
  - Darian and other calendars are versioned plugins.
- **Planetary local clocks** name body, frame, orientation model, meridian, longitude sign and flavor. They handle retrograde rotation, tidal locking and polar absence.
- **Moon.** TCL belongs to the IAU lunar reference system. Operational LTC has no finalized constant (CGPM Resolution 6, 2026), so requesting it gives `StandardNotDefined` unless an experimental profile is chosen. No fixed "microseconds per day" substitutes for the model. [Resolution 6](https://www.bipm.org/en/cgpm-2026/resolution-6)
- **Interstellar** support extends charts, metrics, worldlines and signal solvers, never a solar-system ephemeris. Cosmic time and redshift depend on the cosmology.
- **Disconnected settlements** use offline packs and causal logs.

---

## 11. Formats, rule data and editions

> **BLUF:**
> - **Parsing never guesses;** display is localized and reports its losses.
> - **Codecs decode every bit exactly** on their own tick, in their declared domain. Conversion to `Instant` is a separate, checked step.
> - **Rule data is selected in `.dewy` source** with `$time.rules`. The host contributes only its zone *name*, unless `zone_source='host'`.
> - **Editions are per module.** E warns nothing, E+1 warns, E+2 changes, and only for modules that opt into E+2.
> - **Cost follows use.** A program links and maps only the modules it reaches.

### Parsing and display

- **Each parse names its terms:** a grammar or profile, the result type, an optional locale, whether all input must be consumed, and size budgets.
  - Offsetless text gives local fields.
  - Ambiguous numeric dates, two-digit years and abbreviations give candidates unless the profile supplies a convention.
  - "Yesterday" is computed in the viewer's civil context, not by subtracting `24hour`.
- **Localization** covers component order, digits, grammatical month forms, 12/24-hour clocks, eras and time-dependent zone names; week rules and weekends come from dated cultural context. [Unicode TR35](https://www.unicode.org/reports/tr35/tr35-dates.html)
- **Display returns text plus declared losses** (zone identity, calendar, precision, uncertainty, intent). Display resources acquired with the context don't make each call fallible. `$time.require_loss` makes accepting the losses explicit.
- **RFC 9557.** `Z` means a known UTC time with unknown local offset, like `-00:00`; `+00:00` states a preference. Annotation criticality and offset conflicts follow the profile. [RFC 9557 §2](https://datatracker.ietf.org/doc/html/rfc9557#section-2)

### Native interchange

- **Contents:** schema tag, scale/domain/epoch identity, tick and width, the count as an integer, portable zone and pack identities, and optional evidence or intent.
- **JSON** uses integer strings or records, never inexact numbers.
- **Never on the wire:** a process-local handle, or a `ClockReading`.
- **Three kinds of round trip.** Numerical, semantic and byte-for-byte round trips are distinct promises. The last needs the raw payload, including negative zero, NaN payloads and two-part decompositions.

### Exact codecs

Decode keeps the codec's native tick and origin. Mapping to J0 can leave the grid even when the native value is on a nanosecond grid, as with a pre-1972 UTC rate or a smear inverse. Encode checks range, divisibility and fidelity; a remainder needs explicit rounding and a loss report.

| Format | Native tick | On the 1ns grid? | Notes |
|---|---|---|---|
| POSIX `timespec` | 1ns | Yes | Leap/smear behavior governs inversion; 32-bit `time_t` overflow is `OutOfRange` |
| Windows FILETIME | 100ns from 1601 | Yes | Keep API sentinels; not elapsed TAI since 1601 |
| PTP / IEEE 1588 | 48-bit s + 32-bit ns, 1970 TAI | Yes | Keep the timescale flags; ARB isn't TAI. The `correctionField` (signed 2⁻¹⁶ ns) stays beside the value, including its too-large state |
| RFC 3339, ≤ 9 fraction digits | Decimal | Yes | ≥ 10 digits keeps `Instant<tick=1s/10^k>` |
| CCSDS CDS | ms / µs / ps of day | ms, µs: yes; ps: no | Days are never blindly × 86400s; UTC rules validate day length |
| NTP 64-bit | 2⁻³² s (≈0.2328 ns) | No | 32-bit seconds + fraction; era from evidence; zero and the leap indicator are explicit variants |
| NTP 128-bit date | 2⁻⁶⁴ s | No | Signed 64-bit era-seconds + 64-bit fraction |
| CCSDS CUC | 2^(−8f) s | No | P-field lengths; agency epochs need definitions |
| GPS week + TOW | TOW unit | TOW: usually | 10-bit (legacy) or 13-bit (CNAV) weeks don't identify the era; refuse without era evidence |
| SPICE ET, two-part JD (binary64) | Magnitude-dependent | No | Decode exactly as dyadic rationals; keep the raw parts; ET is TDB, so a model is needed for TT |

Sources: [RFC 5905 §6](https://www.rfc-editor.org/rfc/rfc5905.html#section-6), [RFC 8877](https://www.rfc-editor.org/rfc/rfc8877.html), [CCSDS 301](https://ccsds.org/Pubs/301x0b4e1.pdf), [GPS rollover](https://www.gps.gov/news/gps-week-number-rollover), [SPICE time](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/time.html).

### Rule data and the host

- **Packs are immutable and content-addressed.** Each identifies its authority, license, source edition, schema, dependencies, publication and effective dates, coverage and supersession. Signatures authenticate bytes, not truth.
- **Selected in source:** `$time.rules = rules.iana_2026c`, where `rules` is an imported `.dewy` module whose constant is a descriptor (authority IDs, content digests, coverage, continuation profile).
  - Transition tables can themselves be generated `.dewy` source, lazily loaded like any library.
  - There is no project-file key and no lockfile. External signed packs may remain transport data, but their selection and verification live in source.
  - A compile-time literal whose pack bytes are missing fails the build. Runtime loading is an explicit, fallible call.
- **The host contributes its zone name.**
  - The context captures `America/New_York` once; the rules come from the pinned pack, so builds are reproducible and a distribution's tzdata update can't change a test.
  - Fallbacks: a POSIX `TZ` string becomes a rule-defined zone; a fixed offset becomes an `Offset`; a copied `/etc/localtime` without a name is captured as host rules with a status.
- **`$time.zone_source = 'host'`** opts into the OS rules for programs that must follow urgent government changes without a rebuild.
- **`ZonePackStale` is a status, never a failure of `today`.** When host and pinned rules disagree for the captured zone, the status carries both identities.
  - It says "stale" only when publication data orders them. Otherwise freshness is unknown, since an OS database can be older than the pinned pack.
- **Updates are explicit.** Fetching and installing packs are operations, never side effects of conversion or compilation. They produce migration previews for future appointments, and past instants never move.

### Editions

- **Three separate identities:**
  - the **source edition** (what bare names and convention defaults mean in this module);
  - the **definition identity** (what `Gregorian` means; frozen once published);
  - the **data selection** (`$time.rules`).
- **Per module.** `$edition = 2026` at the top of a module. §14 asks David to choose between this and `$build.edition`.
  - It applies to that compilation unit only and is never inherited from an importer.
  - Generics and plugins use their definition site's edition.
  - A literal integer needs no bootstrap import.
- **Omitted edition.** It means a permanently specified baseline (2026), never "whatever this compiler prefers", and it warns. Scaffolding writes the current edition.
- **Evolution contract.**
  - Edition E defines a default.
  - E+1 warns on every bare use whose meaning will change and offers the explicit spelling.
  - E+2 may change the default, only for modules declaring E+2.
  - At least one published edition intervenes; the deprecation period is never inferred from years. Old editions keep their meaning; a compiler may eventually refuse one with a migration diagnostic, never reinterpret it.
- **What editions govern:** bare `Date`, `date"…"` and `today`'s calendar, and convention defaults such as `age`'s leap-day rule and display profiles.
- **Never versioned:** J0, the meaning of a tick such as `1ns`, the TT-rate axis, integer-count meaning, and the plain `Instant` alias's wire identity. A new representation gets a new type and schema.
- **UTC regimes and zone rules** are pack segments, independent of edition. Old source can adopt new rules, and new source can reproduce old ones.

### Module cut and cost

| Module | Contents | Data it may map |
|---|---|---|
| `time` | `Instant`, `Duration`, `ClockReading`, `MonoPoint`, `Interval`, `now`, `monotonic`, `sleep`, `within`, `elapsed`, contexts, the UTC segment table, POSIX/NTP/PTP/RFC 3339 codecs | ~40-row UTC table |
| `time.civil` | Dates, zones, periods, `today`, recurrence, appointments, localization | Zones reached; locale data on display |
| `time.science` | Scales, `Coordinate`, `Estimate`, `observe`, ephemerides, signals, SCLK, Mars, CCSDS/SPICE/JD codecs | Named kernels only |

- **Linked by reachability.** The prelude re-exports `now`, `monotonic`, `sleep`, `within`, `today`, `interval` and the literal calls (`instant`, `date`, `zoned`, `zone`, `utc`) as `$shadowable const`s; reaching one links its module. Everything else is qualified (`time.civil.recurrence`). A stopwatch links only `time`.
- **Indexed lookups.** Zone and correlation lookup is `O(log n + k)`. Recurrence charges candidates examined. Big-number, iteration and ephemeris costs are declared separately.
- **No code in data,** and no precompiled library images.

---

## 12. Every convenience assumption has an opt-out

> **BLUF:**
> - **17 named obligations.** Each convenience the defaults rely on is a `$time.require_*` member.
> - **On and off.** Turning one on demands an explicit choice or evidence. Turning it off (`=false`) restores only its documented convenience.
> - **Bundles.** `$time.strict` enables all 17; `$bulletproof` includes `$time.strict`.
> - **Free when unused.** Obligations are compile-time. The default path stores no assumption trace and no evidence.

### Principles

- **Defaults** select contexts and profiles. They never repair ambiguity, assume independence, invent coverage or choose numerical routes.
- **The assumption trace is a compile-time artifact** (diagnostics and hover), not runtime data. A strict context stores at most one integer identity.
- **Compile-time tags can't prove dynamic data.** Strictness can demand runtime evidence and return an unresolved value; necessary validity checks are never suppressed.
- **Mechanics (approved style).** A bare member enables, `=false` disables. More local settings override inherited ones, and obligations propagate through types, effects and facts, with no whole-program pass.

### The 17 obligations

| # | `$time.` member | Convenience removed → what it then requires |
|---|---|---|
| 1 | `require_context` | Entry snapshot of clock, zone, locale, calendar, location and rules → explicit argument or lexical capture of known identity |
| 2 | `require_calendar` | Edition-default calendar, numbering and day/week conventions → explicit calendar and boundary choice |
| 3 | `require_bounds` | Half-open interval defaults → explicit bounds; no default epsilon |
| 4 | `require_profile` | Inherited parse, recurrence, overflow, rounding, gap/fold scope policy and convention defaults (`age`'s `march_1`) → a named profile or a written policy |
| 5 | `require_clock_domain` | Suspend-inclusive default, monotonic continuity, VM continuity and generation lifetime → capability checks; reading subtraction returns `Duration \| ClockDiscontinuity \| DomainMismatch` |
| 6 | `require_clock_accuracy` | Treating a nominal reading as adequate → acquisition and calibration evidence meeting a bound; `today` returns its union |
| 7 | `require_clock_trust` | Accepting a source for security decisions → an explicit trust policy |
| 8 | `require_realization` | Projecting TAI, UTC(k) or TT(BIPM) onto ideal coordinates → a correlation estimate or a declared nominal interpretation |
| 9 | `require_history` | Published zone, calendar or legal history as actual practice → authority and observance evidence |
| 10 | `require_future_rules` | Current laws, holidays and UTC regimes continuing → coverage plus a stated scenario; answers are conditional |
| 11 | `require_location` | Default geocentre, meridian, horizon or illuminating body → explicit location and frame with an error budget |
| 12 | `require_model` | A convenient approximation, route or tolerance → a model and error contract |
| 13 | `require_extrapolation` | Extending ephemerides, correlations, Earth orientation or predictions beyond coverage → a warranted extension model |
| 14 | `require_dependence` | Assumed independence or covariance → a joint model with evidence |
| 15 | `require_loss` | Nominal display, hulls, quantization, float export, dropped evidence or intent → declared acceptance plus a loss report |
| 16 | `require_protocol` | Leases, clock-based expiry, delivery guarantees, restored deadlines → drift, network, failure and recovery assumptions |
| 17 | `require_resources` | Default loading, storage growth, search, numeric work and provider availability → exposed bounds and fallibility |

- **Closed inventory.** Any new convenience names its row or adds a new one to the bundle. Inherent ambiguity, domain and validity failures are enforced regardless of tags.
- **Monotonic continuity** joins the assumptions table in `assumptions.md` under row 5, beside the allocation axiom it resembles.

```dewy
$time.require_context
wait_for = (delay:Duration<(>=? 0s)> context) =>
    time.with_context(context @sleep(delay))

$time.strict
report = (reading context) => {
    $time.require_loss=false
    printl(reading.nominal.display(profile='nominal' context=context).text)
}
```

- **What the refinement proves.** `delay`'s refinement discharges one local obligation. It doesn't prove the clock is available or that wakeups are timely.
- **What the inner tag accepts.** It accepts display loss only, not clock accuracy or trust.

---

## 13. Capability acceptance and delivery

> **BLUF:** Every layer preserves domain, evidence, uncertainty and intent before every model exists, and only implemented operations are advertised. Fixtures pin definitions and editions; oracle disagreements are diagnosed as convention, coverage or implementation.

- **Core:**
  - the J0 reference integers;
  - ±10,000-year and ±10²¹-year values;
  - the 129-bit `max − min` intermediate;
  - `OffGrid` vs `OutOfRange` vs an unproved narrowing;
  - `1ns/3`, `0.1s`, floor `ticks`;
  - quantize loss signs;
  - max-count successor and interval normalization;
  - cross-tick comparison;
  - `width=64` overflow.
- **Clocks:**
  - same-session subtraction;
  - mixed tokens;
  - two test clocks at zero;
  - a counter reset during a timed callback;
  - snapshot/restore and clone reminting;
  - a copied reading before and after resync (no retroactive estimate);
  - a pinned leap or continuous-UTC transition crossed while running;
  - wall steps in both directions;
  - suspend vs active;
  - entry failure;
  - a stale monotonic sample never giving zero elapsed time or an early sleep.
- **Literals:**
  - compile the same literal against packs A and B that disagree;
  - run A's build with B present;
  - remove A's payload;
  - cross A's expiry;
  - re-resolve the appointment under B;
  - historical corrections never mutate old facts;
  - repeat with a future UTC regime and an unpublished calendar date.
- **Civil:**
  - 2016 leap labels;
  - synthetic negative-leap UTC adjacency, POSIX/NTP inversion and smear;
  - pre-1972 nanosecond labels mapping off-grid;
  - tzdb vs zic/zdump;
  - more than two inverses;
  - `1day` vs `24hour`;
  - British 1752, Swedish 1712;
  - leap months;
  - repeated clamp vs anchored month-end;
  - differently anchored period comparison;
  - RFC explicit vs generated gaps, UNTIL types, `THISANDFUTURE`;
  - host vs pinned zone disagreement.
- **Codecs:**
  - every codec round-trips its payloads at each promised fidelity;
  - NTP zero and leap-indicator-unsynchronized states;
  - PTP correction overflow;
  - GPS `week=0` in eras 1 and 2.
- **Science:**
  - exact TT↔TCG and TCB↔TDB inverses;
  - TCG↔TCB refusal without ephemerides;
  - distinct worldlines;
  - asymmetric signal legs;
  - SCLK re-correlation;
  - Mars24 reference cases;
  - unavailable LTC.
- **Cost:**
  - a stopwatch links only `time`;
  - instruction counts on the flagship panel;
  - no bulk data in unused programs;
  - fuzzed parsers and packs under resource limits;
  - the usual focused/quick and full/bootstrap/fixed-point gates, with at most 4 workers.

---

## Examples

> **BLUF:** Fifteen motivating programs, from a stopwatch to Mars. The correctness review's corrected set replaces the critique's. Literals and proved operations are unwrapped; `or_throw` marks real partial boundaries. `civil`, `science` and `mars` abbreviate `time.civil`, `time.science` and `time.science.mars`. `rules` is an imported descriptor module, as in Example 10. `mission`, `payroll` and similar are application modules, not proposed stdlib names.

**1. Time a build, pace a frame, bound a fetch.** *Shows:* monotonic elapsed time, float `dt`, no civil code linked.

```dewy
let start = now
compile
printl"compiled in {now - start}"

let budget = 16_666_667ns                 # 1s/60 rounded up to the grid
let last = monotonic
loop true {
    let frame = monotonic
    let dt = (frame - last) / 1s as float64
    last = frame
    update(dt)
    draw
    let spent = monotonic - frame
    if spent <? budget { sleep(budget - spent) }
}
```
- **`1s/60` is off the 1ns grid,** so the budget is rounded explicitly. `sleep` may wake late.
- **Fetching** with a fallback is `within(2s @fetch) ??<Timeout> cached`; other failures stay visible.

**2. A weekly meeting vs a fixed delay.** *Shows:* `Period` vs `Duration`.

```dewy
let meet = zoned"2026-10-26T09:00[America/New_York]"
let weekly = meet + 1week          # 2026-11-02T09:00-05:00
let fixed = meet + 168hour         # 2026-11-02T08:00-05:00
printl"{weekly.nominal - meet.nominal}"   # 169h
```

**3. Daily alarms that actually hit a gap and a fold.** *Shows:* policies only where a transition needs them.

```dewy
let early = civil.recurrence(zoned"2026-03-01T01:30[America/New_York]"
    every=1day fold='earlier')
let late = civil.recurrence(zoned"2026-03-01T02:30[America/New_York]"
    every=1day gap='preserve_displacement')
let season = interval(instant"2026-03-01T00:00:00Z" instant"2026-12-01T00:00:00Z")
let [alarms cursor] = late.expand(season limit=400 work=100000)
```
- **`early`** meets the 1 November fold (01:00–02:00). 01:30 is never in a gap.
- **`late`** meets the 8 March gap, where 02:30 becomes 03:30. It never meets a fold.
- **RFC import contrast.** Imported as RFC 5545, an explicit 02:30 means 03:30, but a generated one is omitted.

**4. Invoice anchors and birthdays.** *Shows:* clamp vs anchor, convention defaults.

```dewy
let jan = date"2027-01-31"
let feb = jan.add(1month overflow='clamp')      # 2027-02-28
let mar = feb.add(1month overflow='clamp')      # 2027-03-28: clamping drifted
let invoices = civil.recurrence(jan every=1month anchor='month_end')   # Jan 31, Feb 28, Mar 31
let age = date"2000-02-29".age(on=date"2027-02-28")                    # 26
```

**5. A durable log and human display.** *Shows:* instants format without zone data; display reports loss.

```dewy
let stamp = now.nominal
log.write"{stamp} request {id}" or_throw
let shown = meet.display(locale='fr')
printl(shown.text)
```
- **Formatting `stamp`** needs only the UTC table. A later pack update never rewrites the line.
- **`shown.losses`** lists what the French rendering dropped, such as the zone ID.

**6. An archived leap, old UTC and a synthetic negative leap.** *Shows:* leap labels are validated, arithmetic is continuous.

```dewy
let before = utc"2016-12-31T23:59:59"
let leap = utc"2016-12-31T23:59:60"
let after = utc"2017-01-01T00:00:00"
printl"{after.nominal - before.nominal}"        # 2s
let apollo = utc"1969-07-20T20:17:40".nominal   # -235107732425406200ns from J0
# utc"2015-12-31T23:59:60"                      # compile error: no leap there
```
- **POSIX export of `leap`** needs a named phase policy.
- **A synthetic pack** with a skipped label tests adjacency, the short day, and the POSIX/NTP inverses on both sides of 20 May 2027.

**7. Sub-nanosecond science, exact codecs, GPS eras.** *Shows:* off-grid values have honest homes.

```dewy
let q = (instant"2026-10-24T12:00:00Z" as science.Coordinate<science.TT>) + 1ns/3
let [nearest loss] = q.quantize(tick=1ns rounding='nearest_even')
let tcg = q as science.Coordinate<science.TCG>        # exact: divides by 1−L_G
let stamp = ntp.decode(packet_bytes)                  # native 2^-32 s tick
let gps_2019 = gps(week=0 tow=0s width=10).resolve(era=2)   # 2019-04-07T00:00 GPS
```
- **NTP zero and the leap indicator** survive decoding as variants.
- **Shared error.** `X=10s+E`, `Y=13s+E` gives `Y−X = 3s`; with marginals only, `[1s,5s]`.

**8. A historical calendar and an incomplete date.** *Shows:* successors by capability; partial labels.

```dewy
$calendar = civil.British
let following = date"1752-09-02" + 1day          # 1752-09-14
let source = civil.YearMonth<civil.Swedish>(year=1712 month=2)
```
- **No invented fields.** `source` invents neither a day nor a midnight.
- **The Swedish calendar** accepts `1712-02-30` in its own sequence.

**9. A crescent-publication gathering after sunset.** *Shows:* observational calendars and publication waits (§8).

**10. An urgent rule update.** *Shows:* frozen literals vs live appointments; migration.

```dewy
$edition = 2026
import p"time_rules.dewy" as rules
$time.rules = rules.iana_2026c

let standup = civil.appointment(local="2027-04-05T09:00" zone=zone"America/Sao_Paulo" every=1week)
let newer = civil.load_rules(rules_path) or_throw
let preview = standup.preview_migration(to=newer window=next_year)
```
- **The preview** lists changed future occurrences before anything is committed.
- **Resolved literals elsewhere** stay the values they were.

**11. Payroll across the fall-back hour.** *Shows:* the fold choice changes elapsed work.

```dewy
let shift = zoned("2026-11-01T01:30[America/New_York]" fold='earlier')
let done = zoned"2026-11-01T03:30[America/New_York]"
let worked = done - shift                         # 3h; with fold='later', 2h
let credited = payroll.credit(shift done) or_throw
```
- **Credit is a contract rule,** not elapsed time.
- **Records.** Corrections append valid-time and knowledge-time assertions. Expiry checks use an explicit reject/permit/defer policy.

**12. Ancient sky direction, with ΔT applied.** *Shows:* no ancient UTC, real coverage, real uncertainty.

```dewy
let de441 = science.ephemeris(rules.de441) or_throw
let tt = science.tt("-0584-05-28T12:00:00" calendar=civil.Julian)
let delta_t = science.delta_t(tt model=science.morrison_stephenson_2004)
let ut1 = science.ut1(tt delta_t=delta_t)      # UT1 = TT − ΔT, carrying ΔT's uncertainty
let sky = science.apparent_direction('moon' at=tt observer=babylon
    ephemeris=de441 rotation=ut1)
```
- **The date.** It is a Julian-calendar TT label at an illustrative noon (the conventional date of Thales' eclipse, 585 BCE), not a recorded eclipse time.
- **Coverage.** DE441 covers −13200 to 17191; DE440 (1550–2650) would not. Both coverages are known from the descriptor, so the only `or_throw` is loading the kernel.
- **ΔT is applied.** UT1 = TT − ΔT drives Earth rotation, and ΔT's large uncertainty at this epoch propagates into `sky`.

**13. A modern eclipse search.** *Shows:* a defined computation, not "an ephemeris plus a date range".

```dewy
let de440 = science.ephemeris(rules.de440) or_throw
let years = interval(instant"2026-01-01T00:00:00Z" instant"2028-01-01T00:00:00Z")
let [found cursor] = science.solar_eclipses(years ephemeris=de440 earth=science.iers_eop
    geometry=science.iau_eclipse_geometry tolerance=1s work=100000)
```
- **The computation.**
  - Find Sun–Moon conjunctions in TDB.
  - Test the lunar shadow axis against Earth's radius plus the penumbra, with IAU lunar radius and limb conventions.
  - Classify each eclipse as partial, annular, total or hybrid.
  - Ground paths need Earth orientation, and predictions carry their error.
- **Expected results:** 2026-02-17 annular, 2026-08-12 total, 2027-02-06 annular, 2027-08-02 total.
- **`tolerance=1s` is solver residual,** not certified physical error.

**14. A rover command and proper time.** *Shows:* SCLK roles, moving endpoints and worldlines (§10).

```dewy
let execute_at = mission.sclk"1/1465644281.0".correlate(kernel=mission.clock_kernel) or_throw
let send = mission.latest_send(execute=execute_at contacts=mission.contacts
    processing=mission.decode_and_queue transmission=mission.airtime) ??<NoFeasibleWindow> none
```
- **What `??<NoFeasibleWindow>` leaves alone.** It defaults only an infeasible plan; missing kernels and non-convergence stay visible.

**15. Earth, Mars and the Moon.** *Shows:* clock faces vs simultaneity; unavailable standards.

```dewy
let earth = instant"2027-03-01T09:00:00Z"
let mtc = mars.mtc(earth)                              # no site needed
let arrival = mission.signal.arrival(emit=earth receiver=mars.jezero) or_throw
let lmst = mars.lmst(arrival site=mars.jezero)         # site needed
let lunar = science.lunar_time(earth realization='ltc') ??<StandardNotDefined> none
```
- **Two different questions.** `mtc` is a Mars24 clock face evaluated at a TT coordinate. `arrival` answers when the signal gets there.

---

## Prior art

> **BLUF:** The critique's survey, corrected by the correctness review. Every mature library converged on an integer instant, a type split between instants and civil values, and periods distinct from durations. Their bugs come from hidden fallbacks, silent fold/gap repair, mutable global data and one value doing two jobs.

| System | Lesson | How Dewy handles it |
|---|---|---|
| **Go `time`** | `Sub` uses monotonic samples when both operands have them, and falls back to wall time when one was stripped (by `Round`, `AddDate`, zone views or serialization). `Add` keeps both. `==` compares monotonic and location; `Equal` compares coordinates. | The type says which clock: `ClockReading` subtracts monotonically, `.nominal` is wall, and readings have no codec, so nothing can fall back. |
| **java.time** | The type split, seconds + nanoseconds, an injectable `Clock`. Its time-scale is UTC-SLS after 1972, so `Instant` never represents `:60`. The `SMART` resolver adjusts invalid fields. | Same split, with a context. Continuous TT-rate axis; leap labels live in `UtcLabel`. No smart resolver. |
| **Joda-Time** | `Instant` stores only epoch milliseconds; chronology lives on `DateTime`. | Calendars stay off `Instant`, via a type parameter on dates. |
| **Noda Time** | Explicit local types. `InZoneStrictly` throws; `InZoneLeniently` repairs. `Period` ≠ `Duration`. | Whole-union resolution, with `choose` as a free function; named policies; `Period`. |
| **JS `Date` / Temporal** | `Date` is mutable milliseconds mixed with local fields. Temporal uses integer ns ignoring leaps, calendar and zone *identifiers*, and durations needing `relativeTo` for context. | Integer ns. `Period` is separate from `Duration`, and anchored comparisons are named. |
| **Python `datetime`** | Aware `+` and same-`tzinfo` `-` ignore transitions. `fold=0` silently picks a side. Naive and aware values share a type. | Civil adds resolve under a policy; no fold default; separate types; no float timestamps. |
| **Rust chrono / jiff** | chrono has partial leap support, with zones in separate crates. jiff clamps `:60`, prefers the system tzdb with bundled fallback, and shares zones via `Arc`. | No clamp. Pinned rules by default, host rules opt-in, and pack-scoped handles. |
| **Rust `time` / hifitime** | RUSTSEC-2020-0071: `localtime_r` racing environment mutation. hifitime: integer centuries + ns on a continuous scale. | Platform-safe host capture, once. Continuous scale with integer storage. |
| **C++ `<chrono>`** | Compile-time tick and clock in the type. Integral `duration_cast` truncates. | Ticks in the type. Inexact conversion is `OffGrid`, never truncation. |
| **Erlang** | Separate monotonic engine; observable wall-offset changes; multi-time-warp is the default. | Monotonic domain plus a subscription protocol for correlation changes (§6). |
| **SOFA / ERFA** | Two-part JDs; stale compiled leap tables. `iauTaitt` is a fixed `32.184s`, with no `L_G`. | Two-part JD codec. Packs with validity intervals. `now` adds one offset. |
| **Skyfield / Astropy** | Whole + fraction JD parts (collapsing them loses precision); two-double storage; Astropy's scale defaults to UTC and it auto-downloads IERS data. | int128 columns (`width=64` for bulk); explicit scale; explicit fetch. |
| **SPICE** | ET is TDB seconds past J2000 as a double. A global kernel pool. SCLK partitions. | ET is a `Coordinate<TDB>` codec; kernels sit behind pinned contexts; SCLK keeps raw counts. |
| **iCalendar** | Exclusive DTEND (intentional). UNTIL type follows DTSTART. `THISANDFUTURE` shifts by original IDs. `P1D` ≠ `PT24H`. | The RFC 5545 profile states each rule (§6). |
| **NTP / PTP** | Wire sentinels: NTP zero and an unsynchronized leap indicator; PTP correction overflow. | Explicit adapter variants with raw bits kept. |
| **RFC 9557** | `Z` means UTC with unknown local offset. | Profile metadata (§11). |

---

## 14. Open decisions

> **BLUF:**
> - **Settled by David:** the epoch (J0), integer ticks, `now` without parentheses, and the `@f()` lint.
> - **Fifteen decisions remain.** Names are reversible; persisted meanings and wait behavior are not.
> - **Already approved and not reopened:** the `$time.*` namespace style.

### Settled

| Item | Decision |
|---|---|
| Epoch | J0, `1977-01-01T00:00:32.184 TT`, `e=0` |
| Representation | `Instant` is an exact integer count of ticks, not a rational. The TT-rate axis and tick meaning are never versioned. |
| `now` | No parentheses; common values lightweight |
| Partials | `@f()` with no arguments warns; write `@f` |
| Source-only settings | No project-file keys or lockfiles |

### Remaining

| # | Decision | Recommendation | Reversibility |
|---|---|---|---|
| 1 | Default width | int128 for `Instant` and `Duration`; `width=64` explicit; width independent of tick | Spelling reversible; ABI costly after release |
| 2 | Easy clock operators | `reading − reading` is monotonic elapsed time; `reading + Duration` is a `MonoPoint`; `.nominal` is wall. Continuity is an environmental assumption under `require_clock_domain`. | Reversible before release; a behavior change after |
| 3 | `today` | Nominal `Date`, plus `today_support`; the union only under `require_clock_accuracy` | Reversible before release |
| 4 | Literal infallibility | Frozen, pack-identified snapshot; within coverage, unique, on-grid, in range; otherwise a compile error with a fix-it. Live appointments migrate explicitly. | API reversible; persisted semantics costly |
| 5 | Edition spelling | `$edition = 2026`: per-module source semantics, unlike root-only `$build`. Omitted means the 2026 baseline, with a warning. | Spelling reversible; edition contract durable |
| 6 | Calendar name | `Gregorian` (short; adoption lives in named historical calendars), not `ProlepticGregorian` | Reversible before publication |
| 7 | `day` / `week` | Calendar `Period`s; `week` = 7 successors; lexical `$time.gap` / `$time.fold` | Reversible before release; later it changes code meaning |
| 8 | `age` default | Completed anniversaries, `leap_day='march_1'`; opt out via `require_profile` | Edition-versioned |
| 9 | Zone source | Host zone *name* plus pinned rules; `$time.zone_source = 'host'` opt-in; `ZonePackStale` as a status | Reversible |
| 10 | Rule selection | `$time.rules = <descriptor constant>`; tables as generated `.dewy` | Spelling reversible; pinned identity contract semantic |
| 11 | Relative waits (v4) | Suspend-inclusive monotonic; `clocks.active` explicit | Reversible before use; behavior-changing later |
| 12 | Intervals (v4) | Half-open `interval(a b)` plus stored flags | Convenience reversible; stored bounds not |
| 13 | Intent (v4) | Separate `Appointment` / `Occurrence` / `Event` / `Observation` | Additive; discarded intent can't be rebuilt |
| 14 | Strictness names (v4) | 17 `$time.require_*`, `$time.strict`, in `$bulletproof`; row 5 covers continuity | Names reversible; the inventory is a contract |
| 15 | Name inventory | The table below | Names individually revisable |

### Notes on each

1. **Width.** int64 ns ends in 2269 and fails the 10,000-year priority. A width heuristic would make footprints jump. *Unblocks:* layout, ABI and codecs.
2. **Clock operators.** The stopwatch is the most common use, and wall subtraction lies across NTP steps. Go's lesson is to make the clock visible in the type. *Unblocks:* the trivial tier, games and timeouts.
3. **`today`.** Most programs want a date, not a union. Strict ones get the honest union. *Unblocks:* the trivial tier.
4. **Literals.** This contract removes most `or_throw`s without hiding real failures. It extends the existing `regex` literal rule with success-type refinement. *Unblocks:* §5 and the examples.
5. **Edition spelling.** `$build` facets are root-only and global; an edition is per module. `$build.edition` (the representation review's choice) would need a documented exception to that rule. *Unblocks:* calendar evolution, and later any language default.
6. **Calendar name.** *Unblocks:* public signatures and stored identities.
7. **`day` / `week`.** A Duration-typed `day` breaks substitution invariance. *Unblocks:* DST-safe civil arithmetic. The `$time.gap` / `$time.fold` spellings are new.
8. **`age` default.** Jurisdictions differ (some use 28 February), so `legal_age` always takes one. The default is flagged because it's a convention. *Unblocks:* short birthday code.
9. **Zone source.** It balances reproducibility against urgent law changes. *Unblocks:* host capture.
10. **Rule selection.** *Unblocks:* reproducible literals and updates independent of edition.
11–14. **v4 decisions.** These are unchanged in substance from v4.

### Spelling inventory

**New in v5.** All are proposals unless marked.

| Kind | Spellings |
|---|---|
| Type parameters | `width=` on `Instant` and `Duration`; `Duration<tick=…>` |
| Types | `UtcLabel`, `Coordinate<Scale>`, `ClockObservation`, `Resolution`, `Gregorian` (or `ProlepticGregorian`), `British`, `Swedish` |
| Results and statuses | `OffGrid`, `ClockDiscontinuity`, `ZonePackStale` |
| Literal calls (no new syntax) | `instant"…"`, `zone"…"`, `utc"…"`; compile-time success refinement for these and `date"…"`, `zoned"…"` |
| Functions and members | `instant(text)` (replaces `parse_instant`), `convert<T>`, `.nominal` (readings, zoned values, UTC labels), `today_support`, `observe`, `interval`, `display(…).text` / `.losses`, `load_rules`, `preview_migration`, `appointment`, `legal_age` |
| Metatags | `$edition` (or `$build.edition`), `$calendar`, `$time.rules`, `$time.zone_source`, `$time.gap`, `$time.fold` |
| Period units | `day`, `week` as `Period` (`month` and `year` already decided) |
| Policy labels | `anchor='month_end'`, `keep='resolution'`, `zone_source='host'` |
| Lint | Empty `@f()` (settled) |

**Carried from v4** (still awaiting approval; meanings updated where noted):
- **Core and clocks:** `TimePoint`, `Instant`, `Duration`, `TAICompatible`, `Estimate`, `Interval`, `IntervalSet`, `ClockReading` (now compact), `MonoPoint`, `TemporalContext`, `now`, `monotonic`, `today`, `elapsed`, `with_context`, `with_clocks`, `clocks.active`, `ticks`, `quantize`, `compare_estimates`, `certainly_before`, `possibly_before`, `same_set`.
- **Civil:** `Date`, `TimeOfDay`, `LocalDateTime`, `Offset`, `Zone`, `ZonedDateTime`, `Period`, `Calendar`, `DayBoundary`, `MonthDay`, `YearMonth`, `Appointment`, `Occurrence`, `Event`, `Observation`, `date`, `zoned`, `choose`, `add`, `age`, `recurrence`, `expand`, `next`, `plan`, `as_of`.
- **Science:** `Worldline`, `ProperClock`, `SignalPath`, `Sclk`, `correlate`, `proper_elapsed`, `causal_relation`.
- **Results:** `Gap`, `Ambiguous`, `AmbiguousToday` and `UnknownToday` (strict only), `Unknown`, `Unspecified`, `MissingContext`, `MissingData`, `OutsideCoverage`, `InvalidDate`, `InvalidFields`, `OutOfRange`, `DomainMismatch`, `InconsistentEvidence`, `Indeterminate`, `Incomparable`, `NoOccurrence`, `AwaitingPublication`, `SearchBudgetExceeded`, `NoFeasibleWindow`, `StandardNotDefined`, `UnknownClockConvention`, `UnsupportedClockSemantics`.
- **Policies:** `earlier`, `later`, `all`, `preserve_displacement`, `next`, `clamp`, `march_1`, `require_authority`, `emitted`, `nearest_even`.
- **Strictness:** the 17 `$time.require_*` members and `$time.strict`.

**Removed from v4:**
- `WallTime`, replaced by `ClockReading.nominal` and `ClockObservation`;
- `parse_instant`, replaced by `instant(text)`;
- the rational plain `Instant`;
- the Apollo epoch;
- the runtime assumption trace;
- `CoordinateTime`, replaced by `Coordinate<Scale>`.

**Rejected, so they are not "also available":**
- a `NegativeLeap` type;
- clamping `:60`;
- a project-file edition key;
- a tick-dependent width heuristic;
- `day` as `86400s`;
- `mars.now`, or `hour` meaning a Mars hour;
- a process-wide time-warp flag;
- any new keyword for literals, editions or clocks.
