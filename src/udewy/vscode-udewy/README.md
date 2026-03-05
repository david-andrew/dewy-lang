# Udewy Language Support for VS Code

Syntax highlighting for the Udewy programming language.

## Features

- Syntax highlighting for `.udewy` files
- Bracket matching and auto-closing
- Comment toggling with `#`

## Installation

### From Source (Development)

1. Copy or symlink this folder to your VS Code extensions directory:

   ```bash
   # Linux
   ln -s /path/to/editors/vscode-udewy ~/.vscode/extensions/udewy

   # macOS
   ln -s /path/to/editors/vscode-udewy ~/.vscode/extensions/udewy

   # Windows (PowerShell as Admin)
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.vscode\extensions\udewy" -Target "C:\path\to\editors\vscode-udewy"
   ```

2. Restart VS Code or run `Developer: Reload Window`

### Package as VSIX

1. Install vsce: `npm install -g @vscode/vsce`
2. Package: `vsce package`
3. Install the generated `.vsix` file via VS Code

## Language Syntax

Udewy is highlighted with support for:

- **Keywords**: `let`, `const`, `if`, `else`, `loop`, `return`, `break`, `continue`
- **Operators**: `and`, `or`, `xor`, `not`, `=?`, `>?`, `<?`, `>=?`, `<=?`, `:>`, `=>`, `|>`
- **Constants**: `true`, `false`, `void`
- **Intrinsics**: `__syscall0__` through `__syscall6__`, `__load__`, `__store__`, etc.
- **Type annotations**: `:type` and `:>returnType`
- **Comments**: `# line comment`
- **Strings**: `"double quoted"` with escape sequences
- **Numbers**: decimal, `0x` hex, `0b` binary
