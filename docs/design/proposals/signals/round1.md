# Signals as ordinary concurrent work — round 1

This is a language/library proposal, not an implementation claim. The accepted concurrency design takes precedence over implementation-era passages in LANGUAGE.md. David's latest direction is (b), with **visible source closure**, not invisible cancellation of an infinite loop. All files in this round are confined to this scratch directory.

## Start with the REPL

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
        loop press in ctrl_c or_throw { printl"KeyboardInterrupt" }
    }
}
```

The signal iteration ends when the REPL finishes. It does not need to read `r.alive`. The same rule gives the ordinary parallel example:

```dewy
parallel {
    regular_work() or_throw
    loop press in ctrl_c or_throw { printl"Ctrl+C received" }
}
```

`ctrl_c` was acquired before entering the block, as above. `regular_work` is any ordinary finite workload; complete programs are in `programs/`.

The two `KeyboardInterrupt` sites are deliberate: an active terminal read consumes a Ctrl-C as `Interrupted`, clears the partial line, and the REPL prints before prompting again. Otherwise the control listener gets it. One press does not reach both control paths. Passive observers still see a notification.

## Rules proposed in this round

1. `signals` is an ordinary module, imported from `@lib/std/signals.dewy`. Its members are inert source descriptors. Holding a descriptor changes nothing. `source.intercept` acquires control of that signal's normal disposition; `source.observe` creates a passive subscription. Both return handles, not callbacks. Both are fallible. A second controller for the same signal gives `SignalInUse` without replacing the first.
2. An interception remains active until `.stop()` or the last shared handle is dropped. Use `defer source.stop()` next to acquisition to make the lifetime explicit even when helpers retain copies. `.stop()` is idempotent and closes all views of that registration. It does not stop another registration. No special foreground-task restriction or new entry-point injection is needed; exclusive acquisition settles competing controllers. This is ownership coordination, not a sandbox against hostile libraries.
3. Every active `parallel` block has its own view of each registration used inside it. Ordinary helpers use the caller's view. Copies share that view within one block. A second block gets its own queue and its own closed state. A source used outside `parallel` has a normal explicitly owned view, with no automatic completion.
4. When every unfinished item in a block is waiting only for that block's signal views, close those views together. Already finished items do not sustain the block. This is a terminal signal-view state, **not** completion of the block itself. The woken items run their normal control flow and cleanup, and the block joins them normally. A block containing only signal listeners consequently closes immediately on reaching that state; a standalone signal service uses a plain loop, `select`, or `merged` outside `parallel`.
5. Signal-only means a `next` on a signal view or a `select` whose enabled waits are all such views. A timer, timeout, channel, external task wait, I/O wait, or runnable computation prevents this state. `none` select arguments are absent. Ordinary helpers do not obscure the current wait. Nested parallel blocks own independent views and apply the rule themselves. The precise treatment of other structured joins needs the program review below.
6. A view closes with `Closed<E>`, just like a channel, not `Canceled`. `loop press in source or_throw { ... }` consumes this terminal outcome as iteration ending. `loop true` does not stop on its own: `match source.next { <Closed> => break ... }` is necessary. A failure propagating via `or_throw` and genuine parent cancellation retain their existing meaning. Closing a view neither cancels its task nor closes another block's view.
7. A handler already processing an event finishes its current work. Once it asks for another event, the block may close its view instead. Ordinary blocking inside a handler can prolong the block. Use `race` when the requested policy is to cancel that work rather than finish it.
8. A source is a coalescing notification, not a count of key presses. Each open view holds at most one pending notification. A further arrival while one is pending merges with it. A successful `next` consumes one; a losing select consumes nothing. Already queued notifications and simultaneous closure need an explicit precedence in the next review.
9. Without a controller, Ctrl-C requests root cancellation and an unhandled Ctrl-C cancellation exits 130. Holding only observers does not change that. With a controller it supplies events instead, including while a handler is busy. Existing unrelated cancellation remains effective. Three runtime-observed Ctrl-C arrivals within one second force exit 130, even with interception or protection. Retain v5's second-press emergency exit on the default cancellation path.
10. No user function runs in the native OS signal handler. That handler records/wakes; Dewy handlers are normal scheduled work and can use ordinary I/O, channels, and structured tasks.

## Sources and results

The descriptor names are provisional and have not been cold-read in this sub-agent. They are exported consistently even on an unsupported target; acquisition returns `SignalUnavailable`, never a source that waits forever pretending to work.

| Descriptor | Native event | `next` payload |
|---|---|---|
| `signals.ctrl_c` | POSIX SIGINT / Windows CTRL_C_EVENT | existing `CtrlC` |
| `signals.sigterm` | POSIX SIGTERM | `signals.Signal[name='sigterm']` |
| `signals.sighup` | POSIX SIGHUP | `signals.Signal[name='sighup']` |
| `signals.sigwinch` | POSIX terminal size change, where provided | `signals.Signal[name='sigwinch']` |
| `signals.sigusr1`, `signals.sigusr2` | POSIX application signals | corresponding `signals.Signal` |
| `signals.ctrl_break` | Windows CTRL_BREAK_EVENT | `signals.Signal[name='ctrl_break']` |
| `signals.console_close` | Windows CTRL_CLOSE_EVENT | `signals.Signal[name='console_close']` |

`SignalListener<E>.next` returns `E | Closed<E> | Canceled`; an explicit timeout adds `Timeout`. Source iteration treats `Closed<E>` as the end, forwards `Canceled` through its written `or_throw`, and yields only `E`. Existing Waitable machinery installs `.CtrlC`, `.Signal`, `.Closed`, `.types`, and explicit source selectors. These are source-qualified match arms, not new nominal types per source.

`intercept` returns `SignalListener<E> | SignalInUse | SignalUnavailable | Canceled`. `observe` returns `SignalListener<E> | SignalUnavailable | Canceled`. `SignalUnavailable` includes unsupported target, absent console, and registration failure with an explanatory message. Ordinary allocation failure keeps the existing environmental policy. Stop is nonwaiting, infallible `void`, so it keeps `()`.

SIGTERM/SIGHUP/SIGUSR1/2 retain native default disposition without an interceptor. SIGWINCH retains its normally ignored disposition. SIGINT has Dewy's cooperative default above. Windows close is a notification of imminent termination, never a veto. The signal API makes no claim to catch SIGKILL or SIGSTOP, nor to recover synchronously from an invalid memory access. Raw terminal mode may deliver a byte instead of Ctrl-C; this API does not turn raw bytes into signals.

## Cases

### David's constructor and `alive`

The record guide defines fields, defaults, and methods, not executable constructor rows that start tasks. There is no basis for treating a `run()` row as asynchronous. Even if an ordinary constructor called `run` synchronously, `r` would not be published before it returned. Construct the record first and call `r.run()` explicitly in the parallel item. Methods mutate their own object; ordinary record copies remain independent. No reactive sharing is added to `alive`. The recommended handler never reads it. Keep it only if other sequential code needs the final state.

The guide's current spellings are `input(prompt)` with `EndOfInput`, and `read_line` with `none` at EOF. `readl` occurs in David's notes, but this round must not silently adopt a new alias. The REPL uses `input`, distinguishes EOF from I/O errors, handles `quit`, and does not discard `Canceled` with an ordinary default.

### Search and save

`programs/02_search_save.dewy` races a long search against a Ctrl-C event. A winning event stops and joins the search; the parent remains uncanceled and saves a mutex-protected best result with a deadline before `exit(130)`. `13_default_cancel_save.dewy` shows the simpler default-cancellation variant: catch the search's `Canceled`, save under `task.protect_from_cancel(5s @save(best))`, report all save failures, and return the original cancellation. `within` alone cannot save after pending parent cancellation. Protection remains necessary, but is an ordinary call taking a function handle; there is no new scope syntax.

Protection masks incoming parent cancellation, not its own deadline. The protected call reports its own deadline as `Timeout`; independent `Canceled` results and ordinary errors remain. Parent cancellation stays pending afterward. Both the deadline and joining are cooperative. Neither OS termination nor three rapid presses guarantees a durable save.

### Groups, early return, and task handles

Finite task groups are `parallel` blocks/comprehensions. Persistent signal helpers need no group handle with the new closure rule. Early results belong in an ordinary function used as one item, or in a `race` when peers should actually be canceled. An ordinary `return` is not newly allowed out of a parallel body.

Dynamic spawned groups may still use `task.tasks(@body)` with its existing `Tasks<E>` parameter and ordinary local function boundary; scoped fail-fast, normal success joining, failure stopping/joining, and the task-handle error union remain. This is not the rejected signal-callback API: it is an optional existing dynamic-group facility. It does not grant nonlocal `return`/`break`. `none` is not a failure. An owner-stopped task's wait can still return `Canceled`, so consume the expected child cancellation and then check the caller for a simultaneous stop.

### Server, game, shell, resize, Windows, libraries

The programs cover a bounded, sequential TCP server that stops accepting on SIGTERM and lets a bounded current request finish; a terminal simulation whose Ctrl-C messages pause and quit it; a small command shell whose foreground child receives SIGINT directly; and a resize-aware terminal report. The shell neither retransmits SIGINT nor implements full job control. It uses the existing process API and shares the terminal's foreground group.

Windows close must notify normal work while the runtime's native control callback remains outstanding, subject to the OS's termination deadline. The program attempts a bounded save and releases its close listener; it cannot keep a closing console alive. Do not promise five seconds, or console output during close. Microsoft documents host-dependent control-handler timeouts and unreliable console services during close: [HandlerRoutine](https://learn.microsoft.com/en-us/windows/console/handlerroutine).

A library registers `observe`, then iterates in the caller's parallel block. It gets an independent mailbox without stealing events or suppressing the app's default. A library needing control accepts an application-owned listener or returns a request over a channel. Observation under default cancellation is best-effort, not guaranteed logging before exit.

## The central lifetime alternatives

**Chosen (b): close the block's signal views.** The iteration visibly has an end. Source closure is a normal value, so no private cancellation or hidden break is needed. The cost to predict is understanding that these signal views are bounded by the surrounding parallel work, and that a signal-only block is not a daemon.

**Possible later (a): watch the condition's reads.** `programs/16_condition_wakeup_alternative.dewy` sketches this unselected extension. Reuse `Closed` on a loop-owned source view when the condition becomes false; the manual loop still writes its break. A compiler could index guard-read places and sibling writes, register versions before parking, then recheck to prevent a lost wake. Known direct field reads are feasible. Getters, aliases, arbitrary helper control flow, and record-copy versus shared-place semantics need a wider reactive-loop design. This is worth revisiting, not rejected because the compiler would work harder. It is unnecessary for the selected REPL and changes more than signal lifetime.

**Existing baseline (c).** `18_race_baseline.dewy` stops the handler when work completes, including mid-handler; `19_done_channel_baseline.dewy` closes a done channel and selects it before signals. Both are useful explicit policies. The baseline costs more plumbing but does not infer that a signal wait is background work.

## What is new, and why an existing construct does not suffice

| Addition | Existing attempt first | What it cannot do |
|---|---|---|
| OS source descriptors, `intercept`, `observe`, listener outcomes | Channel plus a producer task | No existing safe operation receives an OS signal or controls its default disposition. An OS adapter is needed; language syntax is not. |
| Per-parallel signal views that close at signal quiescence | `parallel { work; loop true { next } }` | An infinite external source never ends. `race` cancels; a done channel works but adds plumbing. David chose ordinary source iteration with automatic block-bounded closure. |
| `Signal`, `SignalUnavailable`, `SignalInUse` | Existing `CtrlC`, `Closed`, `Canceled` | Other events need an identity; acquisition failures must not look like successful installation. Existing `Closed` and `Canceled` are reused, not replaced. |
| Console `Interrupted` behavior | `input(...) ?? break` | EOF, Ctrl-C, and I/O errors must not all end the REPL. This is the already proposed v5 stable input type, retained. |
| Ordinary handle form of `protect_from_cancel` | `within(5s @save)` | A pending parent cancellation reaches `within`; it cannot do cleanup despite it. Reuse v5 protection with a function handle, without inline blocks. |

There is no new keyword, metatag, function boundary, callback rule, injected `main` argument, reactive record, or nonlocal exit form. There **is** a new runtime rule for signal views; calling the whole change “only library names” would conceal it.

## Considered and rejected

Waiting-only interception makes a busy handler briefly restore the default. Implicit task-lifetime interception hides acquisition and makes startup scheduler-dependent. Multiple exclusive owners or “last registration wins” lets a library hijack policy. Exact press counting promises more than ordinary OS signals provide. A global source closing with the first block breaks shared users. Absorbing `Canceled` would invisibly end `loop true`, contrary to David's latest correction. A `Closed` arm that ignores closure and loops forever is a progress error under the existing terminal-wait rule, not an excuse for the runtime to break the loop. Callbacks and `inline` blocks remain withdrawn for signal handling.

## Review target

Write and inspect every program, settle queue-versus-close order and nested joins, check that resource acquisition and auto-closing views have independent lifetimes, then regrade honestly. Preserve this round unchanged.
