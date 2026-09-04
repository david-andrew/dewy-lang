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

## In an editor

Cursor, VS Code, and VSCodium debug Dewy through their stock native-debugger extensions — CodeLLDB (`lldb`, on Open VSX too) or C/C++ (`cppdbg`, gdb) — since the program carries DWARF for its Dewy source and the `dewy_lldb.py` / `dewy_gdb.py` scripts give the Variables pane, hovers, and the Debug Console Dewy values. The Dewy extension registers `.dewy` files for gutter breakpoints and offers the two launch configurations under "Add Configuration…"; written out, with a task that builds the debug executable first (`dewy debug --build file.dewy` prints its path, `__dewycache__/<path>/<name>.debug`, and launches nothing):

```json
// launch.json
{
    "name": "Dewy: debug current file (lldb)",
    "type": "lldb",
    "request": "launch",
    "program": "${workspaceFolder}/__dewycache__/${relativeFileDirname}/${fileBasenameNoExtension}.debug",
    "cwd": "${workspaceFolder}",
    "preLaunchTask": "dewy: build debug",
    "initCommands": ["command script import ~/.dewy/runtime/tools/dewy_lldb.py"],
    "sourceLanguages": ["c"]
}
// tasks.json
{
    "label": "dewy: build debug",
    "type": "shell",
    "command": "dewy",
    "args": ["debug", "--build", "${file}"],
    "options": { "cwd": "${workspaceFolder}" },
    "problemMatcher": []
}
```

A program that takes arguments — the tokenizer wants the file to tokenize — gets them from `"args"`: a fixed list (`"args": ["tests/sample.dewy"]`), or, in the CodeLLDB form, a prompt each run through a launch input (`"args": "${input:programArguments}"` with an `inputs` entry of type `promptString`; CodeLLDB splits the string like a shell). The repository's `launch.json` has both — **Dewy: debug current file with arguments (lldb)** asks for the command line, and **Dewy: t0 on current file (lldb)** runs the bootstrap tokenizer on whatever file is open in the editor (`"args": ["${file}"]`, with its own build task for `t0.dewy`), so a breakpoint in `t0.dewy` plus a `.dewy` file in the active editor is the whole setup.

The gdb form is the same with `"type": "cppdbg"`, `"MIMode": "gdb"`, and `"setupCommands": [{ "text": "source ~/.dewy/runtime/tools/dewy_gdb.py" }]`. (CodeLLDB is the one exercised by the compiler's own tests, through its debug adapter.) In a checkout of the compiler the scripts are `${workspaceFolder}/tools/…` and the command `python -m dewy` (the repository's own `.vscode/launch.json` is exactly this). Gutter breakpoints, stepping, the call stack, and the Variables pane then behave as for any native program, with Dewy names, lines, and values; a `$breakpoint` in the program pauses the editor on its line. The `>>>` prompt of a program run *without* a debugger belongs to the terminal, not the editor.

## How the debugger sees Dewy

Positions: the compiler marks each statement of the µDewy it emits with a `# @loc path:line:column` comment naming the Dewy position it came from; the µDewy compiler turns each into a DWARF line-table row (a `.loc` for the assembler) for whatever it emits next, and a µDewy file compiled on its own reports its own lines the same way.

Variables: each declaration is marked `# @var name shown formatter type`; the µDewy compiler records every variable (a fixed slot in the frame) with the name it is shown under and its type, in a lexical block that starts at the declaration, as DWARF variable information. Values: for each type of a variable in a debug build, the compiler adds a function `__dewy_debug_show_N = (v:T):>int64` that renders a value the way `"{v}"` does into a static text block; the variable's DWARF type is named after it, and the debugger scripts `dewy debug` loads (`tools/dewy_lldb.py`, `tools/dewy_gdb.py`) call that function on the stopped frame's word and read the text back. A type the module cannot spell or print (a function, a `bigint` under a unit) gets no formatter and shows as a word.

All of it is metadata: a program compiled with or without it is the same program, and a µDewy implementation that ignores the markers is still a correct one — though both µDewy compilers, the Python one and the bootstrap one written in µDewy, emit it (a parity test keeps their assembly identical). Evaluating typed-in Dewy expressions at a stop, and an IDE front end, come next.
