# Phase 1 implementation checkpoints

Started 2026-09-20 from `be7d1b1a`. The scope is all of Phase 1 in
[ROADMAP.md](ROADMAP.md), with the correctness/parity closure checkpoint
first. This ledger records implementation and validation, not new language
decisions. Open design questions stay open until resolved with David.

## Work remaining

- Correctness/parity: resolve `nat_types` through sound reasoning or a
  reviewed expectation; run explicit fixture manifests and a fresh paired
  native checkpoint at integration boundaries.
- 1.1: complete copy reporting and explicit-copy policy across entry points;
  explicit aggregate copies and local places/views; last-use moves in both
  implementations; deterministic lifecycle hooks and move-only resources;
  measured scoped placement and copy budgets. Keep COW as a provisional
  fallback rather than changing value semantics.
- 1.2: bounded relational proof machinery, mutation/alias-aware facts,
  loop invariants, checked proof boundaries and auditable unsafe boundaries.
  Unsettled surface forms require design review; unsupported proofs must
  remain unknown rather than silently accepted.
- 1.3: effect vocabulary and propagation, effect polymorphism and contracts;
  errors remain return alternatives, separate from effects.
- 1.4: implement and test the settled juxtaposition, reserved-name,
  unit-nominal, and uniform-container decisions. Preserve the decisions to
  keep type brackets and conventional export privacy. Keep the explicitly
  open byte-packing and Unicode escape questions visible.

## Strict-copy cleanup

The inherited uncommitted CLI-only `$explicit_copies` implementation was
removed on 2026-09-20, with its patch and tests archived under
`../dewy-build-artifacts/phase1-2026-09-20`. It depended on incomplete copy
notes, bypassed non-CLI compilation, and prescribed remedies that did not
yet exist. This abandons that partial implementation, not the approved
directive. Reintroduce the policy with the relevant semantic/lowering API,
explicit remedies, source provenance, and acceptance-parity tests. Existing
`dewy analyze` copy reports remain available.

## Validation discipline

Each implementation batch needs acceptance/rejection and independent
execution outcomes, with hosted/native agreement. Ownership batches also
need second-generation native execution. Run complete build/fixed-point
checks at integration checkpoints, not for every small edit. Maintain
separate timing rows for C-built and direct-built executing compilers;
30 seconds is the minimum native target and 10 seconds the stretch goal.
