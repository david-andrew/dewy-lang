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
| Developer feedback | Fast native edit loop, quick/full suites, C bootstrap, editor/watch/REPL | Keep test lists unified; add bounded differential fuzzing and reusable instruction measurements | No language change |
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
