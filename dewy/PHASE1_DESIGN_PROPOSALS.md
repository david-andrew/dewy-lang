# Phase 1 proof and effect surfaces — proposals for review

This document separates approved direction from proposals still awaiting
review. David requested review before implementation on 2026-09-20. The settled ownership work can proceed
independently. The existing `$runtime_assert` and `$prototype` rules remain
unchanged.

## Checked and unchecked local facts

Use the existing static assertion and the proposed unsafe metatag:

```dewy
$assert i <? xs.length
$unsafe_assume i <? xs.length
```

`$assert` already implements the checked boundary: proven assertions erase,
refuted assertions fail, and unknown assertions fail with a different
explanation. There is no reason to add a synonymous `$prove` directive.
The proof-engine work should improve the facts `$assert` can establish.

`$unsafe_assume P` introduces that one assumption without a runtime check.
It emits an auditable entry naming the proposition, source location, and
obligations it discharges. It neither weakens unrelated checking nor disables
checking for a block. David confirmed that these boundaries should be
metatags, and proposed this more explicit spelling on 2026-09-20.

Both accept only the liquid proposition language. Their facts refer to the
current value versions, and are invalidated by the same writes and calls as
facts learned from ordinary conditions. An unsafe assumption is not a claim
that remains true after a value changes. A false assumption can invalidate
bounds or representation safety; its audit entry must survive optimization.
No unchecked external proof certificates.

## Proof functions — revised proposal, awaiting review

Use `$proof`, with the conclusion in a fact-only return annotation:

```dewy
$proof
ordered = (a:int64 b:int64<v => a <=? v> c:int64<v => b <=? v>):> <a <=? c> => {
    $assert a <=? b
    $assert b <=? c
}
```

This extends the existing `<predicate>` fact notation to a complete return
contract. It means “establish this fact,” rather than “produce a Boolean that
might be false.” The parameter annotations supply the preconditions; the
body supplies the checked argument; the return annotation names exactly what
the caller gains. There is no `$proves` statement hidden in the body.

The checker must establish the return fact at every feasible normal exit.
The two assertions in this deliberately simple example document intermediate
steps; an empty body would also succeed because the preconditions imply the
conclusion. The return fact can mention parameters and trusted measures,
not proof-local names or mutable globals. Conjunctions use the existing
proposition language, e.g. `:> <P and Q>`.

An invocation has ordinary function shape:

```dewy
ordered(low middle high)
# low <=? high is now available to the caller's checker.
```

The call checks the preconditions, substitutes the arguments into the
conclusion, and associates the resulting fact with their current value
versions. The invocation and its proof body erase; no heap proof object or
Boolean return is produced. Reassigning an argument later invalidates the
fact normally. Initial proof arguments must be side-effect-free fact terms
(names, literals, trusted measures), so erasure cannot drop an observable
argument evaluation.

For the first implementation, proof evaluation is finite and acyclic:
no unproved recursive proof cycles, effectful calls, allocation, unchecked
assumptions, or diverging paths that could make a false conclusion appear
vacuously true. Branches and calls to other checked proof functions can
structure a larger argument. A future richer proof language can produce the
same checked conclusion representation.

A spelling requiring less new type syntax would be `:> void & <P>`. I favor
`:> <P>` for proof functions because the returned information is the fact
itself; the `void` is only a representation detail. This fact-only contract
is a proposed extension, not something the compiler already supports.
Initially it is restricted to `$proof` functions; ordinary result-bearing
functions retain their existing refined return types. General first-class
proof values and effectful functions returning standalone facts are outside
this proposal.

Review needed: approve `$proof` and the fact-only `:> <P>` return contract,
including erasure and the initial terminating/pure subset? David rejected
the earlier `$lemma`/body-`$proves` shape; neither will be implemented.

## Effect contracts

David approved this starting direction on 2026-09-20. Keep the direction in `resources/types_and_effects_systems.md`: attach an
effect row to a function result annotation, with kind checking separating
value-type intersection from effect combination:

```dewy
read_count = (...):> (int64 | ReadError) & reads<filesystem> => ...
update = (@state:State):> (void) & mutates<state> => ...
```

The HIR signature stores a result type and an effect row separately; an
effect is never a value-union alternative. Parameter subjects identify
bindings/routes, not their spellings. Resource subjects such as `filesystem`
need nominal effect identities so unrelated modules cannot accidentally
assert the same authority just by choosing the same name.

Proposed semantics for the first implementation:

- No written row means infer, preserving existing source compatibility.
- A written row is an upper bound: inferred behavior must be a subset.
  For the explicit empty row I recommend `& Effects<never>`, replacing the
  earlier empty-parameter spelling. `never` denotes an empty set of possible
  effects; `none` ordinarily denotes an inhabitant, not the empty set. This
  uses the bottom concept in the effect kind, not a runtime `never` result.
  The exact spelling remains subject to David's review.
- Start with reads, writes/mutation, allocation, escape, and possible
  process failure. Returning an error alternative is not an effect.
- Function subtyping permits fewer effects than the caller allows.
  Indirect calls must retain their signature's row; “unknown” is never pure.
- A callback's row can be forwarded by an effect parameter, rather than
  enumerating every effect in higher-order library code. The syntax for
  quantifying an effect parameter still needs a decision (ordinary `type`
  parameters would incorrectly conflate two kinds).
- Treat `noreturn` as a checked control-flow guarantee, not a permission in
  the may-effect set: subset ordering is the wrong implication direction
  for “this call never returns.” Likewise, an error return and a process
  failure must remain distinct.

Still to review: `Effects<never>` versus `Effects<none>`, and how effect
identities and effect parameters should be introduced. Allocation
failure policy remains separately tentative; this proposal does not choose
`$fallible_allocation`, error identities, or an exit code on its behalf.
