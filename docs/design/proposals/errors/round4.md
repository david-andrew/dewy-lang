# Combining failures, round 4

## Combine two

```dewy
import p"@lib/std/errors.dewy" as errors
ReadFailed:type = type of error & [message:string]
CloseFailed:type = type of error & [message:string]
combine = (read:ReadFailed close:CloseFailed):>errors.ErrorGroup => {
    return read & close
}
```

## Split them back out

```dewy
import p"@lib/std/errors.dewy" as errors
split_back = (both:errors.ErrorGroup) => {
    return both.errors                  # exact immediate children, in insertion order
}
show_parts = (both:errors.ErrorGroup):>void => {
    loop part in split_back(both) { errors.report(part) }
}
```

## Accumulate in a loop

```dewy
import p"@lib/std/errors.dewy" as errors
validate_many = (texts:array<string>) => {
    let failed:array<exception> = []
    loop text in texts {
        let n = to_int(text)
        if n is? exception failed.push(n)
    }
    errors.join(failed...)              # void for none, original for one, group for many
}
fold_more = (first:exception rest:array<exception>) => {
    let acc:exception = first           # a nonempty stream has an ordinary seed
    loop e in rest { acc &= e }
    return acc                         # no deduplication; nested group boundaries retained
}
```

## Where each came from

```dewy
import p"@lib/std/errors.dewy" as errors
show_origins = (failure:exception):>void => {
    loop leaf in errors.leaves(failure) {
        let site = leaf.$origin
        if site is? none printl("origin unavailable")
        else printl("{site.file}:{site.line}:{site.column} in {site.function}")
    }
}
```

## Cleanup pairing

```dewy
import p"@lib/std/errors.dewy" as errors
WriteFailed:type = type of error
CloseFailed:type = type of error
Output:type = type of any & [
    $__drop__ = ():>CloseFailed => CloseFailed
]
save = () => {
    let output = Output[]
    return WriteFailed
}                                      # returns WriteFailed & CloseFailed
```

**Recommendation: use `a & b` for two failure values, with one `ErrorGroup` result type; retain `errors.join` for a variable-length collection. Do not claim that the result is `A & B`.** A genuinely intersection-typed candidate is specified and tested against the contracts below. It works for a restricted set of compatible payloads; it is not a total combiner for arbitrary failures. The operator itself is useful without that return-type promise. This is a deliberate departure from the requested *intersection return type*, not an attempt to rename a group and call it an intersection. If that type promise is indispensable, this proposal recommends join for general failures rather than silently weakening intersection.

This new file supersedes rounds 1–3 as the recommendation. Historical files and the independent review remain unchanged. Scope: error composition, inspection/recovery, and v1 diagnostics. Read-only checkout; all writes in this task directory; no commits or agents. Budget: about 90 minutes. No implementation, cleanup-timing redesign, or new concurrency surface.

## 1. Correcting the argument about intersection

The review's M2 is correct. A runtime value can retain `[a,b,a]` while its public type normalizes to `A & B`; `A & A = A` does **not** erase the second occurrence. Ordering and multiplicity are facts about the value. The earlier summary's impossibility argument is withdrawn.

The existing type contract is stronger than containment, though. `docs/LANGUAGE.md:4155–4161` says a shared record field has the **intersection** of the two field types; incompatible shared field types make the declaration an error. `resources/discussion_points.md:1225–1303` already gives value-level `&` and `&=` for callable conjunction/overloading. Its `:4612–4635` distinguishes non-generative intersection from minting identity. These were reread, and `/usr/bin/grep` was used before adding the provisional recovery name. The spelling `&` is an excellent candidate; it does not by itself decide which value/type contract errors should use.

### A concrete candidate whose return type really is `A & B`

Call this candidate I. It is a proposed extension of nominal intersections, not currently implemented Dewy.

1. **Storage and type.** `a:A & b:B` in value position constructs an immutable ordered carrier of the exact input occurrences, typed `A & B`. A third occurrence is retained even if type normalization removes a duplicate factor. Binary grouping records the binary tree; a leaf walk gives left-to-right order. Passing the value through A, B or exception storage preserves that hidden carrier. There is no projection merely because a parameter has the wider A type.
2. **Visible fields.** The carrier has a canonical record view. For a shared field, take the leftmost value, but construction is legal only when that value and the resulting record are proven to satisfy **all** intersected field constraints/invariants. Unique fields come from their respective side. Thus two string `message` fields give the first message in `(a & b).message`; the second remains in the exact parts. This is a specified projection policy, not a loss of storage. A more elaborate policy could choose the first admissible field value; it still cannot inhabit an empty intersection.
3. **Nominal tests and ordinary handlers.** `g is? A` and `g is? B` are true. A `match` takes the first matching arm once, binding the entire carrier; an A parameter sees the canonical fields while retaining the other occurrences. By today's selected-handler rule, `g ??<A> fallback` replaces the entire value, including B. `or_throw<A>` forwards the entire value. Neither operation projects only A. If the application wants only one occurrence, it explicitly splits first. This is coherent ordinary subtyping, but a poor default for *independent* failures: adding B to an existing A result can make an old A fallback silently discard B.
4. **Cancellation.** `Canceled & CloseFailed` satisfies Canceled, CloseFailed and therefore error. A cached carrying flag can still make bare `??`, typed `??` without an explicit Canceled alternative, and collectors forward the entire value. **D4 Q1 can be preserved; intersection typing does not make that impossible.** `or_throw<Canceled>` and `is? Canceled` then agree, an important advantage over the group design. But `is? error` is also true, so the existing ordinary-error arm/if can handle cancellation where bare Canceled would not match. Making that test false would violate the stated intersection. Accepting it is an explicit safety/compatibility change, not a missing flag implementation.
5. **Splitting.** A uniform library query, candidate-only `errors.parts(g)`, returns the exact immediate original values and their origins. A leaf walk retains duplicates and context. This query is needed because adding an ordinary `.errors` field to an A & B could collide with an existing field of either operand. Narrowing to A is not a way to select one of several A occurrences.
6. **Accumulating.** With a first failure, `let acc:exception = first; loop e in rest { acc &= e }` works and retains the carrier through erasure. No runtime multiplicity needs to enter the type. The type alone is not an inventory of children. A zero-length stream has no failure seed; `none` is a real exception, not an identity. Use an array plus a zero/one/many fold. No new neutral failure or special `void & e` is needed.

Candidate I is fully usable for *compatible* payloads under those rules. It is not rejected for its ability to store occurrences. These are the counterexamples it must answer:

```dewy
ReadMessage:type = type of error & [message:'read failed']
CloseMessage:type = type of error & [message:'close failed']
# Candidate I: invalid result type, even though both originals are stored perfectly.
combine_refined = (a:ReadMessage b:CloseMessage):>ReadMessage & CloseMessage => {
    return a & b
}
```

```dewy
CodeNumber:type = type of error & [code:int]
CodeText:type = type of error & [code:string]
# Candidate I: no canonical code can be both an integer and a string.
combine_codes = (a:CodeNumber b:CodeText):>CodeNumber & CodeText => {
    return a & b
}
```

These are labeled negative candidate programs, not proposed v1 code. Shared `message:string` with unequal values is **not** this impossibility: left projection is legal there. Disjoint singleton message types and int/string really are incompatible under Dewy's existing record-intersection rule. Automatic cleanup has to preserve both even in those cases; turning an attempted merge into another error, or requiring a different operator only for those payload types, fails that requirement.

### Could a different intersection interpretation solve it?

A faceted object could keep separate A.message and B.message projections, making an A view return one and a B view another. That is a viable larger language design. It changes the current single shared-field intersection contract, needs an unambiguous unqualified `.message` rule, and must define parameter conversion, writes and narrowing without silently losing the other facets. A contextual projection cannot be described as the current value-preserving narrowing rule without explaining that change. Returning both messages changes a scalar field into a multi-expression; it likewise is not the existing A & B contract.

A partial-handler design can also preserve B when `??<A>` handles A, or give match arms subgroup/remainder behavior. That is a viable *new handling semantics*, similar in purpose to except*. It must work after the carrier was widened to A, not just when the compiler still sees `A & B`. An A-typed function could then encounter and propagate arbitrary hidden remainder kinds, widening result contracts or requiring a separate aggregate distinction. The operator spelling alone does not settle that choice. Round 4 instead keeps normal nominal matching and offers an ordinary-library recovery helper.

No claim is made that faceted intersections are impossible. They are not the existing construct unchanged, and choosing them would redesign records and handlers beyond this error-combination slice. The negative examples above also cannot be “fixed” by choosing another order of the same incompatible field values.

### Comparison and choice

| Question | I: true `A & B` | G: `a & b` returning ErrorGroup | J: `errors.join(a b)` returning ErrorGroup |
|---|---|---|---|
| Exact order, duplicates, origins | yes | yes | yes |
| Different string messages | left canonical projection; exact parts retained | group's own summary; exact parts retained | same as G |
| Incompatible shared refinements/types | rejected unless intersection semantics change | supported | supported |
| Nominal A/B handlers | match the whole value; may discard siblings | do not match group | do not match group |
| is? Canceled vs selected forwarding | can agree, but is? error also matches | explicit carrying exception remains | same as G |
| General cleanup pair | not total | total under allocation assumptions | same as G |
| Empty/dynamic collection | needs a fold | join is the companion fold | one call already covers it |
| Surface cost | terse, substantial field/handler decisions | terse, honest operator-result typing to teach | explicit function, little punctuation surprise |

**Choose G, plus J for collections.** This takes David's existing operator where it works, rather than rejecting the syntax along with the strict type promise. It is a standard type-directed operation, as value `&` already has operations for integers, sets and callables. It does not alter type-position `A & B`, scalar masks, set intersection or callable composition. The two spellings have distinct everyday jobs: binary composition and zero/one/many folding, not two competing accumulator classes. The cost of explaining why `a:A & b:B` returns ErrorGroup rather than A & B is real and receives a discoverability deduction.

## 2. One group type, with an explicit compatibility cost

`errors.ErrorGroup` is a single nominal child of **exception**, outside **error**. Remove ExceptionGroup, rather than rename the failed distinction. Sentence for users: **“ErrorGroup holds several failures, possibly including cancellation; inspect it as an exception.”** Both all-ordinary and cancellation-carrying groups have this same outer kind.

This means an all-ordinary group no longer matches `is? error`, an `error` match arm, `or_throw<error>`, or an `error` parameter. This is the real cost of one safe family. Widen a reporting parameter to exception, explicitly handle ErrorGroup, or use plain `or_throw`. Do not silently widen the meaning of error. Programs 02–04 and 09 are revised accordingly. The common `or_throw`/`??` flow still works, and no reader must distinguish two almost-identical class names. This is preferable to preserving an all-error shortcut at the price demonstrated by the cold read.

For failure operands, `a & b` evaluates each operand exactly once, left to right, and constructs ErrorGroup with the two immediate children. It is eager. In particular, `f() & g()` is not a short-circuiting sequence: g runs even if f returns cancellation. The intended idiom combines failures already obtained. Fail-fast operations still use `or_throw` between calls. Ordinary non-exception alternatives cannot participate accidentally; narrow a `T | exception` first. No exception arithmetic-forwarding rule discards the second operand here. Error combination is the standard operation for exception operands, not a user-overridable way to change cancellation meaning.

`errors.join(...failures:exception)` evaluates its arguments once and gives void for zero, the unchanged original for one, and one ErrorGroup for two or more. It retains nested groups. `a & b` and `join(a b)` have the same value behavior. A split or recovery can retain a unary group to preserve its context boundary, even though neither constructor creates one. A group never has zero children. `.errors` returns its immediate parts under the existing ownership/copy rules; it is not a mutable path into the group. Payloads are not merged.

The binary expression's type is always ErrorGroup in the default allocation lane. For an unknown-length spread of element type E, join returns `void | E | ErrorGroup`; `E=exception` already includes ErrorGroup, so that simplifies to `void | exception`. A known zero/one count specializes to void/E, and a known count of at least two specializes to ErrorGroup. In particular, `array<error>` does not make the group an error: its fold result includes ErrorGroup separately. `partition_failures` classifies the exception family, so this group does not become a successful item.

Value combination is **neither commutative nor idempotent**: `a & b` has the opposite order from `b & a`, and `a & a` has two occurrences. Binary parentheses preserve different tree boundaries, although either association visits the same ordered leaves. Type-position intersection keeps its algebraic laws; those laws are not imposed on the value operation. This is another fact the operator's cold read must test.

`(a & b).message` is the group's own generic message, “multiple failures”; it is neither input's message. The reporter prints each child. Direct child payload access needs ordinary narrowing of that child. This summary cannot conflict with an operand's refined message because the result type is ErrorGroup, not that operand's type.

`acc &= e` means the usual once-evaluated place update `acc = acc & e`. It requires a nonempty exception seed and a storage type that admits ErrorGroup, normally exception. `let acc:FileError = first; acc &= close_error` is rejected: the new group does not fit FileError. It creates O(n) nodes over n additions, not a flat-array copy on every append. Prefer array.push plus one join for an initially empty or flat large batch; it uses O(n) storage and amortized constant-time push. Neither none nor a successful value is silently dropped by join.

## 3. Matching, cancellation and splitting

Ordinary `is?` and `match` remain outer-kind tests. An ErrorGroup containing FileError is not FileError, error or Canceled; it is ErrorGroup and exception. All its children remain accessible in order. A match on ErrorGroup is an explicit decision to inspect or handle that whole group. An ordinary `??<FileError>` does not consume a group or any of its children. On a group-only static operand it gets the existing impossible-selector error, with a note offering recovery or leaf inspection; on a union containing bare FileError it handles only that alternative.

| Operation on ErrorGroup | No Canceled inside | Canceled anywhere inside |
|---|---|---|
| bare `or_throw` | forward whole | forward whole |
| `or_throw<error>` | retain whole | retain whole |
| `or_throw<Canceled>` | retain whole, flag proved clear | forward whole |
| bare `?? fallback`, including control-flow fallbacks | default whole | forward whole from enclosing function |
| `??<FileError> fallback` when selector is otherwise legal | retain whole | forward whole |
| `??<ErrorGroup> fallback` | default whole | forward whole |
| `??<Canceled> fallback` | retain whole | forward whole |
| `??<Canceled | ErrorGroup> fallback` | default whole | deliberately default whole |
| collector | retain as an element | forward whole |

A broad exception selector is not an explicit acknowledgment of Canceled. A carrying flag is the OR of child flags; context, erasure and copies preserve it. `or_throw<Canceled>` is the one descendant-aware propagation selector. Its continuing path clears the internal carrying fact, so a following `??` passes `$explicit_cancellation`. Naming Canceled is permitted for a group-only operand precisely because it can carry cancellation. Neither exception changes `is?` or turns arbitrary payload fields into cancellation carriers.

This leaves a real conceptual cost: `is? Canceled` can be false when `or_throw<Canceled>` forwards. It is not graded away. Program 08 now shows live ordinary-group and canceled-group paths, explicit default acknowledgment, and the continuing-flow refinement. Removing the second group type and using `&` for deliberate packaging removes two additional traps from its ordinary path; it does not claim to remove this last distinction.

`.errors` returns exact immediate children. `errors.leaves(failure)` traverses left to right, with inherited diagnostic context on each leaf, without changing its nominal kind or origin. No implicit deduplication. A direct-parts reconstruction deliberately leaves the old parent's wrapper context behind; leaf traversal is the way to retain diagnostic ancestry on extracted values. Inherited context retains frame identity: re-embedding a leaf beneath the same ancestor does not repeat that frame, while identical text from two separate context calls remains two frames.

Keep `errors.split<E>` as an **advanced, deferrable** operation with the round-3 matched/rest subtree contract. It is not required for two-part extraction or ordinary selective repair. Its remainder is still ordinary data and can be mistakenly discarded. Do not sell it as the safe default when a helper can keep the remainder automatically. Cause edges and stack traces are not part of v1.

## 4. M1 fixed: recovery does not begin after cancellation wins

The minimal correction to the old algorithm is `errors.split<MissingAsset>(failure or_throw<Canceled>)`. That is necessary for incoming cancellation, but it does not address the amount of recovery code, nor task cancellation that arrives before the next repair. Program 09 instead uses one ordinary-library operation:

```dewy
import p"@lib/std/errors.dewy" as errors
MissingAsset:type = type of error & [path:Path message:string]
regenerate = (missing:MissingAsset) => {
    missing.path.write_text("generated placeholder") or_throw;
}
recover_missing = (failure:exception) => {
    return errors.recover<MissingAsset>(failure @regenerate)
}
```

`recover` is a **new provisional name, not in the completed r22 cold read**. The helper is essential to the proposed v1 ergonomics, but its spelling needs a fresh cold read before a naming decision. It is an ordinary function taking a function handle, not callback-shaped control flow: return/break/or_throw inside regenerate belong to regenerate as usual.

The contract is exact:

1. If the incoming value carries Canceled, return **that original value unchanged**, before splitting, allocating reconstruction nodes, consulting callbacks, or starting any repair. This includes transported cancellation when the current task itself is not canceled. Erased exception storage must preserve the flag. The guard applies under `$explicit_cancellation` too.
2. E selects **ordinary error leaves**, not group nodes or Canceled. The callback accepts E and returns `void | exception`. A successful callback removes that leaf. An exception result replaces its position with a group of the original leaf and the repair failure; other leaves stay in their original order and context. A returned Canceled or group carrying it stops further callbacks. An ordinary repair failure does not stop independent repairs.
3. Task cancellation is checked on entry, at each repair's start, and before reporting success/returning the final result. Start admission and cancellation have a defined ordering: if cancellation wins before that start, the callback is not entered. Keep every as-yet-unattempted leaf, plus the new cancellation occurrence. Stop scanning for work, but bookkeeping may finish to retain the value. A callback whose start wins may already be executing when cancellation arrives; it must observe the normal cancellation points, including the write helper. This is cooperative cancellation, **not** a promise to roll back a write or interrupt arbitrary instructions at the wall-clock instant of a signal.
4. If cancellation arrives during a successful callback, its completed repair stays successful; preserve the unattempted/unmatched failures and append cancellation. If the callback fails as cancellation also arrives, keep the original, the repair failure, and cancellation unless the repair result already carries it. A final check prevents the last successful callback from turning a canceled task into void success. The implementation must make the start/check ordering real; a loose “check much earlier, then do arbitrary setup” is insufficient.
5. The helper owns the remainder and returns it automatically. No parts.rest binding, nested leaf loops or stop flag in application code. No matches returns the original (unless task cancellation adds a failure); all successful matches and no unmatched leaves gives void. Contextual unary branches survive pruning where necessary.
6. For v1 the selected E payload must support an ordinary independent copy to the callback under Dewy's existing ownership rules. This permits retaining the original on failed repair. Selecting a move-only error is diagnosed; use explicit consuming inspection/recovery until a borrowing callback contract is designed. Unmatched owning payloads remain owned once by the retained tree; they are never duplicated. This is an honest scope limit, not a new Copy keyword or a promise of unrestricted owning recovery.

The helper's conceptual walk is iterative: return early on incoming carry; then visit ordinary matched leaves in order, admit each start, invoke repair, and reconstruct only changed paths. It preserves groups/context and stores a stop state internally. O(nodes + callback work + retained metadata), with the same finite-memory construction gate as any group reconstruction. It may require the cancellation-check integration from D41; the public name `check_cancel()` is not renamed or settled by this proposal. Tests model the admission ordering, not a real scheduler or side-effect atomicity.

## 5. Smaller diagnostics, including none's cost

V1 keeps `with_context(failure message)`, `$origin`, SourceLocation and the full-tree reporter with `locations=true`. Context is transparent and persistent: the original kind and payload remain, adding text to a copy does not mutate aliases, and the context call site is retained privately. The reporter prints private context frames and group children without requiring public `$context` or causal-edge APIs. Program 10 now demonstrates layered context, **not** domain-error translation. That original optional requirement is deferred explicitly, not claimed implemented by renaming it.

Record an origin token at construction of an **error or a non-none exception**, including a unit Canceled. **none is exempt:** it remains an absence marker with no per-occurrence token, and its `$origin` is none. A context operation may annotate an absence explicitly, with its own context site, without pretending to know the original absence's creation. This revises the previous blanket “every exception” rule.

Copies/forwarding keep the original site; a reused constant keeps its declaration site. Groups have their combination site's origin and retain each child's origin. Unknown foreign/imported origins stay none. SourceLocation has file, line, column and function; paths are build-root-relative where known, lines/Unicode-scalar columns are one-based. Display is requested separately with locations=true.

Exempting none prevents this feature alone from requiring a token on every ordinary `T?` absent value. It does **not** make successful code free: adding a token to an error alternative may enlarge the entire `T | Error` result, arrays of results, record fields, spills and return ABI, even when the actual value is successful. Small unit errors can grow disproportionately. Source tables retain filenames/function names in the binary even when display is off. Separate compilation may inhibit elision. Constructors on the error path perform capture, but layout/calling-convention costs can affect both paths.

Acceptance must measure representation sizes, binary tables and instruction counts for unit errors, `int?`, a small record optional, common success/error unions, result arrays, group arrays and precompiled boundaries. No new opt-out tag is invented to avoid measuring this. Default-on origin remains provisional until those costs are shown acceptable. No claim that a four-byte identifier means four bytes of total overhead.

V1 reporting prints group summary, leaf kind/message and context, with optional locations and escaped terminal controls. It does not dump payloads or auto-enable stack traces. The fixed generic group message is not a secret-bearing payload dump. A group's unhandled main exit code is provisionally the first ordinary-error leaf's existing code; otherwise the first non-none exception leaf's, otherwise ErrorGroup's nonzero assigned code. For `WriteFailed & CloseFailed`, WriteFailed wins; for `Canceled & CloseFailed`, CloseFailed wins. Both cases are explicit in program 01. Dynamic group exit-code selection remains an entrypoint integration delta, not accepted cleanup-code priority.

Defer `caused_by`/`$cause`, public `$context`, `$trace`, ErrorTrace, trace statuses, `$errors.trace`, and trace display. Repeated cause attachment therefore has no v1 overwrite behavior. Any later causal API must settle fresh/replace/append semantics and ownership before it returns. There is no hidden dependency on these APIs in programs-r4.

## 6. Names and gates

The three r22 readers understood the intended broad roles of the existing vocabulary; none distinguished ErrorGroup from ExceptionGroup. This is evidence for removing the distinction, not proof that readers learned the precise runtime semantics of all 27 lines. Read r22/guesses22-a.md, guesses22-b.md and guesses22-c.md; their order/multiplicity guesses support the group interpretation. The new operator use and recover name are not covered by that test.

**Essential v1:** `ErrorGroup`, its `.errors` and generic `.message`; `errors.join`, `errors.leaves`, `errors.with_context`, `errors.report` (`file=`, `locations=`); `$origin`, `SourceLocation` and its file/line/column/function; plus the provisional `errors.recover<E>`. Value `&`/`&=` and array.push reuse spellings. None of the existing Canceled/or_throw/?? names is new. `errors.split<E>` with matched/rest is useful but can wait behind the safe helper. Candidate I's `errors.parts` is not in the recommendation. ExceptionGroup is removed, not deferred.

**Remaining gates:** cold-read recover and the operator usage; compile the paper programs/negative examples when implemented; prove cancellation admission/flag-flow through erased storage; demonstrate owner-safe reconstruction; settle lossless cleanup construction under explicit allocation failure; measure origin representation and flagship costs. Reserving nodes before acquisition is a possible route for cleanup, but the initially returned foreign owner and later transfers still need a concrete contract. The K3 resource gate is not removed by this revision.

No change to cleanup lifetimes, hidden exits on loop jumps, or automatic aggregation of parallel failures is approved here. Program 04 keeps per-item CPU errors as values and folds them afterward. The old proposed automatic multi-failure parallel join is deferred to its owning design. R4's algebra model exercises ordinary grouping, cancellation and recovery; it does not validate Dewy typing, ABI, physical allocation, real callback scheduling, or measured complexity.
