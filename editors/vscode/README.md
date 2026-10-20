# Dewy for VS Code

Language support for [Dewy](https://github.com/david-andrew/dewy-lang) (`.dewy`): a language with
Python-like ease, C-like speed, and safety by default. Editor features come from the Dewy
compiler itself, so they follow the language exactly, including your unsaved edits.

Dewy is young and changes quickly; this extension tracks the compiler in the repository.

## Features

- **Diagnostics as you type**: the compiler's errors and warnings for the edited file and the
  files it imports, from unsaved text.
- **Completion**: locals, functions, record fields, members (`xs.`), types in annotations,
  keywords, `$` directives, the names a module exports (`from p"model.dewy" import …`) and
  file paths in `p"…"` imports.
- **Hover**: inferred types and signatures in Dewy notation (`array<int64>`, `<T>(x: T):>T`),
  with the comments above a declaration as its documentation.
- **Navigation**: Go to Definition (including into imported files and import paths), Find All
  References, highlighted occurrences, Outline and Go to Symbol in Workspace.
- **Rename** across files, including workspace files that are not open; refused when it would
  collide with another name or touch the standard library.
- **Signature help** for Dewy's space-separated arguments, following named arguments
  (`f(scale=2)`) and nested calls.
- **Semantic highlighting**: parameters, locals, fields, functions, methods, types and library
  names, with declarations and constants marked.
- **Inlay hints**: the inferred types of variables and function results.
- **Quick fixes** the compiler suggests: `@f` for a function value, Dewy member spellings
  (`startswith`, `xs.pop(i)`), misspelled names, `@` for updating loop elements.
- **Format Document** with the compiler's formatter.
- **Run, test and debug**: code lenses above `main` (Run, Debug) and `test "…"` blocks
  (Run test, Run all tests), editor title buttons, and debugging with CodeLLDB.
- **Syntax highlighting** for the current surface: directives (`$assert`), `@` handles and
  places, units (`300ms`), `or_throw`, `=?`/`<?`/`is?` operators, angle-bracket types, string
  interpolation, raw and path strings, based numbers, byte literals and nestable `#{ … }#`
  block comments.

## Getting the compiler

The extension finds a compiler in this order and never downloads one by itself:

1. the `dewy.core.path` setting;
2. the toolchain bundled in the platform builds of this extension (Linux x64 and arm64,
   macOS Apple silicon, Windows x64);
3. an installed toolchain, `~/.dewy/bin/dewy-core` (`%USERPROFILE%\.dewy\bin\dewy-core.cmd` on
   Windows);
4. `dewy-core` on the `PATH`.

On the platforms above, installing the extension is enough. Elsewhere, install Dewy or build
the compiler (see the repository's [development guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/DEVELOPMENT.md))
and set `dewy.core.path`. Highlighting works without a compiler.

Working on the compiler itself? Point `dewy.core.path` at the checkout's `tools/dewy` launcher:
it rebuilds the compiler when its sources change. Run **Dewy: Restart Language Server** to pick
up a new build.

## Settings

| Setting | Default | |
|---|---|---|
| `dewy.core.path` | `""` | The `dewy-core` compiler, or a checkout's `tools/dewy`. Empty: discover one as above. A standalone toolchain keeps its `lib/` beside `bin/`. |

Compiler-backed features start once the workspace is trusted; untrusted workspaces get
highlighting only.

## Commands

- **Dewy: Run Current File**, **Dewy: Debug Current File**
- **Dewy: Test Current File**, **… in Release Mode**, **Dewy: Watch Tests in Current File**:
  run the file's `test "…" { … }` blocks in a task terminal. Watching reruns them after saved
  edits to the file, its imports or embedded assets.
- **Dewy: Restart Language Server**

Runs and tests save open files first; compiler errors also appear in Problems. Use
**Tasks: Terminate Task** to stop one.

## Debugging

Install [CodeLLDB](https://marketplace.visualstudio.com/items?itemName=vadimcn.vscode-lldb)
(also on Open VSX). **Dewy: Debug Current File**, the Debug lens or F5 builds the program with
variable information and starts it: breakpoints in `.dewy` files, locals and record fields, and
formatters for strings, arrays and other Dewy values. Panics stop in the debugger. For
arguments, add a configuration:

```json
{
    "type": "dewy-core",
    "request": "launch",
    "name": "Dewy: current file",
    "program": "${file}",
    "args": ["--level", "practice"],
    "cwd": "${workspaceFolder}"
}
```

`program` is the source file. `args` may be a shell-style string, such as
`"${command:dewy.programArguments}"` to be asked each run. `env` sets the environment;
`"stopOnPanic": false` keeps running past panics. Debugging covers native programs, not
WebAssembly builds.

## Limitations

- Each check runs the compiler afresh in a child process (tens to a few hundred milliseconds),
  so diagnostics and completions trail typing slightly; hover, definitions, highlights and
  semantic tokens answer from the last check in well under a millisecond.
- The compiler implements a growing subset of the Dewy design and reports unsupported forms as
  errors.
- References search the workspace's `.dewy` files that mention the name; files outside the
  workspace folders are not searched.

## License

GPL-3.0. The language client and debug workflow adapt MIT-licensed code from Sloppy; see
THIRD_PARTY_NOTICES.md.
