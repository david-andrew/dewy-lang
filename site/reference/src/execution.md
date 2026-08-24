# Source Files and Execution

A source file is a compilation unit. Its executable top-level expressions run once in source order after imported dependencies have initialized.

A program does not require `main`. When a zero-argument function named `main` exists in the entry module, the program invokes it after top-level initialization.

```dewy
printl"initializing"

let main = ():>int64 => {
    printl"running"
    return 0
}
```

`main` may return `void` or an integer exit status. Additional standardized entry parameters such as command-line arguments and environment access are provisional.

An explicit top-level call to `main()` is an ordinary call and does not suppress automatic entry invocation.

Imported modules initialize once in dependency order. Import cycles and colliding names are errors unless a future construct explicitly defines a valid cycle or disambiguation.
