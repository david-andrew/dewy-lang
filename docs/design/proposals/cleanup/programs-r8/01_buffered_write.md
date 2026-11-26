# 01. Buffered file writes

`save` has one success exit. `export_csv` has two: it stops at the first invalid row and reports
how many it wrote. A full disk often shows up only at the final flush.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files
Row:type = [name:string score:int]

save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
}   # flush and close: a full disk becomes save's result

export_csv = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 return i     # out flushes on this exit too
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    rows.length
}
```

`export_csv`'s inferred result gains `FileWriteFailed | FileCloseFailed` from three places no
line names: `return i`, the fallthrough, and (joined) each failing write.

## (b) Marked scope

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
} or_throw

export_csv = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 return i
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    rows.length
} or_throw      # covers `return i` and the fallthrough
```

Without the markers: a warning per function naming `out` and both exits; at run time the flush
failure is discarded and `export_csv` reports rows it may not have written.

## (c) Value-tied `defer`

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw
    out.write_bytes(data) or_throw;
}

export_csv = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    defer out.close() or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 return i
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    rows.length
}
```

## (d) Explicit close

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
    out.close() or_throw
}

export_csv = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 { out.close() or_throw; return i }
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    out.close() or_throw
    rows.length
}
```

## (e) Disposition on the binding

```dewy
save = (path:Path data:array<uint8>) => {
    let out drop or_throw = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
}

export_csv = (path:Path rows:array<Row>) => {
    let out drop or_throw = files.open(path 'w') or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 return i
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    rows.length
}
```

Two `or_throw`s on one line handle two failures at two times.

## (f) Finish on success, clean up on failure

```dewy
save = (path:Path data:array<uint8>) => {
    let out = files.open(path 'w') or_throw
    out.write_bytes(data) or_throw;
    out.close() or_throw
}

export_csv = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    out.write_text("name,score\n") or_throw;
    loop i in [0..rows.length) {
        if rows[i].score <? 0 return i
        out.write_text("{rows[i].name},{rows[i].score}\n") or_throw;
    }
    rows.length
} or_throw      # two success exits: the marker is the shorter of the two fixes
```

Without the close line in `save`:

```text
error: out (File, line 2) is still open where save ends (line 4).
       Its final flush can fail with FileWriteFailed | FileCloseFailed.
       Finish it:          out.close() or_throw
       or cover the body:  } or_throw
```

A failing write needs nothing more in any version: `out` flushes on that exit and a second
failure joins (`FileWriteFailed & FileCloseFailed`).

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 3 | 0 | — |
| (b) | 2 tokens | 0 | 0 (3 if unmarked) | warning; the flush failure is discarded |
| (c) | 2 lines | 0 | 0 (3 if missing) | warning |
| (d) | 3 lines, 1 brace group | 0 | 0 (3 if missing) | warning |
| (e) | 2 clauses | 0 | 0 | error |
| (f) | 1 line, 1 token | 0 | 0 | error, with both fixes |
