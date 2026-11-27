# Functions and Calls

A function is written `(parameters) => body` and bound to a name like any other value. Parameters are separated by spaces, each with an optional type after a colon. The value of the body's last expression is the result; `return` leaves early.

<!-- dewy-example: {"mode": "run", "stdout": "42\n5\nHi, Ada!\nHello, Ada!\n"} -->
```dewy
double = (value:int) => value * 2
printl(double(21))

hypot_squared = (a:int b:int):>int => a*a + b*b   # :> states the result type
printl(hypot_squared(1 2))

greet = (name:string greeting:string="Hi") => printl"{greeting}, {name}!"
greet("Ada")
greet("Ada" greeting="Hello")                     # by name
```

A function with no parameters is called by naming it, and `@name` is the function itself, a value you can store or pass:

<!-- dewy-example: {"mode": "run", "stdout": "42\n[2 4 6]\n"} -->
```dewy
double = (value:int) => value * 2
let callback = @double
printl(callback(21))
printl([1 2 3].map(@double))
```

The [reference](/reference/functions-and-calls.html) has the complete rules.
