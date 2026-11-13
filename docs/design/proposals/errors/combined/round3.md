# Combining failures, David's design: round 3

This round answers the independent review (`review-round2.md`, six must-fixes) and takes in
David's batch-10 decision that `Canceled` is no longer special: `??` and `or_throw` treat it
like any other failure, and `??<~Canceled>` handles everything except it. Rounds 1 and 2 stand
where this file doesn't replace them. Revised programs are in `programs-r3/` (fifteen, one new),
graded in `dogfood-round3.md`.

**Spelling.** Following David's standing idiom, values combine with `and` (`e1 and e2`,
`stack and= e`) and types with `&` (`E1 & E2`, `<E1 & E2>` arms, `??<~Canceled>`). They are one
operator. On failure values, both operands are evaluated: they are failures already in hand.

**What changed, in one list.**
- Cancellation options A, B and D are gone, with the dominance rule; `~E` (complement) is
  specified for selectors; `$explicit_cancellation` is redefined; the spin case gets a targeted
  warning and a canceled run exits 130.
- `match` arms now select exactly what `is?` selects and bind the whole value (the review's
  preferred alignment); `??<E>` still consumes only what it names in full. One rule ties them:
  a failure part can only disappear through an action that names it.
- The dropped-part check is replaced by an ownership-based obligation contract (temporaries,
  calls, copies, storage, captures), with its cost bound.
- `A & B` has one meaning: facets for minted (nominal) types, merged fields for plain records,
  decided by the operand types, so an alias always means what its expression means.
- No automatic stack lifting: two failures of one type combined in generic code are the same
  compile error as in concrete code, reported at each use.
- One-shot helpers' cleanup contract is stated; a failed commit leaves its transaction to roll
  back.
- Cleanup failures live in their owners' own slots and stacks are chains of segments, so automatic
  cleanup merges never allocate; the construction gate stays open until that is built and tested.
- A stack's nonemptiness is a refinement on its storage, enforced on every mutation.
- Stacks are handled by their own selector (`??<ErrorStack<E>>`), as `is?` sees them.
- Origins are scoped to the whole-program source build GOALS.md specifies.

## Questions for David, each with a minimal example

### Q1. A failure part disappears only through an action that names it

`is?`, `match` arms and `or_throw<E>` select a failure that has an `E` part; `??<E>` consumes
only a failure whose every part it names. An arm binds the whole value, so whatever the arm's
type doesn't name must still be forwarded, handled or dropped with `;` inside it.

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
        quota:QuotaExceeded => printl"quota: {quota.message}"    # error: this arm also takes
        offline:Offline => printl"network: {offline.message}"    # QuotaExceeded & Offline, and its
        n:int => printl"{n} bytes"                               # Offline is dropped unnamed
    }
}
limit_or_default = (text:string) => {
    return record_limit(text p"limits.log") ??<ParseError> 100
}   # ParseError alone gives 100; ParseError & FileCloseFailed stays a failure
```

The fix-its for `careless` are: add a `QuotaExceeded & Offline` arm before it, return `quota`,
or write `quota;` to drop it on purpose. **Rec:** yes. Reversible before release.

### Q2. Excluding a type: `??<~E>`

`~` is `not`, so `??<~Canceled>` handles every failure that isn't a cancellation. A
cancellation combined with anything else isn't handled either, because one of its parts is a
`Canceled`:

```dewy
poll = (sensor:Sensor) => {
    loop true {
        let reading = sensor.read(timeout=1s) ??<~Canceled> continue or_throw
        record(reading)
    }
}   # a Timeout or a read error: read again; Canceled (alone or with a cleanup failure): leave poll
```

`~` rather than `not` here, by the standing idiom: `&`, `|` and `~` in type expressions,
`and`, `or` and `not` in value expressions. `~` also binds tightly, so `??<~(E1 | E2)>` shows its
grouping. **Rec:** yes, as specified under S1 below.

### Q3. A loop that only `continue`s after a failed wait warns

```dewy
worker = (jobs:Receiver<Job>) => {
    loop true {
        let job = jobs.receive ?? continue    # warning: after cancellation every receive fails
        process(job)                          # at once, so this loop spins; write ??<~Canceled>
    }
}
```

The warning fires when a `??` whose selector covers `Canceled` sits on an operation that can
return `Canceled`, inside a loop, and its fallback is `continue` (or a value on a path that
reaches the loop's next iteration without leaving the loop). It is a warning, not an error,
because a loop that also checks a deadline or a counter is correct. **Rec:** yes.

### Q4. A run canceled by Ctrl-C exits 130, whatever `main` returns

```dewy
main = () => {
    let rounds = input_int("rounds? ") ?? 10     # Ctrl-C at the prompt gives 10
    play(rounds)                                 # play's next wait fails at once, and so on
}   # exit status 130: Ctrl-C canceled main, and no listener took it
```

With `Canceled` ordinary, a default can turn Ctrl-C into a value. The program then stops at its
next wait that doesn't default, but if it reaches the end of `main` its status would be 0. This
rule keeps the shell convention: when Ctrl-C cancels a program whose code doesn't listen for it
(`loop _ in signals.ctrl_c`, batch 9), the run ends with 130 once `main` returns, unless `main`
ended with a failure (which is reported, and exits with its own code). A program that takes
Ctrl-C itself decides its own status, as now. **Rec:** yes. Reversible.

### Q5. `$explicit_cancellation` checks that a handler says what it does with `Canceled`

```dewy
ask = () => {
    $explicit_cancellation
    let rounds = input_int("rounds? ") ?? 10           # error: this `??` also handles Canceled;
    play(rounds)                                       # write ??<~Canceled> or ??<Canceled | …>
}
```

Under the tag (in `$bulletproof`), a `??`, `match` arm or collector element that can consume a
`Canceled` must name it in its selector, positively or as `~Canceled`. Plain `??` and
`??<exception>` on an operation that can be canceled are errors with both fix-its. It changes no
behavior. **Rec:** yes.

### Q6. Facets for minted types, merged fields for plain records

```dewy
User:type = type of any & [id:int name:string]
Settings:type = type of any & [id:int theme:'light' | 'dark']
both_ids = (profile:User & Settings):>string => {
    return "{(profile as User).id}/{(profile as Settings).id}"   # two ids: name the facet
}
Size:type = [width:int height:int]
Place:type = [x:int y:int]
area = (box:Size & Place):>int => box.width * box.height      # plain records merge, as today
```

`&` of minted types keeps each as its own facet, so a field both declare is reached through
`as`; `&` of plain records merges their fields as LANGUAGE.md says today. `and` on two plain
record values that share a field is an error whose fix-it mints one of them. **Rec:** yes. It changes
nothing existing.

### Q7. Two failures of one type are an error in generic code too, at each use

```dewy
run_both = <T U>(first:(():>void | T) second:(():>void | U)) => {
    let a = first()
    let b = second()
    if a is? exception and b is? exception return a and b
    if a is? exception return a
    if b is? exception return b
}
check_disks = () => run_both(@root_disk @data_disk)   # error: run_both combines a DiskLow with a DiskLow;
                                                      # two failures of one type go in an ErrorStack
```

**Rec:** yes (David's rule, applied where the types become known). The alternative, a generic
`and` silently making a stack, is a change to his rule and is not proposed.

### Q8. Library vocabulary, with two contracts

```dewy
count_lines = (path:Path) => {
    let text = path.read_text or_throw       # read_text: string | FileError | InvalidUtf8 | Canceled
    return text.split("\n").length
}
transfer = (tx:db.Transaction) => {
    tx.commit() or_throw                     # a failed commit leaves tx open: it rolls back at the end,
}                                            # so CommitFailed & RollbackFailed is possible
```

The per-operation names read correctly in the cold read (mostly 5/5). `FileError` becomes the
parent of the file failures (LANGUAGE.md has it as a sibling today). Closing a read-only handle
can't lose data, so its failure isn't reported (the existing assumptions.md row "the library's own
drop hooks cannot fail"), and `read_text` closes before decoding. **Rec:** yes.

### Q9. The error stack's name

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

Cold read: `ErrorStack` 3/3/3 (readers unsure which end is the top), `ErrorList` 4/4/3 ("kept
in the order written"), `Errors` 3/4/3. **Rec:** `ErrorStack`, your word; `ErrorList` read better
on order if you'd rather.

### Q10. Taking all the parts of one family: `as error`

```dewy
wrap = (job:int result:Canceled & FileCloseFailed & SocketCloseFailed) => {
    return (result as Canceled) and UploadFailed[job "upload failed" (result as error)]
}   # result as error is FileCloseFailed & SocketCloseFailed
```

`v as T` takes the parts that are `T`: one part, or several when `T` can hold them together
(`error` can; a family with shared fields, like `FileError`, can't, so that is ambiguous). This is
David's "take a subset of a combined object". **Rec:** yes.

### Q11. Metatag names

```dewy
show = (failure:exception):>void => {
    loop part in failure.$parts printl("{part.$origin}: {part}" file=stderr)
}
```

Cold read: `$origin` 4/4/4 (as good as `$location`, better than `$where`); `$trace` and
`$backtrace` both good; `$parts` and `$failures` tie; `$origin_at_caller` 4/4/3, best of three
(`$track_caller` was once read as recording the whole call chain). **Rec:** `$origin`, `$trace`,
`$parts`, `$origin_at_caller`.

## M1: one meaning for `A & B`

The review's point: `Both:type = User & Settings` and a parameter written `User & Settings` must
accept the same values, but round 1 gave the declaration one `id` and the parameter two.

**Rule.** `A & B` means one thing everywhere: values that are an `A` and a `B`. What that looks
like is decided by the operand types, never by where the expression is written:

- **Minted types** (`type of error`, `type of any`, and their children) can't share a value: a
  value has one nominal type. So every value of `E1 & E2` is made of facets, one per minted
  operand, each with its own fields. A field one facet declares is read directly; a field several
  declare is read through `as`. There is no merged form, so there is no conflict with the existing
  contract, which LANGUAGE.md limits to plain records ("intersections are module-level declarations
  of plain (not minted) records").
- **Plain records** are structural: one record with all the fields is both. `A & B` of plain
  records keeps today's meaning: one record, a shared field with the intersection of its types,
  a conflict (`string` and `int64`) an error. Value `a and b` of plain records builds that one
  record when they share no field; if they share one, it is an error: "both declare `id`; mint one
  (`type of any & [...]`) to keep two, or build one record".
- **A plain record beside a minted type** adds fields to that type's facet, which is the existing
  payload form (`type of error & [message:string]`). Beside two or more minted types it is an
  error (no use was found; write the fields into one of them).
- **Values** are combined with `and` (`user and settings`), types with `&`, by the standing idiom.
- **Aliases** are substitutable: `Both:type = User & Settings` is exactly `User & Settings`.

Program 11 now mints `User` and `Settings` to show facets, and shows plain records merging. This
narrows David's "for any combined value" for *shared fields*: plain records can't keep two of one
field, because a plain record type is its fields. Disjoint plain records and every minted type
behave as he described.

`$parts` is now defined only on failures (`array<exception>`). Round 1 offered it for records
and functions too, with a type that didn't fit them; facets of a record are reached by `as`, and
function overload sets are out of this round's scope.

## M2: who owes a failure, and what discharges it

Round 1's check looked only at variables, so `take_a(pair)` lost a part with no variable in
sight, and it rejected `host_of`, which only reads one part of a borrowed pair. Replacement:

**Which values carry an obligation.** Every *owned* compound failure: a combination or a stack,
or a value whose type includes one. Single failures are unchanged (today's statement rule). Combined
records (`User and Settings` values) carry none: they are not failures.

**Who owns it.** The obligation follows ownership, as Dewy's moves already do:

| Holder | Owns the obligation? |
|---|---|
| a `let` binding, or a temporary (a call's result not yet bound) | yes |
| a field or element of an aggregate it was moved into | the aggregate does (it then carries the obligation) |
| a closure that captured it by move | the closure does |
| a parameter (shared, the default) | no: the caller keeps it, so a callee may read any part |
| a consuming parameter (the value moved in at its last use, whole) | yes, the callee |

Copies of an immutable compound share one obligation: discharging any copy discharges it.

**What discharges a part.**
- Forwarding the whole: `return`, `or_throw`, the value of a block, a send, a task's result.
- Moving the whole into another holder (the obligation moves with it).
- A consuming handler that names the part: `??`, `??<E>` covering it, a `match` arm whose type
  names it.
- `;`, which drops on purpose.
- `as E` whose result is itself discharged (returned, stored, handled): that discharges part `E`.

**What does not.** `is?`, reading a field, printing, an implicit projection into a parameter,
`as E` whose result is only read. These observe.

**Where it is checked.** Where a holder stops existing with parts still owed: its last use, a
reassignment, the end of a temporary's statement, a branch that leaves. The diagnostic names the
part and the point:

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
take_a = (a:A):>A => a
lose_b = ():>A => take_a(pair)       # error: pair's result is A & B; take_a uses its A and the B
                                     # is dropped here. Forward it, or bind it and drop B with `;`
host_of = (failure:QuotaExceeded & Offline):>string => {
    return (failure as Offline).host # fine: `failure` is borrowed; the caller still owes it
}
```

**What it guarantees.** A part never disappears without an action that names it or drops it on
purpose. It does not guarantee recovery: `??<error> 0` names everything and consumes it.

**Cost and bounds.** The analysis runs only in functions where a compound failure type occurs.
Each compound value has one indexed set of owed parts (a bit set over that function's part types);
sets join at merges by union, and calls use the callee's ownership summary (shared or consuming
parameters), which the ownership pass already computes. Work is linear in the function's value
flow times the number of distinct part types, with no enumeration of union subsets. Above 64
part types in one function it falls back to whole-value tracking (the diagnostic then asks for the
whole to be forwarded or dropped). It must show its cost on the flagship panel before landing.

## M3: no generic stack lifting

Round 1 let `T & U` become a stack where `T == U`. That changed David's rule through abstraction.
Now:

- `a and b` on failures requires the two operand types to be disjoint. Where they are type parameters, the
  requirement is checked at each instantiation, with the same diagnostic as concrete code, naming
  the call that instantiated it (program 13, line 26).
- The same holds for unions and families that may overlap: `(E1 | E2) & (E2 | E3)` and
  `FileError & FileCloseFailed` are errors ("these may both be E2"); narrow first.
- Program 13 now tests `is? exception`, not `is? T`, so a success type `T = void` never combines.
  `T = Canceled` gives `Canceled & U`; `T = U = Canceled` is the duplicate error.
- Repeats go through an explicit stack (`check_all`, program 13).
- Automatic cleanup is not user `and`: it combines exact alternatives it generates, and uses a
  stack where the same type repeats, which is David's own suggestion for cleanup.

## M4: one-shot helpers and failed commits

A helper that opens, reads and closes owns a handle during its call; not returning the handle
doesn't make its close infallible. The contract now:

- **Read-only handles** (`files.open(p 'r')`, and the ones inside `read_text`, `read_bytes`,
  `glob`): their close can't fail observably. On Linux, macOS and Windows a read-only descriptor is
  released whatever close reports, and no data can be lost. The library's drop hook is `():>void`,
  under the existing assumptions.md row ("the library's own drop hooks cannot fail"), whose opt-out
  is the bulletproof route. `read_text` closes before decoding, so `InvalidUtf8` never meets a close
  failure. Results: `string | FileError | InvalidUtf8 | Canceled`.
- **One-shot writes** (`write_text`, `write_bytes`): they write a temporary file and rename it over
  the target, so a failure leaves the target unchanged. Their temporary's close or removal can fail
  after a failed write, which they report exactly:
  `int | FileError | Canceled | FileWriteFailed & FileCloseFailed | Canceled & FileCloseFailed`.
- **Writable handles** (`files.open(p 'w')`, sockets): fallible close, as before.
- **Transactions**: a successful `commit()` consumes the transaction. A failed commit leaves it
  open, and it rolls back at scope end, so `CommitFailed & RollbackFailed` is possible. A driver
  whose failed commit has already rolled back reports that by consuming the transaction; the type
  follows the driver's documented states. Program 14 lists it.

Programs 04, 07, 08 and 09 rely on the read-only rule; their comments and types now say so.
Under the assumption's opt-out, `read_text` returns the combinations, and program 04's
`array<FileError | InvalidUtf8>` would not compile until widened, which is the point of the
opt-out.

## M5: cleanup failures without allocation

Round 1's "one slot per owner array" didn't show how a stack survives being merged or moved. The
contract now, kept as a gate to build and test with allocation refused:

1. **The slot is part of the owner.** Every owner whose cleanup can fail carries room for its own
   cleanup failure and a link, inside the owner value (a `File` has room for one
   `FileCloseFailed`). It exists before the owner is acquired, and it moves wherever the owner
   moves: returned from a helper, pushed into an array, put in a record.
2. **A stack is a chain of segments.** Cleanup writes each failure into its owner's slot and
   links the slots in cleanup order. The storage the slots live in goes to the stack: an owner
   array's buffer is moved into the stack (not copied); slots in a frame are copied into the
   function's result, whose layout has room for its fixed number of named owners.
3. **Merging is linking.** A pending body stack and new cleanup failures merge by writing one link
   in the body stack's last segment. No contiguous buffer, no allocation. The body stack is
   uniquely owned at that point (it is being returned).
4. **A refused growth keeps the owner.** If `outs.push(owner)` can't grow the array, it gives
   `OutOfMemory` and the owner stays in the statement's temporary, which has its own slot, so the
   owner still closes and its failure still comes back (`OutOfMemory & FileCloseFailed`).
5. **User-written appends** (`stack and e`, `stack and= e`, `ErrorStack[xs...]`) allocate a segment and follow the
   ordinary allocation policy (`$explicit_allocation_failure`). Only automatic cleanup is promised
   to be lossless.
6. **Cost.** Each fallible owner grows by one cleanup failure and a link (about 32 bytes for a
   `File`: a shared path, a constant message, a link). Indexing a stack walks its segments
   (usually one or two). Fixed pairs (`FileWriteFailed & FileCloseFailed`) stay inline, as before.

## M6: a stack is never empty, for its whole life

`ErrorStack<E>` is `type of error & array<E length>?0>`: the length refinement is a storage
contract, and refinement.md's rule applies, "do not erase invariants through mutable access":

- `pop`, `remove` and `clear` compile only where the result stays nonempty (`clear` never; `pop`
  where the length is proven at least 2), like any refined array.
- A stack can't pass to an `@xs:array<E>` parameter or a raw mutable view, which would drop the
  refinement; a mutable parameter must declare the same refinement.
- `E` must be an `error`, checked at each instantiation. `Canceled` isn't an error, and neither is
  a combination carrying it (a combination is an `error` only if every part is), so neither can be
  an element. That follows from the types, not from a special rule.
- `.first` and `.last` need no proof on a stack (program 10 now uses `.last`).

## S1: cancellation, now that it is ordinary

Options A, B and D and the dominance rule are gone. What remains is ordinary:

- `??`, plain `or_throw`, `match`, collectors and `partition_failures` treat `Canceled` like any
  failure. A collector holds it as an element; program 07 forwards it per element with
  `[loop r in results r or_throw<Canceled>]` before folding failures into a stack.
- `Canceled & FileCloseFailed` is an ordinary combination: `is? FileCloseFailed` is true, so a
  library can report the close failure during cancellation (program 12, line 17).
- **`~E` in selectors.** `~T` is the type of everything that isn't a `T`. A combination is a `T`
  when some part is, so it is a `~T` only when no part is. Hence:
  - `??<~Canceled>` consumes every failure in which no part is a `Canceled`. It does not consume
    `Canceled & E1`, which stays a failure, under the all-parts rule (`Canceled`, one of its parts,
    isn't a `~Canceled`).
  - `??<~(E1 | E2)>` consumes failures with no `E1` or `E2` part, `Canceled` included.
  - `or_throw<~Canceled>` forwards everything that isn't a cancellation and leaves `Canceled` and
    `Canceled & E1` in the value.
  - `is? ~E` is `isnt? E`.
- The coverage rule, stated for any selector `S`: `??<S>` consumes a failure `X` when `X is? S`
  and every part of `X` is a `T` for some atom `T` of `S` (an atom is a type `S` is built from with
  `|` and `&`; a complement such as `~(E1 | E2)` is one atom). Plain `??` is `??<exception>`. So `??<A & B>` consumes `A & B` but not `A` alone, and
  `??<A | B>` consumes `A`, `B` and `A & B`. `or_throw<S>`, `is? S` and arms select `X is? S`.
- The spin case is real and is not fixed by the type rules: Q3's warning targets it, and Q4 keeps
  a canceled run's exit status 130.

## S2: arms aligned with `is?`

Adopted, as Q1. An arm selects what `is? T` selects, in source order; it binds the whole
narrowed value; the obligation check makes the arm name or forward what its type doesn't. So
replacing `if x is? A` with `match x { a:A => … }` no longer changes which paths run. Arm order
matters, as for any overlapping patterns: a more specific arm goes first, and one placed after a
broader arm that already takes everything it would is unreachable, which is an error. The arm's
type is a selector: `problem:FileError` binds `problem` to the alternatives it took, which may
include a pair whose `.path` is ambiguous, while a `FileError` parameter holds one failure. Hover
and the ambiguity diagnostic say which.

## S3: stacks are handled as stacks

`is? FileCloseFailed` is false on `ErrorStack<FileCloseFailed>` (a list isn't one of its
elements), and now `??<FileCloseFailed>` doesn't consume it either. Handle a stack with
`??<ErrorStack<FileCloseFailed>>`, a family or `error` that holds it (`??<error>`), or an arm on
the stack type. Mixed stacks follow the same static rule: `??<ErrorStack<A>>` does not consume an
`ErrorStack<A | B>`, whatever it holds at run time. Nested stacks and stacks inside combinations
are parts like any other. Round 1's leaf-aware handler is withdrawn.

## S4: origins in the build model GOALS.md sets

GOALS.md makes fresh whole-program compilation from source the model. Within it:

- **The demand closure.** Roots are every `$origin` read, every `$trace` read, and in debug
  builds the report of every failure type that can reach the end of `main`. From each root the
  closure follows every way a failure value reaches it: returns, parameters, fields (including
  `cause:error`), array elements, `$parts`, erasure to `error` or `exception` (a read on an
  `exception` demands every failure type that can flow into it), generic instances (each its own
  type), and function values (every failure type their signature admits). The checker already
  builds this flow for inferred results; fields and arrays add edges. Linear in the edges.
- **Outside the model.** A precompiled Dewy library, if one is ever allowed, would need its
  failure layouts fixed with origin storage always present; a foreign function's failure gets the
  origin of the Dewy adapter line that made it. No import changes a layout after the fact, and no
  origin is invented.
- **Site ids** are one table for the whole program, built at link time.
- **Size.** A 4-byte site id is not 4 bytes of cost: alignment can grow every result union that
  holds the failure. That is what the gate measures.
- **Traces**: at most 64 frames, innermost first, in a buffer the failure value owns and moves
  with it; a task's trace ends with the line that started it; frames inlined without debug
  information are missing. If the buffer can't be allocated, `$trace` is empty, which is
  indistinguishable from an empty call chain. That limit is disclosed, not solved.

## S5: what a declared signature looks like

Per-operation names keep one file's failures apart; they don't keep a big function's result
small. The review's upload job (six body failures, four fallible cleanups) has 112 exact
alternatives. The trade-off, as guidance:

- Local and private code: leave results inferred and exact; hover shows them compactly.
- A stable shape used in several places: name it with an ordinary alias.
- A library boundary: wrap. Ordinary failures, cleanup ones included, go in the library's own
  error with a `cause:error`; `Canceled` stays its own part, so callers can still forward it:

```dewy
upload = (job:Job store:db.Store):>void | UploadFailed | Canceled | Canceled & UploadFailed => {
    let result = send_job(job store)
    if result isnt? exception return
    if result isnt? error return result                   # Canceled alone
    let failed = UploadFailed[job.id "upload {job.id} failed: {result}" (result as error)]
    if result is? Canceled return (result as Canceled) and failed
    return failed
}
```

That is program 15. It costs four lines of policy, which the grades count. `exception` is the
widest declared result, for code that only reports.

## S6 and the notes

- **S6:** program 05 prints "wrote … rows" in `main`'s `<void>` arm, after the close succeeded.
- **N1:** the sketch notes stand as syntax details to reconcile, not objections to David's
  semantics.
- **N2:** arm order matters for overlapping patterns (S2 above).
- **N3:** the `parallel` block extension, exit-code priority (lowest code; a canceled run 130 per
  Q4) and `or_throw(& previous)` stay outside this design.
- **N4:** the comparison with `ErrorGroup` (round 1) is corrected: `ErrorGroup` keeps one stable
  result alternative, uniform outer-kind tests, and one representation for dynamic mixed
  collections. This design moves those costs into exact types, the coverage rule and the
  obligation analysis; it removes per-pair allocation and the recovery helper.
