# Integer ranges, round 1: `.length` and `.reversed`

Arrays have `xs.length` and `xs.reversed`. A stored integer range, `[0..n)`, has neither: probed at this
HEAD, `[0..5).length` is "IntRange has no field 'length'" and `[0..5).reversed` is "IntRange has no
field 'reversed'". Nothing in `docs/design/` or `resources/discussion_points.md` gives ranges members
(the notes there only discuss range syntax: no spaces, stepped-range precedence, and indexing), so the
design is open. Ladder 153 shows the cost: its dynamic-programming table walks backwards with
`loop p in [pieces.length - 1, pieces.length - 2..0]` and `loop t in [n, n - 1..0]`, which repeat the
bound and spell the first element as arithmetic. This round proposes the two members, dogfoods them on
thirteen programs and grades them. The result is open decision D53.

## The proposal

```dewy
loop p in [0..pieces.length).reversed { ... }     # was [pieces.length - 1, pieces.length - 2..0]
loop t in [0..n].reversed { ... }                 # was [n, n - 1..0]
let pages = [0, size..total).length               # 10 for size 10, total 95
```

- `r.length` is the number of elements the range yields, an exact `int` that is `>=? 0`. Facts narrow it
  as for any `int` (`[0..xs.length).length` is at most `xs.length`). Exact, because the full signed-word
  range `[min..max]` has 2^64 elements, which no 64-bit count holds.
- `r.reversed` is the same elements in the opposite order, and it is a range (`IntRange`), not an array.
  A range can express every reversal: it starts at the last element and steps by the negated step.
- Forms: `[0..5)` has 5 elements and reversed yields 4 3 2 1 0 (`[4, 3..0]`); `[0..5]` has 6; `(0..3]`
  has 3 and reversed yields 3 2 1; `[0, 3..10)` has 4 and reversed yields 9 6 3 0; `[10, 7..0]` has 4
  and reversed ascends 1 4 7 10; `[5..0]` is empty, has length 0, and reversed is empty. A reversed
  range reversed again has the first one's elements.
- A reversed range is lazy like any other: no array, constant storage, independent cursors, so it works
  where a stored range does: `loop`, `and` headers, `x in? r`, `xs[r]`, and a parameter `r:IntRange`.
- Only integer ranges. `Range<Instant>` and the other ordered ranges cannot be walked and have no count
  (`intervals.measure` is theirs).

## Why a range, not an array

An array would allocate, lose `xs[r]` selecting by a stored range, no longer be an `IntRange` where one
is asked for, and break `and` headers (`loop i in [0..n) and j in [0..n).reversed`). The array's
`xs.reversed` is a new array because an array is already a stored list; a range is a recipe, and its
reverse is another recipe. Programs 6, 8 and 13 below exist because of this; in pass 1 `.reversed`
returned an array and each scored 3 or 4.

## Two-question test

1. The common path: counting and walking down. Today the descent is `[n - 1, n - 2..0]`, repeating the
   bound; the length of a stepped range is a loop that counts.
2. Adjusting today is that arithmetic, which is correct but easy to get off by one at `)` versus `]`
   and which can hide an empty array (`[-1, -2..0]`). Natural enough to ask about, not enough to
   change anything decided. It is an additive member on an existing type, type (b). Both names exist
   on arrays, so no cold-read test is needed.

## Peers

| Language | Count and reversed walk of `0..n` |
|---|---|
| Python | `len(range(n))`, `reversed(range(n))`: both work, `reversed` gives a range-like iterator |
| Go | no ranges: `for i := n - 1; i >= 0; i--`; count is arithmetic |
| Rust | `(0..n).len()`, `(0..n).rev()`: both exact, lazy |
| TypeScript | no ranges: a loop or `Array.from({length: n}).reverse()` |
| Swift | `(0..<n).count`, `(0..<n).reversed()`, lazy for ranges |

Python, Rust and Swift all give a range both members and return a lazy reversed range. Dewy matches
them, with an exact count where theirs wraps or traps at the extremes (Rust's `len` is `usize`, which
cannot hold a full `i64` range).

## Dogfooding

Thirteen realistic programs. Grades 1–5 on obvious, discoverable, concise, safe by default and
complete (O D C S Co), against Python, Go, Rust, TypeScript and Swift. Where a program scored under 5
in pass 1, the proposal changed (marked "pass 1"), and it was graded again.

### 1. Backward dynamic-programming table (ladder 153)

```dewy
loop p in [0..pieces.length).reversed {
    loop t in [0..n].reversed {
        can[p][t] = ...
    }
}
```

5 5 5 5 5. No `- 1`, no `- 2`: the bounds read as the table's own. For an empty `pieces` the loop
does nothing, which `[-1, -2..0]` also does but by accident of the sign.

### 2. Countdown

```dewy
loop i in [1..10].reversed { printl(i) }
printl("liftoff")
```

5 5 5 5 5. The inclusive `]` says 10 prints; Python needs `range(10, 0, -1)`.

### 3. Binary digits, high bit first

```dewy
bits = (v:uint8):>string => [loop b in [0..8).reversed if ((v >> b) and 1) =? 1 "1" else "0"].join("")
```

5 5 5 5 5. Today `[7, 6..0]`, with the `7` standing for "8 minus 1". Verified shape on this HEAD with
the stepped form, which prints `00100101` for 37.

### 4. How many pages

```dewy
pages = (total:int64 size:int64<(>? 0)>):>int => [0, size..total).length
```

Pass 1: 4 3 5 3 4: `.length` returned `uint64`, and the full-range case does not fit; a stepped
range with a computed step also needs its step proven nonzero, which the signature now says. Change:
`.length` is an exact `int`. After it: 5 5 5 5 5. Replaces `(total + size - 1) // size`, whose
rounding is the thing readers check twice.

### 5. Every other row, from the bottom

```dewy
loop r in [0, 2..rows).reversed { draw_row(r) }
```

5 5 5 5 5. Rows 0, 2, 4, 6 of seven, drawn 6, 4, 2, 0. Today the descent starts at the last element, which depends on the
parity of `rows`, so the code needs a branch; reversing the set is the right meaning.

### 6. Select the first three, newest first

```dewy
let newest = values[[0..3).reversed]       # values[2, 1..0] today
```

Pass 1 (`.reversed` an array): 4 5 4 5 3, since an array of indexes copies and a range does not select
as a slice. As a range, the existing `values[IntRange]` rule applies. After the change: 5 5 5 5 5.

### 7. Insertion sort's inner step

```dewy
loop j in [1..i].reversed {
    if xs[j - 1] <=? xs[j] break
    xs.swap(j - 1 j)
}
```

5 5 5 5 5. The range says `j` runs from `i` down to 1; the bounds of `xs[j - 1]` and `xs[j]` come
from the range's ends, as for any inclusive loop.

### 8. Walk either way

```dewy
walk = (r:IntRange down:bool):>int64 => {
    let total:int64 = 0
    loop i in (if down r.reversed else r) { total = total * 10 + i }
    total
}
```

Pass 1: with an array result the two arms differ in type and the `if` needed a conversion: 3 4 3 4 3.
As a range both arms are an `IntRange`: 5 5 5 5 5.

### 9. Frames in an animation

```dewy
let frames = [0, 16..duration_ms].length         # one per 16ms, both ends included
```

5 5 5 5 5. An inclusive stepped range counts its endpoint when it lands on it.

### 10. Multiples of seven in a span

```dewy
let first = a + (7 - a % 7) % 7
let count = [first, first + 7..b].length
```

5 5 5 5 5. Empty when `first >? b`: the range is empty and `.length` is `0`.

### 11. Ranking from the last place up

```dewy
loop place in (0..n].reversed { printl"{place}: {names[n - place]}" }
```

5 5 5 5 5. `(0..n]` reversed is `n, n-1..1`, the exclusive first end stays excluded.

### 12. Palindrome by two cursors

```dewy
is_palindrome = (cs:array<string>):>bool => {
    loop a in [0..cs.length) and b in [0..cs.length).reversed {
        if a >=? b return true
        if cs[a] not=? cs[b] return false
    }
    true
}
```

Pass 1 (array result): `and` headers need stored ranges: 2 4 3 4 2. As a range: 5 5 5 5 5. (A
shorter form is `cs =? cs.reversed`; the loop is the one that exits early.)

### 13. The edges

```dewy
[0..0).length                 # 0
[5..0].length                 # 0
[0..0).reversed.length        # 0
[-9223372036854775808..9223372036854775807].length    # 18446744073709551616, an int
```

5 5 5 5 5. Empty ranges stay empty after reversing, and the full range counts exactly.

### Summary

All 65 marks at 5 after two pass-1 changes: `.length` is an exact `int` (program 4) and `.reversed` is a
range (programs 6, 8, 12). Python, Rust and Swift give both members; Go and TypeScript have no
ranges and do it by arithmetic. The old forms in programs 1, 3 and 6, an empty `[5..0]`, and the missing members were
probed on this HEAD; the new members do not exist yet.

## Not proposed

- `.first`, `.last` and `.is_empty` on ranges: ranges have none today either. They are a separate
  question (an empty range's `first` is `none`, an optional), and no program above needed them.
- `.reverse()` in place: a range is a value.
- Array `.reversed` stays a new array, as LANGUAGE.md says. (LANGUAGE.md writes it `xs.reversed()` and
  the compiler warns "drop the `()`"; the doc line wants the parentheses removed.)
