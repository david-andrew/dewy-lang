# Compact-core completion status

Updated 2026-10-19. This tracks `restart/sloppy-frontend`; it does not redefine
the [language goals](GOALS.md). The [language guide](../core/LANGUAGE.md) specifies
current behavior. [RESTART](RESTART_2026_10.md) retains historical experiments.
New front-end or user-facing language design requires David's approval.

## Current position

- The ordinary language, native/web games, libraries, editor, REPL, watch and
  project testing are usable in the experimental core. This is not full Dewy.
- The last measured optimized host passes 6,296 checks. Its fresh 44,005-line
  default build takes 217 ms on the i5-8350U laptop, about 203k root lines/s.
  This synthetic measurement does not establish the 250k representative-program
  goal. Native and optional GCC-host results must remain separately labeled.
- Generated-program performance is mixed. Managed helper calls, text and
  dispatch still trail C; some record/array workloads are faster.
- Bounded wrapper inlining now cuts default managed-helper runtime about 39%
  on the laptop, from about 22.8 to 13.9 ms. Release stays near 12.9 ms; C is
  8.4 ms. The independent native bootstrap passes 6,303 tests in 170 seconds.
  Its checkpoint has 56 passes and four inconclusive record timings, with no
  established regression. [Summary and raw evidence](audits/2026-10-19/bounded-wrapper-inlining.json).
- Selective Sloppy JSON token fast paths cut object parsing about 30%, numeric
  arrays about 36%, and keyword arrays about 86% in paired desktop measurements.
  String timing remains machine-sensitive: desktop release regressed, while a
  bounded laptop check of the same executables was flat. String-copy prototypes
  were dropped. [Evidence](audits/2026-10-19/json-token-dispatch.json).
- The audit batch passes 6,323 tests after an independent bootstrap and 200
  differential fuzz seeds across five modes (1,000 executions). All 28 existing
  benchmark artifacts match the preceding wrapper stage, with fresh checksums.
  [Validation](audits/2026-10-19/bounded-differential-fuzz.json).
- Grouped constant matches now use bounded lookup tables where appropriate;
  private 1-/2-byte scalar slots can stay in registers. Native instruction
  counts fell across the measured compile workloads, and laptop comparisons
  passed. The latest native synthetic default result is about 127k root lines/s
  on the older laptop, still well short of the target.
  [Grouped matches](audits/2026-10-19/grouped-match-lookup.json),
  [narrow slots](audits/2026-10-19/narrow-scalar-slots.json).
- Sloppy's recursive-return optimization cuts integer fib(38) runtime about
  4.2% on the laptop, with floating recursion flat. Desktop integer timing is
  inconclusive. Release compile instruction cost rises 0.13–0.29%; all laptop
  compilation comparisons pass. The optimizer batch passes 6,359 tests after
  an independent bootstrap; existing 28 benchmark artifacts are unchanged.
  [Evidence](audits/2026-10-19/recursive-branch-returns.json).
- Sloppy's array-swap implementation plus panic-message call metadata cut
  ten million release swaps from about 45.2 to 30.7 ms on the laptop; C is
  28.0 ms. Default falls from about 54.3 to 41.8 ms. Shared arrays, nested
  managed values and stateful closure copies retain their isolation.
  [Swap](audits/2026-10-19/array-swap.json),
  [checked-helper inlining](audits/2026-10-19/panic-argument-calls.json).
- Bounded decimal parsing is about 8.6x faster by default and 10.2x in release
  on the signed-decimal workload, and faster than the checked C `strtoll`
  counterpart there. Whitespace, hex, boundary and malformed-input workloads
  also improve. The library batch passes 6,393 tests after independent bootstrap
  plus 100 fresh fuzz seeds in five modes. Its laptop checkpoint has 70 passing
  comparisons and two inconclusive default timings (string equality and shifted
  arrays against the preceding compiler), with no established regression.
  [Evidence](audits/2026-10-19/integer-parsing.json).
- Register allocation now recognizes a scalar-returning call immediately
  consumed by a nonreturning call, without extending successful-path values
  across it. Array swap improves another 6.6% by default and 9.0% in release
  on the laptop; release now matches C on that workload. Other 30 benchmark
  artifacts are unchanged, and all twelve compilation comparisons pass.
  Debug builds retain their existing variable-preservation behavior.
  [Evidence](audits/2026-10-19/terminal-message-calls.json).
- A broad release inlining-cost adjustment was tested and reverted: ordinary
  builds gained less than 1% latency while compiler rebuilding cost increased
  about 2%. [Deferred experiment](audits/2026-10-19/structural-inline-cost.json).
- Existing C bindings now honor variadic float promotion and System V's
  vector-register convention. Tests call a separately compiled C library from
  Dewy in default, release and debug modes, including stack arguments.
  [Evidence](audits/2026-10-19/c-variadic-arguments.json).
- Early return/break/continue now releases abandoned statement temporaries and
  partially constructed values, including closures and pending mutable-argument
  copies. Initialization needed for safe cleanup is added only where an escaping
  path requires it. All 32 ordinary benchmark artifacts remain unchanged;
  laptop compilation comparisons and 100 fresh fuzz seeds pass.
  [Evidence](audits/2026-10-19/partial-construction-cleanup.json).
- Register lifetime/cost metadata now shares one record array. All 32 benchmark
  artifacts are unchanged; all laptop compilation comparisons pass. The gain
  is modest: roughly 0.7% for compiler rebuilding, with most timings near flat.
  [Evidence](audits/2026-10-19/register-lifetime-records.json).
- Two further experiments were reverted promptly: paired SSE string comparisons
  regressed laptop release runtime about 10%, and transitive effect-summary reuse
  saved too little compiler work to prioritize. Their unfavorable evidence is
  retained ([strings](audits/2026-10-19/paired-string-equality.json),
  [effect analysis](audits/2026-10-19/effect-summary-reuse.json)).
- File line reading no longer rescans its accumulated prefix after refills;
  stdin reads directly into its result buffer, and string copies skip redundant
  zeroing. On the laptop, release 4MB line reads fall from 82.5 to 3.0 ms,
  short lines from 14.4 to 7.1 ms, and 8MB stdin from 14.6 to 2.2 ms.
  A byte read after a final unterminated line now returns empty at EOF.
  The batch passes 6,437 checks after independent bootstrap and 100 fresh fuzz
  seeds in five modes. The ordinary checkpoint has 68 passing comparisons and
  four inconclusive runtime timings, with no established regression.
  [Evidence and limitations](audits/2026-10-19/buffered-input.json).
- Grapheme length now scans ASCII prefixes in words; Unicode boundaries use
  a deduplicated combined property table. On the laptop, release mixed-Unicode
  length is about 4x faster and traversal 2.6x; ASCII length is about 35x faster.
  All 32 ordinary benchmark artifacts are unchanged and all twelve compilation
  comparisons pass. The batch passes 6,455 checks after independent bootstrap
  and 100 fresh fuzz seeds in five modes. Unicode 16 behavior is unchanged.
  [Evidence, including rejected prototypes](audits/2026-10-19/grapheme-pages.json).
- Fixed-array reads omit bounds checks when the complete unsigned index domain
  fits, retaining checks through signed narrowing. Exhaustive native/web tests,
  599 quick checks, artifact comparisons and laptop compilation checks pass.
  Lookup latency is flat; the 16-bit timing remains inconclusive. This is a
  smaller-code improvement, not a claimed speedup. Full validation is closed
  by the following inlining batch. [Evidence](audits/2026-10-19/fixed-index-domain.json).
- Read-only comparison-call facts were tested and reverted: a targeted load
  disappears, but compiler workloads do not improve. The wider graph pass is
  deferred. [Evidence](audits/2026-10-19/readonly-comparisons.json).
- Release inlining now admits tiny read-only leaf loops into larger callers.
  Ordinary compiler instruction counts fall 0.7–0.9%; on the laptop, the default
  synthetic build is about 1.1% faster while compiler rebuilding is 1.15% slower.
  All twelve compilation comparisons pass; all 32 runtime artifacts are unchanged.
  Independent bootstrap passes 6,468 tests, plus 100 fresh fuzz seeds in five
  modes. Native throughput is about 127k root lines/s, still below the target.
  [Evidence and rejected variants](audits/2026-10-19/tiny-read-loop.json).
- Existing matrix multiplication now uses cache blocks and four-row accumulation.
  Laptop release dense products improve 27–47%, sparse about 14%, and all-zero
  about 20%; all fourteen targeted comparisons pass. Six new boundary cases,
  587 focused checks and 611 quick checks pass; all 32 ordinary runtime artifacts
  are unchanged. Full validation is closed by the following allocation batch.
  [Measurements and rejected fallback](audits/2026-10-19/blocked-matrix-product.json).
- Ordinary array-size validation now avoids division when a cheap operand bound
  proves the product safe. Targeted allocation/growth runs improve 11–16%; all 12
  laptop compilation comparisons pass, improving 0.8–1.5%. Native synthetic
  throughput is about 129k root lines/s. Independent bootstrap passes 6,484 tests
  plus 100 fresh five-mode fuzz cases, closing the matrix batch. Across 80 runtime
  comparisons, 74 pass and 6 remain inconclusive; no established regression and
  no whole-stage promotion. [Evidence](audits/2026-10-19/array-byte-count.json).
- A fresh same-laptop Sloppy comparison (native self-hosted, same workload,
  own libraries) measures default Sloppy Jo at 226 ms, Dewy Jo at 283 ms, and
  equivalent Dewy source at 346 ms. Release is 521/378/453 ms respectively.
  Default Sloppy skips optimization passes Dewy uses for generated-code quality;
  source formatting also differs. This leaves a real default-build gap without
  implying all of it is frontend cost. [Calibration](audits/2026-10-19/fresh-sloppy-calibration.json).
- Proven stable array-element views no longer acquire per-call managed copies
  in release mode. Matrix-row indexing is 4.6x faster on the laptop; default
  mode is unchanged. All 32 ordinary artifacts are unchanged and all 12 compile
  comparisons pass. Snapshot boundary checks and 615 quick checks pass; full
  validation is closed by the following call-lowering batch. [Evidence](audits/2026-10-19/element-view-calls.json).
- Default compilation now recognizes calls to custom helpers that never return,
  keeping their failure path out of small inlined callers. A checked-helper loop
  runs about 2.2x faster on the laptop; release/debug policy is unchanged after
  rejecting an unconditional variant's 6% release regression. All 32 ordinary
  artifacts and the targeted release artifact are unchanged; all 12 compile
  comparisons pass. Independent bootstrap passes 6,494 tests and 100 fresh
  five-mode fuzz cases, closing the call-lowering batch.
  [Evidence and rejected variant](audits/2026-10-19/nonreturning-helper-calls.json).
- The fixed performance reference remains `ea1cba0e`; the last accepted whole
  stage remains `cd07ea34`. Conflicting laptop release timing is unresolved.

## Capability ledger

| Area | Implemented boundary | Next useful work / evidence | Design approval |
|---|---|---|---|
| Value semantics | Independent ordinary values and private closure copies; explicit shared captures; recursive records | Preserve behavior while removing managed-call overhead; native/web mutation and callback tests | Required for changing the contract |
| Functions and generics | Named/default arguments, named callable values, overloads, generic top-level functions/records | Complete composition cases; explicit generic local closures and constrained parameters remain absent | Required for new surface rules |
| Records and collections | Named/anonymous records, arrays, dictionaries, sets, literal spreads, typed matching and narrowing | Maintain consistent assignments/guards; structural conversions and call-argument spreads remain absent | Required before selecting their missing semantics |
| Numerics | Machine numbers, explicit `BigInt`/`Rational`, numeric arrays and matrices | Improve ordinary kernels and library implementations; automatic integer growth remains absent | Required for arithmetic-policy changes |
| Compile-time work | Constant expressions and fixed-array lengths | General compile-time execution remains absent; define its supported boundary before implementation | Required for new evaluation/effect rules |
| Games and batteries | Native/web game examples, GPU arrays, networking and rollback examples | Triage Sloppy improvements by actual application need; run selected game/tool integration checks | Internal fixes need none; new APIs/syntax need review |
| Developer feedback | Fast native edit loop, quick/full suites, C bootstrap, editor/watch/REPL | Maintain unified quick/full test lists, bounded differential fuzzing and instruction measurements | No language change |
| Compilation performance | Native pipeline plus separately built optional GCC host | Attribute costs on representative programs and the compiler itself; keep default/release, native/host, and hardware explicit | No change to targets without agreement |
| Strict systems lane | Goal recorded; proof/effect and forbidden-cost checking not recreated | Keep separate from completion of ordinary language/game work | Required before selecting its interface |

## Next sequence

1. Use current profiles and native-versus-GCC generated-code comparisons to
   choose the next substantial runtime/compiler improvement. Instruction
   diagnostics and bounded differential fuzzing are now maintained commands.
2. Continue selective Sloppy correctness/library ports with matched measurements.
3. Complete an ordinary-language/application capability from the ledger;
   present any missing user-facing design before implementing it.

Quick and focused checks accompany edits. Full suites and independent bootstrap
close coherent batches; optimized-host retraining belongs at larger checkpoints.
Changed generated programs need runtime checks. Unchanged programs can reuse
valid artifact certificates with fresh checksums. Fewer retired instructions
are useful diagnostic evidence, not proof of lower latency. Do not weaken
fixed-reference comparisons, discard unfavorable samples, or repeat campaigns
until a desired result appears.
