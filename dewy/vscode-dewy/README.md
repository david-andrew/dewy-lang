# Dewy Language Support for VS Code

Syntax highlighting and basic editor support for the **Dewy** programming language (`.dewy`).

## Features

- Syntax highlighting for `.dewy` files
- Bracket matching + auto-closing (`()`, `[]`, `{}`, `""`, `''`)
- Line comments with `#` and nestable block comments with `#{ ... }#`
- Indentation + folding based on `{ ... }`

## Usage

- Open a `.dewy` file and VS Code should automatically use the `dewy` language mode.
- If it doesn't, use the language picker and choose `dewy`.

## Highlighted language constructs

The grammar aims to highlight the following (non-exhaustive) constructs:

- **Keywords**: `let`, `const`, `local_const`, `overload_only`, `if`, `else`, `loop`, `match`, `return`, `yield`, `break`, `continue`, `import`, `from`
- **Word operators**: `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `not`, `as`, `in`, `of`, `transmute`, and the question forms `in?`, `is?`, `isnt?`, `not=?`
- **Operators**: `=?`, `>?`, `<?`, `>=?`, `<=?`, `<=>`, `=>`, `|>`, `<|`, `->`, `<->`, `:>`, `::`, `:=`, `..`, `...`, `??`, `@`, `@?`, `^`, `//`, `/`, `+`, `-`, `*`, `%`, `\`, `|`, `&`, `~`, `<<`, `>>`, `<<<`, `>>>`, `<<!`, `!>>`, compound assignments such as `+=` and `//=`
- **Constants**: `true`, `false`, `void`, `undefined`, `end`, `∞`, `∅`
- **Metatags**: `$target`, `$supported_targets`, `$no_prelude`, and other `$name` forms
- **Built-in types**: `int`, `uint`, `int8` … `int64`, `uint8` … `uint64`, `bool`, `string`, `char`, `rational`, `fixed`, `bigint`, `type`, `array<…>`, `dict<…>`, `set<…>`, and the base dimensions `Time`, `Length`, `Mass`, `Current`, `Temperature`, `Amount`, `Luminosity`, `Angle`
- **Type annotations**: `name:Type`, `:>ReturnType`, and unions/intersections `A | B`, `A & B`. Type parameters `<…>` are bracket groups that take part in bracket-pair colorization like `()`/`[]`/`{}` (comparison and shift operators are excluded), and their contents follow Dewy's own rules: bare names are types, `name=` and `name:` are ordinary identifiers, and the right-hand side of `=` is an ordinary expression (`array<int64 length=2>`, `<(x:int64):>int64>`); object types `[name:T …]` likewise
- **Ranges**: `[0..n)`, `(a..b]`, and the other mixed-delimiter forms are balanced by the editor itself — the language configuration lets `[` close with `)` and `(` with `]`, so bracket matching and pair colorization treat them as ordinary pairs
- **Functions**: definitions `let name = (…) => …` / `(…):>T => …`, calls `name(…)` and juxtaposed string calls `printl"…"`, and function values `@name` (the `@` is colored as a modifier so it stands apart from punctuation; the same applies to place parameters and arguments)
- **Strings**: `"…"` and `'…'` (including triple-quoted forms) with escape sequences and `{interpolation}`, raw strings `r"…"`, template strings `t"…"`, path strings `p"…"`, heredocs `$"delim" … delim`, rest-of-file strings `$"""`, and packed based strings such as `0b"1111_0000"` and `0x"de ad be ef"`
- **Numbers**: decimal (`1_000_000`), based (`0b101010`, `0t1120`, `0q222`, `0s110`, `0o52`, `0d42`, `0z36`, `0x2a`), and exact decimal/exponent literals (`9.8`, `1.25e2`, `5e-1`)
- **Identifiers**: the full Dewy repertoire — Latin and Greek letters, mathematical letter symbols such as `ℝ` and `ℤ`, `_`, `‾`, `!`, `°`, plus superscript/subscript/prime decorations (`x₁`, `v′`)
- **Comments**: `# line comment` and nestable `#{ block comments }#`

The identifier character classes in the grammar are generated from the compiler's own tokenizer tables (`dewy/parser/t0.py`), and `tests/python_misc/test_dewy_highlighting.py` checks that the keyword and operator lists stay in step with the parser.

## Limitations and roadmap

This extension currently provides a TextMate grammar + language configuration (highlighting, brackets, comments, folding). Highlighting is purely lexical: it cannot tell a type name from a variable outside annotation positions, resolve overloads, or know which `[…]` is an array, object, dictionary, or set literal.

Once the bootstrap Dewy compiler exists, this grammar will be combined with a proper Dewy language server (LSP) that provides semantic highlighting from the type checker, go-to-definition, hover types (including refinements and inferred integer representations), member listing, rename, diagnostics, and formatting. The TextMate grammar will remain as the fast first pass and as the fallback for editors without LSP support.

## Repository

The extension lives in the `dewy-lang` repository: `https://github.com/david-andrew/dewy-lang` under `dewy/vscode-dewy/`.

## License

GPL-3.0
