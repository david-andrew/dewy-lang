# 01. Buffered file writes

`save` has one success exit. `export_csv` has two: it stops at the first invalid row and reports
how many it wrote. A full disk often shows up only at the final flush.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
Row:type = [name:string score:int]

save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw       # FileWriter
    defer out.close() or_throw
    out.write_bytes(data) or_throw;
}

export_csv = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 return i            # i is computed, then out closes; a failed close replaces i
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    rows.length
}
```

One line per writer, beside its open, covers every exit. If a write fails and then the close
fails too, `save` gives `ErrorStack[FileWriteFailed FileWriteFailed]`, the write's first.

Without the `defer` in `save`, with or without an explicit `out.close() or_throw` at the end:

```text
error: out (FileWriter, line 2) is still open if out.write_bytes fails (line 3).
       Closing it flushes, which can fail with FileWriteFailed | FileCloseFailed.
       Close it on every exit:  defer out.close() or_throw     (after line 2)
```

The explicit close at the end (round 8's (f)) still compiles when nothing between the open and
the close can fail. In practice there is always a write in between, so the idiom is the `defer`.

## (g-auto)

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;               # fails: out flushes, a failed flush joins, unwritten
    out.close() or_throw
}
```

`export_csv` is the same as in (g): two success exits make the `defer` the shorter fix.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 2 lines | 0 | error at the first fallible line, offering the `defer` |
| (g-auto) | 2 lines | 0 | error at the success exit |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Python's `with open(...)` is one line and an indent; Go's `defer f.Close()` is one line and loses
the failure; Rust and Swift write nothing and lose it. (g) is Go's line with Python's outcome.
