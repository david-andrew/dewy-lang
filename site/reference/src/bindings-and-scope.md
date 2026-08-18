# Bindings and scope

`let` creates a mutable binding and `const` creates a binding that cannot be
assigned after initialization. An assignment to a name with no visible binding
implicitly creates a `let` binding; otherwise it reassigns the visible binding.

```dewy
let mutable = 1
const fixed = 2
inferred = 3
mutable += fixed
```

Bindings have lexical identity. Nested scopes can shadow outer names. Eager
expressions cannot read a binding before initialization. Function bodies may
refer to later declarations, but initialization requirements are checked at
each reachable call site.

Non-capturing local functions lower by hoisting. Capturing local functions are
analyzed but closure lowering is not yet implemented.
