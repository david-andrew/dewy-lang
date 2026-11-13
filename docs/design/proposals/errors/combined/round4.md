# Combining failures, David's design: round 4

This round answers the independent check of round 3 (`review-round3.md`, R1–R6). It is in two
parts. **Part 1** is what David decides: eight surface questions, each with a minimal example in
its enclosing function. **Part 2** holds the implementation contracts (the type laws, selector
coverage, the obligation analysis, cleanup storage, the library's completion contracts, the exit
rule); they are ours, and David doesn't need to read them. Programs are in `programs-r4/`,
graded in `dogfood-round4.md`. Rounds 1–3 stand where this file doesn't replace them.

Settled by David and not asked again: values combine with `and` and types with `&` (one
operator); `Canceled` is an ordinary failure in `??` and `or_throw`; `??<~Canceled>` excludes it;
two failures of one type combined are a compile error pointing to the error stack.

Withdrawn from round 3: Q4 (a canceled run exits 130 whatever `main` returns) and the ban on a
plain record beside two minted types. Neither was needed; Part 2 gives the general rules that
replace them.

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

**Rec:** yes. Reversible before release.

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
wrap = (job:int result:Canceled & FileCloseFailed & SocketCloseFailed) => {
    return (result as Canceled) and UploadFailed[job "upload failed" (result as error)]
}   # `as error` takes every error part: FileCloseFailed & SocketCloseFailed
```

One rule for every `&`: each minted operand is its own facet with its own fields, and all plain
records merge into one record (today's rule). A field more than one of these declares is reached
with `as`. `v as T` keeps every facet that is a `T` (the "subset" David described), and is an error
when the kept facets can't form a `T` (two `FileError`s, whose shared `path` would be ambiguous).
**Rec:** yes. It changes nothing existing: plain-record intersections behave as LANGUAGE.md says.

### D5. Library failure vocabulary

```dewy
save = (path:Path rows:array<Row>) => {
    let out = files.open(path 'w') or_throw
    loop row in rows out.write_text("{row}\n") or_throw;
}   # a write fails, then the close fails: FileWriteFailed & FileCloseFailed
count_lines = (path:Path) => {
    let text = path.read_text or_throw   # includes FileReadFailed & FileCloseFailed: reads report closes too
    return text.split("\n").length
}
```

One type per operation, under a family per resource: `FileReadFailed`, `FileWriteFailed`,
`FileCloseFailed`, `FileRemoveFailed` (new this round, for removing a file, including the
temporary file an atomic write abandons) under `FileError`, which becomes their parent (today it
is a sibling); `SocketConnectFailed`, `SocketListenFailed`, `SocketSendFailed`,
`SocketReceiveFailed`, `SocketCloseFailed` under `NetError`; `ProcessWaitFailed`,
`ProcessStopFailed` with `SpawnError` under `ProcessError`; `QueryFailed`, `CommitFailed`,
`RollbackFailed` under `DbError`. The cold read read every tested one correctly, mostly 5/5
(`FileRemoveFailed` follows the pattern but is untested). **Rec:** yes.

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

# Part 2: implementation contracts (ours)

## C1. The intersection and projection laws (R1)

**Canonical form of a type intersection.** Flatten; expand aliases; collect the minted operands as
a set and drop any that is an ancestor of another (`Child & Parent` is `Child`: a child already is
its parent, so no second facet); merge every plain-record operand into one record by today's rule
(shared fields intersect their types; a conflict is an error; a later default wins); keep
complements as constraints (`A & ~A` is empty). Order and grouping can't matter: the result is a
set of minted types plus at most one record.

**The minting declaration is not an intersection.** In `Name:type = type of P & [fields]` the record
operands become `Name`'s own fields: that is the existing payload form, and after it `Name` is one
minted type carrying those fields. Everywhere else `&` intersects.

**Sources and field reads.** The sources of a canonical intersection are its minted types and its
merged record. A field, inherited ones included, that exactly one source declares is read directly;
one that several declare is read with `as`.

**Values.** `a and b` makes a value whose facets are the facets of `a` and of `b`; plain-record
facets merge into one, so two plain records that share a field are an error (one record has one
field of that name; the fix-it mints one, or builds one record). Operands whose types can overlap
(the same type; an ancestor and its descendant; unions or families that may share a member) are an
error, checked at each generic instantiation; for failures the fix-it is `ErrorStack`, for other
values an array.

**`is?`.** `v is? N` (minted) when some facet's type is `N` or below it; `v is? R` (plain record)
when each field of `R` comes from exactly one facet, with the right type; `&` both; `|` either;
`v is? ~T` exactly when not `v is? T`.

**Projection `v as T`.** On the canonical `T`:
- a minted `N` keeps every facet that is an `N`;
- a plain record keeps the facets that provide its fields (each field from exactly one);
- `~S` keeps every facet that, on its own, is not an `S`;
- `T1 & T2` keeps what `T1` keeps and what `T2` keeps;
- `T1 | T2` uses the one alternative `v` satisfies; if `v` satisfies several and they keep
  different facets, it is ambiguous;
- the kept facets must form a `T`: a combination of several facets is a `T` only if `T` declares no
  field those facets share (`error`, `exception` and complements declare none; `FileError` declares
  `path`, so two file failures as one `FileError` is ambiguous: "name one").

Laws: identity (if `v`'s static type is canonically `T`, `v as T` is `v`); idempotence; grouping
and alias invariance; subset (`(a and b and c) as A & B` is `a and b`); family subset (`as error`
keeps every error). Implicit conversion of an argument to a parameter type `P` is `v as P`, by the
same law. **Holding**: a declared result, variable or field of type `T` holds `v` only when
`v as T` is `v` itself, so nothing is dropped by storing. **Proven**: when every alternative of
`v`'s static type gives a valid result; otherwise a guard (`if v is? T`) or `v as T?`.

Examples: `Marker & Place` (minted, plain) with `x` in both: two sources, `(m as Place).x` and
`(m as Marker).x` (program 11). `(A & Place) & B` = `A & (Place & B)` = `{A, B} + Place`.
`Both:type = T1 & T2` (plain) merges as today and `x.a` is direct, as in
`tests/cases/object/intersections.dewy`.

## C2. Selector coverage is semantic (R2)

The selector is first canonicalized: aliases expanded, put in disjunctive form over minted types,
plain records and complements, and every unsatisfiable conjunct removed (`B & ~B`, or a minted type
beside the complement of its ancestor). Then:

- `or_throw<S>`, `is? S` and `match` arms select `X` when `X is? S`.
- `??<S>` consumes `X` when `X is? S` and **every facet of `X` is needed**: it belongs to some
  smallest sub-combination of `X` that is an `S`. Equivalently, for each conjunct `S'` of `S` that
  `X` satisfies, collect `X as S'`; every facet must be in one of them.

| Selector | `A` | `A & B` | `Canceled & E1` |
|---|---|---|---|
| `??<A>` | consumed | passes (B not needed) | — |
| `??<A \| (B & ~B)>` (same as `??<A>`) | consumed | passes | — |
| `??<A \| B>` | consumed | consumed | — |
| `??<A & B>` | passes (not an `A & B`) | consumed | — |
| `??<~Canceled>` | consumed | consumed | passes (not a `~Canceled`) |
| `??<~(A \| B)>` | passes | passes | consumed |
| `??<error>` | consumed | consumed | passes (Canceled isn't needed by `error`) |

Cost: a failure has at most as many facets as the function has part types; per conjunct, one pass
over the facets. Above 16 facets the handler conservatively doesn't consume (the value passes on,
which loses nothing), with a note.

## C3. The obligation analysis (R3)

**What carries one.** Each *occurrence* of a compound failure (two or more facets, or a stack): an
`and`, a cleanup combination, a stack construction, or a call result whose type has one. In the
analysis an occurrence is its creation point; in a loop, one per iteration, which must be discharged
or moved into a container before the loop comes round.

**Representatives.** Every copy that holds the occurrence: bindings, temporaries, aggregate places,
captures. Dewy values are by-value, so a copy is a representative whatever the lowering (borrow,
copy or move); the rule never depends on optimization.

**Discharge, per part type of the occurrence:** forwarding the whole (`return`, `or_throw`, a
block's value, a send, a task result); a handler or arm whose selector needs that part (an arm's
binder becomes a representative of the parts it didn't need); `;`; an `as` whose result is itself
discharged. Moving into an aggregate makes the aggregate place a representative; it discharges
nothing.

**The check.** On each path, when the **last** live representative of an occurrence ends with
parts owed, it is an error at that point, naming the part. Liveness is the existing liveness
analysis.

```dewy
check_copy = () => {
    let original = pair
    let later = original
    printl(original)                 # not the last representative: no error here
    later ??<A | B> void             # discharges the occurrence
}
```

**Calls: checked summaries.** Each function gets, per parameter, the part types it discharges on
every path (through any discharge of the parameter or its copies) and whether it returns a
representative. Summaries are computed bottom-up, recursion by a fixed point starting from
"discharges nothing", and checked like any inferred effect. A function value whose callee is unknown
(a handle, a foreign function) discharges nothing and returns no representative.

```dewy
handle = (v:A & B):>void => { v ??<A | B> void }   # summary: discharges A and B
observe = (v:A & B):>void => { printl(v) }         # summary: discharges nothing
check_call = () => {
    let v = pair
    handle(v)                        # discharges v's occurrence
    observe(v)                       # fine; with observe in place of handle, v ends owing A and B
}
```

**Containers.** Fixed fields and fixed-size arrays are tracked per place. A dynamic array is one
summary place: reading an element by an unknown index observes; overwriting or removing an element
that may hold an occurrence ends that representative (a removed element, such as `pop`'s result,
becomes a representative); the container's occurrences are discharged by forwarding, storing or
dropping the whole container, or by a loop over it whose body discharges its element on every path.
`[pair pair]` holds two occurrences (two calls); `let p = pair; [p p]` holds one occurrence twice,
and discharging either element discharges it, because they are the same failure.

**Cost.** Occurrences are creation points, parameters and call results: linear in the function.
State per occurrence is a bitset of owed part types (whole-value tracking above 64) and a live
representative count. Dataflow over the control-flow graph: edges × occurrences × bitset words.
Summaries: one fixed point per strongly connected component, monotone in a finite lattice. It runs
only in functions where a compound failure type occurs. Gate: its cost on the flagship panel.

## C4. Cleanup storage (R4)

1. **A slot per fallible owner, reserved at acquisition, in storage that outlives the frame.**
   When an owner whose cleanup can fail is acquired (`files.open`, `store.begin`), its cleanup
   failure slot is allocated with it (in the owner's own allocation where it has one, otherwise one
   small allocation). If that allocation is refused, acquisition fails before the resource exists:
   `OutOfMemory`, nothing to clean up. The slot belongs to the owner and moves with it.
2. **A slot holds** the failure, a link to the next slot, and an optional reference to a prior
   failure value.
3. **Cleanup writes, links, and refers; it never mutates existing storage.** Each failing owner
   writes its failure into its slot; slots of owners ending together are linked in cleanup order; if
   a failure is pending (the body's result, possibly a stack from deeper frames), the first new slot
   refers to it. The pending value is immutable and reference-counted, so a snapshot of it held
   elsewhere is unaffected. The new value's storage is these slots, which survive the frame.
4. **Recursion** (the review's `nested`): every frame reserved its own slot at `open`, so
   arbitrarily many returning frames each add one slot referring to the pending value. No fixed
   result capacity is involved.
5. **Refused array growth**: the owner being pushed already has its slot; `push` gives
   `OutOfMemory`, the owner stays in the statement's temporary, and its close failure goes into its
   own slot (`OutOfMemory & FileCloseFailed`).
6. **User-written combining** (`stack and e`, `ErrorStack[xs...]`): allocates a new node referring
   to the old value, under the ordinary allocation policy; `and=` on a uniquely owned stack may
   reuse storage. Only automatic cleanup is promised lossless.
7. **The array surface is kept**: iteration in order; `.length`, `.first`, `.last` from the head;
   indexing walks segments (usually one or two); shrinking and mutable views follow the nonempty
   refinement and detach a copy first, under the ordinary allocation policy.
8. **Cost**: one slot per fallible owner (about 32 bytes for a `File`), possibly one small
   allocation per acquisition where the owner had none; segment walks on indexing.
9. **Gate**, built and tested with allocation refused: two named owners; recursion; a full body
   stack plus an owner array's cleanup; refused growth; a shared snapshot of a pending stack;
   refusal at acquisition.

## C5. Library completion contracts (R5)

- **No new assumption, no suppression.** Read handles report a failed close as `FileCloseFailed`,
  like write handles. A platform adapter may return success where that target documents that close
  always releases the descriptor and its error carries nothing for a read-only file (Linux); that
  is an audited adapter fact per target, and the types stay portable. The assumptions.md
  lock-hook row is untouched.
- **`read_text` / `read_bytes`**: `string | FileError | InvalidUtf8 | Canceled | FileCloseFailed |
  FileReadFailed & FileCloseFailed | Canceled & FileCloseFailed`. The handle closes before decoding,
  so `InvalidUtf8` never meets a close failure. A close that fails after a complete read gives
  `FileCloseFailed` (the text isn't returned).
- **`write_text` / `write_bytes`** (atomic replace, as LANGUAGE.md documents): write a temporary,
  flush and close it, rename it over the target, sync the directory. A failure before the rename
  leaves the target unchanged; the library then closes and removes the temporary, so the result is
  the failure, `& FileCloseFailed` if the temporary's close also failed, `& FileRemoveFailed` if its
  removal did (any subset). A failure syncing the directory after the rename is
  `FileWriteFailed[replaced=true]`: the new contents are in place, but may not survive a crash.
- **Transactions**: `commit()` consumes the transaction on every outcome; a failed commit rolls back
  itself: `void | CommitFailed | CommitFailed & RollbackFailed | Canceled | Canceled & RollbackFailed`.
  So ownership never depends on a run-time outcome: after `commit()`, `tx` is gone.
- **Strict mode** has nothing to opt out of here.

## C6. The exit status (R6)

One rule, from the final result only: success exits 0; a failure reaching the end of `main` is
reported and exits with its kind's code, a combination or stack with the highest of its parts'
codes (D7); `Canceled`'s code is 130, by the ordinary per-kind code; `exit(n)` exits `n` at once. No
flag survives a handled cancellation, a child task's cancellation affects only the values it
produces, and signal listeners play no part.

## C7. Smaller points from the review

- **Origins** (round 3, S4) stand: the demand closure also follows callbacks, formatting calls and
  effect edges; measured before landing.
- **Program 15** now has four live resources, including a helper process stopped when abandoned.
- **Program 08's** result keeps decoding failures distinct from close failures.
