# Ranges

A range is a span over numbers, characters, or another ordered type. Ranges show up in loops, indexing, and membership tests.

A range always contains `..`. Endpoints juxtapose with `..`. An optional `first,second` pattern sets the step size.

## Syntax

```dewy
[first..]               # first to inf
[..last]                # -inf to last
[first..last]           # first to last
[..]                    # -inf to inf

[first,second..]        # step is second - first
[first,second..last]
[..2ndlast,last]        # step is last - 2ndlast
```

`[first..2ndlast,last]` is not allowed. Use `[first,second..last]` instead.

The inferred step may be positive or negative. A zero step such as `1,1..10` is invalid.

Bounds are inclusive by default. Square brackets include an end; parentheses exclude it. The two ends are independent.

```dewy
[first..last]   # include both
[first..last)   # include first, exclude last
(first..last]   # exclude first, include last
(first..last)   # exclude both
first..last     # same as [first..last]
```

### Juxtaposition

An endpoint is part of the range only if it is juxtaposed with `..`:

```dewy
first..last     # first to last
first ..last    # -inf to last
first.. last    # first to inf
first .. last   # -inf to inf
```

Range juxtaposition is medium-low precedence, so `first..last + 1` is `first` through `last+1`.

```dewy
first..last+1
first,second..last/2
a in first..last
```

## Numeric Ranges

```dewy
(1..5)  # 2 3 4
(1..5]  # 2 3 4 5
[1..5)  # 1 2 3 4
[1..5]  # 1 2 3 4 5
1..5    # 1 2 3 4 5
```

A right-unbounded range such as `0..` has a first value and iterates forever. A left-unbounded range such as `..10` is a valid range value but cannot be iterated, because it has no first value. The same is true of `..` and `..3,5`.

## Character Ranges

Unannotated string bounds use one-grapheme strings. Iteration is defined when each supplied anchor is a grapheme containing exactly one Unicode scalar. Values advance in scalar order and skip the surrogate interval.

```dewy
ord_range = 'a'..'z'
alpha_range = ['a'..'z'] + ['A'..'Z']
loop letter in 'z','y'..'a' { ... }
let ascii_scalars:range<uint32> = 'A'..'Z'
```

Multi-scalar graphemes have no invented universal successor. Enumerating them requires an explicit alphabet or collation policy. See [Strings and Graphemes](string-types.md).

## Uses

### Loops

```dewy
loop i in 0..5 print'{i} '
# 0 1 2 3 4 5

loop i in 5,4..0 print'{i} '
# 5 4 3 2 1 0
```

A reversed range **requires** an explicit step. `5..0` results in an empty range.

### Range Arithmetic

```dewy
loop i in [0..4]/4 print'{i} '
loop i in [0..4]*0.25 print'{i} '
# both: 0 0.25 0.5 0.75 1
```

This expresses the same intended values as `[0,0.25..1]`. Numerical libraries can provide `linspace` and `logspace` helpers without changing the range grammar.

### Compound Ranges

```dewy
complex_range = [1..5] + (15..20)
loop i in complex_range
    printl(i)           # 1 2 3 4 5 16 17 18 19
7 in? complex_range     # false
16 in? complex_range    # true

complex_range = [1..20) - (5..15]
```

### Membership

```dewy
5 in? [1..5]         # true
5 in? (1..5)         # false
3.1415 in? (1..5)    # true
```

### Indexing

```dewy
full_string = 'this is a string'
substring = full_string[3..12]
printl(substring)    # 's is a str'
```

Because indexing is juxtaposition, the range's own brackets choose inclusive or exclusive ends:

```dewy
full_string(3..12)   # ' is a st'
full_string[3..12)   # 's is a st'
full_string(3..12]   # ' is a str'
full_string[3..]     # 's is a string'
full_string[..12]    # 'this is a str'
full_string[..]      # the whole string
```

`end` is the index of the last element:

```dewy
arr[end]       # last element
arr[end-1]     # second to last
arr[..end-3]
arr[5..end-3]
arr[end-3..]
```

> **Provisional design:** Integer positions and `end` define ordinary sequence slicing. Indexing by noninteger ordered domains requires a collection-specific indexing contract and is not implied by the generic range syntax.
