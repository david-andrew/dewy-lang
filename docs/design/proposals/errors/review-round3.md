# Independent review: combining failures, rounds 1–3

Verdict: the ordered-tree design is a useful foundation, but the current recommendation needs two corrections before being presented as settled. Program 09 starts recovery despite cancellation already present in its input; the case against an intersection-valued `&` also relies on claims about information loss that do not follow from the type. The separate resource-exhaustion gate remains unresolved and correctly disclosed.

Scope: review of the supplied designs, twelve paper programs, names, model and comparisons against the binding Dewy decisions. Owned outputs: this file and regrade-round3.md only. Non-goals: implementation, naming cold reads, new decisions, cleanup timing, concurrency redesign, repository edits or commits. Budget: approximately 90 minutes. The checkout was read-only. No agents were launched.

## Must-fix findings

### M1 — Forward incoming cancellation before selective recovery

**Location:** `programs/09_selective_recovery.dewy:7–16`, especially `stopped = false` at line 9; `round2.md:136`; the existing model's recovery test begins with an uncanceled input and only injects cancellation during recovery.

**Concrete scenario:** call `recover_missing(errors.join(Canceled MissingAsset[p"thumb.txt" "missing"]))`. Split puts the canceled subtree in `parts.rest`, puts the missing leaf in `parts.matched`, and starts the regeneration at line 16. It does so even though the incoming failure already carries cancellation. The stop flag handles only a *new* bare Canceled returned by regeneration. If the current task is not itself canceled, as with an explicitly transported cancellation value, this can perform a real write. If it is canceled, correctness should still not depend on the callee's next checkpoint stopping the work.

**Suggested fix:** change line 7 to `let parts = errors.split<MissingAsset>(failure or_throw<Canceled>)`. Under the proposal's own descendant-aware rule, this forwards the original input whole before recovery. Then retain the existing stop logic for cancellation that first occurs during recovery. Add model cases with cancellation before, between and after matching leaves, including nested/contextual groups; assert zero callbacks and exact preservation of the input occurrence/context sequence. Also exercise the same guard under `$explicit_cancellation` after erased storage.

**Evidence:** an in-memory probe using the supplied model constructed Canceled + MissingAsset and followed the program's selection loop: it attempted occurrence 2. The proposed pre-split selector returned `forward`. No files or device calls were used. The regrade records this additional counterexample separately from the initial independent scores.

### M2 — Correct the reason for rejecting `E1 & E2`

**Location:** `round1.md:39`, `round2.md:72`, and the opening recommendation in `summary.md`.

**Concrete scenario:** a value can carry `[a, b, a]` in ordered storage even when its public type simplifies to `A & B`. Types do not normally encode insertion order or runtime multiplicity. In particular, `A & A = A` does not prove that a value typed A cannot retain two A occurrences in separate storage. The summary currently presents these as impossibility arguments, making David's strongest alternative look weaker than it is.

**Suggested fix:** replace that rationale with the full steelman and the actual substitution/cancellation objections below. Explicitly distinguish an error-value `&` overload returning a group from a universal combination whose resulting type really is the existing intersection. The former is viable and may be ergonomic; the latter needs semantic changes. Keep the recommendation provisional, rather than implying that ordered storage alone decides it.

## Strongest case for David's operator, then the judgment

At value level `a & b` could allocate a composite containing two exact occurrences. The value, not its type, preserves order, duplicates, origins and separate payloads. A direct-parts view splits them back out, and an array remains the right many-item accumulator. Existing type-level `&` already means conjunction; an error-valued overload can read naturally as “both failures.” An intersection type need not encode every property of that value. With distinct structural fields, an aggregate could in principle also supply both interfaces. The notation saves ceremony in the especially common body-plus-cleanup pair, and the rest of this proposal already provides the storage and splitting machinery it needs.

The difficulty is what promises a value of `A & B` must satisfy, beyond containing an A and a B:

- With `A[message="read failed"]` and `B[message="close failed"]`, the combined value has one ordinary `.message` projection if it is substitutable as both records. Choosing the left message is possible when both fields merely have type string, but loses the other projection at that interface; it needs an explicit policy. Distinct refinements, such as message singleton types, can make the intersection genuinely unsatisfiable. Ordered side storage does not solve incompatible constraints.
- Repeated A values can be stored, but `g is? A`, passing g to an A parameter, and `??<A>` then operate on something statically indistinguishable from one A. Which payload does the ordinary A handler see, and is handling that projection allowed to consume its siblings? This is a substitution/handling question, not a storage impossibility.
- Most decisively, `Canceled & CloseFailed` would have to satisfy CloseFailed and therefore `error`. An ordinary `is? error` handler would then catch a cancellation-bearing composite. Preserving the established cancellation boundary requires giving up that intersection typing, changing family matching, or restricting which combinations are legal. The proposal's separate ExceptionGroup deliberately avoids this problem.
- Dewy's current nominal families and non-generative record intersections do not already define an ordered composite that is simultaneously several independently minted error kinds. This would be a proposed semantic extension, not a free consequence of existing `&`.

**Judgment:** an operator overload returning the same ordered group as join is viable and deserves an honest choice on readability; no algebraic law requires an overloaded value operator to return a type intersection. Universal intersection typing does not fit the current nominal matching and cancellation rules without further decisions. I provisionally prefer join for an initial API, but the correct reason is the unresolved projection/substitution contract, especially cancellation, not the inability of values to store order or duplicates.

## Should-fix findings

### S1 — Evaluate the viable single-type alternative explicitly

**Location:** `round1.md:47`; `round2.md:66,199`; `round3.md:58`.

**Scenario:** one group type derived directly from `exception`, outside `error`, can hold both all-error and canceled groups. The cached cancellation rule still forwards a carrying group through `??`; broad `is? error` never swallows it. Therefore the assertion that one type necessarily reintroduces the broad-handler bug or requires data-dependent nominal subtyping is too strong.

**Fix:** compare this alternative on its real cost: even a group of ordinary errors no longer satisfies `error`, `or_throw<error>` no longer forwards it, and APIs accepting `error` need widening or explicit group handling. A single type under `error` is unsafe for cancellation without special matching; a single type under `exception` is safe but less compatible. I favor retaining the two nominal classes if preserving all-error family handling is a requirement. Most callers can learn only join/leaves/split and never name either class, as programs 02–05 demonstrate. Explain the tradeoff rather than saying one type is impossible. Python's analogous two-family solution also retains a common group superclass; Dewy's proposed classes deliberately do not have that relationship. [Python exception groups](https://docs.python.org/3/library/exceptions.html#exception-groups).

### S2 — Reduce the recovery protocol before inventing more language machinery

**Location:** `programs/09_selective_recovery.dewy:7–25`; `round2.md:108–112`; `round3.md:59`.

**Scenario:** recovering one leaf kind requires two zero-or-one root arrays, two loops, repeated narrowing to the selected kind, a remainder accumulator and a stop flag. Deleting the initial rest assignment loses unrelated failures even though the result record itself remains used; a generic unused-binding diagnostic need not detect unused fields. M1 shows another easy omission. These are ergonomic and safety costs on one of David's central requests.

**Fix:** prototype a reusable ordinary-library recovery operation, or a simpler typed matching-leaf view with an explicit preserved remainder, before concluding only a language-wide linear effect system can help. Require the helper to preserve unmatched failures, retain an original leaf when its recovery fails, stop on cancellation, and retain not-yet-attempted matches. Do not choose a public spelling until cold-tested. The low-level split can remain an advanced escape hatch.

Ordinary `??<FileError>` retaining a group is coherent with `is?` and today's nominal selector rule. Making “contains FileError” default the *whole* group is unsafe because it erases siblings; I reject that interpretation. But it is not the only descendant-aware design: Python `except*` partitions, handles only matching subgroups and automatically propagates unmatched and newly raised failures. This is a materially safer default than returning an ordinary rest field. Keep the current outer-only `??` rule for a first version, with the proposed group-only selector diagnostic, while acknowledging the recovery ergonomics gap. [Python except*](https://docs.python.org/3/reference/compound_stmts.html#except-star). Go's tree-searching Is/As are another source of user expectations, but finding a child does not itself partition or recover it. [Go errors](https://pkg.go.dev/errors).

### S3 — Cut the first-version diagnostic surface

**Location:** `names.txt`; `round2.md:144–174`; `programs/06_cli_diagnostics.dewy:16–20` and `10_domain_cause.dewy:6–13`.

**Scenario:** joining two failures introduces two group names, immediate parts, leaves, split, transparent context, cause translation, four metadata members, a reporter, trace options, a trace setting, trace status alternatives and location/trace record types. The core application paths are short, but the diagnostic contract is a second substantial subsystem.

**Fix:** first version: join; immediate ordered parts; uniform leaf iteration; low-level split; origin; one type-preserving context operation; and whole-tree reporting with an explicit location option. Retain the existing array accumulator. Defer caused_by/$cause, public context-frame inspection, $trace/ErrorTrace/statuses and the trace setting. Causes were optional in the brief (“if it falls out”); async/target-specific stack capture clearly does not fall out of a four-byte origin token. The reporter may traverse private context frames before a public $context API exists. Keep origin and requested display distinct. Program 10 and the trace-specific portion of 06 become later work, not hidden dependencies of joining errors.

### S4 — State the broad cost of default origins, including none

**Location:** `round2.md:156–168,195`; `programs/11_occurrence_origins.dewy:6–18`.

**Scenario:** “every newly constructed exception” includes none, since none is an exception in the binding language. Origin-bearing unit sentinels and optional values can therefore enlarge arrays, record fields, unions, return buffers and calling conventions far outside visibly failing operations. Even a successful call that constructs optional absence may carry the token. “Successful operations execute no capture work” does not establish zero successful-path cost from layout and ABI changes. Binary source tables also disclose build-relative filenames/function names even if report display is off.

**Fix:** keep the existing warning about alignment and binary size, but explicitly state whether none participates and what this means for optionals and success-path layout. Measure representation sizes and instruction counts for unit errors, common T? values, error-bearing result arrays and ordinary successes, including precompiled boundaries, before describing the default as cheap. The existing flagship/binary-size gate is necessary but should include these cases. Default-on source sites are a reasonable provisional choice; their cost is **warned about but not yet shown acceptable**. Do not add a new opt-out spelling merely to avoid measuring it. Bounded opt-in traces already carry a substantially better warning.

### S5 — Define repeated cause attachment, or leave causes out of v1

**Location:** `round2.md:150`; `round3.md:38,52`; `semantics_model.py:49–52`.

**Scenario:** `caused_by(caused_by(ConfigError[...] read_failure) parse_failure)` silently replaces the first cause in the model. A second layer of a library can destroy an existing diagnostic chain; an owning first cause additionally needs a specified completion/transfer policy. The nongroup-outer restriction does not prevent this case.

**Fix:** specify whether the operation rejects an existing cause, replaces it deliberately, or creates another outer domain value. A fresh-outer convention is insufficient for erased values unless the rule is enforceable. Add repeated-attachment coverage with an owning cause if the API stays. The simplest first-version answer is to defer caused_by with the rest of the causal API. The probe confirmed the first cause was absent after the second attachment; no source file was changed.

## Notes and acceptance boundaries

### N1 — Cancellation and selector changes are declared, not already decided

`decisions.md:510–514` and `LANGUAGE.md:4179–4185` make selected propagation follow matching. `round2.md:98` and `round3.md:48–50` explicitly introduce the descendant-aware Canceled exception, carry-state refinement and an impossible-selector exception. This is a semantic extension requiring review, but it is not concealed. The API must teach `is? Canceled = false` alongside `or_throw<Canceled> = forward` for a carrying group. Batch 9's placement of settings and assigned dunder functions is followed in programs 01, 06 and 08. Ordinary string interpolation is valid; the “fmt only” rule forbids alternate format-spec syntax, not these plain interpolations (`decisions.md:470–475`). I found no unacknowledged new parser spelling.

### N2 — Cleanup and parallel extensions must stay separately gated

`round2.md:140` proposes retaining additional parallel failures beyond the current first-failure rule, and line 174 proposes dynamic group exit codes. Both are identified as extensions. D40 Q2 timing and the visible-exit issue remain open; a review of error composition cannot approve them. The CPU-only parallel example is valid evidence for its stated deterministic all-results scenario, not evidence for canceled waiting collect-all. The proposed first-ordinary-leaf exit-code priority also needs a deliberate body+cleanup example; do not infer general cleanup-code precedence from the Canceled+close example alone.

### N3 — The lossless allocation-exhaustion problem is a real implementation blocker

`round2.md:186` and `programs/01_cleanup_pair.dewy:31` correctly disclose it. With a pending owning failure and a failed completion, an allocation needed to create the group can itself fail; returning only OutOfMemory loses failures, and printing them does not preserve their values. Do not label automatic cleanup grouping complete or remove K3 until reservation/ownership-preserving construction has a concrete contract, including reservation refusal before acquiring the owner, an initially returned foreign owner, and subsequent transfers. This is an acknowledged blocker before implementation acceptance, not a newly discovered undisclosed defect or a demand to implement the compiler in this review.

### N4 — Model checks validate the algebra, not the advertised representation

I reran `python3 -B semantics_model.py`: PASS, 10,885 partition cases plus the stated extra checks. Deep iterative leaves/split traversal passes. The model computes canceled recursively (`semantics_model.py:21–22`), rather than testing an O(1) cached bit, and represents inherited paths with tuple concatenation (`:60,63`), rather than the proposed shared paths. Thus it is not evidence for cached cancellation, ABI preservation, linear-time context traversal, ownership, allocation, traces or scheduling. The author already bounds most of those claims honestly. Add M1's incoming-cancellation case to the algebra checks.

The first independent matrix was written before reading dogfood.md. Afterward, a separate adversarial probe found M1; only program 09's S and K grades were revised on that new evidence, with the original tuple retained in regrade-round3.md. Final Dewy floor: 2 for cancellation discoverability (08) and selective-recovery concision (09). No naming cold-read or all-5 claim is justified.
