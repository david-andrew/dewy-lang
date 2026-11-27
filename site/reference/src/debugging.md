# Debugging

> [Generated coverage](/status/#ref-debugging) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Failure Reports

A failed runtime check or `$runtime_assert` prints `panic:`, the site, the requirement and the values it saw, then the program's own call chain, to standard error. The program exits with status 101. Compiler-made helpers are left out of the chain.

<!-- dewy-example: {"mode":"run","stdout":"20\n","exit":101} -->
```dewy
withdraw = (balance:int amount:int):>int => {
    let left = balance - amount
    $runtime_assert left >=? 0, "overdrawn by {-left}"
    left
}
main = () => {
    printl(withdraw(30 10))
    printl(withdraw(10 25))
}
```

```text
panic: example.dewy:3: overdrawn by 15
    in withdraw (example.dewy:3)
    called from main (example.dewy:8)
```

A bounds check under `$runtime_checks` reports the same way: `panic: file.dewy:2: index 5 out of bounds (length 3)`.

An error value that reaches `main` prints its kind and its `message` field (`error: ParseError: …`). A debug build with `-g` prints the whole payload. A `secret<T>` value prints as `<redacted>` there too, and in debuggers.

`dewy check --obligations file.dewy` lists every obligation that compiles to a runtime check, with the setting responsible:

```text
file.dewy:2:40: runtime check: index is in bounds: missing lower and upper bounds ($runtime_checks)
```

## Debug Output

`console.debug(…)` writes to standard error in debug builds. Release builds leave the call out and do not evaluate its arguments. `console.info`, `console.warn` and `console.error` print in every build; `printl(x file=stderr)` writes any value to standard error.

<!-- dewy-example: {"mode":"run","stdout":"result\n"} -->
```dewy
printl("result")
console.debug("only in debug builds: {6*7}")
console.warn("cache is stale")
```

## `$breakpoint`

`$breakpoint` is a statement. It takes no arguments. When the program reaches it, it prints to standard error a banner naming the site and every live binding of the enclosing function (parameters, and locals declared so far), one per line in literal form, strings quoted. Functions, types, ranges and the compiler's hidden bindings are left out. At the top level it shows only local bindings.

<!-- dewy-example: {"mode":"check"} -->
```dewy
total = (xs:array<int>):>int => {
    let sum = 0
    loop x in xs { sum = sum + x }
    $breakpoint
    sum
}
printl(total([1 2 3]))
```

```text
── breakpoint at example.dewy:4 ──
  xs = [1 2 3]
  sum = 6
>>>
```

Then the program reads commands from standard input at a `>>> ` prompt:

| Input | Effect |
|---|---|
| `\c` or an empty line | continue |
| `\q` | quit with status 130 |
| `\h` | list the commands |
| anything else | refused: a compiled program cannot evaluate an expression yet |

The end of input continues, so a program with breakpoints left in still runs unattended (`< /dev/null`, a pipe that runs dry).

The design also has `$breakpoint` trap into an attached debugger instead of prompting. That is not built: under a debugger it still prompts, so set a native breakpoint on the line.

## Native Debuggers

Build with `-g` and without `--release` for variable-level debugging: it keeps local variable locations instead of running the default local optimization pass.

```sh
dewy-core build program.dewy -g -o program-debug
gdb ./program-debug
```

Types carry their Dewy spellings. `lib/debug/dewy_gdb.py` (load with gdb's `source`) and `lib/debug/dewy_lldb.py` (lldb's `command script import`) show values the way string interpolation prints them: `int` as its number, strings quoted, and arrays, records, optionals, unions and dictionaries as their literals. `lib/debug/dewy.natvis` does the same for Visual Studio. `dewy-core --print-lib` prints the library directory.

The VS Code extension debugs through CodeLLDB; set `dewy.core.path` to the standalone `bin/dewy-core` or the checkout's `tools/dewy`. See the [extension guide](https://github.com/david-andrew/dewy-lang/blob/master/editors/vscode/README.md).
