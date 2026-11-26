# 11. A library type whose finish writes a footer (round 10)

Round 9's `Archive` wrote its footer in `$__drop__`, so `defer drop(archive)` after a failed
`add` published a partial archive with a count. Round 10: a hook may only end the value's
fields, and new work goes in a `$__consume__` method that decides the value.

```dewy
import p"@lib/std/files.dewy" as files
Item:type = [name:string bytes:array<uint8>]

Archive:type = type of [index:FileWriter data:FileWriter count:int=0
    add = (name:string bytes:array<uint8>) => {
        data.write_bytes(bytes) or_throw;
        index.write_text("{name} {bytes.length}\n") or_throw;
        count += 1
    }
    $__consume__
    finish = () => {                         # success: the footer, then both closes
        defer data.close() or_throw
        defer index.close() or_throw
        index.write_text("count {count}\n") or_throw;
    }
    $__abandon__ = () => {                   # failure exits: both closes, no footer
        defer data.close() or_throw
        index.close() or_throw
    }
]

open_archive = (dir:Path) => {
    let index = files.open(p"{dir}/index.txt" 'w') or_throw
    defer index.close() or_throw             # failure exits: the return moves index into the archive
    let data = files.open(p"{dir}/data.bin" 'w') or_throw
    Archive[index data]
}

pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    defer drop(archive) or_throw             # failure exits: abandon, no footer
    loop item in items archive.add(item.name item.bytes) or_throw;
    archive.finish() or_throw                # decides the archive: the abandon doesn't run after it
}
```

- `finish` is a `$__consume__` method (LANGUAGE.md's existing marker): it owns the archive, so it
  may consume `index` and `data`, and the per-exit rule checks it like any body.
- Calling it decides the archive, so `$__abandon__` doesn't run afterwards. That is the one new
  piece: a consuming call is the decision batch 9's `$__abandon__` waits for.
- `Archive` has unpublished work, so `pack` without `finish` is rule 5's error:

```text
error: archive (Archive, line 2) is unfinished where pack ends (line 5).
       Finish it:  archive.finish() or_throw
```

The round-9 hook, with the footer in `$__drop__`:

```text
error: Archive's $__drop__ runs on failure exits, and index.write_text (line 9) writes new data.
       Move it into a finishing method:   $__consume__ finish = () => { … }
       and close the fields without it:   $__abandon__ = () => { … }
```

## Scores

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 4 | 5 | 4 | 5 | 5 |

Obvious 4: `defer drop(archive)` above `finish` is turned off by it, which the `defer` line
doesn't show. Concise 4: the constructor is two bindings and a `defer`. Rust and Python would put
the footer in `Drop` or `__exit__` and write it on the failure path too, the bug this fixes.
