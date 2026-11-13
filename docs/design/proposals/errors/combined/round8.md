# Combining failures: round 8, the final D42 section

Paste everything between the two `---` lines in place of the current D42 section of
`docs/design/open_decisions.md`. The matching "Questions at a glance" lines, the amended coverage
contract and a note of what changed follow it.

---

### D42. Combining failures and seeing where each came from

Your design (batch 10): failure values combine with `and`, their type is `E1 & E2`, `as` takes a part out, and two failures of one type need the error stack. These questions settle the rest; the type laws, the compiler's checks and cleanup storage are contracts in the [proposal](proposals/errors/combined/).

The questions about cancellation are in D44.

#### Q1 (b). A failure part disappears only through an action that names it

`is?`, `match` arms and `or_throw<E>` select a failure that has an `E` part. `??<E>` consumes a failure only when every part of it is needed to make an `E`: `??<E1 | E2>` consumes `E1 & E2`, and `??<E1>` passes it on whole. Beyond that the duty is narrow. A `match` arm that takes more than its type names must forward, handle or drop with `;` the rest, and converting a call's result may not drop a failure part. Otherwise a combination kept in a variable is like a single failure kept in a variable.

```dewy
careless = ():>void => {
    match total_bytes {                       # int | QuotaExceeded | Offline | QuotaExceeded & Offline
        quota:QuotaExceeded => printl"quota: {quota.message}"    # error: the pair reaches this arm,
        offline:Offline => printl"network: {offline.message}"    # and its Offline is dropped unnamed
        n:int => printl"{n} bytes"
    }
}   # fix: an arm `both:QuotaExceeded & Offline => …` first, or end the arm with `quota or_throw`
lost_in_call = ():>void => {
    log_quota(check_quota)                    # QuotaExceeded | QuotaExceeded & Offline. Error: Offline
}                                             # would die with the result; bind it first, or handle it
sketch = ():>void => {
    let result = total_bytes
    if result is? QuotaExceeded log_quota(result)     # the shape of your batch 10 sketch
    if result is? QuotaExceeded & Offline printl"{result as QuotaExceeded}, then {result as Offline}"
}
```

The alternative, held, makes a combination owe until something names each part, wherever it is kept:

| Case | Narrow | Held |
|---|---|---|
| `sketch` | compiles | error at its end: `result`'s parts were only read; add `result;` |
| `careless` written as `if r is? QuotaExceeded … else if r is? Offline …` | compiles, and the pair's Offline goes unnamed | error |
| An arm that leaves through another failure: `quota:QuotaExceeded => { send_alert(quota) or_throw; quota or_throw }`, when the alert fails | compiles, and the pair's Offline leaves with the alert's failure | error |
| A failed cleanup replaces a result that holds combinations | compiles; the result is dropped, as any result is | error; close the owner first with `out.close() or_throw` |
| What the compiler checks | each arm that owes, and each conversion of a call's result: local and linear | every place a combination flows, across calls and containers, with conservative errors where it can't prove a case |

The losers of `race` and `first_ok` are consumed whole, as D44 says.

Take this rule with the narrow duty, so that a combination in a variable behaves like a single failure in a variable?

- **Rec:** narrow. Your sketch compiles, a combination is held to the same standard as a single failure, and the check is local and linear. **Reversible** before release: narrow can become held only by rejecting programs that compiled, while held can become narrow without breaking any.
- **You give up:** a combination kept in a variable, or dropped by an arm that leaves through another failure, can be lost unseen, as a single failure can today; and an `if … is?` chain doesn't get the check a `match` arm gets.

#### Q2 (b). Combined values: facets, merged plain records, and `as`

```dewy
User:type = type of any & [id:int name:string]
Settings:type = type of any & [id:int theme:'light' | 'dark']
both_ids = (profile:User & Settings):>string => {
    return "{(profile as User).id}/{(profile as Settings).id}"   # each minted type keeps its own id
}
Size:type = [width:int height:int]
Place:type = [x:int y:int]
area = (box:Size & Place):>int => box.width * box.height      # plain records merge, as today
wrap = (job:int result:Closed<Job> & FileCloseFailed & SocketCloseFailed) => {
    return (result as Closed<Job>) and UploadFailed[job "upload failed" (result as error)]
}   # `as error` takes every error part: FileCloseFailed & SocketCloseFailed
```

Each minted operand of `&` is its own facet with its own fields, and plain records merge into one record, as they do today. A field that several facets declare is reached with `as`. `v as T` keeps every facet that is a `T`, and is an error when those can't form one `T` (two file failures, whose shared `path` would be ambiguous). A later plain-record default still wins.

Take this one rule for every `&`?

- **Rec:** yes; plain-record intersections behave as LANGUAGE.md says. **Reversible** before release.
- **You give up:** reading directly a field that two minted parts both declare; you write `(v as User).id`.

#### Q3 (a). Library failures: one leaf per operation, and a family is never returned bare

```dewy
import p"@lib/std/files.dewy" as files
save = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    loop row in rows out.write_text("{row}\n") or_throw;
}   # a write fails, then the close fails: FileWriteFailed & FileCloseFailed
count_lines = (path:Path) => {
    let text = path.read_text or_throw   # includes FileReadFailed & FileCloseFailed: reads report closes too
    return text.split("\n").length
}
publish = (path:Path text:string) => {
    path.write_text(text) ??<FileSyncFailed> 0 or_throw;   # the new text is in place; only the
}                                                         # disk's confirmation failed
copy_into = (source:Path target:Path) => {
    let out = files.open(target 'w') or_throw
    let input = files.open(source 'r') or_throw   # an open failure with no specific leaf: FileOpenFailed
    out.write_text(input.read_text or_throw) or_throw;
}   # if out's close fails too: FileOpenFailed & FileCloseFailed
```

Each failure the library returns is a leaf, so cleanup never puts a family beside one of its own members:

- **Files**, under `FileError`, which becomes their parent (today it is a sibling), so `:>T | FileError` accepts every file failure. Opening fails with `FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists` or `FileOpenFailed`. Then there is one leaf per operation: `FileReadFailed`, `FileWriteFailed`, `FileSyncFailed`, `FileCloseFailed` and `FileRemoveFailed`. Listing a directory reads; making a directory or renaming writes; removing a directory removes.
- **Atomic writes:** `FileWriteFailed` means the new contents aren't installed (a failed close of the temporary file included), `FileSyncFailed` means installed but not confirmed on disk, and `FileCloseFailed` on the directory's path means installed and confirmed.
- **Sockets**, under `NetError`: `SocketConnectFailed`, `SocketListenFailed`, `SocketAcceptFailed`, `SocketSendFailed`, `SocketReceiveFailed` and `SocketCloseFailed`.
- **Processes**, under `ProcessError`: `SpawnError`, `ProcessWaitFailed` and `ProcessStopFailed`.
- **Databases**, under `DbError`: `QueryFailed`, `CommitFailed` and `RollbackFailed`; D43 names the leaves for opening and beginning.
- A failure can belong to more than one family through `&`: `RollbackFailed:type = type of DbError & UndoFailed` is both a `DbError` and an `UndoFailed`, D44's family for undos whose effects persist. `ProcessStopFailed` is likewise a `ProcessError & UndoFailed`.

Each failure keeps the native reason in its message.

Take this vocabulary, with `FileError` becoming the parent of the file failures?

- **Rec:** yes. **Reversible** before release.
- **You give up:** returning `FileError` as a catch-all from library code, and short results: a function lists each kind it can give, such as `FileWriteFailed & FileCloseFailed`, though `:>T | FileError` still accepts them all.

#### Q4 (c). The error stack's name

```dewy
check_rows = (rows:array<string>) => {
    let problems:array<RowError> = []
    loop i in [0..rows.length) {
        if to_int(rows[i]) is? error problems.push(RowError[i+1 "not a whole number"])
    }
    if problems.length >? 0 return ErrorStack[problems...]
    return rows.length
}
```

The stack is never empty, keeps the order its failures were added in, and may hold any exception except `Canceled` (D44). It is an `error` when all of its elements are.

Name it `ErrorStack` or `ErrorList`?

- **Rec:** `ErrorStack`, your word; `ErrorList` if you'd rather the name say the order. Holding non-error exceptions such as `Stopped` doesn't change this, since both names say "Error" equally. **Reversible** before release.
- **You give up:** with `ErrorStack`, a name that says which end comes first: cold readers weren't sure where its top is.

#### Q5 (c). Metatag names

```dewy
show = (failure:exception):>void => {
    loop part in failure.$parts printl("{part.$origin}: {part}" file=stderr)
}
```

`$origin` is where a failure was made, `$trace` the calls active then, `$parts` the failures inside a combination or stack, and a function tagged `$origin_at_caller` gives its failures its caller's line. They cost nothing unless read. A `$trace` read adds about 264 bytes to each failure of the types it can see, plus a stack walk where those failures are made, and the compiler warns when that lands in a loop. On WebAssembly a trace stops at the origin. D44 gives `Canceled`'s origin.

Take `$origin`, `$trace`, `$parts` and `$origin_at_caller`?

- **Rec:** yes. **Reversible** before release.
- **You give up:** `$location` and `$backtrace`, which read about as well.

#### Q6 (b). Two cleanup failures of one kind

```dewy
import p"@lib/std/files.dewy" as files
save_two = (left:Path right:Path text:string) => {
    let a = files.open(left 'w') or_throw
    let b = files.open(right 'w') or_throw
    a.write_text(text) or_throw;
    b.write_text(text) or_throw;
}
main = () => {
    save_two(p"a.txt" p"b.txt" "hello") ??<FileCloseFailed> void or_throw
}
```

One failed close comes back bare and two come back as a stack, whichever way D40 Q2 decides when cleanup runs:

| Closes that fail | Block end: b, then a, close at `}` | Last use: a closes after line 5, b after line 6 |
|---|---|---|
| one | `FileCloseFailed` | `FileCloseFailed` |
| both | `ErrorStack<FileCloseFailed>`, b's first | `ErrorStack<FileCloseFailed>`, a's first: a's failed close ends `save_two` at line 5, and b closes on the way out |

A body failure of another kind stays beside either shape (`FileWriteFailed & ErrorStack<FileCloseFailed>`). With a stack as a value of its own type, `main`'s handler takes the bare failure and forwards the stack, and an arm `c:FileCloseFailed` always gets one failure, so `c.path` works. `loop part in result.$parts` sees a bare failure and a stack's entries alike. The alternative is for handlers to look inside a stack: `??<FileCloseFailed>` would then take both shapes, but an arm `c:FileCloseFailed` could receive a stack, so `c.path` would need a test first.

Keep a stack a value of its own type, so `??<FileCloseFailed>` takes one failed close and forwards two?

- **Rec:** yes: no exception for one library type, arms keep their type, and the double failure is forwarded, never swallowed. **Reversible** before release.
- **You give up:** one handler for both shapes: to take both you write `??<FileCloseFailed | ErrorStack<FileCloseFailed>>`, or loop over `$parts`.

#### Q7 (b). The exit code of a combined failure

```dewy
main = () => {
    save(p"scores.csv" [Row["ana" 91]]) or_throw   # the write fails, then the close fails:
}   # FileWriteFailed & FileCloseFailed; with table codes FileWriteFailed 3, FileCloseFailed 4, it exits 4
```

A failure reaching the end of `main` is reported part by part, as today. A single kind exits with its code from the table (1, 2, 3, … in declaration order, or its pinned `exit_code`). A combination has no order, so its code must come from a rule that needs none:

- **Highest code among its parts** (a stack: among its elements). Pinned codes, such as `Offline`'s 69, usually sit above the automatic 1, 2, 3, …, so a code someone chose on purpose usually wins over a numbered one.
- **Lowest code.** The first-numbered kind wins, so an automatic 1 beats a pinned 69.
- **One fixed code for every combination.** A script learns only that several things failed, not which.
- **A code of its own for each combination.** The codes run out: a function holding a few resources has over a hundred combinations, past the limit of 100.

Exit with the highest code among the parts?

- **Rec:** yes. **Reversible** before release.
- **You give up:** the code names one part only. A script can't tell from the code that the close also failed; the printed report lists every part.

Dogfooded in 15 programs; every new name was read correctly cold.

**Taken, as direct extensions of your design:**
- `??<E>` consumes when every part belongs to some smallest set of parts that makes an `E`.
- `is?` is true when some part matches; `as T` and `as T?` need a unique part, and naming the leaf fixes an ambiguity.
- An argument or a declared `let` projects from a variable; a declared result, a field or an element holds the whole value.
- Where the compiler can't prove a case, it stops with a fix, and the verdict is the same on every host.
- A one-shot `read_text` closes before it decodes.
- An allocation refusal returns `OutOfMemory` together with every cleanup failure.
- A stack may nest.
- Cleanup puts a parent and its own child (a hand-made `FileError` and a `FileCloseFailed`) in a stack; `and` rejects them.
- A structural selector matches when one part has all of its fields.
- A later default that doesn't fit the merged field type is an error.

For D43: commit consumes its transaction on every outcome, rolling back on failure (`CommitFailed & RollbackFailed` if both fail).

---


"Questions at a glance" lines to match:
- (a): `D42 Q3: one leaf per operation, families never returned bare; FileError becomes the file failures' parent.`
- (b): `D42 Q1, Q2, Q6, Q7: no part lost silently (narrow or held); facets and as; a stack stays its own type; exit code of a combination.`
- (c): `D42 Q4, Q5: ErrorStack or ErrorList; $origin, $trace, $parts, $origin_at_caller.`

## Contract: the coverage shortcut with several families

This replaces round 6 C2's intersection row and round 7 §1.7's adjustment. A facet may now match
more than one family: `RollbackFailed` matches both `DbError` and `UndoFailed`. So "every atom is
matched, and every facet matches some atom" is no longer enough. Take F = `RollbackFailed &
QueryFailed` with S = `DbError & UndoFailed`. Its only minimal witness is {RollbackFailed}, so
`QueryFailed` is not covered and nothing is consumed.

For an intersection of nominal atoms a1 & … & ak, give each facet x a k-bit mask M(x) of the
atoms it matches. Sat(K) holds when the masks in K OR to all k bits.
- **Witness test.** A facet x is in some inclusion-minimal witness exactly when, for some atom j
  that x matches, M(x) OR U_j is all k bits, where U_j is the OR of the masks of the facets that
  don't match j.
  - If so, x together with the facets that miss j is a witness in which x alone supplies j.
    Removing other redundant facets keeps x needed, which leaves a minimal witness containing x.
  - Conversely, any witness in which x is needed for j uses only facets that miss j, and their
    masks are all in U_j.
- **Covered(F,S)** holds when the masks of F OR to all k bits and every facet passes the witness
  test.
- **Cost.** Computing the k masks and the U_j takes O(f·k) membership tests, through the family
  index. Each test is a word operation on k-bit masks, so the total is O(f·k·⌈k/w⌉), linear in
  the facet count. With single parentage this gives exactly round 6's answer.

The union and complement rows are unchanged, since they never relied on single parentage. A
complement conjoined with the intersection still requires that no facet match it. Selection by
`is?` and arms is unaffected, since it stays existential. C1.2's overlap test still compares
supplied identities: `RollbackFailed` and `QueryFailed` share a family, but neither is the
other's ancestor, so `and` accepts them.

## What changed from round 7

1. Q3: a failure can belong to two families through `&` (`RollbackFailed:type = type of DbError & UndoFailed`), an ordinary intersection.
2. The coverage shortcut for intersections uses per-facet masks; it stays O(f·k), and the old single-parent rule was wrong for `RollbackFailed & QueryFailed`.
3. New Q7: a combination exits with the highest code among its parts, weighed against lowest, one fixed code, and a code per combination, with no Ctrl-C example.
4. Q4: the stack holding non-error exceptions doesn't change `ErrorStack` versus `ErrorList`.
5. "Questions at a glance": Q7 joins (b), and the (a) line says that families are never returned bare.
