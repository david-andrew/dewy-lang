# Phase 1 proof and effect surfaces — proposals for review

This document separates approved direction from proposals still awaiting
review. David requested review before implementation on 2026-09-20. The settled ownership work can proceed
independently. The existing `$runtime_assert` and `$prototype` rules remain
unchanged.

## Checked and unchecked local facts

Use the existing static assertion and the reviewed unsafe metatag. Both use
the assertion form's argument grammar, `cond [, message]`:

```dewy
$assert i <? xs.length
$unsafe_assert i <? xs.length, 'the external producer validated this index'
```

`$assert` already implements the checked boundary: proven assertions erase,
refuted assertions fail, and unknown assertions fail with a different
explanation. There is no reason to add a synonymous `$prove` directive.
The proof-engine work should improve the facts `$assert` can establish.

`$unsafe_assert P` introduces that one assumption without a runtime check;
the name does not make it a checked assertion. Its optional message follows
`$assert`'s compile-time string-literal rule and supplies an audit explanation.
The directive owns the separating comma, just as `$assert` does. It emits an
auditable entry naming the proposition, message, source location, and
obligations it discharges. It neither weakens unrelated checking nor disables
checking for a block. David selected `$unsafe_assert` in the follow-up review
on 2026-09-20; it replaces the earlier `$unsafe_assume` proposal.

Both accept only the liquid proposition language. Their facts refer to the
current value versions, and are invalidated by the same writes and calls as
facts learned from ordinary conditions. An unsafe assumption is not a claim
that remains true after a value changes. A false assumption can invalidate
bounds or representation safety; its audit entry must survive optimization.
No unchecked external proof certificates.

Initial implementation: both compilers accept unknown assumptions in the pure
fact-term subset, retain them through optimization in a versioned JSON audit,
and invalidate their facts normally on mutation. The initial consumer list is
a conservative inventory of checks in the same function, **not** exact proof
dependency tracking. That remaining work is part of the audit milestone.
Conditions known false are currently unsupported; whether the final boundary
rejects known contradictions or deliberately admits them is awaiting review.
This limitation does not change the distinction between unknown and refuted.

## Proof functions — reviewed direction

Use `$proof`, with the conclusion in a fact-only return annotation:

```dewy
$proof
ordered = (a:int64 b:int64<v => a <=? v> c:int64<v => b <=? v>):> <a <=? c> => {
    $assert a <=? b
    $assert b <=? c
}
```

Reserve `:> <P>` for `$proof`. It means
“establish this fact,” rather than “produce a Boolean that
might be false.” The parameter annotations supply the preconditions; the
body supplies the checked argument; the return annotation names exactly what
the caller gains. There is no `$proves` statement hidden in the body.

The checker must establish the return fact at every feasible normal exit.
The two assertions in this deliberately simple example document intermediate
steps; an empty body would also succeed because the preconditions imply the
conclusion. The return fact can mention parameters and trusted measures,
not proof-local names or mutable globals. Conjunctions use the existing
proposition language, e.g. `:> <P and Q>`.

An invocation has function-call spelling but is a statement, not a value.
Only a direct call whose target resolves to a known `$proof` declaration is
allowed, including a statically resolved imported declaration:

```dewy
ordered(low middle high)
# low <=? high is now available to the caller's checker.

let x = ordered(low middle high)  # error: a proof call is not a value
let callback = @ordered          # error: no first-class proof functions
```

Passing `ordered` as a callback, storing it, or invoking it through a
function-valued parameter is likewise invalid. Ordinary function-handle and
implicit-call rules do not turn a proof declaration into a value. These are
call-site rules, not merely limitations on how proof values are represented.

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

Ordinary functions keep `:> T` and `:> T & <P>`. In particular,
`:> void & <P>` is a real runtime function which returns nothing and
establishes a fact. It need not be a pure, terminating proof and is not
erased on that account. It owes the fact on each normal return; its ordinary
effects and possible nonreturning behavior remain part of the call.

Implementation: both compilers now reserve bare `:> <P>` for `$proof`.
Ordinary fact procedures use `:> void & <P>`. The HIR keeps explicit proof
flags rather than inferring erasure from refined `void`.
This restriction concerns fact blocks, not ordinary type blocks such as a
function-handle result `:> <(x:int64):>int64>`.
The existing exit-obligation machinery can be shared, but proof declarations
and proof-call statements must remain distinguishable in checked IR from
ordinary `void` functions. Do not infer proof status from a refined `void`
result or erase an ordinary call merely because it has the same fact.

David approved this direction with these restrictions on 2026-09-20.
General first-class proof values remain out of scope. The earlier
`$lemma`/body-`$proves` shape is discarded.

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
- A written positive row is an upper bound: inferred behavior must be a
  subset. Listing an effect permits it; it does not require it to occur.
- David selected `& no_effects` for the explicit empty row, with `Effect<>`
  as its desugared spelling. It permits no effects. This replaces the
  earlier `Effects<never>` / `Effects<none>` alternatives.
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

### Negative guarantees — approved initial rules

David proposed `no effectname`, e.g. `no reads<filesystem>`. Treat this as
an exclusion constraint on the inferred row, not the complement of an
effect set. It promises absence without granting every other effect:

```dewy
pure = (...):> Result & no_effects => ...
local_work = (...):> Result & no reads<filesystem> => ...
```

`local_work` may have other effects, which are inferred and propagated. The
checker must establish absence of filesystem reads through its whole call
graph, including callbacks. An unknown indirect call cannot satisfy an
exclusion without a compatible signature contract. Resource aliasing must
not let a filesystem read evade the constraint under a different name.

David approved these initial surface rules in the follow-up review on 2026-09-20:

| Annotation | Meaning |
| --- | --- |
| `no_effects` | The complete row is empty. |
| `reads<filesystem>` | Permit this read effect within the written positive upper bound. |
| `no reads<filesystem>` | Forbid this read effect; infer the rest if no positive bound is written. |
| `no reads` | Forbid the whole read family; infer other effect families. |
| `reads<>`, `no reads<>` | Reject with a diagnostic suggesting `no reads` or `no_effects`. |

Positive bounds and exclusions are checked together: the inferred row must
fit the bound and avoid every excluded effect. A row containing only
exclusions remains open to inferred effects outside those exclusions. This
does not weaken the earlier closed-upper-bound rule for positive rows.

Rejecting the empty family spelling avoids a trap: if `reads<>` denotes an
empty set, then excluding that set with `no reads<>` forbids nothing. It
cannot mean “no reads.” Bare `reads` is a family, not an implicitly
parameterized positive row; require subjects in positive `reads<...>` forms.
The internal empty row `Effect<>` is distinct from instantiating an effect
family with no subjects. Future effect-polymorphic elaboration may produce
empty rows without exposing this ambiguous source shorthand.

Still to review: how effect identities and effect parameters should be
introduced. Allocation
failure policy remains separately tentative; this proposal does not choose
`$fallible_allocation`, error identities, or an exit code on its behalf.
