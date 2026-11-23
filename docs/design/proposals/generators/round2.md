# Generators and multi-values, round 2

**Recommend one value per advance (A), one owner per cursor, and `lazy loop` for a deferred loop.** With `lazy (1 (2 3) 4)`, a consumer can stop after 2 without asking for 3. With `lazy (1 [2 3] 4)`, the middle item is one array. This uses the distinction Dewy already makes between expressing two values and constructing one value with two fields. An ordinary function that computes both fields before returning still runs to completion. Abandoning either kind of traversal must release its live resources at a predictable program point.

The 13 paired programs favor A in three cases and B in two, with eight ties. The two B wins identify a specific feature worth keeping on the table: a fixed positional row can pass through several functions without changing representation at the source level. The full B alternative is in Q1. The examples were traced on paper. Neither execution time nor compile speed was measured. [Paired programs and grades](dogfood-r1.md)

## 1. What can flow into a consumer

| Source | What a use receives | Example |
|---|---|---|
| A fixed eager pack | Its positional values, already evaluated if bound | `let p = (20 22)` then `add(p)` gives 42 |
| An array, tuple or record | One ordinary value | `let t:[int64 string] = [7 "red"]`; `paint(t...)` fills two positional parameters |
| A generator | One owner of suspended computation | `let g = lazy (20 22)`; `add(g...)` moves and drains a fresh cursor whose two integer outputs are proven |
| A stream of unknown length | As many single items as the consumer requests | `lazy loop n in ns { if n >? 0 n }`; `[g...]` eagerly collects all items of an infallible g |

A binding holds a **fixed count**. A fixed heterogeneous group such as `let p = (7 "red")` retains its positional types. An eligible use of `p` expands it exactly as the written values would expand. A call sees the expanded positions before static overload selection. Operands, conditions, indexes and named arguments require one value. `p[0]` and `p + 1` fail for the pair; `let (id color) = p` unpacks it. Parenthesized multi-result types remain confined to their existing whole-binding and result positions. Fixed homogeneous function results, including through a handle, keep their existing contracts. For example, `pair = ():>(int64 int64) => (20 22)` and `let f = @pair` permit `add(f())`. A heterogeneous fixed function result can use an ordinary tuple type `:>[int64 string]`. Generators need no change to existing homogeneous eager multi-result function inference or annotations. [Multi-expression decisions](../../../../docs/design/multi_expressions.md:147)

An eager flow expression may contribute a runtime-dependent count **to a sink that accepts it**. `let p = if c (1 2) else (3 4 5)` and `let p = (loop i in [0..n) i)` remain errors. Neither `let` nor a fixed call silently constructs a runtime-sized pack. Storing arbitrary loop output pending a later use would, in general, require a growable buffer, initialized-prefix cleanup and allocation even though the code looks like simple grouping. The eager array `[loop i in [0..n) i]` makes that materialization explicit. An existing eager function with varying output can still feed its supported collector or checked unpacking. In a lazy output position it can feed the generator sink, but its call completes **before** incremental delivery begins. Such an eager callee can already need proportional storage.

For varying data layouts, bind a **single explicit union value** and match its variants, or collect an array and use existing sequence patterns. Example: `let a = [if wide (1 2 3) else (4 5)]`, then `match a { (x:int y:int) => x+y (x:int y:int z:int) => x+y+z } else 0`. The fallback covers an array whose type admits other lengths. Existing `match (x y) { (a:int b:string) => … }` handles a fixed pack. An event type such as `Pointer | Button | Quit` preserves which event occurred even when two variants happen to have equally many integer fields. No shape-union type for eager packs or arity-dependent overload dispatch is proposed. [Sequence pattern rules](../../../../docs/design/match.md:18)

Positional arguments and array collectors take the values a pack expresses. Arrays and generators need postfix `...` to supply their contents. Record, map and set entries retain their own requirements. Eager `[loop i in ns { i i^2 }]` collects both numbers for each input. Prefix `...rest:T` collects leftover positional arguments into a homogeneous array, with subsequent parameters keyword-only. In unpacking, `(head ...rest) = p` retains the remaining pack values. A bare parameter-list `...` begins the keyword-only portion. There is no general prefix-collection expression. Write `[g...]` to collect; `...g` would have no destination. [Calls and rest](../../../../docs/LANGUAGE.md:329)

## 2. Construction, scope and the next value

**Syntax.** Propose reserving **new** `lazy` as an expression introducer. It takes one body expression using the ordinary control-body grammar. A delimited body ends at its matching delimiter. An undelimited body extends over the following expression, including its ordinary operators, and stops at its enclosing argument, body or delimiter boundary. Thus `lazy price(x) * count` defers the product, `(lazy price(x))...` spreads the constructed cursor, and `lazy { child()... }` delegates inside it. `lazy ( … )`, `lazy { … }` and `lazy loop x in xs body` all follow this rule. `lazy x in xs body` is the sketch's additional shorthand; omit it. Existing `loop` carries its full header and fallback grammar. Indentation and blank lines do not group outputs. The expression following a loop or conditional header is its body. Use a block when it contains several expressions. Region-specific array separator rules still apply only where the language defines them.

Every `lazy` creates an implicit scope. `let g = lazy (let k = 3 k)` makes a generator; k belongs to its body. Inside that scope `()` permits bindings to flow into the containing block and `{}` introduces its normal inner scope. In `lazy { printl("open") 1 }`, constructing g does not print or enter the body. Capture costs are incurred at construction. A body initializer, source lookup or loop bound evaluates only when reached. In `let r = make_range()` followed by `lazy loop i in r i`, the call ran before construction. In `lazy loop i in make_range() i` it runs at first demand, once for that loop entry.

**Advance synchronously until one value, end or terminal failure.** In a streaming output position, visit ordinary groups, blocks, selected arms and loop bodies in source order, descending through nesting. A nonempty fixed pack already in hand publishes its fields in order across successive advances. A `void` result, assignment, declaration or discarded result publishes nothing; continue on the same advance. A diverging path can spend arbitrarily long looking for its next output. Each handoff transfers one owned value and suspends immediately. Evaluate operands, arguments, binding initializers, eager collectors and ordinary callees under their original eager rules. These are evaluation boundaries even inside a lazy body.

| Expression in the streaming body | Demand trace under A |
|---|---|
| `(1 printl("work") 2)` | First advance gives 1. Second prints work and gives 2. Disposal after 1 skips the print |
| `eager_fn()` for `eager_fn = () => (1 printl("work") 2)` | First advance executes the whole call including its print and callee cleanup, then gives 1. Second gives the pending 2. Disposal after 1 drops the pending value |
| `lazy_fn()...` for `lazy_fn = () => lazy (1 printl("work") 2)` | The child is constructed when reached. First advance gives 1. The following advance enters the child again, prints work and gives 2 |
| `lazy_fn()` without spread | Gives the child generator owner as **one** item. Ownership transfers to the consumer |
| `[left() right()]` | Evaluates both calls to construct one array before publishing it. A consumer can accept that array atomically |
| `[3 4]...` in a streaming body | Evaluates the array once and publishes 3 and 4 on separate advances |

A bare postfix spread in a lazy output position is a **new placement** for the existing postfix operator, in addition to its new generator operand. It binds at ordinary postfix precedence. It can forward supported container elements one by one, or delegate to a child generator until it ends. `lazy { first()... second()... }` evaluates the second factory only after the first reports end. An empty child continues in the parent on the **same** request. A child failure unwinds the parent before it reaches later entries. In ordinary code the equivalent forwarding loop is `loop x in source x`; for a fallible source whose failure must propagate, write `loop x in source or_throw x`. The positional and record-literal meanings of spread retain their existing context.

A cursor has a fresh, suspended or finished state and can be running only under an exclusive advance. Finishing includes the tail after the last value and all completion duties. In `lazy { 1 printl("complete") }`, the print requires an advance after 1. Destroying that suspended owner skips the print and runs outstanding cleanup. Clean end or forwarded failure sets the cursor to finished; later advances report end without repeating a failure or cleanup. An explicit generator-local final result such as `g.result` is unnecessary. An unlimited `lazy { let n:int = 0 loop true { n n += 1 } }` keeps its current exact integer, whose storage may grow, and never needs a list of earlier values. Existing stored ranges remain reusable values with independent loop cursors.

**Control.** A bare `$name` prefixes its construct. Using `$done` before `lazy` applies this existing feature to the lazy body. `break $done` exits it normally, including cleanup. An unlabeled `break` or `continue` still targets the nearest loop inside the body. `continue $done` needs a loop target and is an error for a generator label. Active labels retain their lexical uniqueness. Jumps cannot enter or leave another lazy activation, including through delegation. A direct `return` or `?? return` in a lazy body is an error: the constructing function may have returned. An ordinary function nested inside the body may return from its own call. The labeled `take` example below exercises a stop without pulling an extra item. [Labels](../../../../docs/LANGUAGE.md:5211) · [Metatag placement](../../../../docs/LANGUAGE.md:5794)

## 3. Element type, length, calls and iteration

The proposed type is `generator<T>`, optionally refined by `length=N` and an ordinary terminal-failure bound `failure=E`. T is **one ordinary value type**, possibly a union, fixed positional array, owning record or another generator. Infer T from reached output sites and delegated element types using ordinary covering types. A pack contributes the types of its individual positions. For `lazy (42 "hi" true)`, each loop item has the covering singleton-element union. `lazy { [1 2] [3 4]... }` needs a consumer admitting an array value and integer values. A narrower declared T must accept every possible item. `loop x in lazy (1 (2 3) 4)` gives one integer each turn. A scalar callback handles all four. A consumer of a union needs applicable operations or an exhaustive match. A generator with no possible output admits element type `never`.

`length=N` proposes an optional nonnegative proof about **the original successful traversal**. Under A it counts items. A precondition `n >=? 0` with a representable bound gives `lazy loop i in [0..n) i^2` exactly n normal outputs; for an unrestricted signed n the count is max(0,n). A filter usually loses exact count. Inferring a length never evaluates a side-effecting bound early. A fixed-length annotation is neither an indexing interface nor a promise that a producer will finish in bounded time. `g.next` changes the remaining count; an unknown call taking `@g` invalidates position facts. No runtime length counter is required. A proof for the initial cursor cannot justify a fixed spread after a partial traversal.

**Fixed calls check the whole remaining sequence.** For `add(g...)`, require a finite traversal bound and proof of exactly two remaining integers on normal exhaustion. For a typed mixed signature, each positional type must fit, too. A literal sequence can keep temporarily ordered type facts even though its general iterator element type is a union. Retain these facts through a known value or factory summary; a widened `generator<int|string length=2>` alone cannot prove integer first and string second. An unsupported or unknown proof is a compile error at the spread. Existing materialized array spreads keep their own proof or opt-in checked-length rule. No speculative third item is consumed to *validate* an unknown length. Even with exact arity proven, a valid drain **must resume to normal end**, including tail effects and cleanup, before calling the function.

For example `f(before() g... after())` evaluates the callee, `before()`, the whole traversal including its terminal work, then `after()`, then omitted defaults; the callee body starts last. If handling a terminal failure aborts argument evaluation, release initialized argument temporaries, skip `after()` and skip the call. Preserve static overload selection, including the existing diagnostics for positional arguments shifted by an expanded fixed pack. In v1, direct generator-to-call spread uses statically known finite width even for a rest call. To fill a rest parameter from an unknown count, explicitly materialize an array, then use the ordinary array spread. This gives a visible storage boundary. A full eager drain of an infinite stream need never return.

**Expose one manual protocol for all T.** Propose `g.next` on a mutable generator place, returning one successful `array<T length=1>`, bare `none` at end, or a terminal exception outside the success wrapper. A singleton fixed array is an existing inline value. `lazy none` gives a success containing none on the first advance and bare none on the next. An emitted exception similarly remains a successful item. The loop consumes the discriminator and binds **T**, without exposing or allocating a wrapper per iteration. Other provisional iterators that return an item or none retain their existing behavior. Manual consumers can explicitly forward the relevant failures and preserve EOF: `let step = g.next or_throw<error | Canceled>`, then `if step is? none { break }`, then `let [item] = step`. The selector must include the actual terminal types it intends to forward. Q4 addresses the extra unwrap.

**Two input generators in an `and` header** extend the supported source combinations. Evaluate sources once, left-to-right. On each turn advance left, then right; evaluate the body only if both supplied an item. If right ends or fails, release any unmatched left item, retaining the left cursor's consumed position and prior effects. If left ends, do not touch right on that turn. For `loop a in @left and b in @right use(a b)` with left 1,2 and right 9, the first turn calls `use(1 9)`; the next may consume 2 before observing right's end. A body break after the first turn runs neither probe. Fallback runs when no body turn entered on normal end; forwarding a terminal failure exits before fallback. A `zip` helper remains ordinary application code. Use fixed typed tuples or named records to represent one pair. Existing range/array headers keep their ordinary behavior. Combining generator sources in an `or` header is outside the v1 extension; existing source support for `or` is unaffected.

## 4. Ownership, borrowing and transfer

Give **every** generator one owner and an exclusive cursor. Moving a generator transfers the current continuation, pending eager results, active child and all cleanup. `let other = g` is valid at a proven last use, otherwise it attempts a disallowed copy. A by-value parameter, a plain generator loop, a spread and a delegating parent use ordinary ownership transfer. `loop x in make() …` owns the temporary. `loop x in g …` can move g at last use. A second use of that same binding diagnoses the attempted copy and suggests borrowing or calling the factory again. The existing rule that an ordinary copyable iterator is stepped by value still stands. A fresh call of a generator factory starts new work, with new captures.

`loop x in @g …` borrows and mutates the named cursor. Breaking this loop leaves the cursor at its next item. Use `[loop x in @g x]` to drain a retained infallible cursor in place. A move after a borrowed break transfers that suffix. Exhausted borrowed cursors remain valid and report end. Reentrant or concurrent resume, replacement, or destruction while an advance is in progress must fail the exclusive-place check. In a borrowed source loop the consumer cannot advance the same generator again under the outstanding exclusive iteration loan in v1. Resume after leaving the loop or use the manual protocol when the consumer controls individual advances.

Copy-at-position would allow two independent private cursors over a pure range, but effects after the fork could run twice. A socket handle or a pending journal duty cannot be duplicated. Conditional copyability would need a stable contract covering all suspended states and erased callers. None of the 13 programs needs to fork a cursor. Application alternatives are a factory, buffering an explicitly replayable input, or forking the application-specific source when it supports that operation. The generic cursor has no `.copy()` operation in v1.

Snapshot free locals at construction as for closures, copying or moving as ownership permits. Implicit capture is read-only. In `let n = 1`, `let g = lazy n`, `n = 2`, the generator still produces 1. For private writable state use `lazy { let current = start … }`. For intentional sharing, a captured callable may already have an explicit `$capture @n` binding, e.g. `let read = ($capture @n) => n` and `let g = lazy read()`. A shared local can outlive its creator only under the existing closure rules. No new capture-list spelling is needed on `lazy`. Read a captured mutable parameter as a snapshot of its value when legal. A retained loan of that parameter, an iterated element, a scoped arena or a method receiver cannot escape its lifetime. Invalidate facts about shared places across consumer code; a condition proved before handoff may need proving again on resume. Failed construction releases exactly the initialized capture prefix. [Capture rules](../../../../docs/LANGUAGE.md:625)

Publish owned values only. `loop x in @values` traverses the live source binding; `loop @x in values` lends the element to the loop body. The double-place form `loop @x in @values` is rejected. `lazy { loop @x in values { @x } }` is also rejected: the next resume or disposal can invalidate the element address. Use `loop @x in values { x += 1 }` for immediate mutation, or `lazy loop x in values x+1` for owned results. A future lending protocol would need a checked turn-scoped result, exclusion of conflicting advances, and prevention of storage, collection and task escape. This round needs no such protocol.

A generator may move between tasks only if every possible stored capture, pending value, live local, child and cleanup duty is sendable under Dewy's task rules. A cursor can outlive its creator with owned captures. A cursor retaining a task-affine resource, an explicit nonsendable capture or a request-local cancellation value cannot cross tasks, even inside a record. A guard cannot span a handoff to arbitrary consumer code that could acquire the same lock. Prefer `let n = { let held = @(m.lock()) held.count }` followed by an output `n` after the guard releases. Internal references crossing suspension require stable bases and proved lifetimes across relocation and destruction; reject an unproved borrow. No background task starts merely by constructing or advancing a generator.

## 5. Failures, cancellation and disposal

The operational outcomes are **item**, **end**, or **terminal failure**. A terminal failure occurs once, even when an in-place consumer keeps the finished cursor. A direct `or_throw` in a lazy body forwards to the advance executing that body. Thus `lazy { to_int(s) }` can emit an ordinary error as data, while `lazy { to_int(s) or_throw }` fails its advance on invalid input. Items accepted earlier stay accepted. Delegating a failed child terminates the parent with that failure and any further cleanup failure. A consuming loop over a source with possible ordinary terminal failure requires `loop x in source or_throw …` or explicit manual step handling. The producer's creator is not on this return path.

An eager infallible drain permits `[g...]`. For v1, require a visible consuming loop or manual handling where eager draining can report an ordinary failure or cancellation. For example, `let xs = [loop x in g or_throw x]` forwards failure before publishing the completed array. Then `f(xs...)` uses the existing materialized-array rules. This avoids adding round 1's special `g... or_throw` interpretation for eager argument spreads. A streaming delegation `child...` adopts the child's terminal contract, like `loop x in child or_throw x`. A stream containing error *payloads* can itself be infallible. If a partly constructed array or call loses its input to a failure, release the initialized prefix; effects already performed retain their ordinary meaning.

Track separate summaries for constructing, advancing and destroying. The factory pays for capturing, any frame storage it acquires and any eager work it writes before `lazy`. Each advance pays for the body, invoked callbacks, child advances, frame growth, any observed waits and completion work it actually performs. The destroying scope pays for unfinished-frame cleanup and implicit hooks. Suspension to return an item is synchronous; it alone does not introduce `blocks`. A caller excluding `blocks`, `allocates` or `panics` must meet the exclusion for each operation it performs, including implicit destruction on every exit. Erasure preserves contracts or conservatively widens them. `generator<string failure=ReadFailed>` bounds ordinary terminal failures including disposal; omitted `failure` in a written type means no ordinary terminal failure. An inferred value keeps more precise phase summaries. A written upper bound without precise phase information must be assumed possible at either terminal boundary. An eager failure opening a file **before** constructing the generator belongs separately to the factory's result. Example helpers and error names in this document are application-specific.

Use the callable rule for captured time policy and execution-time core/resource caps. Existing reservations retain their original accounting; an advance or cleanup that acquires more storage uses the applicable limits there. Check effects, cap use, sendability and strict-cost obligations even through stored generators and callbacks. A `no blocks` function may hold a cursor with a blocking advance only when each operation it performs, including its possible drop, meets the function's contract. [Effect summaries](../../../../docs/design/effects.md) · [Settings on captured functions](../../../../docs/LANGUAGE.md:5838)

Under the **open D44 proposal**, a delegated wait participates in the advancing task's cancellation context. Pure handoff inserts no invisible poll. A producer that can compute indefinitely between waits can explicitly use `check_cancel() or_throw` at an appropriate work boundary. A plain source loop that receives its task's pure cancellation ends quietly if D44 Q5 is taken; `loop x in source or_throw …` forwards it. In particular, a producer recording successful EOF must use the forwarding form on its upstream, or a canceled input could run its successful tail. Distinguish cancellation from EOF at the manual step boundary even if one loop policy treats both as a stop. A delegated cancellation closes both active cursors in order. A cancellation plus failed cleanup retains the cleanup failure; quiet handling of cancellation cannot erase another part. Existing batch 10 gives ordinary `??` and `or_throw` their usual failure rules. D44 further constrains which work may hold a cancellation value, protected cleanup, and losers' failed undos. Generator transfer cannot smuggle a work-local value through a capture or payload. [D44 Q2 and Q5](../../../../docs/design/open_decisions.md:82) · [Batch 10](../../../../docs/design/decisions.md:736)

**Cleanup belongs to the active owner.** Propose observable cleanup at owning-block exit as in D40 Q2. Suspension retains the scopes and their registered duties. On normal scope exit, abandonment, consumer error or producer failure, unwind active inner scopes before outer scopes. Dispose an active delegated child before continuing parent unwind. Within a scope run registered defers in reverse registration order, then live locals in reverse ownership order using each owner's normal hook and field rules. Include an eager helper's unhanded values in pending ownership. Record discharge before invoking each action; move and partial construction must preserve a single duty. On a cleanup failure keep unwinding other live owners. A consumer's `continue` closes its current iteration scope and resumes the same traversal. A jump that actually exits an owning traversal drops it. Ordinary compiler-supported unwinding applies; crash durability is a separate storage requirement.

| How an owner stops | Observable duty |
|---|---|
| Dropped fresh | Release captures acquired at construction. No body-local registration or acquisition has occurred |
| Drained through end | Run the tail, then active cleanup, before reporting end. A failed close reports terminal failure instead |
| Owned traversal abandoned at `break` or consumer return | Skip unexecuted producer code, release active child/resources, and run registered defers before control passes out of the owning scope |
| Borrowed `@g` traversal breaks | Release the traversal loan. The owner can resume. A later owning exit triggers disposal even if it never resumes |
| Read fails after k items | Already-delivered items remain handed off. Release resources and report the read failure together with any cleanup failure |
| Cancellation while waiting | Use the task's cleanup policy and applicable grace; no normal EOF tail. Write a plain progress count for cleanup, never stash the cancellation token in a journal |
| Consumer fails while holding a suspended owner | Consumer unwind disposes the cursor. Its failure and a failed disposal both reach the caller under D40/D42 |

Keep a **checked, infallible one-off `defer` inside `lazy`** provisionally under D40 Q5. It registers when execution reaches the statement. Its action can read current producer-private locals on disposal. It may neither suspend to publish another item nor jump, panic or forward an error. Check its effects against the cleanup context. In a token stream, stage the next token in a reserved slot, increment a bounded delivered count, and hand off the owned token with no further fallible operation or cancellation point. When the consumer stops after two tokens, publish exactly those two as partial. The complete flag is set only after observing upstream EOF. A factory-level defer runs too soon. A line after the producer loop misses disposal at suspension. A generic finish adapter can count the items it sees but needs explicit access to private staging state and an owner that runs on abandonment. A reusable ticket's `$__drop__` can enforce the same guarantee and is preferable when reservation itself always incurs the duty. Q5 and the programs below show both forms.

An abandoned log reader can use its existing infallible owner release. A socket whose close can fail is a stronger case. **Recommend checked disposal with visible local exit under D40 Q1/Q6 and failure composition under D42.** A failing advance reports terminal failure at its consumption site. Disposal on consumer abandonment can fail in the **consumer's** function even if the producer has no further demand. Give such an owner a named, marked block when control would continue locally; a bare owning loop with an unmarked possible fallible drop gets the block fix. A suffix on the source acknowledges advance failures; it does not mark a separate consumer-owned scope. On a failed read, close during that advance and report both failures there; a later drop of the finished cursor cannot close again. If the consumer fails after a successful item, close on consumer unwind and combine the two failures there. Distinct failures combine as `BodyFailed & CloseFailed`; repeated failures of one kind follow D42's stack choice. Preserve `$__abandon__` where a resource already has an undo role. Neither an infallible user hook nor an infallible defer can stand in for a fallible close. Until the checked disposal path exists, reject suspensions carrying that duty rather than claiming successful release. Q6 gives the enclosing function and the alternative if D40 takes another route. [D40](../../../../docs/design/open_decisions.md:490) · [D42](../../../../docs/design/proposals/errors/combined/round8.md)

## 6. Evidence from the paired programs

Scores rate obviousness, discoverability, concision, safety and completeness. They are design judgments, not timing data. The original B programs for 09 and 12 exercised round 1's variable-arity binding. Their fixed alternatives are the applicable B programs under round 2's binding rule. Thus A won 3, B won 2 and 8 tied **in the original comparison**; switching those two cases to fixed representations leaves A with 1, B with 2 and 10 ties. The recommendation rests on the general item contract and the cost of supporting B in every generic consumer, not on treating the original tally as a vote. [Dogfood method, traces and grades](dogfood-r1.md) · [Review A](review-r1-a.md) · [Review B](review-r1-b.md)

| Workload | Original result | What determined the result |
|---|---|---|
| 01 Reply preview | Tie | An owning break publishes the delivered prefix. A reused ticket can carry the duty. [Local action](programs-r1/01-reply-a.dewy:11) · [Ticket](programs-r1/01-reply-owner.dewy:5) |
| 02 Rotated access logs | Tie | A cutoff or preview limit closes the active reader and skips unopened shards. A read failure bypasses the empty fallback. [Log scan](programs-r1/02-access-log-a.dewy:9) |
| 03 Paginated catalog | Tie | One request for an item can cross empty pages; a consumer stopping partway through a page pays only for pages already fetched. [Catalog traversal](programs-r1/03-catalog-a.dewy:9) |
| 04 Asset tree | Tie | Recursive delegation retains the active path and skips later siblings on early stop. [Tree walk](programs-r1/04-asset-tree-a.dewy:9) |
| 05 Port-rule parser | Tie | The parser controls exactly when to ask for a token. A helper amortizes the manual success-wrapper unpack. [Parser](programs-r1/05-port-rules-a.dewy:34) |
| 06 Retry preview | Tie | A zero budget requests nothing; observing end of a four-item prefix never demands a fifth source item. [Bounded consumer](programs-r1/06-retry-preview-a.dewy:17) |
| 07 Meter map/filter/chain | B | A constructs a fixed tuple, spreads it into positional helpers, and collects a two-result calibration back into a tuple. B forwards the pair through those helpers directly. [A](programs-r1/07-meter-pipeline-a.dewy:9) · [B](programs-r1/07-meter-pipeline-b.dewy:9) |
| 08 Ledger zip | B | A uses a typed pair and two positional spreads. B supplies a grouped row to both report calls. Both reconcile equal-length snapshots only after preflight. [A](programs-r1/08-ledger-zip-a.dewy:13) · [B](programs-r1/08-ledger-zip-b.dewy:13) |
| 09 Game input | A | Named event variants survive overlapping field layouts. New event kinds need no arity discriminator. B with the same union ties A. [A](programs-r1/09-game-input-a.dewy:9) · [Original B](programs-r1/09-game-input-b.dewy:14) · [Fixed B](programs-r1/09-game-input-b-fixed.dewy:21) |
| 10 Monitor replay | Tie | Offline `none` is useful data; a paused chunk retains the owner until a later request can observe EOF. [Replay](programs-r1/10-monitor-replay-a.dewy:18) |
| 11 Inventory socket | Tie | A borrowed break leaves disposal to the marked owner block. A close failure prevents UI completion. The safety and completeness grades depend on checked disposal. [Socket owner](programs-r1/11-inventory-socket-a.dewy:20) |
| 12 Ragged channel export | A | A record carries the existing sample array, including width zero. Original B constructs an eager variable-width pack and a variadic wrapper collects it back into an array. Fixed B ties. [A](programs-r1/12-channel-export-a.dewy:9) · [Original B](programs-r1/12-channel-export-b.dewy:9) · [Fixed B](programs-r1/12-channel-export-b-fixed.dewy:15) |
| 13 Recorder flags | A | A streams both results of the eager decoder as independent samples. B must unpack the pair and write two output entries. Both pay for decoding the pair before the first handoff. [A](programs-r1/13-recorder-flags-a.dewy:17) · [B](programs-r1/13-recorder-flags-b.dewy:17) |

**The callback test.** Give a fresh `lazy (1 (2 3) 4)` separately to `map(source @double)` and `filter(source @is_even)`. The adapters call `f(x)` and `keep(x)` respectively, each with one integer parameter. Under A, map gives 2, 4, 6, 8 and filter gives 2, 4. Under B the second turn supplies two positional integers. Both adapters must be rejected at the callback use unless the programmer changes the input or handles that row explicitly. Under B a function requiring a pair has the symmetric problem on the two singleton turns. This example isolates typing from I/O and from runtime-varying eager bindings. A plain stored pack still expands in `add(p)` under either option. Review B's suggestion to remove that expansion would overturn an accepted substitution rule.

**What A costs for the meter row.** With `let row:[int64 int64] = [minute raw]`, `qualified(row...)` checks the existing binary predicate. `let corrected:[int64 int64] = [calibrate(row...)]` captures the eager two-result callback as one item. Either spread `corrected...` into a positional sink or unpack it once. A fixed typed tuple can use slots/registers and does not intrinsically need a heap allocation; copy and ownership costs still depend on its fields. B expresses that same handoff as a pack row and calls `qualified(row)`, `calibrate(row)` and `chart.add_point(row)`. A named record such as `Reading[minute raw]` is an alternative if the application controls its callbacks. It gives the fields names but requires projecting them for existing positional APIs. The advantage of B is real at those interfaces, rather than a measured allocation saving.

## 7. Lowering and compile speed

A concrete producer needs a local continuation graph with a resume point, captures, locals live across handoff, any pending fields from an eager result, an active delegated source and cleanup state. A request transfers a value before suspending. Destruction dispatches on the initialized state and shares the lexical unwind plan with producer failure. An unknown or recursive caller need never suspend its ordinary call stack. `lazy (1 2)` can fit in a tiny inline value. Recursive `walk(child)...` can require resumable storage proportional to active depth. On a deep tree, destruction must also have a bounded call-stack implementation.

| Consumer and producer | Required implementation path and cost |
|---|---|
| Known non-escaping numeric generator in its consuming loop | Fuse producer control directly into the consumer body. For `loop x in (lazy loop i in a i*2) use(x)`, the generated loop should need no cursor heap object, indirect resume or intermediate array. Preserve all observable stops, cleanup and arithmetic effects |
| Known, locally composed map/filter chain | Build a bounded local fusion plan over input, predicate, transform and consumer operations. A filter that rejects an item asks for another; an accepting consumer that breaks prevents every subsequent demand. A known eager two-result call still computes both before any handoff |
| Local or returned concrete cursor with known layout | Put state in an inline object, caller result slot or another proved-valid scope. Returning a cursor alone does not require a heap frame. Moving it preserves the cleanup duty |
| Heterogeneous storage, opaque call, captured indefinite lifetime, or recursion | Use an erased cursor with a state pointer and shared resume/dispose entries where needed. Heap storage is one legal implementation when inline, caller or bounded arena storage cannot work. Charge storage at actual acquisition, including a child first allocated on resume |
| Unproved lifetime or costly representation under strict policy | Reject the specific allocation, detach, costly copy, check, effect or borrow at its source. Show whether it is construction, resume or disposal. A planned but unperformed optimization cannot establish a strict contract |

**Avoid specializing on the whole adapter chain.** Key reusable adapter code on the needed input/output ABI and relevant effect/ownership contract. Store an upstream cursor and callback as environment data at an opaque boundary. Do not construct public types shaped like nested `Map<Filter<Chain<…>>>` or clone each downstream adapter for every upstream composition. Give a concrete producer one reusable resume/dispose implementation per necessary ordinary Dewy instance. A local consuming loop can inline known operations from small summaries. Bound cloning and memoize plans at joins; crossing an opaque call, recursion or the size budget uses the shared cursor convention. Keep one layout descriptor per required concrete frame. A generic published library must work without seeing all its consumers.

For example, the meter pipeline and a second pipeline sharing calibration can share the same adapter entry points even when the sources differ. A known local composition may instead compile to a single hand-written-style loop. At an opaque callback, inlining can stop while the adjacent known producer/consumer still fuse. Preserve callback arity, capture snapshots, the temporal placement of eager calls, child cleanup, matched and unmatched zip advances, resource caps and cancellation. Never replace an observable unmatched left advance with a length shortcut. [Iteration contract](../../../../docs/design/semantic_contracts.md:19)

**Analysis is demand-driven.** For an ordinary scalar call use the existing checker fast path. For one demanded lazy body with N IR entries, E CFG edges and P explicitly expressed fixed-pack positions, control construction and collection of local output/phase events take O(N+E+P) before the cost of existing type joins and ownership analyses. Keep a covering element type, simple exact-count/finite-bound facts, and an ordered type prefix only for consumers needing positional proof. Bound saved positions by the number actually demanded and the compiler's proof-work limit. Compose count facts by addition for sequences, known repetition for proven loop bounds, agreement at a branch, unknown for filters/early exits otherwise. Use overflow-safe size arithmetic, never unroll a million-step range to count it. Ownership/liveness uses existing sparse indexes and bounded worklists; bitset liveness costs a join per processed edge and iteration. Recursion widens to unknown unless a local contract suffices. An unsupported proof rejects the fixed-width/strict use, while ordinary iteration still works. A pipeline of L local adapter operations takes O(L) plan entries per inspected linear path, bounded duplication at branches, and no cross-program enumeration of chains. These are design bounds, not measured throughput.

Under `$no_hidden_costs`, account for construction, pending results, frame movement, resume/drop calls, recursive growth, eager materialization and any COW detach using the emitted plan. Opaque effects are conservative. Under `$explicit_allocation_failure`, report an allocation refusal at the phase that attempts it, releasing initialized state. `int` in an infinite generator can itself grow. Distinguish this cost from a frame that takes constant space.

## 8. Other design choices in context

| Direction | Lesson for this proposal |
|---|---|
| Python generators | Explicit yield and delegation make suspension visible. Delegation can forward close and a return value. Dewy's existing expression flow and one-way pull requirement allow `lazy` and `child...` to cover the cases tested here. Deterministic abandonment still needs an owner. [Delegation and finalization](https://peps.python.org/pep-0380/) |
| JavaScript generators | A done discriminator permits the full payload domain and supports bidirectional communication. Dewy needs the discriminator; these programs need no send/throw-into channel. [Generator objects](https://tc39.es/ecma262/multipage/control-abstraction-objects.html#sec-generator-objects) |
| C# iterators | Scoped enumerator disposal provides a useful precedent for resource lifetimes on early exit. Dewy can distinguish a fresh factory call, an owning loop and a borrowed cursor without an additional enumerable abstraction. [C# specification](https://ecma-international.org/publications-and-standards/standards/ecma-334/) |
| Rust iterators and proposed gen blocks | One typed item and fixed tuples fit the A programs well. Closures cover simple sources, and gen blocks offer explicit control for custom producers. Dewy's compile-speed target favors sharing adapter implementations across chain shapes. [Iterator](https://doc.rust-lang.org/std/iter/trait.Iterator.html) · [Gen-block proposal](https://rust-lang.github.io/rfcs/3513-gen-blocks.html) |
| Kotlin sequences | A sequence builder supplies lazy steps and delegation. Its documentation gives an example in which stopping early leaves a builder's finally block unexecuted. Dewy needs the stronger ownership rule for its token journal and socket. [Sequence builder](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.sequences/sequence.html) |
| Lua and stackful coroutines | Suspending deeply nested helpers and exchanging several values serve interactive workloads. Preserving arbitrary call stacks and foreign frames would undermine the proposed eager-function boundary. [Coroutine semantics](https://www.lua.org/manual/5.4/manual.html#2.6) |
| Haskell-style laziness | Pure, demand-driven values express infinite data naturally. General non-strict evaluation changes ordinary binding timing and resource retention in an effectful Dewy program. Keep deferral explicit. [Expression semantics](https://www.haskell.org/onlinereport/haskell2010/haskellch3.html) |
| Library iterator adapters | Existing iterator records suit steerable domain traversal. They remain a baseline for code generation; implementing the asset tree or failed socket by hand requires tracking resume, initialized fields and cleanup across every exit. |

## 9. Disposition of the sketch audit

Numbering corresponds to the original audit. The first nine are the must-settle findings. “Adopt” in this table means the recommendation made by this proposal. D40, D42 and D44 remain subject to the designer's decisions. [Audit with decision and fixture references](audit-r1.md)

| Finding | Disposition in round 2 |
|---:|---|
| 1 | Keep `let` packs fixed-count. Correct the sketch's variable `values` and eager mixed-loop `xs` using an array, union or lazy loop (§1) |
| 2 | Statically expand eligible arguments and select one overload. A changing count cannot dispatch a fixed call; explicitly match ordinary values (§§1, 3) |
| 3 | Fixed heterogeneous groups remain valid. Preserve the current homogeneous ordinary multi-result function restriction and handle contracts. Use fixed tuple values or a singleton-element union for mixed outputs (§§1, 3) |
| 4 | `add(g...)` requires finite, exact remaining width and positional type proof. Drain through the tail before the call. Unknown-count rests go via an explicit array (§3) |
| 5 | Adopt one value per advance, including emitted none and exception data inside an unambiguous success. Full B alternative in Q1 (§§2–3) |
| 6 | Adopt a move-only cursor. Plain loop/spread takes ownership; `@g` mutates its retained place. Fresh calls restart (§4) |
| 7 | Reject place outputs, including a place into the producer's own frame. Release internal loans at appropriate scopes (§4) |
| 8 | Preserve construction, advance and disposal effects through higher-order calls, erasure and implicit cleanup (§§5, 7) |
| 9 | Adopt visible checked disposal as an open D40/D42 dependency. Until implementable, reject an outstanding fallible duty at suspension. A terminal or disposal failure must have an owning receiver (§5, Q6) |
| 10 | Existing sequence patterns already match fixed packs and ordinary arrays; domain variants can be exhaustively matched. Drop the proposed eager variable-count scrutinee (§1) |
| 11 | Keep prefix rest contextual. For binary forwarding use `forward = (a:int b:int) => add(a b)`; a truly variadic wrapper should call a suitable rest function (§1) |
| 12 | Bare `inner()...` is new in a lazy output position; it delegates incrementally. A supported existing iterable can instead be forwarded with a loop (§2) |
| 13 | Designer clarified that labels already prefix constructs. Apply the existing feature to lazy; extend the reader's accepted target and keep activation-local jump validation (§2) |
| 14 | Correct the sketch's double-place header to `loop @x in values` for mutable elements or `loop x in @values` for a live source. Neither permits escaping a place (§4) |
| 15 | Two generator inputs in an `and` header extend the provisional iterator implementation. Specify ordered pulls and the unmatched item (§3) |
| 16 | Reserve the proposed `lazy` introducer with one body expression; retain `lazy loop` and omit the extra shorthand (§2, Q2) |
| 17 | Designer confirmed indentation is formatting. A following single body expression works on either line. Multiple siblings require a block (§2) |
| 18 | Eager array collectors collect every contribution; map/record/set entry rules do not generally flatten their contents. Mixed streams require compatible consumer types (§§1, 3) |
| 19 | Trace both helper kinds and the print between 1 and 2. A void print contributes no step; abandoning a cursor skips its unexecuted tail (§2) |
| 20 | Step count describes traversal, with the nonnegative-bound condition for squares and source evaluation at loop entry (§§2–3) |
| 21 | Use the advancing task, distinguish cancellation from EOF, and forward delegated failure. D44 quiet loops and explicit checkpoints are conditional on adoption (§5) |
| 22 | Register infallible defer when reached. Owning break unwinds; borrowed break preserves the cursor. Keep hook and fallible-disposal alternatives (§5, Q5–6) |
| 23 | Capture snapshots/ownership at construction, initialize body locals on demand, and invalidate shared facts on resume (§§2, 4) |
| 24 | Retain eager ordinary calls. Historical implicit generators, explicit yield and a separate final result are superseded by explicit lazy construction and terminal outcomes (§§2, 5) |
| 25 | Existing array separators retain their dimension rules; elsewhere `f();` discards the result, including inside lazy. Line layout does not create a step. No new n-D collector decision (§§1–2) |
| 26 | A stored range retains independent traversals. An infinite cursor may never finish a drain and exact integers can grow (§§2, 7) |
| 27 | Fusion preserves effect order, one observable advance per participating input, producer/consumer handoffs, failures and destruction (§§3, 7) |
| 28 | Capture callable time policy, apply execution caps, retain existing memory charges, and reject an outstanding lock across uncertified consumer work (§§4–5) |

## 10. What still needs proof or measurement before implementation

| Obligation | Evidence needed |
|---|---|
| Ownership and handoff | A local lowering proof for fresh, running, suspended and finished states. Check failed capture initialization, move-after-pause, pending eager result ownership, move-only payloads inside unions, delegation, and reentrancy. Each duty must have exactly one owner at every transition |
| Deterministic cleanup | Instrument reply, rotated log and socket traces for exhaustion, owning break, borrowed break then resume, failure before and after handoff, cancellation, drop before first demand, and repeated advances after failure. Verify inner-child order, zero double-closes and the exact journal prefix |
| Checked disposal | Resolve D40 Q2/Q6 and D42 combinations. Show that a close failure at a local exit prevents subsequent consumer code; that a simultaneous read/consumer failure survives; and that two same-kind closes remain observable. Include construction refusal, cancellation and nested delegation |
| Types, manual steps and source grammar | Prototype `lazy loop`, nested scopes/labels, A's transparent groups, fixed-pack forwarding, optional/error items, recursive annotated output, existing generic iterator coexistence and compile-time rejection of unproved arity. Exercise full and partially consumed known-length cursors, homogeneous/mixed positional proof and checked array spread |
| Fusion equivalence | Differentially trace fused, inline-frame and erased-frame versions against an unfused reference: scalar map/filter, eager pair, `take(0)`, `take(k)`, zip with a shorter right side, consumer failure at first output and a fallible tail. Include callbacks that mutate explicit shared state |
| Runtime cost | Compare generated code and allocations for a hand-written loop, local lazy loop, meter pipeline, opaque callback and recursive tree. Show no generator allocation/dispatch in the required fused scalar case. Measure forwarding of a fixed tuple versus two scalar slots before assigning it a speed penalty. Separate heap growth by recursion depth and exact-integer arithmetic |
| Compile budget | On the flagship panel report same-host single-worker instruction counts with no generators, representative generators, chain families of increasing depth/diversity and imported opaque producers. Count distinct adapter implementations, cloned IR, output code size and peak compiler storage. Confirm linear growth for the bounded straight chain and bounded work at joins. On the designated quiet host measure fresh lines/s against the 200k floor and 250k target. No estimate establishes these gates |
| Safety across resumption | Negative cases for leaking element places, retained guards, saved `Canceled`, moving a task-affine cursor, and strict callers acquiring hidden frame storage or blocking cleanup. Verify settings and cost diagnostics through erased types. Cold-read the proposed names separately |

## Open questions for the designer

### Q1 (a). What one advance delivers

~~~dewy
let g = lazy (1 (2 3) 4)
loop x in g printl([x])
~~~

Should the loop print four singleton arrays, or three arrays with `[2 3]` in the middle?

**Recommendation.** A, four singleton turns. Use one typed tuple or record for an atomic item. The recorder receives the decoder's samples directly, and a unary map or filter works on every integer in this example. B gives the meter pipeline and ledger report useful direct positional forwarding (§6). **Reversible before release.** Switching later changes callback contracts, demand, I/O order, zip pairing and the effect of a consumer break.

**The fully specified alternative B.** Keep §§1–5 on eager bindings, control, ownership, effects and disposal, with the following replacements for the generator output surface and checker.

1. Parse the immediate delimited body of lazy, a streaming loop body, and each selected streaming arm as a sequence of entries. Bare expression bodies have one entry. A control entry visits its body entries incrementally. A spread entry delegates one complete child step per advance, or streams each element of a container as a singleton. Newlines never determine boundaries. Thus `lazy (a b)` gives two singleton steps and `lazy loop x in xs { x x }` gives two per iteration.
2. Evaluate each ordinary entry eagerly and publish its entire nonempty fixed pack as one step. A nested value group or block in entry position, a binding holding that fixed pack, and an eager function returning it have the same step width. For `lazy ((a b))` there is one pair. For `lazy { if c ((a b)) else ((d e f)) }` one step has the selected width. With singly delimited arms each arm instead streams successive entries. A zero-width contribution produces no step, a nested generator is one item, and bare `child...` preserves child row boundaries. Publishing is atomic per row; a failed second field prevents handing off the first, while prior effects remain. A whole draining helper can still run for unbounded time before a handoff.
3. **New use of pack shape in a generator type under B only:** `generator<(int64 int64)>` means a two-field step; `generator<int64 | (int64 int64)>` admits a singleton or that pair. Keep alternatives as a finite set of whole fixed-width rows, preserving positional correlation; fields may themselves be ordinary unions or products. A finite branch choice may vary the width *between steps*. An ordinary grouped entry or eager helper with unbounded output width cannot become an implicit runtime-sized step. Collect an explicit array or use streaming iteration to produce its elements. There is no relaxation of the fixed eager binding or ordinary multi-result rules. In particular the original eager `let fields = …` in workloads 09 and 12 remains rejected.
4. A simple loop binder refers to this step's complete contribution. For a known fixed width, substitution fills that many positional arguments; `paint(row)` can call a binary function. With alternative widths, the binder is a **step-local view** usable directly as a `match` scrutinee, in an array collector accepting every field type (as in `[x]` above), or in a streaming re-expression preserving its possible shapes. A match can distinguish `v:int` from `(a:int b:int)`; in a narrowed arm each binding is an ordinary fixed value or pack. A use such as `let q = row` or a positional call must prove a single static arity under the current facts, and a scalar context must prove one. No runtime arity-based overload selection. A pair and a singleton tuple of two fields remain distinguishable in the manual result by the extra container level. For a mixed-width step view use the outer step arity first for pack patterns; a scalar typed arm matching a container can then use existing patterns on that one container. A catch-all covers remaining shapes. This protocol-specific view is an additional type-checker cost of B.
5. Manual `.next` returns one ordinary positional container holding the whole successful row, bare none at end, or terminal failure outside the row. A discriminated union of fixed containers covers mixed successful row shapes. A singleton none still returns a one-slot container. A consumer may store that container. A loop normally forwards the fields directly, without requiring a heap allocation. A generator loop fallback counts successful **steps**, and zip pulls one step per side with the same left-to-right unmatched-step rule. A combined contribution `((a b))` concatenates the fields from both input steps; nest explicit tuples when the two source identities matter.
6. Streaming `child...` forwards row boundaries through a chain. Eager `[g...]` and `f(g...)` concatenate their fields. `length=N` counts **initial steps**; a separate static fact proves total remaining flattened fields and types for a fixed positional call. For `lazy ((1 2) (3 4))`, the counts are two and four respectively. A filter keeps only complete rows. A map hands a whole row to its callback, and the callback's result forms a whole output row at its ordinary entry. Mixed arity requires explicit discrimination as in §6. These judgments follow the producer and do not change according to the caller.
7. A fixed row can travel in registers or result storage, saving resume dispatches; its slowest field delays the first handoff. For independent recorder samples the B producer must unpack the eager pair and publish two entries. Fusion must preserve these boundaries even when no cursor is materialized. A scalar facade over B can split a delivered row but cannot move the first handoff ahead of its last field's evaluation. A plus explicit tuple rows is the converse hybrid. No demand or code-generation measurements currently favor either.

### Q2 (c). Construction and type spellings

~~~dewy
squares = (n:int64):>generator<int64> => lazy loop i in [0..n) i
two = ():>generator<int64 length=2> => lazy (20 22)
~~~

Use reserved `lazy` on an ordinary expression and `generator<T>` for its type? Keep the existing `loop` word in the first line?

**Recommendation.** Yes. A single operand grammar covers all three shorthand sites in the corpus, including combined loops. `length` is the existing word with a proposed generator-specific unit, and `failure` is a proposed named type argument for terminal failures. The new language names are **`lazy`** and **`generator`**; **`failure`** and the new use of **`length`** also need spelling review. Audit collisions before reserving the keyword. **Reversible before release.** Renaming after adoption would change source and possibly collide with existing identifiers.

### Q3 (b). One owner or a copy at the suspension point

~~~dewy
rest = () => {
    let g = lazy (10 20 30)
    loop x in @g { printl(x) break }
    let h = g
    [h...]
}
~~~

Should moving g to h continue with 20 and 30, and a subsequent use of g make that transfer ill-typed?

**Recommendation.** Yes. A factory is the restart operation. Borrow g for a pause and use a proven last-use move for transfer. The alternative, copying eligible cursors at the same position, needs rules for replayed effects, live resources, callback environments and delegated state. No workload requests it. **Reversible before release; additive later** to introduce a separately checked explicit fork of eligible sources. Changing an existing move into an implicit copy would alter effect and cleanup behavior.

### Q4 (b). Manual steps that can carry none

~~~dewy
observe_offline = () => {
    let g = lazy none
    let step = g.next
    if step is? none { return false }
    let [item] = step
    return item is? none
}
~~~

Should a successful manual step carry a fixed one-element array, leaving bare none for end and ordinary failures outside the item?

**Recommendation.** Yes for the initial protocol. This function returns true, and the same code shape works for an element that is an exception. Loops bind the element directly. A dedicated tagged step type could improve manual-parser ergonomics, at the cost of more names and constructors. `next` is an existing spelling with a **new built-in generator result convention**. **Reversible before release.** Changing the public manual result later breaks generic parsers.

### Q5 (a). A one-off action inside a lazy body (D40 Q5)

~~~dewy
track = (slot source) => lazy {
    let delivered:int = 0
    defer slot.publish_count(delivered)
    loop x in source { delivered += 1 x }
}
~~~

Should this registered infallible action publish the current count on exhaustion or destruction of the owner, including when a consumer kept only a prefix?

**Recommendation.** Keep the checked form provisionally. With a pre-reserved slot and a proved counter bound it directly expresses a producer-private obligation at first demand. A reusable owner with `$__drop__` is equally capable and can enforce registration at construction. Removing defer should wait for an equivalent local owner/callback that preserves effects and borrows. Neither form makes fallible disk I/O infallible. **Reversible before release.** Destruction timing after release is observable under either spelling.

### Q6 (a). A fallible close can leave the consumer's function (D40 Q6, D42)

~~~dewy
preview = (service ui) => {
    {
        let rows = service.listing_rows()
        loop row in @rows or_throw {
            ui.add_item(row) or_throw
            break
        }
    } or_throw
    ui.finish()
}
~~~

If closing the suspended socket fails at the marked block boundary, should `preview` return that failure before `ui.finish()`? If `ui.add_item` or the socket read also failed, should the caller receive both?

**Recommendation.** Yes. The source suffix forwards advance failures. The block suffix acknowledges destruction on every exit of that owner. A pure cancellation cannot swallow a separate close failure. Require an explicit owning scope for locally continuing fallible disposal until D40 settles alternative visible exits. If checked implicit disposal is declined, require an explicit consuming finalization that reports failure plus statically verified coverage on abandonment, or exclude such suspended owners. An infallible drop-only implementation cannot support this program. **Reversible before implementation.** Choosing another policy after release could start running code applications had expected to skip.

### The whole design in programs

**Take exactly two requests from a possibly infinite source.** This infallible example highlights that a successful handoff suspends before its following label test. The advance for end must never touch a third input.

~~~dewy
take = (source count:int64) =>
    $taken
    lazy {
        if count <=? 0 { break $taken }
        let left = count
        loop item in source {
            left -= 1
            item
            if left =? 0 { break $taken }
        }
    }

first_two = (source) => [loop x in take(source 2) x]
~~~

**A reply journal with a partial consumer.** Here the application reserves bounded storage. Staging failure leaves the previously staged prefix intact. After successful staging, the bounded count increment and token transfer cannot fail or observe cancellation. Publication is a nonblocking, allocation-free, infallible update of an already-reserved record.

~~~dewy
reply = (app request journal) => lazy {
    let ticket = journal.reserve(request.id request.max_bytes) or_throw
    let delivered:int64 = 0
    let complete = false
    defer ticket.publish(delivered complete)
    loop token in app.tokens(request) or_throw {
        ticket.stage(delivered token) or_throw
        delivered += 1
        token
    }
    complete = true
}

preview_reply = (app request journal screen limit:int64) => {
    if limit <=? 0 { return }
    let shown:int64 = 0
    loop token in reply(app request journal) or_throw {
        screen.append(token) or_throw
        shown += 1
        if shown =? limit { break }
    }
    screen.finish_preview()
}
~~~

For a/b/c with limit two, the trace is reserve, stage a, hand off a, stage b, hand off b, release the upstream, publish a/b as partial, then finish the preview. Failure in the second stage records a only. Failure in the second append records a/b because b reached this consumer. Breaking immediately after the actual last token still records partial until the producer observes EOF. A consumer that merely releases its borrow of `@g` leaves the owner free to resume. A never-started cursor has no reserved slot in this version. Reserve in the factory and transfer an owning ticket if even a never-started request must be recorded. Durable publication needs the fallible boundary in Q6. [Reply traces](programs-r1/01-reply-a.dewy)

**The reusable owner for the same journal.** The slot, count and complete flag live together and travel with the duty. A staging helper accepts `@ticket`, stages and increments on success. Completing the producer sets `ticket.complete = true` only after upstream EOF.

~~~dewy
ReplyTicket:type = type of [slot:ReplySlot delivered:int64 complete:bool
    $__drop__ = ():>void => { slot.publish(delivered complete) }
]

reply_with_ticket = (app request journal) => lazy {
    let slot = journal.reserve(request.id request.max_bytes) or_throw
    let ticket = ReplyTicket[slot 0 false]
    loop token in app.tokens(request) or_throw {
        stage_next(@ticket token) or_throw
        token
    }
    ticket.complete = true
}
~~~

`ReplyTicket`, `stage_next` and the journal members are application names. They propose no library additions. Both designs retain the same obligation on read error, consumer failure, cancellation and early owning break. [Complete owner version](programs-r1/01-reply-owner.dewy)
