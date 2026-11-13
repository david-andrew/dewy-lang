# Combining failures: round 7, the last fixes and D42 for open_decisions

This is the last fix round. It answers `review-round6.md`: one must-fix (M1), three should-fixes
(S1–S3) and notes N1–N5. It also takes two inputs from the cancellation round
(`~/dev/tmp/par13/cancel/round5.md`, D44) and writes the paste-ready D42 text in §2. Rounds 5 and
6 stand except where this file amends them. Nothing was compiled. No program changes, so there is
no `programs-r7/` and no `dogfood-round7.md` (see §1.8).

## 1. Fixes

### 1.1 M1: converting a temporary may not drop a failure part

**Rule.** A projection may not drop a failure part from a temporary that dies at that projection.
A projection here is an implicit conversion at an argument, a declared `let`, or an explicit
`as`. A temporary is a call result or any other unnamed value. The fix-its are to bind the value
first or to handle the rest. Projecting from a named place (a variable, an arm binder, a field)
stays allowed under the narrow D1, exactly as for a single failure in a variable.

The check is local and syntactic. At each projection, if the source is not a place and some shape
that can reach it keeps a failure facet outside the selected subset (C1.3), it is an error. The
cost is O(1) per projection on top of the projection's own C1.3 work. Under held, C3-H already
rejects these, and this rule adds nothing.

```dewy
both = ():>E1 | E1 & E2 => E1 and E2
main = () => {
    log_error(both)              # error: E2 would die with the temporary; bind it first, or handle E2
    let first:E1 = both          # error, the same
    let pair = both
    log_error(pair)              # fine: pair keeps E2, like any failure in a variable
}
```

**Your batch 10 sketch still compiles**, both halves of the original in `brief.md`:
- `match combined_fn() …` is a match, not a projection, and its `<E1 & E2>` arm comes first.
- `log_error(result)` and `result as E1`/`result as E2` project from the variable `result`.
- `return r1 & r2` returns the whole pair.

C3-N's gate gains both negative lines above and the `pair` positive.

### 1.2 S1: D1's two missing rows

The rows are in §2's Q1 table: `careless` written as an `if … is?` chain, which compiles under
narrow and is an error under held; and an arm that leaves through another failure, which drops
its unnamed part under narrow and is an error under held. The recommendation now says what
narrow gives up, in its "You give up" line.

### 1.3 C3-N notes (review N1–N3)

- **An arm without a binder that owes** (`<QuotaExceeded> => …` reached by the pair) is an error,
  with two fix-its: put the combination's arm first, or bind it and forward it
  (`q:QuotaExceeded => { …; q or_throw }`).
- **A subject forwarded after the `match`** (`match result { c:FileCloseFailed => printl(c.path) … }`
  then `result or_throw`) is a known false positive, fixed with `c;`. It is listed in C3-N's gate.
- **The arm's value** joins the disposals: an arm whose value is its binder whole, where the
  `match`'s result is stored, returned or forwarded, disposes it.

### 1.4 S2: an atomic write's temporary close is a `FileWriteFailed`

Inside `write_text` and `write_bytes`, a failed close of the temporary file is a
`FileWriteFailed`, because its buffered data may never have reached the file. This replaces
round 5's row "Temporary consume-close itself fails: FileCloseFailed". Removal of the temporary
still adds `FileRemoveFailed` if it fails, and there is no rename. An atomic write's three
outcomes then read from the type alone:

| Failure | Meaning |
|---|---|
| `FileWriteFailed` | the new contents are not installed |
| `FileSyncFailed` (target's path) | installed, but the disk didn't confirm them |
| `FileCloseFailed` (directory's path) | installed and confirmed; only the directory handle's close failed |

`FileRemoveFailed` can accompany the first.

### 1.5 S3: what traces cost, and where

- **Layout per type, filling per site.** Each value of a failure type that some `$trace` read can
  see carries an inline buffer: up to 64 four-byte site ids, plus a count and a truncation flag,
  264 bytes. Every result union that can hold such a value grows by that much. A creation site
  walks the stack only if its value can flow to a `$trace` read, by round 3's flow demand per
  site and per instantiation. Every other site leaves the buffer empty and pays nothing at run
  time.
- **The walk.** A table-driven walk of up to 64 frames costs time in proportion to depth, paid
  once per failure made at a walking site. The estimate, to be measured in the C4.3 gate, is tens
  to a few hundred instructions per frame. If a function's failure can reach a read through any
  caller, its creation site walks for every call. So `to_int(x) ?? 0` in a parse loop pays one
  walk per failed parse when some other `to_int` call flows to a read. Inlined calls are
  specialized by their caller's demand, so those don't pay.
- **The warning.** At each `$trace` read, the compiler warns when its demand gives the buffer to a
  failure type that is created or defaulted inside a loop. The warning names the read, the site,
  the bytes added per value, and whether that site walks. The fix is to read `$trace` on a
  narrower type, after `as`. A debug build, which demands traces for every failure reaching
  `main`, doesn't warn.
- **WebAssembly**, and any target without unwind tables, can't walk frames from inside the
  module. There, `$trace` holds the creation site and the task's start line, marked truncated.
  No shadow stack is added, because that would cost every call.
- **Considered:** a per-thread ring with a 4-byte handle in the value. It is smaller, but a later
  failure can overwrite a trace before anyone reads it.

### 1.6 N4: multi-field structural atoms

`is? [path:string message:string]` is true when one facet provides both fields. That keeps C2's
row 1 correct, because the witnesses are still singletons. A plain record is one structural
source, so a merged plain record still satisfies it.

### 1.7 Inputs from the cancellation round (D44)

- **Stack elements.** A stack may hold any exception except `Canceled`, so two workers' `Stopped`
  failures come back as `ErrorStack[Stopped[1] Stopped[2]]`. A stack is an `error` when every
  element is one, and an `exception` otherwise. This replaces round 5's "elements must fit whole
  in `error`" (C1.3 holding, D16). `cause:error` holds a stack only when the stack is an `error`.
- **`UndoFailed`.** D44 adds a family for undos whose effects persist: `RollbackFailed`,
  `ProcessStopFailed`, and any user type declared `type of UndoFailed`. Q3 points to it. That
  makes `RollbackFailed` both a `DbError` and an `UndoFailed`, and `ProcessStopFailed` both a
  `ProcessError` and an `UndoFailed`. Dewy's minted types have one parent today, so this is
  unresolved between the two rounds. If a leaf may have two parents, C2's intersection fast path
  keeps its row but checks that the atoms have disjoint descendant sets (from the family index)
  instead of relying on single parentage. The cost is the same.
- **D42's cancellation questions** (the spin warning, `$explicit_cancellation`, the exit code)
  move out of D42, with one line pointing to D44. This conflicts with D44's own knock-on edits,
  which keep the exit-code question in D42 for ordinary combinations, with no Ctrl-C example. §2
  leaves it out as directed. If it stays, it needs its own question, with an example such as
  `FileWriteFailed & FileCloseFailed` reaching `main`.
- D44's knock-on edits also add `race`/`first_ok` losers to Q1's consuming actions and `Canceled`'s
  `$origin` to the metatags. §2 points to D44 for both rather than restating them.

### 1.8 Programs and grades

No program changes:
- No program projects a temporary that holds a combination; each binds first or uses `or_throw`.
- No program calls an atomic write expecting a `FileCloseFailed`.
- No program reads `$trace`.

Round 6's grades stand. Program 06 at discoverability 4 is confirmed fair by the review.

## 2. D42 for open_decisions

Paste everything between the two `---` lines in place of the current D42 section of
`docs/design/open_decisions.md`. The "Questions at a glance" lines to match follow it.

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
- `RollbackFailed` and `ProcessStopFailed` are also `UndoFailed`s, D44's family for undos whose effects persist.

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

- **Rec:** `ErrorStack`, your word; `ErrorList` if you'd rather the name say the order. **Reversible** before release.
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
- (a): `D42 Q3: one leaf per operation; FileError becomes the file failures' parent.`
- (b): `D42 Q1, Q2, Q6: no part lost silently (narrow or held); facets and as; a stack stays its own type.`
- (c): `D42 Q4, Q5: ErrorStack or ErrorList; $origin, $trace, $parts, $origin_at_caller.`

## 3. Resolution, finding by finding

| Finding | Resolution | Where |
|---|---|---|
| M1: converting a temporary drops parts under narrow | Projecting a temporary that would drop a failure part is an error; bind first or handle the rest. Local, O(1) per projection. The sketch still compiles | §1.1; D42 Q1 |
| S1: D1 hides two losses | Rows for the `if … is?` chain and the arm leaving through another failure; "You give up" says both | §1.2; D42 Q1 |
| S2: the temporary's close in an atomic write | `FileWriteFailed`; the three outcomes read from the type | §1.4; D42 Q3 |
| S3: trace cost and WebAssembly | 264 bytes per value of a traced type, walks only at sites that can reach a read, a warning in loops, WebAssembly stops at the origin | §1.5; D42 Q5 |
| N1–N3: C3-N details | A binderless owing arm is an error with fix-its; the forwarded-subject false positive is in the gate; the arm's value disposes | §1.3 |
| N4: multi-field structural atom | One facet provides all the fields | §1.6; taken |
| N5: the regrade | Confirmed, unchanged | §1.8 |
| MF3 residual: a hand-made parent packed with a child | Forwarded, nothing lost; kept as a taken item | D42 taken |
| Readiness: D1, D4, D5, D17 edits | Labels, history and "Withdrawn" cut; `poll` dropped; reversibility added; the `$parts` line added; names cold-read (3/3 each, confidence 3–5) | §2 |
| Cancellation inputs | Stack holds any exception except `Canceled`; `UndoFailed` pointed to; D44 referenced, not restated | §1.7; D42 Q3, Q4 |

**Unresolved must-fix: none.** Two cross-round points are open (§1.7): `RollbackFailed` and
`ProcessStopFailed` need two parents to be both resource failures and `UndoFailed`s; and D44's
knock-on edits keep an exit-code question in D42 that §2 leaves out.
