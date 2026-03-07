# udewy Language Support for VS Code

Syntax highlighting and basic editor support for the **udewy** programming language (`.udewy`).

## Features

- Syntax highlighting for `.udewy` files
- Bracket matching + auto-closing (`()`, `[]`, `{}`, `""`)
- Line comments with `#`
- Indentation + folding based on `{ ... }`

## Usage

- Open a `.udewy` file and VS Code should automatically use the `udewy` language mode.
- If it doesn’t, use the language picker and choose `udewy`.

## Highlighted language constructs

The grammar aims to highlight the following (non-exhaustive) constructs:

- **Keywords**: `let`, `const`, `if`, `else`, `loop`, `return`, `break`, `continue`, `import`
- **Word operators**: `and`, `or`, `xor`, `not`, `transmute`
- **Operators**: `=?`, `>?`, `<?`, `>=?`, `<=?`, `=>`, `|>`, `=`, `+=`, `-=`, `*=`, `//=`, `%=`, `<<`, `>>`, `<<=`, `>>=`, `//`, `+`, `-`, `*`, `%`
- **Constants**: `true`, `false`, `void`
- **Intrinsics**: `__syscall0__` … `__syscall6__`, `__load64__`, `__store64__`, `__load8__`, `__store8__`, `__load16__`, `__store16__`, `__load32__`, `__store32__`
- **Type annotations**: `:Type` and `:>ReturnType`
- **Strings**: `"double quoted"` with escape sequences, and path strings like `p"..."` (highlighted as strings)
- **Numbers**: decimal (`123`), hex (`0xDEAD_BEEF`), binary (`0b1010_0101`)
- **Comments**: `# line comment`

## Limitations

This extension currently provides a TextMate grammar + language configuration (highlighting, brackets, comments, folding). It does not include language-server features like go-to-definition, rename, diagnostics, or formatting.

## Repository

The extension lives in the `dewy-lang` repository: `https://github.com/david-andrew/dewy-lang`.

## License

GPL-3.0
