# Array-literal fixtures — round 2, option B

Expected results under option B. `1-D` means `array<T>` with no shape, `.length` the count. `length=[…]` is n-D, `.length` that shape, outermost axis first. `nested` means `array<array<…>>`, `.length` the outer count. A trailing note marked **A** is what option A would do instead, and only where they differ.

`⏎` is a line break. `⏎⏎` is a blank line.

## Scalar grid

| # | Literal | Result |
|---|---|---|
| 1 | `[1 2 3]` | 1-D `[1 2 3]`, length 3 |
| 2 | `[1⏎2⏎3]` | 1-D `[1 2 3]`, length 3 |
| 3 | `[⏎1 2 3⏎]` | 1-D `[1 2 3]`, length 3 |
| 4 | `[1; 2; 3]` | 1-D `[1 2 3]`, length 3 |
| 5 | `[1;2;3]` | 1-D `[1 2 3]`, length 3 |
| 6 | `[1 ;; 2]` | 1-D `[1 2]`, length 2 |
| 7 | `[1 ;;]` | 1-D `[1]`, length 1 |
| 8 | `[1 ;]` | 1-D `[1]`, length 1 |
| 9 | `[1 2⏎3 4]` | `[1 2 3 4]`, `length=[2 2]` |
| 10 | `[1 2 ; 3 4]` | `[1 2 3 4]`, `length=[2 2]` |
| 11 | `[1 2;3 4]` | `[1 2 3 4]`, `length=[2 2]` |
| 12 | `[1 2 3 ;]` | `[1 2 3]`, `length=[1 3]` |
| 13 | `[1 2 ; 3 4 ;]` | `[1 2 3 4]`, `length=[2 2]` |
| 14 | `[1 ; 2 ;]` | 1-D `[1 2]`, length 2 |
| 15 | `[1 ; 2 ;;]` | `[1 2]`, `length=[1 2]` |
| 16 | `[1 2 ; 3 4 ;; 5 6 ; 7 8]` | `[1 2 3 4 5 6 7 8]`, `length=[2 2 2]` |
| 17 | `[1 2⏎3 4⏎⏎5 6⏎7 8]` | `[1 2 3 4 5 6 7 8]`, `length=[2 2 2]` |
| 18 | `[1 2 ;; 3 4]` | error: skipped separator level: levels 0 and 2 appear, and level 1 does not |
| 19 | `[1 ; 2 ;; 3]` | error: the rows of an array literal must have the same size: this one has 1 element, the first has 2 |
| 20 | `[1 2 ; 3 4 ; 5]` | error: the rows of an array literal must have the same size: this one has 1 element, the first has 2 |
| 21 | `[1 2 ; 3 4 ;; 5 6]` | error: the blocks of an array literal must have the same size: this one has 1 row, the first has 2 |
| 22 | `[;]` | error: an array literal cannot start with `;` |
| 23 | `[; 1]` | error: an array literal cannot start with `;` |
| 24 | `[]` | 1-D `[]`, length 0 |
| 25 | `[1 2 ;⏎3 4]` | `[1 2 3 4]`, `length=[2 2]` |
| 26 | `[1 2 ; ; 3 4]` | error: skipped separator level: levels 0 and 2 appear, and level 1 does not |
| 27 | `let v:array<int64 length=[3]> = [1 2 3]` | shaped rank 1, `.length` is `[3]`, `v[1]` is 2 |
| 28 | `let w:array<float64> = [1.0 2.0⏎3.0 4.0]` | error: this literal is 2×2, and `array<float64>` is 1-D; join the lines with `\` or ask for `array<float64 length=[2 2]>` |
| 29 | `let w:array<float64> = [1.0 2.0 \⏎3.0 4.0]` | 1-D `[1.0 2.0 3.0 4.0]`, length 4 |

19 is ragged after renormalization, not a skipped level. 21 is the old fixture 28, with the plural "1 row".

## Comments, blanks, `\`, operators

| # | Literal | Result |
|---|---|---|
| 30 | `[1 # a; b⏎2]` | 1-D `[1 2]`, length 2. The `;` in the comment is not a token |
| 31 | `[1 # note⏎# note⏎2]` | 1-D `[1 2]`, length 2 |
| 32 | `[1 2 # note⏎3 4]` | `[1 2 3 4]`, `length=[2 2]` |
| 33 | `[1 2 # note⏎⏎3 4]` | error: skipped separator level: levels 0 and 2 appear, and level 1 does not |
| 34 | `[1 #{ a; b }# 2]` | 1-D `[1 2]`, length 2 |
| 35 | `[1 #{⏎⏎a; b⏎}# 2]` | 1-D `[1 2]`, length 2. The blank line is inside the comment |
| 36 | `[1 2⏎   ⏎3 4]` | error: skipped separator level: levels 0 and 2 appear, and level 1 does not. The middle line is only spaces, and two newlines are level 2 |
| 37 | `[1 2\r⏎3 4]` | `[1 2 3 4]`, `length=[2 2]`. `\r\n` is one break |
| 38 | `[1 +⏎2  3 +⏎4]` | 1-D `[3 7]`, length 2 |
| 39 | `[2 3 5 \⏎7 11]` | 1-D `[2 3 5 7 11]`, length 5 |
| 40 | `[[1⏎2] [3⏎4]]` | nested, length 2; each element is 1-D length 2. The inner breaks are not outer gaps. **A:** `length=[2 2]` |

36's source is a newline, a line of spaces, and a newline. That is two breaks. I need the table cell to be only the error. Let me fix 36 when I edit — I'll write it cleanly below by replacing. I'll fix after the write if the cell is messy. I'll leave a clean version via a careful rewrite of that row in a follow-up if needed. Looking at what I wrote, the cell contains "Wait" style thinking. I must fix it before finishing.

## Discards and gap merge

`f` is `() => void` and is called once per discarded call.

| # | Literal | Result |
|---|---|---|
| 41 | `[1 (2;) 3]` | 1-D `[1 3]`, length 2 |
| 42 | `[1 (2; 3) 4]` | 1-D `[1 3 4]`, length 3 |
| 43 | `[f(); 7]` | 1-D `[f() 7]`, length 2. `f` is called and its value is kept |
| 44 | `[1 2 (f();) ; 3 4]` | `[1 2 3 4]`, `length=[2 2]`. The empty group is deleted; max(space, `;`) is level 1 |
| 45 | `[1 2⏎(f();)⏎3 4]` | `[1 2 3 4]`, `length=[2 2]`. max of the two newlines is 1, not 2 |
| 46 | `[1 2⏎⏎(f();)⏎3 4]` | error: skipped separator level: levels 0 and 2 appear, and level 1 does not |
| 47 | `[{1; 2} 3]` | 1-D `[2 3]`, length 2 |
| 48 | `[a=1 b=2]` | record, not an array |
| 49 | `[a=1; b=2]` | record `b=2` |
| 50 | `[[a=1]⏎[a=2]]` | 1-D array of 2 records, length 2 |
| 51 | `["a" -> 1; "b" -> 2]` | dict `"b" -> 2` |
| 52 | `xs[1; 2]` | error: `;` is not allowed in an index |

## Nests, ascription, `new`

`xs` is 1-D `[10 20 30]`. `ys` is 1-D `[40 50]`. `rows` is nested `[[1 2] [3]]`.

| # | Literal | Result |
|---|---|---|
| 53 | `[[1 2 3]]` | nested, length 1; the element is 1-D `[1 2 3]`. **A:** `length=[1 3]` |
| 54 | `[[1] [2] [3]]` | nested, length 3; each element length 1. **A:** `length=[3 1]` |
| 55 | `[[1 2] [3 4]]` | nested, length 2. **A:** `length=[2 2]` |
| 56 | `[[1 2] ; [3 4]]` | nested, length 2. Same as 55. **A:** `length=[2 2]` |
| 57 | `[[1 2]⏎[3 4]]` | nested, length 2. **A:** `length=[2 2]` |
| 58 | `[xs ys]` | nested, length 2. **A:** error, lengths 3 and 2 |
| 59 | `[xs ; ys]` | nested, length 2. Not a stack. **A:** error, lengths 3 and 2 |
| 60 | `[[1 2] [3]]` | nested, length 2. Legal. **A:** error, lengths 2 and 1 |
| 61 | `let m:array<int64 length=[2 2]> = [[1 2] [3 4]]` | `[1 2 3 4]`, `length=[2 2]`. Same under A |
| 62 | `let m:array<int64 length=[2 2]> = [[1 2] [3]]` | error: these rows have different lengths (2 and 1); this target asks for `length=[2 2]` |
| 63 | `let n:array<array<int64>> = [[1 2] [3 4]]` | nested, length 2. Same under A, because the type opts out |
| 64 | `[xs]` | nested, length 1. The element is `xs` |
| 65 | `xs[new]` | `[10 20 30]`, `length=[1 3]` |
| 66 | `xs[.. new]` | `[10 20 30]`, `length=[3 1]` |
| 67 | `rows[new]` | error: `new` inserts an axis of a rectangular array; this value is nested. Write `[rows]` to wrap it, or `[loop x in xs [x]]` to wrap each element |
| 68 | `[1 [2 3]]` | nested, length 2: the number 1 is not an array, so this is a type error: an array literal's elements must have one type. **A:** the same type error, not a collapse |
| 69 | `[loop y in [0..0) [loop x in [0..4) 0]]` | nested, length 0. The width 4 is not stored. **A:** empty n-D, width dropped |
| 70 | `let m:array<int64 length=[0 4]> = [loop y in [0..0) [loop x in [0..4) 0]]` | `length=[0 4]`, proved, no run-time check |

68 is a uniform element type, not a separator question. A scalar and an array do not share a type, so the literal is rejected before either option considers collapsing it.

## Runs

| # | Literal | Result |
|---|---|---|
| 71 | `[loop i in [0..3) i]` | 1-D `[0 1 2]`, length 3 |
| 72 | `[loop i in [0..3)⏎i]` | 1-D `[0 1 2]`, length 3 |
| 73 | `[loop x in [2 5] {1.0 x x^2}]` | 1-D of 6 numbers: `1.0 2 4 1.0 5 25` |
| 74 | `[loop x in [2 5] {1.0; x x^2}]` | 1-D of 4 numbers: `2 4 5 25`. `1.0` is discarded |
| 75 | `[loop i in xs i ; loop j in ys j]` | 1-D, the cells of `xs`'s run then the cells of `ys`'s run. One written level, so the `;` renormalizes away |
| 76 | `[1 2 ; loop i in [0..2) i]` | `[1 2 0 1]`, `length=[2 2]`. The run length is proved |
| 77 | `[1 2 ; loop i in [0..3) i]` | error: the rows of an array literal must have the same size: this one has 3 elements, the first has 2 |
| 78 | `[1 2 ; loop i in xs i]` | obligation: cannot prove this row has 2 elements; the length is checked at run time under `$runtime_checks`. Not a syntax error. Under the flag, a mismatch panics |
| 79 | `[1 xs... ; 2]` | obligation, same text as 78, when `xs.length` is not proved. Proved 0: `[1]` against `[2]`, `length=[2 1]`. Proved 1: error: the rows of an array literal must have the same size: this one has 1 element, the first has 2 |
| 80 | `[xs... ; ys...]` | 1-D, `xs`'s elements then `ys`'s elements. The only written level is 1 |
| 81 | `[loop i in [0..3) i ;]` | `[0 1 2]`, `length=[1 3]` |
| 82 | `[loop y in [0..2) [loop x in [0..3) y*3+x]]` | nested, length 2; `n[1]` is 1-D `[3 4 5]`. **A:** `length=[2 3]`, and `n[1][0]` does not typecheck |
| 83 | `[loop i in [0..2) {i i*10}]` | 1-D `[0 0 1 10]`, length 4 |
| 84 | `[loop i in [0..2) [i i*10]]` | nested, length 2. **A:** `length=[2 2]` |
| 85 | `[loop i in [0..2) i i*10]` | error: `i` is not defined. The body is the name `i` |
| 86 | `[loop x in [1 2 3 4] if x >? 2 x]` | 1-D `[3 4]`, length 2 |
| 87 | `let rows:array<array<string>> = [loop line in lines line.split(",")]` | nested. Legal under B with no annotation, and under A only because the annotation is written. **A without the annotation:** error: cannot prove these rows have the same length; give this the nested type `array<array<…>>`, or check it at run time with `$runtime_checks` |
