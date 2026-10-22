# Self-hosting readiness: zip pilot (2026-10-21, base da5fbd36, branch wt/selfhost)

Pilot: `tests/fixtures/selfhost/zip.dewy` is compiler/zip.jo hand-translated to Dewy, plus
its helpers (`put16`/`put32` from elf.jo, `append_bytes` from util.jo). `zip_jo.jo` drives the
real `compiler/zip.jo`. `tests/test_selfhost_zip.py` checks that both write identical archives,
in default and release builds, and checks them with Python `zipfile`. The inputs include an
empty file, deflated text, random bytes and a Unicode filename.

## Result

**zip.dewy compiles and runs today, with no private syntax.** It needs only representation
rewrites, and its archives are byte-identical to Jo's. Instruction counts (icount):

| workload | dev Dewy / Jo | release Dewy / Jo |
|---|---|---|
| zip: 3 MB random + 2.3 MB text | 2.065 / 2.065 G | 1.927 / 1.927 G |
| zip: 20 MB, stored path | 7.527 / 7.527 G | 6.863 / 6.862 G |
| lexer kernel (byte classifier, 3.2 MB of compiler source, x20) | 1.968 / 1.906 G (+3.3%) | 1.936 / 1.930 G (+0.3%) |
| IR kernel (1M-node record arena: build, then mutating fold x10) | 0.601 / 0.601 G | 0.478 / 0.478 G |

The two kernels were scratch experiments, and their outputs matched. As a
pilot, zip.jo is almost trivial: it never touches enum tags, pointer types, `extern`, OS
gating, tuples crossing languages, or a whole-module translation. The kernel parity shows
that the code generator is not the obstacle. The obstacles are surface and bootstrap.

## Constructs zip.jo needs (Jo -> Dewy)

| Jo | Dewy today | Class |
|---|---|---|
| global `int[]`, ranges, `xor`/`>>`/`&`, hex | works; `int` -> explicit `int64` (Jo `int` wraps, Dewy `int` promotes) | A |
| tuple `(str, u8[])[]`, `f.0`/`f.1` | `array<[string array<uint8>]>`, `f[0]`/`f[1]` (an array type with a type per position; round 4) | A |
| `when not BOOTSTRAP:` | dropped: stage0 never compiles Dewy, so the gate is meaningless here | see `$target` |
| closure capturing loop locals | works (snapshots) | A |
| `mut u8[]` | `@b:array<uint8>` / `put16(@h v)`, also across Jo<->Dewy | A |
| `len(str)`, `loop c in str` (bytes) | `s as array<uint8>` (specified view; measured zero-copy). The loop source needs parens, and there is now a diagnostic for that | A |
| `data(out)+n`, `mem_copy` | the literal form compiles via undocumented Jo-prelude leakage; `out.extend(src)` is documented and costs the same | A |
| `deflate` (lib/game/image.jo) | `from p"@lib/game/image.jo" import deflate` (it also leaks in unimported) | A |
| `write_bytes -> bool` | `write_bytes(path out) is? int64` | A |

## Compiler-wide gaps (probed; counts from the 10-20 audit)

| Gap | Class |
|---|---|
| `$target` / `$supported_targets` (modules-and-imports.md "Targets") | **a**, implemented |
| OS axis: `TARGET == "windows"` x44, macos, linux. The design's `$target` names only backends | **c** |
| Build-mode flags `BOOTSTRAP`/`DEBUG`/`WATCH`/`PROGRAM_NAME`: no spelling | **c** |
| Pointer type spelling (87 `*u8` types): `ptr<T>`, `p[i]`, `p + n`, `p as ptr<U>` under `$unsafe` (LANGUAGE.md "Foreign functions") | **a**, implemented |
| `extern` + `@lib`/`@symbol`: `=> $extern(name=... lib=...)` | **a**, implemented |
| Payload-free `enum` (557 variants): typed `const` tags today; designed nominal families | A / b |
| Byte-character literals (`'('`, 1194 uses): `b'('` | **a**, implemented |
| Path import without selection: the design splats it, the implementation (and tests) qualify it as `stem.name` | **a/c**: contradicts current behaviour, so David decides |
| Tuples crossing languages: Jo `(str, u8[])` is Dewy's `[string array<uint8>]` both ways (round 4: no separate tuple concept) | **a**, implemented |

## Mixed-language transition (FFI / host ABI)

There is no foreign boundary. Both frontends lower into one AST, checker and IR, so a call
across the languages is an ordinary call.

- **Dewy -> Jo**: `from p"x.jo" import f`, `@lib/...`, or a bare-name module (a Dewy importer
  falls back to `.jo`).
- **Jo -> Dewy**: `use 'lib.dewy'` (verified: Jo calls a Dewy `put16` through `mut`).
- **Type mapping**: `mut` <-> `@`; `T[]` <-> `array<T>`; `u8` <-> `uint8`; Jo `int` takes
  `int64`; `str` <-> `string` (Dewy indexes graphemes, so pass bytes on hot paths).
- **C**: `$extern` in either language.
- **Bootstrap blocker for Dewy inside the compiler**: generation 1 (stage0 ->
  `core-bootstrap`) has no Dewy frontend (`bootstrap/frontend.jo`), and it builds generation
  2 from `compiler/`. So `use 'zip.dewy'` in wasm.jo would break `--bootstrap` unless a Jo
  twin is substituted for generation 2 too. That substitution is the frozen-Jo step in
  miniature.

## `$target` in the design, and what is now implemented

- **Value**: a compile-time string naming the backend: `x86_64`, `riscv`, `arm`, `c`,
  `wasm32`. Here x64 (all OSes) is `x86_64`, arm64 is `arm` and wasm is `wasm32`.
- **Folding**: `=?` / `not =?` against a literal, and `in?` / `not in?` against a literal
  list, combined with `not`/`and`/`or`, fold while lowering.
- **Gated `if`**: it compiles only the live arm and splices it into the enclosing scope, at
  module level (imports and declarations) or in a block. Dead arms are never checked.
- **Mixed conditions**: a condition mixing `$target` with runtime values stays an ordinary
  `if`.
- **Misspellings**: an unknown target literal is an error.
- **`$supported_targets = [...]`**: once per module, at file scope; any other target is an
  error.
- **Tests**: `tests/cases/target/*` (native and web), plus `tests/test_target_names.py`
  (x86_64, wasm32 and arm64 under qemu).

## Leaves shipped (B3)

`zip.dewy` (the web build's archive), `spelling.dewy` (the checker's "did you mean"
distance) and `leb128.dewy` (the one LEB128 encoder of the wasm, DWARF and Mach-O
writers, formerly three). Rules, enforced by `tests/test_selfhost_twins.py`: every
`compiler/*.dewy` has its `FROZEN_TWINS` entry; it imports only the library, never a
compiler module; its twin defines no name it lacks; each `.jo` module calling it
`use`s it (Dewy names reach only their importers, unlike Jo's shared namespace). Each
pair has a differential test (`tests/test_selfhost_*.py`) against an independent
Python oracle in default and release builds. Compiler output stayed byte-identical
(734 builds: examples and ladder, native, `--release`, `-g`, wasm32, aarch64-mac,
x86_64-windows).

Gaps met on the way: `loop {` needs `loop true {`; `loop c in s as array<uint8>`
needs parentheses; `bytes as string ?? ""` is reported as an unsupported type
expression rather than asking for `(bytes as string | none) ?? ""`; no 1-D
`fill(v n)` (a comprehension stands in); Dewy can take a Jo `enum` imported from Jo
but declares none of its own for Jo code to switch on (string-literal unions are
words, not tags); a leaf cannot read the compiler's state, so the stateful halves of
`line_col` and `hash_bytes` stay in Jo.
