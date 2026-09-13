# Dewy roadmap after the native bootstrap

This is the high-level roadmap for taking the language from "a native
compiler pair exists and is reasonably performant" to the language as it was
intended. It is deliberately not a task list. It records the order in which
the remaining pieces should land, why that order, and the strategy for the
pieces where the project has previously bogged down.

How this relates to the other documents:

- [`status.md`](status.md) is the feature-by-feature implementation tracker
  and the home of the detailed design essays (liquid refinements, ownership
  tiers, nominal/structural construction). This document orders that work.
- [`bootstrap/IMPLEMENTATION.md`](bootstrap/IMPLEMENTATION.md) is the log of
  the native bootstrap effort. That effort continues as mandated until a
  verified, packaged, installable pair exists. Nothing here changes it.
- [`semantic/*.md`](semantic/) are the design notes for individual areas.
  Where this document says a design is open, the note is where the options
  live.
- [`../site/reference/src/design-status.md`](../site/reference/src/design-status.md)
  is the user-facing maturity ledger. It should move items from provisional
  to settled as the phases below complete.

Recorded 2026-09-13 from a roadmap discussion. The ordering is a
recommendation David accepted for phases 1.1 through 1.3; later phases are
the preliminary proposal and will be revised as earlier phases land.

## Organizing principle

Dewy's identity rests on three commitments, and nearly every unfinished
feature either depends on one of them or is blocked by one being half-built:

1. value semantics whose cost is never hidden;
2. compile-time proof instead of runtime checks, with no runtime traps;
3. one language for runtime and compile time (compile-time evaluation, not
   macros).

Work is therefore ordered by "which foundation does this need", not by user
visibility. The pieces users notice most (floats, matrices, closures, GUI
examples) come after the pieces that make them cheap to build once.

One structural cost shapes everything: while the hosted Python compiler and
the bootstrap compiler must stay in parity, every feature costs twice. The
highest-leverage decision after the fixed point is to retire Python as the
reference as soon as the native pair passes the regression corpus. Until
then, foundation changes are scoped to land once, in the native compiler.

## Phase 0: workable native compiler (in progress, mandated)

Exit criteria that the later phases depend on:

- verified fixed point: two native generations of both compilers, byte
  identical, built without Python (`tools/bootstrap_native.sh`);
- the native pair passes the full end-to-end corpus, the differential
  `test_bootstrap_*` groups, and the `$test` runner;
- installer and release wired to the verified package; CI green;
- the Python compiler frozen except for seed rebuilds, then retired as the
  behavioral reference;
- compile-time performance adequate for dogfooding. Full-source checking
  measured in hundreds of seconds and multi-gigabyte peaks makes the language
  unusable regardless of features. A serialized checked-prelude cache on the
  native side (the counterpart of the hosted resident prelude) is likely the
  single largest available win and is independent of any language work.

## Phase 1: foundations to their intended designs

### 1.1 Memory and ownership model

The intended design is recorded in `status.md` ("Ownership and storage
model") and `semantic/value_semantics.md`: one owner per value, moves by
last-use liveness, borrows where proven read-only, deterministic release,
placement (stack, static, scoped arena) as a proof-gated optimization.
Copy-on-write is a provisional bootstrap accelerator
(`bootstrap/PERFORMANCE.md`), not the long-term mechanism.

**What went wrong last time.** The model was not the problem. The analysis
could not justify enough borrows and moves, so lowering fell back to "copy to
be safe", and the compiler's own code shape hit the worst case for that
fallback. Self-build profiles showed every sample inside string cloning,
called from record copying, called from reading a node out of the type
arena: a read-only arena lookup paid a full deep copy each time, for a
cumulative 324 GB allocated against 9 GB live. Copy-on-write made those
copies free until a write, which is why it unblocked the bootstrap.

**Strategy.** Make it structurally impossible to re-enter that state
silently.

1. **Every copy visible and budgeted.** Extend the existing kernel gates
   (`tests/python_misc/test_array_sharing.py` and its byte/allocation
   counters). Add a `dewy analyze` mode that lists every dynamic aggregate
   copy with the reason the analysis could not borrow or move it. Treat
   "unexplained copies on the compiler's own sources" as a CI metric with a
   fixed budget per kernel and per thousand lines. Regressions surface in a
   pull request, not at 25 GB in a self-build.
2. **Mechanisms in order of where the bytes went.** First: read-only
   element and field reads that do not escape their expression or scope
   lower as views, justified by the effect analysis proving the root is not
   mutated during the borrow. This alone removes the arena-lookup case.
   Second: moves at last use for records, strings, and unions (arrays
   already have this). Third: scoped arenas for the checker's per-branch
   temporaries. Each step is measured against the gates before the next.
3. **Ratchet copy-on-write down, do not rip it out.** Keep it behind the
   same descriptor interface as the fallback. Count detachments and shared
   snapshots per kernel. Remove it from a shape only when the static path
   drives that shape's count to zero on the compiler's sources. What remains
   becomes the opt-in strategy the design wants for types that choose it.
4. **A fast path that never waits on inference.** The compiler makes the
   `addr`-handle-into-arena idiom the bootstrap already uses cheap first.
   Whether a read-only borrow spelling should exist as an explicit escape
   hatch is an open surface question (`semantic/user_managed_storage.md`)
   and needs David's decision; without it, a failed proof leaves only a
   hidden copy or a rewrite.
5. **Explicit fallback policy (decided 2026-09-13).** When a borrow or move
   cannot be proven, the default is a copy accompanied by an analysis note,
   never a silent copy. A module-level opt-in directive turns any unproven
   copy of a runtime-length aggregate into a compile error. The compiler's
   own sources compile under that directive. The directive's spelling is
   not chosen yet (surface change; needs approval before landing).

The difference from the earlier attempt is the order and the gate: each
mechanism lands against a measured kernel and the compiler's own sources,
with copy-on-write as a measured floor rather than a cliff.

### 1.2 The proof engine

Today the refinement system is an interval analysis plus a growing set of
fact-transfer rules, and the bootstrap keeps finding sound-but-missing rules
one at a time. The intended design is the liquid refinement system in
`status.md`: a proposition grammar with a finite qualifier vocabulary,
symbolic state across mutation, effect and alias tracking so proofs survive
calls, a solver that answers unknown rather than false, checked lemmas, and
an `unsafe` boundary that is a real audit obligation. Building that properly
turns the rule-by-rule work into a system. It is also the feature that
distinguishes Dewy from every other systems language, and the standing rule
applies throughout: proofs come from facts the analysis carries, not from
restructuring code into a shape the analysis happens to understand.

### 1.3 Effects as a real vocabulary

The transitive parameter effect analysis exists
(`semantic/analyze/effects.py`); the language-level vocabulary does not.
Effect polymorphism, allocation and failure as effects, and the
`noreturn`/escape set are prerequisites for compile-time purity (Phase 2),
the resource-exhaustion policy (`semantic/resource_exhaustion.md`), and the
concurrency model (Phase 4). Effects remain separate from errors: errors are
union alternatives, effects describe evaluation behavior.

### 1.4 Design-decision sprint

A short pass over small surface questions that get more expensive every
month and block documentation and library code. None needs a large
implementation; the value is in closing them. The cases, each with a
minimal example, options, and a recommendation, were presented to David on
2026-09-13 and await his decisions:

1. juxtaposition with two precedences and union-typed operands, including
   whether a number on the right (`x 2`) stays legal;
2. based byte literals: non-power-of-two bases, separators, digit order;
3. which of `extern`, `intrinsic`, `none`, `void`, `untyped`, `end`, `new`
   are keywords versus ordinary or contextual identifiers;
4. `<>` versus `[]`/`()` for parametric types (recommendation: keep `<>`);
5. explicit export control versus public-by-default with an opt-out;
6. the Unicode identifier repertoire and source normalization policy;
7. whether a unit-like nominal type and its sole inhabitant are one object;
8. `s.add` versus `push` on sets (recommendation: keep `add`).

Not decisions: the three precedence adjustments still listed as open in
`design-status.md` landed on 2026-08-31 and that appendix needs a doc fix.
Multidimensional shape syntax is a real design but belongs to Phase 3.

## Phase 2: expressiveness on top of the foundations

- **Parameterized types**, explicit type arguments, monomorphization. This
  unlocks the stated long-term goal of moving arrays, dictionaries, sets, and
  strings out of the compiler into Dewy libraries, which shrinks the
  compiler and makes the ownership model testable in library code.
- **Closures as environment records**, using the ownership model for
  captures (today: lambda-lifted non-escaping local functions only).
- **Compile-time evaluation, first slice:** the reflection primitives in
  `semantic/argparse_and_reflection.md` (`fields`, `members`, `$field`,
  unrolled literals). Then general compile-time execution under the purity
  and termination rules. This replaces pressure for compiler builtins; the
  rule stands that library features are built on reusable primitives, never
  on the checker recognizing a library call. Note: compile-time execution
  does not make the compiler faster; it makes it smaller and more uniform.
- **Error propagation completeness:** transformed propagation, pipe
  forwarding, the `exception` family finished.

## Phase 3: the engineering numerics story

The front-page promise, nearly untouched: IEEE floats and promotion,
multidimensional arrays with shapes and broadcasting, vectorized calls,
matrix and linear-algebra overloads, the rest of the units library
(conversions, offset scales, display units), a math standard library. After
Phase 2 because it needs generic types, compile-time shapes, and the
juxtaposition decision. `semantic/numerical_stress_test.md` is the
evaluation plan.

## Phase 4: reach

- A stable foreign-function interface; target triples with structured
  `$target` gating (`status.md`, "Proper compilation target list"); full
  prelude on wasm32; at least one non-Linux host.
- The concurrency model (`semantic/safety_and_concurrency.md`):
  partition-first fork-join, `Send`/`Sync` as structural properties, then
  the resource-exhaustion policy. Deliberately last among language
  features: its design has a dozen open questions and needs ownership and
  effects settled first.

## Phase 5: ecosystem

Language server on the native parser and checker (replacing the lexical
TextMate grammar and any tree-sitter path), formatter, installed-package
imports, the documentation projects and case studies in
`../site/DOCUMENTATION_PROJECTS.md`, and the trusted-computing-base and
DewyOS explorations. These make the language real to other people, but
should not be built twice, so they wait for the native compiler and a
stable surface.

## Deprioritized

- Additional µDewy backends, the browser playground, and the hypothetical
  ndewy rung (a TBD section in `../udewy/trusted_computing_concept.md`; no
  code exists). Finished enough, or not started, and correctly so for now.
- Growing the Python compiler beyond seed duty.
- Any new user-visible spelling before the Phase 1.4 decisions; surface
  changes need David's approval first.

## Open ordering questions

- Whether the proof engine (1.2) should precede the ownership model (1.1).
  Current lean: ownership first, because it is what blocks the bootstrap's
  own memory behavior today.
- Whether compile-time reflection deserves to move into Phase 1 so more of
  the standard library can be written in Dewy earlier. Current lean: no; it
  does not help compiler performance and its purity rules want effects
  (1.3) first.
