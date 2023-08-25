# Hello, World!

Printing "Hello, World!" is super simple in Dewy. Assuming you've got everything set up, and can invoke the language from the command line, here's how to run your first Dewy program.

## Put Your Code in a Directory

It's probably a good idea to put your code in a dedicated directory.

```bash
$ mdkir code
$ cd code
$ mdkir hello_world
$ cd hello_world
```

## Write the Source Code

Next we'll create the source file. In a text editor of your choosing, create a file called `hello.dewy`. For example, I like using sublime, which can be invoked from the command line:

```bash
$ subl hello.dewy
```

Then in the text editor, enter the following code

```dewy
printl'Hello, World!'
```

This code invokes the `printl` function with the string `'Hello, World!'`. `printl` is a commonly used function which prints the specified text to the terminal, followed by a newline.

When you are done in the text editor, save and close the file.

## Run the Code

Running a dewy file is as simple as invoking the file with the `dewy` command

```bash
$ dewy hello.dewy
```

Which should print `Hello, World!` in the terminal. 

(TODO explain about any build files, possible in a hidden directory)