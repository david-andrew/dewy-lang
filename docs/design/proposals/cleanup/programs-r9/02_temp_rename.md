# 02. A temporary file renamed into place

`publish` writes beside the target and renames over it. `publish_if_changed` returns early when
nothing changed. `publish_forgot` lacks the last line: the bug every design should catch.

## (g) Written cleanup

```dewy
import p"@lib/std/files.dewy" as files

publish = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    defer tmp.discard() or_throw        # failure exits only: persist consumes tmp on success
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
}

publish_if_changed = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    defer tmp.discard() or_throw
    if (path.read_text ?? "") =? text { tmp.discard() or_throw; return false }
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
}
```

`publish_forgot`:

```text
error: tmp (TempFile, line 2) is unpublished where publish_forgot ends (line 5).
       Its text would be thrown away.
       Publish it:  tmp.persist(path) or_throw
       or say so:   tmp.discard() or_throw
```

Without the `defer` in `publish`:

```text
warning: tmp (TempFile, line 2) is removed if tmp.write_text fails (line 3), and the removal
         can fail with FileRemoveFailed, leaving the temporary file and its text on disk.
         Report it:  defer tmp.discard() or_throw
```

The removal is a leftover, so this is a warning; at run time a failed removal is discarded.
That answers the review's point that a stray temporary may hold the secret: the editor shows it,
and `$no_discarded_failures` makes it an error. The unpublished text is unfinished work, so
forgetting `persist` is always an error.

`publish_if_changed`'s early exit repeats the discard because the `defer` never covers a success
exit for unpublished work (rule 5). That is the rule doing its job: a `return` added later to a
function that persists at the end would otherwise throw the text away silently.

## (g-auto)

The `defer` lines go. On a failure exit `tmp` is removed by its hook, and a failed removal joins
the leaving failure with nothing written; there is no warning to give. `publish_if_changed` keeps
`tmp.discard() or_throw` at its early exit.

## Scores

| | Added over (a) | Hidden | Forgotten `persist` |
|---|---|---|---|
| (g) | 1 line per function; 1 brace group, 1 call | 0 | error naming the publish |
| (g-auto) | 1 brace group, 1 call | 0 | error naming the publish |

| Obvious | Discoverable | Concise | Safe by default | Complete |
|---|---|---|---|---|
| 5 | 5 | 4 | 5 | 5 |

Concise 4: the early exit says `discard` beside a `defer` that also says it. Python, Go, Rust,
TypeScript and Swift all write nothing for the early exit, and all of them let a forgotten
publish pass silently (Rust's `NamedTempFile` deletes on drop). The repeat is the price of the
error; see round 9, iteration 2.
