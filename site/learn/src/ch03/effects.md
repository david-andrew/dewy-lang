# Effects

An effect is something a function may do besides computing its result: block on I/O, allocate, panic, write a place it was given. The compiler infers effects for every function, so ordinary code never writes them. You state them when you want a promise checked.

`& no blocks` promises that a function never waits on I/O, a lock or a sleep. The compiler checks the promise through everything the function calls:

<!-- dewy-example: {"mode": "reject", "diagnostic": "blocking operation exceeds the contract"} -->
```dewy
tick = (n:int):>int & no blocks => {
    printl(n)        # printing is I/O
    n + 1
}
```

`& no panics` promises that a function cannot stop the program. Code that opted into runtime checks may panic, and the effect follows it to every caller:

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
tick = (n:int):>int & no panics => n + 1
printl(tick(41))
```

`$no_hidden_costs` at the top of a module, function or block turns on a strict lane for realtime, audio or systems code: no runtime checks, no code that may panic, no hidden allocation and no implicit costly copy. Game and application code never has to enter it.

The [reference](/reference/refinements-and-effects.html) has the complete rules.
