# Operators

Most operators work as you expect. This chapter lists what differs from Python, C and JavaScript.

## Arithmetic

`+`, `-` and `*` are the usual. Whole numbers are exact and do not overflow by default, so `2 ^ 100` is just the number.

<!-- dewy-example: {"mode": "run", "stdout": "9\n14\n1024\n1267650600228229401496703205376\n"} -->
```dewy
printl(7 + 2)
printl(7 * 2)
printl(2 ^ 10)
printl(2 ^ 100)
```

`^` is the power operator, not xor. It groups to the right and binds tighter than `*`, and a leading minus applies after it: `-2 ^ 2` is `-4`.

### Division

Three operators divide, and each answers a different question.

- `/` on whole numbers gives an exact fraction. Nothing is lost to rounding. If either side is a float, the result is a float.
- `//` divides and rounds down to a whole number.
- `%` is the remainder that goes with `//`.

<!-- dewy-example: {"mode": "run", "stdout": "7/2\n3\n1\n3.5\n1/2\n"} -->
```dewy
printl(7 / 2)
printl(7 // 2)
printl(7 % 3)
printl(7.0 / 2)
printl(1/3 + 1/6)
```

`//` and `%` round toward minus infinity, the same as Python and unlike C. The remainder takes the sign of the divisor, so `%` never surprises you when counting around a ring:

<!-- dewy-example: {"mode": "run", "stdout": "-4\n2\n"} -->
```dewy
printl((-7) // 2)
printl((-7) % 3)
```

`//` and `%` are for whole numbers only; a float is an error. To floor a float quotient, write `(a / b).floor()`.

### Updating a variable

Every arithmetic operator has an assigning form: `+=`, `-=`, `*=`, `//=` and so on.

<!-- dewy-example: {"mode": "run", "stdout": "3\n"} -->
```dewy
let x = 10
x -= 3
x *= 2
x //= 4
printl(x)
```

## Comparison

`=?`, `<?`, `>?`, `<=?` and `>=?` compare, and `not` before one negates it. Chains like `0 <? x <? 10` work. [Branching and Flow Control](flow-control.md) covers them with `if`.

## Logic

`and`, `or` and `not` combine true/false values and short-circuit. `xor` is there too.

## One operation, two spellings

`&`, `|` and `~` are the symbol forms of `and`, `or` and `not`. They are the same operation, so on true/false values they agree, and on whole numbers they work on the bits:

<!-- dewy-example: {"mode": "run", "stdout": "2\n7\n-1\nfalse\ntrue\n"} -->
```dewy
printl(6 & 3)
printl(6 | 3)
printl(~0)
printl(true & false)
printl(true | false)
```

The two spellings differ only in how tightly they bind. The symbols bind tighter than the comparisons and the words bind looser. That makes each one natural for its own job: symbols for masks, sets and types (`flags & MASK =? 0`, `x is? int|string`), words for logic over comparisons (`x >? 0 and y <? 10`). Writing `x >? 0 & y >? 0` is the one mix-up to avoid; use `and`.

Shifts are `<<` and `>>`:

<!-- dewy-example: {"mode": "run", "stdout": "16\n64\n"} -->
```dewy
printl(1 << 4)
printl(256 >> 2)
```

## Precedence

From tightest to loosest, the levels you will meet most:

1. member access, calls and indexing: `a.b`, `f(x)`, `xs[i]`
2. `~`
3. `^`
4. `*` `/` `//` `%`
5. `+` `-`
6. shifts
7. ranges `a..b`
8. `&`, then `|`
9. comparisons, `is?`, `in?`
10. `not`, then `and`, then `xor`, then `or`
11. `as`, `=>`, `|>`, and assignment last

When in doubt, add parentheses. They only group, they cost nothing, and `(80+4)//2` says what it means.

## Operator sections

A binary operator with only its right side, in parentheses, is a function of the missing left side. `(* 2)` means `x => x * 2`, and `(>? 4)` means `x => x >? 4`. They are handy where a function is expected:

<!-- dewy-example: {"mode": "run", "stdout": "[10 20 30]\n[5 9]\n"} -->
```dewy
printl([1 2 3].map((* 10)))
printl([1 5 9].filter((>? 4)))
```

Only operators with no prefix meaning work this way. `(- 1)` is minus one, not "subtract one".

The [reference](/reference/operators-and-precedence.html) has the complete rules.
