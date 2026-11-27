# Your First Dewy Program

Save this as `hello.dewy`:

<!-- dewy-example: {"mode": "run", "stdout": "Hello, Dewy!\n"} -->
```dewy
printl"Hello, Dewy!"
```

and run it:

```sh
dewy hello.dewy
```

It prints `Hello, Dewy!`. `printl` prints a line; with a single string argument the parentheses are optional, so `printl"Hello, Dewy!"` and `printl("Hello, Dewy!")` mean the same thing.

## Something with a little more to it

A file runs from top to bottom, so a script needs no boilerplate. When a program grows, give it a `main`: it runs once, after the top level, and can receive the command line as `argv`.

<!-- dewy-example: {"mode": "run", "args": ["Ada", "Grace"], "stdout": "Hello, Ada!\nHello, Grace!\n2 names, 8 letters\n"} -->
```dewy
main = (argv:array<string>) => {
    let names = argv[$clamp 1..]      # everything after the program name
    let letters = 0
    loop name in names {
        printl"Hello, {name}!"
        letters += name.length
    }
    printl"{names.length} names, {letters} letters"
}
```

```sh
dewy hello.dewy Ada Grace
```

`argv[$clamp 1..]` takes the elements from position 1 on, and gives an empty array if there are none. A plain `argv[1..]` would not compile here: nothing proves that `argv` has a second element. That is Dewy's central rule at work, and the [tour](../pitch.md#no-hidden-crashes) explains it. For real options and flags, use the [`argparse` library](../pitch.md#whole-programs).

## Check, build, repeat

```sh
dewy check hello.dewy                      # errors only, no executable
dewy build hello.dewy -o hello             # a native executable
dewy build hello.dewy --release -o hello   # optimized
dewy build hello.dewy --target wasm32 -o hello.html   # a web page
dewy watch hello.dewy Ada                  # rerun after every save
```

`dewy file.dewy` builds in debug mode and runs the result; nothing is left behind. `check` is the fastest way to see every error, and it is what the editor runs as you type. A file can also choose its own build: `$build.mode = 'release'` or `$target = 'wasm32'` at the top of the main file.

## Try things interactively

Run `dewy` with no file to get a prompt. Definitions stay for the session, and the value of each expression is shown:

```text
>>> let score = 20
>>> twice = (x) => 2x
>>> twice(score) + 2
42
>>> :type score
int
```

`:help` lists the commands, and Ctrl-D leaves. Piping a program in runs it: `echo 'printl"hi"' | dewy`.

## Start a project

`dewy new` writes a starting point with a README:

```sh
dewy new hello-app program     # hello-app/main.dewy
dewy new gold-rush arcade      # a complete collect-and-dodge game
```

The game templates (`arcade`, `platformer`, `3d`, `story` and `online`) are complete, playable programs with menus, sound and tests, and run natively or in a browser. Edit them while `dewy watch` keeps the game running.
