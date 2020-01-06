# Hello, World!

Printing "Hello, World!" is super simple in Dewy. Assuming you've got everything set up, and can invoke the language from the command line, here's how to run your first Dewy program.

## Put Your Code in a Directory

It's probably a good idea to put your code in a dedicated directory.

```bash
$ mdkir ~/code
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
printn('Hello, World!')
```

This code invokes the `printn` function with the string `'Hello, World!'`. `printn` is a commonly used function which prints the specified text to the terminal, followed by a newline.

When you are done in the text editor, save and close the file.

## Run the Code

Running a dewy file is as simple as invoking the file with the `dewy` command

```bash
$ dewy hello.dewy
```

Which should print `Hello, World!` in the terminal. Note that in addition to printing that string, a new executable file named `hello` has appeared in the directory

```bash
$ ls
hello.dewy hello
```

This is because Dewy is a compiled language. Calling the `dewy` command on a source file will compile that file into an executable (the `hello` file in this case), and then run that executable. 

If you would instead like to separately compile, and then execute your code, you may do the following:

```bash
$ dewyc hello.dewy  #compile the file
$ ./hello           #execute the compiled file
```