# Control flow and iteration

`if`, `else if`, and `else` form an ordered conditional. An exhaustive
conditional can produce a scalar value; a non-exhaustive conditional produces
`void`.

`loop` covers Boolean repetition and iterator consumption. `break` and
`continue` can target an enclosing loop through a scope metatag label.

```dewy
loop i in 0..10 {
    if i =? 5 { continue }
}
```

Static integer ranges support inclusive and explicit open bounds, descending
steps, and `first,second..last` notation. Multiiterators combine static range
iterators using `and`, `or`, `xor`, `nand`, `nor`, or `xnor`. Iterator leaves
advance eagerly from left to right once per condition evaluation.
