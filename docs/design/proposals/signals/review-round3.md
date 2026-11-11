# Review of signals as events, round 3

Verdict: the specified closure rule (b) is coherent under the stated restrictions, but the proposal has not established that its mandatory acquisition/release API is minimal. I would revise that part before recommending adoption. I found no demonstrated contradiction in (b) with the accepted dependency, cancellation, or select rules. Its limitations must remain part of the public contract, rather than being described simply as “the handler stops when work finishes.”

References below use `round3.md`, `summary.md`, and `programs/` relative to this scratch directory; `docs/` and `resources/` refer to the read-only repository. I read the task brief, all 23 current programs and three support modules, the final and earlier rounds, and the relevant binding decisions. This is a design review, not a compiler acceptance claim. The existing abstract model ran successfully: 24 startup interleavings and eight scenario groups. Its coverage limits are discussed below. No repository files were changed.

## Must-fix

### M1. Establish the need for mandatory acquisition and explicit stop; the rejected alternative is weaker than the obvious block-lifetime alternative

**Evidence:** `brief.md:9–33,60–62` requires composition with existing constructs before adding machinery. `round3.md:26–31,68–80` instead requires an inert descriptor, an activating shared registration, a separate `defer stop()`, and dynamically selected block views. `round3.md:223,227` acknowledges the earlier ownership objection but rejects “wait-only interception (busy-handler gaps).” That does not reject interception installed once on first use and retained until the owning block exits. `docs/design/decisions.md:633–635` explicitly asks for cleanup that does not depend on remembering a second step; `docs/design/decisions.md:649–655` asks for ordinary concurrent signal handling. The current “smallest working changes” claim at `round3.md:5` is therefore unsupported.

The smallest sound alternative worth comparing is:

```dewy
parallel {
    regular_work() or_throw
    loop _ in signals.ctrl_c or_throw { handle_interrupt() }
}
```

On the first executed signal operation/iterator activation in a running block, attach that block's subscription and retain its interception authority until the block joins. Ordinary helpers inherit that owner. Rule (b) closes its view, preserving queued data; block exit automatically releases its policy. Handle copies cannot extend the block's policy. Passive observation can remain an explicit, rarer operation. This uses no new parser form and needs no remembered release.

**What actually changes:** the default remains in force before the first executed attachment. A press before the listener starts can therefore cancel the root. Busy-handler gaps do **not** restore the default after attachment. Acquisition failures now belong to the first-use operation's stable outcome type. If the application needs interception before any work begins, an optional explicit preparation step is justified. Guaranteeing implicit interception at block entry even through arbitrary helpers would require additional analysis or an explicit readiness mechanism; do not claim that guarantee for free. Overlapping blocks also need a stated policy: independent subscriptions with interception active while any owning block remains, or an explicit controller for applications requiring exclusive authority.

**Simplest fix:** make block-owned automatic lifetime the common path and keep explicit preactivation as an advanced option, or provide a complete counterexample showing why the first-use/block-lifetime alternative fails a required guarantee. If explicit acquisition remains mandatory, make its owner automatically end at its declared scope independently of escaped consumer copies; explicit `.stop()` can remain an early-release operation. Do not describe shared last-handle drop plus a required `defer` as having removed the second-step problem. This finding requires a design revision/comparison, not a return to the rejected callback or inline syntax.

## Addition-by-addition minimality assessment

| Addition beyond the sketch | Needed? Smallest sound alternative and tradeoff |
|---|---|
| Required `.intercept` | A native adapter and an interception activation point are necessary. A separate mandatory public acquisition call is not established as necessary. First use retained to block exit works, with the startup tradeoff in M1. Explicit preparation earns its place when startup ordering matters (`round3.md:68,78`). |
| `.observe` | A distinct passive policy is justified by a library that must not suppress shutdown (`programs/support/telemetry.dewy:3–6`, `programs/22_observer_keeps_default.dewy:3–6`). It can remain an explicit subscription operation while direct source use supplies the ordinary intercepting path. No second keyword or block form is needed. |
| `defer ctrl_c.stop()` | Not necessary for native notification or for (b). It is necessary for the proposal's chosen **shared registration ownership** if copies can escape: last-handle drop otherwise extends interception (`round3.md:69`). A block/scope-owned authority with consumer views that cannot extend it removes the requirement. Current examples do ask users to remember acquire **then** stop. Existing `defer` is allowed for now, so its mere use is not a binding-decision violation; making it mandatory without examining automatic ownership is the minimality failure. |
| Descriptor/registration/view split | Distinguishing native signal identity from individual subscriptions and closure domains is useful internally. A distinct public shared policy-owning registration is not forced by the sketch. A descriptor plus block-owned subscription state suffices for (b). The proposal should distinguish necessary runtime identities from the selected public ownership API (`round3.md:64–74`). |
| `SignalInUse` | Needed only after choosing exactly one exclusive process-wide interceptor. It is not required to prevent event theft: independent subscriptions can broadcast, and an intercepting-subscription count can govern the default. That alternative lets unrelated modules both suppress default behavior; exclusivity instead forces explicit app coordination but still cannot prevent a library acquiring first (`round3.md:72`). State this as a policy tradeoff, not as unavoidable soundness machinery. An explicit exclusive-controller option can coexist with the simpler common path. |
| Per-block mailboxes | Independent **closed state** is necessary if one source can serve independent blocks without one terminating the other (`programs/20_shared_source_nested_blocks.dewy:3–16`). Independent retained notifications are necessary for the promised broadcast semantics. One bounded slot per block is a simple implementation; individual subscription objects could express the same thing. A single destructive queue plus one global close would break those promises. This addition is justified by the selected sharing contract, not by the REPL alone. |
| Unassigned pending slot | Needed to preserve a press between explicit preacquisition and first view attachment, under the chosen registration-wide interception lifetime (`round3.md:78–82`). It is not required with first-use activation. Reusing that slot after every block has closed also carries old presses into later blocks. A simpler optional preactivation API could buffer only for its designated first subscription; alternatively document that preattachment presses coalesce/drop. Each choice changes an explicit delivery guarantee, not memory safety. |
| REPL constructed before `run` | Justified. `docs/LANGUAGE.md:2180–2187,2331–2367` defines construction/defaults and methods, not an implicit asynchronous constructor task. A synchronous constructor calling `run` cannot publish `r` until `run` finishes, so the sibling that reads `r` would depend on its completion (`docs/design/open_decisions.md:210–213`). Construct first, then execute `r.run()` as the work item, as `programs/01_repl.dewy:7–10` does. No new constructor semantics is warranted. The now-unused `alive` field can also be omitted from the minimal example. |

## Closure rule (b): soundness and runtime feasibility

The important invariant is **no currently runnable or ordinarily parked owned activity**, not “no possible future ordinary code.” A continuation after a signal wait can contain arbitrary future work; (b) deliberately closes before that continuation becomes runnable. `round3.md:86–95,129–133` says this and preserves normal results/control flow. It does not fabricate cancellation or silently break a manual loop.

| Case | Assessment |
|---|---|
| Ordinary helpers | Sound: classify the task's actual registered wait, not the helper's name or a guessed source effect. `round3.md:109,139` and `programs/12_library_observer.dewy:7–10` fit this. A helper computing, sleeping, saving, or sending is ordinary activity until it reaches a signal wait. |
| Nested parallel blocks | Coherent, but intentionally context-sensitive. The inner block owns its views and may finish independently; an outer join on it counts as ordinary activity until it finishes (`round3.md:115,139`). The outer block must not count inner views as its own. Wrapping only a listener in a fresh nested parallel block makes it close immediately; sharing a source does not share a lifetime. Program 20 correctly includes work in each inner block. |
| All-signal select / disabled operations | Sound if classification uses the complete enabled wait set, including operations that are already ready, and shares the select's commit discipline (`round3.md:104–108,121–123`). `none` adds no completion source. A losing wait takes nothing, consistently with `docs/design/open_decisions.md:216`. |
| Select mixing signals and timers | The stated rule is sound but provides no automatic end for this handler. A live timer, explicit timeout, channel, or I/O source sustains it (`round3.md:106–108,112`). Repeating a finite timeout does not make the whole loop finite. This is a limitation of (b), not an undecidable analysis problem. See S1. |
| Dependency-blocked items | Round 3 fixes the relevant error. Program 23's report cannot keep its own iterator prerequisite alive (`round3.md:89–93,113`; `programs/23_dependent_report.dewy:11–15`). Ready-but-unscheduled work must count as ordinary. Completion must release/update ready dependents before taking the closure snapshot. Successful-predecessor edges remain binding (`docs/design/open_decisions.md:211`). |
| Scoped owned tasks and `race` | Aggregate actual child states through the ownership tree; include the group body's live execution and any deadline. Only a parent parked solely at the owned join can inherit the children’s signal-only state (`round3.md:111–112,141`). Closed results still follow the ordinary race/failure policy; closure is not special cancellation. |
| `BackgroundTasks` / external task waits | Correctly excluded. An app-owned child can outlive this lexical block and uses its own outside-block lifetime (`round3.md:114,141–143`; `programs/21_external_task_lifetime.dewy:9–15`). Waiting for an unrelated task must not adopt its descendants. This agrees with `docs/LANGUAGE.md:3632–3638` and D4's task policies (`docs/design/open_decisions.md:221–222`). |
| Item mid-handling | Sound for the chosen policy. Compute, sleep, I/O, and sends sustain the block (`round3.md:110,125,137`). Closure may wait indefinitely for an ordinary deadlock. Multiple active handlers can also sustain one another under a continuing event stream; see S1. `race` remains the explicit cancel-mid-handler policy. |
| Queued events, cancellation, and closure | Coherent: close before an immediately ready receive commits, drain existing payload once per view, then return `Closed`; real cancellation wins without consuming data (`round3.md:121–133`). This matches channel draining (`docs/LANGUAGE.md:3679–3687`) and terminal-wait progress checking (`docs/design/proposals/concurrency/unified/select-v6-round11.md:26–30`). |

**Cheap decidability:** yes, for this runtime-state rule. In a finite acyclic dependency graph, a pending node traces to unfinished prerequisite roots. If no runnable/ordinary-parked root remains and the live roots are owned signal-only waits, dependent nodes cannot independently sustain the block. Existing prerequisite counters plus counts for runnable, ordinary-waiting, and signal-waiting work suffice; no inference about future helper behavior is needed. Initialization can be O(n + e), wait transitions O(1) plus ownership-depth propagation, dependency completion pays its outgoing edges, and closing views pays O(v), as `round3.md:207–211` now allows. This is not a proof that a particular runtime already supplies those counters or that a flagship cost gate will pass.

The implementation must serialize wait registration/commit, ready transitions, dependency release, closure, and event routing consistently. “Atomically” in `round3.md:93` is a real synchronization obligation. A snapshot that temporarily treats an already-committed handler as parked, or examines dependencies before publishing newly ready successors, would close prematurely. These requirements can be met with scheduler metadata; they do not establish an impossibility or justify whole-program scans.

## Should-fix

### S1. Qualify the completion promise with mixed waits and overlapping handlers

`round3.md:45` says iteration ends when work finishes, while `round3.md:97,106–112,137` supplies necessary exceptions. Add a compact counterexample beside the idiom:

```dewy
parallel {
    finite_work() or_throw
    loop true {
        match select(@ctrl_c.next timeout=1s) {
            <CtrlC> => handle_interrupt()
            <Timeout> => report_status()
            <Closed> => break
            <Canceled> => Canceled or_throw
        }
    }
}
```

Under the proposal this can run forever after `finite_work` finishes: every iteration has an ordinary timer. Likewise two busy handlers can keep at least one item in ordinary activity continuously, so the cohort never becomes signal-only. The “one final queued invocation per view” bound at `round3.md:125` bounds the backlog **once closure occurs**, not the total invocations after ordinary work finishes. The busy-handler example has only one handler (`programs/08_busy_handler.dewy:16–19`) and does not test this distinction. State it explicitly and show the existing done-channel/race escape. This does not require expanding (b) into intent inference.

### S2. The REPL still has two delivery paths, and the boundary can still scramble its prompt

The branch is mechanically predictable: an intercepted arrival during the terminal read becomes `Interrupted`; another arrival goes to signal views (`round3.md:183–185`). But a reader must implement the same user action at `programs/support/repl.dewy:7–10` and `programs/01_repl.dewy:10`. The signal-only handler normally does not handle a press while the prompt is waiting. It can also print after the next prompt: a press arrives between reads, its iterator task becomes runnable, then the REPL prints/starts the next prompt before that task prints. Not converting an older queued event to `Interrupted` (`round3.md:183`) does not serialize this output.

This split is inherited, not an undisclosed new contradiction: v5 explicitly consumes a press in the console read rather than delivering it twice (`docs/design/proposals/concurrency/unified/proposal-v5.md:180–197`), and D4 retains stable `Interrupted` input types (`docs/design/open_decisions.md:219`). Preserve that fact when describing alternatives.

Smallest alternatives: (1) for a prompt-only REPL, handle `Interrupted` in the prompt owner and omit the parallel printing watcher; it cannot provide a distinct non-input handler without further coordination; (2) for a full REPL, use an existing `race` around a command/read operation and the signal wait, return `Interrupted` from the read helper without printing there, and handle both `Interrupted` and `CtrlC` in the REPL owner after the loser joins. This can preserve console consumption, but must specify the terminal adapter's cancellation/line-reset behavior when a queued event wins against a newly started read; (3) always broadcast to the event source while input reports `Interrupted`, but then one component must own notification/output to prevent double printing. Alternative (3) changes the existing consumption policy. At minimum, narrow the prompt-ordering claim to the exact active-read case at `round3.md:185`.

### S3. Complete the resource lifecycle and arrival linearization contract

If retaining the proposed ownership model, explicitly state the following in the final rules:

- **Stop:** does it preserve each view's pending payload, close every existing/outside-block view, and make every future view closed? Round 1 says stop closes all views (`round1.md:52`), and the model does so (`closure_model.py:38–41`), but the final API description only says idempotent/infallible/nonwaiting (`round3.md:69,161–171`). Distinguish discarded unassigned data (`round3.md:80`) from preserved attached data.
- **Retirement:** remove each block's routing entry when that activation finishes, and reclaim a closed mailbox once nobody can consume it. Repeated sessions with one long-lived registration must not retain every historical block. `closure_model.py:20–27` keeps historical views, and `closure_model.py:31` scans all of them. That is fine for a small model, but does not validate the final O(open views) routing or active-memory bounds (`round3.md:209`).
- **Native arrival versus scheduler dispatch:** ownership/read-active selection must be fixed at the defined arrival point. The raw native handler records while the scheduler routes later (`round3.md:175`), but console consumption is determined “at the arrival” (`round3.md:183`) and acquisition is a linearization point (`round3.md:78`). State how registration/read epochs distinguish a stopped/reacquired controller or a read that finished before dispatch. Do not accidentally deliver an old press to a new owner, or interrupt a new read. This is an implementation obligation with metadata/synchronization costs; no user syntax is needed.

### S4. Add actual boundary cases before treating the abstract model as closure-bookkeeping validation

The model's `dependent` state has no prerequisite edges (`closure_model.py:45–51,122–129`). Its owned-frontier checker is separate from block closure (`closure_model.py:112–121`); it does not simulate joins, a group body, select commits, nested owners, or readiness publication. Consequently it checks manually classified examples rather than the general DAG/ownership algorithm described at `round3.md:207–209`. The limited-claim language at `round3.md:233` and `dogfood.md:127` is welcome.

Before implementation, exercise a dependent with multiple prerequisites, a prerequisite becoming ready on the final completion transition, an owned join containing ordinary body work, mixed selects after source retirement, and two overlapping busy handlers. These can be small state traces; a new compiler analysis or evidence artifact is not required. Do not call the current model proof of cheap graph-aware closure.

### S5. Keep the costs of the native adapter and Windows close distinct

`round3.md:175` describes a bounded notification-only native handler, whereas `round3.md:203` requires a Windows close callback to remain outstanding for the cleanup attempt. The latter is an explicitly waiting native callback, even though it runs no Dewy user code. State that backend-specific exception and account for callback/wakeup resources separately from scheduler fan-out. This is an internal inconsistency in the blanket cost wording, not a finding that Windows best-effort cleanup is impossible. The platform floor is already disclosed, and this review does not independently validate the external platform documentation.

## Nits

- **Task wait call style:** `programs/21_external_task_lifetime.dewy:15` writes `watcher.wait`. Its successful result is `void`, so it should be `watcher.wait()` under `docs/design/decisions.md:549–552`; v5 makes that exact example explicit at `docs/design/proposals/concurrency/unified/proposal-v5.md:24`. Error alternatives do not turn a successful-void call into a value-producing call for this convention.
- **Remove unused REPL state from the minimal presentation:** `round3.md:11,13` and `programs/support/repl.dewy:3,5` maintain `alive`, but the selected handler does not read it. The example works without it. Keeping it only for comparison with David's sketch should be labeled as such.
- **Names remain provisional:** `round3.md:219` correctly disclaims cold-read approval. Keep that caveat before any of these names enters a decision item; the standing gate is `docs/design/decisions.md:424–426`. No name or approval claim is supplied by this review.

## Binding-decision reconciliation

- The final design uses prefix metatags, ordinary errors, `Closed<E>`, cancellation forwarding, source-qualified select arms, and the accepted `priority='index'` spelling consistently with batches 3–8 (`docs/design/decisions.md:510–517,604–623,639–655`). The `.wait()` spelling nit is the concrete exception found above.
- The proposal explicitly changes v5's foreground-only/nested-innermost interception into exclusive process-wide shared ownership (`round3.md:72,223`; v5 `proposal-v5.md:187–191`). This needs to remain a disclosed redesign. It is not already approved merely because `CtrlCListener` was accepted with a redesign caveat (`docs/design/decisions.md:621–623`).
- Context-sensitive view selection is a deliberate exception to the standing preference at `docs/design/decisions.md:483–485`. Independent block closure is a concrete reason for local state; it does not automatically justify the longer registration lifetime or mandatory public acquisition. Keep those arguments separate.
- Replacing the rejected inline forms with ordinary function-handle calls for protection/groups is within the requested direction (`brief.md:62,78–79`; `round3.md:195–199`). Protection still earns its place: an ordinary deadline cannot make I/O proceed under an already-pending parent cancellation (`docs/design/open_decisions.md:220`; `docs/LANGUAGE.md:3588–3598`). No new hidden `return`, forged cancellation, or source provenance through arbitrary helpers is warranted.

Overall, the strongest parts are visible closure, correct treatment of dependent continuations, separation of real cancellation from `Closed`, and explicit platform/cooperative limits. The weakest part is calling the public ownership ceremony essential before comparing it with automatic block ownership. Preserve (b), the native adapter, and explicit REPL execution; simplify or substantiate that ceremony and keep the timer/handler/input limits visible.
