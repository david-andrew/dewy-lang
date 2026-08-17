# Hello, World!

It's traditional in most languages to write a small program that prints "Hello, World!" to the screen. Achieving this is super simple in Dewy!

## Put Your Code in a Directory

It's probably a good idea to put your code in a dedicated folder.

```bash
$ mdkir ~/code
$ cd ~/code
$ mdkir hello_world
$ cd hello_world
```

## Write the Source Code

Next we'll create the source file. In a text editor of your choosing, create a file called `hello.dewy`.

Then in the text editor, enter the following code

```dewy
printl'Hello, World!'
```

When you are done in the text editor, save and close the file.

## Run the Code

Running a dewy file is as simple as invoking the file with the `dewy` command

```bash
$ dewy hello.dewy
```

Which should print `Hello, World!` in the terminal. 

## Top-Level Execution and `main`

Dewy executes top-level code in source order. A program does not need a
`main` function, as the example above demonstrates.

When a module declares `main`, Dewy runs the complete top level first and then
automatically invokes `main`. For now, an automatically invoked `main` takes no
arguments and returns either an integer exit code or `void`; its return type may
be inferred.

```dewy
let message = 'Hello'
printl'{message} from the top level'

let main = () => {
    printl'Hello from main'
    return 0
}
```

An explicit `main()` at the top level is an ordinary call. It does not suppress
the automatic invocation, so that program calls `main` once in sequence and
once again after top-level execution finishes.


## How it Works

This code invokes the `printl` function with the string `'Hello, World!'`. `printl` is a commonly used function that takes text and prints it to the terminal, followed by a newline. `print` and `printl` currently work on Linux x86_64 only.


## Compiling and Running Are the Same Step

> NOTE: this is not relevant until the LLVM/other compiler backends are implemented.

When you run the program, you are actually doing two things: first compiling, and then running.

Compiling is the process that translates the code from Dewy, which your computer doesn't understand natively, to machine language which it does understand. The resulting translation is saved to a file, called an **executable**, that your computer can run directly. Once the executable is created, the `dewy` command then automatically runs it for you.

All of this goes on under the hood, so you don't have to worry about it. But you might notice the effects of this process, e.g. the first time you run a program, it might take a bit longer than subsequent runs. Additionally, you might notice a hidden directory containing the executable, and perhaps other files related to the compilation process. In this case, the directory is called `.hello/` and contains the executable `hello`.