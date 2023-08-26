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


## How it Works

This code invokes the `printl` function with the string `'Hello, World!'`. `printl` is a commonly used function that takes text and prints it to the terminal, followed by a newline.


## Compiling and Running Are the Same Step

**NOTE: this is not relevant until the LLVM/other compiler backends are implemented.**

When you run the program, you are actually doing two things: first compiling, and then running.

Compiling is the process that translates the code from Dewy, which your computer doesn't understand natively, to machine language which it does understand. The resulting translation is saved to a file, called an **executable**, that your computer can run directly. Once the executable is created, the `dewy` command then automatically runs it for you.

All of this goes on under the hood, so you don't have to worry about it. But you might notice the effects of this process, e.g. the first time you run a program, it might take a bit longer than subsequent runs. Additionally, you might notice a hidden directory containing the executable, and perhaps other files related to the compilation process. In this case, the directory is called `.hello/` and contains the executable `hello`.