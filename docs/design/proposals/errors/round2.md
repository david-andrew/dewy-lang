# Combining failures, round 2 — core recommendation

**Round 3 corrects leaf-context traversal, owning payloads, and a few diagnostics; read it alongside this document.**

```dewy
import p"@lib/std/errors.dewy" as errors
WriteFailed:type = type of error
CloseFailed:type = type of error
failed_save = () => errors.join(WriteFailed CloseFailed)
inspect = () => {
    let result = failed_save
    match result {
        group:errors.ErrorGroup => {
            loop child in group.errors { errors.report(child) }
        }
    }
}
```

```dewy
import p"@lib/std/errors.dewy" as errors
FieldError:type = type of error & [field:string message:string]
validate = (name:string age:int) => {
    let failed:array<error> = []
    if name.length =? 0 failed.push(FieldError["name" "required"])
    if age <? 18 failed.push(FieldError["age" "must be at least 18"])
    errors.join(failed...)              # void, original FieldError, or ErrorGroup
}
```

```dewy
import p"@lib/std/errors.dewy" as errors
CloseFailed:type = type of error
interrupted_save = () => errors.join(Canceled CloseFailed)
caller = () => {
    interrupted_save ?? void            # forwards the WHOLE group; cannot report success
    printl("saved")
}
```

**Use ordered groups, not `E1 & E2`. Accumulate in an array; join once. Ordinary matching tests the outer kind. Split explicitly to recover only some children.** Errors gain small origin metadata; context preserves their type; stack traces are opt-in. This is a proposed design, with paper programs, not an implementation or accepted decision. All new spellings need cold reads.

## 1. What was read and what governs this design

Sources are in `/var/home/david/dev/dewy-lang/`:

- `docs/LANGUAGE.md:4142–4209`: nominal errors, intersection, forwarding and narrowing; `4651–4712`: optional values and typed defaulting.
- `docs/LANGUAGE.md:274–310`: collectors, `void` and multi-expressions. A collector directly emitting Canceled leaves its enclosing function.
- `docs/LANGUAGE.md:1219–1227`, `1536–1547`, `3018–3020`, `4234–4237`: function/type intersections, precedence, set intersection and integer masks. `&` is not an ordered product of values.
- All batches in `docs/design/decisions.md` were read. Batch 4 D4 Q1–2 governs cancellation and selected propagation; batch 5 accepts `$explicit_cancellation` and `partition_failures`; batch 9 makes dunder hooks assigned functions and distinguishes scoped `{}` from unscoped `()`.
- `docs/design/open_decisions.md:51–70`: Q3 is this task. Q2 lifetime timing and visible cleanup failure exits are still open; this proposal does not approve round 5's implicit exits on loop jumps.
- `docs/design/proposals/cleanup/round5.md:153–183`: prior pairing and cancellation rules. Replace the pair mechanism only, not the unrelated lifetime proposals.
- Searched `resources/discussion_points.md` with `/usr/bin/grep` before choosing names: the proposed group, context and origin spellings had no established entry. Relevant constraints: `1197–1207` resource-owned cleanup; `2112` diagnostic traces; `3437–3465` is? as type testing; `3521` intersection satisfies both structures; `4612–4635` non-generative intersection. `2434–2460` covers fmt. Nothing there grants an error-combining `&`.

## 2. The value and its type

`errors.join(...failures:exception)` evaluates arguments once, left to right. It accepts failures only, not successful results. No argument is implicitly propagated by this ordinary call.

| Argument count | Result |
|---|---|
| 0 | `void` — no failure, not `none` |
| 1 | The original value, with identity, metadata and payload intact |
| 2 or more, all arguments are `error` | `errors.ErrorGroup` |
| 2 or more, at least one argument is not `error` | `errors.ExceptionGroup` |

`ErrorGroup` is a nominal child of `error`. `ExceptionGroup` is a nominal child of `exception`, **not** a child of `error` and not a parent of ErrorGroup. Both provide `.errors`, an ordered snapshot of their immediate children. ErrorGroup's children are errors; ExceptionGroup's are exceptions. Neither type is generic, and neither is a `FileError`. No multiple nominal inheritance or data-dependent subtyping is introduced.

A result inferred from two known errors is ErrorGroup. A variable-length `array<error>` spread gives `void | error` (including ErrorGroup), or a tighter element union plus ErrorGroup when element kinds remain known. A variable-length `array<exception>` spread gives `void | exception`. Known length one preserves the input type. Known length at least two with uncertain element families gives `ErrorGroup | ExceptionGroup`; the factory chooses from actual children. The exact member-kind set is **not** encoded in the group type. This deliberately bounds type growth across recursion and heterogeneous batches, at the cost of losing exhaustive leaf-kind coverage from the signature.

The groups are library/runtime value types with invariant-preserving factories, like existing managed containers, not publicly mutable records. `.errors` is a computed value snapshot; assigning to `group.errors` is invalid. Mutating a saved snapshot changes that array only. No new readonly keyword. The library cannot expose a backdoor that forges an all-error group around Canceled.

`join(a join(b c))` retains its tree. `.errors` returns `[a, join(b c)]` in explanatory notation; `errors.leaves` visits a, b, c. Repeated values remain repeated, even if equal or sharing storage. No deduplication and no ordering by error kind. An ordered group is not an intersection: A & A has no second occurrence, and a shared `message` field cannot hold two messages. A value-level `&` overload could call join, but would still return a group, not an intersection. Do not add that alias in this round.

## 3. Matching and forwarding are explicit

Normal `match` and `is?` inspect the **outer** value. They never search children or causes. A contextualized FileError is still a FileError; a group containing one is not. `??<FileError>` and `or_throw<FileError>` select bare FileError alternatives only. If a static result is exclusively a group, selecting FileError is the existing “operand cannot hold FileError” diagnostic, with a note pointing to `errors.split<FileError>`. It is not silently a no-op.

For a function whose result can be a bare FileError, success, or a group:

| Operation | Bare FileError | ErrorGroup containing FileError + another error | ExceptionGroup carrying Canceled + FileError |
|---|---|---|---|
| `is? FileError`, `match` FileError arm | yes | no | no |
| `is? error`, `match` error arm | yes | yes, binds whole group | no |
| `is? exception`, `match` exception arm | yes | yes, binds whole group | yes, binds whole group |
| bare `or_throw` | forward | forward whole | forward whole |
| `or_throw<FileError>` | forward | retain whole as value | retain whole as value |
| `or_throw<error>` | forward | forward whole | retain whole as value |
| `or_throw<Canceled>` | retain | retain | forward whole |
| bare `?? fallback` | default | default whole | forward whole from function |
| `??<FileError> fallback` | default | retain whole as value | forward whole from function |
| `??<error> fallback` | default | default whole | forward whole from function |
| `??<ExceptionGroup> fallback` | retain | retain | forward whole from function |
| `??<Canceled> fallback` | retain | retain | forward whole from function |
| `??<Canceled | ExceptionGroup> fallback` | retain | retain | explicitly default whole |

Rows are semantic cases, not permission to name impossible selectors in a narrower static operand. For example, test `or_throw<Canceled>` on a result type that admits cancellation. A broad `exception` selector does not count as explicitly naming Canceled.

**The only descendant-aware selected propagation is `or_throw<Canceled>`**, extending the cleanup round's direction to these general groups. It preserves the whole containing value; it never extracts Canceled and loses its siblings. There is no corresponding descendant-aware `is? Canceled`. Document this distinction beside the two operators, rather than pretending they are identical type tests.

Cancellation protection is computed at group construction as the OR of children's cached cancellation flags. Ordinary leaf Canceled sets the flag. Context retains it. A copied value or erased exception retains it. Readers inspect that bit in O(1), not recursively at every `??`. User payloads are not recursively scanned: an ordinary application record containing an exception is data, not an automatic cancellation carrier. This proposal does not redefine existing protocol-specific wrappers.

At `??<E>`, a cancellation-carrying group leaves the function unless E explicitly names Canceled **and** selects that group's outer type. Bare `??`, `?? void`, control-flow fallbacks and collectors all preserve the whole carrying value. Under `$explicit_cancellation`, those implicit exits are compile errors; `or_throw<Canceled>` is the fix. A group whose type can carry cancellation is conservatively checked even if the particular value happens not to. An explicit `match` on ExceptionGroup or exception may handle it; that is as deliberate as matching bare Canceled. Handling it does not reset the task's cancellation state.

## 4. Taking parts out without dropping the rest

- `group.errors` gives immediate children in insertion order, preserving nested boundaries. It is the inverse of a multi-input join, subject only to the zero/one normalization.
- `errors.leaves(failure)` gives a non-allocating, iterative traversal in depth-first left-to-right order. It yields the failure itself if it is not a group. It does not descend into an error's cause: a cause is why one failure occurred, not an independent failure to recover from.
- `errors.split<E>(failure)` returns an ordinary record `[matched:array<exception> rest:array<exception>]`. The arrays are empty or hold one reconstructed root subtree each. E tests **leaves only**. No matches means matched=[] and rest=[original]; all matches means matched=[original] and rest=[]. Partial matches prune the tree, preserving order, origin, context and duplicates on each surviving branch. Unary reconstructed groups remain groups so context isn't lost; join itself never manufactures unary groups. A pruned group is reclassified from its actual children. Empty branches disappear, not as a `none` placeholder.

A typed split is explicit data work: it does not propagate cancellation by itself. A caller must handle `rest`, normally with `errors.join(parts.rest...) or_throw`. A bare `Canceled` can therefore be inspected by splitting, but forwarding the rest still forwards it. A group selector passed as E is rejected: it is a leaf partition, not an ambiguous combination of outer/inner matching. `error` and `exception` as E select leaf families; `Canceled` selects that exact leaf.

The returned record has both arrays together so a caller sees the remainder. Normal unused-binding diagnostics must name a completely unused rest; no new linear error system is proposed. A caller can deliberately discard it with existing constructs. This is safer than “contains means catch,” but does not prove that arbitrary user-written recovery handled every leaf. The final score keeps that deduction.

A cause below a ConfigError is not selected by `split<FileError>`. Recover the ConfigError at its abstraction boundary, or explicitly inspect `$cause`. Recovering the low-level cause alone cannot declare the higher-level operation successful.

## 5. The accumulator and parallel outcomes

Use the existing array:

```dewy
import p"@lib/std/errors.dewy" as errors
parse_all = (texts:array<string>) => {
    let failed:array<error> = []
    loop text in texts {
        let value = to_int(text)
        if value is? error failed.push(value)
    }
    errors.join(failed...)
}
```

`push` is amortized constant time; join once is O(n). The array is not itself a failure. A nonempty check isn't required to turn it into a `void | exception` return. If a successful payload is also needed, forward `errors.join(failed...) or_throw` then return the payload. `partition_failures` remains the accepted way to separate successful and failed array elements.

Do **not** construct a cancellation group through `[Canceled other]`: the collector forwards before join runs. Write `errors.join(Canceled other)`, or explicitly `pending.push(canceled)` after narrowing, then `join(pending...)`. Arguments, `push`, and a record's fields are ordinary value storage; a collector's special cancellation behavior does not recursively inspect arbitrary data. Program 08 covers this exact boundary.

A batch accumulates ordinary failures. When a cancellation value is observed, it appends that value and returns the complete accumulated group immediately. It does not continue more work after cancellation. Retry does likewise. Direct iteration over `errors.leaves` permits explicit Canceled handling; putting that traversal into a collector re-applies the collector rule.

For `parallel` all-results processing, keep ordinary failures as per-item values, then partition/join in input order. Program 04 uses nonwaiting CPU validation so it has no cancellation checkpoints. No exception is thrown from its items. If waiting work can produce Canceled, an ordinary collector still cancels and forwards on that value; this design does not silently turn it into a collect-all primitive. Packaging outcomes as application records is an explicit alternative, but scheduling/externally canceled not-yet-started items still needs the concurrency design's contract. Do not claim that wrapper alone guarantees a complete canceled batch.

Fail-fast `or_throw` in a parallel item still cancels siblings as already decided. Recommend the join/unwind boundary retain every additional failure it observes while joining, especially cleanup failures: trigger first, other completed failures in item/source-index order, each child's cleanup in its execution order. Failures from operations never started do not exist and must not be fabricated. The trigger may depend on scheduling; ordering the collected remainder does not promise deterministic winner selection. The all-results program has deterministic input order. Implementing automatic multi-failure joins is an extension to the current first-failure rule and needs concurrency integration, not just this library.

## 6. Context, causes and source locations

### Context preserves a failure's kind

`errors.with_context(failure message)` returns the same type and payload with one diagnostic frame attached. The message describes an operation, e.g. “loading application configuration.” The frame records the context call's source site. Context is outermost-first when displayed and retains the earlier failure as its explanation; adding another frame never overwrites the first origin. A frame on a group applies to that subtree, not to its siblings. No new exception kind is needed merely to add text. This operation is not a recovery and cannot hide cancellation.

Read-only `failure.$context` exposes the ordered context frames as ordinary records with `message` and `location`. It may be empty. Context metadata is persistent and value-local; annotating a copy does not mutate errors kept elsewhere. No global registry keyed by error equality or error kind.

When a library genuinely changes the domain kind, `errors.caused_by(outer:error cause:error)` returns the outer error with read-only `outer.$cause` set to that cause. That member is `error | none`. The outer type controls ordinary matching and its exit code. A cause is singular; use a group if several errors caused it. Construction is acyclic: the returned value refers to older immutable values, and public metadata cannot be mutated into a cycle.

The restriction to error is intentional: `caused_by(ConfigError[...] Canceled)` is a type error. Forward cancellation first, or use transparent with_context. Similarly a cancellation-bearing ExceptionGroup cannot become an ordinary ConfigError cause. Application-defined records can always store arbitrary values; they do not acquire standard cause traversal by naming a field `cause`. Supporting custom wrapper protocols is out of scope, not silently inferred.

### Origin is recorded before it can be requested

Every newly constructed Dewy exception occurrence records a compact source-site token. This includes constructing a unit exception value in an expression, not just `return` or `or_throw`. Reading an existing binding, copying, passing, forwarding, joining or splitting it preserves that occurrence. A constant sentinel reused in several operations therefore has its original construction location; to mark each operation, construct the unit error at that operation or add context there. No mutation of the singleton type object and no loss of the two origins of two same-kind errors.

`failure.$origin` gives `errors.SourceLocation | none`. SourceLocation has `file`, `line`, `column`, `function`; lines and columns are one-based, columns count Unicode scalar values. Paths are build-root-relative when known, and do not require the source file to exist at run time. Unknown/imported origins give none, never the current inspection location. Foreign adapters record the Dewy adapter construction site; they cannot claim to know a native library's internal site. A group's origin is the join call; its children's origins remain available. Implicit cleanup groups identify the cleanup exit site, with the failing hook's own origin on its child.

The target representation is one site identifier, typically 32 bits, with a shared static table. It can enlarge a tiny error or its union because of alignment, and the table contributes binary size. No per-failure heap allocation or stack walking is needed just for origin. Successful operations execute no capture work. Metadata access is a compiler metatag member read on any narrowed exception and does not invoke ordinary exception-forwarding member navigation. Erasing to `exception` preserves it. Metadata does not participate in error equality/hash; payload equality does. DCE can remove unobservable tables in a closed program, but separate compilation may require retaining tokens. These are design costs, not measurements.

### A requested stack trace is not a time machine

`$errors.trace = true` at the top of a function body enables capture during that function, its calls and started tasks, following batch 9 scope settings. Default false. Capture occurs at **new exception construction**, not when `$trace` is read, and forwarding does not recapture it. Existing values entering the scope do not acquire a historical trace. A context frame can supply the new boundary's site.

`failure.$trace` is `errors.ErrorTrace`, with `frames:array<errors.SourceLocation>` and `status:'disabled' | 'captured' | 'truncated' | 'unavailable'`. Frames run from construction outward. At most 32 logical synchronous frames are recorded; status says truncated rather than pretending to be complete. The origin still exists if tracing is unavailable. Inlined source frames should be recovered where the target supports them. Task-parent history is **not** promised as a synchronous call stack. Groups retain each child's trace, with their own optional construction trace.

Capture takes O(min(depth,32)) time and bounded storage per new exception, and may require frame/unwind metadata on successful code too. Heap use, inability to symbolize some targets, and the effect on inlining/frame layout must be measured. `$no_hidden_costs` exposes those costs; scope settings are not permission to hide them. In an explicit allocation-failure lane, optional diagnostic capture may return status unavailable without replacing the application failure. That exception applies only to optional trace data, never to dropping a failure payload. No environment-variable toggle.

## 7. Reporting and cleanup

`errors.report(failure file=stderr locations=false trace=false)` is a void call, streaming the whole group/context/cause tree. It prints kind and message, numbered group branches, “caused by” edges and context frames. It never dumps arbitrary payload fields. Locations and traces appear only on explicit request; an unavailable location or trace is labeled, not invented. Repeated occurrences print repeatedly. The streaming implementation must avoid native recursion proportional to user-controlled group depth; its worklist has an explicit resource policy. Output failure follows the existing console policy. This design does not promise an allocating formatter succeeds after total memory exhaustion.

An unhandled group at main uses that report shape with locations/trace off. Its nonzero exit code is the first ordinary-error leaf's existing code in traversal order, otherwise the first non-none exception leaf's code, otherwise ExceptionGroup's assigned nonzero code. A domain error's cause does not replace that domain error's exit code. `dewy build --exit-codes` must describe this dynamic selection for group alternatives rather than claim one fixed group code. This is a proposed extension of entrypoint reporting. In a Canceled + close-error pair, the close error determines the code, matching the earlier cleanup proposal.

Replace `CleanupError[primary=E cleanup=F]` with `errors.join(E F)`. No primary/cleanup wrapper survives. Add a context frame to the cleanup child saying which owner's completion failed, including the exit site's location; this is text metadata, not a new typed role. A lone completion failure remains that original kind, optionally contextualized. Further completion failures fold after existing ones in actual cleanup order. A pair remains a subtree; flatten only when printing leaves or explicitly traversing them. The original body error remains first. Successful values are not error children; pending `none`, if it is the failure being propagated, is a real exception child, not “no prior failure.”

Program 01 exercises a function return and a hook with two failures. Program 08 exercises cancellation plus cleanup. Neither settles early release, lock lifetime or the visible exit needed on `break`/`continue`/inner braces. D40 Q2 and that visible-exit problem remain open.

## 8. Costs, resource limits and implementation acceptance

Ordinary errors do not allocate for origin alone. Adding context/cause/group data can allocate, as can growing the accumulator. join takes O(number of immediate arguments), without copying descendant trees. Join from a last-used erased exception array should be able to transfer its buffer. Group flags are calculated once from child flags. An implementation must not promise every typed-array conversion is free. Repeated binary joins allocate O(n) nodes but have O(n) depth; traversal/split/report therefore use iterative algorithms. Shared immutable subtrees use ordinary value ownership/COW and do not require a process-global registry.

Split visits O(nodes plus metadata retained) and creates at most O(nodes) new branch nodes. Leaves visits each occurrence once, using O(depth) work storage. Cause/context edges are distinct from aggregate children. Carrying flags are part of the representation, preserved across erasure and ABI crossings. Static inference uses indexed summaries on reachable group/metadata operations and monotone failure unions, not powersets of all possible simultaneous error combinations. Source table work is linear in emitted sites. Library code must be demand-loaded; an integer-only hello world should not import a report formatter or stack unwinder.

**Unresolved implementation gate: allocation while reporting allocation failure or completing owners.** A design cannot keep an unbounded number of arbitrary payloads in finite emergency storage. The resource design already distinguishes the default allocation assumption from the explicit lane. Grouping must not replace existing failures with only OutOfMemory and call that lossless. The implementation needs either pre-reserved cleanup nodes/capacity acquired before the corresponding work, or a concrete non-allocating ownership-preserving representation. A streaming emergency diagnostic is not a value-preservation solution. Until one is demonstrated, cleanup grouping under explicit allocation exhaustion has K=3, not 5. Normal application bounds (program 12) limit diagnostic growth but do not prove physical allocation can succeed.

Acceptance gates before implementing/landing:

1. Compile the twelve paper programs after proposed APIs exist; preserve their stated output/return contracts. Negative tests must reject error arguments containing successes, impossible selectors, group-as-leaf selectors, cancellation as a domain-error cause, and metadata mutation.
2. Verify duplicate instances and two distinct origins; nested context through split; forwarding after erased storage; zero/one join; none versus no failures; copied snapshots; no Canceled swallowed by ?? variants or collector variants, including `$explicit_cancellation`.
3. Verify each leaf appears in exactly one split side, with stable order within each side. Rejoining the two sides need not restore their interleaving; retain the original if that is wanted.
4. Exercise cleanup at function returns and parallel join with at least two failed completions; no hidden approval of unresolved loop-exit behavior.
5. Prove/review ownership and exhaustion behavior for error payloads with owners, aliasing, COW and precompiled/foreign boundaries. Do not equate a metadata sketch with an ABI implementation.
6. Measure instruction-count and binary-size deltas for successful/error-heavy/no-trace/trace configurations on the flagship panel before landing, then the required quick, full, bootstrap and fixed-point gates. No performance measurements or compiler test claims are made here.

## 9. Decisions to take forward

Recommend the semantics above provisionally; syntax review covers the names in names.txt. Two group types are justified by Dewy's existing error/exception distinction, not a desire for a general hierarchy redesign. Selected handlers remain outer-kind tests, with the single explicit cancellation propagation extension. Source-site recording is small and default; traces remain bounded and opt-in.

Remaining review deltas are real: two nominal group names, a descendant-aware or_throw<Canceled>, transparent metadata on exceptions, dynamic group exit-code selection, and automatic multi-failure retention at parallel joins. Cleanup timing, custom wrapper protocols and the explicit-allocation representation are not settled here. No independent naming test was run; this package must not be labeled cold-read or all-5 dogfooded.
