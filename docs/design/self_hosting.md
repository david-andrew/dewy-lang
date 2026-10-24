# Self-hosting readiness: zip pilot (2026-10-21, base da5fbd36, branch wt/selfhost)

Pilot: `tests/fixtures/selfhost/zip.dewy` is compiler/zip.jo hand-translated to Dewy, plus
its helpers (`put16`/`put32` from elf.jo, `append_bytes` from util.jo). `zip_jo.jo` drives the
real `compiler/zip.jo`. `tests/test_selfhost_zip.py` checks that both write identical archives,
in default and release builds, and checks them with Python `zipfile`. The inputs include an
empty file, deflated text, random bytes and a Unicode filename.

## Result

**zip.dewy compiles and runs today, with no private syntax.** It needs only representation
rewrites, and its archives are byte-identical to Sloppy's. Instruction counts (icount):

| workload | dev Dewy / Sloppy | release Dewy / Sloppy |
|---|---|---|
| zip: 3 MB random + 2.3 MB text | 2.065 / 2.065 G | 1.927 / 1.927 G |
| zip: 20 MB, stored path | 7.527 / 7.527 G | 6.863 / 6.862 G |
| lexer kernel (byte classifier, 3.2 MB of compiler source, x20) | 1.968 / 1.906 G (+3.3%) | 1.936 / 1.930 G (+0.3%) |
| IR kernel (1M-node record arena: build, then mutating fold x10) | 0.601 / 0.601 G | 0.478 / 0.478 G |

The two kernels were scratch experiments, and their outputs matched. As a
pilot, zip.jo is almost trivial: it never touches enum tags, pointer types, `extern`, OS
gating, tuples crossing languages, or a whole-module translation. The kernel parity shows
that the code generator is not the obstacle. The obstacles are surface and bootstrap.

## Constructs zip.jo needs (Sloppy -> Dewy)

| Sloppy | Dewy today | Class |
|---|---|---|
| global `int[]`, ranges, `xor`/`>>`/`&`, hex | works; `int` -> explicit `int64` (Sloppy `int` wraps, Dewy `int` promotes) | A |
| tuple `(str, u8[])[]`, `f.0`/`f.1` | `array<[string array<uint8>]>`, `f[0]`/`f[1]` (an array type with a type per position; round 4) | A |
| `when not BOOTSTRAP:` | dropped: stage0 never compiles Dewy, so the gate is meaningless here | see `$target` |
| closure capturing loop locals | works (snapshots) | A |
| `mut u8[]` | `@b:array<uint8>` / `put16(@h v)`, also across Sloppy<->Dewy | A |
| `len(str)`, `loop c in str` (bytes) | `s as array<uint8>` (specified view; measured zero-copy). `loop c in s as array<uint8>` converts the source | A |
| `data(out)+n`, `mem_copy` | the literal form compiles via undocumented Sloppy prelude leakage; `out.extend(src)` is documented and costs the same | A |
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
| Tuples crossing languages: Sloppy `(str, u8[])` is Dewy's `[string array<uint8>]` both ways (round 4: no separate tuple concept) | **a**, implemented |

## Mixed-language transition (FFI / host ABI)

There is no foreign boundary. Both frontends lower into one AST, checker and IR, so a call
across the languages is an ordinary call.

- **Dewy -> Sloppy**: `from p"x.jo" import f`, `@lib/...`, or a bare-name module (a Dewy importer
  falls back to `.jo`).
- **Sloppy -> Dewy**: `use 'lib.dewy'` (verified: Sloppy calls a Dewy `put16` through `mut`).
- **Type mapping**: `mut` <-> `@`; `T[]` <-> `array<T>`; `u8` <-> `uint8`; Sloppy `int` takes
  `int64`; `str` <-> `string` (Dewy indexes graphemes, so pass bytes on hot paths).
- **Enumerations**: a Dewy union of string literals (`Phase:type = 'lex' | 'parse'`) is a
  Sloppy enum to Sloppy code: `match p: lex:`, `.lex`, `Phase.lex`, `int(p)`, `Phase(1)`, table
  keys. Its members are numbered in the order its set was first written, so a twin's
  `enum Phase:` lists them in that order (`tests/test_selfhost_twins.py`).
- **C**: `$extern` in either language.
- **Bootstrap blocker for Dewy inside the compiler**: generation 1 (stage0 ->
  `core-bootstrap`) has no Dewy frontend (`bootstrap/frontend.jo`), and it builds generation
  2 from `compiler/`. So `use 'zip.dewy'` in wasm.jo would break `--bootstrap` unless a Sloppy
  twin is substituted for generation 2 too. That substitution is the frozen-twin step in
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
distance), `leb128.dewy` (the one LEB128 encoder of the wasm, DWARF and Mach-O
writers, formerly three) and `base64.dewy` (the web page's module and icon, and the
macOS signature's hashes, formerly two encoders). Rules, enforced by `tests/test_selfhost_twins.py`: every
`compiler/*.dewy` has its `FROZEN_TWINS` entry; it imports only the library, never a
compiler module; its twin defines no name it lacks; each `.jo` module calling it
`use`s it (Dewy names reach only their importers, unlike Sloppy's shared namespace). Each
pair has a differential test (`tests/test_selfhost_*.py`) against an independent
Python oracle in default and release builds. Compiler output stayed byte-identical
(734 builds: examples and ladder, native, `--release`, `-g`, wasm32, aarch64-mac,
x86_64-windows).

`line_table.dewy` (each file's line starts and the last line found: `line_col`) is
the first stateful leaf. A leaf owns its state type (`LineTable`) and takes it by place
(`@t`); Sloppy keeps the one global (`src_lines: LineTable` in util.jo) and passes it in.
The type has no defaults, so the zero value is the empty table and the Sloppy global runs no
initializer in module order. Its word-at-a-time newline scan matches Sloppy's instruction
count (`speed`: flagship panel within 0.01%).

`sha.dewy` (SHA-256 and SHA-1: the macOS signature's page hashes, its LC_UUID and the
bundle's sealed icon) and `icns.dewy` (the bundle's icon) are the first hot leaves. Words
are `uint32<overflow='wrap'>`; the schedule and constants are `array<... length=64>`,
which drops their bounds checks. Like for like (rotations as two shifts and an or), the
Dewy SHA-256 needed +51% of Sloppy's instructions. The shipped one rotates by shifting the
word doubled into a `uint64<overflow='wrap'>`, computing that once per sigma: 1.485 / 1.527 G
(release 1.407 / 1.491 G) hashing 10 MB by pages. SHA-1 is 0.949 / 1.045 G. An aarch64-mac
build of the compiler takes 1.5% fewer instructions and writes the same bytes.

Open gaps from these leaves, by cost:
- A literal beside a policy-typed operand (`w + 1`, `w & 0xFF`, `w xor 0xFFFFFFFF`) goes
  through `int` and `__mi_low_word`, about 30 instructions in place of one. Plain `uint32`
  does not.
- Wrap lowering zero-extends after every 32-bit operation, even shr/and/or/xor, whose
  results already fit. It keeps a dead `and -1` after a constant shift and never forms a
  rotate.
- A loop counter is `int`, so `at + t * 4` with `at:int64` is checked `int` arithmetic
  (+21%) unless it is written `let q:int64=...`.
- A one-line helper with four checked byte loads is not inlined (+6%). Repeated pure calls
  are not shared (+19% when each rotation doubles its own word).
- Sloppy's style, `int64` with `& 0xFFFFFFFF` masks, costs 3x: the mask's bound does not
  reach the exact additions through array elements.

Gaps met on the way, and since closed: a conversion ending a loop header converts the last source; `bytes as string ?? ""`
converts to `string | none` and falls back; `fill(v n)` is documented; Sloppy takes a Dewy
string-literal union as its enum. Still open: the intern table (`hash_bytes`) as a leaf
costs +0.5–0.8% on the panel (lex+parse +2%): a new name needs a byte-range substring
Dewy lacks (copy loop, UTF-8 check, conversion: ~600 instructions against Sloppy's ~250), and
Sloppy retains a string passed beside a `mut` place (~20 instructions a call).
