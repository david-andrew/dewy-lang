# 10. Parallel and concurrent work that owns files

`mirror` writes the same data to two disks in parallel and journals the result. If one copy
fails, its sibling is canceled mid-write. `log_events` hands a writer to a spawned task.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files

copy_to = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
}   # out flushes here

mirror = (data:array<uint8>) => {
    let journal = files.open(p"mirror.log" 'a') or_throw
    parallel {
        copy_to(p"/mnt/a/backup.bin" data) or_throw;
        copy_to(p"/mnt/b/backup.bin" data) or_throw;
    }
    journal.write_text("mirrored {data.length} bytes\n") or_throw;
}   # journal flushes here

log_events = (events:Channel<string> path:Path) => {
    let out = files.open(path 'a') or_throw
    concurrent {
        spawn { loop e in events or_throw out.write_text("{e}\n") or_throw; }   # the task owns out
    }   # out flushes when the task ends, before the group joins
}
```

When copy A fails, copy B is canceled: B leaves on a failure exit (`Canceled`), its `out`
flushes there, and a failed flush stays beside A's failure (D44 Q8's row "A sibling canceled by an
early exit keeps what it forwarded, and its cleanup failures"). That part is the same in every
approach. What differs: `copy_to`'s and `mirror`'s success exits, and the end of the spawned
task, all flush with nothing written.

## (b) Marked scope

```dewy
copy_to = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
} or_throw

mirror = (data:array<uint8>) => {
    let journal = files.open(p"mirror.log" 'a') or_throw
    parallel {
        copy_to(p"/mnt/a/backup.bin" data) or_throw;
        copy_to(p"/mnt/b/backup.bin" data) or_throw;
    }
    journal.write_text("mirrored {data.length} bytes\n") or_throw;
} or_throw

log_events = (events:Channel<string> path:Path) => {
    let out = files.open(path 'a') or_throw
    concurrent {
        spawn ({ loop e in events or_throw out.write_text("{e}\n") or_throw; } or_throw)
    }
}
```

A task body has no settled place for the marker: `spawn { … } or_throw` would attach to the
`spawn` expression, so the body needs round 7's grouping, and whether a task's body counts as an
owning scope that the grouping marks is a new rule.

## (c) Value-tied `defer`

```dewy
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
            defer out.close() or_throw
            loop e in events or_throw out.write_text("{e}\n") or_throw;
        }
    }
}
```

## (d) Explicit close

```dewy
copy_to = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
    out.close() or_throw
}

mirror = (data:array<uint8>) => {
    let journal = files.open(p"mirror.log" 'a') or_throw
    parallel {
        copy_to(p"/mnt/a/backup.bin" data) or_throw;
        copy_to(p"/mnt/b/backup.bin" data) or_throw;
    }
    journal.write_text("mirrored {data.length} bytes\n") or_throw;
    journal.close() or_throw
}

log_events = (events:Channel<string> path:Path) => {
    let out = files.open(path 'a') or_throw
    concurrent {
        spawn {
            loop e in events or_throw out.write_text("{e}\n") or_throw;
            out.close() or_throw
        }
    }
}
```

## (e) Disposition on the binding

```dewy
copy_to = (path:Path data:array<uint8>) => {
    let out drop or_throw = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
}
```

`mirror` likewise. In `log_events` the clause on `out` is cleared by the capture into the task, so
the task's end needs its own rule, as the lazy body did in program 08.

## (f) Finish on success, clean up on failure

```dewy
copy_to = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
    out.close() or_throw
}

mirror = (data:array<uint8>) => {
    let journal = files.open(p"mirror.log" 'a') or_throw
    parallel {
        copy_to(p"/mnt/a/backup.bin" data) or_throw;
        copy_to(p"/mnt/b/backup.bin" data) or_throw;
    }
    journal.write_text("mirrored {data.length} bytes\n") or_throw;
    journal.close() or_throw
}

log_events = (events:Channel<string> path:Path) => {
    let out = files.open(path 'a') or_throw
    concurrent {
        spawn {
            loop e in events or_throw out.write_text("{e}\n") or_throw;
            out.close() or_throw         # a task body's end is a success exit like any other
        }
    }
}
```

The canceled sibling needs nothing: cancellation is a failure exit. Each task, item and function
finishes what it owns on its own success exits, so no rule crosses a task boundary.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 3 | 0 | — |
| (b) | 2 tokens, 1 grouping; task-body marking is a new rule | 0 | 0 | warning |
| (c) | 3 lines | 0 | 0 | warning |
| (d) | 3 lines | 0 | 0 | warning |
| (e) | 2 clauses; the task's end is uncovered | 1 | 0 | error |
| (f) | 3 lines | 0 | 0 | error |
