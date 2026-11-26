# 11. A library type whose cleanup writes a footer and closes two files

`Archive` appends entries to a data file and an index. Its cleanup writes the entry count to the
index, then closes both files.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files
Item:type = [name:string bytes:array<uint8>]

Archive:type = type of [index:FileWriter data:FileWriter count:int=0
    add = (name:string bytes:array<uint8>) => {
        data.write_bytes(bytes) or_throw;
        index.write_text("{name} {bytes.length}\n") or_throw;
        count += 1
    }
    $__drop__ = () => {
        defer data.close() or_throw          # the hook owns the fields: it may consume them
        defer index.close() or_throw
        index.write_text("count {count}\n") or_throw;
    }
]

open_archive = (dir:Path) => {
    let index = files.open(p"{dir}/index.txt" 'w') or_throw
    defer index.close() or_throw             # if data's open fails
    let data = files.open(p"{dir}/data.bin" 'w') or_throw
    Archive[index data]
}

pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    defer drop(archive) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
}
```

**A hook owns its value's fields.** Inside `$__drop__`, `index` and `data` are the hook's to
consume, and owing fields are accounted for at each of the hook's exits like locals: the same
rule, applied to the hook's body. The footer, then the index's close, then the data's close run,
and every failure folds. This also closes round 8's gap (program 11, iteration 2): `drop(archive)`
is the finishing call, and the hook is never run twice because consuming a field inside the hook
is what finishes it. `Archive`'s cleanup type is inferred from the hook:
`void | FileWriteFailed | FileCloseFailed | ErrorStack<…>`.

`open_archive` can't be `Archive[files.open(…) or_throw files.open(…) or_throw]` any more: if the
second open fails, the first writer is open with nothing to account for it.

```text
error: the FileWriter opened at line 2 is still open if the open at line 3 fails.
       Bind it and close it on every exit:
           let index = files.open(…) or_throw
           defer index.close() or_throw
```

## (g-auto)

`open_archive` keeps the one-expression form (a failed construction cleans up its finished
fields, and their failures join). The hook needs no `defer`s; the fields close after it
automatically, folding by D42. `pack` writes `drop(archive) or_throw` at its end, or the `defer`.

## Scores

| | Added over (a) | Hidden | Forgotten |
|---|---|---|---|
| (g) | 1 line in `pack`; 2 in the hook; `open_archive` split into bindings (+2 lines) | 0 | error |
| (g-auto) | 1 line | 0 | error |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 4 | 5 | 4 → 5 |

Concise 4: the constructor can't be one expression. Rust's `Archive { index: File::create(..)?,
data: File::create(..)? }` is one expression and loses a flush failure; Python's equivalent needs
an `ExitStack` too. See iteration 4. Complete 4 → 5: a finishing method on a hooked type no longer
needs `discard self`, because the hook consumes its own fields (iteration 1).
