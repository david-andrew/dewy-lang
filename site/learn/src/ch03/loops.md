# Loops and Multiple Iterators

Dewy has one loop. `loop` followed by a condition repeats while the condition holds; `x in xs` is a condition that binds the next value and is false when there are none left.

<!-- dewy-example: {"mode": "run", "stdout": "15\n4\n"} -->
```dewy
let total = 0
loop value in 1..5 { total += value }
printl(total)

let n = 100
let halvings = 0
loop n >? 10 {
    n = n // 2
    halvings += 1
}
printl(halvings)
```

Because `in` is just a condition, iterators combine with `and` and `or`. With `and` the loop stops when either side runs out, which numbers a sequence without an `enumerate` helper:

<!-- dewy-example: {"mode": "run", "stdout": "0: red\n1: green\n2: blue\n"} -->
```dewy
colors = ["red" "green" "blue"]
loop i in 0.. and c in colors printl"{i}: {c}"
```

`break` leaves a loop and `continue` starts the next pass; a label such as `$outer` lets either name an enclosing loop. A loop inside brackets collects its values into an array, and an `if` inside it filters:

<!-- dewy-example: {"mode": "run", "stdout": "[1 9 25 49 81]\n"} -->
```dewy
odd_squares = [loop i in 1..10 if i % 2 =? 1 i * i]
printl(odd_squares)
```

A loop over an array iterates the value the array had when the loop started, so changing the array inside the body is safe. `loop x in @xs` iterates the live array instead, and lets the body update each element in place.

The [reference](/reference/ranges-and-iteration.html) has the complete rules.
