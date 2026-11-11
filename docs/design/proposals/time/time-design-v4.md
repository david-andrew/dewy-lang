# Time, dates, clocks and calendars

> **BLUF:** Dewy has one time system, and it covers everything from `now()` to Mars.
> - **Simple calls stay trivial.** One context is captured at program entry. Subtracting two times gives a plain `Duration`, reads never need an error branch, and uncertainty prints as a status.
> - **Underneath is an exact core.** Coordinates are exact rationals on an ideal TT-rate axis, stored as integer ticks.
> - **Nothing is guessed.** Missing knowledge, civil ambiguity and uncertainty are values the program sees.
> - **Strictness is opt-in.** Every convenience assumption has a `$time.require_*` opt-out; `$time.strict` enables them all and is part of `$bulletproof`.
> - **No new syntax or keywords.** Names are proposals unless already approved. §14 lists the decisions needed.

This is v3 restructured for reading, with no semantic changes.

**Reading guide:**
- **Core:** the trivial tier, §1 (coordinates), §5 (civil), §7 (clocks), §12 (opt-outs) and §14 (decisions).
- **Supporting:** §2–§4 (uncertainty, intervals, UTC) and §6 (recurrence).
- **Applications:** §8–§11 and §13; skim these.

## Vocabulary

| Term | Meaning |
|---|---|
| **Scale** | Defines a coordinate and its rate convention (TT, TAI, UTC, TCB, …) |
| **Realization** | Physical clocks and observations that estimate a scale (TAI, UTC(k), TT(BIPM)) |
| **Epoch** | The chosen zero |
| **Representation** | How the coordinate is encoded (scalar, calendar fields, Julian date) |
| **Format** | How it is presented as text |
| **Nominal** | The exact coordinate a label or reading names. It does not claim that an event was measured there. |
| `Instant` | An exact point on the ideal TT-rate axis |
| `WallTime` | An envelope: nominal `Instant`, source, `Estimate<Instant>`, status and display context |
| `ClockReading` | A `WallTime` plus acquisition evidence |
| `Estimate<T>` | The set of admissible values under identified assumptions |

Scale, realization, epoch, representation and format are independent. For example, a TAI label can be a scalar, TT can be written as calendar fields, and a Julian date still needs a scale.

---

## Trivial tier

> **BLUF:** Ordinary programs call `now`, `sleep`, `within`, `today` and `parse_instant` with no setup.
> - Subtracting two readings gives a plain exact `Duration`.
> - Clock reads never fail. Problems surface as a status on the value, once at program entry, or through the task's failure channel.

```dewy
let start = now()
work()
printl"took {now() - start}"
sleep(300ms)
printl"today is {today()}"
let deadline = now() + 5s
within(2s @fetch()) or_throw
let t = parse_instant"2026-10-24T12:00:00Z" or_throw
printl(t + 90minute)
```

### What each line does

This assumes a healthy UTC host, a start at `2026-10-24T12:00:00Z`, a second read 125ms later, and clock support within that date.

- **`now()`** captures a `ClockReading`. `now() - start` is a plain exact `Duration`, so the first line prints `took 125ms`.
- **`sleep(300ms)`** returns the empty result after at least 300ms on the elapsed clock. Cancellation propagates through the enclosing task's cancellation contract, not through a discarded error.
- **`today()`** gives `Date` and prints `today is 2026-10-24`.
- **`deadline`** is a `WallTime` 5 coordinate seconds after that call's nominal reading. It is a wall target, not a monotonic timeout.
- **`within`** returns the fetch result, or a timeout, cancellation or fetch failure. `or_throw` forwards those outcomes.
- **`parse_instant`** returns `WallTime | ParseError |` resolution failures. Here it succeeds, and the final line prints `2026-10-24T13:30:00Z`.

### `WallTime` and `ClockReading`

- **Contents.** `WallTime` holds an exact nominal `Instant`, the source label or observation, an `Estimate<Instant>`, a status, and interpretation/display context. `ClockReading` adds acquisition evidence.
- **Not an `Instant`.** Neither type is an exact physical observation, and neither is an implicit subtype of `Instant`.
- **Arithmetic:**
  - `wall + duration` gives `WallTime`; it translates both the nominal coordinate and the estimate.
  - `wall − wall` gives `Duration`, computed from the **nominal coordinates**.
  - Comparing nominal coordinates is a separately named operation. Ordering estimates is covered in §2.
  - Arithmetic never invents a representative for an `Estimate` that lacks one.

### Durations

- **Plain durations** are exact numeric differences, not accuracy certificates. A wall step can make a difference negative; it is never clamped.
- **Elapsed time immune to wall steps:** `time.elapsed(@work())` uses the default monotonic provider. It returns a duration or a real continuity failure, and needs no clock scope.
- **Uncertainty-bearing difference:** `finish.estimate - start.estimate` keeps the dependence between the two estimates.
- **Strict callers:** `$time.require_clock_accuracy` and `$time.require_loss` forbid implicit nominal arithmetic while their obligations are unmet. Strict code must ask the nominal question explicitly or supply evidence.

### Display

- **Purpose.** Human display is a compact declared view, not serialization.
- **Markers:**
  - `~2026-10-24T12:00:00Z`: `~` means measured or estimated. It is not an accuracy bound.
  - `?` is added when accuracy is unknown.
  - Stale or discontinuous sources append their status.
- **Parsed values print without `~`.** A value derived from a label, like `t`, asserts an interpretation, not a measurement. Its projection onto ideal TT is nominal; it never proves that realized UTC equals ideal TT.
- **What `parse_instant` does:** it parses a full offset-bearing label, resolves the scale convention, then keeps the nominal projection and the original label.
  - Offsetless input, or input that resolves more than one way, fails instead of guessing.
  - Low-level parsing can stop at labels.

### Program entry

- **What the runtime does at entry:** it validates and retains the clock handles the program demands, a usable nominal wall seed, the wall convention, and any civil configuration needed.
- **Failures are reported once, at entry,** before dependent user code runs: unavailable providers, unsupported wait semantics, missing configuration.
  - Embedders can handle that result or install a supplied or test context.
  - This is not an undocumented exception, and it does not demand scientific accuracy.
- **Pay only for what you use.** Pure programs acquire nothing. Elapsed-only programs need no civil packs.
- **Entry captures configuration,** not frozen clock values.

### Live reads

- **Reads are total.** Each read is a data acquisition from the established handle, so `now()` has no error branch.
- **Degradation is visible:**
  - Losing synchronization widens the uncertainty.
  - Losing fresh wall samples switches to identified holdover.
  - If there is no justified continuation, the last nominal coordinate is kept as stale, with unknown support and a discontinuity status. It is never claimed to be current.
- **`today()` projects the actual support:**
  - One possible date gives `Date`.
  - Several give a printable `AmbiguousToday`, e.g. `today is uncertain (2026-10-24 or 2026-10-25)`.
  - Unknown support gives `UnknownToday` with a marked nominal date, `~2026-10-24?`.
  - Missing civil coverage prints its status.
  - Algorithms that need a definite date handle the union. Formatting never silently picks one side of a civil ambiguity.

### Capture across closures and tasks

- **Captured providers stick.** Closures and async tasks keep the captured provider across migration and suspension; changing host settings does not replace it.
- **Waits and cancellation are fixed early.** Default wait capabilities and cancellation behavior are set at entry or at task creation.
- **Lost wait capability fails the wait.** If a required wait capability is lost at runtime, the wait ends through the task's declared failure channel. It never returns as an early successful sleep.
- **Strictness is opt-in.** Strict metatags (§12) expose these ambient, resource and failure contracts without forcing a branch onto every ordinary clock read.

---

## 1. The coordinate core

> **BLUF:**
> - `Instant` is an exact rational number of seconds on an **ideal TT-rate axis**, counted from a frozen epoch (Apollo recommended).
> - It is stored as an integer count of a rational tick.
> - Real clocks (TAI, UTC(k)) are *realizations*; their relation to the ideal axis is an estimate.
> - `as` is used only for unique, exact conversions.

### The axis

- **Points.** `TimePoint<Domain>` is an affine point. `Instant` is its terrestrial specialization: signed exact-rational seconds from a frozen epoch on the ideal TT-rate axis.
- **Stable.** The axis does not change when metrologists improve a realization.
- **A convention.** It is mathematical, not the proper time of every observer or a universal simultaneity.

### Defining constants (exact)

- `L_G = 6.969290134e-10` and `L_B = 1.550519768e-8`, dimensionless rationals.
- `TDB0 = -6.55e-5s`, and the conventional TAI-to-TT(TAI) offset `32.184s`.
- `J0 = 2443144.5003725`, the common nominal 1977 reference Julian-date number. Its TT label is `1977-01-01T00:00:32.184 TT`.
- For each named scale S, `x_S = (JD_S − J0) × 86400s`.
  - Each JD argument belongs to its own scale.
  - Equal numbers in different scales do not automatically identify the same remote event.

With rational seconds value `q` (not the stored tick count) and epoch offset `e`:

```
q × 1s = x_TT − e
x_TT = (1 − L_G) × x_TCG
x_TDB = (1 − L_B) × x_TCB + TDB0
```

- **Inverses:** `x_TCG = (q × 1s + e)/(1−L_G)` and `x_TCB = (x_TDB−TDB0)/(1−L_B)`. These are exact affine definitions, including the inverse divisors.
- **Epoch vs rate.** Changing the zero changes `e`, never the rate.
- **Origins:**
  - The TT/TCG origin coincidence follows the standards convention.
  - The TCB expression uses its own barycentric argument.
- **Out of scope.** Neither equation supplies the geocentric-to-barycentric spacetime transformation (§4).
- Sources: [SOFA TT/TCG](https://raw.githubusercontent.com/Starlink/sofa/master/src/tcgtt.c), [SOFA TCB/TDB](https://raw.githubusercontent.com/Starlink/sofa/master/src/tcbtdb.c).

### Epoch (recommended: Apollo)

- **The value.** The epoch freezes the **ideal TT coordinate** `1969-07-20T20:18:19.7585938 TT`, so `e = (−1175538662127031/5000000) × 1s` relative to J0.
  - Its nominal TAI-compatible label is `1969-07-20T20:17:47.5745938`.
  - Labels defining origins use proleptic Gregorian fields.
- **The digits define a convention.** They say nothing about how accurately the lunar touchdown was observed.
- **Motivation.** It starts from the UTC label `1969-07-20T20:17:40`, where the old rate rule gives `TAI−UTC = 7.5745938s`.
  - At runtime the zero does not depend on that table.
  - Source: [historical UTC coefficients](https://maia.usno.navy.mil/ser7/tai-utc.dat).
- **Alternatives,** which differ only by exact offsets:
  - the standards origin, `e=0`;
  - a Unix-calendar zero, `1970-01-01T00:00:00 TT`.
- **Before publishing.** The constant needs an independent standards-vector check before its wire identity is published.

### Nominal vs realized time

- **`TAICompatible` is a nominal label.** It is the calendar number of an ideal TT coordinate, offset by `−32.184s`. It never claims to be published realized TAI.
- **Real TAI records carry their realization identity:**
  - `TT(TAI)=TAI+32.184s` is an exact relabeling *within that realization*.
  - Its mapping to ideal TT is an estimate.
- **Other realizations keep their identity too:** TT(BIPM edition), UTC(k), provisional products and clock correlations.
- **Recalibration adds, never rewrites.** A new calibration produces a new event estimate. It never changes `q` or rewrites a raw reading.
- **Label arithmetic stays exact.** It can stay entirely in a realized domain: two declared TAI labels have an exact difference even if the physical events are imperfectly known.
- **Projection onto `Instant` is explicit:**
  - It is a named operation, and it keeps its assumption in the containing record.
  - It is not `as`, and it does not prove the event occurred there.
  - Ordinary parsing returns a label or resolution record *before* any projection.

### Arithmetic and range

- **Valid operations:**
  - point − point gives a domain-branded difference;
  - point + compatible difference gives a point;
  - an affine average is allowed when the weights sum to one.
- **Invalid operations:** point + point, scaling a point, and implicit cross-domain subtraction.
- **Fixed scientific intervals** such as the Julian year have separate names. Calendar `year` never becomes a duration.
- **Bare magnitudes** (`5s`, `300ms`, `1hour`, `1ns/3`) are exact and interpreted by the receiving domain. A measured TCB or proper-time difference keeps its domain even though its unit is still seconds.

### Integer ticks, exact rational meaning

- **Meaning vs storage.** A value means exact rational seconds; it is stored as an integer count `n` of a positive rational tick `τ`, and the value is exactly `nτ`.
- **Proposed spellings:**
  - `Instant<tick=1ns>`;
  - `Instant<tick=1s/2^32>`;
  - `Instant<tick=1s/9192631770>`, the caesium-cycle unit. This does not claim a real oscillator is perfect.
  - The same parameter applies to durations and other coordinate domains.
- **A tick is only a representation.** It never changes scale, realization, epoch or observer.
- **Plain `Instant`** admits every finite rational: reduced `N/D` seconds is integer N at its own tick `1s/D`.
- **Fixed-tick values** store only `n` when the type supplies `τ`.
- **Integer width** is independent: a tick does not imply 64-bit storage.
- **Equality across ticks.** Equivalent coordinates compare and hash identically regardless of tick.
- **Arithmetic stays exact:**
  - An unconstrained result uses a common finer rational tick.
  - Assigning to a fixed tick requires divisibility or a checked conversion.
  - The compiler never rounds by inference.
- **`as`** can change ticks only when exactness and range are established.
- **`quantize(tick=… rounding=…)`** returns the rounded value and the signed loss (original minus rounded). Ties, floor, ceiling and truncation are named policies.
- **`t.ticks(tick)`** returns a record of integer `count` and duration `remainder`:
  - `t − epoch = count × tick + remainder`, with `0s <= remainder < tick`;
  - it floors, so `−0.25s` at `1s` gives count −1 and remainder `0.75s`;
  - a duration supplies its own zero;
  - this is a decomposition, not a lossy conversion.

```dewy
let exact = t.nominal
let [count remainder] = exact.ticks(1ns)
let rounded = exact.quantize(tick=1ns rounding='nearest_even') or_throw
```

- **Explicit question.** `t.nominal` states the numeric question explicitly, since `t` is a wall envelope.
- **No sentinels.** Zero and negative values are ordinary coordinates, never missing-value sentinels.
- **No global limits.** There is no global minimum tick or date range. Finite rationals still cannot represent every real number or infinity.
- **Resources.** Allocation, denominator growth and numeric work obey resource contracts.
- **Epoch shifts can refine the grid:**
  - Exact epoch shifts and affine conversions may require finer ticks; for example, an NTP binary fraction shifted to the Apollo zero may leave the binary grid.
  - Plain `Instant` stays exact.
  - Keeping a chosen fixed grid needs the divisibility check.

### What `as` may do

- **Allowed:** unique, exact, applicable conversions only. That means units, frozen epochs and definitionally related scales.
- **Named operations instead:** approximate models, context selection, civil inverses, rounding, and interpreting measured events. These return values.
- **Domain compatibility:**
  - Domain equality can be checked statically or at runtime.
  - Unrelated devices, boots, observers and frames never become compatible through a cast.

---

## 2. Answers, estimates and evidence

> **BLUF:**
> - A lookup returns one answer, a set of candidates, a proved-empty result, or a *specific* unresolved outcome. It never guesses.
> - `Estimate<T>` is a set of admissible values that carries identity, so arithmetic tracks shared error (`X−X = 0`) and never assumes independence.
> - Comparing estimates can answer "indeterminate".

### Kinds of answer

- **Possible results:** one answer, a finite or lazy candidate collection, a proved-empty mapping, or an unresolved result.
- **Civil outcomes:**
  - `Gap` is an established missing civil span.
  - `Ambiguous` carries all known alternatives with their explanations.
- **Unresolved outcomes are distinct:** `MissingContext`, `MissingData`, `OutsideCoverage`, `Unknown`, `UnsupportedModel` and `InconsistentEvidence`.
- **An absent provider** never becomes an empty candidate set.
- **`Unspecified` vs `Unknown`.** `Unspecified` means information was deliberately omitted; `Unknown` means it was sought but is not known.

### `Estimate<T>`

- **Contents:** a stable variable/expression identity, a domain, a support or constraints, evidence references, and an *optional* nominal representative.
- **The representative is optional.** Two competing historical interpretations need no privileged midpoint.
- **Support** can be a singleton, a disconnected set, an interval set, a constrained symbolic object, or unknown.
- **Distribution and confidence** are optional extra structures. A 95% interval is not a guaranteed support bound.
- **Error sources stay separately identified:** measurement, quantization, numerical error, model discrepancy, future-rule scenarios and source disagreement.
- **Precision is not accuracy.** A field's display precision does not establish its accuracy.
- **Partial labels.** `YearMonth` is a partial calendar label, not a uniformly distributed instant.
- **Rounded text.** Turning it into a quantization cell needs its rounding rule and civil context.

### Dependence and arithmetic

- **Joint, not marginal.** Operations map the joint admissible assignments, not independent per-value ranges.
  - `X+d` translates every possible value.
  - `Y−X` is evaluated on the same joint assignment.
- **Copies keep their variable identity.** Another observation with identical bytes is independent only if its evidence establishes that.
- **Examples:**
  - `X−X` is exactly zero, even when X has unknown support.
  - With `X=10s+E` and `Y=13s+E`, where `E` is the same calibration offset bounded by `[0s,2s]`, `Y−X=3s`.
  - With only marginal bounds `[10s,12s]` and `[13s,15s]`, conservative subtraction gives `[1s,5s]`.
- **Untrusted identifiers.** Shared error is never inferred from equal identifiers supplied by an untrusted producer.
- **Probabilistic models:**
  - `Var(Y−X)=Var(Y)+Var(X)−2Cov(X,Y)`.
  - Root-sum-square needs a justified zero-covariance model; independence is a sufficient, stronger condition.
  - Independence is never assumed silently. A caller can supply it explicitly, and the result retains that assumption.
  - Deterministic arithmetic never requires probability.
- **Implementation options:**
  - Strategies: expression nodes with shared error symbols, exact finite sets, or certified enclosures.
  - The budget can limit precision, never soundness.
  - If dependence is forgotten, the result is a conservative enclosure. Direct same-variable cancellation is still preserved.
  - A convex hull is an explicitly lossy enclosure of disconnected possibilities.
  - If neither exact propagation nor a sound enclosure is possible, the result is `UncertaintyUnsupported`.
- **Contradictory evidence** gives an inconsistency, not an empty successful estimate.
- **Conditioning** or adding evidence creates a new value and keeps the earlier evidence graph.

### Equality and ordering

- **Exact coordinates** have Boolean equality and order within a compatible domain. Equivalent rationals hash identically.
- **Record equality** also respects semantic fields and definition identities.
- **Identity is never inferred from coordinates.** Event identity, recurrence identity, original spelling and observational identity are separate operations.
- **`compare_estimates(X Y)`** quantifies over a nonempty joint admissible set:
  - `Before` / `After` / `Same` mean `X<Y` / `X>Y` / `X=Y` for *every* admissible assignment.
  - `Same` can come from shared-variable identity or two equal exact singletons. It cannot come from equal nominal values, overlapping ranges or equal distributions.
  - Otherwise the result is `Indeterminate`, listing the possible relations.
  - Unknown domains give `Incomparable`. Inconsistent evidence is reported before comparison.
  - `Same` means coordinate equality under the evidence, not event or record identity.
- **`certainly_before` and `possibly_before`** are derived queries. A proof-limited engine can return unknown with a reason, never a false certainty.
- **Tolerance equality** is not a hash equivalence.
- **Causal comparison is separate.** Vector-clock `Concurrent` and relativistic `Spacelike` are not in the scalar comparison enum.
- **`if` is unchanged.** It still requires an ordinary Boolean.

---

## 3. Intervals and topology

> **BLUF:**
> - Intervals store explicit endpoint-inclusion flags. The convenience constructor is half-open `[a,b)`.
> - An unknown end is not an infinite end.
> - Allen's 13 relations classify endpoint geometry only. Empty and point cases get their own tagged results, never forced Allen labels.

### Representation

- **Contents:** domain, lower and upper bound, and inclusion flags for finite ends.
- **Kinds of bound:** a finite coordinate, a known unbounded end, or an unknown endpoint with constraints.
- **Unknown is not infinity.** "Until further notice" has an unknown end; it does not assert that the activity never ends.
- **Explicit special cases.** Empty sets and closed singleton intervals are explicit.
- **Constructor checks:**
  - It validates compatible domains and endpoint order.
  - If the order is unresolved, it returns a constrained interval or an unresolved result, never an assumed-valid interval.

### Constructors

- **Default.** The recommended convenience constructor is half-open `[a,b)`. Explicit open and closed constructors always exist.
- **No next instant.** The rational axis is dense, so converting a closed end to half-open by adding a nanosecond is invalid. A discrete calendar-day interval can use the calendar's proved successor.
- **Infinite endpoints** are never members.
- **Equal finite endpoints** give a singleton only when both ends are closed; otherwise the set is empty.

### Set operations and measure

- **Flags are respected** by union, intersection, difference, complement relative to a named universe, membership, containment and disjointness.
- **Canonical interval sets** merge pieces only when the union adds no missing point.
- **The empty set** intersects nothing and is contained in every set.
- **Measure:**
  - A finite interval measures `b−a`, regardless of endpoint inclusion; a singleton measures 0.
  - An unbounded interval has infinite measure, represented outside finite `Duration`.
  - An unknown endpoint gives an estimated or unknown measure.
- **Calendar span length is not elapsed time.**

### Allen relations

For proper intervals A=(a,b), B=(c,d) with `a<b`, `c<d`:

- **before:** `b<c`; **meets:** `b=c`; **overlaps:** `a<c<b<d`.
- **starts:** `a=c` and `b<d`; **during:** `c<a` and `b<d`; **finishes:** `c<a` and `b=d`.
- **equals:** `a=c` and `b=d`.
- **after**, **met_by**, **overlapped_by**, **started_by**, **contains**, **finished_by** are the inverses of the first six.

How to read them:

- **Geometry only.** They classify endpoint geometry, independent of inclusion.
  - `equals` means equal endpoints.
  - `same_set` also compares topology.
- **Examples:**
  - `[a,b)` meets `[b,c)` but is disjoint from it.
  - `[a,b]` and `[b,c]` meet and also intersect at b.
- **Infinite ends.** Known infinite ends use the extended order; infinity is never a fictitious meeting event.

### Degenerate and uncertain cases

- **Empty inputs** give `EmptyOperand`; the set predicates are still defined.
- **Point vs point** gives before/equal/after.
- **Point vs proper interval** gives before/start/interior/end/after, plus membership from the flags. The inverse query swaps operands.
- **Uncertain endpoints:**
  - They give the *set* of possible tagged relations over the admissible joint assignments, plus possible/certain set predicates.
  - Constraints (e.g. "ends after Tuesday") narrow the set. Unknown does not automatically mean every relation.
  - "Certain" means proved for every assignment.
  - When search is limited, the result is a sound superset marked as an enclosure.
- **Composition** uses the standard Allen composition table on proper intervals. Topology and degenerate cases keep their own constraints.
- **Constraint inconsistency** is an error value.

---

## 4. Scale transformations and UTC

> **BLUF:**
> - Converting between scales uses declared, versioned transformations, and route choice is never silent.
> - UTC is a versioned, segmented relation to realized atomic time, including continuous UTC from **20 May 2027**.
> - Leap seconds, smears, POSIX/FILETIME, JD/MJD and GNSS are adapters that keep their conventions.

### Transformations

- **Each one declares:** source and target domains, the event position it requires, its definition/model edition, data dependencies, applicable region, accuracy contract and algorithm. Composition keeps all of these.
- **No silent routes.** Graph search never quietly picks a route; the context names a preferred route, or the alternatives are returned.
- **Exact definitions** need no ephemeris. Applying them to measured events still propagates the measurement uncertainty.

| Conversion | Nature |
|---|---|
| TT↔TCG, TCB↔TDB | Exact affine maps (§1) |
| TAI↔TT(TAI) | Exact offset within one realization |
| TCG↔TCB | Spacetime-event transform: location, Earth trajectory, external potentials, a named relativistic approximation |
| TT↔TDB | Normally composes the above; a geocentre approximation must name its location and error envelope. A scalar alone cannot determine it. |
| Proper time | Integrates a worldline in a metric |
| UT1 | Measured or predicted Earth orientation |
| SCLK | Mission clock correlation |

Missing models, insufficient accuracy and expired coverage are explicit values.

### UTC

- **A versioned relation.** UTC is a versioned relation to realized atomic labels, with three regimes:
  - before 1972: fractional offsets and rate adjustments, using the dated rate formula, never a modern integer offset;
  - from 1972: integer leap steps;
  - continuous UTC.
- **Before supported definitions** the result is outside coverage, unless an explicit proleptic convention is selected.
- **Continuous UTC** is effective **20 May 2027**:
  - The inherited boundary offset comes from authoritative transition records.
  - The adopted bound is `|UT1−UTC| ≤ 3600s`. No future leap-hour mechanism is specified.
  - It is modelled as a new effective segment, not a year test or a hardcoded `37s`.
  - Later standards changes add segments without changing stored labels.
  - Source: [CGPM Resolution 5 (2026)](https://www.bipm.org/en/cgpm-2026/resolution-5).

### Leap seconds

- **Positive leaps** validate the actual inserted label, including `23:59:60`.
- **Negative leaps** remove a label. Synthetic histories test that path without claiming such a leap occurred.
- **Standalone times of day** can carry an unresolved leap marker; validating it needs a date and a regime.
- **Example.** From `2016-12-31T23:59:59 UTC` to the following midnight is `2s` in the declared atomic realization. Tying the labels to actual observations adds their realization errors.
- **UTC to local** handles second-level historical offsets and carries a leap marker where ordinary fields can't. A codec that cannot express the result returns `Unrepresentable`.
- **Earth-orientation interpolation** uses a continuous argument and treats the UT1−UTC discontinuity explicitly.
- **Old announcements:**
  - An expired announcement does not invalidate a leap already established in history.
  - An old pack cannot certify new future policy.

### Adapters and labelled numbers

- **POSIX and FILETIME** counts are adapters, never the core.
  - A collapsed or repeated second can have several inverses.
  - A raw OS reading needs its leap behavior identified.
- **Smears** are distinct time-warp profiles, each with a window, formula, implementation version, inverse multiplicity and error contract.
  - An unknown smear cannot resolve uniquely.
  - A provider that rounds or drops a leap returns loss information or keeps phase metadata.
- **JD and MJD** need scale tags. MJD = JD − `2400000.5`, which also changes the day-boundary convention.
- **J2000** means `JD 2451545.0 TT` when used as this exact epoch; it is not automatically TDB or a frame.
- **GNSS** systems have distinct epochs, offsets, realizations and truncated-era rules.
  - Era resolution needs external evidence; a rollover counter never silently picks the current era.
  - Navigation adapters keep the broadcast ephemeris, satellite-clock and relativistic-correction conventions. A generic GNSS timestamp type cannot hide a correction that was applied twice or omitted.

---

## 5. Civil calendars, zones and arithmetic

> **BLUF:**
> - **Types.** Date, time-of-day, local date-time, offset, zone and zoned date-time are separate types.
> - **Default calendar.** Generic `Date` is proleptic Gregorian with a year zero.
> - **Pluggable data.** Calendars, day boundaries and zones are pluggable, versioned relations that can be multivalued.
> - **No silent fixes.** Folds and gaps are never resolved silently; you choose a named policy.
> - **`Period`** is a calendar recipe, not a number of seconds.

### Types

- **The types:** `Date<Calendar>`, `TimeOfDay`, `LocalDateTime`, fixed `Offset`, rule-based `Zone`, and resolved `ZonedDateTime`.
- **Nothing hidden.** A date has no hidden hour; a time has no hidden date or zone.
- **Resolved records keep everything:** the coordinate or estimate, original intent, calendar, zone, provider editions and the resolution trace.
- **Default `Date` calendar:** proleptic Gregorian with astronomical signed years, including year zero.
  - Era views without a year zero map explicitly.
  - Proleptic arithmetic does not claim historical adoption.
  - Each default is identifiable and individually disableable (§12).

### Calendar protocol

- **A calendar specifies:** field identities, validation, ordered day possibilities, label↔ordinal relations, month sequences, era/year mapping and optional cycle membership.
- **Relations can be partial:** multivalued, pending publication, or valid only within an evidence horizon.
  - Observational calendars do not promise a total bijection.
  - Arithmetic Gregorian/Julian calendars give stronger, total contracts.
- **No built-in shape assumptions:** a calendar need not have 12 months, fixed month names or 7 weekdays, and not every date needs a weekday.
- **Leap months** have distinct identities even when their names or numbers repeat.
- **Lengths vary.** Month and year lengths vary, and days can fall outside a week or month cycle.
- **Separately named implementations:**
  - Chinese and Hebrew leap months;
  - Islamic observation and calculation variants;
  - Persian equinox variants;
  - Japanese eras;
  - Ethiopian/Coptic and Buddhist conventions.
- **Different authorities.** Religious and civil uses can select different authorities.
- **Eras.** Mid-year era transitions and unpublished future era names work without inventing labels.

### Day boundaries

- **What `DayBoundary` does:** it connects a calendar day to physical events.
- **Providers:** midnight in a zone, local sunset, a chosen body's solar phase, or a published operational schedule. Each needs its location, model and authority.
- **Converting between calendars.** A calendar-day identity converts between calendars without claiming an exact physical instant.
- **No unique midnight assumed.** A boundary can be absent or ambiguous; a day realizes to an interval set or unresolved support.
- **Unequal seasonal hours** subdivide daylight and night under a named historical convention. Their lengths need the location and a solar model; they are not fixed `hour` quantities.

### Historical calendars

- **What they compose:** reforms, legal year-start changes, interrupted reforms, exceptional insertions, erroneous early leap practice, and delayed local adoption.
- **Examples:**
  - British 1752: in the named jurisdictional calendar, the day after September 2 is September 14.
  - Swedish `1712-02-30` is valid only in its historical sequence.
- **Places.** A historical gazetteer resolves changing place names and jurisdiction boundaries.
- **Preserved:** original transcription, calendar/year style, place, authority and competing evidence.
- **Old Style and double dating:**
  - Old Style can concern both the calendar and year numbering.
  - Double dating asserts related interpretations that must be checked.
- **Lost conventions,** contradictory records and approximate eras stay unresolved or constrained values.

### Zones

- **Definition.** A zone is an identity plus a versioned transition relation. Offsets can be fractional hours and seconds.
- **Matching offsets don't mean the same zone.** Neither equal current offsets nor matching current rules establish zone identity, since histories can diverge or converge.
- **Renames.** Aliases and renamed IDs keep the original key and a versioned canonical mapping.
- **Abbreviations.** `CST` produces candidates, not a unique zone.
- **Transitions are general.** They can be any size, at any local hour or weekday, any number per year.
  - The same machinery handles no DST, hemisphere differences, temporary suspensions, negative saving, permanent rule segments and nonseasonal corrections.
  - DST annotations are metadata, not the resolver.
- **Dates can vanish or repeat.** Synthetic histories can produce more than two candidates.
- **Missing labels** return the transition span and the valid neighboring boundaries.

### Geography

- **Location to zone** is a separate, time-indexed spatial relation:
  - countries contain several zones, and zones cross borders;
  - overseas jurisdictions differ, and borders move;
  - oceans and disputed areas can need a convention.
- **Locale never supplies a location.**
- **Law vs practice.** Legal rules and observed practice are separate assertions.
- **Moving observers.** Travelers use an itinerary. Ships and aircraft can use an operational clock independent of geography.
- **The date line** changes labels without adding elapsed days. Several observers can legitimately show different civil dates for the same coordinate.

### Resolution policies

- **Native resolution never guesses** a fold or repairs a gap.
- **Named policies:**
  - earliest, latest or all candidates;
  - reject or skip;
  - preserve displacement through a gap;
  - move to the next valid boundary.
- **The last two differ.** A missing 02:30 in a one-hour gap becomes 03:30 under the first and 03:00 under the second.
- **`choose`** takes the whole resolution union as a free function, so exception-forwarding method calls cannot bypass ambiguity handling.
- **Policy traces** stay in resolved records.

### Calendar operations

- **`Period` is a recipe.** It is an ordered list of calendar steps, not a vector of seconds; `month` and `year` combine only with real calendar context.
- **A calendar day is not `24hour`,** especially across reforms, date-line changes, clock shifts and leaps.
- **`Instant + Period`** needs an explicit civil projection and resolution route.
- **Date subtraction** counts calendar successors or declared ordinal differences, not elapsed seconds.
- **Overflow is explicit:**
  - reject, clamp, skip, or another named contract;
  - leap-day year addition and fractional calendar units also need an interpretation;
  - repeated clamping from January 31 can differ from an anchored "last day of each month". Keeping month-end is its own anchor rule.
- **Periods:**
  - Composition keeps order; it need not commute and is not generally invertible.
  - Differences need a decomposition convention.
- **Rounding.** Scalar, calendar-boundary and local-clock rounding each name their tie and gap/fold handling.
- **Anniversaries.** Birthdays, legal age thresholds and anniversaries are date rules, not elapsed seconds divided by a year.
- **Partial dates.** `MonthDay`, `YearMonth`, masked dates and approximate historical descriptions keep their deliberately absent fields.
- **All-day events** are a date span plus intent.
- **Skipped dates.** Projecting a skipped civil date gives empty support. That is different from an unknown calendar announcement.

### `zoned` in practice

`zoned` combines parsing, zone lookup, resolution and optional policy behind one fallible boundary.
- **No bypass.** It consumes the whole resolution union internally, like `choose`, so method forwarding cannot bypass a fold.
- **Policies on demand.** An omitted policy rejects only when it is actually needed.
- **Constants.** Already-validated constants can discharge their checks at compile time.

```dewy
let meeting = time.zoned("2026-10-26T09:00" zone="America/New_York") or_throw
let repeated = time.zoned("2026-11-01T01:30" zone="America/New_York"
    fold='later') or_throw
let shifted = time.zoned("2026-03-08T02:30" zone="America/New_York"
    gap='preserve_displacement') or_throw
let jan = time.date"2027-01-31" or_throw
let feb = jan.add(1month overflow='clamp') or_throw
let birthday = time.date"2000-05-12" or_throw
let age = birthday.age(on=time.date"2026-10-24" or_throw) or_throw
let leap_birthday = time.date"2000-02-29" or_throw
let leap_age = leap_birthday.age(on=time.date"2027-02-28" or_throw
    leap_day='march_1') or_throw
let [instant as meeting_time] = meeting
```

| Binding | Result |
|---|---|
| `meeting` | Monday 09:00 −04:00. No fold policy needed. |
| `repeated` | The later 01:30, −05:00 |
| `shifted` | Repaired to 03:30 −04:00 |
| `feb` | February 28. A policy-free invalid addition returns `InvalidDate`. |
| `age` | 26 completed calendar anniversaries; no leap policy needed. Legal age needs jurisdiction rules. |
| `leap_age` | 26 |
| `meeting_time` | The record's coordinate or estimate, not physical certainty |

`time.choose` is still available when an interface shows the alternatives before deciding.

---

## 6. Intent, recurrence and scheduling

> **BLUF:**
> - **Separate records.** What the user meant (`Appointment`) is stored separately from each resolved `Occurrence`, from what happened (`Event`) and from measurements (`Observation`).
> - **Recurrences** expand lazily within budgets and keep stable keys. Unresolved occurrences stay visible instead of being skipped.
> - **RFC 5545** is an opt-in compatibility profile.

### Records

- **`Appointment`** keeps what should stay fixed: a coordinate, local fields in a named zone, floating fields bound to a travel context, or a physical/astronomical condition.
- **`Occurrence`** is one resolution, with its evidence and policies.
- **`Event`** is what happened; **`Observation`** is a measurement or reception.
- **Intent survives.** Resolving intent never destroys it.

### Recurrence

- **Pipeline:** nominal occurrence keys, then calendar candidates, then resolutions.
- **Retained:** anchor, calendar, zone/location behavior, rule profile, invalid-day/gap/fold choices, inclusions, exclusions, overrides, termination basis and data-update policy.
- **Identity:**
  - The key is the series identity plus the original recurrence coordinate.
  - Rescheduling changes an occurrence's realization, not its key.
  - Emitting both sides of a fold adds branch identities.
  - Era display changes do not create new series identities.
- **Selectors:** daily/weekly, nth or last weekday, end-of-month, leap anniversaries, alternate-calendar dates, solar events and institutional sessions.
- **Combining rules.** Unions, intersections and exceptions have defined precedence and duplicate suppression.
- **Participants in several zones** share one intent and project it independently. Keeping one participant's local hour does not keep everyone's.
- **Floating travel alarms** resolve against the declared itinerary; missing travel information stays unresolved.

### Expansion

- **Policies or unresolved.** Native recurrence requires policies, or it returns unresolved occurrences.
- **Counts** say whether they count nominal candidates or emitted occurrences.
- **Bounded and lazy.** Expansion is bounded by a window, a candidate-work limit, an output limit and cancellation. It returns outputs plus a resumable cursor, or a completed result.
- **Distinct outcomes:** `NoOccurrence`, `AwaitingPublication`, `OutsideCoverage` and `SearchBudgetExceeded`.
- **No hidden unbounded search,** even for a sparse or impossible rule.
- **Ordering.** Ordering guarantees say whether output is ordered by nominal key or by resolved time, since time shifts can change that order.

### RFC 5545 profile

`RFC5545` is a named compatibility profile, not the native default.

- **Explicit values:**
  - An explicit DATE-TIME in a fold selects the first occurrence.
  - An explicit value in a gap uses the pre-gap offset.
- **Generated values:**
  - Generated invalid dates and nonexistent times are skipped and don't consume COUNT.
  - Generated folds use the first occurrence.
- **DTSTART** supplies the first instance.
- **UNTIL** is inclusive, with its prescribed type/UTC constraints. COUNT and UNTIL are mutually exclusive.
- **Inconsistent combinations.** A DTSTART that contradicts its rule is rejected or kept uninterpreted.
- **RDATE, EXDATE,** duplicate suppression and RECURRENCE-ID keep their prescribed roles.
- **Example.** In New York, a gap label at 02:30 means 03:30 when imported as an explicit DATE-TIME, but is omitted when generated by RRULE.
- **Embedded VTIMEZONE** definitions keep their identity. Replacing one with a similarly named system zone is an explicit migration.
- **Export.** Exporting native policies that differ gives a semantic loss report or a bounded materialized expansion; it never promises equivalence from RRULE text alone.
- Source: [RFC 5545 §§3.3.5, 3.3.10, 3.8.5.3](https://www.rfc-editor.org/rfc/rfc5545).

### Execution and updates

- **What a scheduler adds:** durable occurrence IDs, cancellation, retries, duplicate handling, and policies for catch-up, missed runs and lateness. It promises only the selected delivery contract.
- **Exactly-once effects** need transactional or idempotent execution, not recurrence arithmetic.
- **Wall appointments** are re-evaluated when the wall clock or its correlation changes. They are armed as bounded monotonic waits with a specified step policy.
- **Rule updates:**
  - Each update creates a migration preview of affected future occurrences, changed assumptions and resolution differences.
  - A chosen cutover freezes past materializations and re-resolves future intent.
  - Pending or already executing work gets an explicit disposition.
- **Later evidence** adds interpretations of historical events without rewriting observations.
- **Restored schedules** recover intent and re-arm under the current clock domain. They never reuse an old boot's raw deadline.

```dewy
let weekly = time.recurrence("2027-01-04T09:00" every=1week
    zone="America/New_York") or_throw
let [occurrences as batch cursor] = weekly.expand(window limit=100) or_throw
let next = weekly.next(after=window.end) ??<NoOccurrence> none
```

- **`1week`** is a calendar recurrence step interpreted by `every`, not a fixed duration that overrides local time.
- **The native profile:**
  - keeps Monday 09:00;
  - leaves missing and ambiguous occurrences unresolved, never silently skipping or picking a fold;
  - orders by nominal key;
  - supplies bounded work and cancellation defaults.
- **Policies are added only when needed:**
  - `count_basis` matters only when a count is requested.
  - A DST-sensitive daily alarm can state `gap='preserve_displacement' fold='earlier'`.
  - A month-end series can state its anchor rule without configuring unrelated policies.
- **`expand`** returns a record, and its cursor identifies unfinished work. An explicit `work=10000` overrides the context's budget.
- **The fallback on `next`:**
  - The selective fallback `??<NoOccurrence>` leaves missing data, pending publication and search exhaustion visible.
  - Broad `??` deliberately defaults any exception value and `none`, following Dewy's existing semantics; it is not an implicit library recovery policy.

---

## 7. Clocks, scopes and waits

> **BLUF:**
> - **Providers, not scales.** A clock is a provider; its readings carry source, generation and evidence.
> - **No mixing.** Monotonic points from different providers or boots never mix.
> - **Capture.** The context is captured once at entry and inherited by closures and tasks.
> - **Relative waits** default to suspend-inclusive monotonic time; `clocks.active` is the explicit alternative.

### Clocks and readings

- **A clock is a provider,** not a time scale.
- **`ClockReading` keeps:**
  - source identity, raw count and device/boot/reset generation;
  - the acquisition bracket and resolution;
  - synchronization/trust state, correlation edition and the estimate.
- **Resolution is not accuracy.** Accuracy can be unknown even when resolution is fine.
- **NTP, PTP, GNSS** and authenticated transport provide evidence, not perfect physical truth.
- **Distinct failures:**
  - An unidentified POSIX/UTC/smear convention gives `UnknownClockConvention`.
  - Unavailable, unsynchronized and untrusted sources are distinct outcomes.

### Wall vs monotonic

- **Wall time** can step backward or slew.
- **Monotonic points** belong to a provider domain with declared suspension behavior, adjustment behavior and generation.
  - They never mix with wall points or with another boot's points.
  - Incompatible providers selected at runtime give `DomainMismatch`; statically known incompatibility is rejected.
- **Calibration** maps readings through an offset/rate model with coverage.
  - Uncertainty grows with elapsed counter time, under the certified drift bound plus acquisition and transfer error.
  - An expired or absent bound cannot keep its old accuracy claim.
- **Belongs to providers:** CPU counters, SMP synchronization, wrap, reset, audio/video sample clocks, dropped samples and frequency calibration.
- **Sample periods** can be exact rationals even when the oscillator drifts.
- **VM pause, migration and hibernation** need a provider contract: keep the domain only if continuity is guaranteed; otherwise mint a new generation or report a discontinuity.
- **Rollback stays visible.** A negative wall difference is never clamped.

### Capturing providers

- **`TemporalContext`** is immutable configuration: provider handles, calendar/zone/locale selection, model and rule locks, policies and resource budgets.
  - Its clock handle refers to a running service. Immutability freezes identity and configuration, not the passage of time.
- **Scopes capture once.** A scope captures the handle on entry. Short calls (`now`, `sleep`, `within`, `today`) resolve against the nearest captured scope, never a process-global provider chosen afresh on each call.
- **At application entry** the host context is snapshotted once.
  - Changing the host zone or provider needs a new context or an explicitly subscribed update stream; it never silently replaces a handle.
- **Inheritance:**
  - A closure created inside a temporal scope captures its context.
  - Async tasks inherit the creator's context and keep it across suspension, thread migration and resume.
  - Cancellation does not reset the clock.
- **Overrides.** An explicitly supplied context overrides the captured one for that operation.
- **Lifetime.** A context cannot outlive its provider without a retained handle.

```dewy
measure = (job) => time.elapsed(@job())
fetch_with_limit = () => within(2s @fetch())

let simulated = time.with_context(test.context () => measure(@work()))
```

- **Entry context by default.** Ordinary calls use the entry context. Explicit scopes are for injection or changed requirements:
  - `with_context` captures a complete supplied context;
  - `with_clocks` replaces only the clock handles.
- **The callback** is a closure value, and `@work()` is a partial application, not an eager call.
- **`elapsed`** brackets the job with one monotonic handle and generation. A reset gives a continuity failure.
- **`DomainMismatch`.** Supplying two incompatible runtime-selected points still gives `DomainMismatch`.
- **Wall reads** follow the total, status-bearing contract of the trivial tier. No quality check is silently turned into a trap.

### Test clocks

- **Advancing.** A test controller advances a virtual provider that tasks have already captured; it does not replace their provider.
- **Resetting** creates a new generation and invalidates old points. Subtracting monotonic readings from `testA` and `testB` fails even when both counts are zero.
- **Deterministic wakeups.** Advancing test time wakes eligible waits deterministically, and tests choose the order of wakeups that share a deadline.
- **Reversing time** (e.g. game time) is allowed only in a nonmonotonic domain, which cannot satisfy a monotonic-deadline contract.

### Suspension contract

- **Default.** `sleep(5s)`, `within(5s @work())`, relative TTLs and relative deadlines use **suspend-inclusive elapsed monotonic time**.
  - A deadline can expire during suspension, but its callback runs only when execution resumes.
  - Waking the device is a separate platform capability (a wake-capable alarm).
  - Unsupported suspend-inclusive semantics give `UnsupportedClockSemantics`. The runtime never silently substitutes an active-time counter.
- **`clocks.active`** is the named alternative: monotonic time excluding suspension.
  - It measures active system time, not CPU time; process and thread CPU clocks are separate.
  - Paused simulation time is another explicitly chosen domain.
  - Selecting it for a scope changes the meaning of relative waits there and appears in deadline metadata.
- **Timer behavior:**
  - Timers round up to the available resolution, recheck the deadline before succeeding, and may wake late.
  - Zero duration is immediately eligible; negative duration is rejected.
- **`within` limits:**
  - It requests cancellation at expiry.
  - It cannot force an uncooperative operation to finish, or promise that cleanup ends at the deadline.
  - Races between completion and cancellation follow the scheduler's documented arbitration.
- **Wall adjustments** never move a monotonic deadline; wall appointments are re-evaluated separately.
- **Persisted TTLs** need a reboot/recovery policy.
- **Even in the shortest examples,** domain contracts and attainable accuracy remain values or proof obligations.

---

## 8. Worked example: a sunset and publication calendar

> **BLUF:** A community calendar whose months start on an authority's crescent publication and whose days start at local sunset is built entirely from ordinary pieces. It needs no Gregorian fields, universal midnight or Earth time zone.

- **Two separate providers:**
  - The label↔ordinal relation uses authority editions.
  - The day-boundary relation uses location, a horizon/refraction convention and a solar ephemeris.
  - Neither secretly supplies the other's information.

```dewy
let community = app.calendar("community/crescent-calendar") or_throw
let sunset = time.day_boundary(
    kind='sunset' location=community.site
    model=science.solar horizon=community.horizon) or_throw
let gathering = time.recurrence(
    calendar=community boundary=sunset
    selector=community.month_day(1)
    offset=30minute offset_basis='coordinate'
    publication='require_authority') or_throw
let [known pending] = gathering.plan(window work=10000) or_throw
```

- **Syntax used:**
  - `plan` returns a record unpacked into `known` and `pending`; missing boundaries stay unresolved by default.
  - `(a b)` is several values, `[a b]` is a container, and `let [a as b] = record` renames a field.
- **`known`** holds resolved occurrences with their authority edition, boundary estimate and propagated uncertainty.
- **`pending`** holds resumable obligations, e.g. `AwaitingPublication(authority period)` or `NoBoundary(location date model)`.
- **App-defined members.** `site`, `horizon` and `selector` belong to this application's calendar; not every calendar must have them.
- **Timing:**
  - An announced first day starts at that evening's sunset, not Gregorian midnight. The meeting is 30 coordinate minutes later.
  - Uncertainty in solar geometry propagates into the meeting time.
  - If the sun doesn't set at that latitude, no meeting instant is fabricated.
  - A community policy can explicitly substitute another site's sunset or a published clock time; its authority and the semantic change travel with the occurrence.
- **Before publication:**
  - A predictive model can return several candidate days under an explicitly chosen forecast profile.
  - `require_authority` instead leaves a publication-wait obligation.
  - The scheduler subscribes to the authority feed or polls on a bounded plan. This is a cancellable external wait, not an unbounded search.
  - A new signed publication creates a new pinned context and resumes the plan. The signature authenticates the source, not the sighting's physical truth.
- **Identity and corrections:**
  - Stable occurrence identity uses the nominal month/day key.
  - An authority correction creates a revised mapping and a migration decision for future execution. It never erases the original publication or past attendance.
- **Distinct outcomes.** Polar failure, an unpublished month and a disproved date are distinct.
- **Same protocol elsewhere.** It supports a colony calendar over a sol ordinal and an operational boundary, with a publication authority for exceptional shifts.

---

## 9. Institutions, persistence and distributed systems

> **BLUF:** Business calendars, legal deadlines, bitemporal records and distributed clocks are built on the same primitives. A timestamp never implies identity, causality, mutual exclusion or exactly-once delivery.

### Institutional calendars

- **What they combine:** working-week history, observed vs actual holidays, religious and observational dates, bank days, exchange sessions, exceptional closures and private operating rules.
- **What they support:**
  - split and overnight sessions, and moving-zone shifts;
  - fiscal-year origins, 4-4-5 accounting, and tax/reporting calendars;
  - service dates with extended hours. `25:30` is a service-day offset interpreted by its operating rule, not a time-of-day.
- **Business-day and working-time arithmetic** use actual session interval sets with explicit roll and inclusion policies.
- **Surprise closures** and unpublished religious holidays give pending knowledge or named scenarios.
- **Payroll** separates measured elapsed work from contractually credited time across DST, travel and breaks.
- **Named conventions:**
  - Financial year fractions name their day-count convention.
  - Legal ages name their jurisdiction's birthday rules.
  - A generic `year` never becomes contractual seconds.

### Deadlines and law

- **A deadline rule specifies:** jurisdiction, the contract-named zone, the relevant calendar, inclusivity, closure/holiday behavior and boundary semantics.
- **Vague phrases.** "By midnight", "end of day" and "next Friday" are candidate intents until those choices are known.
- **User display preferences** never change legal time.
- **Retroactive laws** keep both the valid date and the publication date. Calculated results keep the rule edition and an explanation.
- **Sources:**
  - An official institutional feed and a third-party prediction are different evidence.
  - Licensing may require supplied rule packs rather than bundled data.

### Bitemporal records

- **Two axes.** Each record pairs a valid-time interval with a transaction/knowledge interval.
  - The axes can have different domains. A database commit sequence can be a more truthful transaction order than wall timestamps.
- **Queries.** `as_of` takes both "valid at" and "known as of".
- **Corrections** append assertions with supersession links, keeping earlier knowledge.
- **Separate times.** Event, publication, reception and processing times stay separate where relevant.
- **Late data.** Late arrivals and watermark bounds never rewrite event time.
- **Partitions.** Local-date partitions use explicit calendar/zone boundary sets, including gaps and folds.

### Distributed systems

- **Events.** Event IDs are independent of coordinates. Equal wall timestamps establish neither identity nor causality.
- **Lamport clocks** preserve happened-before in one direction. Sorting by `(counter node_id)` gives an administrative total order, not physical precedence. [Lamport](https://lamport.azurewebsites.net/pubs/time-clocks.pdf)
- **Vector and dotted-vector clocks** express causality and concurrency under named membership/incarnation rules.
- **Hybrid logical clocks** keep a physical component plus a logical counter. The counter is not extra sub-second precision.
- **Explicit handling** for rollback, counter overflow, resets and hostile remote values.
- **Cross-machine physical order** uses correlated estimate bounds; overlaps stay indeterminate.
- **Leases** need protocol assumptions about drift, communication, renewal, failures, and fencing or equivalent exclusion. A timestamp library cannot supply them.
- **Security expiry policy:**
  - It says whether to reject, permit or defer when trusted time support overlaps an expiry.
  - It handles unavailable or manipulated clocks.
- **Monotonic cache TTLs** keep their device/boot/suspend domain.
- **Durable transactions and scheduling** combine these records with idempotency and recovery. "Exactly once" is never inferred from a unique timestamp.

---

## 10. Science, observers and space

> **BLUF:**
> - `Instant` is a convenient terrestrial axis, not a mandatory hub.
> - Proper time, signal paths, spacecraft clocks, Mars, lunar and interstellar time are model-driven with explicit coverage.
> - Unavailable standards return `StandardNotDefined`.

### General model

- **What an event has:** a time coordinate, a position or worldline point, a reference system/frame, and model context.
- **No mandatory hub.** `Instant` is not required for Mars-local arithmetic or distant missions.
- **Consistent transforms:**
  - Coordinate transforms can require changing spatial coordinates and consistently scaled ephemeris positions, velocities and gravitational parameters.
  - Relabeling only TCB/TDB time while keeping incompatible dynamical parameters is rejected.
- **Proper time** integrates a metric along a specified timelike worldline, from an initial synchronization condition.
  - Different trajectories between the same events can accumulate different proper durations.
  - Weak-field approximations state their potential sign, velocity terms, omitted orders and error envelope.
  - Oscillator calibration stays distinct from relativistic correction.
  - A proper-time difference keeps its observer brand. A coordinate difference cannot claim to be a traveler's wristwatch duration.
- **Earth rotation:**
  - UT1 uses IERS data and prediction errors.
  - Ancient or future `ΔT=TT−UT1` needs a reconstruction model.
- **Angles and phases.** Earth rotation angle, mean/apparent sidereal time and solar phases are angle or phase constructions.
  - Mean solar time needs longitude and rotation; apparent solar time adds solar geometry.
  - Sunrise and sunset need horizon/refraction choices and can have no solution.
  - None of these redefines `hour=3600s`.
- **Causal queries** can establish timelike or null precedence, spacelike separation, or uncertainty under a model.
  - Spacelike coordinate order can reverse between frames.
  - A remote "now" needs a simultaneity convention; signal reachability is a different question.
  - Model coverage and accuracy limit every answer.

### Signals and flight operations

- **Signal paths** separate emission, reception, relay/turnaround and execution events.
  - Moving endpoints are evaluated at their own times, usually by iteration.
- **Propagation profiles** name geometric light time, gravitational (Shapiro) delay, media and hardware corrections, the convergence criterion, residual and model uncertainty.
  - Ordinary SPICE light-time/aberration modes do not include every relativistic correction. [NAIF](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/abcorr.html)
  - Occultation, multiple paths, no path, missing coverage and non-convergence are values.
- **Round-trip ranging** solves separate uplink and downlink legs plus turnaround, in the receiver's proper-clock domain.
  - Half the round trip is not necessarily the one-way delay.
  - Distance at one epoch divided by c is not a moving-endpoint solution.
- **Command planning:**
  - It works backward from an execution window, through decode and queue delays and receiver-clock uncertainty.
  - It intersects feasible emission windows with contact plans, transmission duration and station availability.
  - It returns windows and requirements, or `NoFeasibleWindow`. Sending is separate.
- **Disconnected execution** uses onboard clocks and durable command identities.
- **SCLK** keeps spacecraft/instrument/clock identity, partition/reset era, native count and raw telemetry.
  - Ticks need not have a constant SI duration.
  - Correlation kernels give piecewise maps, quantization, residuals, and reconstructed or predicted coverage.
  - An omitted partition can be ambiguous.
  - New kernels create revised reconstructions while keeping the original ticks and prior results.
  - Kernel pools are isolated behind pinned contexts. [NAIF SCLK](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/sclk.html)
- **Mission elapsed time** names its epoch and scale.
- **Distinct fields:** spacecraft event time, Earth reception time, ground transmission and exposure intervals.

A mission context pins its models once; each call names the physical question:

```dewy
let onboard = mission.sclk.parse("1/1465644281.0") or_throw
let event_time = onboard.correlate(model=mission.clock_kernel) or_throw
let flight = mission.signal.solve(receive=event_time
    sender=mission.station receiver=mission.rover tolerance=10ms) or_throw
let proper = time.proper_elapsed(mission.rover first_event last_event
    model=mission.relativity) or_throw
```

- **The SCLK string** is illustrative.
- **Correlation** keeps its target domain.
- **`receive`** specifies reception, not execution.
- **`10ms`** requests a supported error budget; it never manufactures one. Unsupported kernels or coverage return values.

### Bodies, settlements and distant models

- **Mars** distinguishes Mars Sol Date, mean prime-meridian time, local mean and true solar time, seasonal solar longitude, Mars-year conventions, and mission sol numbering.
  - The named Mars24 model takes TT input and uses its own mean-sol convention. [Mars24](https://www.giss.nasa.gov/tools/mars24/help/algorithm.html)
  - Dividing a sol into 24 hours does not make a Mars hour `3600s`.
  - Mission offsets and landing-site clocks stay explicit.
  - Darian and other proposed calendars are versioned plugins with declared epoch/leap rules and standards status.
- **Planetary local clocks** identify the body, body-fixed frame, orientation model, meridian, longitude sign, location, epoch and mean/apparent/operational flavor.
  - They handle retrograde or irregular rotation, tidal locking, polar absence and multiple illuminating bodies.
  - A habitat can choose an artificial cycle unrelated to rotation.
  - Variable phases can have several inverse events.
  - A location on one body cannot be reused on another.
- **Moon:**
  - Lunar TCL belongs to the IAU Lunar Celestial Reference System.
  - Operational LTC, scaled lunar proposals and ensemble realizations are distinct definitions.
  - The 2026 CGPM resolution calls for explicit models, ephemerides and uncertainty, but supplies no finalized operational LTC constant. [CGPM Resolution 6](https://www.bipm.org/en/cgpm-2026/resolution-6)
  - No fixed "microseconds gained per day" substitutes for the model.
  - Requesting an unavailable realization gives `StandardNotDefined`, unless the caller explicitly selects an experimental profile.
- **Interstellar** support extends reference charts, metrics, worldlines and signal solvers, rather than extrapolating a solar-system ephemeris.
  - Galactic, local-inertial, Fermi and cosmological charts name their conventions and domain.
  - Cosmic time, lookback time, redshift and distance measures depend on the cosmology.
  - Multiple light paths and horizons can prevent unique conversion or synchronization.
  - Huge rational coordinates prove neither a precise Big Bang epoch nor a globally valid chart.
- **Disconnected settlements** use offline packs and causal logs, without presuming an Earth clock is reachable.

---

## 11. Formats, localization and pinned data

> **BLUF:**
> - **Parsing never guesses.** Display is localized, and when it loses information it reports the loss.
> - **Codecs decode every bit exactly** in their declared domain.
> - **Data packs** are immutable, content-addressed and pinned, and fetching them is explicit.
> - **Cost follows use.** A stopwatch pulls in no zone, locale or ephemeris code or data.

### Parsing

- **Each parse names:** a grammar/profile, the expected result type, an optional locale, whether the full input must be consumed, and digit/length/depth budgets.
- **Offsetless text** gives local fields, not an implicit instant.
- **Candidates, not guesses.** Ambiguous numeric dates, two-digit years, abbreviations and natural language give candidate interpretations unless the selected profile supplies a convention.
- **Relative phrases** need a captured reference time, the viewer's zone and locale, and the intended boundary policy. "Yesterday" is computed in the viewer's civil context, not by subtracting `24hour`.

### Human display

- **Localization covers:** component order, punctuation, non-Western digits, grammatical month forms, pluralization, 12/24-hour clocks, noon and day periods, localized eras, and time-dependent zone names. Calendar-specific fields remain available. [Unicode TR35](https://www.unicode.org/reports/tr35/tr35-dates.html)
- **Weeks:**
  - Week calendars specify the first weekday and week-number rules; week-year differs from civil year.
  - Weekend definitions belong to dated cultural or institutional context.
- **Accessibility profiles** can spell out date order, zone, offset, era and uncertainty.
- **Locale preferences** never silently change geography or legal interpretation.
- **`24:00`** is an end-of-day boundary only in profiles that permit it, and its date association is preserved.
- **Rounded human output** is distinct from a lossless machine codec. It can show a nominal reading with an uncertainty marker under a named display contract, but never manufactures an exact value.
- **Loss reports** enumerate what was omitted: scale, zone identity, calendar, precision, uncertainty, provenance or intent.

### Native interchange

- **Contents:** schema/type tags, scale/domain/epoch identities, a canonical rational (numerator plus positive denominator), any fixed-tick type contract, context references, and optional evidence/intent structures.
- **Canonical encoding.** Equivalent rationals have one encoding, for hashing and signatures.
- **JSON** uses integer strings or rational records, never inaccurate numbers.
- **Identity:**
  - Observation identity is distinct from content-addressed definition identity.
  - Equal serialized reading content must never accidentally mint a shared uncertainty-variable identity.

### Exact codecs for real formats

- **Decode** keeps every represented bit or digit as an exact rational **in its declared domain**, with raw labels when inversion is unresolved.
  - Numeric exactness does not make era selection, UTC inversion, SCLK correlation or conversion to ideal TT exact.
- **Encode** checks range, divisibility and semantic fidelity. A nonzero remainder needs explicit rounding and a loss report.
- **Missing epochs or profiles** return requirements, never a guessed current era.

| Format | Key rules |
|---|---|
| **NTP 64/128-bit** | 64-bit: `(era × 2^32 + seconds) + fraction/2^32` from the 1900 NTP epoch; era evidence is external. 128-bit: signed 64-bit seconds (era plus era offset) and a 64-bit fraction, tick `1s/2^64`. Keep leap indicators, sync metadata and any smear profile; neither the fraction nor the era establishes accuracy. [RFC 5905 §6](https://www.rfc-editor.org/rfc/rfc5905#section-6) |
| **PTP / IEEE 1588** | 80-bit: 48-bit seconds plus 32-bit nanoseconds (validated < 10^9); the unit is `1ns`, not `1s/2^32`. TAI epoch `1970-01-01T00:00:00`. Keep clock/domain identity and timescale flags; ARB timescales need their own definition. The correction field (fractional ns) stays exact. [RFC 8877](https://www.rfc-editor.org/rfc/rfc8877.html#section-4.2), [IEEE interp.](https://standards.ieee.org/wp-content/uploads/import/documents/interpretations/1588-2008_interp.pdf) |
| **CCSDS CUC** | Parse the P-field coarse/fine lengths, including extensions; f fine octets give tick `1s/2^(8f)`. Standard epoch 1958-01-01 TAI; an agency epoch needs its definition. An omitted P-field needs an external profile. |
| **CCSDS CDS** | 16/24-bit day count, 32-bit ms-of-day, and an optional µs (16-bit) or ps (32-bit) field. These are decimal subunits, not binary fractions. Standard 1958-01-01 or agency epoch, with UTC rules that validate leap-day lengths. Days are never blindly multiplied by 86400 s. [CCSDS 301](https://ccsds.org/Pubs/301x0b4e1.pdf) |
| **GPS week + TOW** | Keep the full or truncated week width and the TOW unit. `week × 604800s + tow` from 1980-01-06 GPS; rollover needs external era evidence. Nominal GPS = TAI−19s, with realization evidence kept separate. Other GNSS differ. [GPS rollover](https://www.gps.gov/news/gps-week-number-rollover) |
| **SPICE ET / SCLK** | ET is TDB seconds past J2000 in this profile. Finite binary64 decodes exactly as a dyadic rational, with input quantization recorded separately; ET→TT needs a model. SCLK keeps partition, clock identity and native fields; native ticks are not SI seconds. Correlation returns estimates with kernel coverage. [ET](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/time.html), [SCLK](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/sclk.html) |
| **POSIX timespec** | Keep signed seconds and nanoseconds exactly, validated and normalized per the ABI. POSIX epoch/count rules and provider leap/smear behavior govern inversion; `1ns` resolution doesn't restore a collapsed leap phase. ABI overflow (including 2038) gives `OutOfRange`. |
| **Windows FILETIME** | Unsigned 64-bit count of `100ns` from the 1601 calendar origin, keeping API sentinels and leap behavior. Not elapsed TAI seconds since 1601. [Microsoft](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times) |
| **Two-part JD** | Both float parts become exact rationals and are added exactly, before subtracting the scale-tagged origin and multiplying by `86400s`. Decimal inputs keep their decimal value; input quantization is recorded. UTC quasi-JD needs its leap-aware profile. JD, MJD and scale identity stay distinct. |
| **RFC 3339 / 9557** | Decimal fractions decode exactly, with no nanosecond cap. Keep leap labels and unknown-local-offset semantics; a known instant doesn't establish a known zone. RFC 9557 zone/calendar annotations, critical flags and offset conflicts follow the profile. Non-terminating fractions need another format or explicit rounding. [RFC 9557](https://www.rfc-editor.org/rfc/rfc9557.html) |

- **ISO/iCalendar and SQL adapters** state backend/version, session conversion, zone retention, range and fidelity. A stored offset cannot reconstruct a discarded region or intent.
- **Separate error sources.** Representation error, solver error and physical-model uncertainty stay separate. Extra digits never extend coverage.

### Data packs: lifecycle and cost

- **What a pack identifies:** packs are immutable and content-addressed, and each identifies its authority, license, source edition, schema/algorithm version, dependency hashes, issue/publication and effective dates, coverage, uncertainty and supersession.
- **Locks and versions:**
  - A lock selects a compatible closure of packs.
  - Missing pinned bytes give `MissingData`.
  - Client/server version disagreement stays visible.
- **Signatures** authenticate bytes and publisher, not historical truth or future accuracy.
- **What ships:**
  - **Built in:** core algorithms, platform and test clocks, Gregorian/Julian calendars, interchange codecs, and identified baseline UTC, IANA and CLDR packs.
  - **Offline batteries:** richer calendar and locale datasets, with explicit deployment stripping.
  - **Known limits:** IANA's historical coverage, optional backzone and future-rule extrapolation have visible limitations; IANA is not a complete legal-history source.
  - **Science packs:** IERS orientation and announcements, BIPM realizations, IAU definitions, ephemerides, body models and mission kernels.
  - **Authority, legal and community packs** carry their own redistribution and evidence contracts.
  - **Support lists** name the actual implemented models and editions, never placeholders.
- **Updates are explicit:**
  - Fetching and installing updates are explicit operations, never hidden side effects of conversion or compilation.
  - Atomic context replacement installs a coherent dependency set.
  - Existing values keep their old references, and archive exports can embed the closure.
  - Revising historical interpretations and migrating future appointments are separate operations.
- **No precompiled images.** Runtime data loading never creates precompiled library images or bypasses fresh source checking.
- **Dependency layering points inward:**
  1. rational/domain algebra;
  2. clocks and exact definitions;
  3. UTC, calendars and zones;
  4. formatting and recurrence;
  5. institutional and distributed modules;
  6. optional science.

  A stopwatch reaches no locale, zone or ephemeris code or data.
- **Costs:**
  - Indexed zone and correlation lookup is `O(log n+k)` for k outputs; inverse lookup indexes overlapping local segments.
  - Recurrence charges candidates examined, not just outputs.
  - Big-number, calendar, numerical-iteration and ephemeris costs are declared separately.
  - Input limits and cancellation bound adversarial parsers, kernels and rules.
- **No code in data.** User calendar code uses ordinary effect and resource contracts; data packs never execute arbitrary code.

---

## 12. Every convenience assumption has an opt-out

> **BLUF:**
> - **17 named obligations.** Each convenience the defaults rely on is a named obligation, `$time.require_*`.
> - **Turning one on** demands an explicit choice or evidence.
> - **Turning it off** (`=false`) restores only its documented convenience, never an invalid operation.
> - **Bundles.** `$time.strict` enables all 17, and `$bulletproof` includes `$time.strict`.

### Principles

- **What defaults may do.** Defaults select contexts and profiles. They never repair civil ambiguity, assume independence, invent coverage or choose numerical routes.
- **The trivial tier** defines nominal arithmetic explicitly. It never coerces estimates into exact observations or changes retained evidence.
- **Assumption trace.** Every convenience used is recorded in an assumption trace shared by reference.
- **Pack-relative results.** An exact calculation relative to a rule pack is distinct from claiming the pack describes the world.

### Mechanics (approved style)

- **Spelling.** The namespace is the boolean metatag `$time`: a bare member enables its obligation, and `=false` disables it.
- **Bundles.** `$time.strict` enables all 17. `$bulletproof` includes `$time.strict`, alongside the allocation, bounds, finite-float, hidden-cost and deadlock requirements.
- **Scoping:**
  - More local explicit settings override inherited ones, under ordinary metatag rules.
  - Tags apply to the next declaration, block or expression.
- **Propagation.** Obligations propagate through wrappers and generic instantiation using the existing type, effect and fact machinery, with no whole-program time pass.

### The 17 obligations

| # | `$time.` member | Convenience it removes → what it then requires |
|---|---|---|
| 1 | `require_context` | Entry snapshot of host clock, zone, locale, calendar, location, route and pack selection → an explicit argument or immutable lexical capture of known identity. Task migration can't substitute a handle. |
| 2 | `require_calendar` | Generic proleptic Gregorian, astronomical numbering, default day/week conventions and inherited era interpretation → explicit calendar, numbering and boundary choice. Historical use also needs #9; an arithmetic calendar proves no local adoption. |
| 3 | `require_bounds` | Half-open interval defaults → explicit bounds or a type contract. No default epsilon, and no implicit date↔physical-span conversion. |
| 4 | `require_profile` | Inherited parser, recurrence, overflow, rounding, execution and protocol policies → a named profile or a statically fixed policy. This exposes RFC gap behavior, two-digit-year windows, nominal vs emitted counting, midnight/deadline meaning, timer rounding and late-run handling. It proves which convention is used, not what the author intended. |
| 5 | `require_clock_domain` | Default suspend-inclusive provider, platform monotonicity, VM continuity and generation lifetime → provider capabilities and continuity checks. Active, CPU and simulated time must be distinguished. |
| 6 | `require_clock_accuracy` | Treating a nominal reading, drift model or sync status as adequate → acquisition, transfer and calibration evidence that meets the requested bound and validity interval. Unknown accuracy stays usable as unknown, never as zero error. |
| 7 | `require_clock_trust` | Accepting a source for security decisions → the application's trust policy and threat assumptions. Signed packets alone don't prove correctness, freshness, bounded delay or absence of rollback. |
| 8 | `require_realization` | Projecting TAI, UTC(k), TT(BIPM) and so on onto ideal coordinates → an uncertainty-bearing correlation or a declared nominal-interpretation result. A bare nominal projection cannot discharge an exact physical-event obligation. |
| 9 | `require_history` | Accepting published zone, calendar or legal history as actual practice → explicit authority and source criteria, plus jurisdiction and observance evidence; otherwise assertions or alternatives are returned. Pinned bytes give reproducibility, not truth. |
| 10 | `require_future_rules` | Assuming current laws, holidays, announced calendars and UTC regimes continue → effective coverage and a stated authority or scenario contract. No pack proves future rules won't change. Unpublished observations stay pending. |
| 11 | `require_location` | A default geocentre, reference meridian, stationary site, horizon or illuminating body → explicit location and frame assumptions plus an error budget. A downloaded ephemeris discharges none of these. |
| 12 | `require_model` | A convenient approximation, interpolation, omitted correction, route or numerical tolerance → a model and error contract with compatible dynamical parameters. Convergence is not an accuracy certificate. |
| 13 | `require_extrapolation` | Extending ephemerides, correlations, Earth orientation, calendar predictions or rotation models beyond certified coverage → an explicitly warranted extension model. "Allow extrapolation" cannot turn a forecast into proved accuracy. |
| 14 | `require_dependence` | Assumed independence, covariance or shared-error identification → a joint model with evidence or premises. No library default applies root-sum-square; sound deterministic enclosures stay available. |
| 15 | `require_loss` | Nominal display, support hulls, quantization, floating-point export, and omitting evidence or intent → a declared acceptance contract plus a loss report. A requirement of exact fidelity rejects the operation. |
| 16 | `require_protocol` | Distributed leases, clock-based expiry, delivery guarantees and restored deadlines → drift, network, failure and recovery assumptions plus protocol evidence. Timestamp order alone proves neither causality nor exclusion. |
| 17 | `require_resources` | Default loading, storage growth, search, numeric work and provider availability → exposed bounds, fallibility and cancellation under the strict resource rules. A pinned context doesn't mean its bytes are loaded or that an authority will reply. |

### Scope of strictness

- **Closed inventory.** This list closes the inventory for this design. Any new convenience must name its category or add a new obligation included in the bundle.
- **Always enforced.** Inherent ambiguity, domain and validity failures are enforced by explicit operations regardless of metatags.
- **Runtime evidence is allowed.** Strictness can require evidence at runtime and return an unresolved value. It doesn't require every future observation at compile time.
- **What "proof" means:**
  - It is a checked software implication under stated premises.
  - Empirical models, institutional authority and hardware provide evidence with assumptions, not compiler proofs about nature.
  - A conditional scenario gives a conditional result, which can't be passed where an unconditional guarantee is required.
  - The provenance type prevents laundering a premise through a convenience wrapper.

```dewy
$time.require_context
$time.strict

wait_for = (delay:Duration<(>=? 0s)> context) =>
    time.with_context(context () => sleep(delay))

$time.require_loss=false
report = (reading context) => {
    printl(reading.display(profile='nominal' context=context) or_throw)
}
```

- **Explicit nominal display** accepts display loss only. It doesn't certify clock accuracy or trust.
- **Under `require_clock_accuracy`,** nominal arithmetic must be named as nominal or justified against a requested error bound. Keeping an unknown estimate is always allowed.
- **Under `require_realization`,** the projection must be the named nominal one or an uncertainty-bearing correlation, including inside `parse_instant`.
- **Pure label arithmetic.** No single member demands unrelated scientific data for it.
- **What the refined delay proves.** A refined non-negative `delay` discharges one local obligation. It doesn't prove the clock is available, wakeups are timely, cleanup terminates or allocation succeeds.
- **Error forwarding:**
  - `or_throw` is explicit forwarding under Dewy's error conventions.
  - `??<Canceled>` handles cancellation without swallowing unrelated errors.
- **No-traps.** It still means proof or visible failure handling, never an undocumented environmental exception.

---

## 13. Capability acceptance and delivery

> **BLUF:**
> - **No early advertising.** Every layer preserves domain, evidence, uncertainty and intent before every model exists. Only implemented operations are advertised.
> - **Pinned fixtures.** Fixtures pin definitions and editions. Oracle disagreements are diagnosed as convention, coverage or implementation differences.
> - **Test checklist.** The acceptance checklist is below, by layer.

**Core, uncertainty and clocks**
- `1ns/3`, enormous signed offsets, floor splitting, exact epoch changes, checked finite-ABI rounding, affine rejection, domain mismatch.
- Equivalent encodings vs record identity vs physical accuracy.
- Shared calibration cancellation, `X−X=0`, unknown or disconnected support, covariance requirements, inconsistent evidence.
- Allen relations, point and empty variants, unknown vs unbounded ends, half-open intervals that meet but are disjoint.
- Injected unavailable or unsynchronized clocks, rollback, suspend, VM migration, drift and reboot.
- Virtual clocks drive deadline races without real waiting. A stopwatch-only fresh build reaches no unrelated layer.
- The trivial program's exact return and print contracts, entry failure, stale holdover, date-boundary ambiguity and async capture.
- All 17 strict members, individually and bundled.
- Tick fixtures: decimal, binary and caesium grids; non-divisible conversions; negative remainders; epoch-induced denominator changes; finite-width overflow.
- Every codec round-trips its represented payloads. Unresolved eras, partitions, leap phase and model-dependent conversions stay unresolved or estimated.

**Civil time and recurrence**
- An independent check of the frozen Apollo derivation against the historical coefficients and SOFA vectors.
- Round-trip all three labels around the 2016 leap. Reject an invented second 60, and test synthetic negative leaps.
- Historical UTC vs explicit proleptic conventions.
- Before, at and after the continuous-UTC boundary, with current and stale packs and alternate inherited offsets.
- POSIX and smear codecs preserve phase/profile or report loss.
- The same tzdb release and profile with zic/zdump, plus synthetic second-level offsets, midnight shifts, whole-date skips/repeats and more than two inverses.
- Calendar-day vs `24hour` arithmetic, the British reform, the Swedish insertion, leap months, days outside cycles, era boundaries and no-year-zero views.
- Sunset absence and publication-wait composition.
- Repeated clamping vs anchored month-end recurrence.
- RFC explicit vs generated gap differences, COUNT/UNTIL, stable override IDs and timezone-definition preservation.
- Impossible or sparse recurrences distinguish exhaustion, absence, missing law and pending publication.
- Machine round-trips keep semantics; human display reports its declared losses.

**Institutions and records**
- Named fixtures for sessions, closures, fiscal rules, legal deadlines, and credited vs elapsed work.
- Late events and retroactive corrections, queried on both the valid and knowledge axes, without modifying earlier assertions.
- Equal physical timestamps keep vector concurrency. HLC counters never become physical precision.
- Lease and expiry refusal when clock or protocol assumptions are missing.
- Database adapters against their stated backend and session contracts.
- Appointment migration with already-armed work.

**Science and flight**
- Exact TT↔TCG and TCB↔TDB, including inverse divisors and origin signs.
- Position-dependent TCG↔TCB with insufficient or missing ephemerides, accuracy refusal and realization revisions.
- Proper elapsed time on distinct worldlines.
- Moving-endpoint asymmetric signal paths with turnaround and separately validated gravitational and media corrections. Reception, occurrence and execution windows are distinguished.
- Re-correlating partitioned SCLK while keeping ticks and old reconstructions.
- Mars24 reference cases; reject Earth-hour substitution; require declared Darian conventions.
- TCL keeps its context and uncertainty; an unavailable operational LTC stays unavailable.

**Extension and cost**
- A colony calendar, disconnected authority updates, and a spacelike pair whose coordinate order reverses while its causal classification is kept.
- Refuse an unqualified universal now and outside-domain extrapolation.
- Fresh-compile and instruction-count profiling on the flagship panel. Demand-driven indexed providers never pull bulk data into unused programs.
- Honest charging for candidate search, big arithmetic and numerical iteration. Fuzz malformed data and adversarial resource limits.
- Compiler and library changes go through the focused/quick gates and the full/bootstrap/fixed-point batch gates, with at most 4 workers.

---

## 14. Open decisions

> **BLUF:**
> - **10 decisions need approval.** The `$time.*` namespace style is already approved and isn't reopened.
> - **Names vs meanings.** Names are reversible; persisted meanings are not.

| # | Decision | Recommendation | Reversibility |
|---|---|---|---|
| 1 | Epoch | Apollo (ideal TT `1969-07-20T20:18:19.7585938 TT`) | Cheap before publication, costly after |
| 2 | Core rate | Ideal TT-rate axis | Changing it after persistence is a semantic migration |
| 3 | Relative waits | Suspend-inclusive monotonic | Reversible before use, behavior-changing later |
| 4 | Intervals | Half-open convenience plus stored flags | Convenience reversible; changing stored bounds is not |
| 5 | Generic dates | Proleptic Gregorian, year zero | Source default reversible; persisted conventions must survive |
| 6 | Intent | Separate appointment/occurrence/event/observation | Additive; discarded intent can't be rebuilt |
| 7 | Strictness names | 17 `$time.require_*`, `$time.strict`, in `$bulletproof` | Names reversible; the inventory is a contract |
| 8 | Ticks | Integer counts of rational ticks; `Instant<tick=…>` | Spelling/layout reversible; never round silently |
| 9 | Default context | One entry capture, total reads, nominal subtraction | Surface reversible; semantics need approval before release |
| 10 | Names | Ordinary library names, no keywords | Names individually revisable |

### 1. Epoch
- **Recommend:** Apollo, David's preference. Freeze the exact ideal TT label and `e` (§1) after independent vector validation.
- **Alternatives:** the 1977 standards origin (`e=0`), or an explicitly TT-labelled Unix-calendar zero. None of them implies POSIX arithmetic.
- **Unblocks:** wire identity.
- **Note:** Jai compatibility needs a separately verified adapter.

### 2. Core rate
- **Recommend:** the ideal TT-rate axis, which David is leaning toward, with `TAICompatible` nominal labels and first-class realized domains. An improved realization changes event estimates, never the axis.
- **Unblocks:** scientific interoperability.
- **Independent** of the epoch choice.

### 3. Suspend-inclusive waits
- **Recommend:** the default for relative sleep, timeout, TTL and deadline operations. Active, CPU and simulation clocks stay explicit.
- **Failures:** unsupported capabilities are entry or acquisition failures. Expiry does not promise to wake the device from suspension.
- **Unblocks:** portable waits.

### 4. Half-open intervals
- **Recommend:** half-open convenience constructors, explicit stored flags, and the topology, Allen and degenerate-case contracts in §3.
- **Unblocks:** range APIs.

### 5. Generic dates
- **Recommend:** proleptic Gregorian with astronomical signed years including zero, and explicit calendar and day-boundary opt-outs. Historical adoption stays an evidence question.
- **Unblocks:** short date arithmetic.

### 6. First-class intent
- **Recommend:** separate appointment, occurrence, event and observation records, stable nominal occurrence keys, and explicit migration.
- **Unblocks:** resilient schedules.

### 7. Strictness names
- **Already approved:** the `$time.*` style, with bare true or `=false`.
- **Recommend:** the 17 `$time.require_*` names (§12), `$time.strict` for all of them, and inclusion in `$bulletproof`.
- **Unblocks:** independently checked convenience obligations.
- **Reversibility:** member names are reversible; the obligation inventory and its propagation are semantic contracts.

### 8. Tick-generic representation
- **Recommend:** exact rational meaning, implemented as integer counts of rational ticks. Proposed spellings are `Instant<tick=1ns>` plus binary and caesium ticks; plain `Instant` keeps its own denominator.
- **Also approve:** the `ticks` quotient/remainder and the explicit `quantize` loss contract.
- **Unblocks:** zero-loss codecs and efficient specialized storage.

### 9. Default context and trivial calls
- **Recommend:**
  - one capture at entry, with capabilities acquired at entry;
  - total, status-bearing wall reads;
  - ordinary subtraction giving a nominal `Duration`;
  - printable date uncertainty;
  - retained evidence, with strict opt-outs.
- **Kept distinct:** a wall target and a monotonic deadline.
- **Unblocks:** the trivial tier, without pretending clocks are exact.
- **Approval needed:** nominal-vs-measured arithmetic and task failure propagation need explicit semantic approval before release.

### 10. Public-name inventory
- **Recommend:** ordinary library names and no new keywords. The **Semantics** lines mark decisions that go beyond spelling; every other name can be revised independently.
- **Core, evidence and codecs:**
  - `TimePoint`, `Instant`, `Duration`, `CoordinateTime`, `TAICompatible`, `Estimate`, `WallTime`, `Interval`, `IntervalSet`;
  - `ticks`, `quantize`, `convert`, `compare_estimates`, `certainly_before`, `possibly_before`, `same_set`, `parse_instant`.
  - *Semantics:* tick exactness, domain branding, realized vs nominal projection, dependence, comparison and degenerate relations.
- **Civil and intent:**
  - `Date`, `TimeOfDay`, `LocalDateTime`, `Offset`, `Zone`, `ZonedDateTime`, `Period`, `Calendar`, `DayBoundary`, `MonthDay`, `YearMonth`, `Appointment`, `Occurrence`, `Event`, `Observation`;
  - `date`, `local`, `zoned`, `resolve`, `choose`, `add`, `age`, `recurrence`, `expand`, `plan`, `as_of`.
  - *Semantics:* repair, overflow and anniversary policies; count basis; the RFC profile; stable identity and migration.
- **Clocks and science:**
  - `TemporalContext`, `ClockReading`, `MonoPoint`, `Worldline`, `ProperClock`, `SignalPath`, `Sclk`;
  - `with_context`, `with_clocks`, `now`, `today`, `elapsed`, `monotonic`, `active`, `correlate`, `proper_elapsed`, `causal_relation`.
  - *Semantics:* entry and async capture, status and holdover, nominal arithmetic and display, cancellation, suspension and model requirements.
- **Result families:**
  - `Gap`, `Ambiguous`, `AmbiguousToday`, `UnknownToday`, `Unknown`, `Unspecified`, `MissingContext`, `MissingData`, `OutsideCoverage`, `InvalidDate`, `InvalidFields`, `DomainMismatch`, `InconsistentEvidence`, `Indeterminate`, `Incomparable`;
  - plus the clock, loss, search/publication and model failures defined above.
  - *Semantics:* impossible vs unresolved, comparison variants and selective handling. Names can consolidate without collapsing meanings.
- **Policy labels:**
  - Labels such as `earlier`, `later`, `all`, `preserve_displacement`, `clamp`, `march_1`, `require_authority`, `emitted`, `keep_local` and `nearest_even` are public surface.
  - They serialize by versioned meaning.
- **Reused machinery:** juxtaposed units, affine rules, unique `as`, `??`, `??<E>`, `or_throw`, `sleep`, `within` and metatags. Parenthesized refinements, calls, partial applications and container unpacking keep their established syntax.
