# Debugging

Dewy compiles to native code, so debugging is a conversation with the compiled program: stop it, look at its values, step it. Two things make that conversation speak Dewy rather than assembly — a `$breakpoint` directive that stops the program and shows the live bindings, and debug line information that lets a native debugger (gdb or lldb) set breakpoints and step by `.dewy` source lines.

## `$breakpoint`

`$breakpoint` is a statement (a metatag directive, like `$assert`; it takes nothing). When the program reaches it, it prints a banner naming the site and then every live binding of the enclosing function — its parameters and locals declared so far, innermost shadowing outer — one per line in the value's literal form (a string quoted, a container or object as its literal, a value that has no printable form as `name : type`):

```text
── breakpoint at t0.dewy:222 ──
  src = "# just a comment\n"
  i = 0
  matches = [[length=17 token_cls=LineComment]]
  longest_match_length = 17
```

At module level it shows the module's bindings. Functions, types, modules, ranges, and the compiler's hidden bindings are not shown.

Then the program stops. **Without a debugger** it waits at a `>>> ` prompt reading stdin. Commands start with a backslash, so that a plain expression stays free for evaluation later:

| input | effect |
|---|---|
| `\c` or an empty line | continue |
| `\q` | quit (exit status 130) |
| `\h` | list the commands |
| anything else | an expression — a compiled program cannot evaluate one yet, so it is refused with a note |

The end of input (a pipe that runs dry, `/dev/null`) continues, so a program with breakpoints left in still runs unattended.

**Under a debugger** (`dewy debug`, or any gdb/lldb attached to the process) the same directive traps into the debugger instead — the program stops on the `$breakpoint` line in your function, with the debugger's prompt and the snapshot already printed. The program decides at runtime by asking the kernel whether it is being traced, so one build serves both uses.

## `dewy debug`

`dewy debug file.dewy args…` builds the program (like `dewy file.dewy`) and runs it under a native debugger — gdb if installed, else lldb (`--debugger` chooses). Every emitted statement carries its Dewy source position, so the debugger's own commands work on `.dewy` files:

```text
(lldb) b t0.dewy:222          # a breakpoint by Dewy line
(lldb) run
(lldb) n                       # step to the next Dewy statement
(lldb) bt                      # the call stack, by Dewy function names
```

The debugger sees Dewy function names (`describe`, `__dewy_user_main` for the program's `main`) and Dewy lines; the prelude's functions appear under their module-mangled names. What it does **not** yet see is Dewy values: `p total` shows a raw word, and a string or an array is a pointer to its runtime layout. Use `$breakpoint` for values for now; describing the layouts to the debugger (so its `p` and its IDE front ends show Dewy values) is the next step, and evaluating typed-in Dewy expressions at a stop comes after the self-hosted compiler.

## How the positions get there

The compiler marks each statement of the µDewy it emits with a `# @loc path:line:column` comment naming the Dewy position it came from; the µDewy compiler turns each into a DWARF line-table row (a `.loc` for the assembler) for whatever it emits next, and a µDewy file compiled on its own reports its own lines the same way. Both are metadata: a program compiled with or without them is the same program, and a µDewy implementation that ignores the markers is still a correct one.
