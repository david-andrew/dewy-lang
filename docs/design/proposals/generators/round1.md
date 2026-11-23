# Generators and multi-values, round 1

**Recommendation.** An advance delivers one complete contribution of the lazy body (option B). In `lazy (1 (2 3) 4)` there are three consumer turns. The middle turn binds two ordinary Dewy values. A call or array collector spreading that generator sees four values in order. This lets a row remain a row through a filter, a zip and a function call without allocating a container. It also gives an author a choice with observable consequences. If computing the third value fails, the middle turn never delivers the second value. Write two successive contributions when a consumer must be able to stop between them.

This is a proposed language contract. The sketch fixes explicit `lazy`, its implicit scope, eager ordinary functions, implicit pack expansion and static consumer safety. The choices about group boundaries, cursor copies and fallible consumption below are recommendations. D40, D42 and D44 are identified where their open choices matter. Examples using stream, journal and file helpers describe application contracts. No compiler changes, measurements, cold reads or implementation results are claimed.

## 1. Values and their consumers

A **pack** is the ordered results of one evaluation. A binding can remember them. Using the binding substitutes those values in order without rerunning the evaluation. A pack can be empty, singleton, heterogeneous or of varying arity. A singleton has the ordinary type of its value. A successful expression of type `void` contributes zero values. A path of type `never` has no normal result. For instance, `[if show 7]` can finish with an empty array, whereas `[exit(1)]` never hands an array to its caller.

| Expression | What the receiver gets | Example |
|---|---|---|
| `(7 "red")` | Two positional values | `let p = (7 "red")` and `paint(p)` fill two parameters |
| `[7 8]` | One array value | `let a = [7 8]` and `add(a...)` fill two parameters |
| A value of type `[int string]` | One fixed-length array with typed positions, Dewy's tuple | `let t:[int string] = [7 "red"]` and `paint(t...)` |
| `lazy (7 8)` | One generator with an initial cursor | `let g = lazy (7 8)` and `[0 g... 9]` gives `[0 7 8 9]` |
| `lazy ((7 "red"))` | One generator whose first advance gives two values | `loop row in g2 paint(row)` for `let g2 = lazy ((7 "red"))` |

A positional call and an array collector expand packs implicitly. A container or generator in the same position occupies one slot until explicitly spread. Thus `[g]` can hold a generator and `[g...]` consumes a traversal. `p[0]` and `p + 1` are errors for the pair above. `let (id color) = p` gives two bindings. Use `[p]` in a compatible array or tuple context to keep both values as one. The existing idempotent spread of several values in a collector (`[pair()...]`) can remain. It does not recursively open container-valued members. A dictionary or record entry still takes its required entry or field shape. Array dimension separators retain the decisions ledger's context rule. For example, `[(measure();) 7]` discards the measurement inside the group.

An eager binding or inferred result can carry a **choice of whole shapes**. This extends the current restriction to statically counted bindings and calls. Preserve branch correlations through binding, return, a function handle and matching. The previously flagged homogeneous-only restriction on written multi-results must also be lifted for this extension. Existing fixed contracts keep their positional count and proofs.

~~~dewy
choose = (wide:bool) => if wide (1 "red") else ("blue" 2 3)
let p = choose(true)
let f = @choose
let q = f(flag)
let n = match q {
    (id:int name:string) => id
    (name:string lo:int hi:int) => hi-lo
}
~~~

The proposed **new combination of existing type spellings** permits `let q:(int string) | (string int int) = f(flag)` and the same shape union after `:>` on an eager function. A pack shape in these positions describes the entire result. It does not turn a pack into a storable field of some other type. Here a string in position one implies three positions. Treating the positions as independent unions would invent a path. Unknown repetition is also expressible internally. `let p = (loop x in xs x)` eagerly completes and holds all its results, including zero on an empty input. It can need dynamic storage. `[p]` accepts any length when the element types fit. Put `lazy` on the loop to avoid constructing that eager pack.

## 2. Forms and output boundaries

| Form | Parse and operation | Status |
|---|---|---|
| `lazy price(x) * count` | Defer one ordinary expression, here the product | **New keyword and operand form** |
| `lazy (a b)`, `lazy { a b }` | Defer the two body entries, one after the other | **New forms** using existing block syntax |
| `lazy x in xs body` | Abbreviation for `lazy { loop x in xs body }` including normal loop header and fallback rules | **New shorthand** |
| `source...` | Spread an evaluated source once where several values are accepted | Existing postfix, **new generator operand** |
| `(...rest:int)`, `(head ...rest) = p` | Collect surplus positional arguments or bind the unmatched part of a sequence pattern under the existing rest rules | Existing prefix in binding positions |
| `$done` before `lazy { … }`, then `break $done` | Label the generator and terminate this traversal | Existing construct-label feature applied to the new lazy body |
| `match p { (a:int b:string) => … }` | Test the arity and then the positions of an eager pack or a loop's current contribution | Existing sequence-pattern spelling, **new scrutinee** |
| `generator<S length=N failure=E>` | Describe output shapes, optional exact initial step count and terminal failure bound | **New type and type-argument uses** |

After `lazy`, recognize a loop binding followed by `in` as the shorthand. Otherwise an immediately delimited body consumes its matching delimiter, including the ordinary range/literal distinctions in the expression parser. In the undelimited expression form, parse a full body expression as for an unbraced loop body, stopping at the surrounding argument, entry or delimiter boundary. For example, `lazy f(x)...` delegates inside the body and `(lazy f(x))...` spreads the constructed generator outside it. `lazy (f(x)...)` uses the delimited form. Newlines alone never batch outputs. An adjacent call `f(x)` and a handle `@f` retain their ordinary meanings.

**Every form creates a lexical and control scope at construction.** The activation begins executing on demand. Inside it, braces create their usual inner scope and parentheses retain their usual unscoped behavior. For example, `lazy (let k = 3 k)` owns `k`. An outer `printl(k)` cannot see that declaration. Inside `lazy { if b (let k = 1) else (let k = 2) k }`, ordinary definite assignment can make `k` available at the last entry. A function returning the generator can return immediately.

**Classify output positions from the syntax, before checking types.** The following rules give a precise version of B.

1. Read the immediate delimited body of `lazy`, a loop body, or a chosen control arm in streaming position as a list of entries. A bare expression body has one entry. Visit entries in order. A `loop`, `if` or `match` entry routes its body's entries into the same output, incrementally. Its conditions, scrutinee, range and call arguments are ordinary value contexts. Hence `lazy { loop i in [1..2] { i i*10 } }` gives four singletons. A filtering arm that contributes nothing keeps searching during the same advance.
2. An ordinary expression entry evaluates to completion. Publish its entire nonempty result as one step. This includes a pack literal occurring **as an entry**, a pack binding and an eager function returning that pack. Thus the second entry in `lazy (1 (2 3) 4)` and in `let p = (2 3)` followed by `lazy (1 p 4)` has identical behavior. `{2 3}` in that same entry position also produces the pair. A single-expression grouping around an ordinary value preserves the pack. A `void` expression produces no step. A nested `lazy` expression produces one generator value.
3. A postfix spread entry in streaming position evaluates the operand once. A generator forwards each of its steps with its original boundary. A supported container forwards its elements one at a time, each as one value. A pack already in hand forwards one contribution, subject to the existing placement rules for redundant pack spread. Nothing implicitly recurses into elements. `lazy { [1 2] [3 4]... }` gives an array, then 3, then 4. In an eager argument, group or collection the enclosing sink takes the full expansion before returning.
4. The syntax of body delimiters matters at exactly the list/entry boundary. `lazy (a b)` has two entries. `lazy ((a b))` has one pair entry. Likewise `lazy x in xs (x x)` streams two singletons per iteration. Write `lazy x in xs ((x x))`, or `pair = x => (x x)` and `lazy x in xs pair(x)`, for a row. In an arm `if c (1 2) else (3 4 5)` streams the chosen list. `if c ((1 2)) else ((3 4 5))` publishes the chosen row. Replacing a **value expression** by a binding or call returning the same values preserves its contribution. Turning a **streaming body** into an eager helper intentionally moves an evaluation boundary.
5. An inner block evaluated as an ordinary pack entry uses the eager rules even if it contains a loop. `lazy { (loop x in xs x) }` can buffer the whole input for a single step. `lazy { loop x in xs x }` streams. When ordinary punctuation could hide this distinction, the editor should show “one step containing all results” on the eager group. To delegate, put `child...` directly in the streaming body.

Prefix `...` has no free expression form here. For example, `total = (...xs:int) => sum(xs)` collects the surplus positional integers. A rest binding in a pack pattern retains the remaining values as a pack. A rest parameter receives an array. A bare `...` in a parameter list starts keyword-only parameters. Neither form makes `...g` an eager collector. Write `[g...]`.

## 3. Demand, order and completion

A generator value owns a cursor, its capture environment and any suspended child. Construction initializes captures in lexical first-use order (an explicit capture supplied through a closure was already bound when that closure was made). Construction does not enter the body, register a body defer, evaluate a source expression or start a task. For example, `lazy x in open_feed() x` opens the feed on the first advance. In `let feed = open_feed() or_throw` followed by `lazy x in feed x`, the open is immediate. Capture evaluation can itself move or copy an owner. If initializing a later capture fails, release the initialized prefix and report the creation failure to the creator.

| Current state and operation | Result and next state | Witness |
|---|---|---|
| Fresh or suspended, advance | Run synchronously until a nonempty contribution is complete, a terminal outcome occurs, or execution diverges. Transfer the contribution before returning control | `lazy (printl("A") 1 printl("B") 2)` prints A on first demand |
| Suspended, advance | Resume just after the transferred contribution. A delegated child resumes first | Breaking after 1 above leaves B unprinted |
| Fallthrough or `break $done` | Run outstanding cleanup. Report end if it succeeds, otherwise report the terminal failure. Mark cursor finished | With `$done` prefixing `lazy { 1 break $done 2 }`, only 1 is produced |
| Forwarded body failure | Clean up, combine failures where required, report terminal failure once and mark finished | `lazy { 1 to_int("bad") or_throw 2 }` delivers 1 before the failing advance |
| Finished, advance again | Report end, with no repeated cleanup, failure or side effects | Two advances after draining `lazy (7)` both report end |
| Destroy an unstarted or suspended cursor | Release initialized captures and active scopes. Skip remaining body entries and report cleanup failure to the destroying scope | Dropping `lazy { printl("open") }` before first demand prints nothing |

The last output and successful exhaustion are distinct. In `lazy { 1 printl("complete") }` the print requires another advance. Destroying the suspended cursor runs registered cleanup only. A failed attempt to compute an atomic row delivers **no prefix** of it. Earlier observable effects still happened, and initialized fields or temporary owners are cleaned up. `lazy ((read_a() read_b() or_throw))` may perform the first read even when the second fails. There is no rollback of I/O.

An eager call runs through its return and callee cleanup before any of its results can be published. For `pair = () => (1 printl("work") 2)`, `lazy { 0 pair() 3 }` first gives 0. The next advance prints work and gives the pair together. A helper returning `lazy (1 printl("work") 2)` and spread at the same site first gives 1, then prints work on the request for 2. Side effects cannot move across these demand boundaries during inlining. Discarding `pair();` still evaluates the call. Discarding an unstarted generator value releases its captures without running its body.

Delegation is depth-first. In `lazy { 0 inner()... 4 }` the factory is called once when reached, left-to-right. One child step is forwarded per outer advance. An empty child continues to 4 on the **same** advance. A child failure follows the outer terminal path. Early destruction closes the active child before leaving the scopes that hold it. With `inorder = node => lazy { loop c in node.left_children inorder(c)... node.value loop c in node.right_children inorder(c)... }`, only the active traversal path is needed. Here the child collections are ordinary application fields. A cyclic graph can diverge. An endless `lazy { let n:int = 0 loop true { n n += 1 } }` requires no list of past outputs. An advance on an infinite filter that never matches can itself diverge.

## 4. Output types, length and consumer proofs

Use `generator<int>` for a cursor offering one integer per successful step, `generator<(int string)>` for one integer and one string per step, and `generator<(int string) | (string int int)>` for a choice of rows. Within the new shape argument, scalar `T` means a singleton and `(T U)` is a pack, never a tuple object. `generator<[int string]>` gives one tuple object per step. For `lazy (42 "hi" true)` the singleton payload type covers `int | string | bool`; an implementation can retain more precise literals. `lazy { if false 1 }` can be empty; there is no empty step. A generator with no possible step has bottom output shape, expressible as `generator<never>`. A bound step contract admits a narrower concrete shape only when every possible row fits it at the same arity. A required initial length must also be proved and the candidate terminal failures must be contained in the stated bound.

Infer three independent facts. **Step shape** describes the legal rows on one successful advance. **Step count** describes successful steps over a full normal traversal. **Flattened shape** describes their concatenation for sinks such as calls. For `lazy ((1 "a") (2 "b"))` these are a two-field row, two steps, and four values in integer/string/integer/string order. Knowing merely “four values, each integer or string” cannot prove the same call. A filter retains the step shape and generally loses the exact count. An `if` chooses whole alternatives. Sequential entries concatenate, loops repeat their body, and delegation composes the child's summary. An inferred body with private state can still prove an exact count when its loop bound and fixed contributions prove it locally.

`length=N` describes the step count **from the start, conditional on normal completion**. It is neither a promise that the next wait succeeds nor a request to enumerate a stream. N is a proven nonnegative size fact. `let g:generator<(int int) length=1> = lazy ((4 5))` has flattened arity two. For `squares = n => lazy i in [0..n) i^2`, a bound proven nonnegative and representable gives initial length n. A filter, early termination, unknown recursion or unconstrained n can leave the length unspecified. The annotation stays valid on a moved or partly advanced cursor as a fact about its origin. A call that needs *remaining* length uses cursor-position facts: on construction use the initial summary, subtract transferred rows when proved, and invalidate after an unknown mutation through `@g`. Even with `length=1`, `add(g...)` after consuming the pair is rejected. No implicit traversal or mandatory runtime counter is associated with this parameter.

The compiler can describe zero-or-more and positive repetitions internally using a repeated element/row. A completed eager call of unknown count can supply one variable-width row if nonempty. Once selected, the row stays correlated for that step. For example, `many = xs => (loop x in xs x)` and `lazy { many(xs) }` may need an array-backed pack. There is no public repetition type syntax in this round. Such types can be inferred, passed generically or widened by explicitly collecting a container. `lazy { many([]) }` with a suitably typed empty input has **zero steps**, not one empty row.

| Sink | Obligation, checked before execution | Example |
|---|---|---|
| One value, including conditions and named arguments | Each returning alternative must have arity one and meet its type | `(p + 1)` rejects a possible pair |
| Fixed positional call | Every flattened alternative fits the same statically selected signature under normal defaults, conversions and keyword rules | `add((lazy (20 22))...)` succeeds; `add((lazy (1 "two"))...)` fails on position two |
| Rest call | Fixed prefix must fit every alternative. Every surplus position must meet the rest element type | `total((lazy i in xs i)...)` works for integers, including an empty input |
| Array or tuple collector | Each contributed value satisfies the target element or positional type and any length obligation | `let rows:[int string] = [(lazy ((1 "a")))...]` is one two-position tuple |
| Binding, unpack, match | A whole binding retains alternatives. An irrefutable unpack must fit all of them. A match may narrow them arm by arm | `let (a b) = q` fails for `q` in §1, but its two-arm match succeeds |
| Generator loop | One body entry per successful step. A simple binder gets the **whole pack** at its step shape. A pack binder tests/destructures that shape statically | `loop row in g paint(row)`, or `loop (id color) in g paint(id color)`, for a two-field generator |

For `loop x in lazy (1 "two")`, a scalar-only operation must cover the scalar union. For `loop x in lazy (1 (2 3))`, `x` has the choice of a singleton and a pair. An exhaustive `match x { v:int => v (a:int b:int) => a+b }` handles it. Match the evaluated payload once, in arm order, checking arity before projecting fields. Unguarded `_` or an outer `else` covers the remaining shapes, including empty for an eager pack. A typed scalar arm can receive only a singleton. A sequence arm on a singleton container keeps the existing sequence matching behavior, so distinguish a container alternative with a typed arm first when necessary. For a generator pack binder, `(a b)` opens a multi-value step; `[a b]` on a single tuple item uses existing container destructuring. Never infer that a single container is two arguments to a call. Preserve the existing conservative product-coverage rule for matches. Reject lack of proof and identify an uncovered arity, position or alternative.

Expand arguments before ordinary overload resolution. One overload must handle every alternative, including defaults. A two-argument overload and a three-argument overload together do not imply dynamic dispatch. An explicit `match` can select different calls. Effects of preceding arguments, a drained spread, following arguments and omitted defaults occur in that order, once. If a spread fails, do not run later arguments or enter the callee. A callee demanding all of `naturals()...` as rest arguments can wait forever. A loop can stop after a prefix.

Retain existing checked-length policy for materialized arrays and existing unpack obligations. An unknown array length at `add(a...)` may be checked where `$runtime_checks` permits it. For a **generator** spread into a fixed arity, require a static proof that every normally completed remaining flattened shape fits. Do not probe a third item to check that two exist: the probe could block, fail or perform I/O. `let a = [g...]` followed by a length guard on `a` makes the drain explicit. A known ill-typed alternative in an eager pack also fails statically. Data-dependent choice of an already-proved match arm and runtime length assertions on explicitly materialized data are distinct operations.

## 5. Stepping, copying and zip

For a source loop, the ordinary fallback runs only if its body was never entered. An empty contribution does not enter the loop body, and forwarding a terminal failure leaves the function before any fallback.

A cursor is single-pass. Evaluating the factory again constructs a fresh cursor. Reading or assigning a generator value has ordinary Dewy ownership semantics. A permitted copy starts at the **current suspension point**, with independent private state, child cursor and owned payload. Changes through explicitly shared handles and external effects retain their ordinary identity. For example, copying `lazy (printl("open") 1 printl("again") 2)` after the first output lets each cursor print “again”. Neither prints “open” a second time. A cursor that has finished copies as finished.

`loop x in g` obtains a traversal value at entry. A copyable binding used again retains its cursor. A by-value traversal of a move-only cursor requires an allowed transfer, such as a last use, or a fresh result. `loop x in @g` advances the named cursor in place. `g...` in an eager sink or in delegation follows the by-value rule. To spread the remainder *in place*, write `[loop x in @g x]`. There is no new `@g...` spelling. For example:

~~~dewy
let g = lazy (10 20 30)
loop x in @g { printl(x) break }  # 10
let a = [g...]                    # [20 30], g is needed again
let b = [loop x in @g x]          # [20 30], g is now finished
~~~

An early `break` destroys the loop's **owned traversal** on exit. A loop borrowing `@g` releases its loan and leaves the cursor suspended, so another consumer can resume it. Moving the cursor around does not trigger its cleanup. To ensure cleanup at the stopping point, let the loop own the temporary or give the bound owner a short scope. Copying an ordinary numeric cursor is legal. A possible move-only capture, suspended resource, delegated cursor or outstanding one-off cleanup makes the **whole concrete generator type** move-only, even before first advance. The compiler must never duplicate a future cleanup registration to save a move or hide that restriction by erasing the type.

**Manual stepping.** Give built-in generators an unambiguous view of a step using existing single-value representations. Proposed extension of existing `.next`: `g.next` advances the mutable receiver once. It returns one fixed tuple/array containing **all** fields of a successful step, `none` at end, or the terminal exception value on failure. For a singleton use an inline `array<T length=1>`; for a fixed mixed row use `[T U]`; for a choice preserve the corresponding container union. A variable-width row can use its already-owned typed storage. For `g = lazy (none)`, the two answers are a one-element success containing `none`, then bare `none`. An exception emitted as data likewise arrives inside a successful row. A row whose only value is itself a tuple has one **outer** slot. This envelope is the public result of manual stepping only. A generator loop binds its contents directly. Passing a generator through a generic loop must preserve that rule; the provisional user-defined `next -> item | none` adapter keeps its existing contract.

~~~dewy
let g = lazy ((20 22))
let r = g.next
if r isnt? none {
    let [a b] = r
    printl(a+b)
}
~~~

In a combined `and` header evaluate source expressions once in source order, then request one **step per source**, left-to-right per turn. Stop on the first end. An earlier source may already have delivered a row when the later one ends; release that row, without undoing its effects, and leave later sources untouched. Static index bounds can avoid a request only if doing so preserves observable effects, cursor positions and cleanup. If a non-peeking zip must never consume an unmatched value from a live device, use an application reservation or choose the known-limiting input first. `loop a in @left and b in @right use(a b)` does not promise rollback. In an `or` header, exhausted scalar sources contribute the existing absence on later turns. For a multi-field step whose absence would lose row boundaries, reject that header in round 1 and suggest zipping explicit tuple-valued items or writing a loop over manual steps. This extension to combined headers exceeds today's one-binder, noncombined provisional iterator support.

~~~dewy
zip_rows = (left right) => lazy {
    loop a in left and b in right ((a b))
}
let z = zip_rows([1 2] [10 20])
loop row in z printl(add(row))     # 11, then 22
let flat = [z...]                  # [1 10 2 20]
~~~

With mixed-type scalar inputs a row still has both original positional types. If an input itself supplies packs, `(a b)` concatenates their fields under ordinary substitution. A tuple or record on each side preserves nesting if the two source rows must remain identifiable separately.

## 6. Captures, control and concurrency

**Capture values at construction.** Resolve free locals as for a closure. An implicit capture is a read-only snapshot, copied or moved at last use. COW can retain a buffer but writes remain independent. `let x = 1`, `let g = lazy x`, then `x = 2` gives 1 on consuming `g`. A declared local inside the body, as in `lazy { let n = 1 loop true { n n *= 2 } }`, is private mutable state across advances. Module globals and intentionally shared handles retain their existing semantics. Giving a name to a pack eagerly reads its components at the binding, so `let p = read_pair()` before `lazy p` does the read now.

Reuse the closure capture form for **intentional sharing** without inventing a generator capture list. For instance, `let read = ($capture @x) => x`, followed by `let g = lazy read()`, snapshots the callable's environment, which already explicitly shares the local. For a private writable snapshot, initialize `let n = start` in the body. Direct assignment to an implicitly captured outer `start` is an error. A snapshot or ordinary promotable shared local can outlive the creator. A capture that retains a mutable caller parameter, an element loan, an arena allocation past reset or a nonescaping method capture remains subject to its existing provenance and escape checks. Boxing the cursor cannot extend a borrowed place's authority. In `bad = (@xs:array<int>) => lazy xs`, reading `xs` captures its **value** when that value is copyable; it does not let the consumer modify the caller's array.

**Values cross an output boundary by ownership transfer or permitted copy.** Permit internal loans only while base storage and exclusivity are provably stable through suspension, relocation, copy, resume and destruction. The conservative first implementation may reject a loan live across a suspension and suggest ending its scope before the output. In particular, reject a guard keeping a lock held when control passes to arbitrary consumer code. That code can acquire the same lock even in a single task. In `let n = { let held = @(m.lock()) held.count }` followed by a contribution `n`, the guard ends inside the short scope.

**Round 1 produces owned values.** Reject `lazy { loop @x in values { @x } }`: storing the returned address or resuming the producer could invalidate it. To edit the original directly, use `loop @x in values { x += 1 }`. To produce independent results, use `lazy x in values x+1`. A future lending loop could confine each result to one body turn, forbid retention, transfers and container collectors, and exclude resume, mutation, move or destruction of the base while borrowed. That needs a distinct checked consumer capability. Present `@` alone does not express it.

**Labels target active constructs in the same execution.** A bare metatag on its own prefixes the following construct. A blank line does not detach it. Applying that existing feature to a lazy body makes `break $done` leave it normally after cleanup. An ordinary `break` or `continue` still targets the innermost loop within the generator. Reject `continue $done` on a lazy target because it has no next iteration. Reject either jump to a label outside the lazy boundary or into a child through delegation. Preserve active-label uniqueness within each control domain. A plain `return`, including `?? return`, in the body cannot target the already-returned creator and has no generator result channel. Reject it. A nested ordinary function may return normally. For example:

~~~dewy
take_until = (source stop) =>
    $done
    lazy {
        loop x in source {
            if x =? stop break $done
            x
        }
    }
~~~

**Advance using exclusive access.** A suspended value may move to another task if all possible stored states and reachable captures, delegates and cleanup duties satisfy Dewy's `Send` rules. For example, a cursor over owned integers can be passed by value to a task. An explicitly shared mutable lexical capture, local loan, task-affine I/O owner or task-scoped cancellation value prevents that transfer. For example, passing the cursor made from `($capture @x) => x` to another task cannot disguise that shared capture. A moved, sendable cursor over integer values can be consumed with `loop n in input printl(n)` inside its receiving task. Infer this structurally for all reachable states, including before first use; a fresh value cannot be sent if its body can suspend with a thread-affine resource whose drop would run elsewhere. Moving a permitted cursor transfers the cleanup duty. Simultaneous or reentrant advances on the same place violate exclusive access. Sharing a synchronized handle that can transfer the cursor still requires exclusive ownership for each resume and the usual restrictions on waits under locks. A generator itself starts no worker and has no independent cancellation token.

## 7. Effects, terminal errors and cancellation

Charge work at the operation that performs it. Summarize construction, advance and destruction separately, preserving captures, authority effects, conditional costs and failure bounds at indirect calls. For example, `make = path => lazy { path.read_text or_throw }` may construct a small cursor without I/O. Consuming it may read, block, allocate and fail. Destruction may release a resource even when the next entry would have been pure. An owner acquired outside `lazy` moves its acquisition and possible open failure to the creator. A caller with `& no blocks` can hold a cursor with a blocking advance only if its construction, any copies, and every cleanup it must execute meet that caller's contract.

A written `generator<S failure=E>` bounds **terminal** resume and disposal failures together, including failures of captures acquired before first use. Omitted `failure` on an explicit type means `never` for ordinary terminal failures. Inferred types carry the actual bound. A direct factory failure remains in the factory's own result, e.g. `generator<string failure=ReadFailed> | OpenFailed` for illustrative application failures. Handled errors produced as payload remain in S. Ordinary effects are carried in compiler summaries; an erased `generator<S>` alone does not promise a pure, nonblocking or cheap resume, or copyability. An unknown summary cannot satisfy a restrictive caller by omission. No public syntax for a per-phase effect row is required for the concrete and generic cases here.

`or_throw` executed inside a lazy body forwards to the **current advance**. The creator can have returned long ago. In `lazy { to_int(s) }` an ordinary parse failure is data in a successful step. In `lazy { to_int(s) or_throw }` it is a terminal failure, outside the row. For manual recovery examine `g.next` with ordinary `match` or `??`. For a loop over a potentially failing generator, require `or_throw` after the source to forward ordinary terminal failures, or handle manual steps explicitly. An unhandled failure never supplies a fake last element. For example, `loop n in parsed or_throw printl(n)` propagates a failed advance; the loop can already have printed a prefix.

**A spread which drains a fallible source must account for failure.** In another lazy body's streaming output, `child...` delegates its terminal outcome into the parent's summary. In an eager spread this round requires visible propagation at the consumption site: `[(g... or_throw)]` and `add((g... or_throw))`. This is a **new use of the existing suffix on a generator spread**. It selects terminal failure before handing values to the enclosing sink. On success it preserves the payload, even when a payload value has an exception type. Unmarked eager spread of an ordinarily fallible generator diagnoses the failing resume or cleanup and suggests this form or a loop with an explicit handler. Inside parentheses in these examples the spread targets an eager sink. A failed eager collection or argument list destroys accumulated temporaries, propagates the combined failure and never hands off a partial result. Prior observable effects remain. For an explicit policy on partial results, iterate, store the prefix, and examine the terminal outcome.

**D44 integration, conditional on its adoption.** Interpret waits and checkpoints in the advancing task's cancellation context. Constructing a cursor in a cancellable task does not permanently mark it canceled. On delivery of plain `Canceled` from its source, a plain source loop ends quietly under D44 Q5; `loop x in g or_throw …` instead forwards it. The plain form still requires explicit handling/forwarding for any possible ordinary terminal failure. Manual `.next` reports cancellation outside the row. Delegation forwards it. A draining spread must not silently certify a partial list or arity as complete. If cancellation is possible, require the same explicit spread suffix, or a loop with the desired stop policy. Where D44 Q1 applies, infer cancellation at the call site. The `failure=` argument does not require writing `Canceled`. A pure numeric advance is not a hidden cancellation point. A long-running filter can use the proposed `check_cancel() or_throw` inside the loop. No per-element poll is implicit.

For `Canceled` accompanied by a failed close, quiet loop completion can consume only its own cancellation, never the unrelated failure. Route the remaining failure under D42/D44 or require an explicit handling site. A collected data value that might contain `Canceled` must obey D44 Q2 containment, including through a suspended frame, output row or erased generator. It may not outlive its originating work or enter cleanup/protected work. Save a plain progress count or a boolean instead. D44 Q7's loser-cleanup restrictions still apply to drops inside racing tasks. A destroy operation releases resources under the owning task's cleanup policy, with D44's grace running from cancellation. An abandoned cursor does not send cancellation to whoever created it.

Batch 10 of the decisions ledger already makes ordinary `??` and `or_throw` treat `Canceled` like other failures. The older guide's special passthrough does not decide this proposal. If D44 is deferred, keep the implementation's existing source cancellation protocol separately identifiable and gate its public generator-loop rule on D44. No rule for a generator requires weakening D40's cleanup reporting or D42's combined-failure coverage.

## 8. Frame cleanup and the case for defer

Use D40 Q2's proposed owning-block end for observable cleanup. A suspension holds every still-active scope open. Resuming a loop and leaving its body closes that iteration's scope then. Termination or destruction cuts through the active scopes from inside out. Within each one run registered defers in reverse registration order before dropping live locals in reverse ownership order; use the ordinary hook/field ordering for each local. Mark each duty discharged before invoking it. Moves transfer duties; they never duplicate them. Unreached registrations do nothing. An unstarted body therefore has no defers, but initialized captures still clean up. For example:

~~~dewy
watched = () => lazy {
    defer mark("outer")
    loop i in [1..2] {
        defer mark("iteration")
        i
    }
}
~~~

Assume `mark` is a bounded, infallible application action. Break after 1 from an owning traversal: “iteration”, then “outer”. Exhaust normally: “iteration”, “iteration”, “outer”. Break while borrowing `@g`: neither outstanding action runs at the break; both run if that suspended cursor is then destroyed. A generator that may register these one-off duties is move-only. A `defer` in the ordinary factory belongs to that factory and runs before its caller can consume the returned generator.

A generator's synthesized cleanup plays the same role as an owner's `$__drop__`. No finalizer runs as an unobserved background job. A cleanup failure during an advance is that advance's terminal failure. During destruction on a consumer's return or local exit it is a failure of the **destroying function**. For example, if a read fails and closing the reader fails, retain both as `ReadFailed & CloseFailed`. Two failures of the same kind follow D42's stack rule. If destruction after a successful `break` fails, following consumer code does not execute as if the break succeeded. Under D40 Q6's proposed visible-exit rule, put an owned fallible cursor in an enclosing marked scoped block and borrow it in the loop, or explicitly consume the resource under an existing supported close contract. Do not treat a suffix after the loop as a mark on a nested scope.

~~~dewy
{
    let g = read_rows(path)
    loop row in @g or_throw {
        if enough(row) break
    }
} or_throw
publish_summary()
~~~

Here `read_rows` is an infallible factory with fallible reading and cleanup. The source suffix forwards advance failures, and the block suffix acknowledges local disposal on leaving this block. If D40 requires a marked local exit, a fallible temporary traversal whose drop has no such owner is rejected with the named-block fix. The same distinction applies to a consumer body error and destruction of a retained generator during assignment. A consumer `continue` cleans up that body iteration and advances its cursor again. A labeled jump that actually leaves the traversal releases its owned cursor on the exit path. A compiler-managed panic follows ordinary unwind guarantees. No lexical mechanism promises execution after a process kill, hardware loss or a foreign abort.

### A token reply whose consumer may disappear

A request reserves one bounded journal entry. Producing the next token can block or fail. A consumer can read only the first few tokens and return. The journal needs exactly one final status and exactly the delivered prefix, including the empty prefix after a started request. Give each session one move-only entry. In this example the application prepares the bytes before handoff, has a checked maximum reply size, and can publish an already-reserved prefix length and status with an infallible store. A durable write to arbitrary storage is a different contract.

~~~dewy
reply = (request journal) => lazy {
    let slot = journal.reserve(request.id) or_throw
    let delivered:int = 0
    let complete = false
    defer slot.publish(delivered complete)
    loop token in tokens(request) or_throw {
        slot.stage(delivered token) or_throw
        delivered += 1
        token
    }
    complete = true
}
~~~

`reserve` and `stage` may fail. `slot.publish` returns void, cannot block, allocate, panic or fail, and reads the **current** locals on exit. The schema here counts tokens, and the slot retains their prepared bytes. `tokens` offers owned tokens. After staging, the increment and singleton handoff must be infallible with no intervening checkpoint; use a proven bounded counter and an ownership transfer. “Delivered” means handed to this generator's immediate consumer, independent of that consumer's later acknowledgement or of a zip discarding an unmatched row. Record an application acknowledgement separately if that is the required definition.

| How the traversal ends | Journal observation |
|---|---|
| Body reaches source end | Tail sets `complete` and the action publishes the full prefix |
| Consumer breaks after k handoffs and owns the cursor | Destruction publishes k and partial, including a break after the last token if end was never observed |
| Read/stage fails partway | No half-staged token is counted. Terminal unwind publishes the prefix then reports the error |
| Cancellation during an upstream wait | The source suffix forwards it, so the normal tail cannot mark the reply complete. Cleanup publishes the prefix |
| Borrowed consumer breaks; owner later resumes | No premature record. Publication occurs at actual exhaustion or disposal |
| Dropped before first demand, or reservation fails | No body registration owns a slot. If every *created* request needs a record, reserve in the factory and transfer an owning ticket with its own drop into the cursor |

For one local policy, the checked `defer` keeps registration beside the successful reservation and lets it see the private counters at unwind. Code after the producer loop covers normal exhaustion only. Code after a caller's loop cannot observe all owners or the producer's private staging state. A library adapter, illustratively `on_finish` (**candidate helper name only**), can own the producer, count observed rows and invoke an infallible callback on exhaustion/disposal. It must use the same move-only, first-demand, completion and borrow rules. Placed downstream of a filter, it counts filtered rows, and it cannot see a producer's private staged data unless that state moves into the adapter's interface. For a reusable logging policy, that refactoring can be worthwhile.

A journal ticket with `$__drop__ = ():>void => publish(delivered complete)` can instead own the slot, bytes, index and complete flag; `ticket.stage(token) or_throw` advances only the safe prefix. The same return, disposal, error and cancellation cases then follow from ownership. The ticket also naturally covers a reservation made before first demand. For a shared journal protocol this is the stronger API because callers cannot forget the registration. If “record” really requires a fallible flush or remote acknowledgement, a plain defer cannot implement that requirement. Use a fallible owner/finalization boundary with D40 reporting and durable storage if required. Neither a callback nor after-loop code can make a lost device acknowledge a record.

### Two smaller comparisons

| Need and example | Checked local defer | Owner, adapter and after-loop alternatives |
|---|---|---|
| A parser marks a private scratch segment and must restore exactly that segment when its streaming choice ends. `let mark = scratch.used`, then `defer scratch.used = mark` before producing rows. Assume exclusive frame-owned scratch, an infallible scalar store and stable storage | Wins for a one-off nested scope. The registration sees the current scratch and the entry mark, even on early drop during a delegated branch | A reusable segment owner can enforce every reservation. An adapter around the whole stream sees the wrong lifetime for nested branches unless each branch becomes an owned substream. A trailing assignment misses early drop |
| A stream measures elapsed time to its last consumer and increments a counter. `defer metrics.record(start)` after first demand, with a proven nonblocking timer/counter | Covers all owning exits, including partial consumption | A generic finish adapter already has the start, stop and count and wins on reuse. A timed owner works too. Code after the loop suffices only in a function that owns every exit and explicitly handles each one |

Keep D40's provisional one-off, non-failing defer pending the choice in §11. It cannot `return`, jump, propagate an error or suspend to produce another step while unwinding. Check its transitive effects against the cleanup policy. The strongest case is access to *producer-private evolving state at the correct lexical lifetime*. The owner alternative has the same expressive power when it packages that state and preserves its borrow; ease of expressing a local policy is the actual decision.

## 9. Choosing the unit of advancement

Consider `g = lazy (1 (2 3) 4)`, `p = (2 3)` and an eager `pair = () => (2 3)`. Keep the chosen policy independent of who asks for the next step. Otherwise changing a consumer could change the producer's side effects.

| Consequence | A. One value | B. One contribution (recommended) |
|---|---|---|
| Observable turns | Four. The consumer can stop after 2. A literal nested group can produce 2 before evaluating 3 if it is routed through the streaming sink | Three. Reaching the middle entry evaluates both fields before its first handoff |
| Eager boundary | `pair()` must finish on the second turn. A suspended cursor owns the pending 3 until next advance or destruction | `pair()` finishes and transfers the whole row in one turn. Literal, binding and eager call all deliver the same row |
| Scalar loop | `x` has the union of the element types. Ordinary arithmetic is natural on a homogeneous stream | Homogeneous singleton streams work identically. Mixed steps require shape-aware uses, and `f(x)` can pass several arguments |
| Rows and zip | `lazy ((a b))` loses pairing. A one-value tuple `[a b]` is an excellent explicit row and often has no allocation. A variable-arity row needs an explicit sum or container | One pair or triple can reach one loop iteration and fill a positional call. A zip takes one row per side, regardless of width, and packs preserve mixed position types |
| Variable branches | Two versus three values changes stream length. Their common origin is invisible to a general consumer | A single two- or three-field contribution can be matched as a unit. A branch written as successive streaming entries remains two or three turns |
| Spread and delegation | One item per advance throughout. In-place flattening and eager spreading use the same unit | Streaming delegation preserves boundaries. Calls and collectors concatenate fields. For `[g...]` both A and B give `[1 2 3 4]` |
| Effects and backpressure | Lowest latency for individually computable fields. Literal groups may interleave with the consumer even though an eager pair helper cannot. A staged eager pack can keep an unconsumed owner live | A complete logical row or no row. Computing an expensive or blocking field delays the first field, and an unbounded eager row may never publish |
| Generated code | Small, uniform item convention. Separate resume dispatch per scalar in an unfused multi-result helper and possible carry storage | A fixed-width row can travel in registers or a caller result slot. Fewer dispatches per row, but larger transfer and possible variant tag. Scalar-only streams need no row object in a loop |

**Two hybrids.** A scalar core plus explicit tuple rows needs almost no additions to the existing iterator checker. `loop [key value] in pairs use(key value)` is excellent when a row is domain data that callers want to store. `use(row...)` then opens that container explicitly. Choose A with that convention if avoiding the list/entry distinction in §2 matters more than transporting Dewy multi-results. Alternatively a group-aware public cursor can expose an ordinary library projection for scalar iteration: `flatten = source => lazy { loop row in source { loop v in [row] v } }` when the collected fields have a common element type. A heterogeneous row can instead be explicitly matched. The helper may need storage and does not make a grouped producer suspend earlier. A buffered scalar facade still has to compute a whole B row before delivering its first field.

Avoid selecting A for a scalar binder and B for a pack binder. In `lazy ((first() second()))`, changing the binder or passing the source through a generic function would then change when `second()` runs. Avoid grouping an entire loop iteration automatically for all contexts: an iteration can produce indefinitely before returning, as in `lazy { loop true { naturals()... } }`. A delegated child's first step must be reachable.

**Decision criterion.** A and explicit tuple rows are sufficient if `zip` is the only use case. B earns its extra distinction when the *same* multi-result expression can be bound, matched, delegated several levels and passed to an existing positional function without conversion. The concrete price is the extra grouping in a streaming arm and the latency of its slowest field. The tests for B should include first-output latency and `break` traces as well as row values.

## 10. Lowering and verification cost

Lower each demanded concrete lazy body into a resumable control-flow graph. Its cursor needs a program counter, captures, locals live across a handoff, initialized-owner bits where paths disagree, and the current child plus its continuation for delegation. An output writes into the consumer's result slot and records where to resume; an ordinary callee completes on its ordinary call stack. Emit a destruction entry using the same lexical cleanup plan as normal unwinding. `lazy (1 2)` can be represented by a tiny integer state. `lazy { let ticket = acquire() or_throw 1 use(ticket) }` needs a state distinguishing “ticket owned” from “never initialized” or “transferred”.

| Placement or optimization | Condition and example | Cost obligation |
|---|---|---|
| Fused loop | A single known consumer of `lazy i in xs i^2` can receive the square in its existing loop body. An inlined map/filter chain can route values directly to that consumer | No generator heap object, per-item allocator, virtual resume call or intermediate array. Preserve source snapshots, arithmetic costs, cancellation points, body interleaving, early exit and every hook |
| Inline or caller-owned frame | A known-layout cursor saved locally or returned into known result storage can use fields/stack/sret; taking an independent copy follows owner rules. `factory = () => lazy (1 2)` can return a tiny value | An escaping result alone does not force a heap allocation. Report frame size and any nontrivial copy, detach or move effects |
| Erased or escaping frame | Storing unlike unknown-size generators behind an interface or callback can require a boxed environment and indirect resume/drop. A bounded tagged union or caller-provided storage can avoid the box | Account for allocation where storage is acquired. A suspended child allocated on second advance charges that advance, even if its parent was allocation-free |
| Recursive delegation | `inorder(child)...` can require a stack of active records proportional to depth. The caller's transient call stack does not survive an advance. A proven maximum or tail delegation with no pending duties may use fixed storage or frame reuse | Unknown depth requires growable or explicitly supplied storage. Deep destruction should walk that stack iteratively where possible. A chain of frames must carry pending cleanup and never release an ancestor prematurely |
| Eager arguments or groups | `sum_all(g...)` may materialize an unbounded rest array; `lazy { many(xs) }` may hold an eager variable-width row. A proven two-field call can initialize typed slots directly | Count collector allocation, pending owned fields and cleanup of partially initialized prefixes. Known count alone does not eliminate effects of evaluating its fields |

Under `$no_hidden_costs` check the selected lowering in the same plan used for emission. For example, a hot loop that receives a sum from two scalar locals can pass a no-allocation gate. An unbounded recursive cursor boxed on demand fails that gate, with the diagnostic pointing to the recursive spread. A returned cursor that would need an implicit costly copy or COW detach fails at that operation. Possible fixes depend on the witness: keep the concrete type, fuse the consuming loop, transfer at last use, preacquire bounded workspace, or change the result to an explicit materialization in an allocating scope. `.copy()` can make a copy explicit but cannot satisfy a `no allocates` contract if it allocates. Under `$explicit_allocation_failure` report allocation refusal at the actual construction, growth or copy phase and preserve cleanup of the initialized prefix. Strict checking cannot rely on an optimization that might run later. For `lazy today`, capture the existing callable's time-zone semantics at construction; resource caps and cancellation apply at execution under their usual rules.

**Bound the checker.** Reuse the existing sink, type, match, owner, effects and length-fact indexes. Give each lazy body/instance a summary distinct from its factory's ordinary result. Represent shape expressions as shared nodes for empty, positional vector, concatenation, whole-row choice and repetition; keep transfer boundaries in a separate sequence of step summaries. For `if flag (1 "x") else ("y" 2)` retain its two alternatives at one choice node. Independent choices can form exponentially many concrete products; never distribute concatenation over every choice. Check a fixed signature as a sequence of K+1 parameter positions (plus rest or rejection). Memoize reachable positions per shape node, join alternatives there, and check slot types before advancing each position. A rest loop checks a stable single state; a repetition joins reachable positions to a fixed point, including overflow. Keep a separate “may exceed K” state so rejecting a too-wide path cannot erase it.

For a body with N IR entries, E control edges and W explicit field/type occurrences, structural summary construction is O(N+E+W) expected with indexed interning. For a fixed call with K finite positions, checking a bounded choice/repetition graph as an epsilon-NFA against the position automaton visits at most O((N+E+W)(K+2)) state/edge pairs for the **expanded public summary graph** and known slot subtyping. Count subtype/refinement/overload work separately. Share the checked result per summary, signature and relevant length facts. For compact counted loops or shared concatenations, guard expansion and product construction with a deterministic proof-work cap; consume symbolic length facts directly where possible. Example: a million repetitions of a fixed row need one size multiplication for an arity rejection. On saturation retain the runtime shape and widen the proof to a sound element/length upper bound. A total rest collector or catch-all still works. A fixed consumer whose fit cannot be proved gets a diagnostic with the first uncertain region and a match, explicit tuple or length-guard alternative. Never truncate a possible case to obtain acceptance.

A loop or `.next` usually needs only the step summary, a rest sink often only the element bound, a fixed spread the remaining-position summary. Check match coverage per demanded alternative using the existing conservative coverage rules. Do not propagate unrelated branch-predicate correlations across arbitrary calls. For example, an opaque `predicate(i)` in a filter loses exact cardinality. Recursive summary cycles use bounded widening at the instance boundary; require a result annotation if a productive type cannot be inferred. Frame liveness uses the existing local CFG and sparse use lists. With V potentially live values, ordinary backward bitset liveness costs one V-bit join per processed edge per iteration; it is **not** globally linear in N. Demand it for bodies with suspensions and use existing bounded ownership proofs. On budget exhaustion use a larger sound frame or reject an unproved loan. Ordinary code with no generator or dynamic-pack obligation takes the existing fast path with no extra whole-program pass.

**Implementation gates, still unmeasured.** On the flagship compile panel compare single-worker instruction counts on the same host, including a case with no generators. On the quiet benchmark host label fresh compile throughput and verify the existing 200k lines/s minimum and 250k goal. Compare a hand-written loop with a fused numeric pipeline using fixed-width proven arithmetic, inspecting allocation counts, indirect calls and generated code. Compare an unfused cursor and an eager-rest sink separately. Exercise many nested choices, a huge symbolic count and recursive delegation to measure proof saturation and live frame storage. Confirm strict rejection before claiming zero overhead. Runtime success alone cannot establish the compiler-cost bound.

## 11. Other directions and questions for David

| Direction | Where it serves Dewy well | Where the proposed design differs |
|---|---|---|
| Python generators | Explicit suspension sites make the timing of a slow operation easy to see. Delegation forwards child control, including close, and supports a delegated return result | Dewy's `lazy { head tail... }` reuses multi-expression flow and needs no special function declaration, send/throw-into or final-result channel. Python also has standalone generator expressions. [Delegation specification](https://peps.python.org/pep-0380/) |
| JavaScript generators | A step has an explicit done discriminator. Bidirectional resumption and delegated iteration are useful for conversations with a producer | `loop row in g` asks for output only. `return` into a suspended computation and dynamic protocol methods would enlarge the ownership and effects contract. [Generator and iterator objects](https://tc39.es/ecma262/multipage/control-abstraction-objects.html#sec-generator-objects) |
| C# iterators | Separate enumerable and enumerator roles make obtaining a fresh traversal clear. Enumerator disposal composes with resource cleanup on early loop exit | Dewy uses a callable factory for restart and value/place iteration for cursor choice. Local `lazy (1 2)` also works where no dedicated iterator method is needed. [C# language specification](https://ecma-international.org/publications-and-standards/standards/ecma-334/) |
| Rust iterators, closures and proposed gen blocks | A typed item and static combinators suit optimized map/filter chains. The gen-block proposal lets a loop express a custom state machine directly | Explicit tuple items are a good A alternative. In B `paint(row)` consumes a pack directly. A Dewy eager helper still runs to completion, and copying its cursor must respect Dewy value semantics. [Iterator contract](https://doc.rust-lang.org/std/iter/trait.Iterator.html) · [Gen-block proposal](https://rust-lang.github.io/rfcs/3513-gen-blocks.html) |
| Kotlin sequences | The sequence builder supports local mutable state and incremental delegation using a restricted suspension scope | Stopping before completion can leave a builder's finally block unexecuted. A Dewy owner with a registered `defer` must run that cleanup when its traversal is destroyed. [Sequence builder and early termination](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.sequences/sequence.html) |
| Lua and stackful coroutines | A deeply nested helper can suspend its caller chain, and a resume can exchange several values. Useful for interactive control transfer | Retaining arbitrary call stacks would change `lazy { eager_fn() }`, make C/foreign boundaries harder and obscure storage. Dewy's recursive delegation retains explicit active children only. [Coroutine semantics](https://www.lua.org/manual/5.4/manual.html#2.6) |
| Haskell-style non-strict evaluation | Infinite lists and compositional demand work naturally for pure computations; sharing can avoid repeated evaluation | Making ordinary `let p = read_pair()` lazy would overturn Dewy's eager effect order. Shared thunks also change retention and do not provide an exclusive resumable I/O cursor. [Expressions and strictness](https://www.haskell.org/onlinereport/haskell2010/haskellch3.html#x8-420003.1) |
| Library adapters only | Existing `next` records and `map`/`filter` can implement common pipelines. A hand-written traversal is a useful cost baseline and can expose domain-specific operations such as skipping children | An adapter author implementing inorder traversal or a token stream must maintain a program counter, active-child stack, partial initialization and cleanup by hand. The compiler already knows those control points for `lazy`. Keep specialized iterators for steerable traversal |

### Decisions requested

Examples below are minimal witnesses to each choice. Decisions marked source-sensitive are reversible during design; changing them after adoption would alter observable programs.

| Choice | Witness | Recommendation, what it unlocks, and reversibility |
|---|---|---|
| Unit of advance and boundary grammar | `lazy (1 (2 3) 4)`; `lazy x in xs ((x x))` | B with delimited streaming bodies and complete expression contributions. Supports rows as positional results. Source-sensitive: changes steps, effect order and zip |
| Dynamic packs at bindings and calls | `let p = if c (1 2) else (1 2 3)`; `total(p)` | Accept when the one chosen signature covers all shapes. Lift the existing conservative count and homogeneous-result restrictions, retain correlations, require a match for distinct overloads. Broadening acceptance is reversible before release |
| Type and length vocabulary | `generator<(int string) length=2 failure=ReadFailed>` | Use the proposed type, initial step count and terminal failure bound. Enables signatures and precise phase diagnostics. Names can change before release; the unit of length is source-sensitive |
| Direct step result | `let g = lazy none`, then `g.next` | Return an existing positional container, end sentinel or terminal failure. Enables manual steps even for optional and error data. A named variant is another ergonomic choice. Reversible before public iterator APIs depend on it |
| Copy and early break | `loop x in @g { break }` then `g.next` | Resume the retained cursor. Copy only structurally copyable frames; a possible one-off cleanup makes a cursor move-only. Supports partial consumers and exactly-once finalization. Source-sensitive |
| Fallible spread and cancellation | `[(g... or_throw)]`; `loop x in g or_throw use(x)` | Require an explicit suffix for fallible eager drains; forward delegated failure; adopt D44's quiet plain source cancellation only on the pure cancellation case. Protects fixed calls and prevents accidental partial arrays. Reversible before release, coordinated with D40/D42/D44 |
| Lending | `lazy { loop @x in values { @x } }` | Reject place outputs initially; allow owned snapshots and direct mutable loops. A future turn-scoped loan can extend acceptance after a nonescape proof. Additive and reversible during design |
| D40 Q5 | `defer slot.publish(delivered complete)` inside `lazy` | Keep the checked one-off action. It sees private progress on every owning exit. Use an owner for reusable or fallible finalization. Reversible before release. D40 Q2 block-end and Q6 marked local destruction remain separate decisions |
| Shorthand and spelling approval | `lazy x in xs x^2` | Adopt the loop shorthand with ordinary loop grammar alongside `lazy <expr>`. It removes a wrapper on the common transformation. Reversible as syntax before release |

**Name inventory for cold reading.** The language candidates are `lazy` and `generator`; `length` is reused with a new unit on generators, and `failure` is a proposed named type argument. New combinations of existing spellings are listed in §2 and §7, including pack shapes in the generator type, the new generator result convention on `.next`, pack-valued loop bindings and propagation on a drained spread. `$done` is an arbitrary user label applying the established label feature; `next`, `...`, `@`, `or_throw`, `defer` and `$__drop__` are existing names/operators. The illustrative `on_finish` adapter would need separate approval only if standardized. Local helpers, field names, error types and the word “pack” in prose introduce no prelude names. Cold-reading and dogfooding sign-off belong to a later round.

## 12. Corrections and readings of the sketch

The sketch's indented bodies are ordinary expressions following their headers. Putting them on a different line changes none of these examples' control structure. Delimit a body when it contains several entries. The special line/row rules of n-D array literals remain those of array syntax. These are the substantive corrections.

| Sketch section | Correction or more precise example |
|---|---|
| 1–3, eager dynamic arity | The existing multi-expression design accepts fixed pack bindings but restricts a varying count at a binding or fixed call. `let p = if c (1 2) else (3 4 5)` is a requested extension. Use the two arity arms of `match p` or a typed rest function; two overloads do not imply runtime dispatch. In `add(abc)`, three positions overflow the signature **and** `"hello"` does not fit its second integer parameter |
| 2, generator spread | `let g = lazy (1 2)` then `add(g...)` is valid for a fresh, infallible traversal with exactly those two remaining integers. For a retained cursor already stepped once, `add(g...)` cannot use the initial length as proof. A fallible input also needs a terminal policy |
| 4, forwarding rest | `forward = (...args) => add(args...)` promises a variable number of arguments to a fixed binary callee. `forward(10 20)` may specialize with length two but does not justify a general contract. Use `forward = (a:int b:int) => add(a b)` for the fixed call, or `forward = (...args:int) => total(args...)` for genuine variadic forwarding. `(head ...rest) = p` is another existing collecting pattern |
| 5–7, eager loops and binding | `[loop i in [0..5) i^2]` is the eager squares array. A loop alone expresses its values to its enclosing sink. In a written `:>void` context those values need discarding. The variable-length eager `let xs = (… loop …)` in §7 is an eager pack under this extension and may allocate; write `lazy { … }` to stream |
| 8–10, length and state | `generator<int length=n>` applies if the fresh traversal has a proof of n normal steps, including n nonnegative. An n-fold *eager pack type* would lose the cursor, so it cannot substitute. `powers_of_two` starts with 2 because it multiplies first. `lazy { let n:int = 0 loop true { n n += 1 } }` uses private, arbitrary-precision state; indefinite iteration does not guarantee constant byte storage as n grows |
| 11–15, pipelines | Use `map(squares(10) @double)` or the direct `lazy x in squares(10) 2*x` for singleton integers. For a stream of pairs a call `f(x)` must accept both arguments; `map`/filter generics must preserve the callback's effects and ownership. `chain = (a b) => lazy { a... b... }` delegates with early disposal. `flatmap = (xs f) => lazy x in xs f(x)...` delegates each result. `inner()` in an output entry produces one cursor; `inner()...` forwards steps. The tree API in §14 is illustrative: read a possibly effectful child accessor once, e.g. `let left = node.left`, then `if left isnt? none inorder(left)...` |
| 16, zipped inputs | `[a b]` is one explicit container; it can be a tuple in a suitable typed context. `zip_rows` in §5 delivers a two-field pack instead. Ordinary combined headers exist; combined generator iteration requires the advancement and possible unmatched-read rule in §5 |
| 17–18, helper timing | In `lazy { 0 eager_fn() 3 }` the “work” print precedes the **whole** pair step. In `lazy { 0 lazy_fn()... 3 }` the 1 has already been observed before “work” on the following advance. If the consumer stops at 1 in the latter, “work” never prints |
| 19–21, scope and exit | The written `$done` on its own before `lazy` already uses Dewy's label syntax. `break $done` completes the labeled lazy computation. With just one loop, `lazy x in source { if x =? stop { break } x }` can use the nearest loop instead. Ordinary `return` in the factory can return a generator; a direct `return 42` inside its body cannot return from that factory. Breaking a borrowed traversal after B leaves C pending; destroying it skips C |
| 22–23, heterogeneous steps | `lazy (42 "hello" true)` gives three singleton steps; a consumer accepting only integers is ill-typed. `lazy { if c ((1 2)) else ((3 4 5)) }` gives **one** row of the selected arity. The singly grouped arms in §23 are streaming arm bodies under §2. Use a named eager pack as the arm's single entry for the same one-row result |
| 24, producing places | Use `loop @x in values { … }` for a mutable element binding. `in @values` selects live traversal of the source place; it does not grant permission to export element places. For a safe external transform use `lazy x in values transform(x)`. A retained `@x` could alias invalid storage after resume |
| 25, nested grouping | `lazy (1 (2 3) 4)` has exactly three successful advances under B. A caller wanting four scalar turns writes `lazy (1 2 3 4)`. `[g...]` has the same four scalar entries in either case and cannot distinguish their handoff timing |

### Observable acceptance cases

These are discriminating tests for an eventual implementation. “End” and “step” in this table describe outcomes; they are not proposed identifiers.

| Program or change | Required result |
|---|---|
| `let k = 8` followed by `let g = lazy (let k = 3 k)` | Outer k remains 8. First step contains 3 |
| `lazy { if false 1 none }` | A successful singleton containing none, then end. No empty step |
| `pair = () => (1 2)`, `let p = pair()`, substitute either for `(1 2)` in `lazy { 0 (1 2) 3 }` | Same three step shapes. Evaluating p's initializer retains its ordinary earlier timing |
| Change `lazy ((1 fail_now() or_throw))` to `lazy (1 fail_now() or_throw)` | First version fails without producing 1. Second produces 1 even if never resumed |
| `let g = lazy (1 2)`; step in place once, copy g, advance both | Each next success contains 2. No rewind, interference or extra evaluation of the first step |
| `loop row in @g { break }` on a live move-only journal session | Caller still owns the cursor and may resume it. Copying it while retaining the original fails static ownership checking |
| `loop a in @left and b in @right use(a b)` with empty right | At most one unmatched left step for this turn; no body call. Left's already-performed effects and position remain observable |
| `add((lazy { if c 1 else (2 3) })...)` | Reject even though one branch supplies exactly two values; report the one-argument path |
| `lazy { bad_input() }` versus `lazy { bad_input() or_throw }` | In the first a returned exception can be a payload; in the second it terminates the cursor. A second advance after terminal failure reports end |
| Dispose a suspended delegate whose close fails on the way out of a failing consumer | Both failures survive under D40/D42; neither the inactive tail nor a second cleanup runs |
| Cancel during the journal example's upstream wait, then cancel before first demand in a different run | Started slot records its delivered prefix exactly once. Unstarted body registers nothing. Any already-acquired captures still release |
| Compile the same pipeline fused and as a concrete non-fused cursor | Identical outputs, effects, stopped positions, terminal outcomes and cleanup order, including a consumer that takes only one step |

### Dewy sources used for the contract

- Eager multi-results, substitution, unpacking and the static-count restriction this proposal extends. [Multi-expressions](../../../../docs/design/multi_expressions.md) · [Binding decisions](../../../../docs/design/decisions.md)
- Existing block and call conventions, iterator value/place distinction, labels and metatag placement. [Language guide, multiple results](../../../../docs/LANGUAGE.md:275) · [Iterator protocol](../../../../docs/LANGUAGE.md:5015) · [Labels](../../../../docs/LANGUAGE.md:5211) · [Construct prefixes](../../../../docs/LANGUAGE.md:5794)
- Pattern coverage, lifecycle, effect summaries and the compile-speed goal. [Match](../../../../docs/design/match.md) · [Ownership](../../../../docs/design/ownership.md) · [Effects](../../../../docs/design/effects.md) · [Language goals](../../../../docs/GOALS.md)
- Earlier notes considered automatically making an ordinary block a generator, a final return payload and explicit yield. The present sketch chooses explicit lazy construction and keeps ordinary functions eager. [Discussion notes](../../../../resources/discussion_points.md:315) · [Current sketch](sketch.md)
- Open proposals used conditionally for cleanup timing and failure composition. [D40](../../../../docs/design/open_decisions.md:490) · [Cleanup round 7](../../../../docs/design/proposals/cleanup/round7.md) · [D42 round 8](../../../../docs/design/proposals/errors/combined/round8.md) · [D44 round 6](../../../../docs/design/proposals/cancellation/round6.md)
