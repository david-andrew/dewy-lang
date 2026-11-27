# Refinements

A refinement is a condition a type carries. Inside the function the condition is a known fact; at each call the compiler proves it from literals and control flow, and rejects a call that provably breaks it. A condition written as a single comparison uses a partial operator such as `(>? 0)`.

<!-- dewy-example: {"mode": "run", "stdout": "7\n42\n"} -->
```dewy
span = (a:int b:int<(>=? a)>) => b - a
share = (total:int n:int<(>? 0)>) => total // n
printl(span(3 10))
printl(share(84 2))
```

Passing a value that provably breaks the condition is a compile error:

<!-- dewy-example: {"mode": "reject", "diagnostic": "refinement refuted"} -->
```dewy
share = (total:int n:int<(>? 0)>) => total // n
printl(share(84 0))
```

When the argument comes from somewhere the compiler cannot see, such as user input, a guard supplies the fact:

<!-- dewy-example: {"mode": "run", "stdout": "21\ncannot share among 0\n"} -->
```dewy
share = (total:int n:int<(>? 0)>) => total // n

loop people in [4 0] {
    if people >? 0 printl(share(84 people)) else printl"cannot share among {people}"
}
```

Lengths can be refined too: `array<int length >? 0>` is a non-empty array, so reading its first element needs no check. A name for a refined type reads well in signatures:

<!-- dewy-example: {"mode": "run", "stdout": "3\n"} -->
```dewy
NonEmpty:type = array<int length >? 0>
first = (xs:NonEmpty) => xs[0]
printl(first([3 5 8]))
```

`$runtime_assert condition` checks a condition while the program runs and stops with a report if it fails; after it, the compiler knows the condition holds. `$assert condition` must be proven while compiling and never costs anything at run time.

The [reference](/reference/refinements-and-effects.html) has the complete rules.
