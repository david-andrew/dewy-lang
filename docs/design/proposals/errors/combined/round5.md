# Combining failures: round 5 — contract repairs

This round replaces round 4's Part 2 in full and amends its Part 1 below. Earlier material stands
only where compatible with this round. The basis is `audit-round4.md`, M1–M8 and S1–S4;
`docs/design/decisions.md`, batches 9–10; D40/D42; and LANGUAGE.md's conversion, generic-family,
record-default, allocation and ownership rules. This is a paper contract, not an implementation
or a claim that any runtime, performance or cross-target gate has passed.

**Scope and budget.** Resolve the eight audit findings and inexpensive should-fixes in one design
round (about 90 minutes). Owned outputs are this file and, only if revised, `programs-r5/` and
`dogfood-round5.md`, all under this directory. Compiler/library implementation, repository edits,
commits, new naming exercises and the separate cancellation redesign are non-goals. No earlier
round, review, program or grade is rewritten. Acceptance is a complete audit disposition with
one consistent contract for selection, transfer, bounded analysis and allocation-free unwind,
and no new observable policy concealed as an implementation choice.

**Binding direction.** Failure values combine with `and`, their types with `&`; the combination
is an unordered set of distinct nominal parts. `as` takes a subset. Independent same-type failures
require the ordered error stack. Cancellation remains ordinary under `??` and `or_throw`.

**Cancellation hold.** D2, D3 and D7 below are reproduced unchanged from round 4 and await the
separate cancellation round. Examples elsewhere use only the already decided ordinary-value
rule; no new cancellation point, warning, shielding region or exit override is proposed here.

Part 1 exposes policies for David, including the compile-time precision limits of the proposed
check. Part 2 specifies mechanisms conditional on those answers. “Taken, report only” items at
the end of Part 1 are direct extensions of decided rules, not additional approvals.

# Part 1: decisions for David

### D1. A failure part disappears only through an action that names it

`is?`, `match` arms and `or_throw<E>` select a failure that has an `E` part. `??<E>` consumes a
failure only when the whole value satisfies `E` and every part belongs to an inclusion-minimal
nonempty subset that satisfies `E`; `~` is no exception, so
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
with `as`. Membership and field constraints commute; constructor defaults retain their existing
source order: a later plain-record default wins, including through aliases. `v as T` keeps every facet that is a `T` (the "subset" David described), and is an error
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
`FileCloseFailed`, `FileRemoveFailed` (introduced in round 4, for removing a file, including the
temporary file an atomic write abandons) under `FileError`, which becomes their parent (today it
is a sibling); `SocketConnectFailed`, `SocketListenFailed`, `SocketSendFailed`,
`SocketReceiveFailed`, `SocketCloseFailed` under `NetError`; `ProcessWaitFailed`,
`ProcessStopFailed` with `SpawnError` under `ProcessError`; `QueryFailed`, `CommitFailed`,
`RollbackFailed` under `DbError`. The cold read read every tested one correctly, mostly 5/5
(`FileRemoveFailed` follows the pattern but is untested). Existing file acquisition failures
(`FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists`) become children of FileError;
after acquisition, failures use the operation's type, retaining the native reason in its payload/
diagnostic. An otherwise unmapped acquisition failure uses the family's generic failure. This
mapping is included in the question, not just the type names. **Rec:** yes.

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

### D1, clarified: coverage uses witnesses, not projection

```dewy
A:type = type of error
B:type = type of error
same = () => {
    let x = (A and B) ??<A> 0
    let y = (A and B) ??<A | (A & B)> 0
    let z = (A and B) ??<A & ~Canceled> 0
    x; y; z;                         # all three still contain A and B
}
all_named = () => (A and B) ??<A | B> 0   # 0
```

For a failure's nonempty set of facets, consider all **inclusion-minimal nonempty** subsets
satisfying the selector. Consume only if the whole failure satisfies it and the union of those
witnesses is the whole set. Inclusion-minimal means no proper nonempty satisfying subset, not
minimum cardinality. Equivalent selectors give the same witnesses. Negative constraints do not
supply an otherwise unnecessary positive part. `as` is not the coverage algorithm: two different
file failures can both be covered by `??<FileError>` even though `.path` through `as FileError`
is ambiguous. **Question:** adopt this precise reading of D1? **Rec:** yes. **Reversible:** before
release; afterward it determines which fallback runs. This refines D1, rather than adding a
separate selector language.

### D9. Optional projection handles absence; it does not choose between ambiguous parts

```dewy
FileError:type = type of error & [path:string]
ReadFailed:type = type of FileError
CloseFailed:type = type of FileError
inspect = (v:ReadFailed & CloseFailed):>string => {
    if v is? FileError {
        # (v as FileError).path         # error: two providers of path; the test is true
        # (v as FileError?).path        # still ambiguous; optionality cannot choose one
        return (v as ReadFailed).path
    }
    return "unreachable"
}
maybe_read = (v:ReadFailed | CloseFailed) => v as ReadFailed?   # ReadFailed or none
```

**Question:** keep `is?` existential, require both existence and uniqueness for plain `as`,
and reject possible ambiguity even for `as T?`? `T?` already supplies the existing absence
outcome `none`; no new conversion-failure type is introduced. For a union target, two satisfied
alternatives projecting different subsets are ambiguous; write the desired part explicitly.
A complement in a positive intersection constrains the selected result, rather than adding
unrelated facets: `x as (A & ~Canceled)` selects A, if valid. A complement alone filters facets.
The union-target choice is observable even for two selectors with the same existential test:
`A` and `A | (A & B)` select the same inputs, but the latter offers two storage/source alternatives.

```dewy
A:type = type of error
B:type = type of error
leaf = (v:A & B) => v as A                  # A
# choices = (v:A & B) => v as (A | (A & B))  # ambiguous A versus the whole pair
filtered = (v:A & B) => v as (A & ~Canceled) # A, not B
```

The question includes retaining that distinction between existential selection and explicit
projection/storage alternatives, rather than normalizing away an alternative that names a
larger subset. A declared binding/result/field must retain the supplied value whole; an ordinary
parameter may project with the same checked conversion and duty tracking. These general
projection choices apply to ordinary objects too. **Rec:** yes. **Reversible:**
before release; existing conversion spellings stay, but accepting ambiguity later would change
which data a program receives. No runtime test of existential membership repairs known ambiguity.

### D10. Handling one copy acknowledges that occurrence; transport keeps its outstanding parts

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
observe = (v:A & B):>void => { printl(v) }
handle = (v:A & B):>void => { v ??<A | B> void }
okay = ():>void => {
    let saved = { pair }              # transport, not handling
    let copy = saved
    observe(saved)                   # observes, not handling
    handle(copy)                     # acknowledges this one occurrence through both copies
}
lose = ():>void => {
    let nested = [[pair]]
    printl(nested.length)            # error at the last holder: neither part was handled
}
```

**Question:** adopt shared acknowledgment for exact copies of one occurrence, while every
block result, aggregate, capture, projection and returned value transports its remaining duty?
Independent evaluations of `pair` never share acknowledgment. Returning or successfully handing
a value to an owning destination transfers responsibility; it does not mark that value handled
in its recipient. An observer's parameter may return its unmet duty to its caller without the
observer itself being rejected. A function cannot hide an unhandled locally created occurrence
by calling an observer. **Rec:** yes. **Reversible:** before release; this is a compile-time
acceptance rule with no runtime identity or optimization-dependent copying behavior.

### D11. When proof is too expensive or imprecise, stop compilation rather than change a handler

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A and B
partial = (n:int<(>=? 2)>):>void => {
    let xs:array<A & B> = []
    loop _ in [0..n) xs.push(pair)
    let last = xs.pop
    last ??<A | B> void
    printl(xs.length)                # error: other iterations' failures are outstanding
}
complete = (n:int<(>=? 0)>):>void => {
    let xs:array<A & B> = []
    loop _ in [0..n) xs.push(pair)
    loop value in xs { value ??<A | B> void }
}
```

**Question:** permit a conservative compile-time diagnostic when the obligation check cannot
prove a correlated alias/container/call case, or exact selector analysis exhausts compiler
resources? The repair is to handle/forward/drop the whole value, consume a container through a
proven full traversal, or simplify/split the expression at the reported boundary. The compiler
must distinguish an actual unhandled part from “could not prove”. A dynamically indexed element
or one `pop` never counts as handling an unknown number of other elements. An unknown callee
never proves acknowledgment; passing it the whole value alone is not an escape hatch.

**Rec:** yes, with no silent fallback. In particular, 17 facets has exactly the same handler
semantics as 16; no pass-through at a size threshold. Whole-value forwarding/drop remain usable
when precise per-part tracking is lost. **Reversible:** diagnostic precision can improve later
without changing any accepted program's runtime behavior; accepting unproven loss cannot.
This acknowledges real precision limits, not an exact feasible-path checker.

### D12. A one-shot text read closes successfully before decoding

```dewy
load = (path:Path) => {
    let text = path.read_text or_throw
    return text.length
}   # bad bytes plus failed close: FileCloseFailed; decoding was never attempted
raw = (path:Path) => path.read_bytes   # array<uint8> on success; no InvalidUtf8
```

**Question:** retain close-before-decode for the one-shot text helper? A completed read followed
by failed close returns the close failure and withholds the bytes/text; a failed read and failed
close return both failures. A hand-written helper that decodes before scope cleanup can instead
produce `InvalidUtf8 & FileCloseFailed`. **Rec:** yes: finish the owned I/O before starting the
next fallible stage. **Reversible:** before release; afterward it changes possible failure pairs
and whether decode work runs. Reporting an actual read-close failure is already required by D40,
and is a taken item below, not an option to suppress it.

### D13. Commit consumes the transaction on every outcome and attempts rollback before returning

```dewy
finish = (store:Store) => {
    let tx = store.begin or_throw
    tx.commit() ?? void
    # tx.put(row)                    # error: tx was consumed, even if commit failed
}
```

**Question:** make failed commit consume just like successful commit, with a failed commit
attempting rollback before return and reporting `CommitFailed & RollbackFailed` if both fail?
There is no later duplicate automatic abandon. A failed rollback quarantines/releases the
connection according to the adapter's checked state contract; it cannot return a reusable
transaction whose native state is unknown. **Rec:** yes, so ownership does not depend on an
uninspected result. **Reversible:** before release; afterward a public ownership contract.
This chooses failed-commit behavior; D40 permits early consuming completion but does not force it.
Adapters whose commit outcome is indeterminate must say so in the returned failure; rollback is
not represented as proof that a remote commit never took effect.

### D14. Atomic-write failures say whether replacement has already happened

```dewy
save = (path:Path text:string) => {
    let result = path.write_text(text)
    if result is? FileWriteFailed {
        if (result as FileWriteFailed).replaced {
            printl("new contents are installed; durability was not confirmed" file=stderr)
        }
    }
    return result                    # forward this failure and any cleanup failures whole
}
```

**Question:** retain the full temporary/write/flush/close/rename/directory-sync operation and
expose replacement state on `FileWriteFailed`? **Rec:** yes; `replaced=false` before successful
rename, `true` after it. A failed directory sync reports `FileWriteFailed[replaced=true]`; it
cannot honestly promise the target is unchanged. A failure only in closing the directory's
handle is a `FileCloseFailed` for that directory, with the same replacement information in the
aggregate's `FileWriteFailed` stage marker (C5 specifies this case). Replacement state says what
the operation established, not what another process may do later. Success still gives the byte
count. No retry is implied by `false`, or rollback of an installed target by `true`.

**Reversible:** before release; this member and post-rename outcomes become public contracts.
`replaced` is the untested member already used in round 4, now explicitly proposed rather than
hidden in C5. It is provisional: cold-read naming and realistic API dogfood are prerequisites
to moving this question into open_decisions.md. No new naming approval is claimed here.
No new cancellation region is chosen: if an already permitted cancellation is observed after
rename, include it with this replacement-state failure; otherwise follow the separate round's
cancellation-point contract.

### D15. Allocation refusal still leaves the function, carrying failures from its cleanup

```dewy
$explicit_allocation_failure
acquire_two = (first:Path second:Path) => {
    let a = files.open(first 'w') or_throw
    let b = files.open(second 'w') or_throw
}   # reservation for b refused, then a's close fails: OutOfMemory & FileCloseFailed
```

**Question:** extend the function's allocation-failure alternative by the same cleanup-combination
rule as any other function exit? **Rec:** yes; no locally catchable `push`-refusal result is
introduced. The nearest active allocation-failure frame still receives the refusal, but its
result preserves an already pending failure plus all cleanup failures. Automatic completion,
including failure payload construction and result transport, must be allocation-free; effects
that violate that contract are rejected before runtime. Reservation allocations are ordinary
allocations, count against caps and effects, and can cause this function exit. WebAssembly's
existing inability to recover from refusal stays: it terminates, with no lossless-return promise.

Manual `ErrorStack[...]` and `stack and e` follow the existing ordinary allocation policy: refusal
terminates without an active recoverable frame, or unwinds to that frame and returns its refusal
result. They do not guarantee delivery of the result the programmer was trying to build.
**Reversible:** before release; the inferred result extension and no-allocation hook contract
are observable, while the linked-storage layout is internal. This strengthens the return value,
not the existing recovery boundary or guarantees about reclaiming interrupted allocations.

### D16. The error stack remains a nonempty error-only array value, not a transparent selector

```dewy
A:type = type of error
B:type = type of error
use = (xs:ErrorStack<A | B>) => {
    if xs is? A printl("unreachable: a stack is not its element")
    loop failure in xs { failure ??<A | B> void }
    # xs.clear()                     # error: would violate nonempty storage
    xs;                              # explicit acknowledgment of the stack itself
}
```

**Question:** retain the inherited stack contracts as public behavior: nonempty throughout its
life; elements must fit whole in `error`; nested stacks are allowed; stack selectors inspect
the stack's type, not its contents; append/iteration preserve order; ordinary mutable array
access cannot erase the nonempty refinement? **Rec:** yes. An element may contain several error
facets; existential `is? error` alone does not prove it fits whole in the collection.
A whole-value handler/drop of the stack acknowledges its contained obligations; read-only
iteration does not do so unless the body handles every element and the stack's own duty is also
handled or explicitly dropped. The array surface is retained with segmented-storage costs:
length/first/last constant time, index worst-case linear in segments, mutation/detachment may
copy all elements and allocate under ordinary policies. **Reversible:** before release; the
array surface, selector behavior and cost contract are public afterward. This exposes inherited
policies rather than redesigning the stack or changing its name (D6).

### D17. Repeated cleanup kinds have a stable stack shape at each cleanup boundary

```dewy
save_two = (left:Path right:Path) => {
    let a = files.open(left 'w') or_throw
    let b = files.open(right 'w') or_throw
}   # with both owners live: one failed close or two -> ErrorStack<FileCloseFailed>
```

**Question:** where two or more sources at a cleanup boundary (including any pending body failure) can
emit the same kind, group that kind's contributions into a stack even if only one actually fails? **Rec:** retain round 4's
program-06 rule. Different kinds stay distinct peers; a body failure remains a peer unless it
collides with the accumulated kind, in which case that kind's body contribution also enters the
same stack. A body stack already representing that kind is extended logically, without mutating
its storage. No failure means no stack. With only one live source at an earlier exit, its failure
can be bare. Each boundary's inferred type/hover says which shape it has. Ordered entries put an
existing body contribution first, then cleanup in its execution order. The surrounding combination
has no order. Generic user-written `a and b` still rejects repeats; this is automatic completion's
separate, explicit packaging rule. **Reversible:** before release; changing the packaging later
changes selectors. This is a reported discoverability cost, not an all-5 design claim.

## Taken, report only: natural extensions of decided rules

- Keep ordered plain-record defaults through aliases/grouping; only membership constraints and
  nominal facet sets commute (M6). No request to remove the established rule.
- Distinct canonical generic instantiations are distinct facet identities; aliases of one instance
  collide. Bare families select instances without erasing their stored type arguments; `as Closed` keeps
  the subset of distinct matching instances without inventing a new parameterization (S1).
- `Child & Parent` repeats one requirement, not a second supplied value; independently combining
  overlapping possible facet identities is rejected, including after generic substitution (S1/N1).
- Actual read-close failures are reported, regardless of whether the native descriptor was
  released. Delete round 4's Linux suppression permission; no extra strict-mode opt-out (M7).
- Explicit consuming close runs once on every outcome. Its consumed owner is not closed again at
  automatic cleanup; platform release/backstop behavior remains an audited adapter obligation (S2).
- Cleanup slots cannot escape short-lived arenas. Charge their allocation/copy costs to the same
  rows, caps and `$no_hidden_costs` rules as other allocations; no hidden exemption (S3/M8).
- D7's result-based exit choice stays a Part 1 decision; C6 implements it conditionally. Origins
  and trace demand through calls, callbacks, formatting and effects stay as already proposed.

# Part 2: implementation contracts, conditional on Part 1

These contracts add no permission to suppress a failure or silently change a selector. Public
choices are D1/D4/D9–D17 or the taken items above. Internal choices may be replaced by equivalent
implementations meeting the same behavior, effects and gates.

## C1. Facets, ordered defaults, membership, projection and holding (M5/M6/S1/S4)

### C1.1 Two different kinds of metadata

Canonical membership/field requirements flatten intersections, expand aliases, key nominal facets
by `(minting declaration, canonical type arguments)`, remove repeated requirements and ancestors
already implied by descendants, merge structural field constraints, and retain complements as
constraints. Disjoint sibling nominal requirements produce distinct facets, not an empty type.
`A & A` and `Child & Parent` are valid type requirements; supplying independent values with those
colliding identities is a different operation. A contradictory field constraint or `A & ~A` is
empty. The one merged plain-record source and all nominal sources remain distinct regardless of
parentheses. Minting `type of P & [fields]` creates one new nominal type whose own payload includes
those fields; it does not create a separate structural facet.

**Constructor metadata is not that unordered set.** Preserve an ordered stream of field-default
contributions through declarations and alias expansion. Intersection concatenates the streams
left to right, associatively. The last applicable default wins. An alias stores its resolved
stream, and its use contributes that stream at the alias's position. For `Left=[x:int64=1]` and
`Right=[x:int64=2]`, `(Left & Right)[]` has x=2; `(Right & Left)[]` has x=1. Grouping does not reverse
that stream. Equal admitted value sets do not imply equal default constructors. No commutativity
law is claimed for construction metadata; membership tests, selectors and field constraints do
not consult defaults. This preserves LANGUAGE.md:4226–4231.

### C1.2 Supplied identities, not whole-value set disjointness

For `a and b`, flatten the supplied nominal facets; merge disjoint plain-record fields into one
structural source. Two supplied plain records with a shared field are rejected: build the one
record explicitly or mint one source to keep two values. Test overlap between **possible supplied
facet identities**, including ancestor/descendant representations, not overlap between selectors'
whole-value sets. `A and B` is useful precisely because its result is selected by both A and B.
Reject if an identity collision is possible after narrowing and generic substitution; retain the
instantiation site in the diagnostic. A family whose possible instances overlap another operand
needs narrowing; an unbounded opaque family is not a proof of disjointness.

`Closed<int>` and `Closed<string>` are different keys; an alias of `Closed<int>` has the same key.
A bare generic family is a selector over its instances, not a concrete stored parameterization.
A fieldless `as Closed` can preserve both instances as the subset `Closed<int> & Closed<string>`;
it does not invent `Closed<any>`. A family with a shared field follows the same ambiguity rule as
an ordinary parent. The duplicate-failure fix-it is the explicit stack; ordinary object repeats
suggest an array. User `and` does not silently lift at a generic instantiation.

### C1.3 Selection and storage answer different questions

`K is? N`, for a nominal selector N, is true if some facet of K is N or its descendant/instance.
For a structural record R, every required field must have one unambiguous provider in K, of the
right type; `&` means both predicates, `|` either, `~` logical negation of the whole predicate.
A field shared by independent sources is ambiguous to read directly, even if its types agree.
A selector's nominal existence test does not read that field, so two file facets still satisfy
`is? FileError`. Stack values are nominal facets, not bags exposed to this test; a nested
`ErrorStack<A>` does not make `is? A` true.

Projection is a separate checked operation (D4/D9):

Compute candidate source subsets for the whole target; reject ambiguity only after its enclosing
constraints have eliminated invalid candidates. Do not reject an intermediate union before a
conjoined constraint can eliminate one alternative.

1. A nominal target keeps all matching nominal facets, with their original identities. If there
   are none, projection is absent. A structural target keeps the sources providing its fields;
   every required field needs one provider. Retaining a source retains its full payload.
2. Conjoined positive requirements union the sources they select. Negative requirements constrain
   that selected subset; they do not add every unrelated source that happens to pass a negative
   test. If there is no positive requirement, a complement target filters facets individually,
   then checks the resulting whole against the complement. Empty kept subsets are absence, not
   successful empty failure values. Normalize double negation and aliases before this step.
3. A union target contributes its alternative candidates. After all enclosing constraints have
   been checked, if successful alternatives keep different subsets, projection is ambiguous
   (D9); if their kept subsets agree, it is not.
   This includes optional targets: `none` is an absence alternative, not another source provider.
4. Validate each candidate against the target, with every field the target exposes having exactly
   one provider. `ReadFailed & CloseFailed as FileError` fails because `FileError.path` has two;
   `as error` keeps both because that parent declares no conflicting field. An exact intersection
   target still permits its deliberately separate facets: their conflicting field requires a
   subsequent leaf projection, rather than pretending the composite has a single such field.
5. Plain `as T` is legal only when every remaining runtime alternative has a successful unique
   projection. An `is? T` guard eliminates nonmembers, but cannot eliminate projection ambiguity.
   For `as T?`, prove absence-or-unique-projection: absence yields none, and possible ambiguity is
   a compile error. Name the leaf facet to repair ambiguity. No new cast syntax or failure type.

These steps define source selection, not construction/default evaluation. Do not apply ordinary
whole-value selector absorption to erase projection alternatives: a projection is a request for
sources as well as a membership constraint. For example `A | (A & B)` and A have equivalent
**selection** predicates, hence identical coverage in C2; the former projection request still
contains two potentially different source selections and is rejected when both apply (D9).
The diagnostic explains this distinction rather than claiming interchangeable storage contracts.
This is D9's explicit policy question, not an internal normalization freedom. Finite candidate
search is charged to the compiler resource budget; exhaustion diagnoses, never arbitrarily picks
an alternative. For `(A | B) & ~A`, the negative constraint can discard the A candidate before
the final uniqueness check; parentheses/aliases cannot change that outcome.

Projection preserves identity on an exact canonical facet/structural shape, and is idempotent
where defined; `as A & B` from A & B & C keeps A and B. Alias expansion and regrouping intersections
cannot change selected sources. `as error` retains all ordinary-error facets. Implicit argument
conversion uses the same unique projection, with provenance retained (C3).

**Holding** a result/binding/field/element is stricter than merely selecting it: its unique
projection must keep the whole supplied value. The compiler does not silently discard an extra
facet on storage or declared return. `cause:error` holds an all-error combination but not an
exception/error pair with a non-error facet. A guard `x is? error` alone does not prove this
all-parts condition. This explains the error-only stack restriction without changing existential
selection or inventing a cancellation exception. Generic aliases and nested stacks obey the same
rule. Returning a wrapper containing a cause transports the cause's duty to the wrapper.

**Gate:** direct/aliased/regrouped nominal and mixed intersections; ordered defaults LR/RL;
parent/child requirements versus independent supplied values; canonical generic instances;
family subsets with and without shared fields; ambiguous guarded and optional casts; optional
absence; exact identity, subset and idempotence; all-error versus mixed-exception stack elements.
These are required paper cases and future executable cases, not tests already passed.

## C2. Exact semantic coverage, with a bounded compiler rather than bounded behavior (M1/M8)

Given a concrete nonempty set F of failure facets and the ordinary selection predicate Sat(K,S),
define:

- W(F,S) = { nonempty K subset of F : Sat(K,S), and no proper nonempty J subset of K has Sat(J,S) }.
- Covered(F,S) = Sat(F,S) and union(W(F,S)) = F.

`??<S>` consumes exactly Covered(F,S); otherwise it leaves F unchanged. `or_throw<S>`, `is? S`
and `match` use Sat(F,S), not Covered. Once forwarding is selected, forward the whole value;
cleanup may subsequently add facets without re-testing the original selector. A match arm binds
the whole selected value and acknowledges only the witness-covered parts, leaving the rest owed.
Plain `??` uses exception plus its existing none case. `none` is an existing defaultable value,
not an invented failure facet.

Evaluate predicates over subsets directly. No projection is required and no field-uniqueness
condition for nominal projection contaminates selection. No disjunctive-form expansion is needed.
For equivalent selection predicates W is identical, including absorption, dead conjuncts,
negation, aliases and factored/distributed forms. Minimum cardinality is deliberately not used:
for `A | (B & C)` on A & B & C, both {A} and {B,C} are inclusion-minimal and all parts are covered.

| F | S | minimal witnesses | consumed? |
|---|---|---|---|
| A & B | A | {A} | no |
| A & B | A \| (A & B) | {A} | no |
| A & B | A & ~Canceled | {A} | no |
| A & B | A \| (B & ~B) | {A} | no |
| A & B | A \| B | {A}, {B} | yes |
| A & B | A & B | {A,B} | yes |
| ReadFailed & CloseFailed | FileError | {ReadFailed}, {CloseFailed} | yes |
| A & B | ~Canceled | {A}, {B} | yes |
| Canceled & A | ~Canceled | {A}, but whole predicate false | no |
| Canceled & A | error | {A} | no |
| Canceled & A | exception | {Canceled}, {A} | yes |

**Reference solver and honest bound.** Keep the selector as a shared expression DAG with Q nodes.
For f facets, evaluate all nonempty subset masks and each predicate once per mask; let L bound
one whole-predicate evaluation including structural/provider and refinement tests. Compute whether
any proper subset satisfies using a subset dynamic program, then select minimal masks and union
them. Time O(2^f * (L + f)), memory O(2^f + Q + f) with bit masks, in addition to the ordinary
predicate prover. A basic structural implementation has L = O(Q * f * h), where h bounds field
requirements/type-relation work after indexing; expensive refinements retain their existing proof
cost/limits. This is an exponential reference algorithm, not the withdrawn facet-pass estimate.
No immediate-subset-only shortcut is sound for arbitrary negation.

A symbolic implementation may share/short-circuit proofs but must agree with that definition.
The compiler uses a finite work budget including normalization, predicate proving and mask work;
resource exhaustion is a compile-time diagnostic at the selector, per D11. It never chooses a
runtime pass-through, and does not quietly select a different fallback. The budget is a compiler
resource bound, not a source-level facet-count rule. The implementation must handle ordinary
17-facet examples within its configured budget or reject compilation explicitly. No automatic
DNF expansion before budgeting. All handler/type alternatives must be proved or compilation
stops; unknown facts never become evidence of coverage.

**Gate:** every table row; union witnesses of different sizes; family targets sharing fields;
equivalent factored/distributed selectors; negation and redundant live branches; wide cases on
both sides of 16; resource exhaustion before/during normalization. Compare against the exhaustive
oracle for small finite domains. C2 adds compile cost only at actual selector uses.

## C3. Acknowledgment, transport and a finite conservative checker (M2/M4)

### C3.1 Semantic responsibility before the analysis approximation

Each dynamic production of a compound failure (including a stack) creates one occurrence with
an outstanding set of its parts. Independent evaluations are independent even at one static
call site. Exact by-value copies of that occurrence share acknowledgment, independently of
whether the backend borrows, copies or moves storage. A part projection retains a link to the
original occurrence for the selected parts. Combining/wrapping existing failures preserves
those links as well as any new compound obligation; it cannot reset their owed sets.

Separate three operations throughout the IR and summaries:

| Operation | Acknowledgment? | Responsibility after it |
|---|---|---|
| Observation, `is?`, logging, reading length | no | unchanged |
| Copy, block result, local binding, nested storage, capture | no | recipients represent the same outstanding occurrence/parts |
| `as A` / implicit projected argument | no | result represents A's duty; unselected parts remain with other holders |
| Covered `??<S>` / selector-covered part of a selected arm | yes, covered parts | unacknowledged parts remain owed |
| Explicit `value;` | yes, everything intentionally dropped with that value | all its represented parts acknowledged |
| Return/`or_throw` from this function | transfer, not global acknowledgment | caller's result carries the outstanding parts |
| Whole container/task result handoff | transfer | the owning recipient carries contained duties |
| A loop handling every element | only with a universal coverage proof | acknowledges the instances and parts actually covered |

A selected `match` arm acknowledges its selector-covered parts at entry; the binder is the whole
value, including any remaining duty. An `is?` branch is only a test and does not acknowledge a
part. Logging a projected A is still observation unless performed inside such a handler.
A block's value cannot acknowledge anything merely by acquiring braces. Storing a whole container
inside another container cannot acknowledge its contents.

An occurrence's last **guaranteed responsible** local holder must not disappear on a reachable
abstract path while it owes parts, unless responsibility transfers through a verified owning
boundary. A mere possible alias is insufficient to prove such a holder exists. A full function
return passes that duty to its caller, including inside a wrapper/aggregate. A successful send
or task-result publication transfers to a checked owning recipient; a failed send preserves the
unsent value's duty in its returned owner (the existing Unsent contract). This is not permission
to send raw exceptions through channels that prohibit them: use their existing wrapper rule.
Unverified foreign escapes do not count as responsible destinations.

**Calls distinguish borrowed responsibility from locally created responsibility.** Each parameter
has a symbolic external caller representative at function entry. An observer may leave its
parameter unacknowledged: its summary returns that duty to the caller. It may not export an
unacknowledged *locally created* occurrence without an actual result/owning handoff. `observe(v)`
therefore compiles as a helper but cannot make `let v=pair; observe(v)` compile as a whole caller.
A function returning its argument exports provenance rather than an acknowledgment mask.
Projection returned from a helper exports only that subset; the caller still owes the rest.

Required negative cases: M2's `let saved={pair}; printl(saved)` and `let nested=[[pair]];
printl(nested.length)` both fail. Appending `saved ??<A|B> void` or `nested;` respectively repairs
them. D10's copied-then-handled case passes. Replacing handle with observe fails. A returned or
sent wrapper passes responsibility, which its recipient must then meet.

### C3.2 Indexed finite abstract state; independent loop instances never collapse into one duty

Use indexed tables for relevant CFG nodes, origins, places and demanded call instances. A place
is a binding, temporary, fixed aggregate path, capture, external parameter holder, return/escape
slot, or a summary place for a dynamic container. Fixed-size arrays may be indexed by element;
unknown indices use their container's summary place. Origins are static producers, parameter
origins, and fresh-result origins. Part slots include demanded projections as well as nominal
parts; an implementation may widen a large part set to one whole-value duty, losing precision
and issuing D11's diagnostic if a partial proof is then needed.

The chosen finite reference abstraction uses:

- **Distinguished tokens** for one current instance at a creation/extraction site, plus a
  **summary bucket** for older/multiple instances there. Re-executing a site promotes any still
  represented older token to its bucket before assigning a new current token; all its aliases'
  provenance is updated. Thus a token never means both “this new failure” and “all prior failures”.
- Bucket population states 0, 1, 2-or-more, with unknown represented as a set of those possibilities.
  Counts refer to independent instances, not numbers of copies. Removing one from 2-or-more
  yields 1 or 2-or-more, never 0 by assumption. Unbounded instances use fixed-size state.
- Per-token/bucket may-owe part bits and a place-to-token/bucket relation, including whether a
  place definitely holds the distinguished instance, may hold some bucket members, or covers
  **all** members of that bucket. Include must-alias relations between exact copies and proven
  whole snapshots. A count alone is never used to identify a representative.
- An acknowledgment clears a distinguished token's selected bits across exact aliases. It does
  not clear a bucket from one unknown-index read/pop. A proven singleton bucket can be split
  into a distinguished token; otherwise extraction creates a token for the extracted element
  while retaining a nonzero/possibly nonzero residual bucket. If old aliases cannot be related
  precisely, weaken their provenance instead of acknowledging them.
- Clearing a whole bucket requires a must-cover certificate: a whole holder contains all members,
  and is wholly handled/dropped/transferred, or a full traversal handles every element on every
  continuing path. A loop with break, a path skipping handling, mutation skipping elements, or
  a body handling only one branch has no such certificate. Definite full coverage can be
  recognized from the language's existing full-container iteration, without proving arbitrary
  arithmetic termination. Only the traversal's completed exit obtains the full-coverage fact;
  early return/break/throw paths are checked with their unvisited elements still outstanding.
  A collector loop invariant establishes where all accumulated members reside. No unknown-index observation establishes it.
- Fixed copies `[p p]` retain the same distinguished token twice; `[pair pair]` has independent
  tokens. Whole copies of dynamic containers can keep a must-alias snapshot relation until
  mutation. After mutation, preservation of only a shared prefix may be unprovable; the checker
  may reject a later attempted cross-copy discharge. It must not acknowledge unrelated members.

Every transfer must overapproximate its concrete executions. Abstract cardinality operations
split successor possibilities; uncertain aliasing weakens must facts and adds may facts.
For a summary bucket, all-coverage facts survive a transfer only with a proof that every member
still has that holder. If a bucket loses its last proven coverage holder while possibly owing
anything, retain/report that bad possibility even if some may-alias remains elsewhere.
This conservative rule can reject safe programs; it cannot accept a leak by inventing an alias.

**Joins.** The reference domain is a set of complete abstract valuations, joined by set union,
not by adding representative counts or unioning favorable acknowledgment facts. Each valuation
keeps its own owed/provenance/coverage/cardinality facts. Ordinary branches explore both edges
unless the existing prover eliminates one; feasible-path exactness is not claimed. At a join,
a holder present only on another branch cannot save the current valuation. An implementation
may merge valuations by a sound overapproximation (may facts union, must facts intersection,
counts widened); loss of precision can only add a diagnostic or request a whole-value proof.

For M4's repeated `xs.push(pair)`, earlier generations accumulate in a bucket covered by xs.
`pop` singles out the removed member; the residual bucket remains owed. Handling last cannot
clear it. A full traversal whose body covers each element can clear all its element duties;
if the container itself is a stack occurrence, its own separate compound duty is acknowledged
by a whole stack handler/drop as in D16. This distinction prevents both per-site erasure and a
read-only stack loop accidentally acknowledging the stack itself.

### C3.3 Relational summaries and demand closure

A checked summary relates abstract input provenance/alias configurations to possible output
configurations, acknowledgment events, owning escapes and fresh origins. It records must/may
return separately via that relation, projected part subsets, aggregate paths and conditional
choices between arguments. It is not one per-parameter bitset plus a returns-a-copy boolean.
Substitute actual aliases at the call. For a helper that handles one of two parameters, the
relation can prove that passing the same distinguished occurrence twice handles it on both
branches; a widened summary may instead reject this correlated case, expressly as a precision
limit under D11. Possible handling never becomes guaranteed handling at a join.

A known direct call uses its checked summary. A handle uses the union of known possible targets;
if any target is opaque, use an opaque relation: no guaranteed acknowledgment, returned provenance
may include any compatible input plus fresh values, and owning escape needs an explicit checked
contract. “Unknown” is not “returns no representative”. Lack of a known summary does not prove
the last holder can die. Opaque results can be conservatively retained/handled whole; if that
still cannot prove preservation, diagnose at the boundary. Foreign annotations are trusted only
under the existing foreign-contract rules, not synthesized from the call's name.

**Demand starts at actual compound productions/uses**, not signatures that spell `&`: automatic
cleanup combinations, stack construction, compound-valued runtime results, and demanded handler,
projection or storage sites. Follow origin/projection flow through fields, generic arguments,
containers and calls; demand parameter acknowledgment/provenance summaries where those flows use
them. Thus a helper accepting broad `error`, or just a projected A, can be demanded. A dead
purely type-level occurrence of `A & B` alone does not start flow checking. Unknown compatibility
adds dependencies conservatively. Re-run the closure when specialization reveals a new producer.
Existing effect/type work for this discovery is counted in the gate, not called free.

### C3.4 Finite bound, without the withdrawn near-linear worst-case claim

One explicit reference implementation retains finite valuation sets. Let O be indexed origin
sites, R relevant places, P tracked part slots, V/E demanded CFG nodes/edges, and H demanded
function instances. There are at most T = 2(O+R) token/bucket labels when extraction sites are
included among places. A valuation can be encoded by

    B = O(T*P + T*R*(P+1) + R*R + T*T + R + T)

bits: owed/part provenance, may/must/all-coverage relations, alias/equality relations, finite
population tags, liveness and status flags. Extra layout/escape paths must be included in R;
there is no unbounded dynamic origin list. Let K <= 2^B bound the finite valuations, including
bad-state flags. Use bitsets/sparse indexed relations for each valuation. This is an intentionally
loose exponential bound; the analysis does not promise cheap exact correlations.

Intraprocedurally, an incremental worklist can insert each (node, valuation) at most once. Allowing
up to K successors and O(B^2) relation work per transfer gives O(E*K^2*B^2) time and O(V*K*B)
state. For calls, memoize at most K input contexts per instance and a finite relation of at most
K^2 input/output tuples. Compute recursive SCCs by monotone addition of behaviors, starting empty;
opaque targets start with their conservative top relation. Do not certify an acknowledgment from
an incomplete/vacuously empty recursion summary. Diagnose only after the demanded closure and
relations stabilize, or on a definite reachable bad-state witness independent of missing returns.

For a deliberately simple implementation that re-analyzes all contexts after each new summary
tuple, at most H*K^2 additions and O(E*K^3*B^2) work per reanalysis give the coarse global bound
O(H*E*K^5*B^2), with O(V*K^2*B + H*K^2*B) stored state/relations. This includes finite SCC iteration;
it is not a recommended production strategy. A better sparse/widened implementation must state
its own sound abstraction and bound, and preserve the D11 failure policy. Configured resource
limits bound actual work even for the reference procedure; exceeding them stops compilation.
These bounds deliberately include place-origin association state and loop multiplicity, which
round 4 omitted. B and K are theoretical limits, not measured compiler overhead.

**Landing gate:** compare the unchanged flagship panel and self-build before/after on one named
host using load-independent user instructions and the existing speed gates. Include root,
library and generic-instance work; all-processed-lines throughput derived from instructions;
phase instructions per processed node; peak analysis memory; demanded/skipped functions;
O/R/P and actual associations; worklist state insertions/revisits, widenings and SCC iterations.
Measure a no-obligation workload for dormant discovery overhead. Exercise repeated same-site
array instances, fixed/dynamic copies, nested containers, block handoff, branch joins, projected
and opaque calls, conditional aliases, recursion and large-part widening. If the realistic
panel cannot meet the gate, redesign the abstraction before landing; this paper bound is not
performance evidence or permission to ship a pathological checker.

## C4. Escaping storage and allocation-refusal transport (M3/S3)

### C4.1 Reserve the whole nonallocating completion path

A reserved link is insufficient. Before acquiring a fallible owner, reserve all storage needed
for its failure payload, retained context, lifetime/ownership metadata and immutable result link.
Before a function has its first fallible owner, also reserve an **escaping pending-value capsule**
sized for its possible inline body failures and the finite kind/shape descriptors its completion
can need. Dynamic arrays/stacks use handles, not inline copies of all their elements. Recursive
results use the same fixed-size carrier ABI at every level; each frame reserves its own capsule
and each owner its own failure storage. Capacity is bounded by static payload/carrier size and
kind descriptors, never by recursion depth or number of failed owners.

This capsule makes `pending=Canceled`, or any other inline failure, stable without boxing during
cleanup. Existing heap-backed failures/stacks can instead be retained by allocation-free handle
copy/refcount operations. A pending success is withheld until cleanup succeeds; owners in that
withheld value have registered completion duties and are released if the handoff fails. A failed
cleanup replaces success with a failure, and combines with a pending failure. No success payload
is reinterpreted as a failure part.

Acquisition sequence: reserve capsule if needed; reserve owner slot and context; create/register
its temporary holder; perform native acquisition; publish the live owner only on success.
Refusal or native acquisition failure creates no duty for a nonexistent resource and releases
unused reservations. It does **not** mean earlier live owners have nothing to clean up. Moving
an owner transfers its slot and registration; it never allocates at cleanup. Before a growing
array push can allocate, the argument's temporary owner is already registered. On refusal that
temporary and existing elements are on the unwind list. The statement does not resume with a
local `OutOfMemory` result.

All completion operations, including payload construction, demanded origin/trace capture,
reference retention, normalization, result packaging and terminal native release, have a checked
no-allocation/no-panic path. User hook checks keep their existing prohibitions on allocation,
COW detachment, opaque effects and escaping state; adding a returned failure does not waive them.
A custom cleanup message needing string building must be precomputed at acquisition, or the hook
is rejected. A library adapter needs a concrete audited nonallocating implementation, not the
old blanket exemption. A demanded trace uses an already retained stable frame-chain representation
reserved as calls enter, or a proved pre-reserved snapshot; walking/refcounting that chain during
completion allocates nothing. Its entry/reservation costs and possible refusal are ordinary
allocation effects. If that representation cannot meet the contract on a target, trace support
for that path is an unpassed gate, not permission to allocate during unwind.

### C4.2 One pending accumulator survives the allocation jump

Each active recoverable allocation-failure boundary has a fixed-size unwind record in the
wrapper/runtime context that remains live across the jump. It contains the pending tagged
carrier, intrusive head/tail references to reserved slots, and owner-unwind state. It is not a
local in the interrupted inner function. The caller's return carrier can receive an inline
OutOfMemory without any fresh allocation if no resource/capsule was established yet.

On refusal:

1. Select the nearest existing recoverable boundary, exactly as today. Mark OutOfMemory as a
   pending failure in its unwind record. If ordinary propagation/completion already has a pending
   failure, retain it too; do not overwrite it with the new tag. Scalar tags/codes and carrier
   references fit the pre-existing record. An already recorded OutOfMemory is not a second
   independent failure merely because the runtime observes the same refusal twice.
2. Establish pending inline payloads in their previously reserved capsules before their creating
   frames are invalidated. Shared snapshots remain immutable. The runtime's unwind record points
   only to those durable capsules, owner slots or existing durable values before it jumps.
3. Walk registered live owners back to this boundary. Each writes into its reserved payload,
   relinquishes its native resource once, and publishes a slot only if it fails. Link new slots
   without modifying a pending value or any shared snapshot. Parent/recursive frames add their
   own slots while the pending carrier survives.
4. Only after that walk, restore the allocator/context and jump to the wrapper. The wrapper returns
   the **accumulated result**, not the hard-coded OutOfMemory singleton in today's oom lowering.
   Infer all its cleanup-augmented alternatives under the same rule as other function exits.
5. An enclosing frame receives that value normally. If a later independent allocation fails in
   the enclosing function, its boundary starts/preserves its own pending accumulator and performs
   its own cleanup. Never point the outer result into a finished inner wrapper's local record.

The runtime must track owners as Registered -> Running -> Released, retaining an explicit current
owner until its completion/backstop finishes. Today's unlink-before-hook implementation is not
sufficient for this protocol. A consumed native close is never retried as a way of recovering
from interruption. On admitted adapters, nonallocating terminal release/quarantine is established
for every completion outcome. If a native failure leaves recoverable state, that recovery token
must be transferred into pre-reserved failure storage or a pre-reserved quarantine owner; its
lifetime cannot depend on the interrupted frame. Do not claim external effects were undone merely
because a local variable was consumed. This release contract is checked per adapter/handle class;
unsupported classes cannot enter the automatic-completion path under a fictitious infallibility
assumption. The lock-hook assumptions row is unchanged.

An allocation request inside a purported no-allocation completion path is a contract violation,
not an alternate user-visible local recovery path. Ordinary source is rejected by effects before
it can do this. Trusted adapters must be fault-tested/audited for the same property; no return-
value guarantee is claimed for a foreign implementation that violates its trusted contract.
This is the chosen no-allocation solution to M3, rather than promising to resume an arbitrary
interrupted allocating hook. The allowed path therefore cannot introduce a second refusal during
cleanup-payload construction or release.

Worked refusal cases:

- F1 live; F2 slot refused: F2 never exists; F1's close writes its already reserved slot; the
  boundary returns OutOfMemory & FileCloseFailed. Same with an owner temporary in a refused push.
- A previously pending inline failure (including Canceled) plus an independent body refusal:
  retain both before cleanup; append every cleanup failure. If no new allocation was attempted,
  do not invent OutOfMemory. No cancellation-point/shielding policy is changed by this carrier.
- A cleanup constructor attempting dynamic message/boxing allocation: reject at effect checking;
  fault injection verifies no allocation call on the admitted replacement path, which writes
  static/retained payload data. “Tested under refusal” must not mean silently skipping the payload.
- Nested allocation frames and recursive normal returns: every pending value refers to escaping
  reservations, not a departed C/Jo/Dewy stack slot. Each boundary returns its own accumulated value.

Without an active recoverable boundary, ordinary refusal still terminates under the documented
policy. WebAssembly refusal still terminates because recovery is unsupported; do not advertise
a cleanup-augmented returned failure there. This round does not promise reclamation of all
interrupted ordinary allocations or cleanup under process termination.

### C4.3 Lifetime, reclamation, representation and costs

Reservations belong to the owner/result allocation domain and must outlive every result reference.
They cannot be pointers into a borrowed scratch arena after that arena resets. Use the current
allocator only when its lifetime admits the escaping result; otherwise pre-reserve durable
storage in the enclosing allowed domain before entering that allocator scope, with its effects
and caps charged there, or reject the escape. Do not silently choose the global heap. The existing
arena ban on escaping owners/closures/raw pointers is not weakened. An implementation must prove
that even an error-only escape does not smuggle an arena slot past reset. If it cannot, reject
the fallible acquisition in that region, explaining the missing durable reservation.

Unused slots/capsules are released after successful completion or failed acquisition; a failed
slot transfers to the immutable result and is freed after its last reference. Each link owns
its next/prior references. Dropping deep chains uses a nonrecursive intrusive release walk,
without allocating or overflowing the native stack. Copy snapshots retain nodes; no tail mutation
of an old stack is permitted even on a return path. COW mutation allocates/copies before publication;
refusal leaves old shared snapshots unchanged and follows the ordinary boundary policy.

An illustrative **proposed** 64-bit, 8-byte-aligned File slot layout (not a measurement of the
current ABI): refcount 8, next 8, prior carrier reference 8, descriptor 8, cached count 8, first
leaf reference 8, last leaf reference 8, tag/state 8 = **64-byte header**. A retained two-word path
handle (16), native status/operation words (8), demanded site-id plus padding (8) make a 32-byte
payload, **96 bytes total**. A demanded retained trace handle adds another 8 bytes in this layout.
Static messages come from the descriptor. Undemanded origin/trace fields may disappear; other
payloads need their own size/alignment and cannot use this File estimate. Root kind/shape tables
and the pending-value capsule are additional, sized from the instantiated function's type.
Replace round 4's unsupported approximately-32-byte all-in estimate.

A published stack view caches count/first/last for its logical entries, including any referenced
prior segment. Build these caches during nonallocating combination, scanning existing segments
if necessary; construction is not promised constant time. Accessing length/first/last is O(1),
indexing O(s) in segment count s (O(n) worst case), iteration O(n+s), and detach/mutable-view
creation O(n+s) time and O(n) fresh element storage in the worst case. Per-kind views needed by
D17 use reserved static descriptors/counters, never a growing hash map during unwind. Sharing
never justifies writing into a prior snapshot. All extra allocation, copies, retained bytes and
possible acquisition refusal participate in existing effect/cap/strict-mode checks.

**Landing gates:** allocation refused at F2 reservation with failing F1; refused array growth
with registered temporary; deep recursion; full/shared pending stacks; inline pending failures;
nested recoverable frames; failure-payload allocation rejected; traced cleanup with no allocation;
arena reset/escape; acquisition failure reclamation; deep chain release; COW-detach refusal;
WebAssembly termination behavior unchanged. Fault-inject native completion/release separately
from allocator refusal. Record acquisition allocation count, slot/capsule/root/trace bytes, peak
retained bytes and cleanup instructions. No slot/reservation design is accepted on the strength
of its prose alone.

## C5. Completion state machines and portable result construction (M7/M8/S2/N2)

### C5.1 Failure mapping and no suppression

There is no Linux-wide read-close exception. A recognized native completion error becomes the
corresponding completion failure, even where the native handle has already been released. A
truly infallible admitted operation may have `void` completion only with a concrete handle-class/
target contract and fault-injected mapping tests. Descriptor release alone is not such a proof.
No strict-mode switch changes which recognized failures appear.

Under D5, acquisition retains the existing useful file leaves (`FileNotFound`, `FileAccessDenied`,
`IsDirectory`, `FileExists`) now under FileError; an unmapped acquisition failure uses that family’s
ordinary generic failure. Once a handle exists, operation failures normalize to FileReadFailed,
FileWriteFailed, FileCloseFailed or FileRemoveFailed as appropriate, retaining native reason/path
in the established payload/diagnostic representation. This mapping is part of the D5 proposal,
not a second parallel taxonomy secretly introduced here. Socket/process/database adapters follow
their operation families. No public native-status member is invented by the internal C4 layout.

A consuming close relinquishes its local duty on success **and** failure, once. Native interrupted-
close semantics and any terminal recovery/quarantine are specified for each adapter; no blind
retry and no second automatic close. When cleanup encounters another independently failed owner
of the same kind, use D17's stack packaging rather than a forbidden duplicate intersection.

### C5.2 Read bytes and read text are different pipelines

Let O denote admitted open/acquisition failures (including reservation refusal when recoverable),
R denote FileReadFailed and the already permitted interruption/refusal outcomes during the read,
and C denote FileCloseFailed. These letters are mathematical sets, not new public type aliases.
The helper owns one file handle. Allocate/construct only under the existing allocation policy.

| Stage | Owner after the stage | Failure result / next action |
|---|---|---|
| Reserve/acquire | no file on failure | O; no close of a nonexistent handle |
| Read all bytes | live file | on R, retain R, consume-close once; return R or R & C |
| Read succeeded, consume-close | consumed on either outcome | C on failed close; withhold bytes and skip decoding |
| Bytes helper after successful close | no file | return array<uint8> |
| Text helper after successful close | no file | decode: string or InvalidUtf8; ordinary decode allocation refusal if enabled |

Thus the bytes result set is `array<uint8> | O | R | C | (R & C)` and the text set is
`string | O | R | C | (R & C) | InvalidUtf8`, plus any decode-refusal outcome not already in O/R.
Expand R into its actual permitted alternatives at instantiation; do not silently add cancellation
points, or copy string/InvalidUtf8 into the bytes signature. Include OutOfMemory only where the
existing allocation mode/effects admit recovery. These are alternative generators: not shorthand
for flattening a pair into a single shared-field FileError parameter, which would lose holding.
A hand-written decode-before-cleanup helper can still produce InvalidUtf8 & FileCloseFailed.

### C5.3 Atomic writes: every transition has one owner and one replacement state

Text is already a valid string; the bytes helper takes array<uint8>. Both return byte count on
success. Pre-reserve the temporary/operation state, replacement marker and eventual directory
handle's completion storage before publishing native owners; any additional reservation refusal
has the existing function-level effect. Replacement state starts false and is set true only
after successful rename. Never change it back after that transition.

| Stage / observed failure | Replacement | Completion work and result contributions |
|---|---|---|
| Preflight/reservation/temp acquisition fails | false | Return acquisition/refusal failure; remove nothing unless creation actually succeeded and registered the temporary |
| Write or flush fails | false | FileWriteFailed(false); consume-close the still-live temporary once, adding FileCloseFailed if observed; remove existing temporary once, adding FileRemoveFailed if observed |
| Temporary consume-close itself fails | false | FileCloseFailed; close is consumed, so only attempt temporary removal; add FileRemoveFailed if observed; do not rename |
| Temporary close succeeds | false | Its handle duty ends; continue to rename |
| Rename fails | false | FileWriteFailed(false); no remaining temporary handle to close; remove the still-existing temporary, adding FileRemoveFailed if observed |
| Rename succeeds | true | Temporary name is no longer owned; target has been replaced; never remove target as failed-write cleanup |
| Directory handle acquisition fails | true | FileWriteFailed(true), normalized for this operation stage; no nonexistent directory handle to close |
| Directory sync fails | true | FileWriteFailed(true); consume-close directory once; add FileCloseFailed if observed |
| Directory sync succeeds, directory consume-close fails | true | FileWriteFailed(true) operation-incomplete marker and the actual FileCloseFailed for the directory |
| Directory close succeeds after sync | true | Return byte count; no owners/duties left in the helper |
| Recoverable refusal before rename | false | Function unwind returns OutOfMemory plus actual temporary close/removal failures; no locally caught push/allocation result |
| Recoverable refusal after rename | true | OutOfMemory plus FileWriteFailed(true) incomplete-operation marker and any actual remaining directory completion failure; never undo replacement |
| An already allowed cancellation is observed | current state | Preserve Canceled and actual remaining completion failures; if state is true, also FileWriteFailed(true) incomplete-operation marker |

The post-rename marker is explicitly part of D14's proposed public contract: it records failure
to complete the helper's promised protocol, not a second native failure. Emit it once. A native
sync error already normalized to FileWriteFailed(true) supplies that marker; do not add another
identically typed peer. A close-only failure after sync needs the marker because FileCloseFailed
alone cannot say that this atomic-write helper has already replaced the target. A failed write
with replaced=false does not assert that an external actor left the target unchanged; it says
this operation did not install its new file. After true, no error path asserts crash durability.
An inability to establish an atomic/durability step on a target is an operation failure, not
successful partial emulation. No new cancellation point or shielding policy follows from the
table: the cancellation row is conditional on the separate design's admitted points.

Native owner state is explicit (`not acquired`, `live`, `consumed/released`), separate from whether
a temporary pathname exists. Closing failure does not rewind that state. Cleanup checks state,
not a generic “on failure close and remove” template. This sequence needs at most one live file
handle at a time; if an adapter's implementation owns more, its result generator includes D17's
repeated-close stack. Fault injection must cover every owned handle rather than suppress extras
to preserve this table's simpler shape.

### C5.4 Commit consumes even when the outcome is a failure

| Transaction state/event | Action and resulting duty |
|---|---|
| begin fails | no transaction owner; return its acquisition failure |
| live tx exits without explicit completion | automatic abandon attempts rollback once |
| commit begins | transfer tx into the consuming operation's registered temporary; caller binding is consumed |
| native commit succeeds | release transaction-local state once; no automatic rollback |
| native commit fails while tx can remain active | retain CommitFailed; attempt rollback once before return |
| rollback succeeds or native driver already rolled back | no live transaction; return CommitFailed without inventing RollbackFailed |
| rollback fails | return CommitFailed & RollbackFailed; terminal release/quarantine or recovery-token ownership follows the adapter contract |
| allocation refusal interrupts an allocating explicit commit | existing allocation frame unwinds the registered temporary; return OutOfMemory plus actual rollback/release failures, and any independently established pending commit failure |

For an already permitted interruption, use its pending failure in place of CommitFailed if no
commit failure was actually observed, then perform the same checked terminal path. Do not invent
cancellation points. On every returned result, tx is consumed; no second automatic abandon.
A driver with indeterminate remote commit outcome reports that uncertainty and quarantines the
connection; it must not label rollback success as proof that no remote write committed. The
adapter proves its nonallocating abandon/release path and ownership of remaining recovery state.
A quarantined connection is not offered for another query until its native contract permits it.
No new public member spelling for native commit uncertainty is specified here; if typed access
beyond the existing failure diagnostic is needed, it needs its own surface proposal.

**Gate for C5:** inject each acquisition/read/write/flush/close/rename/directory-sync/removal/
commit/rollback outcome; observe every real failure exactly once; count native release calls;
check no removal before creation or after successful rename; verify byte count versus text decode
results; validate replacement information including close-only post-rename failure; quarantine
indeterminate outcomes; assert full cleanup-augmented types including recoverable allocation
refusal. These are executable acceptance requirements, not claims of cross-platform validation.

## C6. Final-result exit rule (unchanged mechanism; D7 awaits the cancellation round)

Conditionally on D7, success exits 0; an escaping failure uses its kind's exit code; a combination
or stack uses the maximum of its recursively contained failures' codes. Ordered stacks report
in their stored order; a combination offers no ordering guarantee, as David decided. A handled
failure has no sticky process status. `exit(n)` keeps its immediate documented behavior. This
round adds no independent cancellation status or signal-listener rule. D7 itself is unchanged.

## C7. Origin/trace demand and packaging

D8's proposed names and the inherited whole-source-build demand closure stand. Demand follows
actual parameter/result/container flows, generic instantiations, callbacks, formatting and effect
edges. An unused origin/trace query does not justify universal capture. Conversely, a broad or
opaque flow adds compatible demand conservatively. Demand-driven metadata must meet C4's
nonallocating completion contract, including trace storage and escaping lifetimes; its acquisition/
entry costs belong in the existing allocation effects and measurement gate. Keep the previous
programs unchanged; in particular program 15's wrapper preserves both its ordinary-error subset
and any separate exception facet through its declared result. No new wrapper helper is introduced.

## Audit disposition and validation record

| Finding | Contract repair | Policy location / remaining gate |
|---|---|---|
| M1 — inequivalent coverage definitions | C2 defines only minimal nonempty witnesses; independent predicate solver, no projection/DNF shortcut | D1 clarification; exhaustive-oracle/equivalence and resource-limit gates |
| M2 — transport erases obligations | C3 separates acknowledgment/transport at every boundary and propagates returned provenance | D10; both block/nested-container counterexamples must reject |
| M3 — refusal loses pending/cleanup failures | C4 adds durable capsules, nonallocating accumulator, wrapper-result transport, complete payload/release checks | D15; refused F2/push, pending value, nested frames and WebAssembly gates |
| M4 — nonfinite/incomplete analysis | C3 gives token generations/buckets, provenance/coverage joins, relational summaries, demand closure and finite exponential bounds | D10/D11; precision limits disclosed and flagship gate pending |
| M5 — guard does not prove projection | C1 separates existential selection from unique projection; optional absence does not cure ambiguity | D9; ambiguous guarded/optional cases reject |
| M6 — unordered defaults contradiction | C1 separates commuting constraints from ordered constructor streams | D4/taken item; LR/RL values remain 2/1 |
| M7 — unsupported read-close suppression | C5 removes it without replacement assumptions | taken D40 extension; target mapping fault tests pending |
| M8 — hidden public policies | Part 1 now carries projection, acknowledgment/precision, close/decode order, commit ownership, replacement state, refusal extension, stack API/shape | D9–D17; no unapproved surface treated as accepted |
| S1 — facet identities/generic families | C1 keys instantiated identities and distinguishes supplied-facet overlap from selector overlap | taken extension; leaf/family/alias gate |
| S2 — incomplete operation states/signatures | C5 splits reads and supplies full write/transaction transition tables | D12–D14; transition/failure mapping gates |
| S3 — lifetime/layout/cost | C4 gives escape allocator rule, success/failure reclamation, proposed 96-byte File layout and explicit complexity/effects | D15/D16; layout and cost measurements pending |
| S4 — stack element admissibility | C1 uses whole holding, not existential `is? error` | D16; mixed-exception/alias/nested-stack gates |

N1's distinction between repeated type requirements and supplied values is retained. N2's
explicit early completion remains compatible with whichever cleanup timing David chooses in
D40; this round neither settles that timing nor removes its pending visible-exit requirement.
N3's result-based exit mechanism remains conditional on unchanged D7. No rejected sticky-status
rule or read-close suppression is revived.

**What this resolves.** All eight must-fixes have a paper-contract repair; none is left as an
unanswered implementation-contract contradiction. David's new policy questions remain choices,
not approvals assumed by the implementation. Runtime/analysis/performance/cross-target gates
remain unrun. A failed future storage or cost gate requires redesign before landing.

**Checks performed for this artifact.** Verified that D2, D3 and D7 exactly match round 4,
all eight must-fixes have disposition rows, and Markdown code fences are paired. The reference
coverage solver was also checked against a separate exhaustive minimal-subset oracle as described
below. These checks validate the document/finite definition, not a Dewy compiler implementation.

**Program/grade status.** No existing program file or grade was changed, so no programs-r5 or
regrade artifact is created. The added minimal examples and transition/refusal cases here are
paper acceptance cases, not compiled or independently graded. Round 4's honest sub-5 grades remain,
including stack-shape discoverability and wrapping concision; this round does not upgrade them
on the strength of a repaired contract. D14's untested member remains provisional and not ready
for promotion to open_decisions.md without its naming/API exercises.

**Finite solver check.** An in-memory reference implementation of C2's subset dynamic program
matched a separately enumerated minimal-witness oracle on 5,700 expression/facet-set cases:
500 generated Boolean expressions over 1–5 facets, including existential-family atoms, unique-
provider atoms, negation, conjunction and disjunction, across their nonempty facet sets. Five
targeted fixtures covered absorption, a negative conjunct, union coverage and witnesses of
different sizes. This checks the finite solver definition only; it is not selector-prover,
obligation-analysis or runtime validation. No benchmark claim is made.
