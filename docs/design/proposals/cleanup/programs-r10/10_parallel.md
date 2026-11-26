# 10. Races: a loser's undo and a loser's writer (round 10)

`copy_to`, `mirror` and `log_events` are as in [round 9](../programs-r9/10_parallel.md). What
changes is the race.

```dewy
import p"@lib/std/files.dewy" as files

backup_to = (dir:Path data:array<uint8>) => {
    let tmp = files.temp_beside(p"{dir}/backup.bin") or_throw
    defer tmp.discard() ?? printl("could not remove the temporary backup in {dir}" file=stderr)
    tmp.write_bytes(data) or_throw;
    tmp.persist(p"{dir}/backup.bin") or_throw
}

save_once = (data:array<uint8>) => first_ok(@backup_to(p"/mnt/a" data) @backup_to(p"/mnt/b" data))
```

A failed removal is now `TempRemoveFailed`, an `UndoFailed`, so `first_ok` can't discard it
(D44 Q6). With round 9's `defer tmp.discard() or_throw`, the loser would forward it into
`first_ok`, which rejects it:

```text
error: first_ok can discard backup_to's result (line 9), which can hold TempRemoveFailed,
       an UndoFailed: a temporary file with its bytes would stay on /mnt/b unreported.
       Handle it inside backup_to (line 3).
```

The handled form above writes where the stray file is. What "handled" means is the program's
choice: a log line, a list of paths to retry, a panic.

The plain writer, raced:

```dewy
fastest_copy = (data:array<uint8>) => first_ok(@copy_to(p"/mnt/a/backup.bin" data) @copy_to(p"/mnt/b/backup.bin" data))
```

```text
error: first_ok can cancel copy_to (line 1) while it holds out (FileWriter, copy_to line 2).
       A canceled copy would leave /mnt/b/backup.bin half written, and first_ok discards its result.
       Write through a temporary file:  files.temp_beside(path) … persist(path)
```

`mirror`'s `parallel` copies are unaffected: a canceled sibling's failures are kept beside the
exit (D44 Q8), not discarded.

## Scores

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 | 5 | 5 | 5 | 5 |

Obvious 4: `backup_to`'s `defer` is turned off by `persist`. Safe by default is 5 again: no
loser's undo or half-written file is discarded silently. Go's `errgroup` and Python's
`asyncio.wait(FIRST_COMPLETED)` leave both on disk with no report.
