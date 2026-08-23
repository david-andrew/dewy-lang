# Standard Library

Dewy ships a batteries-included standard library. It covers paths, I/O, time, collections, and more.

Ordinary modules receive a set of default imports via the import prelude. Values from the import prelude can be overriden. The prelude includes:

- `Path` and `p` for file paths used by [Imports](../ch03/imports.md)
- `print` and `printl`
- `Duration`, `ns`, `ms`, `s`, and `sleep`

A module can set `$no_prelude = true` to opt out of those names without changing anything it imports.

The rest of this chapter sketches areas the library covers. Language-level containers live in [Container Types](../ch03/container-types.md); the library builds richer structures on those.
