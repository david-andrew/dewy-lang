Verdict: keep the typed, unordered failure combinations, but do not accept Part 2 as an implementable contract yet.
Must-fix: 8; should-fix: 4; notes: 3. These count independent contract repairs, not examples.
C1/C2 still disagree about projection, semantic equivalence, and when a test proves a conversion.
C3 needs transfer-preserving obligations and a finite, conservative provenance abstraction before its complexity claim is credible.
C4's escaping slots are promising, but allocation-refusal transport and C5's remaining suppression/public API policies need explicit contracts.

## Scope and evidence

Reviewed `docs/design/proposals/errors/combined/round4.md` in full, the earlier rounds and independent reviews, D42 and D40 in `open_decisions.md`, decisions batches 9–10, the relevant language/ownership/allocation contracts, and selected compiler/runtime implementation. Locations below refer to `round4.md` unless another file is named. The examples are self-contained paper counterexamples under the proposed language, not claims that today's compiler implements it. No compiler builds, repository tests, benchmarks, commits, or repository edits were performed. The sole output is this file. Budget: approximately 90 minutes; non-goals include implementation, naming choices, and redesigning cleanup timing.

## Must-fix findings

### M1 — C2's two definitions of semantic coverage are inequivalent

**Contract and lines:** C1:199–208; C2:224–245, especially 229–231.

**Scenario:** deleting impossible disjuncts fixes the previous review's example but does not fix redundant satisfiable disjuncts. For `X = A & B`, the selectors `A` and `A | (A & B)` select exactly the same values. The only inclusion-minimal sub-combination of X satisfying either selector is A. Nevertheless the proposed per-conjunct projection algorithm collects A from the first disjunct and A & B from the redundant second disjunct, and therefore consumes B too.

```dewy
A:type = type of error
B:type = type of error
ordinary = () => (A and B) ??<A> 0
redundant = () => (A and B) ??<A | (A & B)> 0
negative = () => (A and B) ??<A & ~Canceled> 0
main = () => {
    let x = ordinary
    let y = redundant
    let z = negative
    printl("{x} / {y} / {z}")
    x;
    y;
    z;
}
```

The first two results must agree under semantic coverage. The per-conjunct algorithm instead retains the pair for `ordinary` and yields 0 for `redundant`. Absorption normalization alone is insufficient: for `negative`, the smallest satisfying subset is again A, but `as ~Canceled` keeps both noncancellation facets. C1's union-of-projections for `A & ~Canceled` consequently keeps both, making the algorithm consume B. A negative constraint has supplied coverage for an unrelated positive part.

There is a separate failure of the claimed equivalence: two file failures with shared `path` both satisfy `FileError`. Each singleton is a minimal satisfying subset, so the minimal-subset definition covers both. But `X as FileError` is explicitly ambiguous at C1:206–208; the supposed equivalent algorithm cannot even evaluate its required projection.

The cost claim omits selector normalization. A selector `(A1 | B1) & ... & (An | Bn)` has 2^n conjunctions in disjunctive form. The 16-facet limit does not bound selector size or work performed before that limit is applied.

**Suggested fix:** retain one definition in terms of inclusion-minimal nonempty satisfying subsets, or specify another coherent semantic rule for David to assess. Define “smallest” as inclusion-minimal rather than minimum cardinality if witnesses of different sizes should all count. Do not implement coverage by reusing `as`. Provide a bounded symbolic solver or a disclosed conservative rejection policy, with a bound on normalization as well as facet search. Test redundant live disjuncts, absorption, negative conjuncts, family targets with shared fields, and factored/distributed equivalent selectors. A bounded exhaustive subset implementation has up to 2^F subsets before predicate cost; it is not the advertised single facet pass per conjunction.

### M2 — C3 treats internal transport as discharge, permitting unnamed loss

**Contract and lines:** C3:249–266, 277–281, 293–299.

**Scenario:** a block's value is listed as discharging the occurrence, whereas its receiving binding is merely another representative. No new occurrence is specified at that boundary:

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
lose = ():>void => {
    let saved = { pair }
    printl(saved)
}
main = () => lose
```

The block forwards `pair` as its value, clearing A and B under 258–259. `saved` then ends after observation with no parts owed, although no handler, function return, or explicit drop named either failure. Introducing braces has defeated D1. If block forwarding instead introduces a new obligation, that rule is missing and must preserve provenance through copies rather than reset it accidentally.

The container clauses directly conflict. At 261–262, storing into an aggregate discharges nothing. At 296–297, “storing ... the whole container” discharges its occurrences. The following ordinary nesting can therefore erase the same duty under the latter wording:

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
lose = ():>void => {
    let items = [pair]
    let nested = [items]
    printl(nested.length)
}
main = () => lose
```

These are transport boundaries, not acknowledgment. The same distinction is needed for a returned representative in call summaries: a callee forwarding a parameter transfers a duty to its result, while a callee actually handling it acknowledges it.

**Suggested fix:** separate acknowledgment from transfer in every rule and summary. Internal block handoff, storage, capture, projection, and returned provenance carry outstanding obligations to their receiving places. A return can complete the current function's responsibility while preserving the receiver's responsibility. Define exactly which external handoffs count as forwarding out of this analysis. Reserve global discharge of the shared occurrence for genuine handling or explicit dropping. Add negative tests for these two examples and positive tests that subsequently handle the transported value.

### M3 — C4 does not close the allocation-refusal path, especially during cancellation

**Contract and lines:** C4:309–337, especially 312–313, 319–329; C5:346–358. Related established behavior: `docs/LANGUAGE.md:5223–5236`; `compiler/oom.jo:1–16`; `compiler/oom_ops.jo:88–101`; `lib/std/oom.jo:49–61`.

**Scenario and walkthrough:** the reservation scheme can avoid allocating *a link node* at ordinary cleanup. It still needs a contract for transporting the result through allocation unwinding:

1. Acquire F1, successfully reserving its escaping slot.
2. Attempt acquisition of F2. Reservation is refused before F2 exists, as C4 requires.
3. F1 still exists and its close fails. The function must return `OutOfMemory & FileCloseFailed`, not just `OutOfMemory`.
4. The established explicit-allocation-failure mechanism drops owners and jumps to a wrapper that returns only `OutOfMemory`. Neither that wrapper nor its documented result rule provides a pending-failure accumulator carrying the filled slot. C4's statement “nothing to clean up” is true of F2 only, not the enclosing function.

The refused-`push` example has the same integration gap: ordinary allocation refusal currently exits the nearest allocation-failure function frame; it is not inherently a local `push` result leaving control in that statement. The live temporary must be registered before growth is attempted, and its failure must survive the jump. Merely allocating a slot does not accomplish either transfer.

Cancellation adds a second pending value. Suppose `Canceled` is already propagating, cleanup constructs a dynamic failure payload or boxes a previously inline pending result, and that allocation is refused. Cancellation shielding prevents another cancellation from interrupting cleanup; it does not make allocation infallible. Without an allocation-free construction rule and an unwind accumulator, the wrapper can replace `Canceled` and previously collected cleanup failures with `OutOfMemory`. Cleanup can also be interrupted before the resource's actual release. The present runtime unlinks an owner before calling its hook (`lib/core/rt.jo:1246–1253`), so recovering from interruption cannot assume that owner is still on the unwind list.

For narrow file failures with an already retained path and static message, writing into a correctly sized reserved slot is plausible. For arbitrary fallible owners, “a slot holds the failure” does not prove that producing its payload, preserving an inline pending value by reference, or releasing the remaining resources requires no allocation. Existing user lifecycle-hook checks reject allocation (`compiler/ownership_hooks.jo:139–148`); C4 must say which restrictions survive the new fallible completion path, including trusted library adapters.

User-written `stack and e`/`ErrorStack[xs...]` is explicitly excluded from C4's lossless promise. Under the current ordinary policy it may terminate the process, or under explicit allocation failure replace the attempted result with `OutOfMemory`. That limitation should be stated plainly; it cannot be used as the implementation of automatic cleanup.

**Suggested fix:** specify a nonallocating unwind accumulator whose lifetime survives allocation-frame exit, how an initial `OutOfMemory` and any already pending `Canceled`/body failure enter it, and how all reserved slots reach the caller. Infer the full cleanup-augmented result, not merely `T | OutOfMemory`. Retain/prove no-allocation requirements for the whole automatic completion path, including payload construction and pending-value storage; otherwise define its nested-refusal behavior and guaranteed release backstop. Add refusal at F2 acquisition with an already live failing F1, refusal while cancellation is pending, refusal during failure-payload creation, and nested allocation frames to the existing gate. This is a missing integration/guarantee contract, not a demand that the paper proposal already be implemented. Preserve the documented WebAssembly limitation explicitly unless changing it is separately authorized.

### M4 — C3 has not specified a finite analysis with the claimed complexity or demand boundary

**Contract and lines:** C3:249–256, 264–266, 277–281, 293–305.

**Scenario:** dynamic arrays and loops invalidate the equation “one creation point = one occurrence.” This function creates an arbitrary number of independent failures at one call site:

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
partial = (n:int<(>=? 2)>):>void => {
    let xs:array<A & B> = []
    loop _ in [0..n) xs.push(pair)
    let last = xs.pop
    last ??<A | B> void
    printl(xs.length)
}
main = () => partial(2)
```

Handling `last` must not discharge the independent remaining elements. An exact dynamic occurrence inventory and representative count are unbounded; a single bitset at the creation site cannot distinguish a handled instance from outstanding instances without an additional multiplicity/provenance abstraction. Fixed fields, dynamic arrays, copied aggregates and conditional aliases also need a place-to-origin relation. A representative count alone cannot identify which occurrence a killed or projected place represented. At branch joins, a representative that exists only on another path must not postpone the last-representative check on the current path. The existing copy liveness walk is conservative (for example `compiler/copy_ops.jo:294–320`); reusing it does not supply these provenance/count joins automatically.

The interprocedural domain is incomplete too. A per-parameter “returns a representative” boolean does not distinguish may-return from must-return, partial projections, or conditional selection between two arguments. A helper that handles one of two parameters on each branch, when passed the *same* occurrence for both, discharges it on every path although neither parameter has a guaranteed individual discharge. Conservative rejection is possible, but must be admitted as a precision limit rather than described as an exact per-path rule.

There is also an unresolved checking boundary in the proposal's own `observe(v:A & B)` at line 285. As written, its parameter is its last representative inside that function and ends owing both parts. To allow the example, parameter checks must export unmet duties to the caller or model an external representative. Summaries alone do not state this exemption for local diagnostics.

**Decidability:** exact acceptance on all feasible execution paths is undecidable for general Dewy loops/calls. A conservative finite CFG analysis is decidable. The proposal gestures toward the latter but does not define its joins, count abstraction, provenance domain, or transfer lattice. Thus there is no justified finite-lattice proof or complete worst-case bound *as specified*. This is repairable; it is not a claim that the feature requires an undecidable implementation.

**Complexity:** let V/E be CFG nodes/edges, O indexed static origin classes, R relevant places, P part types, W bitset words, and A the number of possible place-origin associations (up to O×R). Storing one owed set and count per origin omits A. A straightforward finite implementation storing state at each point needs up to `O(V * (O*W + A))` state, plus call summaries. With I intraprocedural propagation rounds, a simple full-state implementation costs `O(I * E * (O*W + A))`, plus summary application and SCC iteration. These are bounds for an explicitly chosen representation, not measurements or a bound established by the current text. The lattice height must bound I, and summary-lattice height must bound interprocedural iteration. Exact correlated-path tracking can be exponential even in loop-free code; loops additionally require a finite abstraction. The 64-part fallback limits W, not O, A, loop multiplicity, or summary iterations.

Typical straight-line code with a few compound origins, sparse provenance, and one-word owed sets can be close to linear in the relevant flow edges, with small constant summary work. That useful expectation does not justify claiming `edges × occurrences × words` for all code.

**Demand:** “only in functions where a compound failure type occurs” is not a sufficient demand algorithm. A helper taking `error` can hold a compound by C1, and a helper taking only an extracted A may acknowledge A on behalf of its caller's compound. Its relevant summary may be needed even though its signature/body never spells `&`. Conversely, a function mentioning a compound only in dead type-only syntax need not trigger a flow analysis. Seed actual obligations and demand the needed summary dependencies through parameters, projections, containers and calls. Unknown callees may conservatively discharge nothing; describe returned provenance as unknown rather than as proof that there is none.

**Suggested fix and rule-4 gate:** define indexed origin/place/provenance tables, finite multiplicity states, sound joins and summary domains; state conservative rejection cases and actual worst-case bounds for that implementation. The spec partly meets rule 4 by naming bitsets, demand and a flagship gate, but does not yet meet its indexed-state/complexity requirements. Before landing, measure baseline versus implementation on the unchanged flagship panel and self-build, on one named host, using load-independent user instruction counts and the existing compile-speed gates. Include root/library/generic-instance work, instruction-derived all-processed-lines throughput, phase instructions per processed node, and peak analysis memory. Record demanded versus skipped functions, origins/places/associations, CFG worklist revisits and SCC iterations. Check a no-obligation workload for dormant overhead. Supplement with same-site dynamic arrays, copied containers, branch joins, recursion, opaque calls and 64-part fallback cases. A future gate promise is appropriate for a proposal; it is not an already passed gate or evidence of a measured regression.

### M5 — C1's `is?` guard does not prove that `as` is defined

**Contract and lines:** C1:195–208, 210–215.

**Scenario:** existential membership is deliberately weaker than unambiguous projection. A pair of FileError descendants passes `is? FileError`, but its `as FileError` is explicitly ambiguous because both facets provide `path`.

```dewy
FileError:type = type of error & [path:string]
ReadFailed:type = type of FileError
CloseFailed:type = type of FileError
inspect = (v:ReadFailed & CloseFailed):>string => {
    if v is? FileError return (v as FileError).path
    return "unreachable"
}
main = () => printl(inspect(ReadFailed["a"] and CloseFailed["b"]))
```

The guard is always true, yet cannot prove the conversion it guards. This contradicts the general remedy at line 215. A runtime test cannot repair a statically known ambiguous result. Likewise `as T?` needs a stated outcome for ambiguity, not merely for absence.

**Suggested fix:** keep existential selection for `is?`/arms, as D1 proposes. Prove `as` only when projection success and uniqueness follow for every remaining alternative. A matching guard narrows candidates but is insufficient when several matching facets remain. Give “name a leaf facet” as the ambiguity repair, and define whether optional conversion rejects ambiguity or returns a failure. Do not change `is?` into a uniqueness test, which would change D1's arm-selection semantics.

### M6 — C1 cannot promise order independence while retaining later-default-wins

**Contract and lines:** C1:173–178, 210–220; D4:98–102. Existing behavior: `docs/LANGUAGE.md:4226–4231`; `compiler/checker_fields.jo:62–69`.

**Scenario:** two plain records with different defaults have order-dependent construction:

```dewy
Left:type = [x:int64 = 1]
Right:type = [x:int64 = 2]
LR:type = Left & Right
RL:type = Right & Left
main = () => {
    printl(LR[].x)    # 2, under later-default-wins
    printl(RL[].x)    # 1, under later-default-wins
}
```

The accepted value sets can agree while the default constructors differ. Flattening to an unordered canonical set and claiming that order cannot matter loses the provenance needed to retain this behavior. It is not fixed by alias expansion. Associative ordered merging of defaults is possible; commutativity of those constructor defaults is not.

**Suggested fix:** distinguish canonical membership/field constraints from ordered declaration/construction metadata. State commutativity for the former only, preserving the established ordered default rule. Retain default provenance through aliases/grouping where constructors need it. If the intent is actually to remove order-dependent defaults, that is a changed language behavior requiring Part 1 approval; D4 currently promises the opposite.

### M7 — C5 still permits read-close suppression under an unsupported Linux-wide assertion

**Contract and lines:** C5:341–345, 359; D40's accepted cleanup-failure result rule in `docs/design/decisions.md:693–698`.

**Scenario:** a read-only handle's native close returns an actual error. C5 first promises `FileCloseFailed`, then permits success on Linux by treating descriptor release and lack of useful error information as a single documented fact. They are separate propositions. The [Linux close manual](https://man7.org/linux/man-pages/man2/close.2.html) documents descriptor release and an EIO outcome; it does not establish that every read-only file/device/filesystem's close error conveys nothing. Its release guarantee is not a read-only error-suppression theorem. Portable adapters also need their own interrupted-close release contract.

Returning success after a recognized close failure is a suppression policy, even when no descriptor leaks and no writes were made. That contradicts “no suppression,” the claim that nothing changes under strict mode, and D40 if the observed failure is meaningful. A platform capability proving that a particular admitted close cannot fail meaningfully is different from ignoring an error merely because the descriptor was released.

**Suggested fix:** remove the Linux parenthetical and return `FileCloseFailed` for actual completion errors. If a narrower adapter operation is genuinely infallible, name its admitted handle class and cite its precise target contract; test the adapter's mapping with fault injection. If discarding particular native errors is desired, disclose that policy in Part 1 and define strict behavior instead of calling it an implementation fact. This finding does not assert that every read-only close error implies lost file data.

### M8 — Part 2 includes observable API and operator policies absent from Part 1

**Contract and lines:** introduction:3–8; C2:243–245; C4:312–313, 324–334; C5:346–359. D5:104–124 approves vocabulary, not all these policies.

**Scenario:** `tx.commit() ?? void; tx.put(...)` changes from an available transaction after a failed commit to use of a consumed value under C5. That is a public ownership/operation contract. D40 explicitly permits consuming methods to finish cleanup early, so the policy can be coherent, but the decision to make failed commit consume and roll back immediately is not forced by block-end cleanup or by error combination.

Other observable items concealed by the “ours” label are:

- `FileWriteFailed[replaced=true]` at line 355: a new public member and post-rename outcome policy; D5 never asks about that field.
- Suppression of selected read-close failures, if retained (M7).
- A selector that consumes up to 16 facets but passes a 17-facet failure at line 244. That changes the value/result/control flow of `??`; it is not merely a slower implementation or diagnostic cap.
- `as T?` at line 215 needs an existing, compatible conversion contract, including ambiguity. It must not silently acquire a new spelling or outcome while being used to justify C1.
- The allocation-failure interaction in C4 needs disclosure if it changes existing function-level refusal into locally catchable operation results, or introduces new public result combinations beyond D40's normal cleanup extension.

Internal choices such as immutable chain layout, indexed bitsets and reserved storage do not themselves require new syntax approval. Their `allocates` effects and memory-cap costs still have to be accounted for by existing policies; a heap slot must not be hidden from `$no_hidden_costs` merely because it implements cleanup.

**Suggested fix:** move the public ownership, member, suppression and handler-limit choices into Part 1, with minimal examples and recommendations. Recommended answers: consuming commit on every outcome with rollback before return and no subsequent duplicate abandon; report actual read-close failures; expose a clearly defined replacement-state member if post-rename failure is supported; reject or conservatively diagnose unsupported selector analysis rather than silently changing the handler's result. These choices are reversible before release but source/behavior contracts afterward. Keep C6's final-result exit rule in Part 2 because D7 already presents that policy to David. Do not treat this audit as approval of new surface.

## Should-fix findings

### S1 — Specify disjoint facet identities and generic-family expansion

**Contract and lines:** C1:173–178, 188–208; C2:224–226.

**Scenario:** under the existential `is?` rule, `A & B` is an inhabitant selected by both A and B. Ordinary semantic nonoverlap of the *whole value sets* therefore cannot be the disjointness test for constructing `A and B`, or every useful pair is prohibited. The intended test is overlap between possible supplied facet identities, including subtype collisions. State that explicitly.

Generic identities must include canonical type arguments. Existing `Closed<int>` and `Closed<string>` are different types (`docs/LANGUAGE.md:3735–3741`), whereas `Closed<int>` and an alias of the same instance collide. A bare `Closed` in a selector covers all instances; it is not an annotation erasing their identities. `Closed<int>[] and Closed<string>[]` should remain two facets; two `Closed<int>[]` operands should be rejected. A fieldless `as Closed` must specify how it retains both instances without inventing a single parameterized instance. Generic families with fields need the same shared-field ambiguity rule as ordinary parents.

**Suggested fix:** key facet sets by canonical instantiated nominal identity, distinguish family selectors from concrete stored types, and check possible *facet* collisions after substitution/narrowing. Include these cases alongside parent/child and repeated leaf cases in the type-law gate. This is an implementation clarification compatible with David's duplicate rule, not a request for automatic generic stack lifting.

### S2 — Complete C5's operation state machines and separate text/bytes signatures

**Contract and lines:** C5:346–358.

**Scenario:** the joint `read_text`/`read_bytes` signature returns `string` and `InvalidUtf8` for both. Bytes should succeed with `array<uint8>` and do not decode. The new portable `FileError` parent also requires a consistent mapping for open/read/close failures and any explicit-allocation-failure extension.

For writes, “a failure before rename ... then closes and removes” includes the case in which close itself already failed. An explicit consuming close must not be retried by automatic cleanup. In particular, retrying a failed native Linux close can close a reused descriptor; the [Linux close manual](https://man7.org/linux/man-pages/man2/close.2.html) explicitly warns against retry. The contract needs state, not an unconditional second close.

Other missing states: temporary acquisition fails before a file exists; flush fails before close; close fails after flush; rename fails after the handle has already been consumed; directory sync/its handle cleanup fails after replacement; cancellation arrives after rename. The last case needs a declared policy for whether completion is shielded or the canceled outcome communicates that replacement happened. If two independently owned native handles can both report `FileCloseFailed`, use the ordinary repeated-type stack rule instead of constructing the prohibited duplicate intersection.

**Suggested fix:** provide a stage/result table, including owned/consumed duties and whether replacement has happened, with no double close/removal of nonexistent temporary. Split the two read signatures. Fault-inject each transition and verify that every observed failure appears exactly once and that all result alternatives/fields match the stage. No new combination operator is needed.

### S3 — Finish C4's storage lifetime and cost accounting

**Contract and lines:** C4:309–323, 330–334.

**Scenario:** “outlives the frame” is necessary but does not establish independence from a short-lived allocator/arena used for acquisition. A returned cleanup chain cannot refer into an arena that is then released. A failed resource acquisition after slot reservation must also reclaim that slot. A slot holding an arbitrary cleanup result must fit its actual union/payload/metadata, not just the file example. Inline pending failures need an established stable reference or an allocation-free by-value path before another slot can refer to them.

The approximately 32-byte estimate does not yet include an identified layout with all ownership/reference-count/length/head/tail fields and alignment. Keeping `.length`, `.first`, and `.last` at the head requires cached state or a different guarantee; segment indexing has worst-case O(number of segments), including deeply recursive chains, rather than “usually one or two.” Mutable-view detachment may need O(total elements) storage/work.

**Suggested fix:** specify the slot allocator/lifetime rule and its memory-cap/effect treatment, payload sizing, success/failure reclamation, and an actual file layout. Demonstrate recursion, arena escape rejection or safe ownership transfer, constant-time advertised head operations, linear worst-case indexing, and allocation refusal during COW detachment. Measure acquisition allocations and peak retained bytes as well as cleanup instructions. These are design/measurement gates, not reasons to reject immutable escaping segments.

### S4 — Clarify the inherited stack element rule under existential `is? error`

**Contract and lines:** C1:195–212; C4:330–332; inherited `round3.md:389–398`.

**Scenario:** round 3 excludes `Canceled & E` from `ErrorStack` because a combination is an `error` only if every part is an error. Round 4's generic minted test instead makes `(Canceled and E) is? error` true whenever E is an error. With C1's separate holding rule, a field/element typed `error` should still reject that whole value: `as error` drops `Canceled`. Thus the stack restriction can survive, but its inherited explanation cannot.

**Suggested fix:** state that generic element admissibility/holding is the all-parts storage condition, not existential selector membership. A runtime `if x is? error` does not prove x fits whole in an error-only collection. Include cancellation-bearing elements, generic aliases, nested stacks, and the wrapper in program 15 in the gate. Preserve ordinary cancellation selection; do not restore a cancellation-specific `is?` exception.

## Notes

### N1 — Several C1 laws have a coherent restricted reading

**Contract and lines:** C1:173–220.

For fully instantiated nominal facets, ancestor elimination makes `Child & Parent` agree with `Child`. It does not authorize combining independently supplied parent/child values: rejecting that construction is compatible with idempotence of *type requirements*. Likewise the ban on `a and a` does not require rejecting `A & A` as a type. Flattening distinct nominal sources and one merged structural source can satisfy grouping/alias invariance; selecting A & B from A & B & C can satisfy subset projection. These repairs from round 3 are useful. Complements must remain whole-value constraints for testing and must not be mistaken for positive coverage contributions (M1). No separate failure of projection idempotence is established here once projection is defined and unambiguous.

### N2 — C5 can coexist with block-end cleanup; its policies still need checking

**Contract and lines:** C5:346–358; D40 Q2/Q6 in `open_decisions.md:61–105`.

Closing a helper's handle before decoding is compatible with block-end cleanup when an explicit consuming close ends that duty first. On close failure the helper returns that failure without decoding; an unperformed decode has no `InvalidUtf8` failure to preserve. The hand-written helper in program 08 intentionally decodes before automatic close and can therefore return `InvalidUtf8 & FileCloseFailed`; that distinction is coherent.

Similarly an explicit `commit()` can consume early under D40; automatic abandon must then be disarmed on every outcome. If rollback fails, the driver must specify release/connection quarantine or how the failure owns remaining recovery state; “the variable is consumed” alone does not prove the external transaction/locks are gone. Dewy ownership and result checks can verify the local state machine, while native release guarantees remain audited adapter obligations. Cleanup errors from nested blocks must escape as the function's result as D40 requires, rather than be exposed as successful local data by a helper implementation.

### N3 — C6/C7 do not require resurrecting the rejected cancellation exit override

**Contract and lines:** C6:361–367; C7:369–374; Part 1 D7:143–155.

The highest-code rule follows the final value and is already exposed for decision in D7. Successful `main` stays successful after a handled cancellation; explicit `exit(n)` follows its documented immediate behavior. This repairs the prior sticky-status contradiction. C7's callback/format/effect demand closure remains a measurement and sound-flow gate; its prose is not evidence that the implementation has passed it. Neither point resolves the selector, obligation, allocation-refusal or API-policy issues above.
