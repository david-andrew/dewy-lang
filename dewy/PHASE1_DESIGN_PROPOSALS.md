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
$unsafe_assume i <? xs.length, 'the external producer validated this index'
```

`$assert` already implements the checked boundary: proven assertions erase,
refuted assertions fail, and unknown assertions fail with a different
explanation. There is no reason to add a synonymous `$prove` directive.
The proof-engine work should improve the facts `$assert` can establish.

`$unsafe_assume P` introduces that one assumption without a runtime check
or a proof. Its optional message follows
`$assert`'s compile-time string-literal rule and supplies an audit explanation.
The directive owns the separating comma, just as `$assert` does. It emits an
auditable entry naming the proposition, message, source location, and
obligations it discharges. It neither weakens unrelated checking nor disables
checking for a block. David confirmed `$unsafe_assume` in the follow-up review
on 2026-09-20. It supersedes the intermediate `$unsafe_assert` spelling,
which suggested a checked assertion rather than an explicit assumption.

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
David approved rejection of proven-false assumptions on 2026-09-20. Known
contradictions fail with `assertion refuted`, including contradictions derived
from incoming facts. Unknown assumptions are accepted and audited; the checker
does not confuse a missing proof with a proof of falsity.

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
  enumerating every effect in higher-order library code. The reviewed `E:Effect` syntax below keeps row parameters separate from
  ordinary `type` parameters.
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

Resource identities and effect parameters use the reviewed forms below. Allocation
failure policy remains separately tentative; this proposal does not choose
`$fallible_allocation`, error identities, or an exit code on its behalf.

### Resource identities and effect parameters — approved initial rules

Reuse nominal type mints for named resources. An effect subject can resolve
to a nominal type identity or an eligible parameter/place route, never just a
string spelling:

```dewy
Filesystem = type of any
read_count = (...):> int64 & reads<Filesystem> => ...
update = (@state:State):> void & mutates<state> => ...
```

`Filesystem` is an ordinary nominal marker. Aliases/imports of that marker
preserve its identity; a second `type of any` mint is distinct, even if it has
the same source name. An effect subject is not an instance of the marker.
Initially match named resource identities exactly; do not invent effect
implications from nominal inheritance. Parameter routes resolve to binding
identities and substitute at calls, using the existing alias analysis.
The standard effect families are compiler vocabulary; custom effect-family
declarations are outside this initial proposal.

For row polymorphism, use a separately kind-checked generic parameter:

```dewy
apply = <E:Effect>(f:():>int64 & E):> int64 & E => f()
```

Here `Effect` names the kind of effect rows. `E` ranges over rows, including
the empty row, and cannot appear in a value-type position. `Effect<>` remains
the empty row itself, with `no_effects` as the preferred source spelling.
Infer `E` from the callback's signature; substitute it into the caller's row.
Unknown callback behavior cannot be inferred as empty. This introduces no
first-class runtime effect values. The same positive-bound/exclusion rules
apply after substitution.

### What allocation contracts measure — approved initial rules

Keep public effects distinct from internal per-parameter access summaries.
Reading an ordinary by-value argument or updating a private local is not an
external read/write effect. Reading or changing caller-owned place storage
is, as are accesses to named resources. Internal route summaries still track
all reads/writes needed to justify borrowing and preserve facts.

An allocation guarantee must account for the logical storage operations left
after proven borrowing, moves and static/stack placement, including implicit
aggregate copies. Do not hide an allocation effect merely because the
provisional COW implementation defers its physical allocation. Inference may
be conservative; unknown allocation behavior cannot satisfy `no_effects`.
For example, a read-only `xs.length` function can borrow its argument and
have no effects, while returning `xs.copy()` for a runtime-length array
requires permission to allocate even if a particular COW execution only
retains its buffer. Source contracts should not accidentally promise that
later COW detachment cannot occur. This proposal does not settle allocation
failure behavior or the resource-exhaustion policy.

David approved these starting rules on 2026-09-20. Both compilers now have
a separate public row representation and check explicit empty rows, named
resource contracts and negative source rows for a conservative initial subset.
Effect-row generic parameters now support callback-row inference and
substitution in both compilers. The initial conservative limits are documented
in the reference: no arbitrary split between multiple row remainders, no
callback-relative place subjects escaping their signature, and no inferred
negative row arguments yet. A future builtin `resource` base type could make resource mints
more explicit; ordinary nominal mints suffice for this first implementation.
The allocation rule remains open to refinement from practical experience.

### Allocation permission spelling — approved initial rules

David approved bare `allocates` and `no allocates`, initially without resource
arguments, on 2026-09-20. The approved measurement rule above remains unchanged:

```dewy
# Permit allocation; other behavior must still meet the rest of the row.
snapshot = (xs:array<int64>):> array<int64> & allocates => xs.copy()
# Exclude allocation while leaving other effects inferred.
inspect = (xs:array<int64>):> int64 & no allocates => xs.length
```

`allocates` is initially an unparameterized may-effect for compiler-managed
storage. `no allocates` excludes it. Reject `allocates<>` and
`allocates<SomeResource>` for now: no reviewed allocator/resource mapping yet
justifies pretending that a user-minted marker selects the compiler's arena.
This does not change the required subjects of `reads<Resource>` or
`mutates<place>`, and introduces no builtin resource type.

The positive spelling permits an allocation rather than requiring one.
Borrowed reads, proven moves and static/stack placement remove the corresponding
storage obligation; logical copies still count when COW merely postpones them.
A result's fixed size alone does not establish stack placement or independence
from the caller. Unclassified storage operations remain unknown, not pure.
The example describes the allocation portion of its contract; a future
separately checked failure effect may also need permission depending on the
allocator's settled failure policy. This spelling proposal neither grants a
no-failure guarantee nor settles that policy.
