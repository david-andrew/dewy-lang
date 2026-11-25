# Answers to round 4 (David, 2026-11-25)

The decisions are recorded in [decisions.md](../../decisions.md) (batch 11). This file keeps
David's examples and the ideas he recorded for later.

## Infinite generators

```dewy
squares = () => lazy loop i in 0.. i^2
primes = () => {  # not as efficient as it could be
    prev: array<int> = [2] # list of previous primes
    $outer
    lazy loop candidate in 3,5.. {
        loop p in prev and p^2 <? candidate
            if candidate % p =? 0 continue $outer
        candidate
    }
}
```

## Multivalues are ordinary values

```dewy
fn1 = () => (42 "hello" true)
fn2 = (a:int b:string c:bool) => printl"a:{a}, b:{b}, c:{c} "

# all of these are valid, identical calls to fn2
fn2(42 "hello" true)
fn2((42 ("hello" true)))
fn2(fn1())
fn2((fn1))
x = (42 "hello" true)  # multivalued type is `(int string bool)`
fn2(x)
y = [42 "hello" true]  # type is `[int string bool]`
fn2(y...)
```

```dewy
fn3 = (a:int b:string c:bool=true) => if c printl"{a}: {b}" else printl"nothing to see"
args = if some_cond
        (42 "hello")
    else
        (0 "" false)

# args has type `(int string) | (int string bool)`, both valid shapes for calling fn3
fn3(args)
```

```dewy
fn4 = (a:int b:int c:int=0) => a*b+c
let v1 = if c (1 2) else (3 4 5)
fn4(v1)

let v2 = if c [1 2] else [3 4 5]
fn4(v2)  # error, doesn't match the signature
```

`log("connection established" if verbose (timestamp user_id))` gives `log` the arguments
`(Timestamp UserId) | void`, so it works if `log` takes those as optional parameters.

It might not always be idiomatic to make a union of multivalues of different widths, but
there will be cases where it is perfectly reasonable.

## Commas (bearing on Q1)

Commas should be non-semantic, mapping to grouping in parentheses, so including one by
accident has no effect: `[1 2 3 4]`, `[1, 2, 3, 4]` (that is, `[(1 2 3 4)]`) and `[1 2, 3 4]`
(that is, `[1 (2 3) 4]`) are the same thing.

## Ideas for later (not questions)

- **`.next` as a record:** `next = <T>():[exhausted:bool value:T|void]`, giving back
  `[exhausted=false value=42]` or `[exhausted=true]`.
- **A one-step `next` statement:** `next v in some_iterable { … }` as shorthand for
  `loop v in some_iterable and _ in [0..1) { … }`. David isn't a fan; the record above is
  preferred.
- **Generator types that promise values:** for example `generator<int64 length>=?2>`, a
  generator with at least two values remaining.
- **Slicing generators:** `pair = (g:generator<int64 length>=?2>) => add(g[0..2)...)` should
  lazily take the first two values, instead of `add([g...][0..2)...)`, which drains the whole
  generator into an array.
- **Places from generators:** look for compelling cases, and compare yielding a place with
  other ways Dewy can do the same thing.
