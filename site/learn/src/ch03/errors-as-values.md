# Errors as Values

Errors are ordinary values with their own types. A function that can fail lists the failure in its return type, so callers can see it and the compiler makes sure they handle it.

<!-- dewy-example: {"mode": "run", "stdout": "43\nnot a number: forty-two\n"} -->
```dewy
ParseError:type = type of error & [message:string]

parse = (text:string):>int|ParseError => {
    let value = to_int(text)
    if value is? error return ParseError["not a number: {text}"]
    value
}

loop text in ["42" "forty-two"] {
    let result = parse(text)
    if result is? int printl(result + 1) else printl(result.message)
}
```

`type of error & [message:string]` mints a new error type with a `message` field. `is?` tests which alternative a value holds, and narrows it in each branch. There are no exceptions to forget to catch: a value that may be an error cannot be used as an `int` until the error case is dealt with.

`main` can return errors too. Each error type in its result gets its own process exit code, so a script reports failure without extra code.

The [reference](/reference/errors-and-forwarding.html) has the complete rules, including forwarding an error to the caller.
