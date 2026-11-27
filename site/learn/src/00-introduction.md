# Welcome to Dewy

Dewy is a general-purpose programming language with three goals:

- **Python-like ease.** Scripts need no boilerplate, types are inferred, and the syntax stays small: one `loop`, one way to write a function, records and arrays written as literals.
- **C-like speed.** Programs compile to native machine code (or WebAssembly), values are laid out densely, and integers are machine words whenever they fit.
- **No hidden crashes.** An index, a division or a narrowing conversion that might fail has to be proven safe, handled as a value, or checked on purpose. Otherwise the program does not compile.

<!-- dewy-example: {"mode": "run", "stdout": "Hello, Dewy!\n"} -->
```dewy
printl"Hello, Dewy!"
```

## How to read this book

- Start with **[A Tour of Dewy](pitch.md)** for the whole language on one page.
- **[Safer than Rust](safer-than-rust.md)** explains the safety rules and how they compare with Rust's.
- **[Getting Started](ch01/00-getting-started.md)** installs Dewy and walks through your first programs, the edit loop and debugging.
- **The Core Language** and the chapters after it take one topic at a time.

Every Dewy example in this book is compiled and run by the website build with the current compiler, under the default rules (no runtime checks switched on), and the output shown is the output it printed. The [reference](/reference/) holds the complete language design, including parts the compiler does not build yet.

Dewy is young. The language is at version 0.0.0, there is no stable release, and details can change between versions.
