# Effects

An effect is something a function does besides produce a value. The
full set of effects, and how you write them, is not yet determined.

`noreturn` is one settled effect. It marks a function that does not
come back to the caller, such as `exit`. You write it in the return
slot.

```dewy
let die = (message:string):>noreturn => {
    printl(message)
    exit(1)
}
```

`noreturn` is not `never`. `never` is a type for a path that cannot
happen. `noreturn` constrains the function. It must not return
control.
