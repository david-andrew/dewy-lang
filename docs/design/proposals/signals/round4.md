# Signals as ordinary concurrent work — round 4

This round supersedes round3. It accepts M1, S1–S5, the nits, and the independent regrade's substantive findings. The earlier mandatory registration ceremony was not necessary; its escaped-owner hazard was a real safety defect. Keep visible closure (b), with its precise limits. Earlier rounds and summary.md remain unchanged.

## The common path and its limit

```dewy
import p"@lib/std/signals.dewy" as signals
main = () => parallel {
    regular_work() or_throw
    loop _ in signals.ctrl_c or_throw { printl"Ctrl-C received" }
}
```

The **first executed signal wait** attaches this block's subscription. Interception remains active between waits and while the handler works. The block's exit automatically releases it, on every path. No `.intercept`, signal `.stop()`, or `defer` is required. Descriptor copies cannot retain authority. Program 32 supplies concrete finite work for this example.

**This is not a guarantee that handlers eventually stop whenever the named work finishes.** Closure occurs when all remaining runnable/parked activity is signal-only. A mixed timer/signal loop can remain live forever, and two overlapping busy handlers can sustain each other under continuing arrivals. The backlog bound applies **after closure**, not after the named work finishes. Programs 26 and 27 are deliberate counterexamples; 19 uses a done channel, and 28 races each handler against done to cancel even mid-handler. Those are the existing escapes when eventual shutdown under an ongoing event stream is required.

Before the first wait attaches, Ctrl-C retains its default. The runtime does not scan future code or execute helpers early. Program 24 orders startup-sensitive work after an existing `next(timeout=0s)` operation in the same block. That is optional early attachment, automatically owned by the block, not a new API. Program 25 uses it in two blocks plus ordinary channels to announce that both subscriptions are ready.

## The REPL: one printing loop, ordered reprompting

The record is constructed first, then explicitly run. It needs no `alive` field. To meet the requested output order, choose review S2 option (2), with an ordinary acknowledgement to the printing loop:

```dewy
import p"@lib/std/signals.dewy" as signals
UnexpectedSignalClose:type = type of error
OutputHandlerClosed:type = type of error
repl:type = [
    run = (notices:Channel<bool> printed:Channel<bool>) => {
        defer notices.close()
        loop true {
            match race(@input(">>> ") @signals.ctrl_c.next) {
                line:string => {
                    if line =? "quit" break
                    printl"you said {line}"
                }
                <Interrupted | CtrlC> => {
                    notices.send(true) or_throw
                    match printed.receive {
                        <bool> => {}
                        <Closed> => OutputHandlerClosed or_throw
                        <Canceled> => Canceled or_throw
                    }
                }
                <EndOfInput> => break
                <Closed> => UnexpectedSignalClose or_throw
                <Canceled> => Canceled or_throw
                problem:error => problem or_throw
            }
        }
    }
]
main = () => {
    let r = repl
    let notices = channel<bool>(1)
    let printed = channel<bool>(1)
    parallel {
        r.run(notices printed) or_throw
        loop _ in notices or_throw {
            printl"KeyboardInterrupt"
            printed.send(true) or_throw
        }
    }
}
```

The error types and channel names here are application-local, not new standard-library API. Programs 01 and support/repl contain this design with the printing loop factored into an ordinary helper. Construction starts no task. EOF and `quit` close notices; the printer ends visibly. File/input errors propagate rather than being mistaken for EOF. Actual `Canceled` propagates.

The reader and event wait race under the same enclosing owner. A press during the active read gives that owner `Interrupted`; an otherwise delivered press gives `CtrlC`. The read helper does not print. Race joins the loser before returning either outcome. When a queued event wins against a newly started terminal read, cancellation resets/discards that read's partial editing buffer and releases terminal-read ownership before the loser joins. It must not leave a detached reader or replay that partial line into the next input. This is a required console-adapter behavior, not a claim that today's implementation has been tested for it.

The resulting order for an interruption **selected by this race** is: finish/reset the read; send one notice; handler prints `KeyboardInterrupt`; handler acknowledges; next read begins and prints its prompt. A canceled read may already have displayed its now-abandoned prompt; the reset terminates that line before the message. The promise concerns the next fresh prompt, not erasing terminal output already produced. If a completed input line wins concurrently with a different pending press, the existing race tie rule applies; signals are coalescing notifications, not a lossless keyboard log. Nothing promises ordering against unrelated tasks that write to the same terminal.

Why this is not the literal two-loop sketch: independent `input` and printing tasks do not establish a happens-before edge between an interrupt message and the next prompt. Silently supplying that edge would be new console/scheduler policy and could deadlock arbitrary handlers. The two channels make it explicit using existing constructs. The handler still owns the message, but iterates over notices selected by the read owner rather than directly consuming the raw source. This is an honest concision cost (3), not a claim that the extra plumbing was in David's sketch.

S2's alternatives were weighed:

- **(1) Print `Interrupted` in the prompt owner and omit the watcher:** shortest for a prompt-only REPL, but does not put notification in the requested handler loop or coordinate non-input interruption.
- **(2) Race read/work and signal, then report one selected outcome:** chosen. It preserves the v5 input-consumption rule for one owner and makes reset/join and prompt order explicit. Printing directly in the owner after the race would eliminate the two channels; the chosen version keeps David's separate printing loop.
- **(3) Always broadcast to the owner's signal iterator as well as returning `Interrupted`:** would require another coordination/deduplication rule to avoid printing twice or reprompting early, and changes v5 consumption. It earns no simplification here. Do not claim ordinary asynchronous console output automatically repairs the prompt.

## 1. Public sources and automatic owners

`signals` remains the ordinary module `@lib/std/signals.dewy`. Each member is a copyable, inert `SignalSource<E>` descriptor. Its direct iterator/`next` interface is the intercepting mode. `.observe` returns the passive mode of that descriptor; reading this member itself attaches nothing. First executing an operation does. Aliases and prepared operations carry signal identity and mode, not a live subscription or authority.

| Descriptor | Native event | Payload E |
|---|---|---|
| `signals.ctrl_c` | POSIX SIGINT / Windows CTRL_C_EVENT | existing `CtrlC` |
| `signals.sigterm` | POSIX SIGTERM | `signals.Signal[name='sigterm']` |
| `signals.sighup` | POSIX SIGHUP | `signals.Signal[name='sighup']` |
| `signals.sigwinch` | SIGWINCH on targets providing it | `signals.Signal[name='sigwinch']` |
| `signals.sigusr1`, `signals.sigusr2` | POSIX SIGUSR1/2 | corresponding `signals.Signal` |
| `signals.ctrl_break` | Windows CTRL_BREAK_EVENT | `signals.Signal[name='ctrl_break']` |
| `signals.console_close` | Windows CTRL_CLOSE_EVENT | `signals.Signal[name='console_close']` |

All descriptors are exported consistently. Unsupported/missing facilities fail at first use, not at an inert field read. `Signal.name` is the literal union of the seven non-Ctrl-C names above. No native count, portable signal number, sender identity or terminal dimensions are implied.

Stable outcomes:

- `source.next`: `E | Closed<E> | signals.SignalUnavailable | Canceled`.
- `source.next(timeout=d)`: the same union plus `Timeout`.
- `loop x in source or_throw`: yields E; drains normal closure then ends; forwards unavailable/cancellation failures.
- `source.observe`: passive `SignalSource<E>`, without an acquisition failure or a separate release operation.

An attachment failure and subsequent loss of an attached facility both give `SignalUnavailable[message=...]`. **Backend loss no longer looks like successful `Closed`.** This is a deliberate improvement over round3. An attached source that loses its facility retains already pending payload, then gives the terminal error; a selector's ordinary priority may choose some other source first. Iteration forwards that error, not EOF. Cancellation still has priority at the operation boundary. Types do not change after successful attachment. An already-recorded terminal failure is sticky: normal block closure cannot replace it with Closed. A terminal error cannot be ignored in a loop while leaving the same failed operation active; the terminal-progress rule applies.

`next` returns a payload and omits `()`. `Task.wait()` succeeds with void and keeps `()`, despite possible failure alternatives. Source-qualified arms, `.types`, and generated outcome-type members use existing Waitable machinery. Removing SignalListener does not mandate deleting an already-approved `CtrlCListener` spelling; it may be an alias for the Ctrl-C descriptor if compatibility is needed, but confers no ownership.

### Which scope owns an executed wait

The nearest **running parallel block in the structured ownership context** owns attachment. Ordinary synchronous helpers and owned `race`/`within` children inherit that context. A nested parallel creates its own owner. An app-owned/background task does not inherit a short lexical caller block: its task entry establishes its own automatic root scope. Structured children without a nested parallel inherit their enclosing owner, so a race winner does not release a subscription before the caller's subsequent cleanup.

Outside any parallel block, the current entry task's automatic root scope owns subscriptions until its structured work and cleanup finish. Rule (b) does not close that root's signal views merely because they are its only waits. This preserves a plain signal-service loop, root-level read/signal races and save-after-interruption code. It also means a helper that directly listens can change its caller's signal policy for the rest of that owner scope. Libraries should normally observe. A tighter lifetime is a `parallel` with the actual work and listener together, not a lifetime inferred from descriptor copies.

Copies cannot extend or reopen an old owner. An escaped descriptor used elsewhere either does nothing (it is inert), or its newly executed wait attaches the **new** owner. There is no consumer object holding the old block alive. On cancellation or error, the owner still stops/joins its owned work, runs normal cleanup, then automatically releases all its subscriptions. This uses the already-existing structured cleanup obligation. A task deliberately ignoring cancellation can still delay its own exit; handle leakage is not the cause. Program 30 specifically retains a descriptor in another task without waiting on it and verifies the intended restoration point by design, not by native execution.

### Broadcast and library policy

There is one bounded mailbox per `(owner activation, native signal, mode)`. Repeated uses/copies within that owner and mode share the mailbox, so two same-owner receivers compete as channel receivers do. Passive and intercepting modes have separate mailboxes. Different owners receive independently. An intercepting-subscription count, not exclusivity, selects default suppression. `SignalInUse` and the required `.intercept` operation are withdrawn.

After each owner attaches, arrivals go to every applicable intercepting view and every passive view, with the console-read redirection below. A late owner gets future notifications only; no registration-wide unassigned slot or cross-scope replay survives. An attached view retains at most one pending notification while its handler is busy. Further arrivals coalesce. Losing select/race receives take nothing. A scope that has locally closed its signal views still holds its interception policy until scope exit; new arrivals are not queued into those closed views. Avoid leaving unrelated long-running tails in that scope if default restoration is needed earlier.

A library listening directly in its own block **does suppress the app's default Ctrl-C while that block remains attached**, even when another block has finished. It does not steal another block's events; both intercept. Program 31 makes that change explicit. `.observe` is the passive library spelling (12/22). No namespace boundary grants or removes signal authority; this is not a security sandbox. Reintroducing exclusivity would not stop a library from acquiring first and has no demonstrated required use case in this round.

## 2. Closure rule (b), unchanged in intent

Each parallel activation has a one-way `signals_closed` state. After publishing completed work, newly ready successors, and wait registrations, the runtime may set it when at least one item remains unfinished and all remaining activity is:

1. signal-only waits on this block's views;
2. an owned join whose entire live frontier, **including its group body**, is such waits; or
3. dependency-blocked items whose unresolved same-block prerequisites lead only to those waits.

Ready-but-unscheduled code, compute, a live group body, a timer/timeout, channel, I/O or external task wait is ordinary activity and prevents closure. Pending continuations cannot keep their own signal prerequisites alive (program 23). Ordinary helpers are classified by their actual current operation. A nested parallel owns separate views; an outer join does not close them. A block with only signal listeners closes when all reach their waits. Program 29 shows the direct helper, nested signal-only refactor, and outside-parallel root cases side by side.

An all-signal `select`, with `none` operations removed, qualifies; a live timeout does not. `merged` uses its active source table; retired sources no longer sustain it, and a mixed source can become signal-only after its ordinary sources retire. Owned races/groups propagate actual frontier state. A separately owned task wait is opaque. These are runtime classifications, not guesses about future helper intent.

Classify/register before consuming an immediately ready signal. Closure closes all views in the cohort, preserving each already pending payload. Each view drains that payload and then gives `Closed<E>` forever. A view first used after the block's latch is set starts closed **without attaching or intercepting**. No old notifications are replayed. New work in a continuation does not reopen the latch; a genuinely new phase needs a new owner or explicit coordination.

An iterator visibly ends. A manual loop visibly handles the outcome:

```dewy
loop true {
    match signals.ctrl_c.next {
        <CtrlC> => handle_interrupt()
        <Closed> => break
        <Canceled> => Canceled or_throw
        problem:error => problem or_throw
    }
}
```

`next or_throw` forwards Closed as a failure, never as a hidden break. Genuine cancellation remains Canceled and is checked before payload/terminal results; closing views does not cancel tasks or swallow errors. Code after iteration and its defers run normally. The parallel block joins normal tails, rather than pretending source closure is function return. Existing deferred cleanup grace, explicit protection and error policies remain.

### The two shutdown counterexamples

**Mixed timer:** program 26 does finite work beside `loop true { match select(@signals.ctrl_c.next timeout=1s) ... }`. Each wait has a timer. After work ends, each timeout schedules another iteration. The loop can last forever. A finite timeout is not a finite handler lifetime. Program 19 adds a done channel and `priority='index'` so done wins when both it and a signal/timer are ready.

**Overlapping handlers:** program 27 has two independently delivered views: A's body lasts 2s, B's 3s. Start both handlers at t=0 and finish named work at t=0.5. Deliver another notification at 1.1, 2.2, 3.3, ... seconds. At t=2 A asks again while B is ordinary and consumes its pending event; at t=3 B asks while A is ordinary; at t=4 A asks while B is ordinary. At t=6 schedule one ready completion before the other's registration; a runnable peer still counts ordinary. This can repeat. These arrivals never need three per second. There need never be a collective signal-only instant, so no closure or finite post-work backlog follows.

The rule is sound but gives no eventual-shutdown guarantee in that schedule. The fix is a written intake cutoff: program 28 closes done after work and races **each** handler against done. It cancels/joins mid-handler; ongoing signal arrivals cannot remove done readiness. Finishing current handlers instead is also possible with a done-channel select between bodies, but the current body can still block forever. All cancellation/deadline bounds remain cooperative.

## 3. Ctrl-C and console behavior

With no intercepting owner, default Ctrl-C requests root cancellation, immediately reports stopping, and unhandled Ctrl-C-derived cancellation exits 130. Retain v5's next-press force exit during that default shutdown. Three separately runtime-observed Ctrl-C arrivals within one second force exit even while intercepted or protected. Count before mailbox coalescing; the OS can coalesce physical presses before observation. An observer does not suppress any default. Interception never masks pending parent cancellation, explicit task stops, sibling failures or deadlines.

With any intercepting owner, root cancellation is suppressed for new Ctrl-C arrivals. For terminal input, preserve v5's consume-in-input behavior **within the read's owner**: if its active terminal read wins the interruption transition, return Interrupted and clear the partial line, without also enqueuing that same control delivery into that owner's intercepting view. Other intercepting owners still receive their events, as do passive observers. This is the explicit extension of v5's single-catcher rule to multiple owners. If the read's owner has not attached but another owner is intercepting, the read can still return Interrupted; it cannot invent a missing signal subscription. With no interceptors it observes root Canceled instead.

`input`, numeric input, `read_line` and console failure aliases retain stable Interrupted outcomes. `input` has EndOfInput; read_line has none at EOF. Pipe/file stdin remains ordinary I/O; raw terminal bytes are not converted to signals here. Ordinary EINTR is not a user KeyboardInterrupt. A queued old signal is not retargeted to a newly started read. Program 01's race can deliberately select that old queued event and cancel its own newer read; cancellation reset then makes the ordering explicit.

Foreground children receive the terminal's SIGINT independently. The parent does not retransmit it. Program 05 preserves parent interception through its task-owned child wait and prints any selected interruption before its next fresh prompt. `run` owns/reaps the child; a bare `child.wait` does not transfer ownership. Full process-group handoff, job suspension and terminal job control remain outside this sample's capabilities. SIGTERM/HUP/USR defaults and SIGWINCH's native behavior remain native without interception. Windows Ctrl-Break is separate, with no new universal exit-code convention. Windows close cannot be vetoed; see below.

## 4. Lifecycle, arrival epochs, and cost

There is no public signal stop/release operation in the common API. Automatic transitions replace S3's old stop question:

- **Local normal closure:** detach views from event fan-out; preserve their queued payload for draining; keep the owner's interception count until owner exit. Later uses of the closed owner get Closed without attachment.
- **Facility loss:** stop accepting new events, retain queued payload, then return SignalUnavailable. The subscription no longer supplies an effective native interception count once that facility is gone; other native signals/owners are unaffected. A failed owner-mode pair stays terminal for that owner, rather than silently reattaching on each next. A fresh owner may try again.
- **Owner exit:** revoke its authority regardless of aliases, remove routing entries and owner-table entries, and discard any unconsumed mailbox contents after its consumers have joined. Release native cleanup holds. Future owners start fresh. Repeated sessions must not accumulate historical routing entries.
- **In-flight capture:** defer reclamation only until the adapter's in-flight references to that routing epoch are quiescent. A queued wakeup uses a generation-checked internal ID and cannot resurrect a retired scope. No public descriptor owns those internal records.

Define **arrival** as the native adapter's capture/receipt linearization point, not the later scheduler dispatch and not an unknowable physical key-down instant. At that point select the then-live routing epoch, the interception count and any active terminal-read generation. Attachment/revocation and capture must be serialized consistently. The terminal adapter arbitrates read success/cancellation/interruption on the same read-generation state: if line completion already committed, that old read is not interrupted and delivery uses source views; if interruption committed first, read completion returns Interrupted. A later read generation is never substituted at dispatch.

A concrete feasible adapter may publish immutable routing snapshots and, during capture, atomically mark the matching live views' preallocated pending slots and the selected read generation. Retiring snapshots/slots waits for in-flight capture readers before reclaiming storage. This makes recipient identity fixed before the scheduler runs and avoids replay into a newly attached block. It does **not** cost O(1) per native arrival: marking v recipients costs O(v). POSIX capture code must use only operations proven async-signal-safe/lock-free on that target; alternatively a target may use an appropriate native signal-wait adapter with the same defined receipt point. This is an implementation obligation, not an already-written portable lock-free algorithm.

First-use installation can fail; it installs all required state atomically or none. An optional timed poll attaches exactly as any next does. A losing select/race operation may still have performed this first-use attachment: loser **commit** consumes no event, while attachment lasts to owner exit by design. Disabled (`none`) operations do not attach. No native adapter queues a callback to user Dewy code; the scheduler executes all user handlers as normal tasks.

**Windows close is the explicit exception to a notification-only native callback.** Its native control callback signals the scheduler and may wait on an internal cleanup-completion gate while the owners captured for that close attempt finish, subject to the host's timeout. No Dewy user code runs in that native callback. The gate, native callback thread/stack, waiting handle and in-flight epoch references are separate resources from mailbox fan-out. A newly attached owner does not prolong an old close event. Passive observers do not hold the close callback open. Neither a time budget nor a scope can prevent OS termination, and the console may already be unusable. This retains the platform limitations described by [Microsoft HandlerRoutine](https://learn.microsoft.com/en-us/windows/console/handlerroutine); it is not revalidated by running Windows here.

For the scheduler side, lazily initialize signal-owner counts from existing item/dependency state in O(n+e). Local wait state transitions are O(1), plus ownership-depth propagation and existing outgoing dependency-edge processing; a cached-frontier implementation must charge every affected edge. A select already registers s waits and classifies them in O(s). Closing an owner's v views costs O(v). Routing/capture is O(active recipients), with in-flight retirement state also charged; memory is O(active owners/items/edges/views/waits plus in-flight capture/close-callback resources), not O(all historical sessions). Native installation, synchronization and Windows cleanup gates are additional backend costs; the number of concurrently outstanding native close callbacks is not assumed constant. No performance measurements or constant-time native notification claims are made. Future implementation must pass the flagship instruction-count gate.

## 5. Work, cleanup, shutdown errors, and unchanged decisions

Program 02 races search against Ctrl-C, joins the loser, saves under a deadline, then explicitly exits 130. Program 13 uses default cancellation and protects the save while the parent is already canceled. `protect_from_cancel(5s @save(best))` remains necessary: `within` alone cannot run through a pending parent cancellation. Protection has its own cooperative deadline and retains independent Canceled/save errors; the caller preserves original cancellation after reporting save failure. It is an ordinary handle call, with no nonlocal return or new block syntax. The durable temporary-file/sync/replace sequence remains a separate already-proposed library dependency.

Programs 02/03 now **fail on unexpected Closed**, as well as forwarding SignalUnavailable and real cancellation. Program 11 exits nonzero on unexpected closure/facility failure without relying on a closing console. Root-level shutdown watchers normally cannot close by (b); swallowing Closed as success would conceal a lifecycle mistake or later refactor. No new public error type is needed: UnexpectedSignalClose is private application code. Program 14 uses merged to drain every normally closed control source; one facility error fails the monitor explicitly, so final buffered reload/dump work is not promised on error.

Program 03's accepted request has **five seconds from entry into its protection**, not a new five seconds beginning at SIGTERM. Race cancellation stops further acceptance and waits for that bounded request to close its socket. The final counter write has a separate two-second limit afterward. These are cooperative, and this is not a five-second total shutdown SLA. Program 11 likewise uses temporary/sync/replace publishing to preserve the old checkpoint if the new write is cut short, with those provisional durable-path operations as an explicit dependency. It makes a best-effort attempt, not a durable-save guarantee before Windows termination.

Programs 04/21 handle real channel/task lifetimes instead of assuming signal closure solves them. The game closes its command channel so a blocked signal-to-command sender can leave. The background watcher has a defer requesting stop on every exit; normal completion also waits with `watcher.wait()` and checks caller cancellation after consuming expected child cancellation. Program-group cleanup joins after early failure. It is passive so it cannot accidentally extend interception.

Finite groups remain parallel blocks/comprehensions. Dynamic spawning can use ordinary `task.tasks(@body)` and existing Task handles when needed; local callback returns, success joins, failures stop/join, none is success. Signals need no special callback/inline scope. Prefix metatags, accepted select priority/source qualifications, losing-operation discipline, ordinary errors, real cancellation, and record value semantics are unchanged.

## 6. Boundary traces required by S4

These are explicit design traces, not claims that the old abstract model proves a DAG scheduler. `closure_model.py` is left as an older, limited model; it does not validate round4's lifecycle/epochs. The following are implementation acceptance cases.

1. **Two prerequisites:** A is ordinary work; H is a signal iterator; report R depends on both. While A is ordinary, no closure. Complete A and publish R's remaining prerequisite H; H is now the only live root, so close H. H drains/returns; R becomes ready and runs. This is program 23 extended to two prerequisites, not an opaque `dependent` label.
2. **Final completion releases ordinary work:** A is ordinary; H signal-waiting; B depends only on A and performs ordinary I/O. A completes. Decrement B's prerequisite counter and publish B ready **before** taking the closure snapshot. B sustains H. A snapshot between those steps is invalid. Only after B finishes may H close.
3. **Owned join with a live body:** a group has two signal-waiting children but its body is still writing a file. The body is ordinary and prevents closure. Once the body finishes and the parent is parked only on that owned join, the all-signal child frontier may participate. A child-only summary would be wrong.
4. **Select commit versus closure:** a signal is ready while another item completes. Register the full select and publish commit/runnable state under the same scheduler ordering. If the receive commits first, its handler is runnable and sustains the block. If closure wins first, preserve the pending value, deliver it once, then Closed. Never leave a committed handler mislabeled parked during the snapshot.
5. **Mixed select after retirement:** a merged source initially has a live ordinary channel plus a signal source. The ordinary channel closes; drain its payloads and retire it. The remaining active signal-only wait can qualify. By contrast an unretired closed channel in an unchanged select is terminal-ready; ignoring it is the existing progress error, not permission to classify it as absent. A live timeout never disappears merely because previous timeouts fired.
6. **Overlapping handlers:** the 2s/3s/1.1s schedule above can avoid quiescence forever. With done at t=5 in program 28, both owned races see done readiness, cancel the still-running bodies and join. Native arrivals do not erase that readiness. Uncooperative bodies can still delay joining.
7. **Scope retirement and alias:** attach owner A, retain a descriptor elsewhere, close and join A, remove A's routing entry/count. A later press defaults if no other owner intercepts. Executing a wait in owner B may attach B, but merely retaining/copying the descriptor cannot do so. Repeat many sessions: live routing size returns to its baseline after each; the old model's historical map is not acceptable implementation storage.
8. **Late dispatch and new owner/read:** capture a press under owner A/read R7. Before scheduler dispatch, A exits and owner B/read R8 appears. The pending wakeup references A/R7's generations, never B/R8. If R7 had completed before capture's arbitration, route as a signal event to A instead; if interruption won, R7 completes Interrupted. Reclamation waits for the capture reference, not for arbitrary descriptor holders.
9. **Broadcast barrier:** in program 25, A attaches, then B attaches, then both ready messages are consumed. Only after that announcement does a new captured press guarantee a mailbox in both blocks. An earlier press may reach only A (or default before either attached); no implicit startup barrier is claimed.
10. **REPL boundary:** active read returns Interrupted, or a queued source event wins and cancels/resets the newly started read. In both cases race joins before sending one notice. Printer prints and sends acknowledgement before next input begins. A simultaneous completed line can instead win under ordinary race semantics; that is a distinct execution, not a false promise of signal priority.

## 7. What is new, alternatives, and remaining floor

The needed library surface is now smaller: the `signals` module and native descriptors; passive `.observe`; `SignalSource<E>`; `Signal.name`; and `SignalUnavailable.message`. Existing next, timed next, Closed, CtrlC, Interrupted, channel/iterator, race, merged and protection forms do the rest. `SignalInUse`, required `.intercept`, shared policy-owning SignalListener, and signal stop/defer ceremony are removed. There is no new early-attach name: an existing timed next already demonstrates the startup case. Names remain provisional; these reviews did not cold-read them.

The added semantics are first-use owner attachment with automatic release, coalescing broadcast by owner/mode, and the selected (b) source-closure rule. The native adapter and independent closed state are necessary; a public ownership token is not. First-use operations now visibly carry unavailable failure in their stable result type. Facility loss is failure rather than normal closure. Console consumption is retained per read owner while other owners receive their notifications. No speculative whole-program analysis or hidden loop exit is introduced.

(a), watched `loop r.alive`, remains a possible generalization, not a supported program; 16 remains visibly labeled. It would need live synchronized reads, write/guard subscriptions and helper/alias rules. (c), done/race, remains the choice when ordinary work completion rather than collective wait state must decide shutdown. No review finding is rejected.

The selected usable examples have a **3 floor** for discoverability/concision or platform completeness: context-dependent view closure and first-use timing need learning; the ordered REPL has explicit message/ack plumbing; terminal/process support and Windows termination retain limits. The retained unsupported (a) demonstrator has completeness 2 and is not counted as a working selected-design example. The escaped-registration safety-2 case is removed structurally; no aliases own subscriptions. Continuing overlapping handlers remain an expressly documented policy limit with a concrete escape, not a claimed fixed liveness property. `dogfood-round4.md` supplies every sub-5 line and separates these limits from implementation validation.
