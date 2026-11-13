# Independent regrade: combining failures, rounds 1–2

The matrix and deductions below were fixed before opening `dogfood.md`. Round 2's amended programs are the objects graded. These are paper-design grades, not compiler/test results. No program was run and no checkout file was changed.

Each tuple is **O / D / C / S / K**: obvious, discoverable, concise, safe by default, complete. 5 means the task has a clear, usable account; 4 means a modest taught rule or limitation; 3 means substantial protocol or an unresolved contract; 2 means a central advertised case contradicts another binding rule; 1 means the task has no credible route. Safety is about preserving failures/cancellation and maintaining the advertised type invariants, not general memory safety. A rejected program primarily loses completeness, rather than automatically losing safety too.

Peer grades assess an idiomatic equivalent preserving the same information, using ordinary classes/records, error collections and explicit cleanup when needed. They do not assume five nonexistent peer implementations were compiled. The anchors in the explanations are lines in `programs/`, identifying the requirement being compared. No deduction is for Dewy's optional parentheses, unfamiliar names alone, or absence of an implementation of this proposal.

Baseline references: [Python exception groups and causes](https://docs.python.org/3/library/exceptions.html), [Go error trees and Join](https://pkg.go.dev/errors), [Rust Result](https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html), [TypeScript discriminated unions and exhaustiveness](https://www.typescriptlang.org/docs/handbook/2/narrowing.html). The Swift comparison uses an explicit error enum/collection and do/catch. These are comparison strategies, not claims that one built-in facility implements this entire proposal.

## Independent matrix

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 combine and match | 4/3/5/5/5 | 4/4/4/5/5 | 4/4/3/5/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/5/5 |
| 02 handler does not swallow | 4/3/5/5/5 | 4/4/4/5/5 | 4/3/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 03 form validation | 5/4/5/5/4 | 5/5/5/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/5/5/5 | 5/5/4/5/5 |
| 04 batch files | 4/3/5/4/3 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/4/5 |
| 05 cleanup written file | 4/3/5/4/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 06 two files fail to close | 4/3/4/4/4 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 07 parallel failures | 4/3/4/4/3 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/4/4/5 | 4/4/3/4/5 |
| 08 library context | 4/4/5/5/4 | 5/5/5/5/5 | 5/5/4/5/5 | 4/4/4/5/5 | 4/4/4/4/5 | 4/4/4/5/5 |
| 09 CLI locations | 4/3/5/4/4 | 5/4/4/5/5 | 4/3/3/4/5 | 4/3/3/5/5 | 4/3/3/4/5 | 4/3/3/4/5 |
| 10 retry | 5/4/5/5/4 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/4/5 |
| 11 combined records | 3/2/5/4/2 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 |
| 12 cancel during cleanup | 4/3/4/5/4 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 13 generic pair | 3/2/5/4/2 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/5/5 |
| 14 transaction rollback | 4/3/5/4/3 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |

Peer K=5 means a sufficiently explicit implementation can express the task; it does not claim a standard library provides this exact abstraction. Repeated C=3/4 and S=4 reflect that explicit implementation burden. Conversely, Dewy's short source does not earn K=5 when its governing contracts contradict one another.

## Deductions, with line anchors

**01 — `01_combine_and_match.dewy`.** O4 at 18–23: the same `QuotaExceeded` selector takes the pair in `is?` but excludes it in `match`. D3 at 18–26: knowing ordinary type tests does not reveal that distinction, or when a parameter projects rather than preserves the value. C/S/K5: the shown, concretely distinct pair is short and each error is reported. For the four cases at 9–21, Python needs a group or explicit composite and its dispatch protocol (O/D/C4); Go, Rust and Swift need composite variants plus dispatch (O/D4, C3); TypeScript needs discriminants/guards and a convention preserving unmatched fields (O/D4, C3, S4). No peer is penalized for failing to use Dewy's spelling.

**02 — `02_handler_does_not_swallow.dewy`.** O4 at 14–15: a parse fallback deliberately does nothing to a parse-plus-close result. D3 at 11–15: the all-parts test and automatic cleanup alternatives must both be learned. S5: this particular program forwards the unhandled pair at 17; the dropped-part-check counterexamples in review M2 are not present here. Python's subgroup handling can retain unmatched failures, but translating this value-producing fallback takes a taught group/catch protocol (O/D/C4). Go's child-finding error helpers do not themselves implement “all leaves covered”; O4/D3/C3/S4 for writing that policy. Rust's explicit enum is O/D4/C3 with exhaustive handling S5. TypeScript and Swift need explicit whole-composite recovery code rather than a general catch/default (O/D4/C3/S4). Anchors: 12, 14–17.

**03 — `03_form_validation.dewy`.** D4 at 12, 18: constructing a nonempty failure collection and matching it as a stack need documentation. K4 at those lines: round 2 specifies nonempty construction but leaves inherited shrinking/mutable-array access unresolved (review M6). The local length guard is sound and obvious; O/S5. Peer equivalents collect ordinary field problems and return a success-or-list value; Go, Rust and Swift need a result wrapper or enum (C4 at the equivalent of 12–18). Python and TypeScript can express the validation task directly. They are not credited with a statically nonempty mutable array for free.

**04 — `04_batch_files.dewy`.** O4/D3 at 3–7: the source relies on the surprising assertion that a one-shot path read cannot return read-plus-close or decode-plus-close failures. S4/K3 at 7, 12, 18–19: preserving such failures in the declared element type has no specified implementation (review M4), and the eventual stack also needs M6's invariant. C5: the collection idiom is good. For the same skip/report/cancel task at 10–18, all peers need separate cancellation and ordinary-error collection paths (D4/C4); Go, TypeScript and Swift also need an explicit convention preventing cancellation from entering the ordinary failures (S4). Python and Rust can use their explicit exception/result partition for S5. The peer grades assume explicit read/close preservation, not a helper silently dropping its close error.

**05 — `05_cleanup_written_file.dewy`.** O4 at 5–9: the additional exit is at cleanup, which is accepted design but still taught. D3 at 15–20: `FileError` covers a pair in a pattern but cannot hold that pair as an ordinary parameter/local type; arm order additionally matters. S4 at 7: “wrote … rows” is printed before final flush/close establishes completion. K5 for the single-owner ordinary-error path. Every peer equivalent needs an explicit finish/close and preservation of both failure results (O/D4, C4 in Python/Go and C3 in Rust/TypeScript/Swift, anchors 5–9, 15–20). S4 reflects the risk of omitting the second failure or announcing success too early, not an allegation that an explicitly correct peer implementation is impossible.

**06 — `06_two_files_fail_to_close.dewy`.** O4/D3 at 11–15: stack-vs-single shape depends on the live-owner set even if only one close actually fails. C4 at 19–23: inspect the stack, then separately forward the original. S4/K4 at 11–15: inline cleanup storage is plausible, but the general reservation/transfer contract claimed by the design is not established (M5), and stack nonemptiness needs M6. All peers need two cleanup attempts, aggregation, and preservation of the body failure (O/D4/C3/S4, anchored at 5–15). Their K5 is for that explicit implementation, without the extra promise that a changing live-owner set has one inferred exact result type.

**07 — `07_parallel_failures.dewy`.** O4/D3/C4 at 10–12 and 17–23: a collector, a manual partition and a stack coexist with a different proposed automatic block-combination path. S4/K3 at 4, 8, 12, 22–23: one-shot cleanup preservation is unresolved; the second half explicitly needs a concurrency extension and a rule distinguishing independent failure from cancellation induced by a sibling. Naming it an extension is honest but does not make this end-to-end case complete. All peers need a collect-all strategy plus deterministic ordering and cancellation handling (O/D4/S4 at 10–12, 22–23); Python/TypeScript C4 and Go/Rust/Swift C3 for that protocol. No peer gets automatic fail-fast task aggregation credited as collect-all.

**08 — `08_library_context.dewy`.** O4/D4 at 18–23: cause wrapping is a good rule but must be learned separately from combination. K4 at 4, 18–23: `cause:error` closes the ordinary-error boundary, but cancellation still exposes `Canceled & FileCloseFailed`; the advertised one-domain-error abstraction does not cover cleanup during cancellation. This is preserved, so S5. Python has a direct cause idiom; Go needs a domain wrapper (C4); Rust and Swift need a wrapper/enum plus forwarding branch (O/D/C4); TypeScript needs those and a cancellation discrimination convention (O/D/C/S4). Anchors: 4, 18–23. These scores concern domain translation, not a claim that every peer's typed public signature is as precise.

**09 — `09_cli_locations.dewy`.** O4/D3 at 14: one line hides flattening of combinations/stacks, construction-site demand, and the I/O caller-site override. S4/K4 at 5–9, 14: retaining metadata and the two-owner cleanup result needs the storage and boundary contracts discussed in M5 and S4; this is not a demonstrated zero-cost facility. C5: the reporting loop is excellent. Python's exception traceback/cause inspection needs a taught traversal (D4/C4). Go/Rust/TypeScript/Swift need explicit source-location capture plus a tree/collection walk for equivalent locations (O4/D3/C3 at 14, 18–21); Go/TypeScript/Swift S4 for maintaining that capture/preservation convention, Rust S5 for an explicit typed representation. K5 for an explicit capture design, not for retrospective recovery of an uncaptured origin.

**10 — `10_retry.dewy`.** D4/K4 at 9, 15–16: the stack name/last-element proof is learnable, but the type's permanent nonempty invariant needs the mutation contract in M6. O/C/S5: the local push proves the construction, cancellation is forwarded before accumulation, and the loop is short. All peers need a cancellation branch and accumulated-attempt reporting (D4/C4, anchors 6–10, 15–19); Go/TypeScript/Swift S4 for the manual cancellation distinction. Python/Rust S5 given their explicit partition. No deduction is for backoff policy or network-library design outside the brief.

**11 — `11_combined_records.dewy`.** O3/D2/K2 at 3, 6, 9, 13–15: the example requires two independent `id` fields in a value typed `User & Settings`, while the existing record intersection denotes one merged `id`. An alias declaration and a parameter annotation cannot silently give the identical type expression different meanings (M1). S4: no consistent account is supplied for preserving both facets while respecting code expecting the merged-record contract. C5: the desired source is compact. All peers can use a product with named `user` and `settings` fields, preserving ids 7 and 31 (C4 for explicit projections at 7–10 and construction at 15; O/D/S/K5). TypeScript object intersection/spread is not credited with preserving two same-named fields; its comparator is the explicit product too.

**12 — `12_cancel_during_cleanup.dewy`.** O4/D3 at 17–21: the reader must know coverage, dominance and the fact that a `FileError` pattern can bind a whole ordinary pair. C4 at 17: merging two arms saved a body but still repeats the concrete cleanup shape in the cancellation selector. A single-value `Canceled` handler is not future-proof if another owner is added. K4 at 10–11, 17: no declarable abstraction over arbitrary cancellation-plus-cleanup shapes is supplied. S5: this specific code prints and returns the complete canceled result. Every peer needs a deliberate shielded cleanup path and a combined canceled/cleanup result (O/D4/C3/S4, anchors 8–19). Explicit code can complete the task (K5); no peer is assumed to obtain this from a generic defaulting operator.

**13 — `13_generic_pair.dewy`.** O3/D2/K2 at 2–5, 17: a concrete duplicate is a binding compile error, but abstracting the same operation makes it construct a stack. This is a new semantic exception, not an established generic rule (M3). S4 at 2–7: unconstrained `T`/`U` can include `void` or `Canceled`, defeating the claimed failure-only and never-canceled stack invariants. C5: once those contracts are supplied the helper is short. Python needs a runtime typed aggregate (O/D/C/S4); Go and TypeScript need erased/tagged aggregate dispatch and validation (O/D4/C3/S4); Rust and Swift need an explicit generic product/sum representation (O/D4/C3, S5). Anchors: 2–8, 15–19. Their representations may keep a pair of equal-typed errors; they are not subject to Dewy's specific duplicate prohibition.

**14 — `14_transaction_rollback.dewy`.** O4/D3 at 12–15: the success of an explicit commit changes whether automatic rollback runs; its failure needs a stated owner-state contract. S4/K3 at 12–15: if a failed commit leaves rollback pending, `CommitFailed & RollbackFailed` is missing from the purported inferred result (M4); if not, the alternative failure/ownership policy is unstated. C5: the business logic is short. Every peer needs explicit transaction completion and preservation of the primary plus rollback failure (O/D4/S4, anchors 6–15); Python/Go C4, Rust/TypeScript/Swift C3. K5 means an explicit commit-state/rollback contract can express it, not that a particular unspecified database driver guarantees rollback after every commit failure.

## Fixed independent result

Floor **2**, in **11** (discoverable and complete) and **13** (discoverable and complete). The guarded nonempty constructors in round 2 are an improvement; the largest remaining deductions concern contracts inside this design's scope, not the spelling of `ErrorStack`.

## Differences from the author

After fixing the matrix, I read `dogfood.md`. No independent grade changed. The following are **all absolute differences of at least two points**, against the author's round-2 Dewy column and peer columns. Values are independent versus author; axes omitted from a row differ by less than two.

| Program | Language | Differences |
|---|---|---|
| 01 | Python | S 5 vs 3 |
| 01 | Go | C 3 vs 5; S 5 vs 3 |
| 01 | TypeScript | S 4 vs 2; K 5 vs 3 |
| 02 | Go | S 4 vs 2; K 5 vs 3 |
| 02 | Rust | S 5 vs 3; K 5 vs 3 |
| 02 | TypeScript | K 5 vs 3 |
| 02 | Swift | K 5 vs 3 |
| 04 | Dewy | K 3 vs 5 |
| 05 | TypeScript | C 3 vs 5 |
| 06 | Python | K 5 vs 3 |
| 06 | Rust | K 5 vs 3 |
| 06 | Swift | S 4 vs 2; K 5 vs 2 |
| 08 | Python | S 5 vs 3 |
| 09 | Go | K 5 vs 3 |
| 09 | Rust | K 5 vs 3 |
| 09 | TypeScript | K 5 vs 3 |
| 09 | Swift | K 5 vs 3 |
| 11 | Dewy | D 2 vs 5; K 2 vs 5 |
| 11 | TypeScript | S 5 vs 2; K 5 vs 3 |
| 13 | Dewy | D 2 vs 4; K 2 vs 5 |
| 13 | Go | C 3 vs 5 |
| 13 | TypeScript | S 4 vs 2; K 5 vs 3 |
| 14 | Dewy | K 3 vs 5 |
| 14 | Python | K 5 vs 3 |
| 14 | Go | K 5 vs 3 |
| 14 | Rust | C 3 vs 5; K 5 vs 3 |
| 14 | TypeScript | K 5 vs 3 |
| 14 | Swift | K 5 vs 3 |

The Dewy differences follow concrete contracts: one-shot cleanup preservation (04), conflicting record-intersection meanings (11), a changed duplicate rule and missing generic restrictions (13), and failed-commit owner state/composition (14). They are not spelling objections. The claims that the remaining deductions are all outside this design and that no part can disappear without a compile error are not supported by the proposed variable-only check (review M2).

The peer differences partly expose a comparison-policy issue. The author often grades **default cleanup idioms** that omit a completion error; I credit a **deliberate explicit preserving implementation**, charging its verbosity/discoverability/safety costs. For example, Rust can call an explicit fallible completion operation before Drop, Swift can attempt cleanup in ordinary do/catch code, and Go can join returned close failures. Their K is not limited to what Drop/defer does automatically. That is why I do not carry the author's K=2/3 default-cleanup scores into a claim that these languages cannot complete the workload. Equally, Go Join alone does not identify four typed outcomes or implement whole-leaf fallback coverage, so I do not credit the complete 01/13 task with C5.

For TypeScript 11, the comparison should preserve both ids with `{user, settings}` rather than intentionally overwrite one with object spread. For TypeScript 01/13, a discriminated result/composite avoids making an untyped AggregateError the only option. For Python 01/08, propagation of unmatched exception-group leaves and explicit cause wrapping are useful safety mechanisms even without static result checking. For 09, explicit construction-site capture is a complete alternative with substantial ceremony; no peer gets an unrecorded trace reconstructed for free. These are reasons for the differences, not executed peer-code evidence or a claim that their default cleanup semantics equal Dewy's proposed automatic preservation.
