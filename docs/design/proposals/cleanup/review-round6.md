# Independent review: cleanup round 6

**Two must-fix specification gaps:** the selected suffix has not been disambiguated from ordinary value propagation for the difficult cases, and fallible statement-lived lending guards have no acknowledgement rule. These block treating the exit-visibility design as complete; they do not block discussing the timing choice with David. I recommend **block-end observable cleanup**, on the strength of stable, movable source boundaries, not the one-point weighted tally. Retaining provisional narrow defer is reasonable as a convenience; the foreign-global example does not establish a capability that a restoring owner lacks.

Scope: `brief-round6.md`, `round6.md`, `summary-round7.md`, README and all 19 `programs-r6/` files; D40 and decisions batch 9; relevant parts of cleanup rounds 1–5, especially the round-5 rules, amendments and independent review/regrade; relevant ownership, borrowing, errors, loop/label and parallel rules. This was a paper specification review. I wrote only this file and `regrade-round6.md`; no checkout edits, implementation, builds, executions of the paper programs, commits or delegates. Independent scores were written before opening the author's dogfood file. The full per-program regrade and five-language comparison are in the other output file.

## Must-fix findings

### M1 — must-fix: one suffix still has two incompletely reconciled jobs

**Rule/lines:** round6.md:298–306, especially attachment at 299 and ordinary-value preservation at 304; programs 08:19/26 and 19:7/22/28–29. Existing ordinary postfix semantics are in docs/LANGUAGE.md:4177–4188; loop values/fallback chains at 4953–4974. The earlier concurrency proposal also relies on trailing `} or_throw` as an ordinary propagation form (docs/design/proposals/concurrency/unified/proposal-v4.md:327–331).

**Concrete scenario:** remove the record wrapper from program 19's second example. These are full functions; `parse` is assumed to return `int64 | ParseError`:

```dewy
without_owner = () => {
    return [loop text in ["12" "bad"] { parse(text) } or_throw]
}
with_owner = (paths:array<Path>) => {
    return [loop path in paths {
        let input = files.open(path 'r') or_throw
        parse(input.read_text or_throw)
    } or_throw]
}
```

The packet says that the suffix attaches to each iteration's owning body, is not a catch around the loop's values, and leaves ordinary explicit propagation unchanged. It also says bare exception-valued body results retain ordinary `or_throw` policy, but does not give the operational reconciliation. Does `without_owner` forward ParseError? Does `with_owner` do exactly the same? If parsing produces ParseError and close also fails, is ParseError already a pending forwarded failure before cleanup, or still an ordinary expression result waiting for the postfix operation? Those choices determine whether both causes survive. A record containing ParseError (19:18–22) tests neither choice. This is an unresolved specification question, not a claim that the two jobs are impossible to combine.

Attachment also cannot be left to the reader in a conditional chain. For example, in a full function containing `if flag { ...fallible owner... } else { ... } or_throw`, ordinary postfix scope suggests the entire conditional, while the new immediate-body/local-coverage rules suggest only the final arm. The packet does not show the required spelling for marking the first arm, both arms, a match arm, a scoped parallel body, or a loop with an `else` fallback. It explicitly defers this grammar decision at 299. That is new grammar/attachment work even though no keyword is new; the clear new-semantics warning is good but does not itself settle the parse.

**Suggested fix:** state one syntactic attachment rule and an ordered rule for ordinary value propagation versus implicit completion. The interpretation must be fixed by syntax, not change when a generic body gains a fallible owner. Show accepted parses and error/cleanup traces for (a) no-owner bare ParseError, (b) the same loop with a File, (c) ParseError plus failed close, (d) a selective suffix, (e) if/else and loop/else, (f) braced match arms, and (g) `parallel { ... } or_throw` versus ordinary propagation on `parallel ( ... )`. Keep records/arrays containing errors as data. If the intended operator has both jobs, say explicitly how it performs both; if grouping distinguishes jobs, give the actual grouping and the resulting behavior. A minimal clarification is sufficient; a different keyword is not required by this finding.

### M2 — must-fix: the inline lending exception bypasses the visibility rule

**Rule/lines:** round6.md:137 preserves an inline lending guard's statement boundary; 298 requires suffixes for inner owning blocks/bodies; 303 forbids using a more distant outer marker to hide an intermediate failure; 388 admits unfinished expression-temporary coverage. The general returned-place protocol keeps a lending method's locals (docs/LANGUAGE.md:1110–1118; docs/design/ownership.md:238–249). No proposed rule restricts those kept owners to infallible cleanup after fallible hooks are admitted.

**Concrete scenario:** an infallibly acquired guard has a fallible finish. The following is a counterexample to the proposed rules, not a claim about today's compiler support:

```dewy
FinishError:type = type of error
Kept:type = type of [
    $__drop__ = ():>void | FinishError => FinishError
]
Host:type = [value:int64
    view = ():> @int64 => {
        let guard = Kept[]
        return @value
    }
]
inspect = (@value:int64):>void => { printl(value) }
run = (host:Host) => {
    inspect(@(host.view))
    printl("continued")
}
```

The kept guard finishes after the `inspect` statement. Its failure leaves `run` and skips the print, with no exit written there. `inspect` itself returns void. There is no inner owning brace/body for rule 298's required suffix; labeling the function body does not solve a mid-function exit. Merely wrapping the call in a marked brace still does not explain acknowledgement of the earlier statement-lived duty under the locality rule. The explicit expression-temporary caveat honestly limits readiness, but this is a concrete unhandled control-flow edge, not merely missing documentation about when memory dies.

**Suggested fix:** choose a bounded rule now. One solution requiring no additional surface form is to reject a fallible inline lending guard in a locally continuing statement, with a fix-it to a named place inside a marked owning block:

```dewy
run = (host:Host) => {
    {
        let value = @(host.view)
        inspect(@value)
    } or_throw
    printl("continued")
}
```

Alternatively, define precisely how an acknowledgement covers a full-expression guard release and its result/error ordering. Do not silently infer that a caller's existing acquisition suffix covers all future completion. Include fallible kept locals, not just Mutex's infallible unlock, in the acceptance matrix. If fallible lending guards are intended to be unsupported, state and diagnose that restriction explicitly rather than accepting the counterexample.

## Should-fix findings

### S1 — should-fix: add the large owned-buffer retention case to the timing evidence

**Rule/lines:** round6.md:101–129 (panel and recommendation), 135 (an aggregate retains owned children), 139 (unobservable reclamation), 148/390 (retention costs). Programs 01 and 04 already cover long lock holds and timer work; there is no large-buffer example.

**Concrete scenario:** a Batch owns a large byte buffer and an observable release hook. A function borrows `batch.bytes` for decoding, keeps only a small independent summary, then runs an unrelated long tail or waits. Under block-end, the Batch and its required storage survive that tail; under last-use, its hook and memory release can precede the tail. Many simultaneously active calls can turn the extra retention into a meaningful memory-cap/OOM problem. This is distinct from an extra timer ticking and from a peer waiting for EOF. A plain hook-free byte array is a control case, not automatically a block-end loss: the proposal already permits earlier unobservable storage reclamation. If the compiler can free fields before an outer hook without changing behavior, specify that narrower optimization rather than counting it as a semantic guarantee.

**Suggested fix:** add a full-function owner-bearing-buffer before/repair and a hook-free buffer control. State the memory-retention cost without fabricated workload frequency. If assigned a score, report that the one-point lead can disappear; do not tune its weight to preserve the winner. Keep explicit consuming release or a shorter scope as the repair. The current recommendation remains defensible without winning the tally.

### S2 — should-fix: compare the foreign toggle with a concrete small owner

**Rule/lines:** round6.md:81, 361, 368 and 372–378; program 16:6–12 and 24–25. The real-global-state motivation is credible, but the principal no-defer comparison is capture/restore, which intentionally lacks unwinding coverage.

**Concrete scenario:** for the same trusted ABI, an internal module-level nominal owner can store `prior:bool` and assign `$__drop__ = ():>void => { $unsafe legacy.set_diagnostics(prior) }`. Construct it while holding the gate, before changing the flag. In the call site, this replaces save/change/defer with an owning saved-state value plus the change. Since it is acquired after the lock guard, reverse owner cleanup restores the flag before unlock. It covers the same supported unwinding as defer. This needs no local nominal declaration and no new public resource name. Making a reusable safe public interface opaque is a separate encapsulation problem, already acknowledged by the packet; neither approach alone solves it.

**Suggested fix:** show that actual owner alternative with the same contracts and count both definition and call-site ceremony. Explain the real preference: one-off defer avoids introducing a nominal type and makes the restoration expression local; a small owner centralizes the invariant and makes future use harder to forget. Do not frame unwinding coverage as an advantage over that owner. My verdict is **keep provisionally for local convenience, not proved indispensable**. If the pattern already occurs in a library, the owner is at least as strong and likely the better default.

The researched global-state analogue supports the existence of the problem, not ordinary concurrent per-call toggling: GSL's own [thread-safety guidance](https://www.gnu.org/software/gsl/doc/html/usage.html#thread-safety) recommends setting its global controls at startup rather than changing them from different threads. The packet already represents that limitation honestly. No verified GSL adapter was supplied here or by the author.

### S3 — should-fix: state conservative marker checking, not an exact reachability oracle

**Rule/lines:** round6.md:298 and 306 (reachable paths, consumed states, generic instances), 389 (indexed summaries). Program 12:19–29 is the positive consumed-before-continuation case.

**Concrete scenario:** a generic owner is consumed on one branch, moved on another, and retained on a third; an indirect helper has an unavailable or recursive completion summary. A checker cannot assume the remaining path is impossible or cleanup is infallible just because it cannot prove otherwise. Equally, it need not solve arbitrary path feasibility to enforce this rule.

**Suggested fix:** explicitly require a conservative failure/initialization summary: a locally continuing edge that may retain a fallible duty needs acknowledgement; omit it only with proof of consumption, transfer, infallibility or function exit. Unknown summaries reject or conservatively require the marker; type/callable conversion cannot erase the duty. Define the generic-template versus instantiation diagnostic and the behavior at the existing analysis budget limit. The borrowed lifecycle machinery makes this plausible, but “reachable” should not be read as promising perfect false-positive-free detection. Include an accepted consumed-on-every-path generic and a rejected maybe-live variant.

### S4 — should-fix: make the lock paper example obey existing integer obligations

**Program/lines:** 01:2, 5–6, 12 and 20; docs/LANGUAGE.md:5683–5686. This is independent of the cleanup recommendation and does not require running a compiler to identify.

**Concrete scenario:** `balance` is an arbitrary int64, `amount` is an arbitrary int64, and the additions have no range proof or runtime-check opt-in. `entries += 1` is also unbounded. Under the established numeric rules these are not generally accepted arithmetic operations, even if every illustrative Mutex API exists.

**Suggested fix:** use exact `int` for this ledger, state the applicable range contracts, or add the existing runtime-check setting with the resulting panic/unwind assumption. Do not treat this small paper-program correction as a cleanup design failure. It accounts for program 01's K4 in my regrade.

## Checks and design judgments

### N1 — note: the timing comparison is substantially fair and its evidence is honestly labeled

**Rule/programs:** round6.md:97–129; programs 01–07, 08:22–25, 09:18–23 and 10:8–29.

**Concrete checks:** recomputing the table gives L/M/B surprise counts **6/7/6** and weighted totals **15/15/14**, as reported. The author exposes the close-before-EOF benefit of last-use and its opposite session-lifetime need; includes delayed file flush, long lock holds, closures and branch-sensitive last use; counts real later-loop uses and moved captures as ties rather than straw-man early destruction. The Spsc sender-before-join regression is both retained and repaired with a real move and join. Generic fallibility/composition sensitivity is a legitimate strike against the mixed rule, not an automatic strike against uniform last-use.

**Suggested treatment:** keep this calibrated presentation and add S1. Early returns are not by themselves a missing win for either side: all candidates must finish retained owners on a true function exit; a pending returned owner is transferred only after other cleanup succeeds. A long tail before a return is the retention question, already covered for locks/tickers and needing the buffer case. The tally is adversarial scenario coverage, not programmer frequencies or a proof of minimum surprise. The text says so prominently, including correlated EOF cases and sensitivity to weights. No claim of empirical usability testing should be added.

My recommendation remains block-end because a later diagnostic use, a new field and a different generic instantiation should not move observable cleanup. A visible short scope or consuming operation is a more direct repair than a fake last use to keep a session, ambient mode or critical region alive. This is a design preference with real retention/protocol costs, not a statistical result that defeats David's initial last-use intuition.

### N2 — note: composition is coherent where specified, but source-level visibility has a limit

**Rule/programs:** round6.md:298–307; programs 08, 09, 11, 12 and 19.

**Concrete cases:** 11:17–18 correctly consults the inner owner's acknowledgement before a labeled outer break. An enclosing loop with no owner needs no extra cleanup marker; marking it cannot substitute for the inner boundary. With multiple live fallible owning scopes, each locally crossed boundary needs its own acknowledgement; when the first cleanup fails, the remaining unwind is already a function exit and need not hunt for further authorization. An explicit return-only scope (11:30–37) is exempt coherently. Unscoped `parallel ( ... )` cannot complete a lifted owner, while a real nested helper completes its own input. Normal `break`/`continue` and function propagation must still respect the parallel construct's own existing control-flow restrictions; a cleanup suffix grants no new cross-task jump.

**Suggested treatment:** retain those rules and supply M1's exact forms/traces for scoped parallel and match arms. A reader sees `or_throw` and can learn that it signals a possible function exit, but `continue` appears to skip ordinary code after the body. No reader study was performed, and the author's O3 is justified. I would accept candidate C as a plausible scope-level direction after M1/M2; I would not claim it already provides a marker on the precise jump line.

### N3 — note: no strictly better rejected alternative is established

**Rule/lines:** round6.md:172–290 (candidates A–H).

**Concrete assessment:** A's generic scan would conflate deliberate error data with cleanup; B changes per-iteration resource protocols; D is coherent and checked but reintroduces explicit consume work; H is the best idiom when a real helper/whole-value operation fits. E's local-result option deserves its stated ergonomic credit: it is not intrinsically impossible to preserve explicit outer `return` while handling normal block completion locally, but it changes this task's adopted function-result cleanup direction and still needs jump/collector rules. There is no demonstrated all-round dominance over C within the binding brief.

**Suggested treatment:** keep candidate F available if David means textual exit marking on each `break`/`continue`. F meets that stronger visibility requirement better than C and should not be dismissed on mere punctuation count, but it duplicates policy and adds jump grammar. G's acquisition marker signals managed lifetime without directly spelling a function exit. Present C versus F as that real choice, not as a correctness win for C. The packet already flags the distinction in summary.md; preserve it.

### N4 — note: batch 9 is respected; new semantics are disclosed

**Rule/lines:** decisions.md:681–705; round6.md:87–91, 307, 378 and 382–391; programs 14, 17 and 18.

**Concrete checks:** hooks use assigned-function form; abandonment rolls back rather than commits; absence in 18:17 cannot publish; explicit commit consumes. Parentheses do not gain owning scope. Cleanup failures remain function results, with explicit closes/helpers supplying local recovery. Ordinary-result capture in 14:14–16 preserves cancellation rather than defaulting it. Q3 is kept open instead of silently reviving the rejected two-field carrier. The child-process stop bound is retained. Shared-channel explicit close is expressly agreed in D40, so its protocol carve-out is a reconciliation of the broad “library resources never need defer” slogan, not an unannounced channel change.

**Suggested treatment:** keep the approval boundary visible. Uniform observable lifetime, kept-guard retention, all-exit suffix semantics and missing-marker errors are proposals. M1's attachment grammar and M2's restriction/extension must join that list when settled. The narrower no-panic/no-exit/transitive contract for defer is an explicit refinement of its provisional non-failing/no-transfer direction, not evidence that arbitrary foreign void functions are checked safe. Do not move this floor-3 packet into open_decisions.md as an all-5 dogfood result. The existing ownership/reference documents still describe the older implementation and must be reconciled only after approval; this read-only task correctly leaves them untouched.

## Handoff

- **Must-fix count: 2.** M1: settle suffix attachment and ordinary-value/cleanup error ordering. M2: cover or reject fallible inline lending guards before locally continuing code.
- **Independent floor: 3**, at programs **04, 06, 08, 09, 11, 12, 16, 17 and 19**. No per-dimension difference of 2 or more from the author's grades. Programs 13 and 14 are all-5 under their explicit finite-depth and ordinary-result requirements.
- **Timing:** recommend block-end observable cleanup for its stable visible lifetime boundary and straightforward short-scope repair. Last-use has real memory/latency/EOF advantages, and the packet's small weighted tally does not establish which rule surprises programmers less often.
