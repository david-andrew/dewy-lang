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

`dewy debug file.dewy args…` makes a debug build of the program and runs it under a native debugger — gdb if installed, else lldb (`--debugger` chooses). Every emitted statement carries its Dewy source position and every variable its Dewy name and type, so the debugger's own commands work on `.dewy` files and show Dewy values:

```text
(lldb) b t0.dewy:222          # a breakpoint by Dewy line
(lldb) run
(lldb) n                       # step to the next Dewy statement
(lldb) bt                      # the call stack, by Dewy function names
(lldb) frame variable          # the live bindings, as Dewy prints them
(array<Hit>) hits = [Hit[length=3 name="a"] Hit[length=10 name="b"]]
(string) label = "run"
(int64 | none) maybe = none
(int64) total = 9
(Hit) h = Hit[length=3 name="a"]
(lldb) p total                 # or one value
(int64) 9
```

A variable is visible from its declaration on, a parameter throughout its function (gdb's `info args`, and frames print as `describe (hits=[…], label="run")`), and a loop variable under its own name. Values print exactly as `"{value}"` would — a string in its literal form, a container or object as its literal, a union as its member. The debugger sees Dewy function names (`describe`, `__dewy_user_main` for the program's `main`); the prelude's functions appear under their module-mangled names, and its variables as words. gdb and lldb are both supported, with the same view.

The debug build is a separate artifact (`<name>.debug` beside the ordinary binary): the value display costs compile time and size, so `dewy file.dewy` builds without it. An ordinary binary still has the line information — `$breakpoint` traps into an attached debugger, breakpoints and stepping work — but its variables show as raw words.

## How the debugger sees Dewy

Positions: the compiler marks each statement of the µDewy it emits with a `# @loc path:line:column` comment naming the Dewy position it came from; the µDewy compiler turns each into a DWARF line-table row (a `.loc` for the assembler) for whatever it emits next, and a µDewy file compiled on its own reports its own lines the same way.

Variables: each declaration is marked `# @var name shown formatter type`; the µDewy compiler records every variable (a fixed slot in the frame) with the name it is shown under and its type, in a lexical block that starts at the declaration, as DWARF variable information. Values: for each type of a variable in a debug build, the compiler adds a function `__dewy_debug_show_N = (v:T):>int64` that renders a value the way `"{v}"` does into a static text block; the variable's DWARF type is named after it, and the debugger scripts `dewy debug` loads (`tools/dewy_lldb.py`, `tools/dewy_gdb.py`) call that function on the stopped frame's word and read the text back. A type the module cannot spell or print (a function, a `bigint` under a unit) gets no formatter and shows as a word.

All of it is metadata: a program compiled with or without it is the same program, and a µDewy implementation that ignores the markers is still a correct one — though both µDewy compilers, the Python one and the bootstrap one written in µDewy, emit it (a parity test keeps their assembly identical). Evaluating typed-in Dewy expressions at a stop, and an IDE front end, come next.
