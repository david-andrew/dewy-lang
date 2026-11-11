# Cold read 19: signal sources (three fresh readers a, b, c)

Questions: (a) does the line replace the OS default? (b) when does the loop end?

| Spelling | (a) replaces default | (b) ends | Verdict |
|---|---|---|---|
| `loop _ in signals.ctrl_c` in parallel | yes, 3/3 (conf ~4) | when the source closes, 3/3 (none knew when it closes) | pass |
| `signals.ctrl_c.observe` | keeps default, 3/3 (3/3/2) | when the stream closes | pass, lower confidence |
| `signals.sigterm`, `sighup`, `sigwinch`, `ctrl_break` | replace, 3/3 | source closes | pass |
| `signals.console_close` | "replaces" 3/3 (design: best-effort cleanup, OS still terminates) | source closes | name passes; the no-veto limit must be documented |
| `signals.SignalSource<CtrlC>` | inert until used, 3/3 | n/a | pass |
| `signals.SignalUnavailable` + `.message` | read as "signal can't be received", 3/3 | n/a | pass |
