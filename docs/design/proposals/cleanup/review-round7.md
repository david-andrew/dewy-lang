# Independent review: cleanup round 7

**Must-fix count: 0 for the bounded paper specification.** Round 6's M1 and M2 are resolved. The grouped body form is coherent but unlikely to be written correctly unaided. Prefer ordinary loop syntax with a checked consuming `out.close() or_throw` before locally continuing exits when that operation fits. Retain narrow `defer` provisionally: program 27 is a clear convenience win for it, despite the owner's equivalent supported unwind action.

Scope: round7.md, summary.md, review-round6.md, all 27 programs and their README; binding decisions batch 9 and D40; relevant LANGUAGE.md/ownership rules and supplied errors round2.md as amended by round3.md. This is a paper review, not execution or compiler validation. Only this output file is written; no checkout changes, builds, commits or delegates.

## Independent grades, fixed before reading the author's grades

The following grades and deductions were recorded before opening dogfood-round7.md. Scores describe the final recommended/accepted form in each file, with intentional negative and before examples used to test diagnostics. They do not punish an expected rejection as a broken positive program. O = obvious; D = discoverable; C = concise; S = safe by default; K = complete. A 5 means no material disadvantage for the stated scenario against idiomatic Python, Go, Rust, TypeScript and Swift; 4 means a manageable tradeoff; 3 means a substantial teaching, ceremony or remaining contract burden. K is completeness under the stated contract, with explicitly unresolved integration gates deducted where relevant. None of these scores establishes implementation readiness or empirical reader performance.

All program citations below refer to `programs-r7/NN_*.dewy`. Each sub-5 dimension has its reason and source lines in its row. Line ranges are inclusive.

| Program | O | D | C | S | K | Evidence for every deduction |
|---|---:|---:|---:|---:|---:|---|
| 01 Lock region | 5 | 4 | 5 | 4 | 5 | D4: named-place versus inline guard lifetime must be learned (4, 11, 18–22). S4: holding the lock across sleep is accepted; shortening the region is manual (11–15, 17–23). Exact int fixes the prior arithmetic defect (2–6). |
| 02 Socket protocol | 4 | 4 | 5 | 4 | 5 | O4/D4: EOF-before-status and alive-through-side-channel require protocol knowledge (4–7 versus 18–22). S4: automatic release still permits the before-version's hang; scope repair is manual (3–14). |
| 03 Buffered file | 4 | 4 | 5 | 4 | 5 | O4/D4: acquisition/write propagation does not mean close/flush succeeded; a marked short scope is required before read-back (3–6, 9–13). S4: stale read and premature audit remain expressible (5–6, 19–22). |
| 04 Ticker and unused guard | 4 | 3 | 5 | 4 | 5 | O4: long computation retains a ticker unrelated to it (4–8). D3: discarded ordinary owners are scope-held, while inline lending has statement lifetime; retention is not visible at line 18 (10–21, README:30,37). S4: timer retention and discarded guard selection rely on a warning/short-scope repair (7, 18–21). |
| 05 Generic and aggregate | 4 | 4 | 5 | 5 | 4 | O4/D4: the function/callable/aggregate has an instance-specific cleanup result not spelled at its declaration or call (3–16, 18–25). K4: correctness depends on generic/callable and aggregate lifecycle summaries surviving conversion (10–11, 22–25; round7:350). Uniform timing does remove the mixed rule's category surprise. |
| 06 Closure capture | 4 | 3 | 4 | 4 | 5 | O4/D3: last call does not release the closure's socket; EOF waits hang unless the closure's owning scope ends (4–13). C4: the repair introduces a helper/call boundary (15–23). S4: the original blocking pattern remains possible (8–12). |
| 07 Branch-sensitive use | 5 | 4 | 5 | 5 | 5 | D4: ownership must be understood to know the otherwise unread stream remains active through line 8 (3–9). Block-end then gives a consistent answer on both branches (10–16). |
| 08 Loop exits | 3 | 3 | 4 | 5 | 4 | O3/D3: a suffix after the whole loop is the natural first attempt, but the body needs grouping; continue/break still bypass ordinary evaluation of the suffix (11, 14–26). C4: grouping and per-body suffix add ceremony (14–19). K4: all-exit CFG lowering is specified, not demonstrated (17–24; round7:362–364). |
| 09 Unscoped parallel | 3 | 3 | 4 | 5 | 4 | O3/D3: parentheses lift bindings and cleanup out of parallel, whereas the nested brace owns out; a helper owns input separately (2–6, 9–23). C4: an extra scope/marker is needed to announce completion before printing (9–16). K4: initialization-aware join/cleanup dependency integration is still a gate (18–23). |
| 10 Spsc join | 4 | 4 | 4 | 4 | 5 | O4/D4: sender retention prevents receiver completion; moving through a producer boundary repairs it (9–23). C4: extra helper and owning transfer (16–23). S4: dynamic identity graphs can evade deadlock diagnosis (28–29). |
| 11 Inner scope and jumps | 3 | 3 | 4 | 5 | 4 | O3/D3: a distant suffix governs a labeled jump; multiple crossed scopes need separate policies, but return-only scopes do not (17–37, 41–51). C4: nested scopes/markers accumulate (41–47). K4: multi-scope jump suppression and once-only failure folding require integration (49–51). |
| 12 Local recovery | 3 | 3 | 4 | 4 | 4 | O3/D3: outer type testing does not recover leaves; split plus remainder forwarding is required (11–22). C4: partition/report/rejoin is substantial for accepting failed files (11–15, 30–34). S4: the programmer must retain/forward rest; losing line 14 or 33 loses nonmatching failures (7, 14, 20–23). K4: owning partition and inherited-context preservation remain errors-design integration contracts (18,22; errors/round3 section 2). |
| 13 Recursive render | 5 | 5 | 5 | 5 | 5 | No deduction under the explicit finite-depth/tree contract (10–17). The parameter removes the mutable restoration obligation. |
| 14 Request timing | 5 | 5 | 5 | 5 | 5 | No deduction for ordinary results and this no-local-cleanup handler (1–2, 12–21). This grade does not claim panic-unwind coverage: lines 22–25 explicitly exclude it from the rewrite's guarantee. |
| 15 External state/many exits | 4 | 3 | 3 | 4 | 4 | O4/D3: callback snapshot/share semantics and delayed mutation through a local aggregate must be understood (3–10, 20–22). C3: type plus restore callback plus registration for a one-off flag (3–10). S4: registration and restoration/reentry policy remain manual (11–18, 40–43). K4: provenance, effects and conflicting-loan checks through the owner are unproved (20–22). |
| 16 Foreign global toggle | 4 | 4 | 4 | 3 | 3 | O4/D4: restoration is hidden in an internal type and depends on reverse cleanup relative to held (5–15). C4: one-off use needs a nominal type, despite the shorter call site (24–26). S3/K3: process-wide gate discipline and trusted ABI/unwind contracts remain external and unverified (1–3, 27–28). |
| 17 Shared channel | 4 | 3 | 4 | 3 | 4 | O4/D3: storage lifecycle does not determine end-of-sending; an ad hoc coordinator owner must close after producers join (1–14, 36–39). C4: custom helper type/registration (2–9). S3: removing the registration can hang; ownership does not infer the protocol (38–39). K4: close policy, cancellation and join ordering need the stated channel/runtime contract (36–38; README:44). |
| 18 Hooks/transaction | 5 | 4 | 5 | 5 | 4 | D4: assigned hook/drop versus abandon/commit behavior must be learned (3–8, 15–23). K4: combined debit/rollback failures require the proposed grouping integration (23). Ordinary abandonment never publishes (17,19,21–24). |
| 19 Collector values | 3 | 3 | 4 | 5 | 3 | O3/D3: grouped body versus outer suffix, error record versus bare error, and streamed output versus pending scalar result differ (8–26, 28–35). C4: grouping and optional wrapper add ceremony (11–14, 28–30). K3: lossless cleanup grouping under explicit allocation exhaustion is unresolved (18–19; round7:97,364). |
| 20 Selective propagation/order | 3 | 3 | 3 | 5 | 3 | O3/D3: selection before cleanup, no group re-test, and unselected ParseError as data require several linked rules (12–25). C3: full selective type lists/grouped bodies are verbose relative to bare propagation (9–12, 18–21). K3: synthesized groups still inherit the finite-memory gate (14–15, 44; round7:364). Incomplete cleanup coverage is correctly rejected (27–34). |
| 21 Conditional/fallback | 3 | 3 | 3 | 5 | 4 | O3/D3: an outer if/loop suffix covers neither body's owner; loop else means no entered iteration, not no break (3–25, 28–40). C3: both arms repeat grouping and suffixes (3–11, 28–35). K4: chain parsing and per-arm cleanup need implementation verification (15,24–25,37–40). |
| 22 Match arms | 3 | 3 | 4 | 5 | 4 | O3/D3: arm-list braces are structural; each owning arm requires a different, grouped brace operand (3–12 versus 19–30). C4: repeated per-arm grouping/markers (4–11). K4: arm-binding and cleanup/result handoff integration remains unproved (16–17,29–30; round7:131,364). |
| 23 Parallel attachment | 3 | 3 | 4 | 5 | 3 | O3/D3: identically placed suffix has different completion coverage for braces/parentheses; let-bound values do not contribute (8–21 versus 24–36). C4: lifetime control requires choosing/scaffolding the right enclosing scope (24–35). K3: scheduler ordering, partial initialization, join-before-cleanup and finite-memory grouping remain contracts (17–21; round7:268,364). |
| 24 Inline lending | 4 | 3 | 4 | 5 | 4 | O4/D3: caller sees a borrowed field, but the kept hidden guard dictates inline rejection and a named marked block (5–18, 20–29). C4: repair adds a binding and scope (21–24). K4: transfer/provenance and unknown-summary rejection need compiler proof (27–36). Infallible inline guards still have a different short lifetime (31–35). |
| 25 Owned-buffer retention | 5 | 4 | 5 | 4 | 5 | D4: an observable hook changes retention compared with a hook-free byte array; early free is permission, not a guarantee (4–5, 13–15, 28–37). S4: retained buffers can exhaust a cap until an author shortens the scope (13–25). The short-scope repair is otherwise direct. |
| 26 Conservative markers | 4 | 3 | 4 | 5 | 4 | O4/D3: acceptance depends on consume/move summaries and instantiation, not just the presence of a local binding (5–12, 16–24, 35–38). C4: maybe-live paths need an extra scope/marker or helper/signature (26–37). K4: bounded fixed-point and erasure preservation are specified but untested (35–38). |
| 27 Borrowed-place restoration | 4 | 3 | 3 | 4 | 4 | O4/D3: explicit shared capture, snapshot prior, type conversion, local aggregate and rejected escape must all agree (4–17, 28–37). C3: three-line type plus five statements versus four for defer (4–12, 19–26). S4: registration remains manual; copied bool replacement silently restores the wrong value (39–47). K4: nonescaping record/callable provenance and effects need a compiler demonstration (33–37,48–49). |

Independent floor: **3**, at **04, 06, 08, 09, 11, 12, 15, 16, 17, 19, 20, 21, 22, 23, 24, 26, 27**. These are individual dimension floors, not averages.

### Five-language comparison underlying those grades

These are comparisons of the stated tasks and resource policies, not new claims about library availability or measured usability. Py = Python; Go = Go; R = Rust; TS = TypeScript; Sw = Swift. Mentioning a familiar pattern does not claim every built-in API has the example's fallible completion semantics.

| Programs | Py | Go | R | TS | Sw |
|---|---|---|---|---|---|
| 01, 04, 07, 25 | with/try-finally makes the protected region visible | lock/restore plus deferred action makes registration local, but long function scopes still retain | lexical guards make retention familiar | try/finally makes ambient restoration explicit | scoped work and defer keep region actions local |
| 02, 03 | nested resource scope/explicit close before dependent work is familiar | explicit close before EOF/status or reread still matters | explicit drop/finish or shorter scope is needed for protocol order | explicit completion before dependent work is familiar | explicit completion/scoped helper is still needed |
| 05, 06 | closure-held resource lifetime is indirect; explicit protocol completion helps | closure captures can likewise obscure release; explicit cleanup is common | captured ownership and lexical drop make the model familiar; finish may be explicit | closure lifetime does not establish EOF; completion is explicit | captured owner/closure lifetime also needs a scope or explicit finish |
| 08, 11, 21, 22 | ordinary loop/branch braces are absent; cleanup is expressed with a nested context/finally | function-scoped defer cannot simply stand in for per-iteration close; helper/close needed | ordinary lexical iteration/arm cleanup needs less marker syntax, though fallible finish is explicit | ordinary loop/branch plus try/finally keeps cleanup visibly local | lexical block/defer needs no expression-grouping distinction |
| 09, 23 | task coordination plus async resource scopes has explicit join boundaries | join coordination and close policy must be written | scoped tasks/owners offer a familiar join-before-drop model | explicit task join/finally makes the lifetime policy visible | structured tasks plus scoped cleanup make join-before-release familiar |
| 10, 17 | explicit producer completion remains a protocol duty | explicit channel completion remains a coordinator duty | separate sending ownership can encode some completion duties; shared coordination still needs policy | producer completion is explicit application work | structured task join does not by itself infer shared-stream completion |
| 12, 19, 20 | selective grouped recovery needs a separate leaf policy; explicit resource scopes are more familiar than grouped-body suffixes | explicit returned errors need manual multiple-cause/remainder policy | explicit returned errors need manual aggregate recovery; finish results are visible | catch/result and aggregate recovery need explicit policies | typed/result recovery and cleanup error policy remain explicit work |
| 13 | depth argument is direct | depth argument is direct | depth argument is direct | depth argument is direct | depth argument is direct |
| 14 | capture/record/return or try/finally for unwind requirements | capture/record/return or defer | capture/record/return or timing guard | capture/record/return or finally | capture/record/return or defer |
| 15, 16, 27 | one-off try/finally keeps mutation/restoration together | one-off defer is shorter than a callback owner | a custom guard/closure guard resembles the owner; borrowing and unwind support still need care | one-off try/finally keeps restoration local | one-off defer is shorter and avoids the nominal callback carrier |
| 18 | explicit transaction commit with rollback scope is familiar | rollback defer/transaction owner is explicit | transaction owner and explicit commit are familiar | transaction helper/finally is explicit | explicit commit and scoped cleanup are familiar |
| 24, 26 | no equivalent static lending/instantiation rejection; dynamic scope protocols are simpler but offer less checking | explicit acquisition/finish lacks the same static duty proof | lifetime/effect-driven restrictions are familiar, but exact fallible-guard policy differs | runtime scopes are simpler but lack the static duty proof | scoped borrowing/cleanup is familiar; conservative effect proofs add teaching burden |

The grouping problem is a real readability disadvantage against all five: familiarity with resource scopes does not teach why `loop … { … } or_throw` is rejected but `parallel { … } or_throw` is accepted. Rust's and Swift's lexical cleanup familiarity makes timing easier to explain, not this postfix AST distinction. Dewy's automatic preservation of fallible cleanup failures and rejection of uncovered local exits earns safety credit; none of the comparisons silently grants every peer that same guarantee.


## Round-6 findings: resolved or not

**M1: YES, resolved as a bounded specification.** The decisive parse sentence is round7.md:105: “a suffix after the completed construct applies to the whole construct, including any attached `else` chain.” Lines 109–125 then identify the acknowledged scope without consulting types: the outer loop has none of its body's cleanup scope; its grouped body does; scoped parallel has its own. Lines 139–144 explicitly select an ordinary contributed failure before cleanup, establish it as pending, append cleanup failures and forbid re-testing the resulting group. The key combination line is 143: “If failure E was already pending, retain errors.join(E F).” Lines 151–155 make selective coverage conservative even when an individual hook can return a group. Traces (a)–(g) are present at 159–268 and instantiated in programs 19–23. Records and arrays are not scanned (139–141); streaming prefixes are not retroactively rolled back (147). There is no remaining type-dependent parse or unspecified ParseError-plus-close order of the kind M1 identified.

This resolves a specification gap, not the readability objection. The same source shape still requires the reader to distinguish a loop's body expression from scoped parallel's own scope. It also means the operator is an all-exit annotation as well as ordinary value selection (135), not just code evaluated after the brace. No parser or cleanup CFG test has been supplied, and I do not treat that as an implementation result.

**M2: YES, resolved by explicit rejection.** The decisive line is round7.md:290: “Reject the inline form if any kept cleanup can fail or its summary is unknown.” That line also rejects the return-expression exception rather than leaving another hidden edge. Line 292 transfers a named place's kept duty to its owning marked block and retains infallible inline statement cleanup. Program 24:12–18 is the rejected counterexample; 20–29 is its named-place fix; 31–36 preserves infallible inline locks and rejects unknown summaries. The restriction is conservative and inconvenient, but it closes the identified hole. An outer brace or call suffix cannot quietly authorize the hidden statement-lived failure (290,294).

The should-fixes are also materially answered:

- **S1:** program 25:4–15 supplies the hook-dependent large buffer, 17–25 its short-scope repair and 28–37 the hook-free control. Adding weight 3 only to block-end changes 15/15/14 to 15/15/17 and raw 6/7/6 to 6/7/7 (round7:298–311). Recommending block-end now rests on source stability, not a winning tally. That is an honest preference with a real memory cost.
- **S2:** program 16:5–15 is the requested actual restoring owner, constructed before mutation and after the gate. Its unwind and restore-before-unlock coverage matches the defer version (17–22). The first-use/reuse costs are correctly counted at 24–26. This establishes substitutability in that case; it does not establish universal ergonomic dominance.
- **S3:** round7:346–352 specifies may-live/may-fail joins, proofs required for discharge, instantiation diagnostics and sound widening/rejection on unknown facts or budget limits. Program 26:3–12 versus 14–24 gives the consume-every-path and maybe-live cases. It promises no exact path-feasibility oracle. Recursive/erased summary behavior still needs concrete compiler cases.
- **S4:** program 01:2–6 and 10–20 use exact int, removing the unstated fixed-width arithmetic proof. Normal allocation costs remain explicitly acknowledged (round7:358).

## Would programmers write the grouped loop correctly unaided?

**I would expect many to write the rejected outer suffix first.** This is a reasoned readability judgment, not a fresh reader experiment. Acquisition and write already say `or_throw`, and the visually natural resource region is the loop's braces. A programmer who has seen `parallel { … } or_throw` has a particularly plausible reason to try the same spelling on a loop. The required repair adds parentheses around braces and puts the suffix inside them, even though parentheses normally mean an unscoped sequence. Transparent grouping is formally consistent with that rule; discovering when it is only grouping is another step. The change fixes the ambiguity by choosing a parse, but choosing a parse is not evidence that people will guess it.

All three alternatives below keep ordinary resource cleanup on error/return. They require a diagnostic for any fallible implicit duty left on a locally continuing exit. They never silently discard failed close or a preexisting body failure. O/C/S are obvious/concise/safe-by-default, graded for the ordinary per-file loop under the same typed cleanup contracts. The safe score assumes the same conservative checker as round 7, including cleanup on failed explicit operations.

| Form | O | C | S | Tradeoff |
|---|---:|---:|---:|---|
| Round 7: `loop … ({ … } or_throw)` | 3 | 4 | 5 | Compact once learned; unusual grouping and skipped-exit annotation. |
| A. Consuming `out.close() or_throw` before continuing locally | 5 | 4 | 5 | Ordinary syntax and a function-exit marker at the failing operation. More complicated bodies can require duplicated completion or restructuring. |
| B. Ordinary loop containing a directly marked inner block | 4 | 3 | 5 | No body-grouping trick; retains one automatic completion policy across all jumps. Adds indentation and two braces. |
| C. A real per-iteration helper, returning a continuation decision | 4 | 3 | 5 | Cleanup is an ordinary function-result contract; caller marks the call. Extra function/result plumbing and explicit translation of outer jumps. |

**A, the best simple-loop alternative:** program 08's final two conditions can safely move after consuming close because they only select a jump; there is no remaining work using out.

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        out.close() or_throw
        if path =? p"skip.txt" continue
        if path =? p"last.txt" break
    }
    printl("all completed")
}
```

Close consumes even on failure (README:36). A failed write already initiates function unwind, so out still completes and joins any second failure. Successful close removes the duty before continue, break or fallthrough. Removing close is a compile error, not permission for hidden local-exit propagation. This is the concrete recommended form for this small loop. For conditions/effects that cannot move, put checked close before each local exit, or select B. An implicit body failure selected only by a suffix must become explicit propagation before close; merely appending close would not preserve its old selection order.

**B, the best general fallback when preserving the existing jumps matters:**

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        {
            let out = files.open(path 'w') or_throw
            out.write_text("row\n") or_throw;
            if path =? p"skip.txt" continue
            if path =? p"last.txt" break
        } or_throw
    }
    printl("all completed")
}
```

This is already expressible under round7:113 and program 11:12–20; it proposes no grammar extension. It preserves automatic close on every edge and the current label targets. It still needs the all-exit annotation rule, so O is 4 rather than 5. I would have a missing-marker diagnostic offer this unambiguous nested-block repair and explain “closing out can return FileError before this continue/break/fallthrough.” The fix-it is assistance, not evidence the original form is discoverable. A repair preserving an existing ordinary-value outer selector must leave that selector in place as well; a cleanup marker is not a reason to silently widen a deliberately selective body policy.

**C** is appropriate only when the work is naturally a subroutine, as programs 06:15–23 and 10:16–23 already demonstrate. The helper owns/completes the file and returns ordinary decision data for the caller to break/continue; `write_one(path) or_throw` makes its possible function exit explicit. Do not treat a lambda as a transparent wrapper around existing `return` or labeled break: those targets change across a real function boundary. Owners bound outside the loop are useful for one resource spanning the whole loop, but are not a general substitute for one distinct file per iteration; extending those lifetimes can recreate program 02/10's waits or program 25's retention.

My preference is **A for program 08, B for a general local cleanup region**. The packet is honest that its grouped spelling has a teaching cost. I would not recommend that spelling as an all-5 usability result without actual cold reads.

## Does defer earn its place after the owner rewrites?

**Yes for one-off local restoration convenience; no exclusive unwind capability is established.** Those are separate tests. The callback owner encodes an action to run later, including capture/effect/lifetime checking. Showing that it can encode defer is not enough by itself to show that replacing a direct local construct makes programs better.

- **16, foreign toggle:** the owner is a good reusable abstraction, and matches the supported unwind/ordering contract exactly (5–15 versus 17–22). It is one statement shorter at each call site and two nonblank lines longer on first use including its three-line definition (24–26). For repeated ABI use I prefer the owner. For one isolated save/restore, defer still makes the restoration expression visible beside the mutation without making the reader find a nominal hook. Neither wins safety from the trusted gate/ABI assumptions. No capability objection survives here.
- **27, borrowed bool:** defer is clearly better for the one-off action shown. Lines 20–23 keep save/change/register/work together in four statements. The replacement adds a three-line carrier type and five body statements (4–12), plus the need to understand explicit shared versus snapshot capture and lifetime/effect preservation through a record (28–37). Both registrations can be forgotten, and both require the same valid borrowed place and non-failing restoration. The owner supplies equivalent unwinding under its proposed checks; it supplies no corresponding safety improvement that pays for the extra machinery in this example. A generic library callback guard could amortize its definition, but that still leaves an extra callback/registration step here and moves defer's action-registration concept into a library. No new helper name is required or approved by this review.
- **15, editor state:** the same convenience objection applies, with stronger whole-editor/field interaction. It is a plausible owner only after the stated paint-footprint and borrowed-place checks are proved (7–22). Reaching many return sites is not the problem; keeping the one-off restoration easy to read is. The capture/restore helper at 24–38 is good for ordinary results and does not cover supported panic unwind (40). This difference is already disclosed, not a new missing capability finding.
- **17, shared sending:** CloseSending is a sensible name for a reusable protocol owner (2–14), but a one-use `defer q.close()` is plainly shorter (15–20). Both need someone explicitly assigned end-of-sending; neither infers that responsibility or eliminates the missing-registration hang (36–39). Prefer the owner when it is an established abstraction, not just to replace one checked statement with an ad hoc nominal type.
- **13, recursive indentation:** prefer the depth parameter (10–17). It removes mutable restoration, so defer earns nothing in this particular program.
- **14, timing:** capture/observe/return is complete and readable for the explicit ordinary-outcome requirement (12–21). If the requirement becomes “record during supported panic unwind too,” the original defer has a real coverage advantage over that exact straight-line rewrite (22–23); a checked timing owner can recover it. That is not a defect in the narrowed current example. Nor should it be counted as evidence that capture is a full semantic replacement for defer generally.
- **18 and ordinary files/locks/timers:** keep intrinsic library release/rollback in owners. Narrow defer cannot safely replace a fallible close or rollback, and neither drop nor defer should publish a transaction (7,17–24).

**Verdict: retain provisional narrow defer**, with the already stated checked non-failing/no-transfer contract, for one-off actions. Default to real owner abstractions for recurring invariants and mandatory library resource release. Program 27 alone is enough to reject “the owner is as good in every relevant respect”; it is not enough to prove defer indispensable to expressiveness. Round7:340 acknowledges the cost accurately, and 342 is a defensible language-minimality preference, but it is not a conclusion forced by the examples. David's provisional keep decision (decisions.md:681–683) still stands unless he chooses to change it.

The local callback implementation gate remains necessary if removal is chosen: prove preservation of the non-owning caller-place provenance and effects through the aggregate; accept local storage, reject escape, and reject conflicting loans without substituting unsafe pointers or copied bools (round7:334–338; programs 15:20–22, 27:28–49). A compiler demonstration should also cover failed construction before activation, all supported unwind paths and restore-before-unlock ordering. This is required validation of the proposal's own claims, not a request to implement it during this read-only review.

## Comparison with the author's grades, read afterward

The original numeric table above was fixed on disk before dogfood-round7.md was opened. The two per-dimension differences of at least two points are:

| Program/dimension | Independent | Author | Reason |
|---|---:|---:|---|
| 19 K | 3 | 5 | I charged the explicit-allocation cleanup-group preservation gate to this combined-failure case (program 19:18–19; round7:97,364); author grades completeness of the ordinary paper trace (dogfood:31,94). |
| 20 K | 3 | 5 | Same broader allocation-lane gate for selected P plus close F and repeated joins (program 20:14–15,44); author grades the fully specified deterministic model contract (dogfood:32,94). |

There are no other differences of two or more. These two differences reflect the scope of K, not disagreement about the specified ordinary-allocation outcomes or a newly discovered must-fix. Under only the ordinary-allocation paper contract, both traces deserve K5; the separate explicit-allocation losslessness gate remains K3. The initial conservative scores are preserved rather than silently revised after seeing the author's. Several one-point K deductions in my table likewise reflect incomplete integration evidence rather than unresolved syntax. The author openly states the same inherited gate at dogfood:94, so this is not concealed incompleteness.

Our strongest substantive disagreement is the design recommendation, not the floor: the author treats equivalent capability plus tolerable owner ceremony as grounds to drop defer; I give the simple one-off restoration syntax in 27 greater weight. We agree that grouped body/arm syntax remains O/D3 and that the foreign owner is not safer merely for being an owner.

## Handoff

- **Must-fix count: 0** for the bounded paper design. Round-6 M1 and M2: yes, resolved. Implementation and usability validation remain outstanding and are explicitly disclosed.
- **Floor: 3**, at **04, 06, 08, 09, 11, 12, 15, 16, 17, 19, 20, 21, 22, 23, 24, 26 and 27**.
- **Best alternative:** explicit consuming `out.close() or_throw` before local exits for the simple loop; an ordinary loop containing `{ … } or_throw` as an inner block for the general jump-preserving form.
- **Defer:** keep provisionally for one-off checked restoration, especially program 27; prefer an owner for reusable invariants. Equivalent unwind capability does not eliminate the direct form's readability and concision advantage.

Only `review-round7.md` was written. The checkout and all other packet files were read-only. No compiler/runtime/native adapter, desktop window/audio, commits or delegates were launched.
