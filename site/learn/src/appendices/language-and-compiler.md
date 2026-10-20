# Language Design and Compiler Support

The [reference](/reference/) is normative language design. This Learn book uses current compiler examples, each with declared output or check intent.

The compiler is implemented in Jo and accepts Dewy source through its in-process frontend. It emits native executables and WebAssembly directly. The archived Python and µDewy implementations are not required.

[Generated coverage](/status/) names the source revision, compiler hash, target, examples and acceptance failures. Native release checks measure that target only. Browser examples have their own WebAssembly execution results. [Archived implementation](/archive/).
