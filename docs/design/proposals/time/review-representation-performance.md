# Review: time core, representation and performance

- **Scope:** one focused design pass; acceptance is a concrete recommendation for each of the five requested items, a replacement §5 example, and a complete approval list for this review. Owned output: this file only. No repository edits, implementation, comprehensive standards audit, or duplicate correctness survey. Budget: one reading/review pass, a small arithmetic code-generation probe, and targeted primary-source checks; no optimization campaign.
- **Inputs read:** v4, the v4 critique/brainstorm, GOALS, decisions, assumptions, precision inference, `$build`/`$target` rules, and relevant LANGUAGE syntax. Recommendations below are proposals for David, not adopted semantics.

## BLUF

- Adopt **plain `Instant` = signed int128 nanoseconds since J0**, exactly 16 bytes. Keep tick and storage width independent; reject the critique's tick-dependent default-width heuristic.
- Give plain **`Duration` the same 16-byte storage**, with explicit 8-byte forms. Exact arithmetic widens intermediates; fixed storage requires proof or a checked conversion. No wrapping, saturation, implicit heap promotion, or time-specific exception to Dewy's integer rules.
- Int128 add/subtract costs **two arithmetic instructions** on x86-64 and AArch64, versus one for int64. The material costs are doubled storage/register use and software general division, not bigint arithmetic on every timestamp.
- Keep a **32-byte pointer-free `ClockReading`**, but make clock identity include provider and generation. Its subtraction measures monotonic elapsed; `.nominal` asks the wall question. Dynamically incompatible readings remain fallible.
- Do not fabricate wall time from a permanently cached offset. Portable `now` takes **two clock samples**; strict correlation takes a bracket or a provider-supplied paired sample. Elapsed-only calls need only the monotonic clock.
- A total stale wall reading can be useful; a stale monotonic sample must **never produce a successful zero elapsed time or early successful sleep**. Continuity failure must reach the task boundary or an explicit result.
- Keep scale-branded exact science coordinates, preferably by specializing v4's `TimePoint<Domain>` machinery. A finer tick cannot turn TT into TCB, UT1, or a spacecraft clock.
- Literal validation eliminates actual parsing/resolution failures only with **known definitions, pinned data, coverage, unique resolution, grid and range proofs**. It does not establish future law or physical accuracy.
- Put editions and pack selections in **`.dewy` source metatags/constants**, with definition-site semantics across imports. Editions govern source defaults; packs govern dated rules; neither renumbers old instants.
- The critique is directionally right but overstates cheapness and infallibility. In particular, Go `Add` retains monotonic data, width overflow is not `OffGrid`, old readings cannot acquire historical accuracy from today's calibration, and ancient `Z` labels do not become valid merely because int128 has enough range.

## 1. Representation, arithmetic, coordinates and `OffGrid`

- **Recommendation — storage and numbers:**
  - `Instant` abbreviates `Instant<tick=1ns width=128>`; signed integer count, fixed J0, no per-value denominator, tag, calendar, or heap allocation.
  - `Duration` abbreviates `Duration<tick=1ns width=128>`. Its zero is a difference, not an epoch. Domain-branded differences remain branded; an observer's proper duration is not implicitly a TT-coordinate difference.
  - `width` stays 128 when only `tick` changes. Explicit `width=64` selects compact storage. A type's footprint must not jump because its tick crosses an arbitrary million-year threshold.
  - Half-ranges below use exactly 31,557,600 seconds per Julian year; endpoints differ by one tick because signed ranges are asymmetric.
  - Signed 64-bit nanoseconds: **±292.271 years**, 8 bytes; J0 places endpoints approximately in 1684–2269. Fine for explicitly bounded contemporary storage, unsuitable as the millennial default.
  - Signed 64-bit microseconds: **±292,271 years**, 8 bytes; loses nanosecond inputs unless divisible. Milliseconds: **±292 million years**; seconds: **±292 billion years**. More range does not compensate for losing an input's quantum.
  - Signed 128-bit nanoseconds: **±5.391448762×10²¹ years**, 16 bytes. Covering ±10,000 years requires **70 signed bits**; ±1,000,000 years requires **76**.
  - One million timestamps occupy **16 MB** rather than **8 MB**, excluding container metadata; a 64-byte cache line holds four rather than eight. This is a real tradeoff for logs and simulations, even though arithmetic is cheap.
  - A seconds-plus-nanoseconds pair normally occupies 16 bytes after alignment and needs normalization/carry rules. It helps formatting and matches common C interfaces, but is a worse default integer-tick model. A packed 96-bit count saves four bytes in storage and complicates alignment/ABI; leave it as an explicit representation, not the default.

- **Recommendation — arithmetic cost:**
  - Tiny Clang 23.1.4 `-O2` probes, generated for x86-64 and AArch64 in scratch, confirmed: add = `add/adc` or `adds/adc`; subtract = `sub/sbb` or `subs/sbc`. Counts exclude register moves, loads, returns, and any required proof/check.
  - Equality used two XORs plus OR and flag materialization on x86-64; compare/conditional-compare/materialization on AArch64. Ordered comparison examines the signed high word and unsigned low word. No universal cycle count follows from these instruction counts.
  - Low-128-bit multiplication used three x86 multiply instructions plus two adds; AArch64 used four multiply/multiply-add instructions. **This is not a full exact 128×128→256 implementation**; Dewy must retain the upper product where required.
  - General signed 128-bit division called `__divti3` on both targets. Constant divisors can lower differently; formatting and general tick conversion are the expensive cases to isolate. Point addition/scaling is already invalid, so ordinary timestamp arithmetic needs neither general multiplication nor division.
  - Int128 is two general-purpose register words, not automatically one SIMD arithmetic lane. Four timestamp loads per cache line do not imply a vectorized four-way 128-bit carry chain. ABI return/pass rules vary; a 32-byte record often passes indirectly when not inlined.
  - These are backend feasibility observations, **not Dewy benchmarks or measured speedups**. Before implementation lands, inspect Dewy's lowering and use its existing instruction-count/flagship gates; do not add a time-specific compiler pass without a measured need.

- **Recommendation — preserve Dewy's exact integer rules:**
  - Width constrains **stored counts**, not intermediate mathematical results. `max - min` of two int128 counts needs **129 signed bits**; 128-bit operands alone do not prove a 128-bit duration result.
  - A bounded expression can use additional machine limbs without heap allocation. Preserve exact count/range facts through the time wrapper; narrow at annotated binding, field, argument, return, or conversion. An unannotated result must retain the necessary wider count representation when its range requires it, rather than silently becoming the 16-byte alias.
  - This requires the same deferred-narrowing behavior already decided for fixed integers. It is a concrete implementation obligation for time operators, not permission to pretend that an ordinary function returning `Duration` can return 129 bits.
  - `Instant + Duration` keeps its tick; range widening does **not** authorize automatic tick refinement. An off-grid operand needs proof, explicit conversion, or an explicitly finer destination.
  - A failed proof is a compile diagnostic, not an `OutOfRange` value. A checked `convert<T>` returns `OutOfRange` for an actual range failure. `$runtime_checks` retains its existing explicit trap policy. Do not make all `+` and `-` operations return overflow unions.
  - Do not extrapolate the existing bounded-counter axiom to arbitrary int128 timestamps. The enormous range is not a proof. Normal `now.nominal + 5s` can be proven using the much smaller range supplied by the OS adapter; two unconstrained imported endpoints cannot.
  - Under `$bulletproof`/`$no_assumed_bounds`, retain those real bounds, require guards or checked conversions at untrusted boundaries, and expose any environmental/provider assumptions separately. No hidden bigint escape hatch.
  - Calendar periods are separate from fixed `Duration`. Keep `1ns/3` as a legal exact quantity expression; it simply is not a plain nanosecond duration. Exact decimal `0.1s` is **100,000,000 ns** and must not be treated like an already-rounded binary float.

- **Recommendation — `OffGrid` and conversion:**
  - `OffGrid` means the exact value is not an integer multiple of the destination tick. `OutOfRange` means the integer count does not fit. An invalid leap label, missing era, absent model, or unresolved domain is neither.
  - `as` requires established exactness, domain compatibility and range. `convert<T>` is the value-returning checked boundary. On failure, diagnostic detail can describe remainder and bounds without placing a rational payload in every successful value.
  - `quantize` requires an explicit rounding policy and returns value plus signed loss, **original minus rounded**. It can still fail for range/domain reasons. Rounding must not saturate silently.
  - Example: `−0.25s` decomposed at a 1-second tick gives count −1 and remainder 0.75s. Rounding `1ns/3` to nearest-even nanoseconds gives 0ns and loss +1ns/3.
  - For cross-tick comparisons, either prove an exact conversion or compare scaled integers in sufficiently wide intermediates. Equality is mathematically defined even when one direction of conversion fails; lack of divisibility does not make equality inherently erroneous. Start with explicit conversion and homogeneous hash-key types; defer heterogeneous hash canonicalization.
  - A representable successor exists except at a finite maximum. Do not erase interval endpoint flags merely because the storage is discrete: rewriting `[a,b]` to `[a,b+tick)` fails at max and changes endpoint-distance calculations. Arithmetic calendar-day domains can also have successors; the critique's blanket ban there is wrong.

- **Recommendation — science coordinates:**
  - Keep a science-only `Coordinate<Scale>` as an exact affine coordinate with a statically named origin/definition and rational seconds representation. Prefer an alias/specialization of `TimePoint<Domain>` over a competing point algebra. `Scale` must resolve to a complete domain definition, not just a string such as `TCB`.
  - A named constant tick is sufficient for an NTP binary fraction, PTP correction, or a fixed affine transform whose denominators are bounded at compile time. It is insufficient as the sole interface for runtime rational input, arbitrary model composition, and all the distinct scientific domains.
  - `Instant<tick=1ns/3>` remains an **Instant specialization** on TT/J0. It is not the plain `Instant` alias, but the critique's claim that it is not an instant is misleading.
  - A rational science coordinate is not a physical observation or exact solution of an approximate model. Such transforms return `Estimate<Coordinate<Scale>>` or bounded numeric results with model errors. Raw SCLK remains a clock-domain count until correlation.
  - Keep rational dependencies, denominator growth and allocation entirely outside the core. Merely using `now`, `Duration`, or `Instant<tick=1ns/3>` must not load science code.

- **Dewy examples** — conversion names here remain proposals:

```dewy
let t:Instant = instant"2026-10-24T12:00:00Z"
let small:Instant<tick=1ns width=64> = t as Instant<tick=1ns width=64>
let delay:Duration<tick=1ns width=64> = 300ms
let fine = (t as Instant<tick=1ns/3 width=128>) + 1ns/3
let checked = convert<Instant>(fine)                 # Instant | OffGrid | OutOfRange
let [value loss] = fine.quantize(tick=1ns rounding='nearest_even')
printl(loss =? 1ns/3)
let tt = t as Coordinate<TT>                        # representation/domain definition conversion
# t + 1ns/3                                       # grid obligation fails
```

- **Alternatives:** int64 ns for explicitly bounded workloads; int64 µs when microsecond loss is an accepted input contract; seconds/subseconds for C adapter structs; fixed specialized ticks instead of rationals when a pipeline has a statically bounded denominator. Reject a rational plain `Instant`, width heuristics, and default saturating arithmetic.
- **New spellings/semantics:** `width` on `Instant` and `Duration`, `Duration<tick=…>`, `Coordinate<Scale>`, `OffGrid`, checked generic `convert<T>`. The tick spelling, `quantize` and `TimePoint` already occur in v4 but remain proposals. Deferred narrowing through time operators needs explicit acceptance/implementation, not new punctuation.

## 2. `now`, `ClockReading` and predictable costs

- **Recommendation — semantic split:**
  - Adopt monotonic `now - start`; adopt `now + 5s` as a `MonoPoint` deadline. `.nominal` extracts the TT/J0 wall coordinate; `now.nominal + 5s` is a wall target.
  - v4 teaches the familiar wall-clock stopwatch mistake. It does not literally repeat current Go behavior: Go already uses monotonic subtraction when both operands have it. Its troublesome property is fallback to wall semantics within the same type after monotonic information is lost.
  - Go `Add` preserves/advances both samples; `AddDate`, rounding, zone conversion and serialization can remove monotonic information. Go's `==` compares representation fields; it does not itself strip them. [Go time source](https://go.dev/src/time/time.go)
  - Never deserialize a `ClockReading` as a fresh live reading. Serialize its explicit wall instant or a separately typed observation. Do not let absence of monotonic data choose the meaning of `-` at runtime.
  - Reading equality compares its semantic record fields, not “same physical event”; wall equality is `a.nominal =? b.nominal`. Define these rather than inheriting bytewise comparison of padding.

- **Recommendation — exact ordinary layout on 64-bit targets:**
  - Bytes **0–15:** `nominal`, signed int128 nanoseconds from J0.
  - Bytes **16–23:** normalized monotonic nanoseconds, signed int64 restricted to **0..2^63−1** within a captured session.
  - Bytes **24–27:** process-local uint32 domain token, uniquely identifying **provider instance + reset generation + tick/suspend contract**. Two test clocks starting at zero must have different tokens.
  - Bytes **28–31:** uint32 state word; reserve bits for wall freshness/quality, identified convention, and correlation quality. These are observations/capabilities, not proof of synchronization or accuracy. Unknown must be representable. Keep the bit layout internal.
  - Total **32 bytes**, 16-byte alignment for this proposed internal layout, no pointers. Metadata needed for acquired providers lives once in the captured context. Compact IDs do not magically eliminate provider lifetime management.
  - Tokens are not globally persistent IDs; they cannot be reused while any reading can survive. Registry/token exhaustion is an explicit resource boundary, never wraparound. An ordinary context registers once; reads allocate nothing.
  - A 64-bit tick field is a **bounded session representation**, not a promise of ten thousand years' uptime. Long-running or raw-native-tick providers can use a separately specialized `MonoPoint`; retiring a session requires an explicit continuity/rebase contract. Do not silently wrap.

- **Recommendation — sampling and cost:**
  - Portable healthy `now`: one wall read + one suspend-inclusive monotonic read, conversion from normalized wall seconds/subseconds to int128, current UTC/POSIX segment-offset addition, and a 32-byte result construction. Provider state/segment checks are constant-time on the current segment; no zone, locale, ephemeris, rational, per-reading allocation, or full history search.
  - **No fixed nanosecond latency claim:** vDSO/shared-page availability, syscalls, clock source, virtualization and contention determine it. Go's Linux amd64 adapter actually calls the clock interface twice, once for realtime and once for monotonic; it does not establish the critique's claimed single-read cached-offset design. [Go runtime adapter](https://go.dev/src/runtime/time_linux_amd64.s)
  - The ordinary two samples are acquired during the same operation, **not asserted simultaneous**. `nominal` is the wall sample's coordinate; the monotonic field is the elapsed sample's coordinate. Subtraction never estimates a wall offset.
  - Strict cross-clock correlation uses monotonic-before, wall, monotonic-after, plus a stable provider/correlation revision, or an OS/hardware paired facility. A bracket bounds acquisition ordering, not physical clock accuracy or a hidden wall step. A changed revision yields an unresolved/discontinuous correlation, not a false tiny error bar.
  - A true shared-page snapshot of both clock mappings can optimize this. A cached user-space wall offset alone cannot track steps, slews or source changes. Maintaining a background synchronizer has costs and assumptions; do not hide one in `now`.
  - The UTC offset cache includes its validity interval and next transition. Cross a known transition and update it even if the pack is unchanged; a backward wall jump can also leave the segment. Unknown smear/leap phase stays explicit. A cached offset is not a license to label an ambiguous POSIX sample exact UTC.
  - Default adapters may expose normalized nanosecond readings from a non-nanosecond counter; that is a declared measurement quantization. Preserve raw count/tick and quantization bounds in the detailed acquisition API when required. Never claim integer storage proves nanosecond accuracy.
  - Elapsed-only `time.elapsed(@work)` or `monotonic` reads **one clock per endpoint**. Keep this route cheap even if compiler field elimination cannot remove unused wall acquisition from a full `now` call.
  - Same-session subtraction: one int64 subtract; the nonnegative count invariant proves its signed result fits. Widening into plain `Duration` is sign extension, not heap promotion. Dynamic domain identity adds a token comparison and failure branch. Without the count invariant, arbitrary int64 subtraction requires 65 bits.
  - `now + 5s` has both grid and range obligations. Ordinary provider/session bounds should expose enough deadline headroom to prove this literal addition; near an exhausted horizon, checked deadline construction or a wider provider is required. Huge dynamic delays are not made total by calling them durations.
  - Display: duration formatting performs integer unit selection; displaying `.nominal` as UTC additionally requires a valid UTC relation and Gregorian field conversion; local display additionally needs zone data. Load these only when formatting is used. No current UTC coverage means display a marked unresolved representation/raw coordinate, not a fabricated `Z` label. Allocation belongs to the chosen formatting sink, not acquisition.

- **Recommendation — trivial success and honest failure:**
  - Capture configuration identity at scope/task entry; acquire only reached capabilities, at first use or explicit context preparation. Static reachability can prepare the needed clock at task entry, but an unused cold feature must not force unrelated packs to load.
  - Successful ordinary reads from one captured context carry a **static same-session brand/refinement**, permitting infallible `now - start`. The task's declared acquisition/continuity failure channel prevents a failed session from returning a new, apparently compatible sample.
  - General runtime-selected `ClockReading` subtraction returns `Duration | DomainMismatch`; a proven same domain removes that alternative. The token is still required for dynamically mixed values. No new generic-parameter spelling is necessary for an inferred brand.
  - If the monotonic provider breaks, fail the enclosing operation/task through that declared channel before returning a successful new reading. A strict API exposes the failure as a handled result/capability. No silent fallback to wall subtraction and no “stale monotonic means elapsed zero.”
  - Losing wall synchronization can retain a valid monotonic sample. Mark wall holdover/staleness; elapsed still works. If no wall seed was ever acquired, initialization fails rather than inventing epoch zero.
  - Under `$time.require_clock_domain`, demand the suspend/continuity contract; under `require_clock_accuracy`, demand acquisition/calibration evidence; under `require_resources`, expose setup/lifetime failures. These must be included in `$bulletproof`; “clock always works” cannot become an undocumented axiom.
  - Suspend: default elapsed includes suspension; a five-second deadline can expire while asleep and run only after resume. `clocks.active` explicitly excludes suspension. Unsupported capability fails setup; no substitute and no implied wake-device guarantee.
  - VM migration/pause: retain the domain only when the provider preserves the declared rate, elapsed/suspend semantics and continuity. Otherwise terminate the old session or report discontinuity. A counter that merely never decreases does not prove elapsed time survived migration correctly. Undetectable hostile rollback requires an explicit trust assumption; a token alone cannot detect it.
  - Wall steps leave the monotonic domain and deadlines alone. Wall subtraction may be negative; wall appointments re-resolve/re-arm under their own policy.
  - An old 32-byte reading cannot retrospectively reconstruct its acquisition bracket or historical error model from today's provider state. `.estimate` must return unknown/missing evidence or use evidence retained **at acquisition**. Offer rich acquisition separately; never start an unbounded hidden archive to make the cheap struct look complete.

- **Dewy examples:**

```dewy
let start = now
work
printl"took {now - start}"
let deadline = now + 5s
let wall_target = now.nominal + 5s
let page = within(2s @fetch) ??<Timeout> cached

loop true {
    let frame = monotonic
    draw
    let spent = monotonic - frame
    if spent <? 16ms { sleep(16ms - spent) }
}
```

- **Alternatives:** two reads for portable ordinary `now`; three for correlation evidence; a platform atomic snapshot where actually available; monotonic-only reads for frame timing. Making every default subtraction a union is honest but inferior ergonomics; making every reading contain an estimate is inferior storage. The captured-session/task-failure contract is what permits the short program.
- **New spellings/semantics:** no extra public fields beyond `.nominal` are required by this layout. `ClockReading`, `MonoPoint`, `monotonic`, `clocks.active`, `with_context` and the strict tags are v4 proposals; approve the changed `-`/`+`, successful-session branding and explicit task failure behavior. Internal domain-token/state fields are not new user surface.

## 3. Literal infallibility and the replacement §5 example

- **Recommendation:** treat literal constructors as checked compile-time evaluations, using Dewy's existing constant/fact machinery. A unique proven success is a plain value; a known malformed or unresolved required literal is a diagnostic. No new literal grammar or global time-analysis pass.
- **What can be checked:**
  - Lexical grammar, digit/field bounds, arithmetic-calendar validity, explicit scale/epoch, rational tick divisibility, destination range, and named policy validity.
  - Constant zone identity, local gap/fold candidates and selected branch **against an available pinned pack and its declared coverage/scenario**.
  - A UTC leap label only with the relevant UTC definition/transition data. Ordinary date validity needs no UTC or zone pack.
  - Literal arithmetic such as January 31 plus one month with `overflow='clamp'`, and completed anniversaries with a necessary leap-birthday policy, can be evaluated fully. Non-leap birthdays need no irrelevant leap policy.
  - Reject unsupported constant evaluation rather than silently inserting an infallible runtime promise. Use the runtime parsing API for intentionally fallible inputs, including tests of invalid literal strings.
- **What remains fallible or conditional:**
  - Runtime text, runtime pack lookup/acquisition, unknown coverage, unannounced observational calendars, ambiguous local fields without a policy, and runtime range/grid checks.
  - A validated `Zone` removes an unknown-name error, not missing future coverage or nonexistent astronomical boundaries. `fold='later' gap='next'` cannot make every possible calendar/zone operation total.
  - Future literals are exact **under their pinned rules/scenario**, not promises about future government decisions. `$time.require_future_rules` demands that scenario/authority contract; a pack hash is not sufficient proof of future reality.
  - Old `Z` labels before the selected UTC definition are invalid/outside coverage absent a named proleptic convention. Use a TT label/calendar or an explicit historical reconstruction for ancient astronomy, not an invented ancient UTC instant.
  - Measured UTC/TAI-to-ideal projection remains nominal. Literal infallibility proves a numeric interpretation, never an observation's accuracy. Strict `require_realization` must still expose/accept that interpretation.
  - All context affecting a literal must be static: literal text plus a runtime zone/context is still a runtime resolution. No dependence on compiler-host timezone, network response, or compilation date.
  - Rule data used solely to fold a literal need not ship at runtime. Later civil addition/display may need it; a `ZonedDateTime` cannot support arbitrary future operations merely from one cached offset.

- **Replacement for v4 §5** — assumes its current proleptic-Gregorian default and a pinned zone/UTC rule selection covering these examples. The 2026–2027 meetings resolve under that selection, not a claim that laws cannot change:

```dewy
let ny = time.zone"America/New_York"
let meeting = time.zoned("2026-10-26T09:00" zone=ny)
let repeated = time.zoned("2026-11-01T01:30" zone=ny fold='later')
let shifted = time.zoned("2026-03-08T02:30" zone=ny
    gap='preserve_displacement')
let jan = time.date"2027-01-31"
let feb = jan.add(1month overflow='clamp')
let birthday = time.date"2000-05-12"
let age = birthday.age(on=time.date"2026-10-24")
let leap_birthday = time.date"2000-02-29"
let leap_age = leap_birthday.age(on=time.date"2027-02-28"
    leap_day='march_1')
let meeting_time = meeting.nominal
let elapsed_finish = meeting_time + 90minute

# User text is a real fallible boundary.
let entered = time.zoned(user_text zone=ny) or_throw
let count = to_int(count_text) ?? 0                 # deliberately broad input fallback
let next = appointments.next(after=meeting_time) ??<NoOccurrence> none
```

- **Results:** `meeting` is 09:00 −04:00; `repeated` is the later 01:30 −05:00; `shifted` is 03:30 −04:00; `feb` is February 28; `age` and `leap_age` are both 26. `meeting_time` is the resolved nominal instant. No `or_throw` is justified on those proven constant results.
- **Alternatives:** retain fallible `parse_instant` for dynamic labels/envelopes and use `instant"…"` for a nominal integer coordinate; do not silently change the former's return type. A constant `date` call with a runtime calendar is not an infallible literal. Keeping every constructor fallible would preserve a simpler API signature but squander the existing literal-proof model.
- **New spellings/semantics:** `instant`, `zone` delimited calls; `date`/`zoned` are already v4 names, now with compile-time success refinement. `.nominal` on resolved civil values makes extraction consistent. Reject the critique's unsolicited March-1 default: the explicit policy above already gives clean code and leaves legal/conventional semantics with David.

## 4. Editions, source settings and versioned defaults

- **Recommendation — separate three identities:**
  - **Source edition:** interpretation of unqualified names/default policies in that module.
  - **Definition identity:** which exact calendar/scale/unit a type means; immutable once published.
  - **Data selection:** the versioned dated rules, authorities, coverage and models used to resolve values.
  - No project-file edition key. Existing decisions make `$build`/`$target` source namespaces and ordinary build-module constants the model; semantic settings must not come from CLI/environment switches.

- **Proposed `.dewy` form** — `edition_2026` and `rules_2026` below are ordinary application-defined constants exported by the imported source module, not reserved words or magic installed resources:

```dewy
import p"time_settings.dewy" as settings
$build.edition = settings.edition_2026
$time.rules = settings.rules_2026

$calendar = ProlepticGregorian
billing = () => {
    let issued:Date<ProlepticGregorian> = date"2027-01-31"
    let due = issued.add(1month overflow='clamp')
    printl(due)
}
```

- **Source rules:**
  - `$build.edition` is a proposed **module-local source-semantic setting**, unlike root-only build mode/target. It applies to the compilation unit, is known before resolving edition-sensitive names, and is not inherited from the importing caller. This difference needs explicit approval/documentation.
  - Bootstrap the settings import using an edition-independent restricted declaration header; require its edition constant to be independent of edition-sensitive expressions. Reject dependency cycles. Do not require executing arbitrary imported code merely to decide how to read a module.
  - Each distributable module pins its edition, directly or through its own imported `.dewy` settings constant. A dependency cannot silently acquire the application's edition. A root file cannot rewrite a dependency's calendar by setting a metatag.
  - An omitted edition keeps a **permanently specified baseline**; it must not mean “whatever this compiler currently prefers.” New project scaffolding writes the current edition. Warn when edition-sensitive bare source omits an explicit selection; strict `require_calendar` requires explicit calendar/numbering semantics regardless.
  - `$calendar` applies lexically to its declaration/block and resolves bare `Date`, `date` and `today` there to a concrete calendar type. Provider context must agree or convert explicitly. Inferred types and exported signatures record the resolved calendar identity.
  - Public libraries should spell `Date<ProlepticGregorian>` rather than an edition-sensitive alias; importing an old function never rebinds its defaults at the call site. Use one canonical name consistently; the critique alternates `Gregorian` and `ProlepticGregorian` without deciding whether they differ.
  - `$time.rules` selects an immutable rule-pack descriptor in source. Descriptor constants include authority/definition IDs, content digests, coverage and continuation profiles. Generated transition tables can themselves be `.dewy` source. External signed/raw packs may remain transport data when needed; their selection/verification contract stays in source, with no second semantic manifest or lockfile required.
  - A compile-time literal with unavailable pack bytes fails the build. A runtime rule-loader exposes acquisition failure at its boundary. Pinning does not fetch/load every named dataset or turn absent data into an empty successful table.

- **Evolution/deprecation contract:**
  - Edition E gives bare `Date` its current calendar. E+1 announces/warns about the pending new default and offers an explicit type/tag migration. E+2 may change bare defaults **only for source opting into E+2**. Require at least one published intervening edition; do not infer a deprecation period from wall-clock years.
  - Old editions preserve their meaning. A compiler may eventually reject an unsupported edition with a migration diagnostic; it must never silently compile it under new semantics. Archive the defining `.dewy` modules/pack descriptors for long-term rebuilding.
  - Changing a default calendar is not changing proleptic Gregorian arithmetic. Jurisdictional reforms are new dated relations, not mutations of an established arithmetic-calendar identity.
  - UTC regimes are dated pack segments selected independently of language edition. Old source can opt into a new UTC pack without changing its calendar. New source can reproduce an old pack/scenario. A pack update creates new interpretation/appointment results rather than moving stored instants.
  - The checked BIPM resolution specifies continuous UTC effective **20 May 2027**, with a 3,600-second UT1−UTC bound. Represent that transition as data with the inherited offset; neither a hardcoded year check nor “UTC can never change again” follows. [BIPM Resolution 5 (2026)](https://www.bipm.org/en/cgpm-2026/resolution-5)
  - New terrestrial, lunar, Martian, ship or habitat scales/calendars introduce named domain definitions and explicit transforms/models. A habitat may choose a local calendar default; it does not redefine Earth's `hour`, TT/J0, or a dependency's `Date`. Remote simultaneity still needs the physical convention/model.
  - Stored dates carry an explicit calendar definition identity, and data-dependent interpretations carry their pack identity. A process-local uint32 zone/calendar handle is not a persistent identity. Wire schemas may put shared IDs once per column/message rather than on every scalar.

- **Never edition-version:**
  - J0/e=0, the ideal TT-rate axis, integer-count meaning, the meaning of a named tick such as `1ns`, or what the existing explicit `Instant<tick=… width=…>` type represents.
  - The current plain `Instant` alias and its interchange identity; a future representation gets a new explicit type/schema rather than reinterpreting old bytes. Machine ABI/endianness still require a codec; a count is not a portable struct dump.
  - Exact conversion, no silent rounding, separation of points/differences, and nominal versus measured meaning.
  - An SI redefinition intended to preserve continuity changes realization knowledge, not old counts. A genuinely different rate convention requires a new domain and transform. Later discoveries can refine event estimates without editing their original observations.

- **Alternatives:** a top-level `$edition` is semantically cleaner if David reserves `$build` for global build facets; it adds another root spelling. A single process-global edition is easier to implement but breaks mixed-edition dependencies. A manifest key contradicts the requested source-first direction. Recommendation is `$build.edition`, subject to the explicit module-local exception above.
- **New spellings/semantics:** `$build.edition`, `$time.rules`, `$calendar`, `ProlepticGregorian` as the canonical explicit calendar identity. `$edition` is an alternative **not also proposed for adoption**. Dataset constant names are ordinary user declarations.

## 5. Disagreements with the critique and bounded follow-ups

- **Recommendation:** keep the fixed integer core, lightweight readings, explicit wall extraction, lazy layers, literal proofs and versioned defaults; correct the following claims before incorporating the critique.
- **Width policy:** reject “64 if tick covers a million years”; use a predictable default and explicit compact types. The critique does not fully specify `Duration`, intermediate widening, or the endpoint difference requiring 129 bits.
- **Overflow:** reject `OffGrid` for inability to prove width. Distinguish missing proof, actual off-grid input and actual range failure. Exact arithmetic cannot be silently replaced by checked int128-at-every-operator semantics.
- **Go:** adopt its monotonic lesson, but correct the `Add`, `==`, and single-sample/cached-offset claims as described above. v4's wall-only subtraction is the older stopwatch mistake, not Go's current subtraction rule.
- **Sampling and status:** reject a permanent cached wall offset and a leap cache refreshed only when the pack changes. A known transition inside the same pack matters. Do not invent synchronization/step detection from fields the OS does not supply.
- **Evidence:** reject retrospective `.estimate` from a current calibration. Small copied values cannot recover discarded historical evidence. Also reject keeping implicit assumption graphs on every ordinary value; compile-time obligations are not runtime provenance storage.
- **Identity and copying:** a uint32 zone ID alone does not identify a rule edition across independent packs. Int128 + uint32 ID + int32 offset is 24 payload bytes and often **32 bytes after alignment**, not universally “a register move.” Cached offsets only answer the already-resolved case. Keep persistent IDs and richer intent records where required.
- **Literal coverage:** reject ancient `instant"…Z"` examples without an explicit historical/proleptic convention. Remove “branded zone + total policy means universally infallible”; missing coverage, arbitrary calendars and finite destination range remain.
- **Science:** a fixed finer tick handles many exact affine transforms. A separate rational science layer is useful for generality, not mandatory for every TT↔TCG operation. Prefer reuse of the existing point/domain design.
- **Intervals:** discrete successors do not eliminate max-endpoint problems or preserve continuous duration measure automatically. Calendar-day successors are not universally forbidden. Retain v4's explicit interval semantics until the intended measure is chosen.
- **Negative leaps:** agree on one general skipped-label mechanism and no new type. Do not infer that negative adjustments are impossible forever, or that UTC leap/smear/codec validation is identical to a zone gap merely because candidate resolution can share code.
- **Calendar policy:** reject the external project-file key. Do not silently approve `age`'s March-1 default, the global `day`/`week` unit change, or nominal-only `today` as representation cleanups; these are separate surface/semantic choices David owns. `today` near an uncertain date boundary still needs its explicit nominal/uncertain contract.
- **Scope boundary:** full recurrence, legal-age, observational-calendar, codec and scientific coverage review belongs with the correctness and coverage review (`review-correctness-coverage.md`). No additional implementation or standards survey is justified by this pass.

- **Dewy counterexamples and retained idiom:**

```dewy
let measured = time.elapsed(@job)
# @job() should warn and suggest @job.

let label_date = date"-0584-05-28"       # valid proleptic calendar label
# instant"-0584-05-28T12:00:00Z"         # not justified by integer range alone

let a = instant"2026-10-24T12:00:00Z"
let b = a + 0.1s                        # exact decimal, exactly 100000000ns
printl(b - a =? 100ms)
```

- **Alternatives:** accept the critique wholesale only by changing established integer semantics, weakening coverage requirements, and assuming undocumented clock services. Those costs are unnecessary; the corrected design retains its useful ergonomic improvements.
- **New spellings:** none in this section beyond those inventoried below. `@job()` lint behavior is already fixed by David.

## Approval inventory: every new public spelling or changed meaning in this review

- **`Instant<… width=128>` / `width=64`, `Duration<tick=… width=…>`:** approve signed count width independent of tick, both plain aliases at 128-bit ns; unblocks layout/ABI and compact storage. Defaults/ABI are costly to change after release; parameter spelling is reversible before release.
- **Exact time-operator intermediates and inferred wider count storage:** approve applying existing fixed-integer rules through these wrappers; unblocks sound full-range arithmetic without heap promotion. Implementation representation is internal; public result/narrowing behavior is semantic.
- **`Coordinate<Scale>`:** approve only as a science-layer alias/specialization of the existing point-domain machinery, rational seconds with a defined origin; unblocks exact off-grid/scientific composition. Name is reversible; domain distinctions must remain.
- **`OffGrid`:** approve divisibility failure only; unblocks exact checked conversion. Reuse v4 `OutOfRange` separately. Error names are reversible before public serialization contracts.
- **`convert<T>(value)`:** approve a checked target-type form returning specific failures; v4 already proposes `convert`, but not this concrete target syntax/contract. Unblocks dynamic exact conversion without misusing `as`. Reversible library spelling.
- **`instant"…"`, `zone"…"` and namespaced `time.zone"…"`:** approve ordinary delimited library calls; no new parser syntax. Unblocks plain coordinate and validated-zone constants. Reversible names.
- **Compile-time success refinement for `instant`, `zone`, `date`, `zoned` (including namespaced forms):** approve only under the stated static context/coverage/grid/range rules. Unblocks removal of redundant `or_throw`. The proof contract is semantic; does not authorize failure suppression.
- **`.nominal` on `ClockReading` and `ZonedDateTime`:** retain v4's explicit numeric question consistently; unblocks wall extraction and the rewritten §5. Reversible member name; nominal-versus-measured distinction is permanent.
- **`ClockReading - ClockReading`, `ClockReading + Duration`:** approve monotonic elapsed and `MonoPoint` deadline results, respectively, with same-session proof or explicit failure. Unblocks the trivial stopwatch/timeout tier. This is a change to v4 semantics requiring David's decision, even though no new operator is introduced.
- **Captured successful-session branding/task failure contract:** approve explicit acquisition/continuity failure behavior enabling short ordinary calls; unblocks total happy-path reads without fabricating elapsed time. No new public spelling; existing strict opt-outs must cover every environmental assumption.
- **`$build.edition`:** approve source-only module-local edition selection and frozen omitted baseline; unblocks mixed-edition default evolution. Reversible spelling before release, enduring source semantics afterward. Alternative `$edition` is not requested simultaneously.
- **`$time.rules`:** approve lexical immutable source descriptor selection with explicit data availability/coverage; unblocks reproducible literals and rule updates independent of source edition. Reversible member spelling; pinned identity contract is semantic.
- **`$calendar`, `Date<ProlepticGregorian>`, `ProlepticGregorian`:** approve a lexical default override and one canonical explicit calendar identity; unblocks local/calendar-specific applications without rewriting dependencies. Calendar identity/algorithm must freeze; names can change before release.
- **Retained v4 proposals used here, not additional inventions:** `TimePoint`, `Instant`, `Duration`, `ClockReading`, `MonoPoint`, `TemporalContext`, `Date`, `Zone`, `ZonedDateTime`, `Estimate`, `tick`, `quantize`, `ticks`, `parse_instant`, `date`, `zoned`, `add`, `age`, `elapsed`, `monotonic`, `clocks.active`, `with_context`, `DomainMismatch`, `OutsideCoverage`, `UnknownClockConvention`, `UnsupportedClockSemantics`, and v4's `$time.require_*`/`$time.strict` names. Their original inventory still needs David's approval; this review neither silently approves all of it nor renames it.
- **Retained policy spellings used in examples:** `zone`, `fold='later'`, `gap='preserve_displacement'`, `overflow='clamp'`, `on`, `leap_day='march_1'`, `rounding='nearest_even'`. Keep their existing v4 meanings; no new default is approved here.
- **Not new surface:** `TT`, fixed integer type names, `as`, `=?`, `@`, `or_throw`, `??`, `??<E>`, metatag placement, no-parentheses zero-argument calls, and `loop <condition> <body>`. Example application names (`settings`, `appointments`, `job`, `cached`, etc.) are placeholders, not proposed standard-library members.
