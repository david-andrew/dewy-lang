# Time, dates, clocks and calendars

Dewy provides exact temporal arithmetic, dependable civil scheduling, and explicit physical models through one composable library. Ordinary tasks require ordinary quantities and a captured context. Additional precision, historical evidence, institutional rules, or relativistic modeling adds the information that the task actually needs. Missing knowledge remains representable.

The design covers scalar coordinates, uncertainty, calendars, clocks, recurrence, interchange, institutions, distributed records, and scientific time across and beyond the solar system. It does not predict legislation, turn measurements into mathematical facts, or declare proposed planetary calendars official. The acceptance contracts are in §13. Public spellings and the eight semantic choices in §14 remain **OPEN DECISIONS**; the preceding sections specify one internally consistent recommended design, conditional on those choices. No new literal syntax or language-wide Boolean semantics is required.

## 1. The coordinate core

### Definition, realization, epoch and representation

A scale defines a coordinate and its rate convention. A realization estimates that scale using physical clocks and observations. An epoch chooses zero. A representation encodes the coordinate. A format presents it. These are independent: a TAI label can be a scalar, TT can be written as calendar fields, and a Julian date is a representation that still needs a scale.

`TimePoint<Domain>` is an affine point. `Instant` is its ordinary terrestrial specialization on an **ideal TT-rate axis**, with signed exact-rational seconds from a frozen epoch. The axis does not change when metrologists improve a realization. It is a mathematical convention, not the proper time of every observer or a universal physical simultaneity.

Use these exact defining constants and coordinates:

- `L_G = 6.969290134e-10` and `L_B = 1.550519768e-8`, dimensionless rationals.
- `TDB0 = -6.55e-5s` and the conventional TAI-to-TT(TAI) offset `32.184s`.
- `J0 = 2443144.5003725`, the common nominal 1977 reference Julian-date number; its TT label is `1977-01-01T00:00:32.184 TT`.
- For each named scale S, `x_S = (JD_S − J0) × 86400s`. Each JD argument belongs to that scale; equal numbers in different scales do not automatically identify the same remote event.

The invariant for a core payload `q` and chosen epoch offset `e` is

```
q × 1s = x_TT − e
x_TT = (1 − L_G) × x_TCG
x_TDB = (1 − L_B) × x_TCB + TDB0
```

Thus `x_TCG = (q × 1s + e)/(1−L_G)`, and `x_TCB = (x_TDB−TDB0)/(1−L_B)`. Changing zero changes `e`, never the rate. The TT/TCG origin coincidence follows the standards convention; the TCB expression uses its own barycentric coordinate argument. Neither equation supplies the missing geocentric-to-barycentric spacetime transformation. These are exact affine definitions, including their inverse divisors. [SOFA TT/TCG definition](https://raw.githubusercontent.com/Starlink/sofa/master/src/tcgtt.c), [SOFA TCB/TDB definition](https://raw.githubusercontent.com/Starlink/sofa/master/src/tcbtdb.c).

The recommended Apollo zero freezes the **ideal TT coordinate** `1969-07-20T20:18:19.7585938 TT`, giving `e = (−1175538662127031/5000000) × 1s` relative to J0. Its nominal TAI-compatible label is `1969-07-20T20:17:47.5745938`. All calendar labels defining these origins use proleptic Gregorian fields. Those decimal digits define a convention, not the accuracy of the lunar touchdown observation. The historical motivation is the UTC label `1969-07-20T20:17:40`, whose old rate rule gives `TAI−UTC = 7.5745938s`. Zero has no runtime dependency on that table. A standards-origin alternative sets `e=0`; a Unix-calendar alternative freezes `1970-01-01T00:00:00 TT`. They differ only by exact offsets. The Apollo constant requires an independent standards-vector check before its wire identity is published. [Historical UTC coefficients](https://maia.usno.navy.mil/ser7/tai-utc.dat).

Define the nominal TAI-compatible label of an ideal TT coordinate as its calendar-number offset by `−32.184s`. Call this view `TAICompatible`, never a claim to published realized TAI. An actual TAI record instead has realization identity; `TT(TAI)=TAI+32.184s` is an exact relabeling **within that realization**. Its mapping to ideal TT is an estimate. TT(BIPM edition), UTC(k), provisional products, and clock correlations likewise retain their realization identity. New calibration produces a new event estimate, never a changed `q` or rewritten raw reading.

Exact civil label arithmetic can stay entirely in a realized domain: two declared TAI labels have an exact coordinate difference even though their associated physical events are imperfectly known. A nominal projection onto `Instant` is explicitly named and retains its assumption in the containing record. It is not `as`, and does not prove the event occurred there. Ordinary parsing returns a label or resolution record before any such projection.

### Arithmetic and range

Points subtract to domain-branded differences; points add compatible differences. Point addition to another point, point scaling, and implicit cross-domain subtraction are invalid. An affine average is available with weights summing to one. Scientific fixed intervals such as a Julian year use separately named definitions; they do not turn calendar `year` into a duration. Bare `5s`, `300ms`, `1hour`, and `1ns/3` are exact magnitudes interpreted by the receiving domain; a measured TCB or proper-time difference does not lose its domain merely because it has the same unit dimension.

The scalar has no fixed minimum tick or date range. Arbitrary rationals represent finite values, not all real numbers, infinity, or unlimited computation. Compact integers, fixed ticks, and split seconds are optimizations when equivalent; explicit narrowing or rounding returns range/loss information. Negative splitting uses floor and a nonnegative remainder: `−0.25s = −1s + 0.75s`. Zero and negative values are ordinary coordinates, never missing-value sentinels. Allocation and numeric work remain subject to Dewy's resource contracts.

`as` is reserved for unique, exact, applicable conversions: units, frozen epochs, and definitionally related coordinate scales. Approximate models, context selection, civil inverses, rounding, or interpretation of measured events use named operations returning values. Domain equality may be static or checked at runtime; unrelated devices, boots, observers and frames do not become compatible through casts.

## 2. Answers, estimates and evidence

A relation returns one answer, a finite or lazy candidate collection, a proved empty mapping, or an unresolved result. `Gap` is an established missing civil span; `Ambiguous` carries all known alternatives and their explanations. `MissingContext`, `MissingData`, `OutsideCoverage`, `Unknown`, `UnsupportedModel`, and `InconsistentEvidence` are different outcomes. An absent provider never becomes an empty candidate set. `Unspecified` means deliberately omitted information; `Unknown` means information sought but not known.

`Estimate<T>` denotes a variable with a set of admissible values under identified assumptions. It contains a stable variable/expression identity, domain, support or constraints, evidence references, and optional nominal representative. A representative is not required: two competing historical interpretations need not have a privileged midpoint. Support can be a singleton, disconnected set, interval set, constrained symbolic object, or unknown. A distribution and confidence claim are optional additional structures; a 95% interval is not a guaranteed support bound.

Measurement, quantization, numerical error, model discrepancy, future-rule scenarios, and source disagreement remain separately identified. A field's display precision does not establish its accuracy. `YearMonth` is a partial calendar label, not a uniformly distributed instant. Turning rounded text into a quantization cell requires its rounding rule and civil context.

### Dependence and arithmetic

Operations map the **joint** admissible assignments, not just independent marginal ranges. Translation `X+d` translates every possible value. Subtraction evaluates `Y−X` on the same joint assignment. Copies preserve variable identity; another observation with identical bytes is independent only if its evidence establishes that fact.

Consequently `X−X` is exactly zero, including when X has unknown support. If `X=10s+E`, `Y=13s+E`, and `E` is the same uncertain calibration offset bounded by `[0s,2s]`, then `Y−X=3s`. With only marginal bounds `[10s,12s]` and `[13s,15s]`, conservative subtraction instead encloses `[1s,5s]`. It must not infer shared error from equal textual identifiers supplied by an untrusted producer.

For probabilistic models, `Var(Y−X)=Var(Y)+Var(X)−2Cov(X,Y)`. Root-sum-square requires a justified zero-covariance model; independence is a sufficient stronger condition. No operation silently assumes independence. A caller may explicitly supply that statistical assumption, and the result retains it. Deterministic arithmetic never requires probability.

An implementation can retain expression nodes and shared error symbols, use exact finite sets, or compute certified enclosures. Its budget may limit precision, not soundness. If it forgets dependence, it reports a conservative enclosure; it preserves direct same-variable cancellation. A convex hull is an explicitly lossy enclosure of disconnected possibilities. If neither exact propagation nor a sound enclosure is available, return `UncertaintyUnsupported`. Contradictory evidence yields inconsistency, not an empty successful estimate. Conditioning or adding evidence creates a new value and preserves the earlier evidence graph.

### Equality and ordering

Exact coordinates have Boolean equality/order within a compatible domain; normalized equivalent rationals hash identically. Record equality additionally respects semantic fields and definition identities. Event identity, recurrence identity, original spelling and observational identity have separate operations. None is inferred merely from equal time coordinates.

`compare_estimates(X Y)` quantifies over a nonempty joint admissible set. `Before` means `X<Y` for every admissible assignment; `After` similarly means `X>Y`; `Same` means `X=Y` for every assignment. Shared-variable identity or two equal exact singletons can establish `Same`; equal nominal values, overlapping ranges, or equal distributions cannot. Otherwise the result is `Indeterminate` with the possible order relations. Unknown domains produce `Incomparable`, and inconsistent evidence is reported before comparison. `Same` establishes coordinate equality under evidence, not event or record identity.

`certainly_before` and `possibly_before` are derived quantifier queries. A proof-limited engine may conservatively return unknown with a reason, never a false certainty. Approximate tolerance equality is not a hash equivalence. Causal comparison is separate: vector-clock `Concurrent` and relativistic `Spacelike` do not belong to the scalar comparison enum. Dewy `if` continues to require an ordinary Boolean.

## 3. Intervals and topology

An interval records its domain, lower/upper bound and finite-end inclusion flags. Bounds are finite coordinates, known unbounded ends, or unknown endpoints with constraints. Unknown is not infinity: “until further notice” can have an unknown end without asserting that the activity never ends. Empty sets and closed singleton intervals are explicit. A constructor validates compatible domains and endpoint order; unresolved order produces a constrained interval value or an unresolved result, never an assumed valid interval.

The recommended convenience constructor is half-open `[a,b)`. Explicit open/closed constructors always exist. On the dense rational axis there is no next instant; converting a closed end to a half-open end by adding a nanosecond is invalid. A discrete calendar-day interval may instead use its calendar's proved successor. Infinite endpoints cannot be members. Equal finite endpoints produce a singleton only when both ends are closed; otherwise the set is empty.

Set union, intersection, difference, complement relative to a named universe, membership, containment and disjointness respect flags. Canonical interval sets merge pieces only when their union introduces no missing point. The empty set intersects nothing and is contained in every set. The measure of a finite interval is `b−a` independent of finite endpoint inclusion; a singleton has zero measure. Unbounded extent has infinite measure, represented outside finite `Duration`; an unknown endpoint yields an estimate or unknown measure. Calendar span length is not physical elapsed time.

For nondegenerate intervals A=(a,b), B=(c,d), with `a<b` and `c<d`, endpoint order defines Allen's thirteen relations:

- **before:** `b<c`; **meets:** `b=c`; **overlaps:** `a<c<b<d`.
- **starts:** `a=c` and `b<d`; **during:** `c<a` and `b<d`; **finishes:** `c<a` and `b=d`.
- **equals:** `a=c` and `b=d`.
- **after**, **met_by**, **overlapped_by**, **started_by**, **contains**, **finished_by** are respectively the inverses of the first six.

This classifies endpoint geometry, independent of finite-end inclusion. `equals` here means equal endpoints; `same_set` also compares topology. Thus `[a,b)` meets `[b,c)` but is disjoint from it; `[a,b]` and `[b,c]` meet and intersect at b. Nondegenerate intervals with known infinite ends use the extended endpoint order; infinity is never a fictitious meeting event.

Degeneracies do not receive arbitrarily chosen Allen labels. Empty inputs return `EmptyOperand`, with their set predicates still defined. Point-versus-point returns before/equal/after. Point-versus-proper-interval returns before/start/interior/end/after according to the coordinate, plus membership from the endpoint flags; the inverse query swaps operands. This tagged relation family is exhaustive for known sets and avoids collapsing singleton cases into several incompatible Allen labels.

Unknown or uncertain endpoints produce the set of possible tagged relations over admissible joint assignments, with associated possible/certain set predicates. Constraints such as “end after Tuesday” narrow that set; unknown does not automatically mean every relation. A certain relation is one proved for all assignments. Search limitations return a sound superset marked as an enclosure. Relation composition uses the standard Allen composition rules on proper intervals; topology and degeneracies retain their separate constraints rather than borrowing an invalid inference. Constraint inconsistency remains an error value.

## 4. Scale transformations and UTC

A transformation declares source/target domains, required event position, definition/model edition, data dependencies, applicable region, accuracy contract and algorithm. Composition retains all of these. Competing routes are not silently selected by graph search; a context names its preferred route, or the operation returns alternatives. Exact definitions require no ephemeris; their application to measured events still propagates measurement uncertainty.

TT↔TCG and TCB↔TDB are the exact affine maps in §1. TAI↔TT(TAI) is an exact offset within a realized convention. TCG↔TCB transforms spacetime events using location, Earth trajectory, external gravitational potentials and a specified relativistic approximation. TT↔TDB normally composes those operations; a geocentre approximation must identify its assumed location and error envelope. A general scalar alone cannot determine it. Proper-time conversion integrates a worldline and metric. UT1 needs measured or predicted Earth orientation; SCLK needs mission clock correlation. Missing models, insufficient accuracy and expired coverage are explicit values.

UTC is a versioned relation to realized atomic labels. Its regimes include historical fractional offsets and rate adjustments, integer leap steps from 1972, and the continuous regime. Historical UTC before its supported definitions returns outside coverage unless an explicit proleptic convention is selected. Pre-1972 mapping uses its dated rate formula, not a modern integer offset.

The current rule pack implements continuous UTC effective **20 May 2027**, with the inherited boundary offset supplied by authoritative transition records. The adopted bound on `|UT1−UTC|` is `3600s`; it does not specify a future leap-hour mechanism. The library represents this as a new effective segment, not a year test or an eternal hardcoded `37s`. Later standards changes can add segments without changing stored old labels. [CGPM Resolution 5 (2026)](https://www.bipm.org/en/cgpm-2026/resolution-5).

Positive leaps validate the actual inserted label, including `23:59:60`. Negative leaps remove a label; synthetic histories exercise that path without claiming such a leap occurred. A standalone time-of-day may retain an unresolved leap marker, but needs a date and regime for validation. The coordinate difference from `2016-12-31T23:59:59 UTC` to the following midnight is `2s` in the declared atomic realization. Associating the labels with actual observations adds their realization errors.

UTC-to-local conversion accommodates second-level historical zone offsets and carries a leap marker where ordinary fields are insufficient. A codec unable to express the result returns `Unrepresentable`. Leap-aware Earth-orientation interpolation uses a continuous argument and treats the discontinuity in UT1−UTC explicitly. An expired announcement does not invalidate a previously established historical leap, but an old pack cannot certify new future policy.

POSIX counts and FILETIME-style conventions are adapters, never the core. A collapsed/repeated second can have multiple inverses; a raw OS reading needs its leap behavior. Smears are distinct time-warp profiles with window, formula, implementation version, inverse multiplicity and error contract. Unknown smear behavior cannot resolve uniquely. A provider that rounds or drops the leap must return loss information or retain extra phase metadata.

JD and MJD need scale tags; MJD subtracts `2400000.5` from JD and changes the numeric day boundary convention. J2000 denotes `JD 2451545.0 TT` when used as this exact epoch, not automatically TDB or a frame. GNSS systems have distinct epochs, offsets, realizations and truncated-era rules. Era resolution needs external evidence; rollover counters never select the current era silently. Navigation adapters also retain broadcast ephemeris, satellite-clock and relativistic-correction conventions; applying a correction twice or omitting it cannot be hidden by a generic GNSS timestamp type.

## 5. Civil calendars, zones and arithmetic

`Date<Calendar>`, `TimeOfDay`, `LocalDateTime`, fixed `Offset`, rule-based `Zone`, and resolved `ZonedDateTime` are separate types. A date contains no hidden birth hour; a time contains no hidden date or zone. A resolved civil record retains its coordinate or estimate, original intent, calendar, zone, provider editions and resolution trace.

The recommended generic `Date` convention is proleptic Gregorian with astronomical signed years, including year zero. Era-based no-year-zero views map explicitly; choosing proleptic arithmetic does not assert historical local adoption. Defaults are identifiable and individually disableable (§12).

### Calendar and day-boundary protocols

A calendar specifies structured field identities, validation, ordered day possibilities, label↔ordinal relations, month sequences, era/year mapping and optional cycle membership. These relations may be multivalued, pending publication, or supported only within an evidence horizon. An observational calendar does not promise a total bijection. Arithmetic Gregorian/Julian calendars can provide stronger total contracts.

There need not be twelve months, fixed month names, seven weekdays, or a weekday for every date. Leap months have distinct identities even when names/numbers repeat. Month/year lengths vary; days can fall outside a week or month cycle. Chinese and Hebrew leap months, Islamic observation/calculation variants, Persian equinox variants, Japanese eras, and Ethiopian/Coptic and Buddhist conventions are separately named implementations. Religious and civil uses can select different authorities. Midyear era transitions and unpublished future era names are supported without inventing labels.

`DayBoundary` connects a calendar day to physical events. Midnight in a zone, local sunset, a chosen body's solar phase, or a published operational schedule are providers. They require the applicable location, model and authority. Calendar-day identity can be converted between calendars without claiming an exact physical instant. A day boundary may be absent or ambiguous; a day realizes to an interval set or unresolved support. No API assumes every date has a unique midnight. Unequal seasonal hours subdivide the chosen daylight/night boundary intervals under a named historical convention; their lengths require the location and solar model and are not fixed `hour` quantities.

Historical calendars compose reforms, legal year-start changes, interrupted reforms, exceptional insertions, erroneous early leap practice and delayed local adoption. British 1752's chronological next day after September 2 is September 14 in the named jurisdictional calendar; Swedish `1712-02-30` is valid only in its historical sequence. A historical gazetteer resolves changing place names and jurisdiction boundaries. Original transcription, calendar/year style, place, authority and competing evidence are preserved. Old Style can concern both calendar and year numbering; double dating asserts related interpretations that must be checked. Lost conventions, contradictory records and approximate eras remain unresolved or constrained values.

### Zones and geography

A zone is an identity plus a versioned transition relation. Exact offsets permit fractional hours and seconds. Neither current offset equality nor matching present rules establishes zone identity: histories can diverge or converge. Aliases and renamed IDs preserve the original key and versioned canonical mapping. An abbreviation such as CST is a candidate-producing parse, not a unique zone.

Transitions have arbitrary size, local hour, weekday and count per year. The same machinery handles no DST, hemisphere differences, temporary suspensions, negative saving, permanent rule segments and nonseasonal corrections. DST annotations are metadata, not the resolver. Whole dates can disappear or repeat; synthetic histories may yield more than two candidates. Missing labels return their transition span and valid neighboring boundaries.

Geographic lookup is a separate time-indexed spatial relation. Countries contain multiple zones, zones cross borders, overseas jurisdictions differ, borders move, and ocean/disputed locations can require a convention. Locale never supplies location. Legal rules and observed practice are separate assertions. Travelers use an itinerary; ships and aircraft may use an operational clock independent of geography. Crossing the date line changes local labels without supplying elapsed days. Several observers can legitimately display different civil dates for the same chosen coordinate.

Ordinary native resolution does not guess folds or repair gaps. A named policy can choose earliest/latest/all candidates, reject, skip, preserve displacement through a gap, or move to the next valid boundary. The last two differ: a missing 02:30 in a one-hour gap can become 03:30 or 03:00. `choose` accepts the entire resolution union as a free function, preventing exception-forwarding method calls from bypassing ambiguity handling. Policy traces remain in resolved records.

### Calendar operations

`Period` is an ordered recipe of calendar steps, not a vector of seconds. `month` and `year` combine only with real calendar context. Calendar-day addition differs from `24hour`, especially across reforms, date-line changes, clock shifts and leaps. `Instant + Period` requires an explicit civil projection and resolution route. Date subtraction counts calendar successors or declared ordinal differences, not elapsed seconds.

Overflow policy is explicit: rejection, clamping, skipping, or another named contract. Leap-day year addition and fractional calendar units likewise require interpretation. Successive clamps from January 31 can differ from anchor-derived “last day of each month”; preserving month-end is its own anchor rule. Period composition preserves order, need not commute and is not generally invertible. Calendar differences require a decomposition convention. Scalar rounding, calendar-boundary rounding and local-clock rounding name ties and gap/fold handling separately.

Birthdays, legal age thresholds and anniversaries are date rules, not elapsed seconds divided by a year. `MonthDay`, `YearMonth`, masked dates and approximate historical descriptions retain deliberately absent fields. All-day events are date spans plus intent. Projecting a skipped civil date can yield empty support; that differs from an unknown calendar announcement.

```dewy
let ny = app.zone("America/New_York") or_throw
let local = time.local("2026-11-01T01:30:00") or_throw
let meeting = time.choose(local.resolve(zone=ny context=app) fold='later') or_throw
let jan = time.date("2027-01-31") or_throw
let feb = jan.add(1month overflow='clamp') or_throw
let [instant as meeting_time] = meeting
```

Here `meeting_time` is the resolved coordinate/estimate carried by the record, not a statement of physical certainty. A policy-free invalid calendar addition returns `InvalidDate`. These functions use established Dewy calls, quantities and field renaming; the library names are proposed.

## 6. Intent, recurrence and scheduling

An `Appointment` preserves what should stay fixed: a coordinate, local fields in a named zone, floating fields bound to a travel context, or a physical/astronomical condition. An `Occurrence` records a particular resolution with its evidence and policies. An `Event` records what happened; an `Observation` records a measurement or reception. Resolving intent never destroys it.

A recurrence generates nominal occurrence keys, calendar candidates, then resolutions. It retains its anchor, calendar, zone/location behavior, rule profile, invalid-day/gap/fold choices, inclusions, exclusions, overrides, termination basis and data-update policy. The key combines series identity with the original recurrence coordinate; rescheduling changes the occurrence's realization, not its key. Multiple fold emissions add branch identities. Era display changes do not alone create new series identities.

Selectors include daily/weekly rules, nth or last weekday, end-of-month, leap anniversaries, alternate-calendar dates, solar events and institutional sessions. Rule unions/intersections/exceptions have defined precedence and duplicate suppression. Participants in different zones share an intent and project it independently; preserving one participant's local hour does not preserve every participant's hour. Floating travel alarms resolve against the declared itinerary, with missing travel information remaining unresolved.

Native recurrence requires policies or returns unresolved occurrences. Count semantics explicitly choose nominal candidates or emitted occurrences. Expansion is lazy and bounded by a window, candidate-work limit, output limit and cancellation. It returns outputs plus a resumable cursor or a completed search result. `NoOccurrence`, `AwaitingPublication`, `OutsideCoverage`, and `SearchBudgetExceeded` are distinct. A sparse or impossible rule cannot cause an unbounded hidden search. Ordered output guarantees specify whether they order nominal keys or resolved times; time shifts can change that order.

### RFC 5545 profile

`RFC5545` is a named compatibility profile, not the native default. Explicit DATE-TIME values in a fold select the first occurrence; an explicit gap value uses the pre-gap offset. Rule-generated invalid dates and nonexistent local times are skipped and do not consume COUNT. Generated folds use the first occurrence. DTSTART supplies the first instance; UNTIL is inclusive, with the prescribed type/UTC constraints, and COUNT and UNTIL are mutually exclusive. An inconsistent DTSTART/rule combination is rejected or retained uninterpreted. RDATE/EXDATE, duplicate suppression and RECURRENCE-ID retain their prescribed roles. [RFC 5545 §§3.3.5, 3.3.10 and 3.8.5.3](https://www.rfc-editor.org/rfc/rfc5545).

For example, a New York gap label at 02:30 can denote 03:30 when imported as an explicit DATE-TIME yet be omitted when generated by its RRULE. Profiles retain embedded timezone definitions and their identity; replacing VTIMEZONE with a similarly named system zone is an explicit migration. An export with different native policies returns a semantic loss report or materializes a bounded equivalent expansion; it cannot promise equivalence from RRULE text alone.

### Execution and updates

A scheduler adds durable occurrence IDs, cancellation, retries, duplicate handling, catch-up, missed-run and lateness policies. It promises only the selected delivery contract. Exactly-once effects require transactional/idempotent execution, not recurrence arithmetic. Wall appointments are re-evaluated on wall-clock/correlation changes and armed as bounded monotonic waits with a specified step policy.

Rule updates create migration previews identifying affected future occurrences, changed assumptions and resolution differences. A chosen cutover freezes past materializations while re-resolving future intent; pending or already executing work has an explicit disposition. Later evidence creates additional interpretations of historical events without rewriting observations. Restored schedules recover intent and rearm under the current clock domain, never reuse an old boot's raw deadline.

```dewy
let weekly = time.recurrence(
    anchor=time.local("2027-01-04T09:00:00") or_throw
    every=time.Period[weeks=1] zone=ny
    gap='reject' fold='earlier' invalid_day='skip'
    count_basis='emitted' context=app) or_throw
let (batch cursor) = weekly.expand(window limit=100 work=10000) or_throw
let next = weekly.next(after=window.end work=10000) ??<NoOccurrence> none
```

The final selective fallback leaves missing data, pending publication and search exhaustion visible. Broad `??` deliberately defaults any exception value and `none`, following Dewy's existing semantics; it is not an implicit library recovery policy.

## 7. Clocks, scopes and waits

A clock is a provider, not a time scale. `ClockReading` preserves source identity, raw count, device/boot/reset generation, acquisition bracket, resolution, synchronization/trust state, correlation edition and estimate. Accuracy may be unknown even when resolution is fine. NTP, PTP, GNSS and authenticated transport provide evidence, not perfect physical truth. An unidentified POSIX/UTC/smear convention returns `UnknownClockConvention`; unavailable, unsynchronized and untrusted sources remain distinct.

Wall time may step backward or slew. Monotonic points instead belong to a provider domain with declared suspension behavior, adjustment behavior and generation. They cannot mix with wall points or another boot. Runtime-selected incompatible providers return `DomainMismatch`; statically known incompatibility is rejected. A calibration maps readings through an offset/rate model with coverage. Uncertainty grows with elapsed counter time under the certified drift bound, acquisition error and transfer error; an expired or absent bound cannot retain its old accuracy claim.

CPU counters, SMP synchronization, wrap, reset, audio/video sample clocks, dropped samples and hardware frequency calibration belong to provider implementations. Sample periods can be exact rational quantities even when the physical oscillator drifts. VM pause/migration and hibernation require a provider contract: preserve the domain only if continuity is guaranteed, otherwise mint a new generation or report discontinuity. Never clamp a negative wall difference to disguise rollback.

### Capturing providers

`TemporalContext` is immutable configuration: provider handles, calendar/zone/locale selection, model/rule locks, policies and resource budgets. Its clock handle refers to a progressing service; immutability freezes identity and configuration, not the passage of time. A scope captures that handle once on entry. Short `now`, `sleep`, `within` and `today` calls resolve against the nearest captured scope, not a freshly selected process-global provider on each call.

At application entry, the ordinary host context is snapshotted once. Host zone/provider changes require a new context or an explicitly subscribed update stream; they do not silently replace an existing handle. A closure created inside a temporal scope captures its context. Async tasks inherit the creator's captured context when created and keep it across suspension, thread migration and resume. Cancellation does not reset the clock. An explicitly supplied context overrides the captured one for that operation; a context cannot escape its provider's lifetime without a retained handle.

```dewy
measure = (job clocks) => time.with_clocks(clocks () => {
    let start = time.monotonic.now() or_throw
    job()
    let finish = time.monotonic.now() or_throw
    finish-start
})

fetch_with_limit = (clocks) => time.with_clocks(clocks () =>
    within(2s @fetch()))
```

Both reads in `measure` share the captured provider and generation. A generation change returns an error rather than manufacturing elapsed time. Short calls outside an explicit scope use the entry snapshot; disabling ambient context requires a passed or statically captured handle. A wall `now()` returns a reading/estimate, never an infinitely accurate `Instant`. `today()` projects its support through the captured civil context and returns ambiguity if possible readings span dates.

A test controller advances a virtual provider already captured by tasks; it does not replace their provider. Resetting it creates a new generation and deliberately invalidates old points. Subtracting `testA.now()` from `testB.now()` therefore fails even when both counts are zero. Advancing test time deterministically wakes eligible waits; tests choose the ordering of equal-deadline wakeups. Reversing simulated game time is permitted only in a nonmonotonic domain, which cannot satisfy a monotonic-deadline contract.

### Suspension contract

The recommended default for `sleep(5s)`, `within(5s @work())`, relative TTLs and relative deadlines is **suspend-inclusive elapsed monotonic time**. A deadline may expire during suspension, but its callback can run only when execution resumes. A wake-capable alarm is a separate platform capability. Unsupported suspend-inclusive semantics return `UnsupportedClockSemantics`; the runtime cannot silently substitute an active-time counter.

`clocks.active` is the named alternative for monotonic time excluding system suspension. It measures active system elapsed time, not CPU execution time; process/thread CPU-time clocks are separate. Paused simulation time is another explicitly chosen domain. Selecting an active provider for a temporal scope deliberately changes the meaning of relative waits in that scope and appears in deadline metadata.

Timers round upward to available resolution, recheck the deadline before success and may wake late. Zero duration is immediately eligible; negative duration is rejected. `within` requests cancellation at expiry but cannot forcibly complete an uncooperative operation or promise that cleanup finishes at the deadline. Completion/cancellation races follow the scheduler's documented arbitration. Wall adjustments do not move a monotonic deadline; a wall appointment is separately re-evaluated. Persisting a TTL requires a reboot/recovery policy. Domain contracts and attainable accuracy remain values or proof obligations, including in the shortest examples.

## 8. Composing a sunset and publication calendar

Consider a community calendar whose months begin by an authority's crescent publication and whose days begin at local sunset. Its label↔ordinal relation uses authority editions; its day-boundary relation uses location, horizon/refraction convention and a solar ephemeris. Neither provider secretly supplies the other's information.

```dewy
let community = app.calendar("community/crescent-calendar") or_throw
let sunset = time.day_boundary(
    kind='sunset' location=community.site
    model=science.solar horizon=community.horizon
    missing='report') or_throw
let gathering = time.recurrence(
    calendar=community boundary=sunset
    selector=community.month_day(1)
    offset=30minute offset_basis='coordinate'
    publication='require_authority' missing_boundary='report'
    gap='reject' fold='all' count_basis='emitted'
    context=app) or_throw
let (known pending) = gathering.plan(window work=10000) or_throw
```

`known` and `pending` are two returned values, not an invented tuple container. `known` contains resolved occurrences with authority edition, boundary estimate and propagated uncertainty. `pending` contains resumable obligations, including `AwaitingPublication(authority period)` or `NoBoundary(location date model)`. The example's application-defined calendar exposes its site, horizon and selector; these are not mandatory members of every calendar.

For an announced first day, its start is that evening's sunset, not Gregorian midnight; the meeting is thirty coordinate minutes later. Uncertainty in solar geometry propagates into its time. If sunset does not occur at that latitude, no meeting instant is fabricated. A community policy could explicitly substitute another site's sunset or a published clock time; its authority and semantic change would travel with the occurrence.

Before the crescent publication, a predictive model can return several candidate days under an explicitly selected forecast profile. `require_authority` instead leaves a publication-wait obligation. The scheduler subscribes to the authority feed or waits under a bounded polling plan; this is a cancellable external wait, not an unbounded recurrence search. A new signed publication creates a new pinned context and resumes the pending plan. Signature verification authenticates its source, not the sighting's physical truth.

Stable occurrence identity uses the community's nominal month/day key. An authority correction creates a revised mapping and a migration decision for future execution; it does not erase the original publication or past attendance observation. A polar failure, unpublished month and disproved date are distinct outcomes. The same protocol supports a colony calendar over a sol ordinal and an operational boundary, with a publication authority for exceptional shifts. No Gregorian fields, universal midnight or Earth timezone are prerequisites.

## 9. Institutions, persistence and distributed systems

Institutional calendars combine working-week history, observed versus actual holidays, religious/observational dates, bank days, exchange sessions, exceptional closures and private operating rules. They support split and overnight sessions, moving-zone shifts, fiscal-year origins, 4-4-5 accounting, tax/reporting calendars and service dates with extended hours. `25:30` is a service-day offset interpreted by its operating rule, not an ordinary time-of-day field.

Business-day addition and working-time accumulation use actual session interval sets with explicit roll and inclusion policies. Surprise closures or unpublished religious holidays return pending knowledge or named scenarios. Payroll distinguishes measured elapsed work from contractually credited time across DST, travel and breaks. Financial year fractions name their day-count convention; legal ages name jurisdictional birthday rules. A generic `year` never becomes contractual elapsed seconds.

A deadline rule specifies jurisdiction, contract-named zone, relevant calendar, inclusivity, closure/holiday behavior and boundary semantics. “By midnight,” “end of day,” and “next Friday” are candidate intent descriptions until those choices are known. User display preferences do not change legal time. Retroactive laws preserve valid and publication dates; calculated results retain the rule edition and explanation. An institution's official feed and a third-party prediction are different evidence. Licensing may require supplied rule packs rather than bundled data.

Bitemporal records pair a valid-time interval with a transaction/knowledge interval. The axes can have different domains: database identity and commit sequence may be more truthful transaction order than wall timestamps. `as_of` takes both “valid at” and “known as of.” Corrections append assertions with supersession links, preserving earlier knowledge. Event, publication, reception and processing times remain separate when relevant. Late arrivals and watermark bounds do not rewrite event time. Local-date partitions use explicit calendar/zone boundary sets, including gaps and folds.

Distributed event IDs are independent of coordinates. Equal wall timestamps do not identify an event or establish causality. Lamport clocks preserve happened-before in one direction; sorting `(counter node_id)` is an administrative total order, not physical precedence. Vector/dotted-vector clocks express causal comparison and concurrency under named membership/incarnation rules. Hybrid logical clocks retain a physical component and logical counter; the counter is not extra subsecond precision. Rollback, counter overflow, resets and hostile remote values are handled explicitly. [Lamport's clock model](https://lamport.azurewebsites.net/pubs/time-clocks.pdf).

Cross-machine physical ordering uses correlated estimate bounds; overlaps remain indeterminate. Leases require protocol assumptions about drift, communication, renewal, failures and fencing or equivalent exclusion. A timestamp library cannot supply them. Security expiry policy specifies reject/permit/defer when trusted time support overlaps an expiry, and handles unavailable or manipulated clocks. Monotonic cache TTLs retain their device/boot/suspend domain. Durable transactions and scheduling combine these records with idempotency and recovery; “exactly once” is never inferred from a unique timestamp.

## 10. Science, observers and space

The general event contains a time coordinate, position or worldline point, reference system/frame and model context. `Instant` is a convenient terrestrial axis; it is not a mandatory hub for Mars-local arithmetic or distant missions. Coordinate transformations can require changing spatial coordinates and consistently scaled ephemeris positions, velocities and gravitational parameters. Changing just a TCB/TDB time label while keeping incompatible dynamical parameters is rejected.

Proper time integrates a metric along a specified timelike worldline with an initial synchronization condition. Different trajectories between events can accumulate different proper durations. Weak-field approximations state their potential sign, velocity terms, omitted orders and error envelope. Oscillator calibration remains distinct from relativistic correction. A proper-time difference retains its observer brand; a coordinate difference cannot claim to be either traveler's wristwatch duration.

UT1 represents Earth rotation using IERS data and prediction errors; ancient/future `ΔT=TT−UT1` requires a reconstruction/model. Earth rotation angle, mean/apparent sidereal conventions and solar phases are angular/phase constructions. Mean solar time needs longitude and rotation; apparent solar time adds solar geometry. Sunrise/sunset requires horizon/refraction choices and can have no solution. These calculations do not redefine fixed `hour=3600s`.

A spacetime causal query can establish timelike/null precedence, spacelike separation or uncertainty under a model. Spacelike coordinate ordering can reverse between frames. Remote “now” requires a simultaneity convention; signal accessibility is a different operational question. Model coverage and accuracy limit every such answer.

### Signals and flight operations

A signal path distinguishes emission, reception, relay/turnaround and execution events. Moving endpoints are evaluated at their respective times, usually by iteration. Propagation profiles identify geometric light time, gravitational/Shapiro delay, media and hardware corrections, convergence criterion, residual and model uncertainty. Ordinary SPICE light-time/aberration modes do not include every relativistic correction. Occultation, multiple paths, no path, missing coverage and nonconvergence are values. [NAIF correction contracts](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/abcorr.html).

Round-trip ranging solves separate uplink/downlink legs plus turnaround in the receiver's proper-clock domain. Half the round trip is not necessarily one-way delay, and same-epoch distance divided by c is not a complete moving-endpoint solution. A command planner works backward from an execution window through decode/queue delays and receiver-clock uncertainty, then intersects feasible emission windows with contact plans, transmission duration and station availability. It returns windows and requirements or `NoFeasibleWindow`; sending is separate. Disconnected execution uses onboard clocks and durable command identities.

SCLK preserves spacecraft/instrument/clock identity, partition/reset era, native count and raw telemetry. Ticks need not have constant SI duration. Correlation kernels provide piecewise maps, quantization, residuals and reconstructed/predicted coverage; an omitted partition may be ambiguous. New kernels create revised reconstructions while retaining original ticks and prior results. Mission elapsed time names its epoch and scale. Spacecraft event time, Earth reception time, ground transmission and exposure intervals are independent fields. Kernel pools are isolated behind pinned contexts. [NAIF SCLK model](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/sclk.html).

### Bodies, settlements and distant models

Mars support distinguishes Mars Sol Date, mean prime-meridian time, local mean and true solar time, seasonal solar longitude, Mars-year conventions and mission sol numbering. The named Mars24 model uses TT input and its specified mean-sol convention; dividing a sol into twenty-four hours does not make a Mars hour `3600s`. Mission offsets and landing-site clocks remain explicit. Darian and other proposed calendars are versioned plugins with declared epoch/leap rules and standards status. [NASA Mars24 algorithms](https://www.giss.nasa.gov/tools/mars24/help/algorithm.html).

A planetary local clock identifies body, body-fixed frame, orientation model, meridian, longitude sign, location, epoch and mean/apparent/operational flavor. It handles retrograde or irregular rotation, tidal locking, polar absence and multiple illuminating bodies. A habitat can choose an artificial cycle unrelated to rotation. Variable phases can have multiple inverse events; location on one body cannot be reused on another.

Lunar TCL belongs to the IAU Lunar Celestial Reference System. Operational LTC, scaled lunar proposals and ensemble realizations remain distinct definitions. The 2026 CGPM resolution calls for explicit transformation models, ephemerides and uncertainty in UTC traceability; it does not supply a universal finalized operational LTC constant. No fixed “microseconds gained per day” substitutes for the model. Requesting an unavailable realization returns `StandardNotDefined`, or the caller explicitly selects an experimental profile. [CGPM Resolution 6 (2026)](https://www.bipm.org/en/cgpm-2026/resolution-6).

Interstellar support extends reference charts, metrics, worldlines and signal solvers rather than extrapolating a solar-system ephemeris. Galactic/local-inertial/Fermi or cosmological charts name their conventions and domain. Cosmic time, lookback time, redshift and distance measures depend on cosmology; multiple light paths and horizons can prevent unique conversion or synchronization. Huge rational coordinates do not prove a precise Big Bang epoch or a globally valid chart. Offline packs and causal logs support disconnected settlements without presuming an Earth clock is reachable.

## 11. Formats, localization and pinned data

Parsing names a grammar/profile, expected result type, optional locale, full-input requirement and digit/length/depth budget. Offsetless text produces local fields, not an implicit instant. Ambiguous numeric dates, two-digit years, abbreviations and natural language return candidate interpretations unless a selected profile supplies a convention. Relative phrases require captured reference time, viewer zone, locale and intended boundary policy. “Yesterday” is computed in that viewer's civil context, not by subtracting `24hour`.

Human display supports numeric component order, punctuation, non-Western digits, grammatical month forms, pluralization, 12/24-hour conventions, noon/day periods, localized eras and time-dependent zone names. Calendar-specific fields remain available. Week calendars specify first weekday and week-number rules; week-year differs from civil year. Weekend definitions belong to dated cultural/institutional context. Accessibility profiles can spell out date order, zone, offset, era and uncertainty. Locale preferences never silently change geography or legal interpretation. [Unicode date conventions](https://www.unicode.org/reports/tr35/tr35-dates.html).

`24:00` is an end-of-day boundary notation only in profiles permitting it; its date association is preserved. Rounded human output is distinct from a lossless machine codec. It can display a nominal reading with an uncertainty marker under a named display contract, but cannot manufacture an exact value. Loss reports enumerate omitted scale, zone identity, calendar, precision, uncertainty, provenance or intent.

Native interchange uses schema/type tags, scale/domain/epoch identities, canonical rational numerator and positive denominator, context references and optional evidence/intent structures. Equivalent rationals have one canonical encoding for hashing/signatures. JSON uses integer strings or rational records rather than inaccurate numeric fields. Observation identity remains distinct from content-addressed definition identity; equal serialized reading content must not accidentally mint shared uncertainty-variable identity.

Adapters cover ISO profiles, RFC 3339/9557, iCalendar, POSIX, FILETIME, NTP era counters, GNSS weeks, SQL types and scientific time formats. They declare limits, leap behavior, fraction resolution and fidelity. Unknown offset conventions remain unknown, never known UTC; RFC 9557 critical annotations and zone/offset conflicts are handled explicitly. SQL adapters specify backend version, session timezone/conversion behavior, retained region identity and numeric/date range. A stored offset cannot reconstruct a discarded zone; an instant cannot reconstruct discarded local intent. Finite ABI overflow, including 2038 limits, returns `OutOfRange`; float/tick conversion reports precision loss. Two-part Julian-date and floating scientific adapters account for representation error separately from numerical solver error and model uncertainty; input digits never extend model validity. [RFC 9557 interchange rules](https://www.rfc-editor.org/rfc/rfc9557.html).

### Provider lifecycle and cost

Immutable content-addressed packs identify authority, license, source edition, schema/algorithm version, dependency hashes, issue/publication and effective dates, coverage, uncertainty and supersession. A lock selects a compatible closure. Missing pinned bytes return `MissingData`; client/server version disagreement remains visible. Signature validation authenticates bytes and publisher, not historical truth or future accuracy.

The distribution includes core algorithms, platform/test clocks, Gregorian/Julian calendars, interchange codecs and identified baseline UTC, IANA and CLDR packs. Richer calendar/locale datasets are available offline as batteries, with explicit deployment stripping. IANA historical coverage, optional backzone and future-rule extrapolation have visible limitations; it is not a complete legal-history source. Scientific packs include IERS orientation/announcements, BIPM realizations, IAU definitions, ephemerides, body models and mission kernels. Authority/legal/community packs have their own redistribution and evidence contracts. Support lists state actual implemented models and editions, not placeholders.

Fetching and update installation are explicit operations, never hidden conversion or compilation effects. Atomic context replacement installs a coherent dependency set. Existing values keep old references; archive exports may embed the closure. Revised historical interpretation and future appointment migration are separate operations. Runtime data loading does not create precompiled library images or bypass fresh source checking.

Dependencies point inward: rational/domain algebra; clocks and exact definitions; UTC/calendars/zones; formatting/recurrence; institutional/distributed modules; optional science. A stopwatch reaches no locale, timezone or ephemeris code/data. Indexed zone and correlation lookup costs `O(log n+k)` for k outputs; inverse lookup indexes overlapping local segments. Recurrence charges candidates examined, not merely outputs. Big-number, calendar, numerical iteration and ephemeris costs are declared separately. Input limits and cancellation bound adversarial parsers, kernels and rules. User calendar code uses ordinary effect/resource contracts; data packs do not execute arbitrary code.

## 12. Every convenience assumption has an opt-out

Defaults may select a context or named profile; they never silently repair civil ambiguity, erase uncertainty, assume independence, invent coverage, or choose a numerical transformation route. Every selected convenience is recorded in an assumption trace shared by reference. An exact calculation relative to a rule pack is distinct from claiming that pack describes the world.

The proposed metatag is `$time_require`, taking independently selectable obligation names. For example, `$time_require = ['ambient' 'clock_accuracy']` disables implicit context selection and unsupported nominal-clock accuracy. This spelling and selector schema require approval. `$bulletproof` enables **every** obligation below, in addition to Dewy's existing allocation, bounds, finite-float, hidden-cost and deadlock requirements. Wrappers and generic instantiation cannot hide unmet requirements; obligations propagate through the existing type/effect/fact system, without a whole-program time pass.

1. **`ambient`:** entry snapshots of host clock, zone, locale, calendar, location, route and data-pack selection are conveniences. Require an explicit argument or immutable lexical capture with known identity. Task migration cannot substitute a different handle.
2. **`calendar`:** generic proleptic Gregorian, astronomical numbering, ordinary day/week conventions and inherited era interpretation require explicit calendar/numbering/boundary selection. Historical use additionally needs the history obligation; a chosen arithmetic calendar alone proves no local adoption.
3. **`bounds`:** half-open interval defaults require explicit bounds or a type contract fixing them. No default epsilon or implicit conversion between date and physical spans is permitted.
4. **`profile`:** inherited parser, recurrence, overflow, rounding, execution and protocol policies require an explicit named profile or statically fixed policy. It exposes RFC gap behavior, two-digit-year windows, nominal/emitted counting, midnight/deadline meaning, timer rounding and late-run handling. The profile proves which convention is used, not what an author intended.
5. **`clock_domain`:** the default suspend-inclusive provider, platform monotonicity, VM continuity and generation lifetime require provider capabilities and continuity checks. Unsupported semantics remain values; active, CPU and simulated time must be distinguished.
6. **`clock_accuracy`:** treating a nominal reading, drift model or synchronization status as adequate requires acquisition/transfer/calibration evidence meeting the requested bound and validity interval. Unknown accuracy remains usable as unknown, never zero error.
7. **`clock_trust`:** accepting a source for security decisions requires the application's trust policy and threat assumptions. Signed packets alone do not establish correctness, freshness, bounded delay or absence of rollback.
8. **`realization`:** projecting TAI/UTC(k)/TT(BIPM) or another realization onto ideal coordinates requires an uncertainty-bearing correlation or a declared nominal-interpretation result. A bare nominal projection cannot discharge an exact physical-event obligation.
9. **`history`:** accepting published zone/calendar/legal history as actual practice requires explicit authority/source criteria and jurisdiction/observance evidence. Otherwise return assertions or alternatives. Pinned bytes establish reproducibility, not truth.
10. **`future_rules`:** continuing current laws, holiday rules, announced calendars or UTC regimes requires effective coverage and a stated authority/scenario contract. No current pack proves that governments cannot amend future rules. Unpublished observations remain pending.
11. **`location`:** a default geocentre, reference meridian, stationary site, horizon or illuminating body requires explicit location/frame assumptions and an applicable error budget. A downloaded ephemeris alone discharges none of them.
12. **`model`:** a convenient approximation, interpolation, omitted correction, route or numerical tolerance requires its model/error contract and compatible dynamical parameters. Numerical convergence alone is not an accuracy certificate.
13. **`extrapolation`:** extending ephemerides, correlations, Earth orientation, calendar predictions or rotation models beyond certified coverage requires an explicit warranted extension model. Selecting “allow extrapolation” cannot turn a forecast into proved accuracy.
14. **`dependence`:** probabilistic independence, covariance, or shared-error identification requires a joint model and evidence/premises. No library default applies root-sum-square. Conditional statistical conclusions keep their premises; sound deterministic enclosures remain available.
15. **`loss`:** nominal display, support hulls, quantization, floating export and omission of evidence/intent require a declared acceptance contract and loss report. A requirement of exact fidelity rejects the operation. Choosing a loss policy never proves exactness.
16. **`protocol`:** distributed leases, clock-based expiry, delivery guarantees and restored deadlines require their drift/network/failure/recovery assumptions and protocol evidence. Timestamp ordering alone cannot discharge causality or exclusion.
17. **`resources`:** defaults for loading, storage growth, search, numeric work and provider availability must expose bounds, fallibility and cancellation under the existing strict resource rules. A pinned context does not imply its bytes are loaded or an external authority will reply.

These categories close the inventory for this design: each new convenience must name its category or add a new obligation included by the bundle. Ordinary explicit operations already enforce inherent ambiguity, domain and validity failures regardless of metatags. Strictness can require evidence at runtime and return an unresolved value; it does not require every future observation at compile time.

Proof means a checked software implication under stated premises. Empirical models, institutional authority and physical hardware provide evidence with assumptions, not compiler proofs of nature. A caller can request a conditional scenario and receive a conditional result; it cannot pass that result where an unconditional accuracy or truth guarantee is required. The provenance type prevents laundering such a premise through a convenience wrapper.

```dewy
wait_for = (delay:Duration<>=? 0s> clocks) =>
    time.with_clocks(clocks () => sleep(delay))
```

A refined nonnegative delay discharges one local obligation. It does not prove the clock is available, wakeups are timely, cleanup terminates, or memory allocation succeeds. `or_throw` is explicit forwarding under Dewy's error conventions; `??<Canceled>` handles cancellation without swallowing unrelated errors. No-traps behavior continues to mean proof or visible failure handling, not an undocumented environmental exception.

## 13. Capability acceptance and delivery

Implementation proceeds through independently useful layers. Early carriers preserve domain, raw evidence, uncertainty and intent even before every model exists. A stage advertises only operations it implements. Fixtures use named definitions and pinned editions; disagreements with an oracle are investigated as convention, coverage or implementation differences.

**Core, uncertainty and clocks.** Verify `1ns/3`, enormous signed offsets, floor splitting, exact epoch changes, checked finite ABI rounding, affine rejection and domain mismatch. Distinguish equivalent coordinate encodings from record identity and physical accuracy. Exercise shared calibration cancellation and `X−X=0`, unknown/disconnected support, covariance requirements and inconsistent evidence. Test Allen relations, point/empty variants, unknown versus unbounded ends, and meeting-but-disjoint half-open intervals. Inject unavailable/unsynchronized clocks, rollback, suspend, VM migration, drift and reboot. Virtual clocks drive deadline races without real waiting; a stopwatch-only fresh build reaches no unrelated layer.

**Civil time and recurrence.** Independently check the frozen Apollo derivation against authoritative historical coefficients and SOFA vectors. Round-trip all three labels around the 2016 leap; reject invented second 60 and test synthetic negative leaps. Compare historical UTC to explicit proleptic conventions. Exercise before/at/after the continuous-UTC boundary with current and stale packs and alternate inherited offsets. POSIX/smear codecs either preserve phase/profile or report loss. Use the same tzdb release/profile with zic/zdump, plus synthetic second offsets, midnight shifts, whole-date skips/repeats and more-than-two inverses.

Compare calendar-day and `24hour` arithmetic, British reform succession, Swedish insertion, leap months, days outside cycles, era boundaries and no-year-zero views. Verify sunset absence and publication-wait composition. Contrast repeated clamping with original-anchor month-end recurrence. Test RFC explicit/generated gap differences, COUNT/UNTIL, stable override IDs and timezone-definition preservation. An impossible or sparse recurrence must distinguish exhaustion, absence, missing law and pending publication. Machine round-trips retain semantics; human display reports its declared losses.

**Institutions and records.** Named institution fixtures cover sessions, closures, fiscal rules, legal deadlines and credited versus elapsed work. Query late events and retroactive corrections along valid and knowledge axes without modifying previous assertions. Equal physical timestamps retain vector concurrency; HLC counters never become physical precision. Demonstrate lease/expiry refusal when necessary clock/protocol assumptions are missing. Check database adapters against their stated backend/session contracts and test appointment migration with already armed work.

**Science and flight.** Test exact TT↔TCG and TCB↔TDB maps, including inverse divisors and origin signs. Test position-dependent TCG↔TCB with insufficient/missing ephemerides, accuracy refusal and realization revisions. Compare proper elapsed time on distinct worldlines. Solve moving-endpoint asymmetric signal paths with turnaround and separately validated gravitational/media corrections; distinguish reception, occurrence and execution windows. Re-correlate partitioned SCLK while preserving ticks and old reconstructions. Match NASA Mars24 reference cases, reject Earth-hour substitution, and require declared Darian conventions. TCL conversions retain context and uncertainty; unavailable operational LTC remains unavailable.

**Extension and cost.** Demonstrate a colony calendar, disconnected authority updates, and a model where a spacelike pair reverses coordinate order while retaining causal classification. Refuse unqualified universal now and outside-domain extrapolation. Profile fresh compilation and instruction counts on the flagship panel; demand-driven indexed providers must not pull bulk data into unused programs. Charge candidate search, big arithmetic and numerical iteration honestly; fuzz malformed data and adversarial resource limits. Applicable compiler/library changes use focused/quick gates and full/bootstrap/fixed-point batch gates, with at most four workers.

## 14. OPEN DECISIONS for David

These choices need semantic approval before publication. Names can change without changing the contracts above; shipped wire meanings and persisted intent are harder to revise.

1. **Epoch.** Recommend the frozen Apollo TT coordinate and exact `e` in §1. The competing recommendation is the **1977 TT standards origin**, `e=0`, for simpler standards normalization. A third option is the explicitly TT-labelled Unix-calendar origin; it does not imply POSIX arithmetic or the historical UTC event. All retain the same rate and capability. This unblocks stable wire identities. Reversible before published data, costly afterward; verify the Apollo derivation before freezing it. Jai compatibility, if wanted, is a separate verified adapter profile.

2. **Core rate.** Recommend the **ideal TT-rate axis with TAI-compatible nominal labels**, as defined by the invariant, rather than a TAI-realization-defined axis. An ideal definition keeps improved realizations from redefining stored coordinates; TAI and TT(TAI) remain first-class realized domains. The alternative makes the chosen published TAI realization normative and must then define its historical extension and refinement behavior. Epoch preference remains independent of this rate decision. This unblocks scientific interoperability and generic event domains. Cheap to choose now, a wire-semantic break later.

3. **Relative wait suspension.** Recommend suspend-inclusive elapsed monotonic defaults for `sleep`, `within`, TTLs and relative deadlines, with explicit active-time providers and separate CPU/simulation clocks. Expiry during suspension does not promise execution or wake from suspension. Unsupported platform semantics are values. This unblocks portable timer contracts; changing the default later changes application behavior, while explicit-domain APIs are stable.

4. **Interval default.** Recommend half-open convenience constructors, with explicit flags and a strict opt-out. Approve the separate endpoint/topology and point/empty relation semantics, rather than making Allen labels imply set intersection. This unblocks range APIs and analytics. Default changes are reversible before adoption; stored bounds must always be explicit.

5. **Generic dates.** Recommend proleptic Gregorian with astronomical year numbering, exposed by identity and strict opt-out. Historical adoption, era views and non-midnight boundaries remain explicit. This unblocks concise ordinary dates without making historical assertions. Reversible before widespread source use; preserve conventions in stored records.

6. **First-class intent.** Recommend distinct appointment, occurrence, event and observation records, stable nominal occurrence IDs, and explicit future migration. This unblocks resilient scheduling and faithful round-trips. The addition is compatible with the scalar core; discarding intent from stored schemas is not recoverable later.

7. **Strictness names.** Recommend the single selector metatag `$time_require` and the seventeen independent obligations in §12, all included by `$bulletproof`. Alternative individual `$no_assumed_*` metatags can expose the same obligations if preferred. Selector names/grouping are reversible; evidence requirements and propagation need approval before convenience APIs are finalized.

8. **Public surface inventory.** Recommend ordinary library APIs with no new keywords. Grouped proposed names follow; **semantic** marks require approval of behavior as well as spelling. Other names still require surface approval.

   - Core/evidence: `TimePoint`, `Instant`, `Duration`, `CoordinateTime`, `TAICompatible`, `Estimate`, `Interval`, `IntervalSet`; `convert`, `compare_estimates`, `certainly_before`, `possibly_before`, `same_set`. **Semantic:** domain-branded differences, realization projection, dependence, `Same` and degenerate relations.
   - Civil/intent: `Date`, `TimeOfDay`, `LocalDateTime`, `Offset`, `Zone`, `ZonedDateTime`, `Period`, `Calendar`, `DayBoundary`, `MonthDay`, `YearMonth`, `Appointment`, `Occurrence`, `Event`, `Observation`; `date`, `local`, `resolve`, `choose`, `recurrence`, `expand`, `plan`, `as_of`. **Semantic:** repair/overflow policies, count basis, RFC profile, identity and migration contracts.
   - Clocks/science: `TemporalContext`, `ClockReading`, `MonoPoint`, `Worldline`, `ProperClock`, `SignalPath`, `Sclk`; `with_clocks`, `now`, `today`, `monotonic`, `active`, `correlate`, `proper_elapsed`, `causal_relation`. **Semantic:** scope/async capture, nominal interpretation, timeout/cancellation and model requirements.
   - Result families: `Gap`, `Ambiguous`, `Unknown`, `Unspecified`, `MissingContext`, `MissingData`, `OutsideCoverage`, `InvalidDate`, `InvalidFields`, `DomainMismatch`, `InconsistentEvidence`, `Indeterminate`, `Incomparable`; clock/trust/accuracy, representation/loss, search/publication and physical-model failures named in their sections. **Semantic:** unresolved versus impossible, comparison variants and selective error handling; exact spellings can be consolidated without collapsing meanings.

Policy labels such as `earlier`, `later`, `all`, `preserve_displacement`, `clamp`, `require_authority`, `emitted` and `keep_local` are included in that surface decision. They must serialize by stable versioned meaning. Existing juxtaposed units, affine operations, unique `as`, `??`, `??<E>`, `or_throw`, `sleep`, `within` and metatag machinery are reused; extending their time-specific contracts does not approve new language syntax.
