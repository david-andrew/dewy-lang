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

Recorded 2026-09-13. The ordering and the phase 1.1 strategy were reviewed
and accepted by David for phases 1.1 through 1.3; later phases are a
preliminary proposal and will be revised as earlier phases land.

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
- the size of the generated µDewy, and the time spent generating it
  (measured 2026-09-14 on `bootstrap/parser/t0.dewy`, 873 lines: 5.7 MB /
  79k lines of µDewy; 17.9 s to check, lower, and emit against 4.6 s for the
  µDewy stage to parse, assemble, and link). The text is large, but the time
  is mostly in *building* it — lowering is about three quarters, checking a
  seventh, emission a ninth (a third of that the source-position markers).
  In order of payoff per risk:
  1. cache the pure type functions the lowering recomputes per site
     (`_object_layout` ran 24k times, the union-member computation 18k, for
     that one program; ninety union result writes cost 9 s between them) —
     output-neutral, plausibly a third to a half of the lowering time;
  2. outline what a person writing µDewy would call a helper for: the
     scope-exit release sequence (3,274 inline blocks of ~6 lines, about a
     fifth of the file) as one prelude call; a per-type copy function for
     object copies and union writes instead of inline field-by-field stores;
  3. hoist string literals (595 sites, each rebuilding its descriptor and
     boundary table with a dozen stores every time the site runs) into
     module init or static data, and build the module-level constant tables
     (the 15k-line top-level function: symbol lists, character sets) as data
     rather than store by store;
  4. emit source-position markers (12.7k lines) only for debug builds, or
     thin them to statement starts.
  Expected together: about half the text and a further slice off lowering;
  measure after each, since the profile shifts. The checker's share is
  analysis proportional to the program, not the output, and is a separate
  problem (the proof engine's bounded traversals, 1.2).
- further mechanical wins the self-time profile of that compile shows, none
  of which changes output (recorded 2026-09-14):
  - `repr` of whole types as sort and cache keys: `runtime_union_members`
    and `enum_members` sort members by `repr(member)` (`semantic/ty.py`),
    and `_member_tag` keys its cache by `repr(plain)`
    (`backend/udewy/lowering_optionals.py`). A record's repr is its whole
    nested dataclass text, guarded by `reprlib` — 3.6 million repr calls and
    7.5 million set operations for one program, the single largest self-time
    item. Memoize per type object (the types are frozen and hashable), or
    key by a cheap structural hash;
  - `location_marker` resolves the source path (`Path(...).resolve()`) for
    every marker — 52k `realpath` and 181k `lstat` calls, about 1.9 s.
    Resolve once per source file;
  - `is_subtype` normalizes both operands on every query (`to_nnf` 276k
    calls, 3.3 s) and `user_brand_carries` runs 474k times (1.7 s). Memoize
    `normalize`, or `is_subtype` itself for hashable operands;
  - the tree rewrites (`ModuleCompiler._rename`, `_uniquify_module_locals`,
    the analysis walkers) call `dataclasses.fields` per node and `replace`
    on every node: 331k and 280k calls, about 3.7 s. Cache `fields` per
    class, and rebuild only changed subtrees — the whole prelude tree is
    renamed on every compile though its renaming never changes;
  - the µDewy stage is its own front end: of its 4.6 s, tokenizing and
    parsing the text are about nine tenths (a character loop with 4.6
    million `startswith` calls, then a recursive-descent parse); assembling
    and linking are about a second. A regex-driven tokenizer helps; better,
    when the hosted compiler drives the µDewy compiler in-process it can hand
    over its statements or tokens and skip the text round trip entirely.

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
fallback. Profiles taken during the September 2026 paired self-build
attempts (summarized in `bootstrap/PERFORMANCE.md`) showed every sample
inside string cloning, called from record copying, called from reading a
node out of the type arena: a read-only arena lookup paid a full deep copy
each time, for a cumulative 324 GB allocated against 9 GB live. Copy-on-write made those
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
implementation; the value is in closing them. Each case below states the
question with a minimal example, then the decision (or that it stays open).
Decisions were made by David on 2026-09-13.

1. **Juxtaposition with union-typed operands (decided).** Writing two
   expressions next to each other is an operation chosen by the operand
   types: a callable on the left means call, a number means multiply.
   The two forms have different precedences on purpose, so that
   `sin(x)^2` is `(sin(x))^2` while `2x^2` is `2 * (x^2)`. The question
   is what happens when the left operand's static type is a union of a
   callable and a number, since the parser cannot pick a precedence:

   ```dewy
   let f:((int):>int) | int = ...
   f(x)^2        # call or multiply?
   ```

   Decision: such union types are allowed by the type system, but a value
   of one reaching a juxtaposition is a compile error as ambiguous. The
   diagnostic must show the explicit forms: `A |> B` or `B <| A` for a
   call, `A * B` for a multiplication. Parenthesizing is not offered as a
   fix, since the parentheses are gone by the time the operation is chosen.
   Both precedences stay. Separately, a number on the right of a name
   (`x 2`) is never a call and never a multiplication: it is two separate
   expressions. The parser's tentative right-side multiply-juxtapose case
   for numbers (noted in the hosted `t2` stage) is dropped.
2. **Based byte literals (open, low priority).** Strings carry no `\x`
   escape because a string is a sequence of scalars, not bytes, so byte
   arrays need their own literal. The compiler already implements the
   based-string family for power-of-two bases, e.g.
   `a:array<uint8> = 0x"00 ff ab 12"`, with digits in big-endian order.
   Still undecided: whether the reserved non-power-of-two bases
   (`0t 0s 0d 0z 0r`) pack or are rejected, which separators are allowed,
   and the exact rule relating digit order to a numeric literal reinterpreted
   with `transmute`. See `../resources/discussion_points.md` ("How to input
   byte-arrays").
3. **Keywords (decided).** The hosted `t1` stage carried a note asking
   whether `extern`, `intrinsic`, `none`, `void`, `untyped`, `end`, and
   `new` are keywords (cannot be shadowed, may change parsing) or ordinary
   identifiers the prelude provides (`let none = 5` would be legal).
   Decision: `extern`, `intrinsic`, `none`, `void`, `end`, and `new` are
   all reserved. `end` is the last-index name inside an index expression
   (`xs[end]`). `new` is the NumPy `newaxis` idiom: `myarray[new]` yields
   an array (or view) with an extra singleton dimension at the front,
   `myarray[... new]` at the end, following NumPy exactly. `untyped` was
   only an internal inference marker (`ty.INFERRED_TYPE` still uses the
   string internally) and is not reserved as surface syntax.
4. **Brackets for parametric types (decided).** Whether `array<int>`
   should become `array[int]` or `array(int)`. Dewy's comparison operators
   are `<?` and `>?`, so the usual less-than ambiguity does not arise; the
   one wart is a shift inside a type parameter needing parentheses
   (`something<(a >> b)>`). Both alternatives collide with indexing or
   calls under juxtaposition. Decision: `T<>` stays.
5. **Export control (decided).** Every top-level binding in a module is
   importable today; the question was whether an `export` keyword or a
   privacy modifier is needed. Decision: Python's convention. Everything
   is public, a leading underscore marks a binding as private by
   convention, nothing is enforced. Left alone until people demand more.
6. **Unicode identifiers (partly decided, low priority).** Which non-ASCII
   characters may appear in identifiers (the hosted `t0` stage lists
   candidate additions), and which visually or semantically equivalent
   spellings name the same binding. Decided: subscript digits are distinct
   from plain digits, so `x₁` and `x1` are different names, but `x₁` and
   `x_1` are the same name. Open: the repertoire itself, superscripts, and
   whether look-alike letters such as the micro sign and Greek mu fold
   together.
7. **Unit-like nominal types (decided).** A minted nominal type with no
   fields, such as an error type declared as `Overflow = type of error`,
   is spelled the same way whether used as a type or as its single value:

   ```dewy
   let r:int64 | Overflow = ...
   if r is? Overflow ...     # the type
   return Overflow           # the value
   ```

   Decision: the shared spelling is the language rule and the name is
   usable in both roles. Whether the implementation represents the type
   and its inhabitant as one object or two is internal.
8. **Container method names (decided).** Dewy collapses names that mean
   the same thing across container types (`length`, `pop`); the open item
   was whether sets should keep `add` or use `push` like arrays. Decision:
   `push` is the uniform name for adding to any container, sets included
   (their insertion order is guaranteed, so "push" is meaningful); `pop`
   is the uniform name for removing. Uniform names may take
   container-specific parameters, but the name and the broad signature are
   the same everywhere. `length` is the uniform accessor for both length
   and shape: on a multidimensional array `myarr.length` returns an array
   of dimensions. There is no `size` or `shape`.

Not decisions: the precedence adjustments once listed as open in the
reference's design-status appendix (word `not` below comparisons,
one-direction comparison chains, postfix `or_throw` below `as`, prefix
`type of`) landed on 2026-08-31; see `semantic/precedence.md` and the
2026-08-31 entry in `status.md`. Multidimensional shape syntax is a real
design but belongs to Phase 3.

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
