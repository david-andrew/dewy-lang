# Signals — final round 4

Read **round4.md**. Revised sources: **programs-r4/** (32 scenarios, including three explicit unsupported/counterexample fixtures, plus three support modules). Every sub-5 grade has a line reference in **dogfood-round4.md**. Earlier rounds, programs and summary.md are preserved.

```dewy
parallel {
    regular_work() or_throw
    loop _ in signals.ctrl_c or_throw { printl"Ctrl-C received" }
}
```

**No required acquisition or signal cleanup.** First executed wait attaches the block's subscription; interception survives handler-body gaps and ends automatically on block exit. Descriptor/handle copies cannot extend it. Native signals broadcast to all attached owner views; any intercepting owner suppresses the default. A library listening directly in its own block therefore changes app policy. `.observe` is passive. SignalInUse, required `.intercept`, shared SignalListener ownership and signal `.stop()` are withdrawn.

**Closure (b) stays visible and conditional.** Once every live frontier in a block is signal-only, close its views together, drain pending values, then give Closed. Iteration ends; manual loops must explicitly break. Publish ready dependents before deciding closure. Helpers inherit the executing owner; nested blocks own separate views; externally owned tasks keep their own scopes. Outside parallel, the entry task owns its subscription to task exit, without automatic signal quiescence closure.

**Limit beside the idiom:** a repeating mixed timer/select stays ordinary forever; two overlapping busy handlers under continuing arrivals can also prevent closure forever. “One queued event per view” bounds backlog only after closure occurs. Programs 26/27 show failures of eventual shutdown; 19/28 use done/race to enforce it. Cancellation remains cooperative.

**REPL:** construct then run, no alive field. A read/signal race selects Interrupted or CtrlC and joins/resets a canceled read. The separate printing loop prints KeyboardInterrupt and acknowledges; only then does the next fresh prompt begin. This uses existing channels and preserves one output owner, at a real concision cost. The two raw loops alone cannot promise prompt ordering.

**Startup:** before first attachment, the default applies. Startup-sensitive work can depend on existing `next(timeout=0s)`; no new early-attach member is needed. Program 25 adds an explicit two-block ready barrier. Passive observation alone never suppresses root cancellation.

**Failures and resources:** first-use failure or later facility loss returns SignalUnavailable, not successful Closed. Unexpected Closed fails shutdown examples. merged drains all normally closed control sources; errors fail fast. Scope exit removes routing state; captured arrival/read epochs prevent old notifications reaching new owners/reads. Windows close may hold a waiting native callback until captured owners finish or the OS terminates them; this cost is separate from event fan-out. No guarantee of persistence or console output at Windows termination.

**New names:** signals module/descriptors (`ctrl_c`, `sigterm`, `sighup`, `sigwinch`, `sigusr1`, `sigusr2`, `ctrl_break`, `console_close`), `observe`, `SignalSource`, `Signal.name`, `SignalUnavailable.message`. names.txt is updated for cold reads; none is claimed cold-read-approved. Existing next, Closed, CtrlC, Interrupted, select/race/merged, protection and prefix metatags remain.

**Floor:** 3 for selected working designs—contextual lifetime, ordered-output plumbing and platform limits. Unsupported/negative fixtures retain 2s. The escaped-registration safety defect is removed structurally. This is paper design with explicit boundary traces, not compiled/native/performance validation. Repository unchanged.
