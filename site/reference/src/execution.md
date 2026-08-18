# Source files and execution

A source file is a compilation unit. Executable top-level items run once in
source order after imported dependencies have initialized.

If a zero-argument function named `main` exists, the generated entry point
invokes it after top-level execution. `main` currently returns an integer exit
code or `void`. A source file without `main` receives an empty generated entry
point.

```dewy
printl("top level")

let main = () => {
    printl("main")
    return 0
}
```

An explicit top-level `main()` call is an ordinary call and does not suppress
automatic entry-point invocation.
