# The Standard Library

Dewy's standard library should make common programs convenient without turning basic language behavior into hidden magic.

The language defines constructs such as arrays, objects, functions, and ranges. The library builds reusable policies and services on top: paths, files, text processing, networking, collections, clocks, concurrency, parsing, and platform capabilities.

## The Prelude

A small source prelude provides names that ordinary programs use constantly:

- `Path` and `p` for paths;
- `print` and `printl` for basic output;
- `Duration` and common exact time scales;
- target-provided essentials such as `sleep`.

Prelude names are ordinary bindings and may be shadowed. `$no_prelude = true` requests a module without implicit prelude imports.

## Library Design Principles

- Common operations should have straightforward defaults.
- Platform capabilities and observable effects should appear in types or effect contracts where they matter.
- Domain libraries should compose with the same arrays, objects, iterators, units, and errors used elsewhere.
- Zero-cost abstractions should remain possible without making low-level representation the default user interface.
- Portable interfaces should distinguish language guarantees from target-specific availability.

The standard library is still being built. Future library explorations are maintained outside the reading path until they have real APIs and programs behind them; the current queue is preserved in the repository's `site/DOCUMENTATION_PROJECTS.md`.
