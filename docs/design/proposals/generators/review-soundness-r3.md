# Soundness review, generators round 3

Reviewed [sketch.md](sketch.md), [round2.md](round2.md), and [round3.md](round3.md) against the current iterator loop, `or_throw`, cancellation, and cleanup rules. Round 3 replaces round 2 where they differ. Recommended option A is assumed except where a rule is still two-valued.

Severity: **unsound** (a rule produces a wrong value, a missed failure, or a double use), **undefined** (two live rules disagree, or an exit has no outcome), **surprising** (a simpler local rule would avoid a wrong program that still typechecks), **minor**.

## 1. Unsound — a plain loop turns cancellation into a successful end

Round 3 says item, end, and terminal failure stay distinct through iteration and delegation. Round 2 also says a streaming `child...` forwards like `loop x in child or_throw x`, while D44 Q5 (still the recommendation) makes a plain loop end quietly on `Canceled`, and the code after that loop runs. `Canceled` is not part of written `failure=`, so an infallible `generator<int>` still accepts the quiet loop. The sketch’s `map` is that loop.

```dewy
map = (source f) => lazy { loop x in source { f(x) } }

save = (source journal) => {
    let n = 0
    loop token in map(source @id) { journal.write(token) n += 1 }
    else { journal.commit_empty() }   # body never entered
    journal.commit(n)                  # runs after a quiet cancel too
}
```

Cancel the task on the first blocked pull, before any item. The inner loop ends as if `source` were empty. `map`’s body then ends and its cursor reports end, not `Canceled`. `save`’s `else` runs when no token arrived, and `commit` runs when some did. `source...` in the same place would forward `Canceled` and skip both. A wrapper written the way the sketch writes `map` publishes a successful journal for a canceled stream.

The same split hits `take` in [06-retry-preview-r3.dewy](programs-r1/06-retry-preview-r3.dewy): the `and` header has no `or_throw`. A cancel on the right side is specified both as “right fails, forward” (round 2 §3) and as “the loop ends” (D44 Q5). One reading reports failure; the other yields a short successful prefix.

## 2. Unsound — flat `next` makes a terminal failure a loop item

[LANGUAGE.md](../../../../docs/LANGUAGE.md:5014) still says a value with `next` is an iterator: the loop calls `next` until `none` and binds every other result. The current lowering does that (`checker_iterator_rewrites.dewy` breaks only on `none` / `Closed`, then binds the step). Round 3 adds `g.next` → item, `none`, or the terminal exception itself, whenever those three are disjoint. It never says a generator is not an iterator, and round 2 tells existing `next` iterators to keep that protocol.

```dewy
Bad:type = type of error & [offset:int64]
let g = lazy { 1; Bad[0] or_throw }
loop x in g { printl(x) }
```

`Bad` is disjoint from `int` and from `none`, so flat `next` is legal. The iterator loop prints `1`, then prints `Bad[0]` as data, then stops because the following advance returns `none` and does not repeat the failure. The failure was consumed as an item. Round 3’s own table says this loop must not bind `Bad` and must forward it. Both rules are in force; the implemented one drops the terminal outcome on the floor.

`loop x in g` is also “step a copy” in that same paragraph and “move the owner” in round 3. If the copy is real, `break` disposes the copy and the original still runs its `defer` later (cleanup twice), or the two cursors share one frame and both advance it. If the copy is rejected because the cursor is move-only, the owning loop round 3 recommends does not compile.

## 3. Unsound — `length=` is the birth count, and a callee trusts it as the remaining count

Round 2 defines `length=N` as a proof about the **original** successful traversal, and also says `g.next` changes the **remaining** count. Those are different numbers. Only the birth count is in the type. A parameter or field stamped `length=2` has no place to record that a caller already pulled.

```dewy
two = ():>generator<int64 length=2> => lazy (20 22)
pair = (g: generator<int64 length=2>) => add(g...)   # demands two remaining ints
let g = two()
let _ = g.next          # yields 20; one item remains
pair(g)                 # still generator<int64 length=2>
```

`pair` spreads with a proof of two integers and then calls `add`. One integer remains, so `add` is entered with the wrong arity, or the missing argument is defaulted. Round 2 says a birth proof must not justify a spread after a partial pull, but inside `pair` the cursor arrives with no history, only the type. Flow facts from the caller’s `next` do not cross the signature. The same lie is `Box[cursor: generator<int64 length=2>]` after `box.cursor.next`.

A written `generator<T>` has the dual hole for failures. Omitted `failure` means no ordinary terminal failure, and round 2 requires a narrower `T` to accept every item, but it never requires the failure bound to accept the body’s terminal failures.

```dewy
risky = ():>generator<int64> => lazy { read_int() or_throw }
let n = risky().next
if n is? none { use_default() } else { use(n) }
```

If the annotation is trusted, `next` is typed `int64 | none` and `ReadFailed` falls into `use(n)`.

## 4. Unsound — a loan stored for the next resume dangles when the cursor moves

Round 2 snapshots free locals at construction, and also evaluates a loop source only when that loop is reached. For a move-only source those are different owners. It also says an unproved borrow across suspension is rejected, but a child owned by the parent is a proved nesting, and inline frames are an allowed representation (“state in an inline object”).

```dewy
let sock = connect() or_throw
let g = lazy loop row in sock.rows() row
let other = sock
let row = g.next
```

Snapshot-at-construction moves `sock` into `g`, and `let other = sock` is a use after move. Lookup-at-first-demand leaves `sock` in place, so `other` and `g` are two owners of one socket: `g.next` reads it, and dropping `other` and `g` closes it twice. Nothing picks which sentence wins, or whether the loan starts at `lazy` or at the first pull. A write to a copyable buffer is the same gap: the `n = 2` example keeps the old snapshot, while “source lookup evaluates when reached” must see the write.

Recursive delegation hits the relocation half:

```dewy
walk = (node:Node) => lazy {
    node.value
    loop i in [0..node.kids.length) { walk(@node.kids[i])... }
}
let g = walk(tree)
let _ = g.next       # suspended in the child; the child holds @node.kids[i]
let h = g            # inline move of the parent frame
let _ = h.next
```

The child cannot outlive the parent, so a lifetime check accepts the loan. The loan is an address in the parent frame. Moving `g` to `h` relocates that frame and the child’s next pull reads the old address. Round 2 requires stability across relocation and also offers inline frames; it does not say which obligation loses.

A third resume hole is re-entry. The exclusive-place rule says a nested `next` “must fail” and does not say whether that failure is terminal, whether the outer advance is finished, or whether `defer` runs.

```dewy
let box = [g: lazy (0)]
let read = ($capture @box) => box.g.next
let g = lazy { 1; read(); 2 }
box.g = g
let _ = g.next
let _ = g.next       # runs read(), which calls next on g while g is running
```

## 5. Unsound — cleanup skipped, doubled, or sequenced after the consumer has continued

**Unlabeled `break` runs the success tail.** `break` targets the nearest loop. `break $done` leaves the generator. After the loop, round 2 runs the rest of the body before end cleanup.

```dewy
reply = (app request journal) => lazy {
    let n = 0
    let complete = false
    defer journal.publish(n complete)
    loop token in app.tokens(request) or_throw {
        n += 1
        token
        if n =? request.limit { break }
    }
    complete = true
}
```

A producer that stops at `limit` with `break` still assigns `complete = true` and publishes a finished journal. `break $done` publishes a partial one. The preview in [01-reply-r3.dewy](programs-r1/01-reply-r3.dewy) avoids this only because the `break` is in the consumer, not in the producer.

**Borrowed break runs later consumer work before `defer`.** An owning break disposes before the next statement. A borrowed break only drops the loan. Disposal waits for the owner’s block (D40 Q2).

```dewy
preview = (app request journal screen) => {
    let stream = reply(app request journal)
    loop token in @stream or_throw {
        screen.append(token) or_throw
        break
    }
    screen.finish_preview()     # journal still unpublished
}                                # publish runs here
```

`finish_preview` observes the slot without the token just handed off. The round 3 owning loop hides this; `@stream` is legal and silent.

**A cursor that is never pulled never registers `defer`.** Registration happens when execution reaches the statement. `take(source, 0)` does not touch its right-hand source (left ends first).

```dewy
let g = reply(app request journal)
let _ = [loop x in take(g 0) x]
```

Limit 0 constructs `reply`, drops it fresh, and publishes nothing. Pulling an upstream that is already empty reserves, sets `complete`, and publishes a finished zero. Both are “no tokens.” Round 2 notes the factory must reserve if a never-started request counts; the language still treats the two zeros differently, and [01-reply-r3.dewy](programs-r1/01-reply-r3.dewy) reserves inside the body.

**An unmatched `and` partner has no failure receiver.** Right ending releases the extra left item by ordinary drop.

```dewy
loop row in open_rows() and label in labels { show(row label) }
```

`labels` ends after `open_rows` has already produced a `row` whose close can fail. That drop is not the source `or_throw`, not a marked block, and not the generator’s finished-cursor path. Round 3 says to reject an unmarked fallible duty or to keep the failure. This release is neither. The close failure is discarded, or it escapes through a path the rules do not name. On a terminal failure of `row`’s producer the same gap appears: child cleanup has already run, and “dispose the active child” on the way out disposes that cursor again unless “finished” is defined to make the second drop a no-op. The text says both “dispose the active child” and “a finished cursor does not repeat cleanup” without saying the child’s end sets finished before the parent unwind.

## 6. Surprising — ordinary `or_throw` on flat `next` forwards EOF

`none` is an `exception`, so postfix `or_throw` forwards it. Round 3 uses that same `none` as the end marker of flat `next`.

```dewy
let token = tokens.next or_throw
if token is? none { return BadPortSyntax[end_offset] }
```

Legal EOF never reaches the test. The function leaves with `none`, not with `BadPortSyntax` at `end_offset`. The separator arm in [05-port-rules-r3.dewy](programs-r1/05-port-rules-r3.dewy) has the same postfix: a well-formed final interval fails instead of committing. `or_throw<BadPortSyntax>` is the one spelling that keeps EOF, and it is a different operator from `loop item in tokens or_throw`, which forwards only the terminal outcome and binds a delivered `none`. One suffix, two discriminators. The source loop already has the three-way split; flat `next` re-encodes end as a value the existing postfix cannot see.

Option A has a second footgun the parentheses don’t show. `lazy (1 (2 3) 4)` is four integers, and

```dewy
eager = () => (1 printl("work") 2)
let g = lazy { eager() }
let _ = g.next
```

prints `work` and retains `2` before the caller has decided to ask for it. Dropping `g` discards `2` but cannot un-print. A group that was supposed to be one step is not.

## 7. Minor — the spelled cursor type is too small for a local check

`generator<T length=N failure=E>` does not carry remaining length (§3), which phase can fail, whether flat `next` is legal, or whether a capture is sendable or blocking. Round 2 says erasure widens conservatively and that a generic library must not see every consumer. It also says ordered prefixes survive “a known factory summary,” and that sendability is checked through stored generators.

A use site then either trusts the short type (findings 2 and 3) or opens the producer body, then every delegated body, to rebuild those facts. That walk is whole-program as soon as `map` stores an opaque upstream. The O(N+E+P) bound is real only for facts already on the contract. Flat-next legality “including every cleanup combination” is the same fork: D42 makes `A & B` usable as an `A`, so a precise overlap test builds the combination closure (exponential in duties); the linear test is the conservative one the spec already allows, and it should be the one that ships. Fusion that clones a resume function per chain shape misses the same target the lowering section is trying to protect.

## What is already closed

Owning `loop x in g` versus `loop x in @g` is a local syntactic split; a later use is a move error, not a silent borrow. Place outputs (`@x` yielded from the frame) are rejected. A finished socket must not close on a second drop, and round 3’s owning helper does put fallible close on the function that returns. `defer` is specified to read the live counter, not a snapshot from the registration line. Empty children continue on the same pull. Those are coherent if the findings above are fixed.

## Fix sketch

Keep one internal step result, `(item T) | end | failed F`, and do not implement the loop by calling flat `next`. Make `child...` and `loop x in child` the same forwarding rule, including `Canceled`. Put **remaining** length in the type that crosses a call, or drop `length=` from the type and keep it as a flow fact that dies at any escape. Decide source capture at construction for names, and reject a child loan into a frame that is allowed to move. Give the unmatched `and` item the same checked drop as an owning break. Keep bare `or_throw` from meaning EOF.
