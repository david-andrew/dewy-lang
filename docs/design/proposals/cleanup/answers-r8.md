# David's response to round 8 (2026-11-26)

Direction, not yet a decision. Round 9 works it through.

## What he likes about (f)
- Types can require at compile time that certain things be handled, otherwise the program doesn't compile. Some types could be less strict: a compile warning, with a clear squiggle in the editor at the point where the value is left unhandled. (He notes this is close to linear types.)
- It's plain code that works through the regular control flow, so nothing about how control flow works changes and nothing feels nonlocal.
- The strict metatag then sits on top, meaning no failure value can be produced without being handled somehow.
- Anything that can't actually fail must never show up in this kind of context.

## Several resources that can each fail at cleanup
This is the case for the error stack.

```dewy
let somefn = () => {
    r1 = ...
    r2 = ...
    r3 = ...
    ... # regular function work
}   # compile error here: r1.close, r2.close and r3.close all need to be called
```

Calling each close in turn isn't enough:

```dewy
let somefn = () => {
    r1 = ...
    r2 = ...
    r3 = ...
    ... # regular function work
    r1.close or_throw
    r2.close or_throw
    r3.close or_throw
}   # still a compile error: r2.close and r3.close don't run if r1.close fails
```

So the function builds up the error stack (spelling illustrative):

```dewy
let somefn = () => {
    r1 = ...
    r2 = ...
    r3 = ...
    defer {
        let errors = ErrorStack
        errors &= r1.close
        errors &= r2.close
        errors &= r3.close
        if errors.length >? 0 return errors
    }
    ... # regular function work
}
```

## When `defer` runs, and several defers
A simple answer: defers run after all regular computation has finished, and may replace the value being returned. Several defers could build the error stack automatically:

```dewy
let somefn = () => {
    r1 = ...
    r2 = ...
    r3 = ...
    # these combine into one error stack if more than one fails; if just one fails, perhaps
    # that single failure is returned, or perhaps it's always a stack to keep the result type simple
    defer r1.close or_throw
    defer r2.close or_throw
    defer r3.close or_throw
    ... # regular function work
    if some_condition
        return expensive_function_call()
    ... # more regular function work
    # normal exit here
}
```

If `some_condition` is true, `expensive_function_call()` runs and produces its value. Before the function actually returns, the defers run, and if any failed, the function returns the failure instead of that value.

## D42
This makes him think D42's rule may need reconsidering: it may obscure too much, and folding failures together ought to be more explicit.
