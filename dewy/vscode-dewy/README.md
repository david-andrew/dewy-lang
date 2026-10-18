# Dewy Language Support for VS Code

Syntax highlighting and basic editor support for the **Dewy** programming language (`.dewy`).

## Features

- Optional compact-core diagnostics, completions, hover types and go-to-definition for saved `.dewy` paths, including unsaved edits
- Syntax highlighting for `.dewy` files
- Bracket matching + auto-closing (`()`, `[]`, `{}`, `""`, `''`)
- Line comments with `#` and nestable block comments with `#{ ... }#`
- Indentation + folding based on `{ ... }`

## Usage

- Open a `.dewy` file and VS Code should automatically use the `dewy` language mode.
- If it doesn't, use the language picker and choose `dewy`.

## Compact-core editor features

On the `restart/sloppy-frontend` branch, build the experimental compiler following
[`core/README.md`](../../core/README.md), then set its executable in VS Code:

```json
{
    "dewy.core.path": "/tmp/dewy-core/bin/dewy-core"
}
```

The toolchain needs its sibling `../lib/`; the frontend runs in-process.
For checkout development, set `dewy.core.path` to the absolute path of
`tools/dewy` instead. That launcher selects/rebuilds the current compiler on each
server start and works even when the editor has opened another project. After
editing compiler sources, use **Dewy: Restart Core Language Server** to pick them
up. `python3 -m tools.core path` instead prints a particular immutable toolchain's
executable; that path continues to select that version after later rebuilds.
The setting is empty by default: highlighting and the existing debugger integration continue to work
without selecting the experimental compiler. With it configured, the extension
starts `dewy-core lsp` in a trusted workspace and sends the current editor text,
including unsaved changes. Save a new buffer to a `.dewy` path before using these
features. Compiler messages appear in Problems; transport errors appear in the
**Dewy Core** output channel. **Dewy: Restart Core Language Server** restarts it.
Changing the compiler-path setting also restarts the server; clearing it stops it.

The core supports a growing language subset and reports unsupported forms. Hover
and completion details use Dewy spelling, including imported library signatures.
Completions include locals, functions, record fields, collection methods, `.length`
and types in annotations. They work on unsaved text and unfinished expressions;
comments and literal string text suppress them, while interpolation expressions
can complete normally. Signatures are described without checking every library
function's body. Generic signatures and instantiated types use Dewy `<T>` notation, including
user declarations and imported containers such as `Pool<Enemy>`.

Format Document uses the core's Dewy formatter on the unsaved buffer, with fixed
four-space indentation. It preserves strings, comments, line breaks and
spacing-sensitive expressions. Results for an older document version are discarded.

**Dewy: Test Current File (Core)** saves open files and runs the current file's
`test "description" { ... }` blocks with the configured compiler. It is also in
the editor context menu. **Dewy: Test Current File in Release Mode (Core)** checks
optimized code. Results appear in the task terminal; compilation errors also
appear in Problems. Use **Tasks: Terminate Task** to stop a run, or **Tasks: Rerun
Last Task** to repeat it. No `tasks.json` or Python test runner is needed. For name
filtering, use `dewy-core test file.dewy words` in a terminal.
**Dewy: Watch Tests in Current File (Core)** keeps that task running and reruns
tests when saved source files, imports or embedded assets change. It recovers
after failing tests and compiler errors. The equivalent terminal command is
`dewy-core test --watch file.dewy words`; add `--release` before the filename to
watch optimized tests. Enter `r` to rerun, `q` to quit, or terminate the editor task.

Rename, signature help and semantic highlighting are not enabled by
this client yet. The existing native-debugger configuration below still targets
the earlier compiler.

The client adapts Sloppy's small JSON-RPC implementation and adds no npm runtime
dependencies. Tests run its actual transport against the native language server
with VS Code API doubles; this is not a desktop extension-host certification.

## Highlighted language constructs

The grammar aims to highlight the following (non-exhaustive) constructs:

- **Keywords**: `let`, `const`, `local_const`, `overload_only`, `if`, `else`, `loop`, `match`, `return`, `yield`, `break`, `continue`, `import`, `from`
- **Word operators**: `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `not`, `as`, `in`, `of`, `transmute`, `or_throw`, and the question forms `in?`, `is?`, `isnt?`, `not=?`
- **Operators**: `=?`, `>?`, `<?`, `>=?`, `<=?`, `<=>`, `=>`, `|>`, `<|`, `->`, `<->`, `:>`, `::`, `:=`, `..`, `...`, `??`, `@`, `@?`, `^`, `//`, `/`, `+`, `-`, `*`, `%`, `\`, `|`, `&`, `~`, `<<`, `>>`, `<<<`, `>>>`, `<<!`, `!>>`, compound assignments such as `+=` and `//=`
- **Constants**: `true`, `false`, `void`, `none`, `end`, `∞`, `∅`
- **Metatags**: `$target`, `$supported_targets`, `$no_prelude`, and other `$name` forms
- **Built-in types**: `int`, `uint`, `int8` … `int64`, `uint8` … `uint64`, `bool`, `string`, `char`, `rational`, `fixed`, `bigint`, `type`, `array<…>`, `dict<…>`, `set<…>`, and the base dimensions `Time`, `Length`, `Mass`, `Current`, `Temperature`, `Amount`, `Luminosity`, `Angle`
- **Type annotations**: `name:Type`, `:>ReturnType`, and unions/intersections `A | B`, `A & B`. Type parameters `<…>` are bracket groups that take part in bracket-pair colorization like `()`/`[]`/`{}` (comparison and shift operators are excluded), and their contents follow Dewy's own rules: bare names are types, `name=` and `name:` are ordinary identifiers, and the right-hand side of `=` is an ordinary expression (`array<int64 length=2>`, `<(x:int64):>int64>`); object types `[name:T …]` likewise. Generic parameter blocks `<T U of Bound>` before a parameter list or object type are bracket groups too: names and bounds are types, `of` is a word operator
- **Ranges**: `[0..n)`, `(a..b]`, and the other mixed-delimiter forms are balanced by the editor itself — the language configuration lets `[` close with `)` and `(` with `]`, so bracket matching and pair colorization treat them as ordinary pairs
- **Functions**: definitions `let name = (…) => …` / `(…):>T => …`, calls `name(…)` and juxtaposed string calls `printl"…"`, and function values `@name` (the `@` is colored as a modifier so it stands apart from punctuation; the same applies to place parameters and arguments)
- **Strings**: `"…"` and `'…'` (including triple-quoted forms) with escape sequences and `{interpolation}`, raw strings `r"…"`, template strings `t"…"`, path strings `p"…"`, heredocs `$"delim" … delim`, rest-of-file strings `$"""`, and packed based strings such as `0b"1111_0000"` and `0x"de ad be ef"`
- **Numbers**: decimal (`1_000_000`), based (`0b101010`, `0t1120`, `0q222`, `0s110`, `0o52`, `0d42`, `0z36`, `0x2a`), and exact decimal/exponent literals (`9.8`, `1.25e2`, `5e-1`)
- **Identifiers**: the full Dewy repertoire — Latin and Greek letters, mathematical letter symbols such as `ℝ` and `ℤ`, `_`, `‾`, `!`, `°`, plus superscript/subscript/prime decorations (`x₁`, `v′`)
- **Comments**: `# line comment` and nestable `#{ block comments }#`

The identifier character classes in the grammar are generated from the compiler's own tokenizer tables (`dewy/parser/t0.py`), and `tests/python_misc/test_dewy_highlighting.py` checks that the keyword and operator lists stay in step with the parser.

## Debugging with the compact core

Set `dewy.core.path` as above and install
[CodeLLDB](https://open-vsx.org/extension/vadimcn/vscode-lldb). Open a `.dewy`
file and run **Dewy: Debug Current File (Core)** from the command palette.
The extension saves modified files, builds with `-g`, and starts the debugger.
Breakpoints, local variables and record fields use the compiler's DWARF data;
the active toolchain supplies formatters for strings, arrays and other values.
Panics stop in `__panic` by default. Build errors appear in **Dewy Core Debug**
output and prevent launch.

For F5 and program arguments, add a **Dewy compact core** configuration:

```json
{
    "type": "dewy-core",
    "request": "launch",
    "name": "Dewy core: current file",
    "program": "${file}",
    "args": ["--level", "practice"],
    "cwd": "${workspaceFolder}"
}
```

`program` names source, not an executable. `args` can also be a shell-style
string, including `${command:dewy.programArguments}` to use the argument prompt.
`env` sets the program's environment, and `stopOnPanic: false` disables the panic
breakpoint. Without `cwd`, execution starts in the source file's directory.
Each launch gets its own executable, removed when its debug session ends.
No build task or formatter path needs to be maintained in the project.
This workflow targets the compact core's native programs; it does not debug
browser/WebAssembly builds.

### Original compiler configurations

The extension lets you set breakpoints in `.dewy` files (click the gutter). The debugging itself is done by the stock [CodeLLDB](https://open-vsx.org/extension/vadimcn/vscode-lldb) extension (`lldb`; also on Open VSX for Cursor and VSCodium) — the Dewy compiler emits DWARF for its source, and its `tools/dewy_lldb.py` script shows values the Dewy way in the Variables pane, hovers, and the Debug Console. "Add Configuration…" in `launch.json` offers **Dewy: debug current file** and **Dewy: debug current file with arguments** (the latter asks for the program's command line each run, offering the last one again, and splits it like a shell). Both build the active file with `dewy debug --build` (a `tasks.json` task named `dewy: build debug`) and launch `__dewycache__/<path>/<name>.debug`. Fill in where the script lives: `tools/` of a checkout, or `~/.dewy/runtime/tools` of an installation. The task:

```json
{
    "label": "dewy: build debug",
    "type": "shell",
    "command": "dewy",
    "args": ["debug", "--build", "${file}"],
    "options": { "cwd": "${workspaceFolder}" },
    "problemMatcher": []
}
```

See the Reference's [Debugging](https://dewy-lang.org/reference/debugging.html) page for the details, the gdb (C/C++ extension) form, and the terminal experience (`dewy debug`, `$breakpoint`).

## Limitations and roadmap

The TextMate grammar is the fast lexical first pass. The optional core client
adds diagnostics, completions, hover and definitions from the compiler. The grammar cannot
resolve overloads or distinguish every bracket use; richer semantic editor
features can be enabled as their Dewy behavior is verified.

## Repository

The extension lives in the `dewy-lang` repository: `https://github.com/david-andrew/dewy-lang` under `dewy/vscode-dewy/`.

## License

GPL-3.0
