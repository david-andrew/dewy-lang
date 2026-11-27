# Ranges

A range is a value that stands for a run of numbers. You write it with `..`, and you meet it most often in loops, slices and membership tests.

## Both ends are included

A bare `a..b` includes both ends. That differs from Python's `range`, but matches how people count: `1..3` is one, two, three.

<!-- dewy-example: {"mode": "run", "stdout": "1\n2\n3\n"} -->
```dewy
loop value in 1..3 { printl(value) }
```

## Say which ends are in

Square and round brackets say, for each end, whether it is included (square) or left out (round). `[0..n)` is the Python `range(n)`:

<!-- dewy-example: {"mode": "run", "stdout": "0 1 2 3 \n1 2 \n1 2 3 \n"} -->
```dewy
let n = 4
loop i in [0..n) print"{i} "
printl""
loop i in (0..3) print"{i} "
printl""
loop i in (0..3] print"{i} "
printl""
```

The end can be a runtime value, as `n` is here. Write `[0..xs.length)` to visit every index of an array.

## Steps

Give the first two values and the range continues at that distance. The pair is written with a comma:

<!-- dewy-example: {"mode": "run", "stdout": "1 3 5 7 9 \n5 4 3 2 1 0 \n"} -->
```dewy
loop i in 1,3..9 print"{i} "
printl""
loop i in 5,4..0 print"{i} "
printl""
```

A range never turns around by itself. `5..0` is empty. To count down, give it a negative step as above.

A range with a step is also a value you can collect into an array, with a loop inside brackets:

<!-- dewy-example: {"mode": "run", "stdout": "[0 2 4 6 8 10]\n"} -->
```dewy
printl([loop i in 0,2..10 i])
```

## Open ranges

Leave off the end and the range goes on forever. It is the natural partner of a finite iterator, since the loop stops when the finite side runs out:

<!-- dewy-example: {"mode": "run", "stdout": "0a\n1b\n2c\n"} -->
```dewy
loop i in 0.. and c in "abc" printl"{i}{c}"
```

An open start, as in `..5`, is a valid range for slicing and for tests, but cannot be looped over, because there is no first value.

## Membership

`in?` asks whether a value is inside a range. It respects open and closed ends and the step:

<!-- dewy-example: {"mode": "run", "stdout": "true\nfalse\ntrue\nfalse\n"} -->
```dewy
let age = 30
printl(age in? 18..65)
printl(5 in? [1..5))
printl(5 in? (1,3..9))
printl(4 in? (1,3..9))
```

That makes `in?` the tidy way to test an interval: `if age in? 18..65 ...`.

## Slices

A range in `[]` takes a piece of an array or string. Inside the brackets, `end` means the last valid index:

<!-- dewy-example: {"mode": "run", "stdout": "[20 30 40]\n[20 30 40 50]\n[10 20 30]\nell\newy\n"} -->
```dewy
xs = [10 20 30 40 50]
printl(xs[1..3])
printl(xs[1..end])
printl(xs[..2])
printl("hello"[1..3])
printl("dewy"[1..end])
```

Because the bare form includes its end, `xs[1..3]` has three elements. Use `[1..3)` for the half-open slice you know from Python: `xs[[1..3)]` is `[20 30]`.

The [reference](/reference/ranges-and-iteration.html) has the complete rules.
