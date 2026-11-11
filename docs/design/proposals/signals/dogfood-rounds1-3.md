# Dogfood and iteration

Final design: `round3.md`. The brief's 12 required scenarios are programs 01–12; 13–23 test retained protection, remaining native signals, all three lifetime approaches, sharing, and library/default behavior. Local support modules contain actual function bodies, not unspecified `work()` or `save()` placeholders.

## Method and honesty boundary

These are paper programs against the proposed language design, not successful executions in today's compiler. I checked control flow, ownership, failure alternatives, task lifetime, source qualification, and consistency with decisions batches 3–8. I did not build the read-only checkout, run these OS signals, benchmark the proposed runtime, or obtain independent/cold readers. The source names are candidates. An executable abstract model checks the proposed closure bookkeeping separately; it does not validate a compiler or the native adapters.

Scores are **O**bvious, **D**iscoverable, **C**oncise, **S**afe by default, **F**ully complete for the stated scenario, each 1–5. A 5 means the code meets that criterion without a material unexplained trade relative to the practical alternatives below. A 4 means a real rule/resource/lifetime fact must be learned; a 3 means substantial platform or scope limits remain. This is a comparative design judgment, not measured user research. Unselected (a), program 16, is judged against its stated hypothetical extension and explicitly does not run under the selected semantics.

Every score below 5 in the final table has a specific source location and reason in the next section. Peer implementations were not written, so no invented line numbers or numerical “test results” for them are supplied. The five-language comparison identifies the corresponding idiom and cost for **every** scenario. A shorter peer program does not automatically have a higher safety/completeness score.

## First round and fixes

The first-round sources are preserved in `programs-r1/`; round1 is unchanged. The initial self-review found fixable issues rather than assigning blanket 5s:

| First-round location | Initial grade affected | Finding | Round-2 action |
|---|---|---|---|
| `programs-r1/03_server_sigterm.dewy:18` | S2, F3 | Racing a bare accept result against a signal did not establish who closes an accepted socket on a losing/tied result. | Replaced it with an owned accept loop: each peer has a defer, accepted request work is bounded/protected, and the race joins that owner. Final 03:13–25 and :33. |
| `programs-r1/support/search.dewy:23` | S3, F3 | A timed-out write directly to the final file could destroy the previous checkpoint. | Write/sync temporary, atomic replace, then directory sync using existing provisional durable-path members; final support/search:24–28. |
| `programs-r1/11_windows_close.dewy:25` | S3 | Propagating an ordinary save error invokes the normal reporting path, whose console may be gone. | Exit nonzero without using the closing console; final 11:25. No guarantee of durable external error reporting is claimed. |
| `programs-r1/07_two_listeners.dewy:8` | O4, F4 | Regression case for round1’s already-stated cohort rule: a literal “every other item finished” implementation would let two listeners keep each other alive. | Retain collective closure and check it in the abstract model; this was a validation target, not a newly discovered textual fix. |
| `programs-r1/08_busy_handler.dewy:6` | O3, F3 | Queue-versus-close precedence was unsettled. A ready stream could keep being consumed before idle detection. | Register/classify before commit; close once, preserve one pending notification, drain then Closed. |
| `programs-r1/20_shared_source_nested_blocks.dewy:6` | S4, F3 | Round1 already specified separate block views but did not settle prepared-handle binding or delivery before either view attached. | Preserve per-block isolation; specify execution-context binding, initial pending transfer, and no retroactive broadcast. |
| `programs-r1/21_external_task_lifetime.dewy:9` | O3, F3 | Lexical nesting could accidentally enroll app-owned tasks in a short block. | Task ownership, not lexical call location, chooses the view context. |

The round-2 review then found one more fixable issue: a pending report depending on the signal handler’s final count could sustain that same handler forever. Round 3 follows the existing same-block prerequisite DAG rather than treating blocked continuations as independent work, adds program 23, and corrects the runtime-cost bound to account for dependency edges. `programs-r2/` preserves the prior sources. After that third round, the remaining sub-5s are listed tradeoffs, untested names, or externally imposed limits. Making them all 5 would require changing David's selected lifetime policy, claiming guarantees the OS does not provide, or expanding into general job control/reactive guards/console APIs. Those are not silent fixes within this round.

## Final scores

| Program | O | D | C | S | F |
|---|---:|---:|---:|---:|---:|
| 01 REPL | 4 | 4 | 4 | 5 | 4 |
| 02 search, event then save | 4 | 4 | 4 | 4 | 4 |
| 03 SIGTERM graceful server | 4 | 4 | 4 | 4 | 4 |
| 04 game pause/quit | 4 | 4 | 4 | 5 | 4 |
| 05 shell with foreground child | 4 | 4 | 5 | 4 | 3 |
| 06 terminal resize | 4 | 4 | 4 | 5 | 3 |
| 07 two listeners | 4 | 4 | 5 | 4 | 4 |
| 08 busy handler | 4 | 4 | 5 | 4 | 4 |
| 09 task group ends early | 4 | 4 | 5 | 5 | 5 |
| 10 default CLI | 5 | 5 | 5 | 5 | 5 |
| 11 Windows close | 4 | 4 | 4 | 4 | 3 |
| 12 library observer with app policy | 4 | 4 | 5 | 5 | 4 |
| 13 default cancellation then save | 4 | 4 | 4 | 4 | 4 |
| 14 HUP/USR1/USR2 controls | 4 | 4 | 4 | 5 | 4 |
| 15 Windows Ctrl-Break | 4 | 4 | 5 | 5 | 4 |
| 16 watched condition, unselected | 4 | 3 | 4 | 3 | 3 |
| 17 manual next, selected | 5 | 4 | 4 | 5 | 5 |
| 18 explicit race baseline | 4 | 4 | 4 | 4 | 5 |
| 19 explicit done channel baseline | 5 | 4 | 3 | 5 | 5 |
| 20 shared source/nested blocks | 4 | 4 | 5 | 4 | 4 |
| 21 externally owned task | 4 | 4 | 4 | 4 | 5 |
| 22 passive observer, default intact | 4 | 4 | 5 | 4 | 4 |
| 23 dependent final report | 4 | 4 | 5 | 5 | 4 |

## Every final score below 5

All `NN:line` references below mean the corresponding final `programs/NN_*.dewy`; `support/...` references mean `programs/support/...`. A score applying to more than one criterion explicitly lists each criterion.

- **01 — O4/F4 at 01:10 and support/repl:7:** active console input consumes the control delivery, so the input code prints the interruption while the parallel handler covers other moments. The split is necessary to preserve v5's no-double-delivery rule and ordered reprompting. **D4 at 01:5:** `intercept`/`observe` are new, untested names. **C4 at 01:5–6 and support/repl:7–11:** Python's single `except KeyboardInterrupt` around a prompt loop is shorter. Dropping the acquisition or conflating EOF/errors would hide policy.
- **02 — O4/D4 at 02:17:** a signal result wins a race and stops/joins the search; an event is not root cancellation. **C4 at 02:6–11:** explicitly reporting timeout, cancellation, and file failure is more verbose than a broad catch. **S4/F4 at 02:6 and support/search:25–28:** protection is cooperative and disk durability still has failure paths; durable-path members are a separately proposed dependency, not implemented here.
- **03 — O4/D4 at 03:17 and :33:** canceling the accept loop still allows its currently accepted request to finish under a separate protection budget. **C4 at 03:11–25:** resource ownership and drain/error policy take an explicit helper. **S4/F4 at 03:17:** a noncooperating handler or OS kill can overrun/defeat the deadline. Sequential one-request service is intentional, not a claim to implement a scalable server.
- **04 — O4/D4 at 04:24–31:** a signal handler that blocks sending is ordinary work, so the game must close its channel on exit (04:4). **C4 at 04:25–31:** explicit send-failure handling is extra plumbing relative to a direct event callback. **F4 at 04:10:** this is a terminal simulation, not permission to block a graphical update/draw callback; game callbacks keep their established restrictions.
- **05 — O4 at 05:24–26:** the parent receives its notification while the OS independently signals the child. **D4 at 05:6 and :13:** input interruption and child waiting are distinct paths. **S4 at 05:13:** a full terminal job arrangement is not established by `run`. **F3 at 05:1–2 and :13:** this is a small same-foreground-group shell; no process-group handoff, background jobs, or interactive job suspension is claimed. Adding those requires a separate process API, not a signal-loop tweak.
- **06 — O4/D4 at 06:11 and :16:** SIGWINCH says to query current state; it does not carry a historical size. **C4 at 06:16–18:** using an existing subprocess for the query is more verbose than a native console-size accessor. **F3 at 06:2 and :16:** requires a Linux terminal and `/usr/bin/stty`; this round does not invent a terminal-dimension API or pretend SIGWINCH exists on Windows.
- **07 — O4/D4 at 07:4–7 and :10–11:** separate registrations broadcast, copied handles in one block compete, and the cohort closes together. **S4 at 07:5:** explicit stop is what bounds policy if a library retains a copy. **F4 at 07:10:** late attachment does not replay earlier events and native coalescing loses counts. Exact lossless key delivery is not an OS-signal guarantee.
- **08 — O4/D4 at 08:6 and :9:** after work ends, a busy handler finishes and may process its one buffered notification before Closed. **S4/F4 at 08:1–2 and :9:** notification coalescing and emergency force-exit mean this is not an exact counter or guaranteed-completion handler. Replacing it with an infinite log would add unbounded resource consumption without fixing native coalescing.
- **09 — O4 at 09:16–18:** a helper's early return ends work; its sibling's iterator ends by block-local source closure. **D4 at 09:14:** ownership acquisition is a new library operation. The program's actual finite status-check scenario otherwise needs no extra capability.
- **11 — O4/D4 at 11:15–18:** interception of close means a cleanup opportunity, not control over whether Windows closes the console. **C4 at 11:21–26:** outcomes need explicit handling without console output. **S4/F3 at 11:21:** the OS deadline can beat the two-second request, and the final file can be incomplete; no reliable save/error-log guarantee is possible during arbitrary process termination. A production editor also checkpoints while running; that is outside this signal-delivery sample.
- **12 — O4/D4 at 12:10 and support/telemetry:4–6:** a synchronous helper's source view uses the caller's block, whereas a spawned app-owned helper would not. **F4 at support/telemetry:4:** observation begins on acquisition, so telemetry cannot report earlier presses. The app's controller still handles them; this is a diagnostic limitation, not policy theft.
- **13 — O4/D4 at 13:9 and :17:** catching a `Canceled` value does not clear the task's cancellation; protection temporarily masks it and the caller must preserve the original reason. **C4 at 13:9–17:** more explicit than a broad `finally`. **S4/F4 at 13:9 and support/search:25–28:** deadline cooperation, durability failure, and the separately proposed file primitives remain the same limits as program 02.
- **14 — O4/D4 at 14:7–14:** source-qualified arms, not the shared payload type, select actions; Closed ends the loop. **C4 at 14:19–24:** three acquisitions need three bounded resource lifetimes. **F4 at 14:19–23:** POSIX-only signals fail explicitly on unsupported targets; the sample is a control plane, not a cross-platform service manager.
- **15 — O4/D4 at 15:4 and :8:** Ctrl-Break is distinct from Ctrl-C and its payload is the general Signal record. **F4 at 15:1 and :4:** Windows console support is required; acquisition elsewhere fails instead of hanging. Nothing here claims that a literal break key event is portable.
- **16 — O4/C4 at 16:12–16:** the apparently simple condition still needs explicit Closed handling in the proposed visible-wakeup variant. **D3/S3/F3 at 16:3 and :12:** this unselected extension must establish live synchronized reads of `r.alive`, dependency versions and helper/alias rules that ordinary record semantics do not supply. Its missing generalization is deliberately not smuggled into (b).
- **17 — D4 at 17:4 and :11:** the user must know this source can close when the block's work ends. **C4 at 17:8–13:** the explicit three-arm match is longer than iteration; it is also exactly the requested visible manual control flow.
- **18 — O4/D4/S4 at 18:12:** race cancellation may interrupt a handler mid-body; cleanup must be cancellation-safe. **C4 at 18:5–8:** helper boundaries and handles are more code than the selected inline parallel items. This is a different useful policy, not an inferior implementation of (b).
- **19 — D4 at 19:12:** argument order matters only with the written `priority='index'`. **C3 at 19:7 and :10–17:** a channel, close/defer, and four source-qualified outcomes are real overhead for a simple REPL. Removing them yields the selected form, but then this would no longer be an explicit baseline.
- **20 — O4/D4 at 20:4–6:** each nested block closes its own view; a helper which introduced a signal-only inner block would end immediately. **S4 at 20:12:** a retained handle can extend interception without the explicit stop. **F4 at 20:6:** each view sees only events since attachment, except the registration's initial unassigned pending slot; broadcast is not retroactive.
- **21 — O4/D4 at 21:9 and :14–15:** ownership, not lexical proximity, controls the background watcher's lifetime. **C4 at 21:14–15:** manual stop/wait/check is necessary for an app-owned task. **S4 at 21:15:** blindly swallowing all `Canceled` would also hide cancellation of the caller; the explicit checkpoint is essential.
- **22 — O4/D4 at 22:5 and support/telemetry:4:** observation does not disable default root cancellation. **S4/F4 at support/telemetry:6:** the observer may be canceled before logging; this deliberately does not promise guaranteed final telemetry by hijacking process shutdown.

- **23 — O4/D4 at 23:13–14:** the pending report is downstream of the signal iterator, so it cannot independently keep that iterator open. The existing dependency graph supplies this information. **F4 at 23:14:** the block’s views stay closed while the report or a more elaborate dependent continuation runs; a genuinely new event-processing phase needs a new block or explicit lifetime coordination.

## Comparison against five languages

Comparison basis, checked in primary documentation:

- **Python:** `signal` exposes process handlers and default `KeyboardInterrupt`; handlers execute on the main interpreter thread. The REPL has a very concise synchronous exception idiom, but a general concurrent event loop needs adaptation. [signal](https://docs.python.org/3/library/signal.html). Structured task groups and cancellation shielding are separate asyncio facilities; shielding a child does not by itself make a canceled caller await it successfully. [asyncio tasks](https://docs.python.org/3/library/asyncio-task.html).
- **Go:** `os/signal.Notify` delivers on channels and needs buffering for a nonready receiver; `Stop` undoes registration. This is the closest event-source comparison. Multiple notified channels are supported, but channel buffering, cancellation and goroutine joining remain explicit application work. [os/signal](https://pkg.go.dev/os/signal).
- **Rust:** the comparison uses Tokio rather than claiming Rust's standard library offers an async signal stream. Its signal stream coalesces; first registration changes process disposition and dropping the stream does not restore the original default. [Tokio Signal](https://docs.rs/tokio/latest/tokio/signal/unix/struct.Signal.html). Dewy's explicit restoration is a meaningful policy difference.
- **TypeScript:** Node is the execution host in this comparison, not TypeScript's type checker. Signal callbacks remove defaults for some signals and Windows behavior differs; event callbacks are concise but promise races do not themselves join/cancel arbitrary work. [Node process signals](https://nodejs.org/api/process.html#signal-events).
- **Swift:** Dispatch provides a source monitoring a Unix signal, with installed handlers and explicit activation. Bridging that source to async iteration/cancellation is additional code. This does not claim a single native Swift API covers Windows console close. [Dispatch signal source](https://developer.apple.com/documentation/dispatch/dispatchsource/makesignalsource(signal:queue:).md).

The following cells identify the realistic alternative for each scenario. These are qualitative API comparisons, not independently compiled peer programs. “Adapter” means application code is required rather than asserting an absent capability is impossible.

| Program | Python | Go | Rust/Tokio | TypeScript/Node | Swift/Dispatch |
|---|---|---|---|---|---|
| 01 REPL | Short `KeyboardInterrupt` prompt loop | Signal channel plus console reader | Signal stream plus line editor | Readline events plus process policy | Dispatch source plus input adapter |
| 02 event/save | Event + task cancel + protected save | Notify + cancel + wait + save | Select + cooperative task exit + save | Callback + AbortController + await cleanup | Signal source + Task cancel + join |
| 03 server | Async stop accepting; bound drain | Context/Notify; explicit graceful server stop | Select + connection ownership + drain | Signal callback + close/drain APIs | Source handler + structured request tasks |
| 04 game | Main-loop events/queue | Signal channel into game loop | Stream/command channel into loop | Callback posts game command | Dispatch handler posts actor command |
| 05 shell | subprocess plus POSIX job-control calls | os/exec plus process attributes | process plus platform job-control support | child_process plus platform restrictions | Process plus native terminal operations |
| 06 resize | SIGWINCH + terminal-size query | Notify + platform terminal query | Signal stream + terminal crate | SIGWINCH/TTY dimensions | Dispatch + terminal query |
| 07 two listeners | Fan-out from one handler | Multiple Notify channels | Multiple stream subscribers | Multiple event listeners | Multiple sources/explicit fan-out |
| 08 busy handler | Explicit pending/coalescing policy | Capacity-one channel, drops when full | Documented coalescing stream | Event-loop callbacks; backlog policy | Dispatch-coalesced notifications |
| 09 early group | Cancel/gather or TaskGroup coordination | Done channel + wait group | Select/task ownership cleanup | Abort plus await all owned jobs | TaskGroup cancellation and joining |
| 10 default CLI | Default KeyboardInterrupt | Default process signal action | Default process signal action | Host default signal action | Host default signal action |
| 11 Windows close | Native console adapter needed | Notify close opportunity; OS still terminates | Windows-specific signal adapter | Host event with eventual forced termination | Windows native adapter, not Unix Dispatch |
| 12 library observer | Library cooperates with app dispatcher | Notify affects process disposition | Registration retains changed disposition | Listener affects host default behavior | Source/disposition cooperation needed |
| 13 default/save | finally/shield with cancellation care | Shutdown context plus independent save context | Cooperative cancel then independent deadline | Abort handling plus separate save policy | Canceled Task needs independent cleanup policy |
| 14 HUP/USR controls | Separate signal handlers | One/many signal channels | Separate streams or selected sources | Name-based event callbacks | One/many dispatch sources |
| 15 Ctrl-Break | Windows SIGBREAK facilities | Control-C/Break normalized as Interrupt | Windows-specific stream | Host SIGBREAK event | Native Windows adapter |
| 16 guard wake | Condition/event synchronization | Done channel or atomic plus wake channel | watch channel plus select | Observable/event callback subscription | Actor/continuation or async stream |
| 17 manual next | Queue iterator with sentinel | Channel receive with `ok` | Stream end through Option | Iterator `.done` / callback removal | AsyncSequence end through adapter |
| 18 race baseline | wait FIRST_COMPLETED then cancel/gather | select then cancel/wait | select; distinguish futures from spawned jobs | Promise.race plus explicit abort/join | TaskGroup first result, cancel/join |
| 19 done baseline | Event + wait/cancel coordination | Native channel select | select over done and signal | Event/Promise coordination | Async stream/task-group adapter |
| 20 nested/shared | Separate queues/lifetimes | Separate channels and Stop registrations | Separate streams, explicit lifetimes | Listener add/remove per owner | Separate sources/cancel per owner |
| 21 external task | Keep task ref; cancel and await | Keep cancel/wait handles | Keep JoinHandle/cancellation token | Keep job/abort handle; await | Keep Task handle; cancel and await |
| 22 passive/default | Chain/recreate default policy explicitly | Notify changes default; app must cooperate | Stream changes disposition; no passive default | Ordinary listener changes default | Disposition must be coordinated separately |
| 23 dependent report | End stream, await result, report | Close/done then read final result | End stream, await task, report | Remove listener, resolve final value | End AsyncStream, await task result |

The selected iterator removes done-channel plumbing relative to the five peer event-source adaptations. It does not make signal lifetime universally more obvious: per-block view closure is a Dewy-specific rule, so O/D remain 4 where that rule matters. Python retains the shorter basic REPL spelling. Existing channel/select idioms remain especially direct in Go; this proposal should not claim exclusive ownership of “signals as events.”

## Checks and final floor

`python3 closure_model.py` passed **24 startup-order permutations and eight protocol scenario groups**: collective close, busy-handler deferral, buffered drain, cancellation priority, independent block views, closed-block late attachment, structured-versus-external wait classification, and dependency-blocked versus ready continuations. This small model asserts intended abstract transitions; it does not simulate OS delivery, a scheduler, closure capture typing, or native timing.

Static inspection found no remaining anonymous `work`/`save` placeholders in the 23 programs, no `.jo` imports, no new `inline` syntax, no conditionless `loop {}`, and no source-qualified match on a stored result. Program 16 is the sole intentionally unsupported alternative. The library module and compiler implementation are absent, so an actual compile/run pass would be misleading; no such success is claimed.

**Final floors: 4 for the selected model's ergonomics; 3 for full platform coverage and externally constrained cleanup.** Program 16 also honestly has 3s because the unselected reactive extension needs more design. Existing baseline program 19 has concision 3 by construction. These floors are stated rather than iterated into false 5s. Names require fresh cold readers outside this sub-agent before any decision item claims they were tested.
