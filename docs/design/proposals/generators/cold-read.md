# Cold read of the generator type spelling

Three fresh readers, given only the lines below and a short context, guessed the meaning of `generator<T failure=E length=N>` and `lazy` (2026-11-23). All three read every line correctly; the lowest confidence (2/5) was on line 4, a declaration without `lazy`.

```dewy
fetch_pages = (urls:array<string>):>generator<Page failure=HttpError> => lazy loop url in urls http_get(url) or_throw
count_up = ():>generator<int64> => lazy loop n in [0..) n
first_two = ():>generator<int64 length=2> => lazy (20 22)
let tokens:generator<Token failure=LexError> = lex(text)
```

## Reader a

1 | `generator<Page failure=HttpError>` is a sequence you pull `Page` values from one at a time; if fetching fails, the error is specifically an `HttpError` rather than an untyped failure. `lazy` means the `loop` over URLs does not run at call time—it runs only as the consumer advances the generator, doing one `http_get` per step. | 4
2 | `generator<int64>` is an iterable source of `int64` values with no declared failure type on the generator (failures, if any, are not parameterized here). `lazy` defers the infinite `loop n in [0..)` so counting from zero does not start until something consumes the generator. | 4
3 | `generator<int64 length=2>` is a generator that yields `int64` and is known at the type level to produce exactly two items before finishing. `lazy` delays producing those values until iteration, so the `(20 22)` sequence is not emitted until the generator is driven. | 3
4 | `generator<Token failure=LexError>` types `lex(text)` as a token stream where lexing problems are `LexError` failures on that generator. This line has no `lazy` keyword; the name suggests a normal (possibly eager) generator binding rather than an explicitly lazy function body. | 3

## Reader b

1 | `generator<Page failure=HttpError>` is a pullable sequence of `Page` values whose next-item operation can fail with `HttpError` (passed out via `or_throw`). `lazy` delays running the `http_get` loop until the caller actually pulls pages, instead of fetching everything when `fetch_pages` is called. | 4
2 | `generator<int64>` is an unbounded sequence of integers with no failure channel. `lazy` keeps the infinite `[0..)` loop from running (or allocating) until values are pulled. | 4
3 | `generator<int64 length=2>` is a sequence of exactly two `int64`s; `length=` is a known finite size on the type. `lazy` turns the two-element group `(20 22)` into a generator that yields those values on demand rather than as an eager tuple. | 3
4 | `generator<Token failure=LexError>` is a sequence of `Token`s whose production can fail with `LexError`. There is no `lazy` on this line; the type only describes what `lex(text)` returns. | 4


## Reader c

1 | generator<Page failure=HttpError> is a sequence of Page values that can end early with an HttpError failure; failure= names the error type the sequence may produce. lazy means the pages are produced one at a time as the caller asks for them, not all fetched up front. | confidence 4
2 | generator<int64> is an unbounded sequence of int64 values, with no failure type, so it never fails. lazy means each number is produced on demand, which suits the endless range [0..). | confidence 4
3 | generator<int64 length=2> is a sequence of exactly two int64 values, here 20 and 22. lazy means those values are produced on demand rather than built as an array. | confidence 3
4 | This is a variable declaration, not a function: tokens has type generator<Token failure=LexError>, a sequence of Token values that may end with a LexError failure. There is no lazy here, so it has no effect on this line; lex(text) supplies the sequence. | confidence 2

