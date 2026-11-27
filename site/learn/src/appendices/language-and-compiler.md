# Language Design and Compiler Support

The [reference](/reference/) is the language design. This book shows what the current compiler does: each example is compiled, and its output checked, on every website build. The repository's [language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md) documents the current compiler in full.

The compiler is written in Dewy: about 200,000 lines, plus a 10,000-line layer of an older helper language (storage, opcode tables and platform glue) that is being ported. It builds itself, starting from a small C seed, and emits native executables for Linux (x86-64 and ARM64), macOS (ARM64) and Windows (x64), and WebAssembly with an HTML page for the browser. It needs no external assembler, linker or C compiler.

[Status](/status/) names the source revision, compiler build, targets and results that each site build measured. The [archive](/archive/) keeps the earlier Python and µDewy implementations.
