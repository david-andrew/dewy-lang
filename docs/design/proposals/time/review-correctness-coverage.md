# Time design v4 + critique: correctness and coverage review

## BLUF

- **Keep David’s integer `Instant` and J0.** A fixed default grid need not lose v4’s capabilities if explicit integer tick types, exact scale coordinates, raw codecs and uncertainty records remain available.
- **Do not accept the critique’s compact records as a complete evidence contract.** Reconstructing an old reading’s estimate from the provider’s *current* error bound is unsound; pack and clock handles also need stable identity and lifetime rules.
- **Literal infallibility is sound only relative to frozen inputs.** A precomputed meeting stays the same resolved value under another tzdb; it does not automatically remain the same local appointment under changed law.
- **Correct the clock cache.** An already-pinned leap transition must take effect without a pack update; wall steps, smear behavior and wall/monotonic correlation updates must remain observable.
- **The critique’s four epoch integers check out.** Its Go account is wrong about `Add` and `==`; v4 deliberately specifies wall subtraction, an ergonomic hazard rather than a copied Go implementation bug.
- **The UTC resolution is real.** Continuous UTC starts 20 May 2027; Bulletin C 72 already excludes a December 2026 leap. The second’s redefinition is a proposal targeted for 2030, not an enacted 2030 change.
- **Repair the science examples.** Ancient UTC is unsupported, DE440 excludes 585 BCE, an unused ΔT does not rotate the Earth, and a date interval plus an ephemeris does not specify an eclipse computation.
- **Keep negative-leap coverage.** Share the skipped-label mechanism, but test its UTC, protocol and arithmetic consequences; a DST-gap test alone is insufficient.
- **Adopt the ergonomic direction with explicit contracts.** Use `now`, `@job`, checked literals and space-separated arguments; retain value failures for genuinely partial operations. Fifteen revised examples appear below.

## 1. Regression check against the 269-row matrix

- **Scope/acceptance:** one focused read-only review of v4, all of the v4 critique/brainstorm, the twelve matrix sections, and Dewy’s goals/decisions/assumptions plus relevant language rules. Owned file: this report only. Non-goals: implementation, repository edits, benchmarks, or repeating the representation/performance review. API sketches below are proposed contracts, not tested Dewy library code.
- **Audit method:** the IDs below are from a scratch matrix analysis. They identify affected concerns, including conditional regressions; omission from the critique’s shorter document does not itself delete a v4 feature. All other matrix rows retain their v4 home **provided the rewrite explicitly carries those contracts forward**.
- **Intentional restriction:** plain nanosecond `Instant` cannot itself represent `1ns/3` or arbitrary finite rationals. That follows from choosing this grid, not from choosing integer ticks generally. The language’s wider time system must still represent those values exactly.

### Numeric range, ancient dates and off-grid results

- **1.15, 6.17 — signed/enormous values and finite storage:** 128-bit ns covers ancient history, ±10,000 years, and ordinary cosmological ages. It does not preserve v4’s unrestricted finite rational range/resolution. Fix: retain arbitrary-range exact `Coordinate<Scale>` and explicitly selected integer tick/count representations; report/prove finite-storage limits. An ancient `Date` must not acquire a hidden 64-bit ns limitation.
- **1.01, 4.17–4.19, 4.31, 5.12, 12.01–12.05, 12.16 — ancient labels:** a proleptic Gregorian date/year zero is valid arithmetic; `instant"-2000-…Z"` is not historical UTC. Fix: construct TT/UT1 coordinates with explicit calendar and model, or preserve a historical source claim. Proleptic *calendar* permission does not grant proleptic *UTC* permission.
- **1.11, 5.01, 5.06, 5.15–5.18, 6.14–6.17, 9.16, 9.18, 10.10, 10.13–10.14 — fine science values/affine conversions/codecs:** `1ns/3`, caesium-cycle ticks, NTP binary fractions, PTP corrections, fine CUC/CDS, decimal fractions beyond nine places and exact TT↔TCG inverses can leave the ns grid. Fix: native integer codec values and branded exact coordinates; conversion to `Instant` requires divisibility and range, or explicit quantization with signed loss. Do not make exact decode depend on ns conversion succeeding.
- **Same numeric rows — quantities remain exact:** `1ns/3` and `1s/3` remain valid standalone durations; only storing/adding them on an incompatible fixed point grid fails. Dewy’s unannotated `0.1s` is an exact decimal quantity, not automatically binary64. A finite float duration can be accepted when its exact represented value is on-grid and in range; otherwise require explicit conversion/quantization. NaN and infinities do not become integer timestamps. Do not outlaw the existing quantity system to protect `Instant`.
- **Same rows — native grid versus J0 grid:** an NTP value on a binary grid relative to its native origin need not stay on that grid after an epoch shift or a historical UTC transform. Fix: preserve the native epoch/domain along with its integer count; use an exact coordinate or a deliberately chosen common grid for normalization. `Instant<tick=1s/2^32>` with fixed J0 is not a universal lossless NTP container.
- **1.16–1.17, 10.14 — equality/hash capability:** different ticks can denote the same coordinate even if neither value fits the other type’s width/grid. Fix: either define exact mixed comparison using bounded cross-products/common widened arithmetic, or reject it statically and offer explicit exact coordinate comparison. Homogeneous hashes may stay cheap. If heterogeneous equality is admitted as key equality, equivalent keys must hash alike; “different types” alone does not settle that contract.
- **6.17 and Dewy’s fixed-integer decision:** The critique treats finite-width arithmetic as automatically returning `OutOfRange`; Dewy specifies exact arithmetic with proved narrowing at storage. Fix: state expression versus stored result rules. Two signed 128-bit point counts can require 129 bits for their difference; affine averages can be off-grid; `max + 1tick` has no representable successor. `OffGrid` means divisibility failure, `OutOfRange` means range failure, and an unproved obligation is neither error by definition.

### Uncertainty, evidence, topology and compact records

- **1.11–1.14, 1.17, 5.19, 9.04–9.09, 9.23–9.24, 10.01, 10.16–10.17, 12.04, 12.15–12.16 — lazy estimates:** `.estimate` built from today’s provider error bound can give yesterday’s reading an unjustified narrow uncertainty after resynchronization. Fix: retain a small stable acquisition/correlation token or offer an explicit detailed read that captures the evidence at acquisition. A plain reading may honestly yield `Unknown` when old evidence was not retained; document this deliberate fidelity limit. Never fabricate historical precision on demand.
- **Same concerns — dependence:** v4’s shared calibration cancellation, `X−X = 0`, disconnected support, absent nominal representative and contradictory evidence remain necessary. Fix: keep `Estimate<T>`’s joint-expression/evidence contract independent of the common record layout. A copy preserves identity; independently imported equal bytes do not. Removing per-value allocation need not remove dependence modeling.
- **1.12–1.14, 3.23, 4.24–4.25, 8.04, 9.07, 9.24 — `today`:** always returning only the nominal `Date` drops v4’s date-boundary ambiguity/unknown support. Fix: if David chooses nominal `today`, name that contract and provide the actual supported dates/unknown result separately; strict accuracy use requires it. Ambiguous support is not caused specifically by “ambiguous civil midnight”: an uncertain clock can straddle any date boundary.
- **1.10, 6.19 — intervals:** a bounded grid has successors except at its maximum. `[a,b] → [a,b+tick)` is valid only for sets restricted to that grid and an available successor/extended end. It changes Allen endpoint geometry and cannot preserve all original bound semantics. Fix: retain endpoint flags or an explicit normalization contract. Do not project a physical uncertainty interval onto integer points without a rounding/enclosure rule.
- **4.09, 6.07 — calendar topology:** The critique’s blanket successor prohibition for “calendar days” is wrong; an ordered calendar can prove a successor, including British September 2 → September 14. Partial/observational calendars may not. Fix: capability-based successor, not a ban by category.
- **1.17, 2.06, 2.14, 3.18, 4.30, 6.12–6.13, 7.14, 7.20, 10.08–10.09, 10.14–10.18 — compact `ZonedDateTime`:** instant + zone number + offset does not preserve original local input, repaired gap displacement, calendar, pack edition, branch/anchor or policy. Fix: distinguish a compact resolved value from an intent/resolution record. Retain v4’s richer record when advertised fidelity needs it.
- **Same rows — handles:** a 32-bit zone number is ambiguous without a pack namespace; content addressing does not automatically make IDs append-only across packs. Fix: value/type/context must retain the defining pack and keep it alive, with no handle reuse while referenced; wire encoding includes portable definition identities, not process-local IDs. The same rule applies to clock/context handles.

### Clocks, leap handling, recurrence and long-lived programs

- **1.06, 9.01–9.06, 9.10–9.14, 10.19 — monotonic arithmetic:** changing reading subtraction/addition to elapsed difference/deadline is an owner-level semantic change. Preserve named wall subtraction and wall appointments. Match provider **and** generation, tick/rate and suspend contract; two test clocks can share generation 0. Handle wrap, reset, snapshot/restore and token reuse. Same boot alone proves neither compatible provider nor `int64` difference fit.
- **9.04–9.09 — elapsed accuracy:** a counter difference is exact in its declared counter coordinate, not automatically exact SI elapsed time. Keep drift/calibration uncertainty for callers needing physical duration. Zero or repeated counter values are valid; monotonic need not mean strictly increasing.
- **9.24 and no-traps — lazy first use:** moving acquisition to first `now` does not erase failure. Fix: expose initialization through a handled acquisition/context/task failure contract, then keep reads total. Do not hide a first-call exception behind a return type claimed infallible. Snapshot configuration at the promised boundary even if opening resources is deferred.
- **5.03–5.10, 9.06, 9.22 — cached offsets:** The critique invalidates the leap offset only on pack update. A running process crossing an *already-pinned* transition then uses the old offset. Fix: scheduled segment invalidation/validated cache coverage, coherent paired samples, and explicit handling of wall jumps and leap phase. Wall/mono correlation must also track steps/slews; one permanent startup offset is a holdover clock, not a live wall clock. Unknown smears remain unknown.
- **5.04, 5.07–5.09, 6.09, 9.22 — negative leap:** sharing gap lookup is sound. Removing UTC-specific acceptance checks is not: label adjacency, shortened UTC day, POSIX/NTP inversion and named smear behavior must follow the synthetic segment. Fix: one synthetic history reused across these adapters; no invented real negative leap or separate public type is needed.
- **2.24–2.26, 3.18, 4.16, 4.24–4.25, 4.30–4.32, 5.05, 5.10, 7.07–7.12, 7.17, 7.20, 9.19–9.21, 10.15–10.18, 11.02, 11.04, 11.07, 11.16, 12.10–12.12, 12.15–12.16 — constant folding/future rules:** infallible literals must not erase data identity, coverage, publication waits or uncertainty. Fix: §3’s snapshot contract; preserve appointment intent and explicit migration. A stale status cannot be inferred merely from host/pinned disagreement: neither copy is necessarily newer or authoritative.
- **1.05, 3.21–3.22, 6.01–6.13, 6.16, 6.18, 7.01–7.22 — recurrence:** keep ordered periods, original anchors, multi-candidate folds, exclusions/overrides, count basis, unresolved occurrences, bounded work and stable cursors. A resolved `zoned` constant does not by itself express whether an appointment preserves an instant or local time. Fix: the recurrence constructor retains both intended local fields and chosen semantics; plain date addition does not secretly make an anchor sticky.
- **4.28–4.29, 6.06, 7.02 — `week`:** with non-seven-day cycles supported, define whether a period week is seven calendar days or a calendar-specific cycle. Fix: recommend seven calendar-day successors for `1week`; explicitly named calendar cycles for other meanings. Do not let contextual unit inference reinterpret an already-bound period at different uses.
- **Remaining matrix coverage:** geography/itineraries, partial labels, observational/reform calendars, localization, business/legal rules, bitemporality, logical clocks, proper time, signals and planetary models survive in v4’s extension layers. The critique’s three-module sketch should organize them, not silently replace their contracts with `Instant` arithmetic.

## 2. Factual verification and corrections

### J0, TAI and the Apollo integer

- **Verified normalization:** J0 = `2443144.5003725`; its TT label is `1977-01-01T00:00:32.184 TT`. The nominal TAI-compatible label is midnight. Exact nominal TT/TAI-compatible arithmetic cancels `32.184s`; no `L_G` multiply belongs in a TAI-compatible wall projection. These are not assertions of perfect realized TAI. [ERFA TT/TCG implementation](https://raw.githubusercontent.com/liberfa/erfa/master/src/tcgtt.c)
- **Independently recomputed using exact fractions:** J0 `0ns`; historical UTC Unix-origin event `-220924791999918000ns`; v4’s conventional Apollo coordinate `-235107732425406200ns`; GPS origin `95040019000000000ns`; J2000 TT `725803167816000000ns`.
- **Apollo derivation:** UTC MJD = `40422 + 73060/86400`; `TAI−UTC = 4.2131700s + (MJD−39126) × 0.002592s = 7.5745938s`. Add this to the nominal Gregorian label displacement from 1977 TAI midnight. Unix-origin offset similarly equals `8.000082s`. The fractional *day* matters. These are conventional label coordinates, not touchdown accuracy. [USNO historical coefficients](https://maia.usno.navy.mil/ser7/tai-utc.dat)
- **Range arithmetic:** The critique’s orders of magnitude and 70/76-bit requirements are sound; signed 64-bit ns from this origin actually reaches September **1684**, not 1685, through April 2269. The one-million-year default-width threshold is a proposal, not a standards requirement.
- **Exact affine definitions:** `x_TT = (1−L_G)x_TCG`; `x_TDB = (1−L_B)x_TCB + TDB0`; inverses divide by `1−L`. A nanosecond default requires an off-grid result carrier. TT↔TDB is a different, modeled operation. [ERFA TCB/TDB implementation](https://raw.githubusercontent.com/liberfa/erfa/master/src/tcbtdb.c)

### The alleged Go bug

- **Correct:** Go prefers monotonic readings for subtraction/comparison when both operands have them; serialization omits them; `AddDate`, `Round`, `Truncate` and zone-changing views strip them; otherwise subtraction can fall back to wall time.
- **Incorrect:** Go `Add` preserves and advances both clocks. `==` does not drop monotonic data; it compares it and location, unlike coordinate-style `Equal`. Go also documents suspend limitations. v4 does not reproduce this hidden fallback: it explicitly chooses nominal wall subtraction and offers monotonic elapsed separately. Critique the mismatch with its motivating stopwatch example; do not call that choice an implementation bug. [Go monotonic-clock contract](https://pkg.go.dev/time#hdr-Monotonic_Clocks)
- **Dewy consequence:** a dedicated reading type that cannot deserialize with accidental fallback is a useful improvement. Whether its easy operators are wall or monotonic remains David’s decision. Neither choice removes domain/continuity failures.

### Leaps, continuous UTC and the second

- **Verified:** historical positive leap labels remain real; 27 positive insertions are reflected in the UTC history and no negative leap has occurred. A negative leap skips a label; `:60` at a nonexistent insertion is `InvalidFields`/invalid leap label, not a numerical `OffGrid` failure. [USNO UTC history](https://maia.usno.navy.mil/ser7/tai-utc.dat)
- **Verified final resolution:** continuous UTC takes effect **20 May 2027**, maximum `|UT1−UTC|` becomes `3600s`; negative-leap operational risk is explicitly a motivation. The resolution specifies no future leap-hour mechanism. This is a versioned current standard, not proof that no future standards body will ever amend UTC. [CGPM Resolution 5](https://www.bipm.org/en/cgpm-2026/resolution-5)
- **Correction to the critique’s “last December slot”:** IERS already announced **no leap at the end of December 2026**. Preserve inherited-offset data rather than baking today’s offset into the type. I did not independently locate the specifically attributed “CCTF statement of 15 October”; the final resolution supports the substantive motivation without that attribution. [Bulletin C 72, 6 July 2026](https://datacenter.iers.org/data/16/bulletinc-072.txt)
- **2030 is conditional:** Resolution 4 requests a proposal and an implementation-date proposal for the 2030 CGPM; species/ensemble consensus and some criteria are still unmet. Replace “when the 2030 definition lands” with “if/when adopted.” Preserve numerical tick meanings and version realization/model relations rather than rewriting stored integers. [CGPM Resolution 4](https://www.bipm.org/en/cgpm-2026/resolution-4), [BIPM second-redefinition FAQ](https://www.bipm.org/en/faq-redefinition-second)

### GNSS, NTP, PTP and codec claims

- **GPS:** nominal GPS = TAI−19s and epoch 1980-01-06 GPS are the intended convention; realized GPS measurements still carry clock/transfer errors. Legacy week fields are 10 bits; CNAV has 13-bit fields. `week=1023 era=0` starts 1999-08-15 GPS; `era=1` starts 2019-03-31; these are the weeks *before* rollover. To demonstrate the rollover dates, use `week=0` with eras 1 and 2. Explicit era evidence is correct. Do not extend GPS epoch/offset/leap rules to all GNSS. [USNO rollover table](https://www.cnmoc.usff.navy.mil/Our-Commands/United-States-Naval-Observatory/Precise-Time-Department/Global-Positioning-System/GPS-Information-SA-DGPS-Leap-Seconds-etc/GPS-Week-Number-Rollover/), [GPS.gov](https://www.gps.gov/news/gps-week-number-rollover)
- **NTP:** correct grids: 64-bit packet timestamp = unsigned 32-bit seconds plus 32-bit fraction; extended 128-bit date = signed 64-bit seconds plus 64-bit fraction, with era/offset subdivision. The latter is not the ordinary packet timestamp. Era must come from evidence; LI/sync metadata and zero’s protocol meaning survive decoding. `2^-32s ≈ 0.2328306437ns`; `2^-64s ≈ 0.0542101086as`. Do not repeat RFC 5905’s inconsistent parenthesized decimal for the latter. [RFC 5905 §6](https://www.rfc-editor.org/rfc/rfc5905.html#section-6)
- **PTP:** correct: full timestamp has 48-bit seconds plus 32-bit decimal nanoseconds, not a binary fractional-second field. PTP epoch is 1970 TAI under its PTP timescale; timescale/domain/UTC-offset-validity flags matter. The critique correctly keeps fractional corrections separate. `correctionField` is signed scaled ns (`2^-16ns`) and has a special too-large state: decode that state, never turn it into an ordinary correction. ARB domains are not implicitly TAI. [RFC 8877 §4.3](https://www.rfc-editor.org/rfc/rfc8877.html#section-4.3), [IEEE interpretations, requests 25/27](https://standards.ieee.org/wp-content/uploads/import/documents/interpretations/1588-2008_interp.pdf)
- **Important correction to the “lands on 1ns” table:** that can describe native encoding precision, not universally the mapped J0 coordinate. Pre-1972 UTC rate adjustments and smear inverses can map a nanosecond-valued label off-grid. Example in the 1968 rate segment: a UTC label increment of `1ns` adds `1.00000003ns` in nominal atomic seconds. Preserve exact native payload and use the appropriate mapping, then check/quantize. PTP atomic timestamps and fixed TAI epoch shifts do not have this particular UTC-rate issue.
- **Binary64 codecs:** ET/JD doubles have magnitude-dependent spacing, not one fixed binary tick for every value. Exact finite-float decode is dyadic, while “quantum” needs exponent/rounding/context; preserve raw parts for full bitwise round-trips, including signed zero and protocol special values. Two different two-part JD decompositions can have the same sum.

### Prior-art verification

- **java.time:** type split, integer seconds+nanos, `Clock`, and resolver styles are good lessons. “Does not model leaps” is incomplete: the Java Time-Scale specifies UTC-SLS after its 1972 boundary and proleptic UT1 before it; actual clocks need not implement the slew. `Instant` does not represent `:60` as a separate label. This is a warning against inferring physical SI elapsed seconds from an API name. No chronology/estimate on `Instant` is useful, but this source establishes no Dewy performance comparison. [Java `Instant` scale contract](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/time/Instant.html)
- **Joda-Time:** The critique’s chronology-baked-into-`Instant` claim is false: Joda’s `Instant` stores only epoch milliseconds and explicitly ignores chronology/zone. Its `DateTime` is a different type. “Lost because…” is unsupported causal history; remove it. [Joda `Instant`](https://www.joda.org/joda-time/apidocs/org/joda/time/Instant.html)
- **Noda Time:** explicit local types, strict/lenient zone resolution and calendar periods are accurately identified. Not every zone operation returns a resolution union: `InZoneStrictly` throws; APIs include different contracts. Dewy should retain checked whole-union resolution, rather than claiming Noda has one universal behavior. [Noda `LocalDateTime`](https://nodatime.org/3.2.x/api/NodaTime.LocalDateTime.html)
- **JavaScript/Temporal:** `Date`’s mutable ms/local-field mixture and zero-based month APIs are real; standardized date parsing exists, so “implementation-defined parsing” needs qualification to nonstandard strings. Temporal uses integer ns ignoring leaps; leap-second string parsing constrains rather than represents `:60`. Current public APIs use calendar/time-zone **identifiers**, not the old public `Temporal.Calendar`/`Temporal.TimeZone` classes in the critique’s inventory. Some `Now` methods obtain the current host zone when omitted; `Now.instant` has no zone selection. [Temporal specification](https://tc39.es/proposal-temporal/), [Instant](https://tc39.es/proposal-temporal/docs/instant.html), [Now](https://tc39.es/proposal-temporal/docs/now.html)
- **Temporal durations:** months and seconds coexist, but operations requiring context demand `relativeTo`; this is an intentional reference-dependent design, not evidence of silent conversion of months to seconds. Dewy’s split can be clearer while still needing a defined mixed-period order and relative comparison. [Temporal duration contract](https://tc39.es/proposal-temporal/docs/duration.html)
- **Python:** precision/fold/POSIX-float statements are broadly correct. The precise arithmetic trap is that addition and same-`tzinfo` subtraction ignore zone transitions/fold, despite using aware values; different-`tzinfo` subtraction accounts for offsets. Naive/aware ordering fails, whereas equality is not simply the same failure. Calling this just a “fixed-duration timedelta bug” obscures the actual operator semantics. [Python datetime arithmetic](https://docs.python.org/3.14/library/datetime.html)
- **chrono/jiff:** chrono supports a restricted leap representation without a complete leap history; IANA crates remain separate. Jiff documents clamping, system-tzdb preference with bundled fallbacks, and a custom-TZif TAI workaround. Its zone is shared through an `Arc`, not a transition table copied into every `Zoned`. Its documented exploration does not establish the critique’s specific shipped-then-ripped-out history. [chrono](https://docs.rs/chrono/latest/chrono/), [jiff](https://docs.rs/jiff/latest/jiff/), [jiff design](https://docs.rs/crate/jiff/0.2.32/source/DESIGN.md)
- **Rust time/hifitime:** the cited unsoundness concerns `localtime_r`/environment races, including time 0.2 APIs, not just unsafe timestamp conversion in 0.1. Hifitime does **not** use float storage: its duration uses integer centuries/nanoseconds. Keep its continuous-scale lesson; remove the misleading float-storage contrast. [RustSec advisory](https://rustsec.org/advisories/RUSTSEC-2020-0071.html), [hifitime Duration](https://docs.rs/hifitime/latest/hifitime/struct.Duration.html)
- **C++ chrono:** compile-time ticks and clock-branded points are real; `duration_cast` can truncate on integral division. The main lesson is explicit conversion policy, not copying truncation or unchecked finite arithmetic. [C++ draft duration conversions](https://eel.is/c++draft/time.duration.cast)
- **Erlang:** the three modes and migration concern are real, but they are compatibility choices, not a warning that a flag inherently causes a time bug. The positive lesson is a separate monotonic engine plus observable wall offset changes; multi-time-warp is the modern default. [Erlang time correction](https://www.erlang.org/doc/apps/erts/time_correction.html)
- **SOFA/ERFA:** two-part JDs and stale leap tables are real; a single modern JD double loses fine timing resolution, not the ability to represent *any* fractional second. `iauTaitt` is a fixed `32.184s` addition; it does not apply `L_G`. [ERFA TAI→TT](https://raw.githubusercontent.com/liberfa/erfa/master/src/taitt.c)
- **Skyfield:** The critique overstates an inherent tens-of-µs limit. Its API supports separate whole JD and fractional components; collapsing them to one modern JD double loses precision. Preserve/export both parts where requested. [Skyfield time API](https://rhodesmill.org/skyfield/api-time.html)
- **Astropy:** two-double storage and location-dependent transforms are correct. Scale and format are not universally required: format may infer and scale commonly defaults to UTC. Leap/EOP handling can consult updateable files and auto-download, so “ships a table” is not its complete lifecycle. [Astropy Time](https://docs.astropy.org/en/stable/time/index.html), [IERS data access](https://docs.astropy.org/en/stable/utils/iers.html)
- **SPICE:** ET is TDB seconds past its J2000 reference in this interface; SCLK partitions, raw clock identities and kernel-sensitive reconstruction are real. Retain isolated contexts. Iterated geometric aberration/light time is not a complete relativistic signal model. [SPICE time](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/time.html), [SCLK](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/sclk.html), [aberration limitations](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/abcorr.html)
- **iCalendar:** exclusive `DTEND` is intentional interval semantics, not itself an off-by-one defect. `UNTIL` is not always UTC: DATE tracks DATE; floating local DATE-TIME tracks local; UTC/TZID starts require UTC termination. `THISANDFUTURE` orders by original recurrence IDs and shifts subsequent starts by the same difference, with duration rules; it is not an arbitrary future-rule migration. Native migration can reuse infrastructure while preserving these profile semantics. Floating time need not describe travel; it can mean the same local fields wherever used. [RFC 5545 §§3.3.10, 3.6.1, 3.8.4.4](https://www.rfc-editor.org/rfc/rfc5545.html)

## 3. Literal infallibility: the sound contract

- **Separate three questions:** valid syntax/fields; a unique value under selected definitions; agreement with real historical practice or future law. Compile-time execution can prove the first two for immutable inputs, not the third.
- **Sound without external data:** proleptic Gregorian field validity, astronomical numbering, unit/grid/range checks, exact frozen epoch/affine constants, explicit fixed-offset arithmetic under a specified supported scale. Validity of `2027-02-28` says nothing about jurisdictional adoption or a physical midnight.
- **Sound with frozen dependencies:** zone existence, leap-label validity, historical-calendar mapping, fold/gap detection and a deterministic resolving policy, **within the acquired pack’s applicable coverage**. The compiled artifact records the complete pack/algorithm/policy identity, including calendar and UTC dependencies, not only the text or zone name.
- **A policy is not universal totality:** `fold='later' gap='next'` cannot solve outside-coverage input, an unannounced month, a future era name, an exhausted finite range or a calendar with no next published boundary. A `Zone` brand proves the ID exists; it does not prove coverage for all local times.
- **Frozen resolved literal:** compile to the resolved coordinate and required compact projection facts. It is infallible as **that snapshot’s value**. Embed the necessary immutable facts, or acquire/verify the exact pack closure through a visible boundary before pack-dependent operations. Losslessly retaining an input label/resolution can use an optional richer record.
- **Different runtime tzdb:** never reinterpret a stored pack-local ID against arbitrary new bytes. The old value remains old. Formatting/recomputation under another pack is a named operation, potentially showing changed local fields or mapping. Re-resolving the original local appointment can produce a different instant, gap, fold or unresolved result.
- **Live appointment:** retain local fields, calendar/zone intent, policy and future-rule scenario. Compile-time checking can establish today’s construction validity; later resolution/migration stays data-dependent. Do not quietly bind a live appointment to a precomputed instant and claim current-law behavior.
- **`$time.require_future_rules`:** an explicit pinned-law scenario plus effective interval can discharge the obligation for a *conditional* answer. A terminal current-standard UTC segment is a valid such contract; no pack proves future governments cannot amend it. An observational calendar without publication stays pending. A conditional answer must not satisfy an unconditional real-world guarantee.
- **Stale build running years later:** distinguish age/publication/expiry from actual coverage and known supersession. Historical established leaps remain valid when a bulletin expires; forecasts/freshness requirements may fail. A frozen 2035 meeting built in 2026 remains reproducible, while its correspondence to 2035 law is unverified. Require updated context or return stale/unknown when current-law fidelity is requested.
- **Host tzdb disagreement:** expose both identities and the observed mismatch; report freshness as unknown if no trustworthy update information exists. An OS database can be older than the embedded pack. Host zone discovery also needs fallbacks for copied `/etc/localtime`, POSIX `TZ` strings, fixed zones and platforms without an IANA name.
- **Strictness boundary:** compile-time metatags select obligations; they cannot prove dynamic data or physical continuity by themselves. Runtime evidence checks may return values, as v4 allows. Proved hot-path operations can cost nothing; a claim that all seventeen obligations are only static flags must not suppress necessary validity checks.
- **Compiler boundary:** literals are ordinary delimited calls with compiler-provable results, not a promise that every string-taking call is evaluated at compile time. Embed/read pack dependencies through the build’s declared input mechanism; no compilation network fetch or arbitrary host-file dependence. Dewy’s current regex contract is a useful analogy, not proof that external-rule validity is equally timeless.
- **Error ergonomics:** prove constant checks away; validate runtime strings once; carry typed values and coverage capabilities. Keep genuine failures such as I/O, unavailable model, runtime fold/gap, overflow, clock reset and insufficient evidence visible. `or_throw` forwards them; it cannot turn them into infallible values.
- **Minimal acceptance:** compile the same literal with pack A/B that deliberately disagree; run A’s build with B present; remove A’s payload; cross its expiry; re-resolve its appointment under B; verify historical corrections never mutate the old fact. Repeat with a future leap regime and an unpublished calendar date.

## 4. Examples: corrections and a 15-example replacement set

### Corrections to the critique’s original fifteen

- **1–3:** `now`, bare zero-argument jobs and `@fetch` are idiomatic. Do not promise status-free subtraction across reset/generation failure; `within` requests cancellation, not forced termination. A 16ms frame is 62.5Hz, not exact 60Hz; sleeping the remainder can wake late.
- **4:** correct local weekly example; October 26 09:00 → November 2 09:00 New York spans **169 hours** under the named rules. A random civil period addition still needs handling when no compile-time proof excludes a fold/gap.
- **5:** 01:30 in New York encounters the autumn fold but **never** the spring 02:00–03:00 gap. Use two alarms or a zone whose transitions affect the selected hour; keep search failures distinct from no occurrence.
- **6:** 00:30 is not folded, so `fold='earlier'` changes nothing. The 00:30→03:30 shift spans **4 elapsed hours**; use 01:30 if demonstrating that the fold choice changes work duration. Payroll credit still requires the contract.
- **7–8:** a UTC rendering needs UTC rule data even though it needs no geographic zone. A default bare `Instant` print format must be specified. Localized output should expose/accept display loss without necessarily making known, acquired formatting resources fallible on every call; log I/O remains fallible.
- **9:** `Date` output alone does not remember month-end intent. Put the anchor on the recurrence/recipe and show a second increment; January→February alone cannot distinguish clamp from sticky month end.
- **10:** `2s` atomic and `1s` POSIX differences are correct for the stated endpoints; exporting the leap label itself is separately ambiguous/unrepresentable. An invalid leap label is not `OffGrid`.
- **11:** replace ancient `Z` with explicit TT or reconstructed UT1. DE440 covers approximately 1550–2650, DE441 approximately −13200–17191. A raw lunar position is not an eclipse prediction or apparent sky direction. ΔT is unused in the sketch; for terrestrial viewing, actually use it for Earth rotation and propagate its uncertainty. Do not attribute a Morrison/Stephenson historical reconstruction to an IERS observational service merely by naming it `iers.delta_t`. Preserve Julian/Gregorian source-calendar differences. [JPL DE440/441](https://ssd.jpl.nasa.gov/doc/de440_de441.html)
- **12:** choose solar/lunar and global/local event definitions; specify a TT/UTC window, Sun/Moon/Earth geometry, radii/limb conventions, numerical search budget and accuracy. Earth-surface path/visibility also needs Earth orientation/ΔT and a terrestrial frame. A lunar eclipse’s shadow falls on the Moon, so “shadow misses Earth” does not describe that event type. A conjunction missing eclipse conditions is not an eclipse.
- **13:** `sclk"…" clock=…` leaves a named argument outside the call; use `mission.sclk.parse("…")` or `sclk("…" clock=…)`. Correlation is not reception or execution until the raw count’s event role is specified. Latest-send planning needs decode/queue margins, execution uncertainty, transmission duration and contacts. `??<NoFeasibleWindow>` must leave missing kernels and convergence errors visible.
- **14:** MTC is a prime-meridian convention, so a Jezero site matters for LMST/LTST, not MTC. A clock-face convention does not itself specify Earth/Mars simultaneity. Proper time needs worldline, metric, endpoints and initial synchronization; `ship.elapsed(since=launch.nominal)` supplies too little. Avoid `let ship = ship.…` accidental shadowing. [Mars24 definitions](https://www.giss.nasa.gov/tools/mars24/help/algorithm.html)
- **15:** the example is era-ambiguous but does not show the rollover instant; corrected values are above. No generic conversion can identify an era solely from a truncated week.

### Replacement set

- **Notation/status:** all time APIs beyond existing Dewy syntax are provisional. `demo`/`mission`/`science` methods below are explicitly application helpers, whose stated contracts supply missing context; they are not claims of implemented stdlib names. Pure checked literals and proved operations are unwrapped; real partial boundaries use `or_throw` or a selective fallback. Parentheses remain for calls with arguments; arguments are space-separated. `@job` is the handle; `@job()` is redundant, not an eager invocation.

#### 1. Time a build, pace a game frame and bound a fetch

```dewy
let start = now
compile
let spent = (now - start) or_throw
printl"compiled in {spent}"
if spent <? 16ms { sleep(16ms - spent) }
let page = within(2s @fetch) ??<Timeout> cached
```

- Reading subtraction is the proposed monotonic contract; continuity failures propagate unless a capability proves them impossible. The sleep uses the selected suspend contract and can return late. Fetch errors other than `Timeout` remain visible. Use `1s/60` only with an explicit timer-grid rounding contract for a 60Hz target.

#### 2. A weekly meeting versus a fixed elapsed delay

```dewy
let meet = zoned"2026-10-26T09:00[America/New_York]"
let end = meet + 90minute
let weekly = meet.add(1week fold='reject' gap='reject')
let fixed = meet + 168hour
```

- Under the pinned rules: `weekly` is November 2 09:00; `fixed` is November 2 08:00. The civil operation is proved infallible for these constant inputs. Dynamic local fields or uncovered dates still return resolution/coverage failures.

#### 3. Daily alarms that actually exercise both gap and fold

```dewy
let early = recurrence(zoned"2026-03-01T01:30[America/New_York]"
    every=1day fold='earlier' gap='reject')
let late = recurrence(zoned"2026-03-01T02:30[America/New_York]"
    every=1day fold='earlier' gap='preserve_displacement')
let batch = late.expand(window limit=20 work=10000) or_throw
```

- `early` tests the November fold; `late` shifts March 8 02:30 to 03:30. The window is explicit and pack-covered; unfinished work returns a cursor. Contrast native resolution with importing an RFC5545 explicit gap value versus an RRULE-generated gap, which is omitted. A fold-all profile preserves branch IDs.

#### 4. Invoice anchors and birthdays

```dewy
let jan = date"2027-01-31"
let feb = jan.add(1month overflow='clamp')
let march = feb.add(1month overflow='clamp')
let invoices = recurrence(jan every=1month anchor='month_end')
let age = date"2000-02-29".age(on=date"2027-02-28" leap_day='march_1')
```

- February 28, repeated-clamp March 28, anchored March 31, age 26. A legal threshold needs a jurisdiction profile; generic age is not legal advice encoded as a default. Ordered month/day recipes also demonstrate noncommutativity.

#### 5. Durable log and human display

```dewy
let stamp = now.nominal
let payload = demo.encode_instant(stamp)
log.write(payload) or_throw
let shown = demo.display(meet locale='fr' profile='nominal')
printl(shown.text)
```

- `encode_instant` emits a tagged integer/epoch/tick schema; it never puts a 128-bit integer into an inexact JSON number. `display` uses acquired pinned resources and returns text plus declared losses; retain them when strict loss accounting requires it. Rendering UTC needs the chosen UTC pack, while geographic tzdb is unnecessary. Record identity includes whatever richer intent/evidence the application chose to persist.

#### 6. Archived leap, old UTC and a synthetic negative leap

```dewy
let before = utc"2016-12-31T23:59:59"
let leap = utc"2016-12-31T23:59:60"
let after = utc"2017-01-01T00:00:00"
printl"{after.nominal - before.nominal}"
let apollo = utc"1969-07-20T20:17:40"
let skipped = demo.resolve_negative_leap_fixture
```

- Output duration `2s`; Apollo’s nominal coordinate is the verified integer above. The fixture rejects the removed label and verifies neighboring atomic positions and adapter outcomes. POSIX export of `leap` needs a named loss/phase policy. Test current/stale packs on both sides of the 2027 transition without hardcoding the inherited offset.

#### 7. Sub-ns science, exact codecs, scale maps and GPS eras

```dewy
let q = demo.j0_tt_coordinate + 1ns/3
let rounded = q.quantize(tick=1ns rounding='nearest_even')
let tcg = q as Coordinate<TCG>
let packet = demo.decode_ntp(raw era=era_evidence) or_throw
let again = demo.encode_ntp(packet) or_throw
let gps_value = gps(week=0 tow=0s width=10)
let gps_2019 = gps_value.resolve(era=2) or_throw
```

- `q` is an exact TT coordinate; it is never silently stored in ns `Instant`. Quantization reports original-minus-rounded loss; exact TT→TCG divides by `1−L_G`. NTP raw payload round-trips without normalization. GPS resolves to 2019-04-07 00:00 GPS, with no current-era heuristic. Add a shared-error fixture `X=10s+E`, `Y=13s+E`: `Y−X=3s`; marginal-only data instead yields `[1s,5s]`.

#### 8. A historical calendar and an incomplete source date

```dewy
let old = demo.british_date("1752-09-02")
let following = old.add(1day)
let exceptional = demo.swedish_date("1712-02-30")
let source = demo.partial_historical_date(year=1712 month=2)
```

- Helpers select named acquired historical calendars; `following` is September 14, the Swedish date is valid there, and `source` invents neither a day nor a midnight. Source calendar/year style, competing interpretations and authority remain attached when converting a document claim.

#### 9. A crescent-publication gathering after sunset

```dewy
let gathering = demo.community_gathering(calendar=community
    boundary=sunset offset=30minute publication='require_authority')
let plan = gathering.plan(window work=10000) or_throw
```

- `community` pins the authority’s month/day mapping; `sunset` independently pins site, horizon/refraction and solar model. Plan separates known occurrences, missing polar sunset and pending publication. New authority evidence resumes a bounded plan, preserving original occurrence keys and solar-time uncertainty.

#### 10. A calendar edition and an urgent rule update

```dewy
$time.require_future_rules
let appointment = demo.local_appointment(meet scenario=rules_a)
let preview = demo.preview_update(appointment from=rules_a to=rules_b
    window=planning_window) or_throw
```

- `rules_a` is an explicit effective-dated scenario, not a timeless prediction. The application reviews changed future occurrences before migration. Source edition selects the bare calendar at definition site; a public `Date<Gregorian>` signature and stored calendar identity stay fixed. Old resolved facts remain old; missing or expired required evidence returns a value.

#### 11. Payroll, legal boundaries and an auditable distributed record

```dewy
let shift = zoned"2026-11-01T00:30[America/New_York]"
let done = zoned"2026-11-01T03:30[America/New_York]"
let elapsed = done.nominal - shift.nominal
let credited = demo.credit_shift(shift done rules=payroll) or_throw
let assertion = demo.record_shift(credited valid=shift_span known=commit_id)
let decision = demo.authorize_until(expiry trusted_reading policy=expiry_policy)
```

- Elapsed nominal atomic duration is `4hour`; credit requires the payroll rule and breaks. Legal/all-day boundaries are explicit interval sets, not user display zones. Corrections append valid/knowledge-time assertions. Expiry overlap produces the policy’s defer/reject/permit outcome; equal timestamps never replace event IDs, vector causality or a lease/fencing protocol. A restored monotonic TTL needs a new boot/recovery decision.

#### 12. Ancient sky direction with honest coverage and ΔT

```dewy
let tt = science.tt_calendar("-0584-05-28T12:00:00" calendar=gregorian)
let rotation = science.ancient_rotation(tt model=ancient_delta_t) or_throw
let sky = science.apparent_direction('moon' at=tt observer=ancient_site
    ephemeris=de441 rotation=rotation model=apparent_sky) or_throw
```

- This is a hypothetical **proleptic Gregorian TT** coordinate, not the asserted time of a historically recorded eclipse. `ancient_delta_t` is an acquired reconstruction with stated coverage/error, e.g. an identified Morrison/Stephenson model. `rotation` actually uses `UT1=TT−ΔT`; apparent direction also needs site, frame, precession/nutation, propagation and optional refraction conventions. DE441 covers the epoch; the output remains uncertain. A source reported in Julian or another calendar needs its own interpretation first.

#### 13. A modern eclipse search

```dewy
let first = instant"2026-01-01T00:00:00Z"
let last = instant"2028-01-01T00:00:00Z"
let window = interval(first last)
let events = science.eclipses(window kind='solar' ephemeris=de440
    rotation=eop_model geometry=eclipse_geometry tolerance=1s work=100000) or_throw
```

- Window is half-open with explicit UTC-to-axis snapshot interpretation. The solver uses Sun/Moon/Earth trajectories, appropriate TDB time arguments, radii/limbs, frame and Earth-orientation model. EOP coverage/prediction error must satisfy the request or fail honestly; solver residual `1s` is not a certified physical error of `1s`. Global event existence differs from visibility at a chosen site. Lunar searches require a distinct shadow/visibility definition. Do not emit non-eclipsing conjunctions as eclipses.

#### 14. A rover command and proper elapsed time

```dewy
let onboard = mission.sclk.parse("1/1465644281.0") or_throw
let execution = onboard.correlate(model=mission.clock_kernel) or_throw
let send = mission.latest_send(execute=execution contacts=contact_plan
    processing=decode_and_queue transmission=command_airtime) ??<NoFeasibleWindow> none
let proper = time.proper_elapsed(mission.ship launch_event arrival_event
    model=mission.relativity) or_throw
```

- The SCLK value is illustrative and explicitly denotes an execution target. Correlation retains partition/native ticks and gives a target-domain estimate. Planning solves moving endpoints with the named geometric/gravitational/media/hardware profile, uncertainty and contact margins; no send side effect occurs. Round-trip ranging has separate legs and turnaround. Proper elapsed time uses endpoints on the ship’s worldline with a metric/initial synchronization contract; coordinate subtraction cannot replace it.

#### 15. Earth, Mars, lunar status and a distant convention

```dewy
let earth = instant"2027-03-01T09:00:00Z"
let event = demo.mars_event(earth convention=mission.simultaneity) or_throw
let mtc = demo.mars_clock(event convention='mtc' model=mars24)
let local = demo.mars_clock(event site=jezero convention='lmst' model=mars24)
let lunar = demo.lunar_coordinate(lunar_event definition=tcl_definition) or_throw
```

- MTC needs no Jezero longitude; LMST does. The event transform’s simultaneity convention is separate from either clock face. Match the named Mars24 convention, not physical rotation to infinite accuracy; a Mars hour is not `3600s`. An unavailable requested operational LTC realization yields `StandardNotDefined`. A distant settlement selects a chart/metric and local clock; an interstellar ephemeris or universal remote `now` is never inferred from these APIs. [Mars24](https://www.giss.nasa.gov/tools/mars24/help/algorithm.html), [CGPM lunar-time resolution](https://www.bipm.org/en/cgpm-2026/resolution-6)

## 5. Prior-art gaps neither draft fully closes

- **Temporal/Jiff — period equality and balancing:** ordered recipes need separate structural equality, equality of their result at an anchor, and comparison/totalization relative to a calendar/zone. `1month` and `30day` cannot have context-free elapsed ordering. Define canonicalization without discarding operation order; do not give recipe hashes a context-dependent equality. [Temporal relative-duration operations](https://tc39.es/proposal-temporal/docs/duration.html)
- **Erlang — notifications are part of a clock service:** v4 says wall appointments re-evaluate, but neither text defines subscription registration versus correlation-change races, lost updates, sequence numbers or resync after overflow. Specify an atomic snapshot+subscription or recheck protocol; include leap-segment effective changes. Otherwise a correct recurrence can still arm against a stale correlation. [Erlang time-offset monitoring](https://www.erlang.org/docs/18/apps/erts/time_correction.html)
- **Rust environment unsoundness — capturing once is insufficient:** a single host-zone lookup can still race with another thread/FFI mutating environment state. Use platform-safe discovery and an audited acquisition boundary, not merely “only once.” [RustSec local-time advisory](https://rustsec.org/advisories/RUSTSEC-2020-0071.html)
- **SPICE/Astropy/Skyfield — value exactness versus source-bit fidelity:** exact rational sum does not preserve two-part decomposition, negative zero, NaN payloads, original precision or source formatting. Define numerical, semantic and byte-for-byte round-trips separately, and retain raw payload when promising the last. A float export needs a rounding cell/error contract, not just a global “quantum.” [Astropy numerical formats](https://docs.astropy.org/en/stable/time/index.html)
- **NTP/PTP — external sentinels:** Dewy’s core “no sentinels” rule does not eliminate them on the wire. NTP zero/LI-unsynchronized and PTP correction overflow become explicit adapter variants, with raw bits preserved; arithmetic must not reinterpret them as ordinary times/corrections. [RFC 5905 §6](https://www.rfc-editor.org/rfc/rfc5905.html#section-6), [IEEE interpretations](https://standards.ieee.org/wp-content/uploads/import/documents/interpretations/1588-2008_interp.pdf)
- **RFC 9557 — offset provenance:** its update treats `Z` as a known UTC time with unknown local offset, like `-00:00`; `+00:00` has a different stated preference. v4 mentions unknown-local-offset semantics but never specifies this updated `Z` distinction. Preserve annotation criticality/offset-conflict behavior already in v4 and add this profile-specific metadata rule. [RFC 9557 §2](https://datatracker.ietf.org/doc/html/rfc9557#section-2)
- **iCalendar — duration and alarms are executable semantics:** distinguish nominal `P1D` from exact `PT24H`, preserve component addition order across discontinuities, relative `VALARM` start/end basis, repeated alarms, DATE event default duration and exclusive ends. v4’s general period model is capable, but its RFC profile never states these mappings; a parser that only preserves RRULE is incomplete. [RFC 5545 §§3.3.6, 3.6.1, 3.6.6](https://www.rfc-editor.org/rfc/rfc5545.html)
- **Edition migration — default calendar is not the whole serialization story:** define definition-site edition capture for generics, plugins and dynamic modules; stable explicit calendar identities; wire schema negotiation and data algorithm versioning. Two editions sharing a compact representation must not accidentally unify distinct calendars. Extensible observational calendars cannot freeze their future data merely by using `Date<Calendar>`.
- **Clock incarnations after snapshot/restore:** a restored VM/process can resurrect the same provider handle/generation, and a cloned image can duplicate it. Specify host/provider continuity attestation or remint domains; process-local small IDs need a no-ABA lifetime contract. Persistent envelopes need portable incarnation identity. This is not solved by a 32-bit generation field.
- **Acceptance additions:** counter-domain reset during a timed callback; copied reading before/after re-sync; pack-handle reuse; maximum-grid endpoint normalization; pre-1972 nanosecond input off-grid on mapping; NTP zero/PTP overflow; old literal under incompatible tzdb; comparison of differently anchored periods. These are focused counterexamples, not a request for another broad survey.

## Decisions David must make

- **Default grid/escape contract:** recommend ns for ordinary `Instant`, with explicitly selected integer ticks and exact branded coordinates/native codecs retained. Unblocks off-grid math and zero-loss interchange. Default layout belongs with the representation/performance review; do not reopen J0/integer ticks. Reversible before ABI publication; wire meaning is costly later.
- **Easy clock operators and date convenience:** recommend reading subtraction → monotonic difference and reading+duration → typed deadline, with named nominal wall operations; choose whether `today` means nominal date or supported-date answer and expose both. Unblocks the ordinary examples. Behavioral change needs approval; reversible before release.
- **Infallible literal meaning:** recommend a frozen, pack-identified resolved value; live local appointments remain intent with explicit migration. Strict future-rule answers stay conditional on named scenarios. Unblocks removing incidental `or_throw`s without hiding uncertainty. Reversible API spelling; persisted semantics costly.
- **Evidence retention versus common record weight:** recommend a compact ordinary value plus a detailed acquisition operation or stable historical evidence token; `.estimate` must return unknown if old evidence was discarded. Unblocks honest lazy detail and dependence. Internal layout reversible; lost evidence is unrecoverable.
- **Calendar defaults and periods:** recommend definition-site edition defaults, explicit calendar identities in public/persisted types, and `day`/`week` as calendar periods (`week` = seven day successors; other cycles explicit). Keep existing calendar-only month/year. Unblocks source evolution and DST-safe examples. New surface/default semantics need approval; reversible before release.
- **What remains from v4’s open list:** recommend half-open convenience with full topology retained, separate intent/occurrence/event/observation, individually scoped strict obligations and the suspend-inclusive default with active-time alternative. Decide the outstanding defaults, not the already fixed `now`/`@job` spelling. Names can change; discarded intent, altered wait behavior and serialized policy meanings cannot be repaired transparently.

- **Verification limit:** this is one design/fact-check pass, not a compiler conformance run. Exact epoch and civil-duration calculations were independently checked; the proposed APIs/examples were not executed. No repository files were edited and no compiler tests were needed for this external report.
