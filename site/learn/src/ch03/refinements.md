# Refinements

A type can carry extra facts such as a length, a range, or a field that is never a certain string. Those facts are refinements. The compiler can automatically prove many of them in ordinary code.

## Writing a Refinement

Any type may take a block `T<...>`. Conditions in that block are what the compiler must prove.

```dewy
NonEmptyArray = array<length>?0>

MyStruct:type = [a:int b:bool c:string]< a>?10 b=?true c not=? 'apple' >
```

An assignment in the block is a shorthand for a constant field:

```dewy
SingleValuedArray = array<length=1>    # same as array<length=?1>
```

A top-level `?`-comparison, function, or assignment is a refinement condition. Every other expression is a parameter value, so a literal boolean does not need extra wrapping:

```dewy
trues:array<true length=5> = [true true true true true]
```

Integer types can be ranged the same way. See [Basic Data Types](basic-data-types.md). What happens if a value leaves a custom integer range is not yet determined.

> Not all Dewy expressions are supported for refinements. The allowed conditions are booleans, equality and ordering, adding and subtracting integers, tests against literals and tags, lengths, and simple relationships between inputs and results. Function calls are allowed when inlining them would result in a valid refinement.

## How the Compiler Accepts a Refinement

- If the compiler can prove it, there is no extra work at run time.
- An explicit check, including leaving early on the failing case (`if not condition { return }`), lets later code treat the value as refined.
- You can also supply a checked proof for something the compiler could not prove on its own. (TBD the structure of such proofs)
- `unsafe` is for when the refinement cannot be proven, but the programmer knows it is true. It tells the compiler to take the claim on trust. That stays a place to audit.

The exact set of conditions the compiler can prove on its own is not yet determined. Arbitrary calls, open-ended "for all" claims, code with side effects, and general nonlinear arithmetic are outside what it handles automatically.
