# Final: signals as parallel event sources

**Read `round3.md`.** Twenty-three scenario programs and three support modules are in `programs/`; earlier sources remain in `programs-r1/` and `programs-r2/`. `dogfood.md` records the revisions and line-specific grades. These are design programs, not an implementation or compiler-test claim.

```dewy
let ctrl_c = signals.ctrl_c.intercept or_throw
defer ctrl_c.stop()
let r = repl
parallel {
    r.run() or_throw
    loop _ in ctrl_c or_throw { printl"KeyboardInterrupt" }
}
```

Construct the REPL before running it; a constructor does not secretly spawn `run`. During terminal input, Ctrl-C clears the line and gives `Interrupted`, which the REPL handles before reprompting. Otherwise the signal iterator receives it. EOF and `quit` finish `run`.

**David's (b), with visible closure:** each registration has an independent view per active parallel block. When all unfinished items are waiting only on that block's signal views, close those views together. Preserve buffered notifications, then yield `Closed<E>`. Iteration ends normally; `loop true` must explicitly match `Closed` and break. There is no synthetic cancellation, hidden break, or implicit function return. A handler already processing an event finishes; an ordinary wait inside it can prolong the block. `race` is the explicit cancel-mid-handler policy.

A result-dependent continuation cannot keep its own signal iterator alive; its report runs after closure. An all-signal `select` counts; a timer, timeout, channel, I/O, or externally owned task wait does not. Ordinary helpers inherit their caller's view. Nested parallel blocks own separate lifetimes; shared sources in two blocks do not close each other. Scoped owned joins propagate their wait state; BackgroundTasks do not join a block accidentally. A block containing only signal listeners closes immediately on reaching that state: an intentional signal-only service uses a plain loop/merged outside parallel.

**Policy ownership:** descriptors are inert. `.intercept` exclusively changes default delivery until `.stop()`/last handle drop; a second owner gets `SignalInUse`. `.observe` is passive and cannot suppress default shutdown. Handle copies share a registration; views in different blocks have separate mailboxes. Each holds at most one pending notification. Closing a view does not release interception; the adjacent defer does.

Without interception, Ctrl-C cancels the root and unhandled cancellation exits 130. Retain v5's second-press default-shutdown escape and three runtime-observed presses within one second forcing exit even while intercepted/protected. The OS can coalesce presses before delivery. Other signal defaults remain native. Foreground children receive SIGINT directly; the parent does not retransmit it. Windows close offers bounded best-effort cleanup, never a veto.

**Changes:** replace `catch_ctrl_c` callback/inline scopes and nested catcher policy with ordinary source ownership and iteration. Add block-local signal closure, a real runtime semantic change. Keep v6 source-qualified type arms, priority, loser commit rules, cancellation values, prefix metatags and record semantics. Keep ordinary `protect_from_cancel(5s @save(best))` for already-canceled cleanup and optional `task.tasks(@body)` for dynamic groups; no special block syntax. (a), watched guard reads, remains a possible later generalization; (c), race/done channels, remains available.

**New names, provisional:** `signals` module; `ctrl_c`, `sigterm`, `sighup`, `sigwinch`, `sigusr1`, `sigusr2`, `ctrl_break`, `console_close`; `intercept`, `observe`; `SignalListener`, `Signal.name`, `SignalInUse`, `SignalUnavailable.message`. `names.txt` has the cold-read inputs; no cold-read approval is claimed.

**Floors:** ergonomic 4 for contextual view lifetime, input/event routing and cooperative bounds; completeness 3 for Windows termination, full shell job control and cross-platform terminal-size support. The unselected (a) also needs more design. Abstract closure-model checks passed; no performance measurement or native execution is claimed. Future implementation cost must pass the flagship instruction-count gate. No repository files were changed.
