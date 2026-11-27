# Branching and Flow Control

This chapter covers the ways a program chooses: `if`, comparisons, `match`, and the logic words `and`, `or` and `not`. Repetition is in [Loops](loops.md).

## if and else

An `if` takes a condition and a body. The body is a `{ ... }` block, or a single statement with no braces.

<!-- dewy-example: {"mode": "run", "stdout": "high\n"} -->
```dewy
let score = 42
if score >? 40 { printl"high" } else { printl"low" }
if score >? 100 printl"off the chart"
```

`if` is an expression, so it can give a value. That replaces Python's conditional expression and C's `?:`. Chain with `else if`:

<!-- dewy-example: {"mode": "run", "stdout": "medium\n"} -->
```dewy
let n = 7
let size = if n <? 5 "small" else if n <? 10 "medium" else "large"
printl(size)
```

## Comparisons end in `?`

Every comparison is spelled with a question mark: `=?` equal, `<?` less, `>?` greater, `<=?` and `>=?`. A plain `=` is always an assignment, so `if x = 3` can never be a typo for a test.

To say "not equal", put `not` in front of the comparison. `n not =? 3` is the same thing, written the way you would say it.

<!-- dewy-example: {"mode": "run", "stdout": "not three\nstill not three\n"} -->
```dewy
let n = 7
if not n =? 3 printl"not three"
if n not =? 3 printl"still not three"
```

Comparisons chain, so a range check reads like the maths:

<!-- dewy-example: {"mode": "run", "stdout": "inside\n"} -->
```dewy
let n = 7
if 0 <? n <? 10 printl"inside"
```

The middle operand is evaluated once. A chain keeps one direction: `0 <? n <? 10` is fine, `0 <? n >? 3` is an error.

## and, or, not

Combine conditions with the words `and`, `or` and `not`. `and` and `or` stop as soon as the answer is known, so the right side of `and` only runs when the left side was true.

<!-- dewy-example: {"mode": "run", "stdout": "yes\n0\n"} -->
```dewy
let calls = 0
tick = ():>bool => { calls += 1; true }
if false and tick() printl"no"
if true or tick() printl"yes"
printl(calls)
```

`tick` never ran. `not` binds below the comparisons, so `not x =? y` means `not (x =? y)`, and `and` binds tighter than `or`.

### Short-circuit assignment

`or=` assigns only if the current value is false, and `and=` only if it is true. The right side runs only when the assignment happens.

<!-- dewy-example: {"mode": "run", "stdout": "1\n1\nfalse\n"} -->
```dewy
let calls = 0
tick = ():>bool => { calls += 1; true }
let ready = false
ready or= tick()      # was false: runs tick
printl(calls)
ready or= tick()      # already true: skipped
printl(calls)
ready and= 1 >? 2
printl(ready)
```

## match

`match` compares a value against patterns and gives the value of the first arm that fits. A literal goes in angle brackets, `|` joins alternatives inside them, and `_` takes everything else.

<!-- dewy-example: {"mode": "run", "stdout": "seven\nvowel\n"} -->
```dewy
let n = 7
let kind = match n {
    <1> => "one"
    <7> => "seven"
    _ => "other"
}
printl(kind)

let c = 'e'
printl(match c { <'a'|'e'|'i'|'o'|'u'> => "vowel" _ => "consonant" })
```

An arm can also name a type, which is how you take apart a value that might be one of several types, such as an optional. [Optional Values and Narrowing](optional-types.md) shows that form. A `match` over a closed set of types or literals does not need `_` when every case is covered, and the compiler tells you when one is missing.

For a numeric range, test with `in?` and an `if`, covered in [Ranges](range-types.md).

The [reference](/reference/control-flow-and-iteration.html) has the complete rules.
