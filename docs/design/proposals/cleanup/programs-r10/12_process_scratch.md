# 12. A child process, its stdin, and a temporary directory (round 10)

`build` and `first_line` are as in [round 9](../programs-r9/12_process_scratch.md), with one
change: the scratch directory's removal is an undo (`TempRemoveFailed`), so `build` without its
`defer` is an error, not a warning. `compress` is new: it writes to a child's stdin, the pipe case
the review found missing.

```dewy
import p"@lib/std/files.dewy" as files
CompressFailed:type = type of error & [code:int]

compress = (data:array<uint8> out:Path) => {
    let gz = spawn(p"/usr/bin/gzip" ["-c"] stdin='pipe' stdout=out) or_throw
    defer gz.stop() or_throw                   # failure exits: stop and reap
    gz.stdin.write_bytes(data) or_throw;       # stdin is a pipe writer: buffered
    let status = gz.wait() or_throw            # closes stdin first (end of file), then waits
    if status not=? 0 return CompressFailed[status]
}
```

- `gz.stdin` is a field of the `Child` that owes its flush and close. `wait()` is a
  `$__consume__` method that ends it before waiting (the child can't finish without end of file),
  so its result is `Status | ProcessWaitFailed | FileWriteFailed | FileCloseFailed`.
- On a failure exit, `stop` closes stdin without flushing and stops the child: the output is
  abandoned anyway.
- `spawn`'s `stdin=` and `stdout=` arguments are illustrative.

Without `defer scratch.remove() or_throw` in `build`:

```text
error: scratch (TempDir, line 2) is removed if spawn fails (line 3), and removing it can fail
       with TempRemoveFailed, leaving the directory and its contents behind.
       Remove it on every exit:  defer scratch.remove() or_throw
```

## Scores

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 | 5 | 4 | 5 | 5 |

Obvious 4: `defer tail.stop()` then `tail.stop()` (and `defer gz.stop()` before `wait`) read as
stopping twice until the turn-off rule is known. Concise 4: `first_line` says `stop` twice.
Python's `Popen.communicate` closes stdin and waits, and ignores a broken pipe on stdin; Go's
`cmd.StdinPipe` must be closed by hand before `Wait`, and a bare `defer` on it drops the error.
