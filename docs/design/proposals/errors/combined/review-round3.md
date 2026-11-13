# Independent review: combining failures, round 3

**Verdict: six must-fixes remain.** Keep the typed unordered combinations, whole-value arm bindings, uniform cancellation selection, explicit repeated-error stacks, and nonempty refinement. Do not mark the six round-2 contracts all resolved. Round 3 repairs real problems, but its new descriptions still fail several substitution, ownership and storage cases.

I recommend against **Q4's sticky exit-status override**, and against accepting **Q6's mixed-record restriction as written**. Neither follows from David's binding direction, and neither has been shown unavoidable. Q10's family-subset intent is useful; its general projection laws need finishing rather than rejection.

## The six round-2 must-fixes: resolved, yes or no

“Yes” here means the paper contract addresses the finding, not that implementation gates passed.

| Round-2 finding | Resolved? | Evidence in round3.md |
|---|---|---|
| M1: one meaning for intersections and aliases | **No, partially** | 231–249 removes the annotation-versus-alias distinction; 256–258 correctly restricts `$parts` to failures. But 234–247 leaves inherited nominal types and mixed intersections inconsistent under grouping, and the “mint one” repair at 243–244 does not implement its promise. See R1. |
| M2: obligations across temporaries, observers and ownership | **No, partially** | 265–305 covers the original temporary leak and exempts borrowed observers; 311–317 adds demand, indexed sets and a cap. The shared-copy rule at 279, per-holder checks at 292–294, and ownership-only summaries at 313–314 do not specify a coherent cross-copy/call/container discharge rule. See R3. |
| M3: no generic evasion of duplicate prohibition | **Yes** | 324–330 checks disjointness at instantiation, rejects overlapping families/unions, uses `is? exception`, and handles duplicate Canceled like any other duplicate. Program 13:26–27 explicitly rejects the former bad call; 14–20 explicitly constructs a stack for repeats. |
| M4: one-shot completion failures and failed commits | **No, partially** | 351–354 and program 14:12–16 add CommitFailed & RollbackFailed and describe active versus consumed transactions. Read helpers now rely on a new suppression assumption (340–345,357–359), while the new one-shot-write contract (346–349) still omits failures it says can occur. See R5. |
| M5: allocation-free lossless cleanup storage | **No** | 364 correctly retains the gate, and 366–381 gives a better segmented route. However, copying frame slots into a fixed-size result (372–373) does not handle recursive pending stacks, and “being returned” does not prove unique storage (374–376). See R4. |
| M6: lifetime nonemptiness and element restriction | **Yes** | 389–398 makes nonemptiness a storage refinement, restricts shrinking mutations and mutable views, and constrains E to error. This addresses the constructor-only invariant and excludes Canceled-containing elements through the type rule, rather than a cancellation exception. |

## Must-fixes

### R1 — Finish the intersection and subset-projection algebra; the mixed-case exception is not justified

**Locations:** round3:145–148,209–211,231–254; program 11:21–23; LANGUAGE:4209–4225.

Aliases now have the same meaning as their expanded expression, and both records in program 11 are minted. That fixes the old direct/aliased example. It does not establish one compositional meaning for all operands:

1. **Parent and child already share inhabitants.** LANGUAGE:4214–4216 explicitly says a minted child satisfies its parent and preserves identity. Thus round3:234–235's reason that minted types “can't share a value” is false for related operands. Specify ancestor normalization: a type requirement `Child & Parent` should not invent two facets. Keep this distinct from combining two independently supplied, overlapping failure operands, which the duplicate prohibition can reject.
2. **Grouping can choose which facet gets structural fields.** Let A and B be unrelated minted records and R a plain record. Under 245–247, `(A & R) & B` attaches R to A, `A & (R & B)` attaches R to B, and `(A & B) & R` is rejected. With a shared field whose constraint is compatible with only one nominal operand, grouping can even decide whether the expression is admitted. This is not the ordinary associative conjunction of requirements described at 231, nor a canonical unordered facet set. An alias must not merely conceal the grouping-dependent choice. “No use was found” at 247 is not a necessity argument for that exception.
3. **The proposed diagnostic is wrong under that same mixed rule.** At 243–244, and program 11:21–23, minting *one* of two overlapping plain records is advertised as keeping both field values. One nominal plus one plain operand instead augments one facet (245–246); there are not two independently projectable ids. Minting both records works in the actual program, but the stated repair does not.
4. **Q10 needs a true subset operation, not just a per-facet filter.** Its `as error` example is well specified: retain the ordinary-error facets and exclude Canceled. But “take the parts that are T” (209) alone fails for `v as (A & B)`: neither individual A nor individual B facet is an A & B, though their subset is. At minimum define `v:T => v as T` identity, selecting A & B from A & B & C, selecting all matching family descendants, and the ambiguity result when a requested family cannot store several descendants. Parent normalization and structural-field constraints must obey the same rules. Q10 should replace the earlier one-part wording, including implicit parameter projection, wherever the result differs.

**Required repair:** give a canonical operand-kind/normalization and projection contract, with parent/child, mixed operands, regrouping, alias expansion and subset-selection examples. If payload construction must be distinguished from combining already formed values/types, make that distinction explicit in the existing type model. Do not accept a new mixed-case ban merely because the paper programs avoid it. This retains David's facet direction and does not request a different operator.

### R2 — The all-parts rule must depend on the selector's meaning, not dead syntax in its expression

**Location:** round3:410–422, particularly 419–421.

The proposed rule uses `X is? S` plus coverage by *any atom occurring in S*. That is not invariant under elimination of an impossible selector branch. For distinct A and B:

```dewy
f = (x:A & B) => x ??<A> 0
h = (x:A & B) => x ??<A | (B & ~B)> 0  # second alternative cannot match anything
```

The two selectors have the same value-set meaning. `x is? (A | (B & ~B))` is true through A. Nevertheless the literal atom rule makes h consume the pair: its A and B parts both occur among the selector's atoms; f retains the pair. B has been smuggled into coverage through a branch that can never select it. This is exactly the sort of hidden special case a general type selector should avoid.

If the intended implementation first reduces `B & ~B` to the empty type and removes it, say so. The contract must explicitly state the canonical resolved selector on which coverage operates, including aliases, complements, intersections/unions and unreachable branches; it currently does not. A compiler that instead preserves a list of syntactically “named” types has invented a separate selector language whose equivalence rules differ from ordinary types. That would need an explicit design decision, not the statement that these are ordinary type expressions.

**Required repair:** define semantic coverage (or a bounded canonical selector representation with conservative rejection when necessary). Include the negative example above, equivalent factored selectors, and the existing positive `A | B`, `A & B`, and `~Canceled` examples. Preserve consume-all/forward-any and the binding ordinary-Canceled rule.

### R3 — Ownership summaries alone cannot implement the proposed shared obligation

**Locations:** round3:265–290,292–317; GOALS:11–17; ownership:51–59,106–125.

The replacement fixes the original naked `take_a(pair)` hole and gives `host_of` a legitimate borrowed case. Three unresolved cases remain:

**Copies versus holder end.** Copies of an immutable compound share one obligation (279), but the check fires whenever *a holder* ends while parts remain owed (292–294):

```dewy
check_copy = () => {
    let original = pair
    let later = original
    printl(original)                 # original's last use; observes only
    later ??<A | B> void             # explicit complete handling, still in this scope
}
```

On the stated shared-obligation interpretation this should be valid: the later copy still holds the obligation. The per-holder check instead rejects the earlier holder's last use. Specify discharge at the last live representative, plus what a forward/return does when some copies remain. A runtime alias between independent values is not an acceptable way to repair this compile-time question.

**Borrowed handlers versus observers.** These have the same borrowed ownership summary but different acknowledgment effects:

```dewy
handle = (v:A & B):>void => { v ??<A | B> void }
observe = (v:A & B):>void => { printl(v) }
check_call = () => {
    let v = pair
    handle(v)                       # cannot move v: it is used again below
    observe(v)
}
```

By-value argument/copy semantics must not change depending on whether an optimizer borrows or copies the readonly parameter. If handling a copy discharges the shared obligation, check_call should pass; replacing handle with observe must fail. A summary saying only “shared” or “consuming” (313–314) cannot tell those programs apart. Conversely, if shared handlers cannot discharge a caller's obligation, that limitation needs an explicit rule and a usable way to forward acknowledgment; claiming all copies share one discharge is then misleading. Returning a projected part, storing/capturing an argument, opaque function handles and recursive calls need conservative transfer summaries too.

**Containers and repeated occurrences.** Moving failures into an aggregate moves their obligations to it (274), while each compound value gets one bitset over *part types* (312). For `[pair pair]`, handling element 0 must not clear the identical-type obligations of element 1. State per-occurrence/place identity or an explicit conservative container rule; include unknown indexes, element overwrite/removal, mutation of a copied aggregate, and a loop handling every element. The 64-part-type cap bounds type-set width, not the number of obligation identities or alias/call-summary work.

**Required repair:** give checked acknowledgment/transfer summaries and a last-representative rule independent of Borrow/CopyInit/MoveInit optimization. State conservative handling of dynamic containers, loop joins and unknown calls; do not infer “handled” just because one same-typed element was handled. Keep the advertised gate and revise its complexity claim to cover these additional edges/states. This is a contract repair, not a demand to implement the analysis during a paper review.

### R4 — Returned stacks are neither necessarily unique nor bounded by this frame's named owners

**Location:** round3:366–385, especially 372–376.

Moving an owner array's backing allocation into a segmented stack is a useful answer for dynamic owner arrays. It does not answer dynamic numbers of **returning frames**:

```dewy
nested = (n:int<(>=? 0)>) => {
    let out = files.open(path_for(n) 'w') or_throw
    if n >? 0 nested(n - 1) or_throw
}   # close failures can accumulate across an arbitrary number of returning frames
```

Each frame has one named owner and one slot. Suppose the deepest close fails, then every enclosing close fails while forwarding that pending failure. The final stack must retain arbitrarily many FileCloseFailed values after all those frames have returned. Copying each frame's slot into a result whose layout has room for “its fixed number of named owners” (373) cannot create unbounded surviving inline capacity. A chain whose nodes still point into returned frames dangles. Reserving storage in an escaping region before acquisition, retaining owned frame storage, or another lifetime-safe representation might solve this, but none is the currently stated copy-into-fixed-result recipe. Reserving only array storage does not cover recursion.

Also, returning a value does **not** establish unique backing storage (376). Dewy retains ordinary copyable/COW arrays. A body stack may have a snapshot still retained elsewhere. Linking the tail in place (374–375) can mutate that snapshot; detaching the shared chain may allocate. “The handle is being moved” and “all its segments are uniquely owned” are different facts.

**Required repair:** specify a lifetime-safe reservation strategy for recursive/dynamic returned chains, and either prove segment uniqueness or concatenate without mutating shared segments. Preserve ErrorStack's array value/mutation behavior and account for the costs of segmented indexing and mutable/raw views. Keep the allocation-refusal gate open; add these cases to it along with full body stack plus array cleanup and refused growth. The fixed two-owner example remains plausible and is not itself disproved by this counterexample.

### R5 — The one-shot library contract still loses declared completion failures, and silently adds a new assumption

**Locations:** round3:179–182,340–359; assumptions:19,26–33; programs 04:5–8,08:7–9,09:8.

The failed-commit-plus-failed-rollback path is now represented. The file half remains incomplete:

- At 346–349, one-shot writes now use a temporary and rename, and the text explicitly admits a failed temporary **removal**. Its claimed exact result lists FileWriteFailed & FileCloseFailed and Canceled & FileCloseFailed, but no independently represented removal failure. A write, close and attempted removal can all fail. If deletion is classified under FileWriteFailed by the current per-operation vocabulary, that repeats the body type and requires an explicit stack; if it has another type, that type and its combinations are missing. Give the actual states/values, not merely the two-error pair. Likewise say whether a post-rename failure can leave a changed target: “a failure leaves the target unchanged” is a stronger atomic-write API promise than failure combination needs.
- Suppressing a read-only close error is a possible **library policy**, not a consequence of owning no handle after return, nor a proof that close cannot fail. The old assumptions row concerns trusted infallible library hooks, exemplified by releasing a lock word. It does not itself authorize discarding a real OS completion failure or establish release on every target. The file says both “failure isn't reported” (181–182) and “can't fail observably” (341); the program comments say “can't fail.” These must not be conflated.
- The proposed strict opt-out is not an existing usable tag: assumptions:19 marks it pending, and :31–33 says those rows are not yet enforceable. Round3:357–359 should specify the strict result vocabulary/combination contract and diagnose an unavailable policy, rather than imply a currently established bulletproof route.

Primary-source cross-check: the [Linux close manual](https://man7.org/linux/man-pages/man2/close.2.html) documents errors and Linux's release behavior, but also explains that interrupted-close semantics differ across platforms/standards. [Apple's archived close manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/close.2.html) lists EINTR without a read-only exemption; it does not supply the unconditional-release proof asserted here. This does not prove a particular Darwin adapter leaks; it means the universal guarantee needs an audited adapter contract. Releasing a descriptor and choosing not to report its error are separate claims.

**Required repair:** either retain explicit completion failures/wrap them, or state the narrowed read-close suppression as a deliberate new convenience assumption with its scope, target obligations and strict-mode contract. Finish the write/removal result before calling it exact. Do not silently broaden the old lock-hook trust row. Atomic replacement is a separate API choice and may simply be left out of this errors round.

### R6 — There is no single exit-status rule in the round, and the new override is an avoidable cancellation exception

**Locations:** round3:101–115,423–424,500–501; summary-round3:6; inherited round1:444–447.

The heading promises 130 “whatever main returns.” Lines 113–115 instead use a failure's own code. The summary says “a canceled run exits 130,” while inherited round1:447 separately gives a Canceled-containing combination cancellation priority. For Ctrl-C plus FileCloseFailed, is the result 130, the close error's code, or the lowest ordinary code? The answer cannot depend on which paragraph is read. An explicit `exit(0)` is another unaddressed termination path.

More fundamentally, a sticky external cancellation flag that turns a successful `main` into exit 130 is an extra entrypoint rule. It resurrects a consumed Canceled value outside the ordinary result/handler model. It need not change `??` selection to be a real exception. The claim that “a program takes Ctrl-C itself” must also specify scope and timing: consuming a Canceled value is not necessarily a signal listener; an observing listener does not take over; a listener might have ended before a later signal. Programmatic child cancellation must not silently taint the process's final exit.

**Required repair:** withdraw this override from the combining-failures recommendation, or present one separately decidable entrypoint policy covering successful main, ordinary failure, Canceled plus cleanup failure, explicit exit, root versus child cancellation, and listener lifetime. My recommendation is **against Q4 as written**. Keep Canceled ordinary and derive automatic reporting from the final result; a signal-owning entrypoint can deliberately return Canceled or choose exit 130. A new process-status latch is not needed to make the type rules sound, does not repair a retry spin before main returns, and has not earned its exception under David's criterion. This recommendation does not reverse his decision to default Canceled normally.

## The eleven decisions, checked individually

| Decision | Recommendation and hidden cases |
|---|---|
| Q1: select any, consume all; whole arm binder | **Keep, conditional on R2/R3.** Source-ordered match and is? are aligned (38–64,428–435). A handler acknowledging a part is not proof of recovery; 308–309 now states that limit honestly. Distinguish borrowed observation from acknowledgment, including observer helpers. |
| Q2: complement selector | **Keep the intent; binding for cancellation.** No cancellation dominance remains (403–418). `is? ~E` and `isnt? E` must agree, including intersections, families and aliases. R2 must make coverage equally semantic. |
| Q3: spin warning | **Keep as a diagnostic, not a safety theorem.** It changes no runtime operator rule. 96–99's condition also catches finite loops/deadline checks, so the message should say “may retry immediately after cancellation,” not assert every such loop spins forever. A wait hidden in a helper and a continue hidden in a callback need stated diagnostic coverage; absence of a warning is not a proof. The sample fix needs the complete `??<~Canceled> continue or_throw` shown at 75, or an explicit prior cancellation forward: complement alone leaves Canceled in the value. |
| Q4: canceled-run exit 130 | **Recommend against as written; R6.** Neither the priority nor the definition of a canceled run is stable, and the sticky override is additional semantics rather than a consequence of ordinary failures. |
| Q5: explicit-cancellation check | **Reasonable strictness policy, needs precise acknowledgment scope.** 127–130 now checks handlers without runtime exceptions. Define alias expansion and how a collector element can positively name/exclude cancellation when it has no written selector. Distinguish moving cancellation into a collection from handling it; show a compilable strict-mode collection example. Broad selectors should not accidentally bypass the opt-in check through an alias. |
| Q6: nominal facets, structural merge | **Do not accept as written; R1.** The alias repair is good, but “beside two minted types is an error” is a new general-rule exception justified only by absence of a paper example. Parent/child identity and the mint-one diagnostic also need correction. |
| Q7: generic duplicate error | **Keep; resolved M3.** Overlap rejection is conservative and may require narrowing or a stack, but it obeys the binding duplicate rule. Type expressions and combining two supplied failure values must still distinguish parent normalization from duplicate construction (R1). |
| Q8: per-operation library errors | **Keep the vocabulary direction, not the unsupported completion promises; R5.** FileError becoming a parent is a visible library change, correctly disclosed at 179–180. Transaction failure/consumption can depend on runtime outcome; document how the owner-state checker follows it instead of pretending a driver's documented state is always a compile-time type. |
| Q9: ErrorStack name and nonempty invariant | **Keep the provisional name and the repaired invariant.** 197–199 honestly reports cold-reader uncertainty. 389–399 uses the existing refinement rule with no new cancellation carve-out. The segmented representation must satisfy the same array surface (R4); the name itself does not settle storage. |
| Q10: take all matching facets | **Keep the `as error` family-subset intent, conditional on R1.** The displayed wrapper preserves Canceled separately and keeps all ordinary error facets in cause. Define identity/composite requests, ambiguity, parent relationships and implicit argument projection. Do not use “one part” and “all parts” as competing definitions. |
| Q11: metadata names and demand | **Accept provisionally within the stated whole-source model.** 450–467 supplies the main closure edges, ABI boundary, alignment cost and trace-capture limitation missing earlier. `$parts` now has a sound failure-only domain (256–258). Demand still needs checked callback/formatting/effect edges and its measurement gates; that is implementation work, not a reason to reject these names. |

There are ten bullets under “What changed” (13–32); the eleven decisions assessed here are Q1–Q11, which appears to be the brief's intended referent. If a new fact makes an ordinary failure noncopyable, unreportable or unable to participate in a generic operation, the type/ownership rule should explain it; cancellation-specific precedence or unstated selector syntax should not.

## Comparison with the author's fixed grades

I opened `dogfood-round3.md` only after writing the independent grade table and its per-program explanations below. There is **one difference of at least two points**: **program 11 completeness, my 3 versus author's 5** (author:25,132–140). The two-minted example repairs the original direct/alias contradiction, but the mixed/parent/grouping laws and the advertised mint-one fix still disagree (R1). That is an unfinished capability contract, not just unfamiliar vocabulary.

All other component differences are zero or one. In particular, my S/K deductions for 04,08,09 concern the unestablished read-close/strict-mode contract (R5), rather than absence of compiler measurements. I agree that 03 and 10's nonempty stack interface is now complete at the paper level; I also agree that 13 no longer deserves the round-2 floor of 2. The author calls program 15 a four-resource exercise (author:183–184), but its source owns three resources; its general boundary policy is useful without claiming the omitted process-cleanup case has been exercised.

## Independent grades (fixed before reading dogfood-round3.md)

Scope: the brief, rounds 1–3, round-3 summary, all fifteen `programs-r3/` files, the six round-2 must-fixes, binding decisions batches 9–10, and the relevant language, ownership, refinement and assumptions contracts. The checkout is read-only. This is a paper-design review, not compiler validation. Only this report is written; no commits, test runs, or delegates.

Scores assess the proposed programs against idiomatic Python, Go, Rust, TypeScript and Swift, not against today's unimplemented frontend. O = obvious, D = discoverable, C = concise, S = safe by default, K = complete; 5 is strongest. Missing representation or analysis measurements remain implementation gates, not automatic grade deductions. A deduction below identifies a source-level burden, inconsistent contract or missing behavior instead.

| Program | O | D | C | S | K |
|---|---:|---:|---:|---:|---:|
| 01 combine and match | 5 | 4 | 5 | 5 | 5 |
| 02 handler does not swallow | 5 | 4 | 5 | 5 | 5 |
| 03 form validation | 5 | 4 | 5 | 5 | 5 |
| 04 batch files | 4 | 4 | 5 | 4 | 4 |
| 05 cleanup written file | 4 | 4 | 5 | 5 | 5 |
| 06 two files fail to close | 4 | 3 | 5 | 5 | 5 |
| 07 parallel failures | 4 | 4 | 5 | 4 | 4 |
| 08 library context | 5 | 4 | 5 | 4 | 4 |
| 09 CLI locations | 4 | 4 | 5 | 4 | 4 |
| 10 retry | 5 | 4 | 5 | 5 | 5 |
| 11 combined records | 4 | 3 | 5 | 5 | 3 |
| 12 cancellation during cleanup | 4 | 4 | 5 | 5 | 5 |
| 13 generic pair | 4 | 4 | 4 | 5 | 5 |
| 14 transaction rollback | 4 | 4 | 5 | 5 | 4 |
| 15 upload boundary | 4 | 3 | 4 | 5 | 4 |

The floor is **3**, in **06 (D), 11 (D/K), and 15 (D)**. The round-2 floor of 2 is not carried over automatically: the direct alias/annotation contradiction and generic stack lifting really have been changed.

Every citation below is to the named file under `programs-r3/`; `r3` means `round3.md`.

- **01:** D4 at 18–26: the reader must learn whole-value arm binding, source-order selection and implicit versus explicit projection. All four outcomes are shown. Against Python/TypeScript an explicit pair/list needs more plumbing; Go/Rust/Swift likewise need an aggregate result representation to preserve both failures. Dewy's example is compact and its particular selectors are unambiguous.
- **02:** D4 at 14–15: a selector spelled with a union also covers an intersection only when every part is covered. That is useful, but needs teaching. Python/TypeScript catch clauses and Go/Rust/Swift result/error cases do not by themselves express this particular all-parts operation; their explicit aggregate handling makes the policy longer but visible. The simple selector used here preserves the close failure.
- **03:** D4 at 12 and 18: the user must discover the nonempty ErrorStack constructor and its outer-stack selector. An ordinary list is familiar in all five peers; Python/TypeScript need a convention to distinguish an error collection from success, and Go/Rust/Swift need an explicit result/wrapper shape. No empty-stack magic remains, and the shown guarded code is clear.
- **04:** O4/D4/S4/K4 at 3–8 and 19: the small collection type depends on a new read-close suppression policy and changes under its still-pending opt-out (r3:340–359); the source comment overstates this as close being unable to fail. Python/TypeScript and Go/Rust/Swift can all accumulate an ordinary list explicitly; Dewy is concise, but has not yet established the platform adapter/strict-mode contract on which this list's completeness depends. The line-counting toy algorithm itself is outside this errors review.
- **05:** O4/D4 at 5–8: the final close and extra result alternatives are implicit in the owner binding. Python/TypeScript scopes and Go/Rust/Swift resource patterns also need a deliberate policy for two failures; Dewy's resulting pair and the explicit diagnostic arm are an improvement in this example. The success message at 13 is now correctly after completion.
- **06:** O4 at 5–16 and D3 at 11–16: whether a close failure is bare or a stack depends on which owners are statically live, including the failed-second-open path. This remains harder to discover than an explicit list in Python/TypeScript or an explicit aggregate in Go/Rust/Swift. Fixed two-owner storage is plausible, and the example forwards the whole result at 24; I do not deduct safety merely because the general construction gate remains open.
- **07:** O4/D4 at 10–13 and S4/K4 at 16–24: filtering cancellation before building the stack is teachable, but the same file executes a parallel-block multi-failure extension that is explicitly not decided. Its independent-failure/sibling-cancellation boundary is not supplied by the errors rules. Python/TypeScript have explicit aggregate/task-result choices, while Go/Rust/Swift need a collection/task policy too; none of those comparisons validates this missing concurrency contract. The ordinary read helper also inherits 04's policy limitation.
- **08:** D4 at 2,4,19–21 and S4/K4 at 7–9: cause versus peer combination must be taught, and the read-only close policy remains unsupported as a general guarantee. Python/TypeScript contextual wrapping and Go/Rust/Swift wrapper errors all offer a comparable abstraction choice. Dewy's own cause field is concise and the cancellation forwarding at 18 is explicit. The inferred signature comment should also account for text-decoding failures admitted by the eventual handle API; closing before decoding removes close combinations, not decoding failures themselves.
- **09:** O4/D4 at 5–9,14 and S4/K4 at 8: the origin/demand/cleanup rules are not apparent from the calls, and the read-close claim inherits 04's limitation. Python/TypeScript tracing and Go/Rust/Swift explicit error-location wrappers offer alternatives with different capture costs; the demand-driven view is promising, but only within the stated closed-source build. This grade does not demand a trace capture implementation now.
- **10:** D4 at 9,15–16: ErrorStack's refined nonemptiness and outer-type test must be discovered; `.last` itself is now justified. A list of failed attempts is straightforward in Python, Go, Rust, TypeScript and Swift; Dewy's code is similarly short and explicitly forwards cancellation at 6 and 10. Discarding failed attempts after a successful retry is the intended policy here.
- **11:** O4/D3 at 2–5,9–11,14–19 and K3 at 21–23: structural merge and nominal facets have different behaviors, and the advertised repair “mint one” contradicts the mixed-record rule (r3:245–247), which adds the plain fields to the one nominal facet. More generally, the mixed/parent/grouping laws remain incomplete. Python/TypeScript would normally use explicit composition/keys for two ids; Go/Rust/Swift also make the two member paths explicit. Dewy's projections are concise, but its broader algebra and this diagnostic must agree before this is complete. The two-minted-value example itself no longer has round 2's alias-context bug.
- **12:** O4/D4 at 5–11 and 16–18: cleanup is implicit, and a Canceled arm binds the whole cancellation-plus-close result. Python/TypeScript and Go/Rust/Swift also require an explicit cleanup/cancellation policy; this example now keeps that policy without suppressing the close-warning test. Whole-value forwarding at 18 is correct under the proposed rules.
- **13:** O4/D4/C4 at 2–8,14–20,23–28: the convenient pair helper cannot serve the repeated-type case; that needs a separate collection helper and an instantiation-time disjointness diagnosis. Python/TypeScript collections and Go/Rust/Swift explicit aggregate errors can use one collection shape, at the cost of exact pair typing. The extra helper is a real ergonomic trade-off, but the binding duplicate rule is now respected.
- **14:** O4/D4 at 6–16 and K4 at 12: commit failure versus success changes whether the transaction remains owned; r3:351–354 explicitly allows driver-dependent consumption but does not say how the documented state distinction is represented and checked when one operation has both outcomes. Python/TypeScript transaction contexts and Go/Rust/Swift transaction wrappers need a driver policy too. The error-pair example includes the previously missing CommitFailed & RollbackFailed, and ordinary whole-result forwarding is clear. A live-state bit or a conservative idempotent rollback contract can finish this without new syntax.
- **15:** O4/D3/C4 at 19–25 and K4 at 1,8–18: the boundary wrapper needs several lines of cancellation/family-projection policy. This is manageable but far less discoverable than the “one ConfigError” case. Python/TypeScript wrapping and Go/Rust/Swift domain-error wrappers require a policy too; the typed cancellation peer is Dewy's useful extra information. However, the advertised four-resource case actually opens three resources and never starts a helper process, so it does not dogfood the four-cleanup/112-alternative boundary claimed at r3:471–491. Its `as error` example is specified, but the general subset projection laws still need the fixes below.


## Final handoff

**Six must-fixes:** R1 canonical intersections/projections; R2 semantic selector coverage; R3 shared-obligation transfer and occurrence tracking; R4 surviving/uniquely mutable cleanup storage; R5 complete one-shot completion and assumption contracts; R6 one separately justified exit-status policy.

**Floor: 3**, in **06 (discoverable), 11 (discoverable/complete), and 15 (discoverable)**. Recommend against **Q4 as written** and **Q6's mixed-record restriction as written**. Keep David's ordinary Canceled, typed unordered combinations, explicit stack for repeats and all-parts fallback direction.
