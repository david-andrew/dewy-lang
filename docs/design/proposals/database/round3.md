# Round 3: keep aggregate expressions ordinary

This final pass supersedes the grouped-expression example in round 1. The rest of round 2 stands. No database source was implemented or compiled.

## The fix

In the original analytics program, `g.items.count` and `g.items.sum(selector)` left a critical type question unanswered. If `items` were a query, those operations would perform fallible I/O inside a predicate/projection required to be pure and total. If it were an ordinary array, zero-argument count was not the documented array API. A special 'expression-only group' would quietly recreate a database DSL.

Final program 04 makes the logical group value a plain record `[key:K items:array<T>]` and writes:

```dewy
report = <S>(store:S first_day:int last_day:int) => {
    let rows = store.sales.where((s) => first_day <=? s.day and s.day <? last_day)
        .group_by((s) => s.region)
        .map((g) => [region=g.key orders=g.items.length
            cents=sum([loop sale in g.items sale.net_cents])])
        .sorted(key=(r) => r.region).all or_throw
    loop row in rows { printl"{row.region}: {row.orders} orders, {row.cents} cents" }
}
```

The unoptimized evaluator constructs ordinary grouped arrays and calls this ordinary Dewy projection. The optimizer may fuse count/sum into accumulator state and avoid those arrays **only** when it proves equivalent types, values, ordering and observable failure behavior under the language's optimization rules. Exact `int` sum cannot be replaced by overflowing SQLite integer SUM. If grouping arrays or an inner comprehension cannot be eliminated, explain reports O(N) retained records and the corresponding allocation cost. The general callable/iteration prerequisite remains; this revision does not claim it solved.

A terminal `query.count` is a database operation returning int|errors; `g.items.length` is an ordinary array member returning an integer. A terminal `query.sum(selector)` remains a proposed convenience, but the grouped example no longer depends on it. `where` still needs a total bool predicate. A map may perform pure allocation consistent with normal Dewy allocation policy; under explicit allocation failure its result is fallible, so the general fallible-transform contract must preserve and forward that failure. Until that contract is designed, such a map is unavailable in that stricter lane. Do not claim the full pipeline works under `$bulletproof` merely because the default example is convenient.

## Cost and representation review

The common desire 'use the index' is not a sufficient performance requirement. A key-ordered result selected through a balance-ordered index can still need an expensive sort. Grouping ordered records can still retain O(N) values. The final proposal reports those costs and offers a bounded page, without claiming every operation is streaming or O(log N).

Index keys are canonical values with an explicitly defined lexicographic order for compound key projections. This is a database descriptor contract, not a change to ordinary array comparison operators. The optimizer may map an ordinary `.sorted(key=)` to that index only if its comparator agrees with the descriptor order. If current ordinary compound-key sorting does not supply that comparator, add the ordinary collection capability first; do not let the same expression sort differently on an array and on a database query.

Counts and integer sums are exact. A query over optional values must explicitly include/exclude/default none as normal Dewy code would. Group keys include none as an ordinary value. NaN and signed-zero behavior must preserve the selected Dewy equality/sort contract; backends cannot silently collapse NaN into SQL NULL. A finite set of indexed scalar/composite codecs ships first, with UnsupportedFeature or local evaluation for unsupported exact operations. An implementation does not get permission to use approximate floating-point math because it is behind SQLite.

Read-only opens have a statically restricted handle when the option is compile-time known, as in program 09. A runtime read_only flag cannot change a static return type: it returns the union of read-only and writable handle types, and code must narrow before mutation. There is no permission hidden only in a runtime bool while the type advertises guaranteed writes.

## Review outcome

All identified local corrections were made: optional handling, CLI argument position, parallel error propagation, unambiguous negative values, set-valued relations, stable page continuation, stale-save checking, strict CSV boundary, and ordinary aggregate expressions. The remaining sub-5 scores in dogfood are explicit scope/contract dependencies or measured-evidence gaps. Names remain untested by independent readers. A fresh language-mechanism design, implemented engine/tooling, or independent usability test could raise those scores; editing this paper cannot honestly do so.

The proposal is ready for a coordinator's critical review, **not** for claiming the brief's fully indexed library-only comprehension requirement achieved. It preserves that requirement as the highest-priority technical gap instead of grading around it.
