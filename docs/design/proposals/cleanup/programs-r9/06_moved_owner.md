# 06. Owners moved into an array, a record and a caller's array

`open_shards` returns four writers in an array; `write_rows` fills them. `open_pair` builds a
record of two writers. `rotate` hands its writer to a caller's archive only when asked to.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
Row:type = [id:int name:string]
Pair:type = [main:FileWriter audit:FileWriter]

open_shards = (dir:Path n:int) => {
    let shards:array<FileWriter> = []
    defer drop(shards) or_throw                  # a later open fails: close the ones already open
    loop i in [0..n) shards.push(files.open(p"{dir}/shard{i}.csv" 'w') or_throw)
    shards                                       # moved to the caller: the defer is off
}

write_rows = (dir:Path rows:array<Row>) => {
    let shards = open_shards(dir 4) or_throw
    defer drop(shards) or_throw                  # closes all four, in reverse; failures fold into a stack
    loop row in rows { shards[row.id % 4].write_text("{row.name}\n") or_throw; }
}

open_pair = (dir:Path) => {
    let main = files.open(p"{dir}/main.log" 'w') or_throw
    defer main.close() or_throw                  # if audit's open fails
    let audit = files.open(p"{dir}/audit.log" 'w') or_throw
    Pair[main audit]                             # both move into the record
}

rotate = (@archive:array<FileWriter> out:FileWriter keep:bool) => {
    defer out.close() or_throw
    out.write_text("-- end --\n") or_throw;
    if keep archive.push(out)                    # moved: the defer is off on this path
}
```

A `defer` follows its value: a move on a path cancels it on that path, and the value's new owner
owes it. In `open_shards` and `open_pair` that makes it an `errdefer` for a constructor.

`drop(shards)` closes each element and folds their failures. Two failed flushes give
`ErrorStack[FileWriteFailed FileWriteFailed]`; one gives it bare.

## (g-auto)

`open_shards` and `open_pair` need nothing: a failed later open cleans up the earlier writers
automatically and their failures join. `write_rows` and `rotate` are as in (g).

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 4 lines | 0 | error at the fallible line, offering the `defer` |
| (g-auto) | 2 lines | 0 | error at the success exit |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 4 → 5 | 5 | 5 | 5 |

Discoverable 4 → 5 (iteration 3): a newcomer writing `open_pair` must learn that a later `or_throw`
can leave with `main` open. The error says exactly that, at the second open, with the fix. Rust
and Swift write nothing and lose a failure; Python needs an `ExitStack` with `pop_all()` to hand
the files out, which is longer; Go closes the earlier files by hand on each error path.
