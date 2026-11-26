# 06. Owners moved into an array, a record and a caller's array

`open_shards` returns four writers in an array; `write_rows` fills them. `open_pair` builds a
record of two writers. `rotate` hands its writer to a caller's archive only when asked to.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files
Row:type = [id:int name:string]
Pair:type = [main:File audit:File]

open_shards = (dir:Path n:int) => {
    let shards:array<File> = []
    loop i in [0..n) {
        let f = files.open(p"{dir}/shard{i}.csv" 'w') or_throw    # failure exit: earlier shards flush and join
        shards.push(f)                                            # f moves into the array
    }
    shards                                                        # the array moves to the caller
}

write_rows = (dir:Path rows:array<Row>) => {
    let shards = open_shards(dir 4) or_throw
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
}   # four flushes, reverse order; two failures come back as ErrorStack<FileWriteFailed>

open_pair = (dir:Path) => {
    let main = files.open(p"{dir}/main.log" 'w') or_throw
    let audit = files.open(p"{dir}/audit.log" 'w') or_throw      # failure exit: main flushes
    Pair[main audit]                                             # both move into the record
}

rotate = (@archive:array<File> out:File keep:bool) => {
    out.write_text("-- end --\n") or_throw;
    if keep { archive.push(out); return }      # moved: whoever owns archive finishes it
}                                              # not kept: out flushes here
```

`open_shards` and `open_pair` have no success-exit duty: every success path moves the owners
out. `write_rows` and `rotate`'s second path gain unwritten failures.

## (b) Marked scope

```dewy
write_rows = (dir:Path rows:array<Row>) => {
    let shards = open_shards(dir 4) or_throw
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
} or_throw

rotate = (@archive:array<File> out:File keep:bool) => {
    out.write_text("-- end --\n") or_throw;
    if keep { archive.push(out); return }
} or_throw      # applies only on the path where out is still owned
```

## (c) Value-tied `defer`

```dewy
write_rows = (dir:Path rows:array<Row>) => {
    let shards = open_shards(dir 4) or_throw
    defer drop(shards) or_throw
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
}

rotate = (@archive:array<File> out:File keep:bool) => {
    defer out.close() or_throw          # canceled on the path where out moves into archive
    out.write_text("-- end --\n") or_throw;
    if keep { archive.push(out); return }
}
```

The brainstorm split on `rotate`: one answer lets the move cancel the `defer` (as here), two
say the `defer` pins `out` and the `push` is an error. Under pinning, `rotate` needs (d)'s form.

## (d) Explicit close

```dewy
write_rows = (dir:Path rows:array<Row>) => {
    let shards = open_shards(dir 4) or_throw
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
    drop(shards) or_throw
}

rotate = (@archive:array<File> out:File keep:bool) => {
    out.write_text("-- end --\n") or_throw;
    if keep { archive.push(out); return }
    out.close() or_throw
}
```

## (e) Disposition on the binding

```dewy
write_rows = (dir:Path rows:array<Row>) => {
    let shards drop or_throw = open_shards(dir 4) or_throw
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
}

rotate = (@archive:array<File> out:File drop or_throw keep:bool) => {
    out.write_text("-- end --\n") or_throw;
    if keep { archive.push(out); return }
}
```

## (f) Finish on success, clean up on failure

```dewy
write_rows = (dir:Path rows:array<Row>) => {
    let shards = open_shards(dir 4) or_throw
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
} or_throw      # an array of writers: the marker finishes every element

rotate = (@archive:array<File> out:File keep:bool) => {
    out.write_text("-- end --\n") or_throw;
    if keep { archive.push(out); return }
    out.close() or_throw
}
```

`array<File>` and `Pair` owe what their writers owe, so their holders get the same error a
single writer would. A caller of `open_pair` writes `logs.main.close() or_throw` and
`logs.audit.close() or_throw`, or marks its scope.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 2 | 0 | — |
| (b) | 2 tokens | 0 | 0 | warning |
| (c) | 2 lines; needs `drop`; move-versus-pin unsettled | 0 | 0 | warning |
| (d) | 2 lines; needs `drop` | 0 | 0 | warning |
| (e) | 2 clauses, one in a signature | 0 | 0 | error |
| (f) | 1 token, 1 line | 0 | 0 | error |
