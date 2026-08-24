# Refinements, Effects, and Safety

This area has a settled semantic direction and a provisional general syntax. The rules below constrain the eventual design; they do not authorize arbitrary expressions as refinements or effects.

## Refinements

A refinement combines a base type with facts every value of that type satisfies. Exact array length is a concrete instance:

```dewy
array<int64 length=3>
```

Refinement facts may arise from annotations, literals, ordinary control-flow conditions, successful explicit checks, and trusted interfaces.

```dewy
if index >=? 0 and index <? values.length
    use(values[index])
```

Inside the body, the index relationship is available to prove the access valid. Mutation and calls invalidate any fact they may falsify.

The general proposition language must be a deliberately bounded, decidable fragment. Unsupported Dewy expressions produce an unknown proof result or a diagnostic; they do not silently enter refinement checking as trusted predicates.

## Operation Preconditions

An ordinary partial operation is valid when its precondition is proven. Examples include indexing within bounds, dividing by a nonzero value, narrowing a number into a smaller representation, and satisfying a function's refined input contract.

When a fact cannot be proven statically, the program chooses an explicit checked operation, establishes the fact with control flow, supplies a checked proof, or crosses an explicit `unsafe` boundary. The compiler must not insert a hidden semantic fallback that changes the operation's type.

## Effects

An effect describes observable behavior relevant beyond a function's return value. The intended effect model covers at least mutation, allocation, blocking, I/O or host capability access, failure, nonreturning control flow, and escape of storage or handles.

Effects propagate through calls. A caller may preserve a refinement or borrow storage only when the callee's effects prove that behavior safe. Unresolved indirect calls require a conservative effect contract.

`noreturn` is a settled effect used by a function that cannot return to its caller. It is distinct from the `never` result type.

## `unsafe`

`unsafe` identifies a proof or memory-safety obligation the compiler has not established. It is an auditable trust boundary, not a request to turn off unrelated checking.

## Provisional Boundary

The complete proposition grammar, qualifier inference, proof-value form, effect vocabulary, effect polymorphism, checked-failure model, and surface syntax for `unsafe` remain provisional. See [Design Maturity](design-status.md).
