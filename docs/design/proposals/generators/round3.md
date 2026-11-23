# Generators and multi-values, round 3

This delta replaces round 2's mandatory singleton-array result for manual stepping, its ownership diagnostics, and its recommended way to write the socket preview. The six revised designer questions follow the regrade. Section references to the base proposal use [round 2](round2.md).

## 1. Pull one token directly. Use a source loop when the outcome matters.

A generator already has three distinct internal outcomes: deliver an item of type T, finish normally, or terminate with an exception in F. Keep that discriminator through iteration, delegation and cleanup. Expose **two existing Dewy operations** on those outcomes.

| Operation | Item | End | Terminal failure |
|---|---|---|---|
| `g.next`, when the three sets of values can be distinguished | Return the item itself | Return `none` | Return the terminal exception itself, once |
| `loop item in @g or_throw { … }` | Bind the exact item, including an exception or `none` delivered as data | Exit the loop normally | Forward the terminal failure from the enclosing execution; skip the EOF path |

**The flat result is available when it preserves all three meanings.** Test the declared or inferred element and terminal contracts, including terminal cleanup failures and applicable cancellation. The sets of values for T, {none} and F must be pairwise disjoint and distinguishable under the existing type system. Use the existing union, family and refinement facts; an unknown overlap gives the conservative answer. Check this once per demanded contract/instantiation, without inspecting stream contents or specializing on cursor position. In particular, neither an item nor a terminal failure can be bare `none` for the flat projection. A family overlap through a D42 combination cannot be erased. Widening the type can remove evidence that makes the flat projection legal. A source loop continues to work with that wider contract.

For the port lexer the sets are `PortNumber | Dash | Comma`, `none`, and `BadPortSyntax`. The following line advances once. A bad byte leaves the parser with its original offset. EOF stays available for the grammar to handle.

~~~dewy
let following = tokens.next or_throw<BadPortSyntax>
~~~

`or_throw<E>` and `??<E>` keep their ordinary value semantics. An unqualified `or_throw` also forwards EOF because `none` is an `exception` in Dewy. An unqualified `??` can consume a lexical error as well as EOF. When the grammar needs a number, `required_port` checks EOF explicitly and reports the end offset. After an interval the parser accepts EOF as successful completion. This distinction replaces round 1's `next_token` wrapper with application grammar. A disjoint exception *item* is legal in a flat result; ordinary `or_throw` applied to that returned value can deliberately forward the item. To forward only the **terminal outcome** irrespective of payload, use the source suffix in the table. [Port parser](programs-r1/05-port-rules-r3.dewy:34) · [Selective forwarding](../../../../docs/LANGUAGE.md:4380)

**One universal manual pull is already expressible.** Use a borrowed loop with a `break` or `return` on the first body entry. The loop's `else` runs if the body never entered. Explicit source forwarding prevents a canceled or failed request from falling into that EOF arm. There is one advance to obtain an item or observe end and no second probe after the break. A loop with `continue` can ask again, so it would not be a single pull.

~~~dewy
read_one = (@g) => {
    loop value in @g or_throw { return [item=value] }
    else { return [ended=true] }
}
~~~

This is an example of an *application* that actually wants a storable outcome. Both successful return arms construct ordinary records. A terminal exception leaves the call directly. Even if a producer emits the same error value it can later forward, callers can distinguish an ordinary record containing that error from the terminal exception. Testing the outer exception before destructuring the success is sufficient. The same construction keeps delivered `none`, clean end and terminal `none` distinct. A consumer branching on the outcome immediately need not construct either record. Generic code may always use the loop. A user-defined iterator already returning a flat `T | none` keeps its provisional interpretation. An old iterator which used none as its end marker has no way to retrospectively distinguish a delivered none. A generator constructed by `lazy` retains that distinction from the point of production. No existing user `next` method changes result type. [Existing iterator protocol](../../../../docs/LANGUAGE.md:5014) · [Loop fallback](../../../../docs/LANGUAGE.md:5188)

For example, `lazy (none 7)` cannot expose flat `.next`. A borrowed source loop delivers none on its first turn and 7 on its second. For `lazy { ParseFailed ParseFailed or_throw }`, the first request delivers an exception as data and the second reports a terminal failure. The same type appearing on both edges precludes the flat view. If `g.next` is unavailable, the diagnostic names the overlap, for example “none is both a possible item and the end marker”, and offers the one-turn loop with both arms. Editor completion should show this explanation at `next`, including in a generic where disjointness is unproved. On an available flat result, hover names the actual item, EOF and failure alternatives. A failed typed return caused by accidentally forwarding EOF should point at `or_throw` and suggest the appropriate selective forward. These are diagnostic requirements, not compiler behavior demonstrated by this round.

**Why these two forms.** A new EOF sentinel such as an end-of-input exception would itself be legal payload and would still collide with overlapping item/terminal error kinds. `Closed<T>` already describes channel closure and has the same collision problem. A universally tagged step or tuple solves representation but charged every parser production for projection in rounds 1–2. `match g.next` works on a disjoint flat result; matching after two identical values have been merged cannot recover provenance. Supplying a default changes which failures are consumed. Peek plus advance introduces a pending owned item, with extra rules for repeated peek, failure and abandonment. The two existing forms cover lookahead and nullable/error data without that state or a new name. The tradeoff is explicit: code requiring a *stored* arbitrary generic outcome supplies a tagged value, as `read_one` does. The compiler never silently changes `.next` from a raw value to a wrapper.

## 2. Make the owner visible at the loop

For a generator there is one source rule: **a value supplies the owner; a place supplies a loan**. A break exits the loop. The loop disposes the cursor it owns; a loop holding a loan releases that loan. The distinction is visible before reading the body and does not depend on whether the compiler finds a later use. A plain loop over a named generator must be a valid ownership transfer. Changing a later line cannot silently turn it into a borrow.

~~~dewy
consume_prefix = (source) => {
    loop x in source { printl(x) break }
}   # disposal occurred on break

print_one = (@source) => {
    loop x in @source { printl(x) break }
}   # the caller's cursor can resume after this call
~~~

A borrowed break establishes only that the loop has finished using the place. A containing function that **itself owns** the generator can return immediately afterward, which disposes that owner during return. Distinguish “loan released” from “kept alive until somebody reads again”. This matters for the socket preview and for cancellation. Ordinary copyable iterators retain the existing by-value copy behavior; the diagnostics below apply to the move-only generator contract.

| Source site | Proposed compiler/editor feedback |
|---|---|
| `loop x in g` or a factory call | At the source and on an early exit, show “loop owns this generator; leaving the loop disposes the remaining traversal”. Include actual cleanup/error effects when present. A deliberate owning break is idiomatic and warrants no general warning |
| `loop x in @g` | Show “advances g in place; break leaves g positioned after the last item”. At `return`, also show whether the enclosing function owns g or only borrows it. On a combined header, identify the owner/loan independently for each source |
| Use of g after an attempted owning loop | Compile error pointing to the transfer and the later use. For continuation offer `in @g`. For replay suggest a fresh factory call, since a borrow would start at the current position |
| A borrow ends and the cursor is never resumed | No blanket warning. Dropping at the next scope boundary, transferring the cursor, or deliberately holding a session open are meaningful. If indexed lifetime facts prove that an observable duty survives across subsequent work, show the owner and predicted release boundary in hover. Offer a short owner scope or a by-value loop only as *different timing choices*. Suppress the delayed-release note when timing is unknown or the cursor already finished |

A later resume consumes no hint and requires no opt-in. The minimal editor check is to inspect the two loop headers above, then change only `in @source` to `in source` in an example with a later resume. The first two displays must name different owners, and the third program must fail at the transfer/later use with a location for each. The context-sensitive wording is part of the design to validate; hover does not constitute evidence of independent discoverability.

## 3. Let a real function return the socket's close failure

**Keep the fallible owner in the function whose result the caller checks.** `display_prefix(rows ui limit)` takes the generator by value. It borrows `@rows` for its loop. The limit arm returns the count from `display_prefix`; it has no locally continuing break that could skip an unmarked close. Its caller executes `display_prefix(…) or_throw` before `ui.finish(shown)`. In the producer, an unscoped `lazy ( … )` puts the acquired socket directly in the lazy frame. A read-loop break reaches frame completion. There is at most one socket per cursor. [Revised socket program](programs-r1/11-inventory-socket-r3.dewy:3)

| First event | Cleanup and caller-visible result |
|---|---|
| Zero outer limit, or open fails | For zero, no request starts. Failed open creates no socket owner. The open error is forwarded and `ui.finish` is skipped |
| Source EOF | The final advance closes the socket before reporting end. A failed close is that advance's terminal failure. Later cursor destruction releases no second socket |
| Limit reached after k displayed items | The borrowed loop exits on the function's return. Save the proposed count, dispose the owning parameter, then hand off k only if cleanup succeeded. A close failure replaces the successful candidate |
| Read and close both fail | Producer unwind reports the whole read-and-close failure. The helper forwards it. It never retries close |
| Display and close both fail | The display error is already pending at function exit. Disposing the suspended frame adds the close failure. The caller receives both, and no success UI runs |
| Cancellable source stops | The explicit source suffix forwards cancellation. Cleanup retains any separate close failure under D42/D44. Stopping delivery does not drain the socket |

**Precisely which answers this needs.** D40 Q1 is decided: fallible cleanup contributes to the enclosing function's result. Apply that rule to an owning generator parameter and to terminal completion of its frame. A proposed return value becomes visible only after the duty succeeds. D40 round 7 already illustrates an ordinary consuming helper as a real function boundary. Q6 is about a *locally continuing* exit with a remaining fallible duty. This program has none at the point where the unfinished socket is released. The source loop borrows the owner and returns or forwards while the loan is active. Normal loop fallthrough has already observed successful terminal cleanup. Under either candidate Q2 timing, the socket is needed for continued pulls while suspended, and release precedes the caller's next instruction. The program requires neither a preferred answer to D40 Q2 nor approval of Q6's block suffix. If a caller instead wants to break an owning loop and continue in the same function, the round-2 alternatives still depend on **D40 Q6**: explicit checked consumption on every locally continuing path, or an authorized scoped-block marker covering them. Do not treat a suffix after the source as that marker. [D40 decisions and questions](../../../../docs/design/open_decisions.md:490) · [Consuming helper precedent](../../../../docs/design/proposals/cleanup/programs-r7/26_conservative_markers.dewy:2) · [Marker attachment and return-only exits](../../../../docs/design/proposals/cleanup/round7.md:129)

D42's direction preserves distinct pending failures as facets, for example `SocketReceiveFailed & SocketCloseFailed`; repeated instances of a kind require the agreed stack direction and D42's eventual concrete representation. This caller forwards the whole failure. It does not project a facet or inspect which stack shape won. Avoid importing the older cleanup proposal's group constructor into the public generator API. A verified infallible-drop-only implementation **must reject** a frame retaining this socket until it can route a fallible drop and preserve the pending failure. That is an implementation gate, not an unanswered D40 Q6 dependency of workload 11. [Combined failures](../../../../docs/design/decisions.md:716) · [D42 repeated failures](../../../../docs/design/open_decisions.md:425)

## 4. Regrade of five rewrites

Grades are paper design judgments on the same five axes as round 1. A 5 means the workload and its stopping contract have a direct expression under the proposed rules. Implementation and blind-reader validation are separate evidence. The arrows use the original A versions. No grade has been increased merely because a proposed tooltip exists.

| Workload | Obvious | Discoverable | Concise | Safe | Complete | Change and stopping witness |
|---|---:|---:|---:|---:|---:|---|
| [01 Reply journal](programs-r1/01-reply-r3.dewy:18) | 5→5 | 4→5 | 5→5 | 5→5 | 5→5 | Name the request's stream and give it to the loop by value. The visible `break` ends that owner before `finish_preview`. An owned break after a/b publishes a/b partial. An append failure still includes the token already handed off |
| [05 Port parser](programs-r1/05-port-rules-r3.dewy:33) | 4→5 | 3→4 | 4→5 | 5→5 | 5→5 | `tokens.next` yields a token directly. The only helper implements a real grammar requirement with the offset at EOF. An inverted range rejects before reading its following delimiter |
| [06 Retry preview](programs-r1/06-retry-preview-r3.dewy:13) | 5→5 | 4→5 | 5→5 | 5→5 | 5→5 | Replace the resume-after-last-item label and counter with a finite range on the left of the ordinary `and` header. Zero demands nothing; the request for end after four attempts checks the finished budget before asking for a fifth delay |
| [10 Monitor replay](programs-r1/10-monitor-replay-r3.dewy:15) | 4→5 | 3→5 | 4→5 | 5→5 | 5→5 | The chunk function borrows the cursor in both its signature and loop. Its match handles the actual offline `none`. Exhaustion runs the completion tail; the budget return leaves the next record for the next call, even at an exact chunk boundary |
| [11 Inventory socket](programs-r1/11-inventory-socket-r3.dewy:13) | 4→5 | 3→5 | 4→4 | 4→5 | 4→5 | The helper owns and returns; the caller checks that complete result before finishing the UI. One close on each acquired socket, and either failure remains reportable. Safety/completeness are for the D40 Q1 return rule, D42 whole-failure forwarding and round 3's fallible-frame contract |

**Remaining deductions, one per rewritten workload below 5.**

- **05, discoverable 4.** A parser author can find `next`, but may write bare `or_throw` and accidentally propagate legal EOF. Validate a `next` completion entry that shows “EOF = none” and offers “forward BadPortSyntax, keep EOF”; retain the deduction until cold readers choose the correct form for both the required-number and separator positions without coaching.
- **11, concise 4.** Splitting counting from the post-close success UI costs a helper even for one caller. To remove that cost without a hidden local return, settle D40 Q6 and compare its shortest checked local-scope version against this helper. An unmarked fallible break cannot earn a 5.

The eight other programs retain their original A grades. They were not rewritten or promoted here. Their remaining deductions and next checks are listed to avoid treating five revised examples as a completed panel. [Original grades](dogfood-r1.md)

| Workload | Remaining gap and what would resolve it |
|---|---|
| 02 Rotated logs | Discoverable 4. Recheck whether readers can locate the active shard's owner and distinguish EOF from read failure at the labeled cutoff using the revised ownership display |
| 03 Catalog | Discoverable 4. Check that a reader can find the prefixed lazy label and stop only after the last possible page, including an empty page with a continuation |
| 04 Asset tree | Discoverable 4. Test the diagnostic for accidentally yielding the child generator itself; it should offer incremental `child...` at the missing spread |
| 07 Meter pipeline | Obvious/discoverable/concise 4. Round 3 does not remove tuple packing/spreading at existing positional callbacks. Try a tuple-taking calibration API if owned by the application, and regrade against the original positional constraint |
| 08 Ledger zip | Discoverable/concise 4. Fixed pairs still need spreading at two positional APIs. Test direct loop destructuring against the existing helpers and retain the length-preflight requirement |
| 09 Game input | All five A grades were 5. Its ordinary variant match needs no round-3 change |
| 12 Channel export | All five A grades were 5. Its existing sample array already represents the variable-width field |
| 13 Recorder flags | Discoverable 4. Test whether the editor's type and handoff preview makes an eager two-result call's pending second item apparent on a first-item return |

**Verification performed.** Small independent control-flow scripts compared the old and revised parser on 9,331 token streams (up to five tokens including an injected lexical failure), checking read positions, error token offsets and commit decisions. The replay comparison covered 4,376 combinations of records, cursor position and chunk limit, including offline none and EOF probes. The socket comparison covered 4,440 availability/limit/fault combinations with open, read, display and close failures, checking operation order, close count, both pending failures and suppression of success UI. These scripts exercised the stated semantics, not a Dewy compiler, byte-offset arithmetic, D44 cancellation delivery or the platform socket backend. Still needed: compile the five source files when the feature exists; execute real ownership/failure injection including cancellation; check the disjointness diagnostic under type erasure; cold-test EOF handling and borrowed versus owning stops. The panel has not reached the all-5 bar.

## Open questions for the designer

### Q1 (a). What one advance delivers

~~~dewy
let g = lazy (1 (2 3) 4)
loop x in g printl([x])
~~~

Should the loop print four singleton arrays, or three arrays with `[2 3]` in the middle?

**Recommendation.** A, four singletons. A unary `map` or `filter` can accept every integer. A consumer that wants an atomic pair uses a fixed tuple or record. B still has the two demonstrated advantages for fixed rows forwarded through multiple positional calls. **Reversible before release.** Switching later changes callback arity, interleaving, backpressure and zip.

**Complete B alternative.** All ordinary eager bindings stay fixed-count, and the ownership, terminal, failure and cleanup rules above apply.

1. The immediate delimited lazy body, each streaming loop body and each selected streaming control arm is a sequence of entries. A bare body has one entry. Visit control entries incrementally. An ordinary nested group or block **in entry position** evaluates to completion and publishes its nonempty fixed pack as one step. A fixed pack binding or eager call returning the same pack makes the same step. Thus `lazy (1 2)` gives two turns; `lazy ((1 2))` gives one. In `lazy { if c ((1 2)) else ((3 4 5)) }` the selected arm contributes one whole row. With only the arm delimiters, it streams separate values. Indentation has no effect. Empty contributions keep looking in the same advance.
2. All fields must be ready before a row is delivered. A later field failing prevents handoff of an earlier field in that row. Earlier effects remain. `lazy { child() }` publishes a child owner as one value; `lazy { child()... }` forwards complete child steps; a spread container supplies its elements as singletons. An ordinary eager helper executes and cleans up before any handoff.
3. **New type usage specific to B.** `generator<(int64 int64)>` describes a two-field step. `generator<int64 | (int64 int64)>` permits a singleton or that pair. Preserve each fixed alternative's width and positional types. Unknown-width eager entries cannot silently become a variable-sized row. Use an array or exceptional/ordinary domain variants as ordinary single values, or iterate to produce a stream of elements. No runtime arity overload dispatch.
4. A simple loop binder denotes the complete contribution. For one proven width it substitutes its fields at an eligible call. With alternative widths, a step-local view can feed an exhaustive match, a collector accepting all field types, or a streaming re-expression. Narrow before storing a fixed eager pack or supplying a call. A scalar arm receives a singleton. A pack arm first tests the outer step width; a singleton containing a tuple can then be matched as a container. Thus the unary callbacks reject the middle turn of Q1, and a binary callback rejects the singleton turns. A fixed-row filter retains the whole row, and a map giving a fixed eager pair at its entry publishes that pair in one turn.
5. **Manual stepping under B.** A producer statically confined to singleton steps uses Q4. For one fixed width greater than one, its ordinary positional tuple is a lossless raw successful result: `.next` can return that tuple, `none` or a disjoint terminal failure under the Q4 proof. No one-slot success tuple is needed for scalar producers. For alternatives of *different* widths use the universal borrowed one-turn loop and match the step-local view there. This preserves the distinction between a two-field contribution and a singleton whose item is itself a two-field tuple; an implicit raw projection of both to the same tuple would erase it. A storable mixed-width value needs explicit ordinary product/variant representation.
6. A combined `and` header advances one complete step per input, left to right. If right ends, left can have performed one unmatched advance. `((a b))` as its body concatenates both contributions' fields. Explicit tuple-valued inputs retain nesting. `[g...]` and a fixed call spread concatenate fields; a delegated streaming spread preserves steps. `length=N` counts initial steps. A separate proof must establish remaining flattened length and positional types for a fixed call. `lazy ((1 2) (3 4))` has two steps and four fields.
7. A fixed B row can travel in registers or caller storage. It may save dispatches at a positional pipeline; it delays a handoff until the whole row is available. An adapter splitting a B row cannot undo already-performed computation. A plus explicit tuple items gives B's atomicity where the author asks for it. Local fusion must preserve the chosen demand rules. The meter/ledger gains and recorder counterexample are traced in [round 2's workload comparison](round2.md:103); they are not performance measurements.

### Q2 (c). Construction and type spellings

~~~dewy
indices = (n:int64):>generator<int64> => lazy loop i in [0..n) i
two = ():>generator<int64 length=2> => lazy (20 22)
~~~

Use `lazy` with the existing expression grammar, retain `loop` in the loop form, and spell the cursor type `generator<T>`?

**Recommendation.** Yes. Add reserved **`lazy`** and type name **`generator`**. Propose **`failure`** for the ordinary terminal-failure type parameter and reuse **`length`** for the exact initial count when proved. With A this counts values; with B it counts steps. Check keyword collisions and cold-read these names separately. No extra loop shorthand. **Reversible before release.** Renaming after source adoption requires migration.

### Q3 (b). Reading the two kinds of early stop

~~~dewy
keep_suffix = () => {
    let g = lazy (10 20 30)
    loop x in @g { printl(x) break }
    return [g...]
}
end_here = () => {
    let g = lazy (10 20 30)
    loop x in g { printl(x) break }
}
~~~

Should the first function return `[20 30]`, and the second dispose g at the break? Should a later read of g in the second function be a transfer error?

**Recommendation.** Yes. One owner, one current position. At an early exit expose which owner survives in the header and exit hover. Diagnose a later use after transfer and suggest `@g` when continuing. An intentional pause or abandonment does not need a general warning. A factory restarts; an explicit fork of eligible sources could be designed separately. **Reversible before release.** Changing ownership or implicit copying later can repeat effects or change finalization timing.

### Q4 (b). A direct token and a lossless single pull

~~~dewy
lookahead = (@tokens) => {
    let token = tokens.next or_throw<BadPortSyntax>
    if token is? none { return "end" }
    if token is? Dash { return "range" }
    return "other token"
}
observe_one = (@events screen) => {
    loop item in @events or_throw {
        if item is? none { screen.offline() }
        else { screen.show(item) }
        return true
    } else { return false }
}
~~~

Should `tokens.next` return the bare token when its possible results distinguish item, EOF and terminal failure? Should a one-turn borrowed loop work for **every** element type, including offline none or an error that can also terminate the source?

**Recommendation.** Yes. Keep the provisional `next` convention for representable flat results. Diagnose collisions and offer the loop which branches on the producer's internal outcome. In `observe_one`, delivered none calls `offline` and returns true, end returns false, and terminal failure leaves the function before either return. Source forwarding tests terminal provenance; ordinary postfix operators on a raw result test its value. Two examples of the raw forms are `g.next ??<none> fallback` to replace EOF while retaining unhandled failures, and `g.next or_throw<error>` when all terminal failures of interest are errors and EOF must stay. Applicable cancellation needs its own coverage. Universal generic iteration requires no proof about the payload. **No new name.** `next`, `none`, `loop`, `else` and the selectors are existing spellings. **Reversible before release.** Changing the result of public `.next` later breaks manual consumers.

### Q5 (a). A local one-off action inside a lazy body (D40 Q5)

~~~dewy
track = (slot source) => lazy {
    let delivered:int64 = 0
    defer slot.publish_count(delivered)
    loop item in source or_throw { delivered += 1 item }
}
~~~

With a pre-reserved slot, a proved count bound, an infallible handoff after increment and an infallible publish, should this action record the current count once at exhaustion or destruction, including consumer abandonment?

**Recommendation.** Keep the provisional, checked one-off `defer`. Its registration sees the producer's evolving private state. For reusable duties a ticket's existing `$__drop__` can own the same fields and enforce registration. A never-started body cannot have registered its action; acquire an owning ticket in the factory when such requests also need a record. A fallible durable write needs a checked boundary. **Reversible before release.** Changing whether or when an already-registered action runs is an observable change.

### Q6 (a). When a failed close reaches the caller (D40 Q1/Q6 and D42)

~~~dewy
first_visible = (rows ui) => {
    loop row in @rows or_throw {
        ui.add_item(row) or_throw
        return true
    }
    return false
}
preview = (service ui) => {
    let found = first_visible(service.listing_rows() ui) or_throw
    ui.finish(found)
}
~~~

Should returning from the function that owns rows first dispose the suspended traversal, so a failed close leaves `preview` before `ui.finish`? If displaying the row and closing the socket both fail, should the caller receive the whole failure?

**Recommendation.** Yes. Apply accepted D40 Q1 at this function boundary. A pending success is replaced by a close failure; a pending failure combines under D42. A failed read that already disposed its producer leaves a finished cursor with no close to repeat. This spelling works with either D40 Q2 timing and does not need Q6's local-exit marker. For a fallible owner destroyed at a locally continuing exit, retain the D40 question: require explicit checked consumption, or allow a marker on the scope that actually owns the duty. Until a supported checked path exists, reject that path. **Reversible before implementation.** Once callers depend on `finish` running only after a successful close, silent dismissal of the close failure would change program behavior.

### The whole design in programs

The full new programs are [reply preview and complete save](programs-r1/01-reply-r3.dewy), [port lexer and parser](programs-r1/05-port-rules-r3.dewy), [infinite retry plan and exact take](programs-r1/06-retry-preview-r3.dewy), [nullable replay across UI chunks](programs-r1/10-monitor-replay-r3.dewy), and [inventory socket with a fallible close](programs-r1/11-inventory-socket-r3.dewy). The reply's reusable owner alternative is [ReplyTicket](programs-r1/01-reply-owner.dewy). Helper names and example record fields are application-local; round 3 introduces no language or library name beyond the round-2 candidates in Q2.
