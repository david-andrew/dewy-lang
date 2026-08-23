# Effects

An effect is something a function does besides produce a value. The full set of effects, is not yet determined.

`noreturn` is one settled effect. It marks a function that does not come back to the caller, such as `exit`. You write it in the return slot.

```dewy
let die = (message:string):>noreturn => {
    printl(message)
    exit(1)
}
```

`noreturn` is not `never`. `never` is a type for a path that cannot happen. `noreturn` constrains the function. It must not return control.

> Note that the above example is technically `never & noreturn`
>
> ```dewy
> let die = (message:string):>never & noreturn => {
>     printl(message)
>     exit(1)
> }
> ```
>
> though the type/effects system infers it automatically. in this case, both `never`, and `noreturn`, would be inferred and can be omitted.

Effects attach to a return type at the top level with `&`. Parenthesize the type expression (or both sides) so the `&` attaches the effect set rather than intersecting into the union. Several effects also combine with `&`: they are all part of the contract, not alternatives. `Effects<IO Random Time noreturn>` is a convenience for the same set.

```dewy
impure_function = (x:int y:int):> (int | never) & IO & Random & Time & noreturn => {
    if time.now =? time.utc'23:59:59' {
        if random.coinflip exit(1)
        printl'a special value for a special time'
        return 42
    }
    return x + y
}
```

> NOTE: effects do not participate in structural typing with regular types. An effect may only appear at the top level of a return annotation. `Invoice | IO` and `(T1 | Effect1) & (T2 | Effect2)` are invalid.
