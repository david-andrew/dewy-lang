# Your First Dewy Program

Create a directory for the program:

```bash
mkdir -p ~/code/greetings
cd ~/code/greetings
```

Create `greetings.dewy` with this source:

<!-- dewy-example: compiler -->
```dewy
let greet = (name:string):>void =>
    printl"Hello, {name}!"

let names = ["Ada" "Grace" "Linus"]

loop name in names
    greet(name)
```

Run it:

```bash
dewy greetings.dewy
```

The output is:

```text
Hello, Ada!
Hello, Grace!
Hello, Linus!
```

This small program already shows several recurring parts of Dewy:

- `let` introduces a binding;
- `(name:string):>void => ...` defines a function with one string parameter;
- whitespace separates array elements, so commas are unnecessary;
- `loop name in names` consumes the array from left to right;
- `{name}` interpolates a value into a string;
- `printl` prints text followed by a newline.

The one-line traditional greeting is valid too:

<!-- dewy-example: compiler -->
```dewy
printl'Hello, World!'
```

Juxtaposing a callable with its argument can express a call, so this is equivalent to `printl('Hello, World!')`.

## Top-Level Code and `main`

Dewy executes top-level code in source order. A small program therefore needs no special entry wrapper.

When a module declares `main`, its top level still initializes first and Dewy calls `main` afterward:

<!-- dewy-example: compiler -->
```dewy
const application_name = "notes"

let main = ():>int64 => {
    printl"starting {application_name}"
    return 0
}
```

An explicit top-level `main()` is an ordinary call; it does not replace automatic entry invocation.

For ordinary use, `dewy` compiles and runs the program in one command. The hosted compiler lowers Dewy to µDewy, after which the selected µDewy backend produces the executable form.
