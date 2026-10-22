# Source Files and Execution

> **Language design.** [Generated coverage](/status/#ref-execution) names measured programs and target restrictions; examples here illustrate the design.

## Current command line

Use `dewy file.dewy` to run, `dewy check file.dewy` to check without output, or `dewy build file.dewy --release -o program` to save a native executable. In a checkout use `./tools/dewy` in place of `dewy`. `build --target wasm32` emits a browser page. See [installation](/install/) and [target-scoped coverage](/status/).

## Source-language rules

A source file is a compilation unit. Its executable top-level expressions run once in source order after imported dependencies have initialized.

A program does not require `main`. When a zero-argument function named `main` exists in the entry module, the program invokes it after top-level initialization.

<!-- dewy-example: {"mode":"design-only"} -->
```dewy
printl"initializing"

let main = ():>void => {
    printl"running"
}
```

`main` returns `void` or the errors that reach it: `void | E`, an ordinary result type, declared or inferred. It gives no exit code: success exits 0, and a script that needs a particular code calls `exit(n)`. An error reaching `main` is printed on standard error and ends the program with its kind's code, assigned 1, 2, 3, … in the order the kinds are declared (a declared result fixes the order), below 126; an error type may pin its own with an `exit_code` member. `dewy build --exit-codes` prints the table. Additional standardized entry parameters such as command-line arguments and environment access are provisional.

An explicit top-level call to `main()` is an ordinary call and does not suppress automatic entry invocation.

Imported modules initialize once in dependency order. Import cycles and colliding names are errors unless a future construct explicitly defines a valid cycle or disambiguation.
