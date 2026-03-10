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
- **Intrinsics**: `__load__`, `__store__`, `__load_u64__`, `__store_u64__`, `__load_i64__`, `__store_i64__`, `__load_u32__`, `__store_u32__`, `__load_i32__`, `__store_i32__`, `__load_u16__`, `__store_u16__`, `__load_i16__`, `__store_i16__`, `__load_u8__`, `__store_u8__`, `__load_i8__`, `__store_i8__`, `__signed_shr__`, `__unsigned_idiv__`, `__unsigned_mod__`, `__unsigned_lt__`, `__unsigned_gt__`, `__unsigned_lte__`, `__unsigned_gte__`, `__alloca__`
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
