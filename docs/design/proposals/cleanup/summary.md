# Cleanup: round 5 summary

Final design: round5.md (programs-r5/, dogfood-round5.md). Round 4's summary is kept as summary-round4.md.

**Verdict:** keep `defer` narrowly, for one-off actions such as printing "done" (checked: non-failing, `void`, no control transfer). Resources clean themselves up.

- **Held owners** (cleanup can fail: files, temp entries, terminal modes, transactions, child processes; and lock guards) last to the end of their block. **Release owners** (memory, sockets, tickers, spsc ends, textures) drop at their last use, as today.
- **Cleanup failures are function results.** A cleanup failure with nothing else pending is returned as itself; one that meets a failure already leaving pairs with it as `CleanupError[primary cleanup]`. A pair carrying `Canceled` still behaves as cancellation (`??` doesn't consume it; only `??<Canceled | CleanupError>` does).
- **Cleanup never publishes.** `$__abandon__` types (transactions, children) roll back or stop on drop and take effect only through an explicit `tx.commit()`, `child.wait` or `child.stop()`; the compiler warns when no path consumes one, or when a success-shaped exit abandons one after a change.
- The 100 ms grace applies only after cancellation. Shared `Channel`/`mpmc` keep explicit close.
- Changes to decided rules: fallible `$__drop__`; fallible owners and lock guards held to block end (changes the loan rule); `Canceled` inside a pair stays cancellation; grace only after cancellation; `defer` restricted to non-failing actions.
- Floor 2 (program 09, C wrapper, blocked on a separate encapsulation question); the design's own floor 3 (14 shared channel, 15 break/continue becoming a return on close failure, 16–17 hand-off and replacement surprises, 18 generic timing).
