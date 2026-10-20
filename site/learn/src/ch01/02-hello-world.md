# Your First Dewy Program

Save this as `hello.dewy`:

<!-- dewy-example: {"mode": "run", "stdout": "Hello, Dewy!\n"} -->
```dewy
printl"Hello, Dewy!"
```

```sh
dewy check hello.dewy
dewy hello.dewy
dewy build hello.dewy --release -o hello
```

The output is `Hello, Dewy!` followed by a newline. Check source without emitting a binary; build when you want to keep an executable. In a checkout, replace `dewy` with `./tools/dewy`.
