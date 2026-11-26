# 10. Parallel and concurrent work that owns files

`mirror` writes the same data to two disks in parallel and journals the result; if one copy
fails, its sibling is canceled mid-write. `log_events` hands a writer to a spawned task.
`save_once` races two backups and keeps the first to succeed.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files

copy_to = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw
    out.write_bytes(data) or_throw;
}

mirror = (data:array<uint8>) => {
    let journal = files.open(p"mirror.log" 'a') or_throw
    defer journal.close() or_throw
    parallel {
        copy_to(p"/mnt/a/backup.bin" data) or_throw;
        copy_to(p"/mnt/b/backup.bin" data) or_throw;
    }
    journal.write_text("mirrored {data.length} bytes\n") or_throw;
}

log_events = (events:Channel<string> path:Path) => {
    let out = files.open(path 'a') or_throw
    concurrent {
        spawn {
            defer out.close() or_throw           # out moved into the task; the task's exits close it
            loop e in events or_throw out.write_text("{e}\n") or_throw;
        }
    }
}

backup_to = (dir:Path data:array<uint8>) => {
    let tmp = files.temp_beside(p"{dir}/backup.bin") or_throw
    defer tmp.discard() or_throw
    tmp.write_bytes(data) or_throw;
    tmp.persist(p"{dir}/backup.bin") or_throw
}

save_once = (data:array<uint8>) => first_ok(@backup_to(p"/mnt/a" data) @backup_to(p"/mnt/b" data))
```

- **Canceled sibling.** Cancellation is a failure exit of `copy_to`'s body. Its `defer` runs
  (shielded, with D44's grace), and a failed close folds with `Canceled`: since `Canceled`
  can't enter a stack (D44), the shape is `Canceled & FileWriteFailed`. `parallel` keeps it
  beside the first failure (D44 Q8).
- **A task body is a body.** `out` moves into the `spawn`, so the task owes it; its `defer` is
  the task's. The enclosing function owes nothing after the move.
- **Race losers.** A loser is canceled, so its defers run on a failure exit and their failures
  fold into its result, which `first_ok` discards whole (D44 Q6). The discard is written: it is
  what `first_ok` means, and hover on the call lists what can be discarded. Under
  `$no_discarded_failures` (D44 Q7) it is an error, and each backup handles its own cleanup
  failures. A failed `discard` is a `FileRemoveFailed` leftover, not an `UndoFailed`, so it may
  be discarded by default.
- **What the loser's lost flush would have said.** The review's case: a loser writing a plain
  `FileWriter` to its final path is canceled, its flush fails, and the failure is discarded. The
  flush failure is the lesser problem: the path already holds a half-written file whether or not
  the flush failed. Raced writes should go through a temporary file, as `backup_to` does, so the
  loser's abandon removes its partial output. A lint for a `FileWriter` to a final path inside a
  raced body is outside this round.

## (g-auto)

`copy_to`, `mirror` and the task can write closes at the end instead of their `defer`s; the
canceled sibling joins its flush failure automatically. `backup_to` needs no `defer`: a failed
write removes the temporary and a failed removal joins.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 4 lines | 0 | error |
| (g-auto) | 3 lines | 0 | error |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Go loses a deferred close in each goroutine; Rust's drop in each thread loses it; Python's
`with` inside each thread raises in that thread, where `concurrent.futures` keeps it for
`result()`; TypeScript's `await using` inside each async function raises into its promise.
