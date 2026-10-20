# Host Interoperability

> **Language design.** [Generated coverage](/status/#ref-interoperability) names measured programs and target restrictions; examples here illustrate the design.

The current compiler emits native executables and WebAssembly directly. Native libraries and browser services have different capabilities; [generated coverage](/status/) keeps their results separate.

Use `dewy-core --print-lib` to locate the matching standard and platform libraries. Source imports and library bindings are described in [Modules and Imports](modules-and-imports.md). The [current language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md) documents host-facing examples and limitations. A stable general foreign-function interface remains a design topic.

The [archived implementation](/archive/) records the earlier lowering through µDewy. It is not required to build or run the current compiler.
