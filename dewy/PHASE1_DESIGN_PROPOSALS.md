# Phase 1 proof and effect surfaces — proposals for review

These are proposals, not implemented language rules. David requested review
before implementation on 2026-09-20. The settled ownership work can proceed
independently. The existing `$runtime_assert` and `$prototype` rules remain
unchanged.

## Checked and unchecked local facts

Proposed spellings:

```dewy
$prove i <? xs.length
$unsafe i <? xs.length
```

`$prove P` asks the static solver to establish P. Failure or exhaustion of
its bounded search is a compile error, with “unknown” distinguished from a
contradiction. It does not insert a runtime branch. `$unsafe P` introduces
that single assumption, with no runtime check, and emits an auditable entry
naming the proposition, source location, and obligations it discharges.
Neither form weakens unrelated checking or disables checking for a block.

Both accept only the liquid proposition language. Their facts refer to the
current value versions, and are invalidated by the same writes and calls as
facts learned from ordinary conditions. An unsafe assertion is not a claim
that remains true after the value changes. A false assertion can invalidate
bounds or representation safety; it must stay visible even if optimization
erases all the affected code. No unchecked external proof certificates.

Question: are metatags the right surface for these two boundaries, or should
`unsafe` be a syntactic construct? I favor the metatags because these are
instructions about proof obligations rather than runtime values.

## Checked lemmas

Proposed first form uses an ordinary function signature for parameters and
preconditions, a `$lemma` declaration tag, and a `$proves` conclusion in its
body:

```dewy
$lemma
ordered = (a:int64 b:int64<v => a <=? v> c:int64<v => b <=? v>):>void => {
    $proves a <=? c
}
```

The checker proves the declared conclusion on every feasible normal exit.
An empty body is valid only when the preconditions already imply it, as in
this deliberately simple example. Branches and calls to other checked
lemmas can decompose harder proofs. The conclusion must mention parameters
and trusted measures, not body-local names or mutable globals. Calls check
the preconditions and instantiate the conclusion into the caller's current
value versions. The checked proof has no runtime body or runtime result.

For an initial implementation I propose finite, acyclic proof evaluation:
no unproved recursive lemma cycles, effectful calls, allocation, unchecked
assumptions, or diverging paths that could make a false conclusion appear
vacuously true. This is a small checked proof boundary, not a general proof
language. A future richer proof language can produce the same checked
conclusion representation. It must not silently turn an unknown obligation
into an accepted proof.

Questions: approve the declaration/conclusion spelling, and the initial
restriction to terminating, effect-free proof evaluation? An alternative is
a proposition-valued return contract, but that needs a new proof-value kind
and a decision about its relationship to ordinary Boolean values.

## Effect contracts

Keep the direction in `resources/types_and_effects_systems.md`: attach an
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
  We need an explicit empty-row spelling; I propose `& Effects<>` using
  the already sketched `Effects<...>` form.
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

Questions: approve the row interpretation and explicit empty row? How
should effect identities and effect parameters be introduced? Allocation
failure policy remains separately tentative; this proposal does not choose
`$fallible_allocation`, error identities, or an exit code on its behalf.
