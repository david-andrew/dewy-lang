# Combining failures, round 3 — traversal and ownership corrections

```dewy
import p"@lib/std/errors.dewy" as errors
MissingAsset:type = type of error & [message:string]
InvalidAsset:type = type of error & [message:string]
inspect_nested = ():>void => {
    let failure = errors.with_context(
        errors.join(MissingAsset["missing thumbnail"] InvalidAsset["bad index"])
        "loading derived assets"
    )
    loop leaf in errors.leaves(failure) {
        errors.report(leaf locations=true)  # retains “loading derived assets” on each leaf
    }
}
```

**Read with round2.md: the amendments below override its affected paragraphs. All other rules stand.** This is the final paper recommendation, not a claim of implementation. It fixes two issues found while writing programs 09 and 11 and auditing ownership, rather than raising the grades by assertion.

## 1. Leaves need their diagnostic path

Round 2's bare leaf traversal made program 09 lose the parent context when it joined an individually failed recovery with its original leaf. That is a fixable completeness defect. The traversal now yields each original leaf **with inherited ancestor context frames**, outermost first, followed by that leaf's own context. Its nominal type, payload, origin and cause are unchanged. This is the same transparent decoration as with_context; it does not mint an error wrapper. The original tree is unchanged.

For the example, each leaf reports “loading derived assets.” Splitting still preserves the actual tree and attaches a group frame once to each surviving branch. Traversing a split side does not attach that frame twice. Repeated equal messages from distinct context calls remain distinct frames; the implementation must use frame occurrence identity, never text equality, to recognize inherited frames. Reporting a whole group emits its own context once, then its children; reporting an isolated decorated leaf emits its inherited path. These are two views of the same diagnostics.

`errors.leaves` is lazy, but **not promised allocation-free**, contrary to round 2's first wording. An iterative traversal needs O(depth) work state. An inherited context path can be shared as immutable nodes; materializing its text costs the output size. Walking nodes without printing frames is O(nodes); printing the same ancestor frame for many isolated leaves costs O(total printed frames), which can exceed O(nodes). The ordinary full-tree reporter avoids that repeated text. There is no native recursion guarantee hidden inside “non-allocating.”

Direct `.errors` still gives the immediate original children. It does not silently attach a group's context: the direct-parts inverse and the leaf-reporting view have different, stated purposes. Using `.errors` and reconstructing a group deliberately drops that group's wrapper metadata unless the caller preserves it. The original parent is always available for full reporting while it is owned.

## 2. Owners in error payloads cannot be cloned

A grouped exception may itself own a resource or an unsent payload. “Snapshot” is not permission to duplicate that owner. All APIs follow Dewy's existing ownership rules:

- Joining/contextualizing consumes an owning failure at its last use; copied ordinary errors keep independent value semantics. No global shared mutable error object.
- Reading `.errors` for observation lends its elements. Materializing independent child values requires either copyable payloads under the existing rules or consuming the group. A second use that would duplicate an owner is a compile error. The exact inferred loan/consume mode appears in the signature/hover, as for other managed values; no new keyword or Copy trait is introduced here.
- Leaves/report borrow while observing. A leaf retained past that traversal requires a legitimate value transfer or copy; an escaped loan cannot outlive the group. A consuming traversal can move each owning leaf once. Grouping borrowed views without owning their source is rejected. An implementation may need ordinary overloads for these modes, but not silently shared ownership.
- split consumes a move-only root and partitions its leaves: each owned payload appears in exactly one output. It does not keep a second owning original. With copyable roots, ordinary copying before the split is allowed. Reconstructed branch context consists of shareable immutable text/site metadata.
- `caused_by` accepts a **nongroup** outer error. A group's simultaneous children are already its explanation. Allowing a group with an additional owning cause would require duplicating that cause across two split branches; reject it rather than invent shared ownership. A nongroup domain error can have a group as its single cause, as already proposed, and the leaf partition never descends into that cause.

The concrete payload/ABI implementation remains an acceptance gate, not measured evidence. These ownership modes must be demonstrated in compiler tests before this becomes an implemented guarantee. The twelve examples use copyable payloads; they do not count as an ownership-payload test.

## 3. Diagnostics must not fabricate compile-time knowledge

Selecting FileError on a statically group-only operand remains an error. But `split<FileError>` on a group cannot be rejected merely because the group type erases child kinds. The library does a runtime leaf test and may give no matches. On a statically known scalar nonmatching leaf, the editor may report that the matched side is empty; generic use stays legal. No exponential child-kind inference is required.

For the cancellation table, “explicitly names Canceled” means membership of the **normalized named union alternatives**, so a type alias for `Canceled | errors.ExceptionGroup` works too. A broad exception family still does not. A carrying group selected by `<Canceled>` alone forwards automatically from `??` and triggers `$explicit_cancellation`; no inconsistent “retained as value” exception is hidden in that row.

The impossible-selector diagnostic has one explicit exception: `Canceled` may be named whenever the operand can **carry** cancellation, even when it cannot be a bare Canceled. Thus both `interrupted or_throw<Canceled>` and `interrupted ??<Canceled | errors.ExceptionGroup> void` type-check for a group-only result. FileError has no such exception. Otherwise the documented acknowledgment of cancellation would itself be rejected as an impossible root type.

On the continuing path, `or_throw<Canceled>` proves the operand's cancellation flag is clear. This is an internal flow refinement, preserved by local copies/erasure of that value, not a new type spelling. A later `??` on it therefore passes `$explicit_cancellation`, including when the remaining public type still includes ExceptionGroup. A general function that may return a new carrying value invalidates that refinement. The compiler must track this indexed fact; removing only the bare Canceled alternative from a union is insufficient.

The nongroup constraint on caused_by is statically proven. An erased `error` used as its outer value must first be narrowed to exclude ErrorGroup. Failure to prove it is a compile error, never a runtime trap or a silently discarded cause. Constructing a nominal ConfigError directly, as program 10 does, proves the condition trivially.

The default reporter escapes terminal control characters in user text and paths. That prevents control-sequence execution; it does not promise to redact secrets a caller deliberately put in a message. Locations and traces still require explicit display options.

## 4. Remaining deductions are not erased

- **Two group types and cancellation propagation:** learning that ErrorGroup is error-only, and that `or_throw<Canceled>` searches a carrying bit while `is? Canceled` does not, is a real O/D cost. One type would reintroduce the broad-handler bug, or require special nominal type rules. This is a chosen tradeoff, not an unfinished rewrite.
- **Explicit remainder:** the programmer must keep the rest from split. A mandatory linear error effect would be a separate language-wide design. Program 09's S4 remains.
- **Variable group member types:** the outer group is checked, its complete child-kind set is not in its type. A typed group extension could recover precision but expands this proposal and recursive type inference. Ordinary leaf narrowing is sufficient for the demonstrated recovery path.
- **Cleanup timing and canceled parallel collect-all:** explicitly out of scope, still open elsewhere. The programs do not claim to settle either.
- **Finite-memory diagnostics and cleanup:** still K3 for lossless explicit-allocation cleanup. A capacity reserve before each owner exists is a plausible implementation route, but a design paragraph cannot prove it works for arbitrary foreign completion and moving payloads.
- **Names:** independently untested, so discoverability grades are provisional and cannot honestly become 5 by self-review. No new agent was launched from this sub-agent.

The executable semantics model checks grouping, selection, partition order and inherited contexts; it does not implement the compiler, resource ownership, allocation, traces, or task scheduling. dogfood.md separates those facts from the paper grades.
