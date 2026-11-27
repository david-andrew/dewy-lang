# Source Files and Execution

> [Generated coverage](/status/#ref-execution) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Command Line

`dewy file.dewy [args...]` runs a program, `dewy check file.dewy` reports errors without building, and `dewy build file.dewy --release -o program` saves a native executable. `build --target` selects another target (`x86_64-linux`, `aarch64-linux`, `aarch64-mac`, `x86_64-windows`, `wasm32`). In a checkout, use `./tools/dewy` in place of `dewy`. See [installation](/install/) and [target-scoped coverage](/status/).

## Top-Level Code

A source file is a module. Its top-level statements run once, in source order, after the modules it imports have initialized. A file without `main` is a script that runs top to bottom.

<!-- dewy-example: {"mode":"run","stdout":"first\nsecond\n"} -->
```dewy
printl"first"
printl"second"
```

## `main`

`main` is optional. When the file given to `dewy` declares it, the top-level statements run first and then `main` runs by itself, exactly once:

<!-- dewy-example: {"mode":"run","stdout":"initializing\nrunning\n"} -->
```dewy
printl"initializing"

main = ():>void => {
    printl"running"
}
```

Calling `main()` at the top level is an error; recursion inside `main` is allowed.

<!-- dewy-example: {"mode":"reject","diagnostic":"main runs by itself, once"} -->
```dewy
main = ():>void => printl"x"
main()
```

Only the entry file's `main` runs. An imported module's `main` never runs automatically, and a splat import does not bring it in, so a library can keep a local test `main`. An explicitly imported `main` is an ordinary function.

The command-line arguments are the prelude's `args`, an `array<string>` whose first element is the program name.

## Exit Status

`main` returns `void` or the errors that reach it: an ordinary `void | E` result, declared or inferred. Success exits 0. A program that needs a particular code calls `exit(n)`, where `n` is a `uint8`; a constant outside 0–255 is a compile error.

An error reaching `main` is printed on standard error as its kind and its `message` field, if it has one (`error: UsageError: usage: fetch HOST`). The program then exits with its kind's code: 1, 2, 3, … in the order the kinds are declared (or as a declared result lists them), up to 100. An error type with an `exit_code` field pins its own code. 101 is a failed runtime check or panic. `dewy build --exit-codes file.dewy` prints the table.

<!-- dewy-example: {"mode":"run","stdout":"","exit":69,"args":["nowhere"]} -->
```dewy
UsageError:type = type of error & [message:string]
Offline:type = type of error & [exit_code:int64=69]

connect = (host:string):>void | Offline => {
    if host =? "nowhere" return Offline[]
    printl"connected to {host}"
}

main = ():>void | UsageError | Offline => {
    let argv = args
    if argv.length <? 2 return UsageError["usage: fetch HOST"]
    connect(argv[1]) or_throw
}
```

Run with the argument `nowhere`, this prints `error: Offline` on standard error and exits 69. Without arguments it exits 1.

## Imports and Initialization

An import names a file relative to the importing file, with a path literal. Imported modules initialize once, in dependency order, before the importing module's top-level statements run.

<!-- dewy-example: {"mode":"run","stdout":"helpers ready\n42\n","fixtures":{"helpers.dewy":"printl\"helpers ready\"\nanswer = ():>int => 42\n"}} -->
```dewy
from p"helpers.dewy" import (answer)
printl(answer())
```

Import cycles and colliding names are errors. See [Modules and Imports](modules-and-imports.md) for the import forms.
