# 12. A child process and a temporary directory

`build` compiles into a scratch directory and copies the result out. `first_line` starts
`tail -f` to read one line, and leaves while the child still runs.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
BuildFailed:type = type of error & [code:int]

build = (src:Path) => {
    let scratch = files.temp_dir() or_throw
    defer scratch.remove() or_throw                                     # a leftover: warning if missing
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw
    let status = child.wait() or_throw                                  # consumes child at once
    if status not=? 0 return BuildFailed[status]
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
}

first_line = (log:Path) => {
    let tail = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    defer tail.stop() or_throw                                          # failure exits
    let line = tail.stdout.read_line() or_throw
    tail.stop() or_throw
    line
}
```

`build`'s child needs nothing: nothing can fail between `spawn` and `wait`, which consumes it.
Removing the scratch directory can fail, so it appears (round 8 hid it as a release; David's
rule is that only what can't fail stays out of sight), but as a leftover: without the `defer`
it is a warning, and a failed removal at run time is discarded.

Without `tail.stop()` at the end:

```text
error: tail (Child, line 2) is still running where first_line ends (line 5).
       Wait for it:  tail.wait() or_throw
       or stop it:   tail.stop() or_throw
```

## (g-auto)

`build` keeps its `defer`: (g-auto) changes only failure exits, and the removal at the success
exit is still a leftover that warns. `first_line` loses its `defer`: a failed read stops `tail`
automatically and a failed stop joins.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 3 lines | 0 | warning (scratch), error (tail) |
| (g-auto) | 2 lines | 0 | warning, error |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 4 | 5 | 5 |

Concise 4: `first_line` says `stop` twice (iteration 2). Python's `Popen` as a context manager
waits, which would hang on `tail -f`; Go and Rust leave `tail` running; `tempfile.TemporaryDirectory`
in Python raises a removal failure from `with`, like (g).
