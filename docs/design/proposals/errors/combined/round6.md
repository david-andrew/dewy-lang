# Combining failures: round 6, fixing the round 5 review

This round answers `review-round5.md`: its three must-fixes (MF1–MF3), six should-fixes and
eight notes. Round 5 stands except where this file amends it. Part 1 now holds nine questions:
D1–D8 and D17. D9–D16 become one-line taken items, and D13 moves to the database round. Binding
context: decisions.md batch 10, D40 and D42 in open_decisions.md, and AGENTS.md rule 6. Nothing was
compiled. The programs are paper programs.

**What changed for David.** D1 now carries the policy that round 5 had hidden in D10: does a
combination held in a variable have to be handled when a single failure needn't be? The narrow
answer, recommended here, removes MF1 and MF2 and most of the compiler check. D5 gives every
family a concrete leaf, so a parent never appears beside its own child (MF3), and takes
`FileSyncFailed` from D14. D17 shows the caller, under both answers to D40 Q2. D4's `wrap` no
longer uses `Canceled` as data. D2, D3, D6, D7 and D8 are unchanged.

# Part 1: decisions for David

### D1. A failure part disappears only through an action that names it

`is?`, `match` arms and `or_throw<E>` select a failure that has an `E` part. `??<E>` consumes a
failure only when every part of it is needed to make an `E`; `~` is no exception, so
`??<~Canceled>` never consumes `Canceled & E1`. A `match` arm binds the whole value, so the arm must
forward, handle or drop with `;` whatever its type doesn't name.

```dewy
report = ():>void => {
    match total_bytes {                       # int | QuotaExceeded | Offline | QuotaExceeded & Offline
        both:QuotaExceeded & Offline => printl"both failed: {both}"
        quota:QuotaExceeded => printl"quota: {quota.message}"    # only QuotaExceeded alone reaches here
        offline:Offline => printl"network: {offline.message}"
        n:int => printl"{n} bytes"
    }
}
careless = ():>void => {
    match total_bytes {
        quota:QuotaExceeded => printl"quota: {quota.message}"    # error: this arm also takes the pair,
        offline:Offline => printl"network: {offline.message}"    # and its Offline is dropped unnamed
        n:int => printl"{n} bytes"
    }
}
poll = (sensor:Sensor) => {
    loop true {
        let reading = sensor.read(timeout=1s) ??<~Canceled> continue or_throw   # Canceled, alone or
        record(reading)                                                      # combined, leaves poll
    }
}
```

**The choice inside it: does a combination kept in a variable have to be handled?** Your
batch 10 sketch, in Dewy spelling:

```dewy
E1:type = type of error
E2:type = type of error
combined_fn = ():>int | E1 | E2 | E1 & E2 => E1 and E2
log_error = (e:E1):>void => printl(e)
main = () => {
    let result = combined_fn
    if result is? E1 log_error(result)          # "works if E1 or E1 & E2 was returned"
    if result is? E1 & E2 {
        let e1 = result as E1
        let e2 = result as E2
        printl"{e1} then {e2}"
    }
}
```

The sketch's `match` half compiles under both rules, because each of its arms names every part
that reaches it (the pair arm comes first). The rules differ on this half:

- **Narrow (recommended):** only a `match` arm owes anything. A combination in a variable
  behaves like a single failure in a variable: you may test it, read its parts and let it go.
  `main` compiles. An arm that takes more than its type names must pass the value on (`or_throw`,
  `return`, storing it whole, or passing it to a parameter that holds it whole), handle the rest,
  or drop it with `;`. This is Dewy's existing rule for a failure that a statement expresses
  ("propagated, handled or discarded with `;`"), applied to the part an arm leaves unnamed.
- **Held (round 5):** a combination owes until something names each part, wherever it is kept.
  `main` is an error at its end, because `result`'s E1 and E2 were only tested and read; the fix
  is `result;`. The same `main` compiles if `combined_fn` can return only `E1`.

The common shapes under each rule:

```dewy
import p"@lib/std/files.dewy" as files
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
gather = (log:Path) => {
    let out = files.open(log 'w') or_throw
    let found = [pair pair]                   # array<A & B>
    out.write_text("gathered\n") or_throw;
    return found
}   # if out's close fails, gather's result is that FileCloseFailed and found is dropped
```

| Case | Narrow | Held |
|---|---|---|
| `careless` above | error | error |
| `let n = pair ??<A> 0`, then `total += n` | type error: `n` can still be `A & B` | the same |
| `gather`: the log's close fails after the failures were collected (MF1) | compiles; `found` is dropped, as D40 Q1 already does with any result a failed cleanup replaces | error; close first with `out.close() or_throw` |
| An allocation is refused while a local holds `A & B` (MF2) | compiles; the local is dropped with the frame, like any local | the pair joins the result, `OutOfMemory & A & B`; a held `array<A & B>` there is an error |
| A loop that handles only some elements of an `array<A & B>` | compiles | error unless every path handles every element |
| What the compiler checks | each such arm, like a definite-assignment check | the whole program's flow of combinations, with conservative errors when it can't prove a case |

**Question:** take the narrow rule? A combination kept in a variable is then treated like any
single failure kept in a variable, and only a `match` arm that takes more than its type names must
deal with the rest.

**Rec:** narrow. Your sketch compiles. There is no rule that holds a combination to a stricter
standard than a single failure. Both of your batch 10 concerns are still met: a handler can't
swallow a part (`??<E>` consumes only covered values, and the arm rule), and a declared result
can't hide one (`:>int | E1` can't return `E1 & E2`). The cost is that a combination stored in a
variable and never looked at again is lost silently, exactly as a single failure is today. Any use
of it as a success still forces handling, because its type keeps every part. **Reversible:**
before release. Narrow can become held later only by rejecting programs that compiled; held can
become narrow later without breaking any.

### D2. A warning for a loop that may retry at once after cancellation

```dewy
worker = (jobs:Receiver<Job>) => {
    loop true {
        let job = jobs.receive ?? continue    # warning: this loop may retry immediately after
        process(job)                          # cancellation; write ??<~Canceled> continue or_throw
    }
}
```

It fires when a `??` that can consume `Canceled` is on a wait (directly or through a call that can
return `Canceled` from a wait) and its fallback goes back round the loop. It is a hint, not a
proof: a wait inside a callback isn't seen, and a loop with its own deadline is fine. **Rec:** yes.

### D3. What `$explicit_cancellation` checks now

```dewy
ask = () => {
    $explicit_cancellation
    let rounds = input_int("rounds? ") ?? 10     # error: this `??` can consume Canceled; write
    play(rounds)                                 # ??<~Canceled> 10 or ??<Canceled | …> 10
}
```

Under the tag (in `$bulletproof`), a handler or arm that can consume `Canceled` must name it,
positively or as `~Canceled`, after aliases are expanded. Storing `Canceled` in a collection isn't
consuming it, so collectors need nothing. **Rec:** yes.

### D4. Combined values: facets, merged plain records, and `as`

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

One rule for every `&`: each minted operand is its own facet with its own fields, and all plain
records merge into one record (today's rule). A field more than one of these declares is reached
with `as`. Membership and field constraints commute; constructor defaults retain their existing
source order: a later plain-record default wins, including through aliases. `v as T` keeps every facet that is a `T` (the "subset" David described), and is an error
when the kept facets can't form a `T` (two `FileError`s, whose shared `path` would be ambiguous).
**Rec:** yes. It changes nothing existing: plain-record intersections behave as LANGUAGE.md says.

Changed from round 5: `wrap` now uses `Closed<Job>`, a channel's exception that is ordinary data,
in place of `Canceled`, which the cancellation round confines to the work it cancels. The rule it
shows is the same.

### D5. Library failure vocabulary: one leaf per operation, and a family is never returned bare

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

One type per operation, under a family per resource. A family is a parent that the library never
returns on its own, so cleanup never puts a parent beside its own child. Round 5's "the family's
generic failure" would have done exactly that: `FileError & FileCloseFailed`.

- **Files**, under `FileError`, which becomes their parent (today it is a sibling, so
  `:>T | FileError` will accept every file failure). Opening fails with `FileNotFound`,
  `FileAccessDenied`, `IsDirectory`, `FileExists`, or **`FileOpenFailed`** for any other reason.
  After that there is one leaf per operation: `FileReadFailed`, `FileWriteFailed`,
  **`FileSyncFailed`**, `FileCloseFailed` and `FileRemoveFailed`. Path operations use the nearest
  of these. Listing a directory or reading a size reads; making a directory or renaming writes;
  removing a directory removes. A symbolic link that a contained path refuses is
  `FileAccessDenied`.
- **Atomic writes** (`write_text`, `write_bytes`) give `FileWriteFailed` until the new file is in
  place and `FileSyncFailed` after it, meaning the new contents are installed but the disk didn't
  confirm them. A failed close of the directory is a `FileCloseFailed` with the directory's path.
  This replaces round 5's D14 `replaced` member.
- **Sockets**, under `NetError`: `SocketConnectFailed`, `SocketListenFailed`,
  **`SocketAcceptFailed`**, `SocketSendFailed`, `SocketReceiveFailed` and `SocketCloseFailed`.
- **Processes**, under `ProcessError`: `SpawnError`, `ProcessWaitFailed` and `ProcessStopFailed`.
- **Databases**, under `DbError`: `QueryFailed`, `CommitFailed` and `RollbackFailed`. The leaves
  for opening a database and beginning a transaction belong to the database round (D43).

Each failure keeps the native reason in its message. The cold read read every earlier name
correctly, mostly 5/5. Four names are untested and queued for a cold read in `names-r6.txt`:
`FileOpenFailed`, `FileSyncFailed`, `SocketAcceptFailed` and `FileRemoveFailed` (round 4's).
**Rec:** yes, keeping only the new names that read correctly. **Reversible:** before release.

### D6. The error stack's name

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

Cold read: `ErrorStack` 3/3/3 (readers unsure which end is the top), `ErrorList` 4/4/3 ("kept in
the order written"), `Errors` 3/4/3. **Rec:** `ErrorStack`, your word; `ErrorList` if you'd rather
the name say the order.

### D7. The exit status of a combined failure: the highest code among its parts

```dewy
main = () => {
    save_frames(frames p"capture.bin") or_throw   # Ctrl-C, then the close fails:
}                                                 # Canceled & FileCloseFailed, exit 130
```

A failure reaching the end of `main` is reported part by part, as today, and exits with its kinds'
code; a combination or stack exits with the highest of its parts' codes, so a cancellation (130)
outranks the cleanup failures it caused, by number and not by a special case. A successful `main`
exits 0; `exit(n)` exits `n`. **Rec:** highest code. The alternative, the lowest code, makes the
close failure's code win here.

### D8. Metatag names

```dewy
show = (failure:exception):>void => {
    loop part in failure.$parts printl("{part.$origin}: {part}" file=stderr)
}
```

Cold read: `$origin` 4/4/4 (as good as `$location`, better than `$where`); `$trace` and
`$backtrace` both good; `$parts` and `$failures` tie; `$origin_at_caller` 4/4/3, the best of its
three. **Rec:** `$origin`, `$trace`, `$parts`, `$origin_at_caller`.

### D17. Two cleanup failures of one kind: what the caller gets, and whether a handler looks inside a stack

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

One failed close comes back bare, and two come back as a stack, whichever way D40 Q2 decides when
cleanup runs:

| Closes that fail | Block end: b, then a, close at `}` | Last use: a closes after line 5, b after line 6 |
|---|---|---|
| one | `FileCloseFailed` | `FileCloseFailed` |
| both | `ErrorStack<FileCloseFailed>`, b's first | `ErrorStack<FileCloseFailed>`, a's first: a's failed close ends `save_two` at line 5, and b closes on the way out |

A body failure of another kind stays a peer of either shape (`FileWriteFailed & FileCloseFailed`,
`FileWriteFailed & ErrorStack<FileCloseFailed>`). Your rule for `a and b` is unchanged: two
failures of one type written by hand are still a compile error pointing to the stack.

What `main`'s handler does with each shape:

- **(a) A stack is a value of its own type** (round 5's D16 rule). `??<FileCloseFailed>` takes
  the bare failure, and the stack goes on through `or_throw`. To take both, name both:
  `??<FileCloseFailed | ErrorStack<FileCloseFailed>> void`. An arm `c:FileCloseFailed` always
  receives one failure, so `c.path` works.
- **(b) Handlers look inside a stack.** `is?`, arms and `or_throw<E>` match a stack when some
  element matches, and `??<E>` takes it when every element is covered. `??<FileCloseFailed>` then
  takes both shapes. But an arm `c:FileCloseFailed` can now receive a stack, so `c.path` needs a
  test first, and `as FileCloseFailed` on a stack is an error: you loop over it instead.

Withdrawn: round 5 grouped failures by the owners that were live at each exit, so a single failed
close could come back as a one-entry stack. Which one came back depended on D40 Q2 and on which
owner failed, and the handler above missed it (dogfood discoverability 3).

**Question:** take (a)? **Rec:** (a). It makes no exception for one library type, an arm keeps
its type, and the common one-failure case is taken by the handler anyone writes first. The rare
double failure is forwarded, never swallowed, and hover lists
`ErrorStack<FileCloseFailed>` among `save_two`'s results. (b) covers every shape with one handler,
at the price of one exception and a weaker ordinary arm. **Reversible:** before release. After
that, either change alters which handler runs.

## Taken, report only

These are direct extensions of decided rules. Round 5's own taken items stand.

- **D1, clarified:** `??<E>` consumes when its inclusion-minimal witnesses cover every part (round 5
  C2). It is the precise reading of D1, not a new choice.
- **D9:** `is?` stays existential; plain `as T` and `as T?` both need a unique projection, and the
  fix for ambiguity is to name the leaf.
- **D10:** copies, block results and storage never remove a part; only a naming action does. Under
  the narrow D1 nothing else follows. Under held, round 5's transport rules apply, amended in C3-H.
- **D11:** where the check can't prove a case, compilation stops with a fix and never passes the
  failure through; the verdict comes from a fixed work count, so it is the same on every host.
- **D12:** a one-shot `read_text` finishes its close before it decodes.
- **D13:** moved to the database round (see "For D43").
- **D14:** folded into D5 as `FileSyncFailed`; the `replaced` member and its marker failure are gone.
- **D15:** an allocation refusal returns `OutOfMemory` plus every cleanup failure. Under held, held
  combinations join that result too (MF2).
- **D16:** a stack is nonempty, holds whole errors only, may nest, keeps push order and has
  segmented-storage costs. Its selector clause moved into D17. The explicit `xs;` after iterating
  a stack applies only under held.
- **Overlap at cleanup:** automatic cleanup treats a parent and its child (a hand-made bare
  `FileError` body failure and a `FileCloseFailed`) like two of one kind and packs them into a
  stack. A hand-written `and` still rejects them.
- **Traces:** reading `$trace` costs nothing per call (C4.1); a trace lives in a fixed buffer
  inside the failure. This removes round 5's call-entry reservation (review SF4).
- **Structural selectors** are existential like nominal ones, so `??<[message:string]>` consumes
  `Quota & Offline`. Reading `.message` still needs a unique provider (N1).
- **A local `let` with a declared type projects** like a parameter (D9); parent-typed storage
  still keeps a child's identity, as LANGUAGE.md says. A declared result, a field and an element
  hold the value whole (N2).
- **A later default that doesn't fit** the merged field type is an error. In a named intersection
  the error is at the declaration, as a field type conflict already is; in an unnamed one it is at
  the construction that would use the default (N8).

## For D43, the database round

- Commit consumes the transaction on every outcome. A failed commit attempts a rollback before it
  returns, giving `CommitFailed & RollbackFailed` if both fail; there is no second automatic
  abandon (round 5's D13 and C5.4). D43 owns `commit`, `rollback` and the transaction API, so
  it decides this.
- `DbError` is a family the library never returns bare. D43 names the leaves for opening a database
  and beginning a transaction, and cold-reads them.
- A `$__abandon__` hook returning `DbError` can carry the driver's text in a fixed-size inline
  field of its reserved slot, cut to fit (C4.1).

# Part 2: contracts, conditional on Part 1

Round 5's C1–C7 stand except as amended here. C3 has two versions: C3-N ships if David takes the
narrow D1, and C3-H if he takes held. Everything else is the same under both.

## C1. Selection, projection and defaults (amends round 5 C1)

- **Structural atoms are existential for selection (N1).** `K is? [f:T]` is true when some facet
  of K provides `f` of type T. Reads of `.f` and projection still need exactly one provider
  (C1.3 steps 1–5). C2's witnesses then treat structural atoms as they treat nominal ones.
- **A declared local `let` projects (N2)** with the same checked unique projection as an argument;
  the source keeps the value whole. A declared result, a field and an element hold the value
  whole (C1.3 holding). Under C3-H, the projection carries the selected parts' duty as an
  argument's does.
- **An ill-fitting later default (N8).** The ordered default stream is unchanged. If the last
  applicable default doesn't satisfy the merged field type, a named intersection
  (`Name:type = Right & Left`) is an error at the declaration, which already happens for
  conflicting field types. An unnamed intersection is an error at a construction that would use
  that default. A use that only tests or holds values is unaffected.
- The stack clause of C1.3 stands under D17 (a): a stack is a nominal value, and a nested
  `ErrorStack<A>` does not make `is? A` true. Under (b), C1.3 changes as D17 describes, and C2
  takes a stack's elements as its facets for `??<E>`.

## C2. Coverage: a linear fast path and a deterministic budget (review SF5)

Round 5's definition stands: `??<S>` consumes exactly Covered(F,S), the case where its
inclusion-minimal witnesses cover F. After alias expansion and normalization, the common
selector forms are decided directly, in time linear in the facet count f:

| Selector form | Covered(F,S) | Time |
|---|---|---|
| Union of positive atoms `a1 \| … \| ak` (nominal, or structural per C1) | every facet of F matches some atom; the witnesses are the matching singletons | O(f·k) |
| Intersection of pairwise unrelated nominal atoms `a1 & … & ak` | every atom is matched by some facet, and every facet matches some atom; single parentage means one facet matches at most one atom, so each witness takes one facet per atom | O(f·k) |
| Either form with nominal complements `& ~c1 & … & ~cm` | no facet matches any `ci`, and the positive part is covered; complements then hold on every subset, so the witnesses are unchanged | O(f·(k+m)) |
| A complement alone, `~c1 & … & ~cm` | no facet matches any `ci`; every facet is then a singleton witness | O(f·m) |

`??<E1 | E2>`, `??<FileError>`, `??<~Canceled>`, `??<A & B>` and `??<error & ~Canceled>` all
take the fast path. Anything else (a union inside an intersection, a negated compound, a
structural atom inside an intersection) uses round 5's subset solver, O(2^f·(L+f)).

**Budget.** The solver counts work units (one unit per predicate node evaluated on a mask), up to
a fixed limit that is a constant of the compiler version and not a setting. Running out stops
compilation at that selector with D11's diagnostic, so a given program and compiler version get
the same verdict on every host. The gate checks that every fast-path form agrees with the solver
on the 5,700-case oracle set from round 5, and adds 17- and 24-facet cases of each form.

## C3-N. The arm check (ships under the narrow D1)

**Where it runs.** For each `match`, the shapes that can reach an arm are the subject's inferred
alternatives minus those taken by earlier arms. An arm **owes** when some reaching shape is not
Covered by the arm's type (C2). Only owing arms are checked. An arm on a subject without
combinations never owes, and nor does an arm whose type names every part of every shape that
reaches it.

**Members.** These are the arm's binder, every immutable `let` inside the arm initialized directly
from a member, and the result of a non-consuming `??` applied to a member. Projections, field
reads and mutable variables are not members.

**Disposals.** A disposal is any of these, applied to a member:
- `or_throw` or `return` of it as the whole value;
- a `??<S>` that consumes every shape reaching it;
- a nested `match`, whose own arms are then checked;
- `;`;
- storing it whole in a field, element, capture or outer variable whose type holds it;
- passing it to a parameter whose declared type holds it whole, such as `e:error`.

**Rule.** A forward must-analysis runs over the arm's control-flow graph with one bit, "a member
has been disposed", combined with AND at joins. The bit must be set on every path that leaves the
arm without propagating a failure: falling off the arm's end, `break`, `continue` and `return`.
A path that leaves through another failure (`log(x) or_throw` failing, or a cleanup failure)
drops the binder with the frame, like any local. Implicit exits (an allocation refusal under
`$explicit_allocation_failure`, a panic) are treated the same way. Neither is a path the arm wrote
to finish normally. The diagnostic names the arm, the parts its type leaves unnamed and the first
path that misses a disposal, with fix-its: add an arm for the combination, or end the arm with
`or_throw` or `;`.

**Cost.** Members come from one pass over the arm. The bit is a boolean lattice, so loops settle in
at most two passes. The check is O(n) in the arm's size; reaching shapes cost O(s·k) C2 tests per
`match` with s shapes and k arms. Over the program this is linear in the size of the owing arms,
plus the per-`match` shape work that type inference already does. There are no summaries, no
container tracking, no budget and no host dependence. Its only precision limit is the one that
definite assignment has: correlated `if`s inside an arm are rejected, and `if`/`else` fixes them.

**Gate.** Negatives: `careless`; an arm that reads a field and falls off; an arm that disposes on
one branch only; an arm that passes its binder to a projecting parameter; a `break` before
disposal. Positives: `or_throw`, `return`, `;`, a covering `??`, a covering nested `match`,
`errors.push(c)` into an `array<error>`, `log_any(c)` taking `e:error`, a wrapper's
`cause=c`, an exit through another failure, and your batch 10 sketch. Measure instructions on the
flagship panel and the self-build before and after on one named host, and report the number of
owing arms.

## C3-H. The held check (only if David takes held)

Round 5's C3 stands, with these repairs:

- **MF1.** A fallible cleanup edge reached while a withheld success still owes parts is a reachable
  drop. The diagnostic offers two fixes: finish the owner first (`out.close() or_throw`, D40 Q6
  form A), or handle the duty before returning. `gather` (D1) joins the required negatives.
- **MF2.** Allocation-refusal edges are exits for the check. On such an exit, each held local that
  owes and fits `error` whole joins the boundary's result as a cleanup failure does
  (`OutOfMemory & A & B`), retained by reference. One 8-byte link per such local is reserved in
  the function's capsule (C4.3 cost). A held value that owes but can't be a failure part (an
  `array<A & B>`) makes the refusal edge a reachable drop, with fix-its: hold it as an
  `ErrorStack`, or handle it before the allocating statement. Round 5's `describe` and an array
  variant join the negatives.
- **SF6.** A write through a mutable borrowed parameter (`collect = (@sink:array<A & B>) =>
  sink.push(pair)`) transfers the duty to the caller's place, and the summary exports it to that
  parameter. That case joins the gate.
- **The bound for the analysis that ships (M4, SF5).** The merged abstraction keeps one state per
  CFG node:
  - may-owe bits and may-hold associations, joined by union;
  - must-hold and all-coverage associations, joined by intersection;
  - bucket populations, widened in {0, 1, 2 or more}.

  Let T be the token and bucket labels (at most 2(O+R), as in round 5), P the part slots, and A
  the place–label association entries the function actually creates. A is sparse and at most
  3·R·T. Every fact moves one way, so a node's state changes at most I = T·P + 3A + 2T times. An
  edge is reprocessed only when its source changes, and one transfer costs O(T·P/w + A) with
  w-bit words. Within one function that gives O(E·I·(T·P/w + A)) time and O(V·(T·P/w + A))
  memory.

  Each demanded function instance f has one merged summary: a relation from its parameter labels
  (Π_f) to result and escape labels, with owed-part bits, of size at most
  Σ_f = (Π_f + 1)·(Π_f + Fr_f)·P, where Fr_f is its fresh result labels. Summaries only grow, so
  a function in a recursive SCC is reanalyzed at most Σ_f + 1 times. The whole-program bound is
  O(Σ over f of (Σ_f + 1)·E_f·I_f·(T_f·P/w + A_f)): polynomial, and in the worst case about the
  fifth power of a function's size when every place holds combinations. T, P and A count only
  demanded compound flows. Round 5's valuation sets become an optional local precision step under
  the same budget. The budget is counted in transfer applications, a constant of the compiler
  version.
- D16's explicit `xs;` after a read-only stack loop stays, and so do D11's container and
  correlated-call limits.

## C4. Storage and refusal (amends round 5 C4)

- **Traces without call-entry reservation (review SF4, M8).** Round 5's "frame chain reserved as
  calls enter" is withdrawn:
  - **Where a trace lives.** Each value of a type that some `$trace` read can see carries a fixed
    inline buffer of at most 64 four-byte site ids (round 1's cap) and a count with a truncation
    flag.
  - **How it is filled.** When the failure is made, the native frames are walked with unwind
    tables. This costs time in proportion to depth, on the failure path only, plus binary size
    for the tables. No instruction is added to any call.
  - **Cleanup failures.** The buffer is part of the slot reserved at acquisition, and it is filled
    during completion while the frames still exist (C4.2 walks owners before it jumps).
  - **Tasks.** A task's trace ends with its start line, which the task record already holds.
  - **Effects.** Nothing on this path allocates, so no effect row changes, and a `no allocates`
    callback stays valid wherever `$trace` is read.
  - **Size.** A result union holding a traced failure grows by about 264 bytes. That is measured
    in the C4.3 gate, and if it is too costly the gate may lower the cap; the trace shows the cut
    as truncation.
- **Native text in a slot (N5).** A reserved slot may carry a fixed inline text field (proposed:
  128 bytes, cut to fit, with a flag) for native error text known only at failure time. Where the
  codes are known, it can use a static code-to-message table instead. Hook results such as D40
  Q4's `$__abandon__ = ():>void | DbError => db_rollback(handle)` use the same field.
- **A second refusal (N6).** Each recoverable boundary's unwind record reserves one stack link.
  It is used when the boundary's refusal meets an `OutOfMemory` already in the pending value: an
  inner boundary returned `OutOfMemory & FileCloseFailed`, and then the outer function's
  allocation is refused. The result is `ErrorStack<OutOfMemory> & FileCloseFailed`, packaged as
  in C5.1. One link per boundary is enough, because a boundary handles at most one refusal before
  it returns.
- **Withheld successes.** Under the narrow D1, a withheld success is plain data, and D40 Q1 drops
  it when cleanup fails (C4.1 as written). Under held, C3-H's MF1 rule applies first.

## C5. Completion (amends round 5 C5)

### C5.1 Mapping and packaging

- **Leaves only (MF3).** Native failures map as D5 lists. No library function returns a bare
  `FileError`, `NetError`, `ProcessError` or `DbError`, and the adapter fault tests check that
  every returned failure is a leaf. Unmapped native reasons become `FileOpenFailed`, the
  operation's leaf or `SocketAcceptFailed`, with the reason in the message.
- **Packaging under D17 (a).** At each exit, completion collects the pending contributions (a
  failure already being returned, which may itself be a stack) and the cleanup failures, in
  execution order. Contributions whose identities overlap form one class: the same leaf, or a
  parent and its descendant, after generic substitution. A class with one failure stays bare. A
  class with two or more becomes an `ErrorStack` of the nearest common family (for one leaf, that
  leaf), with pending contributions first and then cleanup in execution order. A pending stack of
  the class is extended logically, without changing its storage. Classes are peers in the
  combination, which has no order. Wherever a class can hold one failure or several, the
  inferred result lists both shapes. Linking uses the slots' reserved headers (C4.3), with the
  first failed slot's header as the stack's head, so packaging never allocates. A hand-written
  `a and b` still rejects any overlap (C1.2).

### C5.3 Atomic writes after the rename (replaces round 5's post-rename rows and its marker)

The rows before the rename are unchanged, minus the replacement flag. Every reservation precedes
the rename, so nothing after it allocates.

| Stage / observed failure | Result contributions |
|---|---|
| Rename succeeds | Target installed; the temporary name is no longer owned; cleanup never removes the target |
| The directory can't be opened | `FileSyncFailed` (target's path); no directory handle to close |
| Directory sync fails | `FileSyncFailed`; consume-close the directory once, adding `FileCloseFailed` (directory's path) if observed |
| Sync succeeds, directory close fails | `FileCloseFailed` (directory's path) alone; the sync already confirmed durability |
| Directory close succeeds | Byte count |
| Recoverable refusal | Only before the rename (round 5's row); none can occur after it |
| Cancellation | Per the cancellation round. If it can interrupt the directory sync, the result is `Canceled & FileSyncFailed`, because the sync did not complete |

`FileSyncFailed` always means "the new contents are installed; durability is not confirmed", and
`FileWriteFailed` always means "this operation did not install its file". No failure is invented
to carry state.

### C5.4 moves to D43.

## C6, C7

C6 is unchanged. C7's trace demand stands, with storage and cost as in C4.1: demanded traces add
no cost per call and no allocation.

# Resolution, finding by finding

| Finding | Resolution | Where |
|---|---|---|
| MF1: a failed cleanup drops a withheld success that carries combinations | Narrow: no duty, so the success is dropped as plain data, as D40 Q1 already decides. Held: a reachable drop, with fix-its to close first or handle first; `gather` is a required negative | D1 table; C3-H; C4 |
| MF2: an allocation-refusal exit drops a held combination | Narrow: dropped with the frame like any local. Held: refusal edges are exits; a held combination joins `OutOfMemory & A & B` through a reserved link; a held `array<A & B>` is rejected | D1 table; C3-H; D15 taken |
| MF3: `FileError` beside its own child | A family is never returned bare; `FileOpenFailed` and `SocketAcceptFailed` fill the gaps, and DbError's go to D43; cleanup packs any overlap that user code makes into a stack | D5; C5.1; taken item; names-r6.txt |
| SF1: D10 hides the real policy | Narrow vs held is now D1's question, with your sketch; D10 is report only | D1; taken |
| SF2: D17's premise, and D16's selector clause | Shape follows the failure count under either D40 Q2 answer; the caller is shown; (a) opaque stack vs (b) transparent stack; rec (a) | D17 |
| SF3: D14 not ready, its marker an invented failure | `FileSyncFailed` in D5; directory close is `FileCloseFailed` on its own path; member and marker removed | D5; C5.3 |
| SF4 / M8: `$trace` reserves on call entry | Withdrawn; a fixed inline buffer filled by a frame walk, with no per-call cost and no allocation | C4; taken |
| SF5 / M4: no bound for the shipped analysis, budget not deterministic | Narrow: a linear per-arm check with no budget. Held: a polynomial bound for the merged abstraction. C2 gets a linear fast path; budgets are fixed work counts | C2; C3-N; C3-H |
| SF6: writes through `@param` | Held only: transfer to the caller's place and export it in the summary; narrow: moot | C3-H |
| N1: structural selectors | Existential for selection; reads stay unique | C1; taken |
| N2: binding vs parameter | A declared `let` projects like a parameter; results, fields and elements hold whole | C1; taken |
| N3: `wrap` uses `Canceled` as data | Uses `Closed<Job>` | D4 |
| N4: D13 overlaps D43 | Handed to D43 | For D43 |
| N5: native text in hook payloads | Fixed inline text field, or a static code table | C4; For D43 |
| N6: a repeated `OutOfMemory` | One reserved stack link per boundary | C4 |
| N7: example details | D11 and D16's examples are gone with them; D1 clarified is a taken item; no dead branch remains | Taken |
| N8: an ill-fitting later default | An error at a named declaration, or at the construction for an unnamed one | C1; taken |
| Review D9–D17 table | D9–D12, D15 and D16 taken; D13 to D43; D14 into D5; D17 kept with D16's selector clause | Part 1; taken |
| Cancellation round | D2, D3 and D7 are byte-identical to round 5; only D4's `wrap` changed | Part 1 |

**Unresolved must-fix: none,** under either D1 answer. Narrow removes MF1 and MF2; held carries
the repairs in C3-H. **Pending gates:** the cold read of `names-r6.txt`; C3-N's or C3-H's
measurement on the flagship panel; C4's trace size; the C5 fault tests. None of these has been
run.

**Programs and grades.** Under the narrow D1 none of the fifteen programs changes, because each
handles whatever it holds. Under D17 (a), program 06 and the shape comments in program 09
change; see `programs-r6/` and `dogfood-round6.md`.
