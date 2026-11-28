# Reductions with a default, round 1: `max(xs default=d)` and its siblings

The ladder's tree-diff and build-planner programs (149, 150) each needed the largest of a
possibly empty array and had no direct way to say what an empty one gives. Today `min(xs)`,
`max(xs)`, `xs.min_by(key)` and `xs.max_by(key)` take an array with `length >? 0`, proven or
checked like an index (LANGUAGE.md, "No traps"). This round proposes the form for the empty
case, dogfoods it on ten programs and grades it. The result is open decision D50.

## The proposal

```dewy
let widest = max([loop c in changes c.name.length] default=0)
let first = min(starts default=none)                  # int64?: none for no starts
let oldest = files.min_by((f) => f.modified default=none)
```

- `min(xs default=d)` and `max(xs default=d)` give `d` for an empty `xs`, its least or greatest
  element otherwise. `xs.min_by(key default=d)` and `xs.max_by(key default=d)` do the same.
- The result is the element type joined with `d`'s: `default=0` on `array<int64>` stays
  `int64`, and `default=none` gives `int64?`, as `pop(default=none)` gives `T?` (LANGUAGE.md).
- With a default there is no length obligation: the call cannot panic, so nothing is proven.
- Without one, nothing changes: `max(xs)` keeps its `length >? 0` obligation.
- `default` is the existing name of the existing role. `d.pop(k default=v)` and
  `xs.pop(default=none)` already use it for "what an absent value gives", so no new word is
  introduced and no cold-read test is needed.

## Two-question test

1. The common path, a known nonempty array, is unchanged and stays `max(xs)`. Empty input is
   the second most common case: summaries, widths for column alignment, "latest" lookups.
2. Adjusting today means a branch, `if xs.is_empty 0 else max(xs)`, which reads the array
   twice and repeats its expression, or `max([0 xs...])`, which is wrong for negative values
   and allocates. Neither is a natural adjustment, so the form is asked about. It is new
   surface (a parameter), type (b).

## Peers

| Language | Empty-safe largest |
|---|---|
| Python | `max(xs, default=0)` |
| Go | `slices.Max` panics; a loop or a length check |
| Rust | `xs.iter().max().copied().unwrap_or(0)` |
| TypeScript | `xs.length ? Math.max(...xs) : 0` (`Math.max()` is `-Infinity`) |
| Swift | `xs.max() ?? 0` |

Python's spelling is the same word in the same place. Swift and Rust return an optional first.
Dewy gets that too with `default=none` and then `?? 0`, but the direct form avoids the
optional when the default is known.

## Dogfooding

Ten programs, each a realistic task that meets an empty input. Grades 1–5 on obvious,
discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and
Swift.

### 1. Column width for a table

```dewy
print_table = (rows:array<[name:string count:int64]>):>void => {
    let width = max([loop r in rows r.name.length] default=0)
    loop r in rows printl"{r.name}{" ".repeat(width - r.name.length)}  {r.count}"
}
```

Obvious 5, discoverable 5 (Python's word, shown in the editor's signature), concise 5, safe 5,
complete 5. Today: `if rows.is_empty return` before the `max`, which also hides that an empty
table prints nothing.

### 2. Latest timestamp in a log, or none

```dewy
latest = (lines:array<string>):>Instant? => {
    let times = [loop line in lines {instant(line.split[0]) ?? continue}]
    max(times default=none)
}
```

All 5. The `none` default gives the optional the caller expects, without `if`.

### 3. Highest score, zero when nobody played

```dewy
let best = max(scores.values default=0)
printl"best {best}"
```

All 5. `scores.values` of an empty dictionary is the case the guard used to need.

### 4. Shortest path length among reachable targets

```dewy
let reachable = [loop t in targets {dist.get(t) ?? continue}]
let nearest = min(reachable default=none) ?? return "unreachable"
```

All 5. The default and `?? return` compose: the empty case leaves through the same path as a
missing value.

### 5. Oldest file to evict

```dewy
let victim = files.min_by((f) => f.modified default=none) ?? return
victim.path.remove_file or_throw
```

Obvious 5, discoverable 4: a lambda followed by `default=` reads a little crowded, though the
argument is named and the editor shows where it ends. Concise 5, safe 5, complete 5.

### 6. Peak memory over samples, floats

```dewy
let peak = max(samples default=0.0)
printl"peak {fmt'.1f'(peak)} MB"
```

All 5. A float default joins with `float64` elements; NaN handling is `max`'s as today.

### 7. Next free id

```dewy
let next_id = max([loop u in users u.id] default=0) + 1
```

All 5. The most common real use, and the one `max([0 ids...])` gets right only by luck of
ids being positive.

### 8. Critical path length in a build planner

```dewy
finish[name] = time + max([loop dep in t.deps finish[dep]] default=0s)
```

All 5. A `Duration` default joins with `Duration` elements; a target with no dependencies
starts at zero. (Ladder 150 wrote this as a loop with a running maximum.)

### 9. Lowest bid, keeping the type exact

```dewy
Bid:type = [who:string cents:int64]
let winner = bids.min_by((b) => b.cents default=none)
match winner { b:Bid => printl"{b.who} wins at {b.cents}"  <none> => printl"no bids" }
```

All 5. `Bid?` matches the way an optional result is handled everywhere else.

### 10. Widest line of any text

```dewy
longest = (text:string):>int64 => max([loop line in text.lines line.length] default=0)
```

All 5. Without a default this function needs a proof that `text.lines` is nonempty, and an
unproven `max(xs)` is a compile error unless the scope opts into `$runtime_checks`. The
default removes the obligation instead of adding a check.

### Summary

49 of 50 marks at 5; program 5's discoverability is 4 because a key lambda and `default=` share
one call. The 4 comes from writing two arguments in one call, not from the proposal, and a
caller can name the key (`key=`) to separate them. Python is the closest peer and is matched
exactly. Swift's and Rust's optional-first style is available through `default=none`.

## Not proposed

- A default on `sum` or `mean`: `sum` of an empty array is already zero, and `mean` of an empty
  one is a separate question (it has no natural value).
- `first`/`last` defaults: `xs.get(0) ?? d` already says it.
- A method spelling `xs.max(default=0)`: `min`/`max` of an array are functions today; this
  round only adds the parameter.
