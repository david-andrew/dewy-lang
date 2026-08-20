# Hello, World!

Most languages start by printing `Hello, World!`. Dewy makes that a
one-liner.

## Put Your Code in a Directory

```bash
mkdir -p ~/code/hello_world
cd ~/code/hello_world
```

## Write the Source

Create `hello.dewy` and enter:

```dewy
printl'Hello, World!'
```

`printl` writes a string to the terminal and adds a newline. Juxtaposing
`printl` with a string is a function call, the same as
`printl('Hello, World!')`. `print` does the same thing without the
newline.

## Run It

```bash
dewy hello.dewy
```

That should print `Hello, World!`.

## Top-Level Execution and `main`

Dewy runs top-level code in source order. A program does not need a
`main` function.

When a module declares `main`, the top level still runs first, then Dewy
invokes `main`. `main` takes no arguments and returns an integer exit
code or `void`.

```dewy
let message = 'Hello'
printl'{message} from the top level'

let main = () => {
    printl'Hello from main'
    return 0
}
```

An explicit `main()` at the top level is an ordinary call. Dewy still
invokes `main` after the top level finishes, so that program would call
`main` twice.

## Compiling and Running Are the Same Step

`dewy` compiles the source and then runs it. You do not need a separate
compile command for ordinary use.

The hosted compiler lowers Dewy to µDewy, then the µDewy backend
assembles and runs it. Intermediate files go under `__dewycache__/`.
