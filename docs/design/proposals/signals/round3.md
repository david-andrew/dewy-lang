# Signals as ordinary concurrent work — round 3, final recommendation

This round incorporates round2 and corrects its treatment of dependency-blocked continuation items. Earlier rounds remain unchanged. It follows David's final direction: **a parallel block closes its own signal views; iteration visibly ends; a `loop true` must explicitly handle `Closed`.** There is no invisible break and no manufactured cancellation. This is a design proposal; the programs use accepted-but-not-yet-implemented concurrency facilities and the proposed signal module.

## David's REPL, with the smallest working changes

```dewy
import p"@lib/std/signals.dewy" as signals

repl:type = [
    alive:bool = true
    run = () => {
        defer { alive = false }
        loop true {
            let line = input(">>> ") ??<Interrupted> {
                printl"KeyboardInterrupt"
                continue
            } ??<EndOfInput> break
            let text = line or_throw
            if text =? "quit" break
            printl"you said {text}"
        }
    }
]
main = () => {
    let ctrl_c = signals.ctrl_c.intercept or_throw
    defer ctrl_c.stop()
    let r = repl
    parallel {
        r.run() or_throw
        loop _ in ctrl_c or_throw { printl"KeyboardInterrupt" }
    }
}
```

A long-running program with a separate signal handler has exactly the same shape:

```dewy
parallel {
    regular_work() or_throw
    loop _ in ctrl_c or_throw { printl"Ctrl+C received" }
}
```

When work finishes, the signal iteration reaches its end, as iteration over a closed, drained channel does. This is the idiom. `programs/01_repl.dewy` and `support/repl.dewy` are the complete REPL; all remaining functions used in examples have complete scenario programs.

The manual equivalent has a visible exit:

```dewy
parallel {
    regular_work() or_throw
    loop true {
        match ctrl_c.next {
            <CtrlC> => printl"Ctrl+C received"
            <Closed> => break
            <Canceled> => Canceled or_throw
        }
    }
}
```

`(ctrl_c.next ??<Closed> break) or_throw;` is the shorter manual body prefix. `next` returns a value and drops `()`; `.stop()` returns `void` and keeps them. Every condition-style `loop` has a condition. Iterator-style `loop _ in source` is the already-existing other form.

## 1. Three distinct objects, one public handle

There are three internal identities. Their distinction is essential to sharing and predictable lifetime; users normally write only the descriptor, the handle, and its loop.

1. **Descriptor:** `signals.ctrl_c`, `signals.sigterm`, etc. This is inert. Merely importing the module or storing the descriptor neither installs interception nor observes events. A descriptor is not itself iterable. A mistaken `loop x in signals.ctrl_c` diagnoses “choose `.intercept` to handle the signal, or `.observe` to watch without changing its default.” This one acquisition line is the deliberate difference from David's notional spelling.
2. **Registration:** `let ctrl_c = signals.ctrl_c.intercept or_throw`. This owns the process-wide policy for that signal. `observe` owns only an independent passive subscription. Handles have synchronized shared identity, as channels do. Copies do not create another registration. `defer ctrl_c.stop()` gives an explicit end even if helpers keep a copy; last-handle drop is the fallback. Stop is idempotent, infallible, and nonwaiting.
3. **View:** each registration used in a particular running `parallel` block has one mailbox and one closed bit for that block. Calls through ordinary helpers use that same view. A second block gets a different mailbox and closed bit. Automatic closure affects the view, not the registration or other blocks. This context dependence is intentional and belongs to this signal-source contract, not to all iterables or channels.

There is one exclusive interception registration per native signal. Another `.intercept` returns `SignalInUse`, including from a nested helper; it never overrides, stacks, or silently shares control. Any number of observers can coexist. An observer neither consumes the controller's notification nor suppresses the default. A library can install an observer inside an ordinary helper and run it alongside the caller's work (programs 12 and 22). A library needing control should accept an app-owned handle or send an ordinary request to the app. An arbitrary library could deliberately acquire control before the app does; this API is not a module-permission system. The app acquires its policy before starting libraries whose behavior it needs to coordinate.

Two callers consuming **the same registration in the same block** share a mailbox, as channel receivers do: one consumes each notification. Two registrations, or views in two different blocks, receive independent notifications. Program 07 uses a controller and an observer to demonstrate broadcast. Program 20 uses two block views of one registration.

### Activation and the startup interval

Acquisition is the linearization point for interception. It happens before the parallel block's work starts in the idiom. Routing does not depend on whether the scheduler has reached the first `next`, or on whether the handler is currently busy.

A registration with no open views has a single coalescing, unassigned pending slot. Its first subsequently opened view atomically takes that pending notification, if any. Subsequent views begin at their own attachment and get future arrivals; there is no historic replay to a late subscriber. When there are open views, the router fans out to those views instead. If all views have closed but interception is still held, new arrivals can fill the unassigned slot for a later block. A later block may therefore receive a press from that explicitly intercepted gap. Stop discards this unassigned slot.

For two newly starting blocks, broadcast begins when each has attached; it is not retroactive. If that distinction matters, create ordinary application channels and publish readiness explicitly before allowing the external producer to act. No compiler-wide search for future registrations or speculative helper execution is required.

## 2. Exactly when a parallel block closes signal views

A `parallel` block activation owns a one-way `signals_closed` state, initially false. At a wait-registration boundary or an item-completion boundary, the runtime checks whether:

- at least one item is still unfinished; and
- every unfinished item is either parked at a signal-only wait for this block, waiting solely for structured descendant work whose entire outstanding wait frontier consists of such waits, or not yet runnable because its unresolved same-block prerequisites lead only to those waits.

An item that is ready but has not yet been scheduled is ordinary activity, not an absent item. Follow the block's existing acyclic dependency edges when deciding the condition; a pending continuation cannot keep its own prerequisite alive. In program 23, printing the final count depends on the signal iterator returning. Once the five-second work finishes, the iterator's view closes, it returns its count, and the report runs. The block's signal views remain closed while that continuation runs. A later phase needing a new signal lifetime uses a fresh nested or subsequent parallel block, or explicit coordination; it does not silently reopen this one.

If so, atomically set `signals_closed` and close all this block's existing signal views. Any view first requested in this block afterward starts closed, without taking the registration's unassigned pending slot. This includes views of a registration acquired after the state changes. No block-local reopen operation is introduced.

The unfinished items form **one cohort**, rather than keeping one another alive. Otherwise two signal listeners would each count the other as unfinished and neither would end. A block with only signal listeners closes once they all reach their waits. An empty block simply finishes. A block with no listeners behaves exactly as before.

This condition means “there is no remaining ordinary activity that these signal listeners accompany.” It does **not** mean the entire program is idle or that all OS events have ceased. A timer, a socket read, a channel receive, an external task join, or running computation is ordinary activity and sustains the block.

### Classification table

| Current operation | Signal-only? | Reason |
|---|---|---|
| `listener.next`, iterator's next step | Yes, if its view belongs to this block | The new source protocol identifies the wait. |
| `select(@a.next @b.next)` on signal views of this block | Yes | All enabled operations have the same lifetime owner. |
| `select(@a.next none)` | Yes | `none` is absent; the existing nonempty-wait obligation remains. |
| Signal `next(timeout=...)`, or all-signal `select` with a timeout | No | Its timer is another possible completion. Even `timeout=0s` is an explicit poll, not a reason to end a service. |
| `select(@signal.next @done.receive)` | No | The channel is ordinary work, even if the programmer calls it `done`. |
| `merged` with only active signal waits from this block | Yes | Its runtime active wait table supplies the classification. Closed inner channels are retired normally; a mixed merged source can become signal-only afterward. |
| Ordinary synchronous helper that eventually waits on one of the above | Same as the actual current wait | Call depth is not a task boundary. No inlining or whole-program effect inference is required. |
| A helper sleeping/saving/sending during a handler | No while that operation is pending | A handler may finish its current work. |
| An owned `race` or scoped task-group join | Yes only if every outstanding owned child frontier is signal-only for this block and there is no other completion source | Aggregate state propagates through the existing ownership tree. This never adopts an unrelated task. |
| `within(...)` with a live deadline | No | The deadline is a real ordinary completion source, including when its body waits on signals. |
| Item pending on a same-block prerequisite | Only if its entire unresolved prerequisite frontier is signal-only | Acyclic prerequisite edges, not guessed application intent; a ready-but-unscheduled item still sustains the block. |
| Wait on a task owned elsewhere | No | The block does not own its lifetime and must not infer its purpose. |
| Nested `parallel` | Its own block decides | Inner signal views are not outer signal views. The outer join remains ordinary until the inner block completes. |

A prepared operation captures its **registration**, not a view selected at `@` construction. Executing that operation selects the view of the executing structured ownership context. A `merged` consumer is bound to its context when consumption starts, like its existing iteration state; moving active iteration state between independently running blocks is not permitted. This prevents an operation prepared outside a block from accidentally bypassing block-local closure.

### Registration before readiness, and channel-like draining

Register/classify a wait before it consumes even an immediately ready notification. Otherwise a busy stream could repeatedly win without giving the block a chance to close. If the closing condition holds, close the views first, then perform the ordinary receive rules.

**Close preserves already pending notifications.** The closed mailbox gives its one pending payload, if present, and then `Closed<E>` forever. A racing native arrival is either before closure (coalesced into that pending slot) or after it (not enqueued into that view). Events are never fed into a closed view. A losing `select` still consumes nothing. This is the channel rule in LANGUAGE.md, rather than a new “close means discard” convention.

Consequently there can be one final queued handler invocation per view after ordinary work ends. A handler currently executing may also finish its already-consumed event. That is bounded backlog, not guaranteed bounded completion time. If only some signal waits commit, the other closed views can stay undrained until their consumers resume; they cannot accumulate further events.

### What code sees, and cleanup

No task receives a synthetic `Canceled`. A source iterator consumes `Closed<E>` as the end of iteration. A manual `next` returns it as a normal terminal outcome. The existing terminal-wait progress rule rejects an unchanged loop whose `Closed` arm neither leaves nor changes its wait; merely checking a flag elsewhere is insufficient. A `next or_throw` forwards `Closed` as a failure rather than silently becoming `break`.

Code after the iteration runs. Its enclosing helper returns normally. Ordinary defers run at their normal scope exits; closing the source does not unwind them early. Existing cleanup grace, explicitly protected cleanup, error reporting, and joining rules remain. A useful item result is not discarded because its signal view closed. If a handler's normal tail starts more work, that work runs; this is not an automatic return from the item.

Real parent cancellation remains `Canceled`, and ordinary item errors retain fail-fast semantics. An operation in a canceled scope checks cancellation before yielding a payload or `Closed`; a view's normal closure must not conceal concurrent cancellation. The block does not absorb unrelated cancellations. No type is narrowed based on whether an operation happens inside a parallel block.

### Mid-handler, nested blocks, helpers, and other tasks

An event handler in `sleep`, file I/O, a send, or compute is ordinary unfinished activity. The block lets it reach its next signal step and then closes as above. If it waits forever on a channel whose peer already exited, it can still hang: automatic signal closure does not solve arbitrary deadlocks. Program 04 closes its command channel when the game ends, so a blocked sender sees the ordinary send failure and leaves. Use `race` to request cancellation of an in-progress handler, or explicit channels to coordinate more elaborate lifetimes.

A plain helper inherits its caller's block; `telemetry.watch_interrupts()` in program 12 closes with the app. A helper that opens a nested `parallel` creates a new lifetime. In particular, wrapping only the handler in `parallel { loop ... }` makes that inner view close immediately; it does not borrow a distant sibling's lifetime. Put the work and listener in the same block, or pass an explicit done channel. Program 20 tests two nested sessions, each with its own work and view.

`BackgroundTasks` children belong to the program group, not whichever lexical parallel block happened to call `spawn`. They do not gain that block's closure. Program 21 explicitly stops and waits for its background watcher. A scoped task group wholly owned inside one parallel item can participate through its structured join tree; the group's independent failure and cancellation policy still applies. No task is detached or canceled merely to compute liveness.

Outside a parallel-owned computation, callers share the registration’s ordinary outside-block view, which stays open until the registration is stopped or the backend loses its event facility. Thus a server intentionally waiting only for signals uses an ordinary `loop`/`merged` at its outer lifetime. `parallel` with only signal tasks is deliberately not the spelling for that daemon. This is the largest remaining predictability cost of (b), rated 4, not hidden by a 5.

## 3. Source API and native mappings

`import p"@lib/std/signals.dewy" as signals` imports the proposed standard module.

| Descriptor | Supported native event | Payload `E` |
|---|---|---|
| `ctrl_c` | POSIX SIGINT; Windows CTRL_C_EVENT | existing `CtrlC` |
| `sigterm` | POSIX SIGTERM | `signals.Signal[name='sigterm']` |
| `sighup` | POSIX SIGHUP | `signals.Signal[name='sighup']` |
| `sigwinch` | SIGWINCH on targets providing it | `signals.Signal[name='sigwinch']` |
| `sigusr1`, `sigusr2` | POSIX SIGUSR1 / SIGUSR2 | corresponding `signals.Signal` |
| `ctrl_break` | Windows CTRL_BREAK_EVENT | `signals.Signal[name='ctrl_break']` |
| `console_close` | Windows CTRL_CLOSE_EVENT | `signals.Signal[name='console_close']` |

`Signal` is a small record whose `name` is the literal union of the seven non-Ctrl-C spellings above. No signal counts, native sender identity, terminal dimensions, or universal native signal number are promised. A resize notification means “query the current dimensions,” not “this was the size at the press.” Source-qualified matches distinguish equal `Signal` payload types (program 14); stored results can use `event.name`.

Acquisition signatures are:

- `source.intercept : SignalListener<E> | SignalInUse | SignalUnavailable | Canceled`
- `source.observe : SignalListener<E> | SignalUnavailable | Canceled`
- `listener.next : E | Closed<E> | Canceled`
- `listener.next(timeout=d)` adds `Timeout`.
- `listener.stop() : void`

These are value-returning zero-argument operations, so acquisition and `next` omit parentheses. Their callable forms still work as prepared operations. `SignalListener<E>` implements the existing iterable/Waitable protocols. `CtrlCListener`, already approved under `task`, can remain an alias for `signals.SignalListener<CtrlC>`; no second listener model is introduced. Existing generated `.CtrlC`, `.Signal`, `.Closed`, and `.types` need no new pattern syntax.

Acquisition checks cancellation and succeeds atomically or installs nothing. `SignalUnavailable` carries `message:string` describing an unsupported target, missing console facility, or native registration failure. Export the descriptors uniformly; a target that cannot deliver an event returns this error. Do not invent SIGTERM as an alias for Windows close, or SIGWINCH as a Windows keyboard-buffer event. `SignalInUse` is an ordinary error. Heap/admission resource failures follow existing policy rather than a new signal-specific exception scheme. If a previously functioning event facility disappears, its views close after buffered data; recreating the facility requires a fresh acquisition.

With no interceptor, preserve native defaults for SIGTERM/SIGHUP/SIGUSR1/2 and SIGWINCH. A passive observer cannot keep a process alive against those defaults; delivery is best-effort. Windows Ctrl-Break retains the host's normal control-event termination unless intercepted. This round does not introduce a new portable exit code for it. Ctrl-C has Dewy's specified cooperative default below.

The raw native handler performs bounded, allocation-free notification and emergency-counter work; it never calls Dewy user code. The scheduler routes events and executes user handlers later. Observation does not promise execution before an immediately fatal native default action. POSIX standard signals may coalesce before user space sees them, so these are notifications, not key logs. Tokio's own signal documentation describes the same underlying coalescing limitation: [Signal](https://docs.rs/tokio/latest/tokio/signal/unix/struct.Signal.html).

## 4. Ctrl-C, console reads, and foreground children

Without a live interceptor, the first Ctrl-C requests root cancellation, prints the stopping notice, and an unhandled Ctrl-C-derived cancellation exits 130. V5's next press on that default shutdown path forces exit 130 with cleanup skipped. With an interceptor, presses become events instead of root cancellation, throughout its registration lifetime, including busy handlers and gaps between blocks. Observers do not change either rule. Releasing interception restores the default for **future** presses; already handled or queued presses do not retroactively cancel the root.

Three separately runtime-observed Ctrl-C arrivals within a rolling one-second window force exit 130 independently of tasks, interception, console reading, or protection. Count before mailbox coalescing. An OS that coalesces three physical presses before delivering them cannot give the runtime three arrivals; no stronger guarantee is claimed. A registered controller does not mask deadlines, sibling failure, `.stop()`, or any already-pending root cancellation.

When there is an interceptor and the foreground terminal line reader is active **at the arrival**, that read consumes the control delivery: discard its partial line and return `Interrupted`. The controller's signal views do not also receive that arrival. Passive observers receive it. Without an interceptor the read observes root `Canceled`. A queued signal from before the read began is not converted into an interruption of the next prompt. Nonterminal stdin reads remain ordinary I/O; interception does not magically clear a pipe. Concurrent reads of one terminal must use the existing console's exclusive read ownership, not compete for a press.

`input`, numeric input functions, `read_line`, and stdin-line failure aliases retain v5's stable `Interrupted` alternative everywhere. `input` has `EndOfInput`, while `read_line` has `none` at EOF. Only actual terminal line editing uses the rule above; an unrelated EINTR is retried/handled by the I/O adapter rather than manufactured into `KeyboardInterrupt`. The REPL prints its read-interruption message before re-entering input, so there is no asynchronous handler-print versus reprompt race for that press.

David's `alive` field can remain useful after `run` but is not a live cross-task signal by virtue of being a record field. There is no `run()`-starts-a-task constructor rule in the record guide. Explicit construction followed by explicit `run` avoids both blocked construction and conflicting sibling reads of a record being mutated. A shared live guard is the deferred (a) design, not smuggled into this one.

A terminal sends SIGINT to its foreground process group. Interception in the parent does not prevent the child receiving it, and the parent must not forward the same press again. Program 05's child shares that group and standard streams; `run` owns/reaps it. `child.wait` by itself would not transfer ownership of a manually spawned child. Full job control also requires process groups and terminal handoff; no existing spelling was found for those operations, so a full job-control shell is a scope floor, not claimed capability. Nor does this API promise to receive presses when the parent is outside the terminal's foreground group. The guide's existing raw/process APIs remain distinct.

## 5. Cancellation, saves, task groups, and termination

Program 02 uses `race` outside parallel to cancel and join the search on a Ctrl-C event. Its parent is still live, so `within` would suffice for a save deadline; it uses the existing protected form to tolerate an independent concurrent parent stop as well. Program 13 has no interceptor, catches actual root cancellation, and needs protection. Saving takes a snapshot under a mutex, releases it before I/O, writes/syncs a temporary file, and publishes it using the already-proposed durable-path `replace`/`sync` methods. Those methods remain a separate implementation dependency. This round does not invent durability primitives.

`task.protect_from_cancel(5s @save(best))` is an ordinary function-handle call. It runs once despite a pending parent cancel, masks that cancel for its owned work, imposes its own cooperative deadline, and restores the pending parent afterward. Its own cancellation deadline maps to `Timeout`; unrelated `Canceled` or save errors remain. The caller reports save failure and then preserves the original `Canceled`, or explicitly exits 130 for an intercepted Ctrl-C. An event is not itself a root cancellation: returning a freshly invented `Canceled` is not the way to manufacture signal exit provenance.

No protected call gains nonlocal `return`/`break`; they belong in the caller's normal match after the call, or inside the called function with ordinary local meaning. No callback-specific or inline scope syntax is introduced. A nested protection cannot extend an outer protection budget. Existing explicit protected cleanup may replace the ordinary cleanup grace as v5 specified. Deadlines and joins remain cooperative, and neither force-exit nor OS kill guarantees a saved file.

Most groups use ordinary `parallel`, and this round removes the special form entirely for persistent signal listeners. Dynamic spawning may retain ordinary `task.tasks(@body)` and `Tasks<E>`: local function return, success joins, failure stops/joins, child failure is fail-fast, `none` is success, useful results retained. Outside the selected parallel rule, a callback's successful early return does not magically stop its persistent children; stop them explicitly or put finite work and its listeners in `parallel`. Program 09 shows an ordinary helper's early return finishing a block item. Program 21 shows explicit background task stop and expected cancellation handling, followed by a check for caller cancellation.

Program 03 is a sequential bounded echo server: a race on SIGTERM cancels the accept loop, but an already accepted request runs under its own five-second protection and closes its socket before the loser joins. The parent then writes a bounded final count and returns normally. This is graceful draining of one request; it is not a concurrent request-pool API. Importantly, it does not race a bare accepted socket result against a signal and then lose the socket on a tie, as round1 did.

Program 11 handles Windows close by racing work with a close notification and attempting a bounded save. The runtime native control callback stays outstanding while the interceptor owns that close attempt; releasing it allows the callback to return. Windows may terminate the process earlier under its host-controlled timeout, and a closing console cannot be relied on for logging. An observer alone does not defer that native default. No cancellation value or listener keeps the window open. This limitation follows the platform, not a missing Dewy loop feature: [HandlerRoutine](https://learn.microsoft.com/en-us/windows/console/handlerroutine).

## 6. Cost and implementation boundary

There is no new parser form and no compiler search for guard reads. A signal registration supplies runtime wait-kind and owner metadata. Each signal-using block maintains unfinished-item and ordinary-activity counts. The first use can initialize this lazily with one walk of its existing item/dependency state; subsequent ready/park/complete transitions update counters. A dependency-blocked item is not independently runnable; its existing prerequisite counters determine when it becomes ready. Owned joins propagate aggregate state through the structured ownership tree. There is no global task scan at each signal, no polling timer, and no analysis of arbitrary helper bodies.

For `n` owned items and `e` existing dependency edges, `v` views, `s` enabled operations in a select, and ownership depth `d`: initial indexing is O(n + e), local wait-state changes are O(1) plus O(d) owned-join propagation when needed, and dependency completion processes its existing outgoing edges. If the implementation chooses cached frontier propagation instead of runnable counts, charge every affected edge as well: no constant-time claim covers arbitrary DAG fan-out. Select classification is O(s) alongside existing registration, and one closure pass is O(v). Routing a notification is O(number of open views for that registration); memory is O(items + dependency edges + registrations + views + enabled waits). Each view holds at most one payload. The raw OS handler does not pay the fan-out cost. Work without signal operations does not allocate view state.

These are algorithmic bounds, not measured performance claims. A future implementation must show cost on the flagship instruction-count panel before landing. A compiler/runtime warning is appropriate if a chosen backend cannot provide this without material overhead; no speculative “zero cost” claim justifies accepting it. Source-qualified arm checking remains select-v6-round11's indexed demand-driven analysis; this proposal adds no helper provenance inference.

## 7. Alternatives, additions, and differences from existing decisions

**(a), possible later generalization.** Program 16 explores `loop r.alive` with a watched guard. Track statically known reads, synchronize guard evaluation against sibling writes, register versions before parking and recheck to avoid a lost wake. When false, close a loop-owned signal view so a visible `Closed` arm leaves; do not inject a hidden break or forge `Canceled`. Direct stable fields are plausible. Getters, aliases, copied records, mutable helper captures, and waits through helpers require a broader shared-place/reactive-loop contract. Runtime cost includes subscriptions, write barriers, and guard reevaluation on each relevant write; demand-driven indexed analysis can limit the compile cost. David's “compiler can work harder” principle supports investigating this, rather than dismissing it for implementation effort. It is unnecessary for (b) and is not recommended for this round.

**(c), retained explicit policies.** Program 18's `race` cancels mid-handler. Program 19's done-channel `select(priority='index')` makes completion explicit and prioritizes it over a ready signal. Its mixed wait deliberately prevents automatic signal-only closure. These require more code but make lifetime independent of which kind of source is awaited.

**New library surface:** source descriptors, `.intercept`, `.observe`, `SignalListener<E>`, `Signal` with `.name`, `SignalInUse`, and `SignalUnavailable.message`. See `names.txt`, containing every new public spelling as a usage. No cold read has been conducted by this sub-agent; do not call these names approved. `Interrupted`, `CtrlC`, `Closed`, `next`, `stop`, `Waitable`, `within`, `race`, `merged`, `protect_from_cancel`, and task-group names come from existing designs.

**New semantics:** block-owned signal views and automatic terminal closure at signal quiescence. Existing plain `parallel` would wait forever; `race` or a done channel already express alternatives, but David selected the iterator form. Ordinary channels retain their current explicit-close rule. This is not described as a library-name-only change.

**V5 / scope-block changes:** remove `catch_ctrl_c` callback/inline scopes, their foreground-task requirement and nested innermost-catcher stack. Replace them with explicit exclusive interception and passive observation. Retain stable console `Interrupted`, console consumption rather than double control delivery, coalescing, root default cancellation/exit 130, force-exit escape, child process behavior, cancellation checkpoints, and bounded protection. Keep ordinary calls for dynamic task grouping and protected work; no `scope` parameter or altered `return` semantics. RAII-only interception had been rejected in v5; this proposal deliberately revisits resource ownership with an explicit `defer stop()` lifetime because it supports ordinary concurrent iteration. That trade is reported, not treated as already accepted.

**V6 / batches 3–8 unchanged:** type-matched select arms and source qualification, `priority='fair'|'index'`, loser commit discipline, genuine `Canceled`, cancellation forwarding, prefix metatags, record value semantics, `main` injection rules, and useful-result handling. Compiler-only lifecycle hooks are not new user syntax. `defer` remains the already-selected cleanup mechanism pending the separate cleanup design.

Rejected: wait-only interception (busy-handler gaps), global closure (breaks shared blocks), silent cancellation/loop breaking (David rejected it), competing policy override (library hijack), infinite press queues, exact key counts, secretly reactive ordinary record reads, and adding a callback/block form just for signals. No source with an impossible event is allowed to pretend it installed successfully.

## Validation and remaining floors

The 23 scenario programs plus three local support modules cover every brief case and all three alternatives. Program 16 is explicitly unselected and requires (a); the others target this proposal, not today's executable language. `dogfood.md` records line-specific scores and the comparison basis against Python, Go, Rust/Tokio, TypeScript/Node, and Swift/Dispatch. Earlier sources are preserved in `programs-r1/` and `programs-r2/`. Round 3 adds program 23 after finding that round2 counted an iterator-dependent report as ordinary unfinished work and could thereby prevent closure.

The remaining floor is **3 for complete cross-platform operation**, chiefly Windows close's externally imposed lifetime and the absence of full shell job-control operations. Within the requested ordinary signal-handling model the ergonomic floor is **4**: per-block closure/alias lifetime, different console-versus-event delivery paths, and cooperative cleanup bounds need explanation. Names also remain provisional until cold reads. No executable Dewy test or independent review is claimed; the language features under design are not implemented. The abstract-state checks validate only the proposed closure bookkeeping, not a runtime.
