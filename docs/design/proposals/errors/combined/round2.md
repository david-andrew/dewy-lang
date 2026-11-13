# Combining failures, David's design: round 2

Round 1's dogfood (`dogfood.md`) found three fixable deductions. This round fixes them. Everything
in `round1.md` not named here stands.

## 1. Drop "an empty spread makes no stack"

Round 1 let `ErrorStack[xs...]` on an array not proven nonempty give `void | ErrorStack<E>`, so
`ErrorStack[problems...] or_throw` was the whole accumulation idiom. It cost an obvious-grade in
03, 04 and 07: a reader of `ErrorStack[problems...] or_throw` can't tell that nothing happens when
the array is empty, and the rule is one more special case. The guard is the same length and says
what it does:

```dewy
validate = (form:Signup) => {
    let problems:array<FieldError> = []
    if form.name.trim =? "" problems.push(FieldError["name" "is required"])
    if "@" not in? form.email problems.push(FieldError["email" "needs an @"])
    if problems.length >? 0 return ErrorStack[problems...]
    return User[form.name.trim form.email]
}
```

**Rule now:** a stack is never empty, and `ErrorStack[xs...]` needs `xs` proven nonempty, an
obligation like an index (a length guard, a push just before it, or a fixed array). Programs 03
line 12, 04 line 18 and 07 line 12 now use the guard. Regrade: 03, 04 and 07 obvious 4 → 5.

## 2. Context: a cause field, not `&`

Program 08 showed a library author choosing between wrapping a low-level failure and combining with
it. Round 1 didn't say which. Guideline, for the language guide:

- **`&` is for independent failures**, each of which the caller may want to handle by its own type:
  a write and the close after it, two checks, two items.
- **A cause field is for context**: a library that turns `FileNotFound` into its own
  `ConfigError` keeps the original in a field (`cause:error`, which holds a combination whole) and
  puts the original's text in its message. Combining instead (`failure & ConfigNotLoaded[path]`)
  would make `FileNotFound` a peer that every caller's handler must name, which leaks the
  library's internals into its callers' handlers.

```dewy
load = (path:Path) => {
    let text = read_all(path) or_throw<Canceled>
    if text is? error return ConfigError[path "cannot read {path}: {text}" text]
    return parse(text)
}
```

No new name: `cause` is an ordinary field the library declares. Program 08 says so in a comment
(line 2). The discoverability deduction stays (D4): it is a choice that must be taught.

## 3. One arm for a cancellation with or without a cleanup failure

Program 12 had two near-duplicate arms (`stopped:Canceled` and `both:Canceled & FileCloseFailed`).
One arm can name both shapes, and interpolating the value prints every part:

```dewy
main = () => {
    match save_frames(frames p"capture.bin") {
        <void> => printl"saved"
        stopped:Canceled | Canceled & FileCloseFailed => {
            printl("stopped ({stopped}); capture.bin may end early" file=stderr)
            return stopped
        }
        problem:FileError => return problem
    }
}
```

No rule change. Regrade: 12 concise 4 → 5.

## No round 3

Every remaining 4 has a cause outside this design's reach (listed at the end of `dogfood.md`):
cleanup shown only by hover is D40 Q1's accepted design; new names wait for the cold read; a
one-call combining helper would be new surface; the arm-versus-`is?` and cancellation-dominance
rules are the design itself; parenthesized projections come from `as` precedence; the `parallel`
extension and nonempty loop facts belong to other designs. None can be fixed by another round of
these rules without adding surface, so iteration stops at floor 4.
