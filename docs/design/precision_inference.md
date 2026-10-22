# Precision-preserving inference (2026-10-21)

Accepted design, implementing David's 2026-10-21 decision. Implemented for string
bindings (lazy domains); integers keep range facts.

## Binding rule
An annotation fixes storage's type, including an explicitly wider `string`.
Otherwise infer a common type of the initializer and all possible writes in the
binding's lexical lifetime, before checking consumers. Finite string values
join by set union; a general string source makes the join `string`. The set is
flow-insensitive: writes in either branch or any loop iteration participate.
Thus `let mode="fast"; mode="slow"` has `'fast'|'slow'`; an additional
`mode="other"` adds a member rather than causing a rejected store. A match
covering only fast/slow must then fail, even if it precedes that store.
This is the scalar counterpart of later pushes settling an empty container.

Lexical identity matters: shadowing must not merge distinct bindings. Closure
writes participate in the captured binding; a closure's private binding does
not. Mutable escapes whose write domain is unknown require the base type.
Declared fields retain their declared types; inferred record fields and
container elements are outside this first scalar-storage implementation.
Preserving a field's initializer as its contract would incorrectly reject
ordinary later updates, so it needs the same whole-storage solution first.

The implementation may conservatively use the base type when determining a
write's finite domain requires arbitrary function evaluation or an unbounded
constraint solve. It must never guess a smaller domain or insert a new runtime
failure for a previously valid unannotated store. Keep ordinary string APIs
available through the existing literal-set-to-string conversion.

## Integers
Keep mathematical `int` as the public inferred type; preserve singleton/range
information as facts, not restrictive literal storage types. `count=0;
count+=1` remains valid, as does `a=5; a=300`. Existing flow facts, bounded loop
widening and bigint promotion already implement this separation. Do not infer
int8 from 5: that would change overflow semantics. Reuse existing range proofs
and unboxing; no additional integer analysis or representation pass is justified
without a measured performance benefit. Integer behavior therefore does not
change in this batch; add counter/range regression coverage.

## Payoff and cost
A finite string domain enables matches without else, finite members(), and
literal-key checking, using the existing tagged-word representation. Integer
facts enable existing checks to disappear and existing unboxed lowering.
Discover string candidates on demand and bound analysis; avoid repeat checking
of function bodies or a general fixed-point pass. The synthetic compile gate
must remain within +0.3%; runtime bench must stay within +3% of master.

No new surface needs approval. General aggregate write-domain inference and
precision across arbitrary calls are follow-up implementation work, not new
language syntax. Any inability to meet the compile budget is a failed pilot,
not grounds to weaken the gate.

## Implementation
String domains are collected lazily during checking and materialized only when a
consumer (exhaustive match, `members`, finite keys) needs them; storage stays a
string. An eager finite-set representation was too costly.

Round 6 (integers as ranges): unannotated `int` bindings collect literal writes
and once-run literal `+=`/`-=` deltas the same lazy way, settled only for an
exhaustive match or a literal-union conversion (at most 256 values, 8 deltas;
past that, or for any other write, the set is open and the type is `int`).
