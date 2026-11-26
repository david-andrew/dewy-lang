# 11. A library type whose cleanup writes a footer and closes two files

`Archive` appends entries to a data file and an index. Its own hook writes the entry count to the
index; then its fields are cleaned up in reverse order (data, then index), each a flush that can
fail.

## The type (the same in every approach)

```dewy
import p"@lib/std/files.dewy" as files
Item:type = [name:string bytes:array<uint8>]

Archive:type = type of [index:File data:File count:int=0
    add = (name:string bytes:array<uint8>) => {
        data.write_bytes(bytes) or_throw;
        index.write_text("{name} {bytes.length}\n") or_throw;
        count += 1
    }
    $__drop__ = ():>void | FileWriteFailed => { index.write_text("count {count}\n") or_throw; }
]   # cleanup: the footer, then data's flush, then index's flush

open_archive = (dir:Path) => Archive[
    files.open(p"{dir}/index.txt" 'w') or_throw
    files.open(p"{dir}/data.bin" 'w') or_throw      # fails: the finished index field is cleaned up
]
```

An `Archive` can fail its cleanup three ways; two flushes failing give
`ErrorStack<FileWriteFailed>`, beside the footer's failure if that failed too.

## (a) Implicit

```dewy
pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
}   # footer and two flushes: any failure becomes pack's result
```

## (b) Marked scope

```dewy
pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
} or_throw
```

## (c) Value-tied `defer`

```dewy
pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    defer drop(archive) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
}
```

`archive.close()` would read better, but the type can't offer one yet: a `$__consume__` method
that writes the footer and closes the fields still has the outer hook run at its end, writing the
footer twice. A finishing method needs a way to consume the value without running its hook
(Swift's `discard self`); fields under a hook can't be taken apart today.

## (d) Explicit close

```dewy
pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
    drop(archive) or_throw
}
```

## (e) Disposition on the binding

```dewy
pack = (dir:Path items:array<Item>) => {
    let archive drop or_throw = open_archive(dir) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
}
```

## (f) Finish on success, clean up on failure

```dewy
pack = (dir:Path items:array<Item>) => {
    let archive = open_archive(dir) or_throw
    loop item in items archive.add(item.name item.bytes) or_throw;
} or_throw
```

The hook does work (the footer), so it may fail, and `Archive` owes what its hook and fields owe;
`pack` gets the usual error without the marker. If `Archive` held a writer and a socket instead,
only the writer would count. The marker needs no finishing method and no generic `drop`, so the
`discard self` gap doesn't block (f); it blocks only explicit finishing of user types.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 1 exit, 3 cleanups | 0 | — |
| (b) | 1 token | 0 | 0 | warning |
| (c) | 1 line; needs `drop` | 0 | 0 | warning |
| (d) | 1 line; needs `drop` | 0 | 0 | warning |
| (e) | 1 clause | 0 | 0 | error |
| (f) | 1 token | 0 | 0 | error |
