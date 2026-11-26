# 02. A temporary file renamed into place

`publish` writes beside the target and renames over it, so readers see the old contents or the
new, never half. `publish_if_changed` returns early when nothing changed. `publish_forgot` is the
same as `publish` without the last line: the bug every approach should catch.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files

publish = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    tmp.write_text(text) or_throw;      # a failure here abandons tmp: the temporary is removed
    tmp.persist(path) or_throw          # flush, sync, rename over path; consumes tmp
}

publish_if_changed = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    if (path.read_text ?? "") =? text return false    # tmp is abandoned here
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
}

publish_forgot = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    tmp.write_text(text) or_throw;
}   # abandoned: the temporary is removed, path keeps its old text, and publish_forgot succeeds
```

`publish_forgot` returns success having published nothing; if removing the temporary fails,
`FileRemoveFailed` becomes its result instead, which names the wrong problem.

## (b) Marked scope

```dewy
publish = (path:Path text:string) => {           # no marker: tmp is consumed on the success path
    let tmp = files.temp_beside(path) or_throw
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
}

publish_if_changed = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    if (path.read_text ?? "") =? text return false
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
} or_throw      # covers the removal on `return false`

publish_forgot = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    tmp.write_text(text) or_throw;
} or_throw      # silences the warning; the text is still thrown away
```

Unmarked, `publish_forgot` warns that `tmp`'s removal can fail. The warning is about the wrong
thing, and its fix-it (the marker) leaves the bug in place.

## (c) Value-tied `defer`

```dewy
publish = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    defer tmp.discard() or_throw        # canceled on the path where persist consumes tmp
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
}

publish_if_changed = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    defer tmp.discard() or_throw
    if (path.read_text ?? "") =? text return false
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
}

publish_wrong = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    defer tmp.persist(path) or_throw    # the habit from Go's `defer tx.Commit()`
    tmp.write_text(text) or_throw;      # fails: the defer still runs, and publishes half the text
}
```

A fallible `defer` invites `publish_wrong`: work that should happen only on success runs on
every exit. Zig has `errdefer` for the opposite asymmetry; nothing here stops this one. A
forgotten `persist` with the `defer discard` written is silent.

## (d) Explicit close

```dewy
publish = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
}

publish_if_changed = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    if (path.read_text ?? "") =? text { tmp.discard() or_throw; return false }
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
}
```

`publish_forgot` warns at `}` that `tmp`'s removal failure is discarded, which happens to point
at the bug. The suggested fix (`tmp.discard() or_throw`) hides it.

## (e) Disposition on the binding

```dewy
publish_if_changed = (path:Path text:string) => {
    let tmp drop or_throw = files.temp_beside(path) or_throw
    if (path.read_text ?? "") =? text return false
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
}
```

`publish_forgot` with the clause compiles and silently discards.

## (f) Finish on success, clean up on failure

```dewy
publish = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
}

publish_if_changed = (path:Path text:string) => {
    let tmp = files.temp_beside(path) or_throw
    if (path.read_text ?? "") =? text { tmp.discard(); return false }   # discard can't fail
    tmp.write_text(text) or_throw;
    tmp.persist(path) or_throw
    true
}
```

`publish_forgot`:

```text
error: tmp (TempFile, line 2) is unpublished where publish_forgot ends (line 4).
       Its text would be thrown away.
       Publish it:  tmp.persist(path) or_throw
       or say so:   tmp.discard()
```

A failing write needs nothing: on that exit `tmp` is abandoned and the temporary removed.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten `persist` |
|---|---|---|---|---|
| (a) | — | 1 | 0 | silent: success, nothing published |
| (b) | 1 token | 0 | 0 | warning about the removal; the fix-it keeps the bug |
| (c) | 2 lines | 0 | 0 | silent with the `defer`; `defer persist` publishes on failure |
| (d) | 1 brace group, 1 call | 0 | 0 | warning about the removal |
| (e) | 1 clause | 0 | 0 | silent |
| (f) | 1 brace group, 1 call | 0 | 0 | error that names the forgotten publish |
