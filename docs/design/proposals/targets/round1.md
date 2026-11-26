# Compilation target names: round 1 (merged proposal)

Merges brainstorms A, B and C ([brainstorm-a.md](brainstorm-a.md),
[brainstorm-b.md](brainstorm-b.md), [brainstorm-c.md](brainstorm-c.md)), checked
against the compiler as it is today. Dogfood: [dogfood-round1.md](dogfood-round1.md) and
[programs-r1/](programs-r1/). Cold read: [cold-read-round1.md](cold-read-round1.md)
(`native` became `host_tuned` and `$target.gpu` became `$target.gpu_apis`). The
questions are D46 in [open_decisions.md](../../open_decisions.md).

## Summary

1. A name is `processor[-system][-variant]`, joined by `-`, with `_` inside a
   field. A field is written only when the others don't imply it: `wasm32`,
   `cortex_m4f`, `x86_64-linux`, `aarch64-ios17-sim`.
2. The processor field holds an ISA (`x86_64`), an ISA level (`x86_64_v3`) or a
   core (`cortex_a76`, `cortex_m4f`). The level is in the name because the
   command line may override only the target and the build mode.
3. A name means the same thing on every machine. A bare general-purpose
   processor (`x86_64`) is an error with a fix-it. `host` names this machine;
   `native` names this machine with its exact CPU.
4. Linux keeps what the compiler does now: `x86_64-linux` is a static
   executable with no C library linked in; C libraries load at run time.
   `-musl` and `-glibc` exist only for linking C at link time.
5. `wasm32` alone is the browser and its system is `web`. `wasm32-wasi`,
   `wasm32-wasi2` and `wasm32-freestanding` name the other runtimes.
6. Versions are floors glued to the field they qualify: `aarch64-mac14`,
   `aarch64-android33`, `x86_64-linux-glibc2.28`, `c89`.
7. `c` is the processor "chosen later by a C compiler" (`c`, `c89`, `c-posix`).
   C for a known target is an output form: an output name ending in `.c`.
8. Chips and boards are libraries. The target is the core: an RP2040 is
   `cortex_m0p` plus `import p"@lib/boards/pico.dewy"`.
9. `$target` gains members, one fact each: `cpu`, `features`, `os_version`,
   `libc`, `simulator`, `pointer_bits`, `endian`, `gpu`, and the family booleans
   `posix`, `apple`, `bsd`, `mobile`, `hosted`. All fold at compile time.
10. `$supported_targets` entries become patterns (`['posix' 'windows' 'web']`).
    They are also the IDE's target set for `T | unsupported`: using a facility
    that some accepted target lacks is a compile error.

## 1. Grammar

```
name      = "host" | "native" | processor [ "-" system ] { "-" variant }
processor = PROCESSOR_WORD                 # x86_64  x86_64_v3  cortex_m4f  riscv32_imc  ptx_sm80
          | "c" [ version ]                # c  c89  c99  c23
system    = SYSTEM_WORD [ version ]        # linux  mac14  android33  wasi2  linux5.10
variant   = VARIANT_WORD [ version ]       # musl  glibc2.28  sim
version   = DIGITS [ "." DIGITS ]          # glued to its word, no separator
```

- **Separators.** `-` between fields, as today. `_` joins words inside a field
  (`x86_64`, `cortex_m4f`, `x86_64_v3`). A dot appears only inside a version.
- **Order.** Processor, system, then variants, in that order. An out-of-order
  name is an error whose fix-it is the canonical order.
- **Vocabularies are disjoint.** No word is both a processor and a system, or a
  system and a variant. A version is found by stripping the longest known word
  (`c89` is `c` + `89`; `riscv64` is a word).
- **Lowercase ASCII only.**

### What an omitted field means

| Omitted | Meaning |
|---|---|
| the whole target | this machine (`host`), as today |
| the system, after a processor that implies one | that system: `wasm32` → `web`, MCU cores → `freestanding`, GPU words → their API, `c` → standard C only |
| the system, after a general-purpose processor (`x86_64`, `aarch64`, `armv7`, `riscv64`) | error with a fix-it: `x86_64 names only a processor: write x86_64-linux (this machine's system), or host` |
| the variant | the system's default (Linux: no C library linked in; elsewhere the system's C library, never named) |
| a version | the compiler's documented floor (table below) |
| a level or core | the processor's baseline (table below) |

**Chips and boards given as targets** (`--target rp2040`, `--target pico`) are
errors whose fix-it names the core and the board library. The compiler finds
them only on that error path, by looking for `@lib/boards/NAME.dewy` and reading
its `$supported_targets`; there is no chip table in the compiler. A board
library imported by a build for another target stops at the import with the
`$target` line to add.

**Writing an implied field is an error with a fix-it**: `wasm32-web` →
`wasm32`; `cortex_m4f-freestanding` → `cortex_m4f`; `aarch64-linux-android` →
`aarch64-android`. A written **version** is a pin and is always allowed, even
when it equals today's floor, because floors rise between compiler releases.

### This machine

| Name | Means |
|---|---|
| *(nothing set)* | this machine, as today |
| `host` | this machine's processor family and system at the baseline level, so the binary runs on similar machines. Resolves to a canonical name (`x86_64-linux`). Use it to override a file's `$target` from the command line. |
| `native` | `host` with this machine's exact CPU (`znver4-linux`). Not portable. |

`host` and `native` are whole names; they take no other fields.

### Baselines and floors (proposed)

| Processor | Baseline |
|---|---|
| `x86_64` | x86-64-v1 (SSE2). Vectorized loops already pick AVX2 at run time. `x86_64-mac` implies `x86_64_v2`. |
| `aarch64` | ARMv8.0-A with NEON. `aarch64-mac` implies `apple_m1`; `aarch64-ios` implies the oldest core its iOS floor runs on; `aarch64-windows` implies the level Windows 11 requires. |
| `armv7` / `armv6` | ARMv7-A VFPv3-D16 hard float (Debian armhf) / ARM1176 VFPv2 hard float (Raspberry Pi OS) |
| `riscv64` | RV64GC, LP64D |
| `wasm32` / `wasm64` | WebAssembly with SIMD128, bulk memory and sign extension (every current browser) |

| System | Default floor |
|---|---|
| `linux` | kernel 4.4 |
| `mac` | 11 (today's Mach-O header) |
| `ios` | 15 |
| `android` | API 24 |
| `windows` | 10 |
| `freebsd` | 13 |
| `glibc` variant | 2.28 |
| `wasi` | preview 1 (`wasi2` is 0.2) |

## 2. Fields: what goes in the name

A fact goes in the name if it changes what binary you get or what the program
may call, and it is chosen at build time. Implied facts are `$target` members.
Facts that don't change the program (optimisation, output path, debug info)
stay in `$build` or on the command line.

| Fact | Where | Rule |
|---|---|---|
| ISA | processor | `x86_64 x86 aarch64 armv7 armv6 riscv64 riscv32 wasm32 wasm64 xtensa c` and GPU words. `arm64` → fix-it `aarch64`. |
| CPU level or core | processor | x86: `x86_64_v2/v3/v4`. ARM application cores: `cortex_a53 cortex_a72 cortex_a76 neoverse_n1 apple_m1…`. MCU cores: `cortex_m0p cortex_m3 cortex_m4 cortex_m4f cortex_m7f cortex_m7d cortex_m33f`. RISC-V: `riscv32_imc riscv32_imac riscv64_rva23`. Xtensa: `xtensa_lx6 xtensa_lx7`. GPU: `ptx_sm80 amdgpu_gfx1100`. |
| Single extra features (`+avx512f`) | not in v1 | A level or a core covers the real cases; add a core word when one doesn't. |
| Pointer width, endianness | implied by the processor | `wasm32`/`wasm64`, `riscv32`/`riscv64`. Big-endian ISAs would be their own words. |
| Float ABI | implied by the core | `cortex_m4f` is hard float, `cortex_m4` soft. `armv7-linux` is hard float. |
| OS or runtime | system | `linux mac windows ios android freebsd openbsd netbsd uefi freestanding web wasi`, and `posix` with `c` only |
| OS floor | version on the system | `mac14`, `ios17`, `android33` (API level), `windows11`, `linux5.10` (kernel) |
| C library | variant, only where there is a choice | Linux: none by default, `musl`, `glibc[ver]`. Elsewhere implied. |
| Simulator | variant | `sim` (Apple) |
| Object format | implied by the system | ELF, Mach-O, PE, wasm. Raw images (`.bin .hex .uf2`) and C are chosen by the output name. |
| GPU API | implied by the system | `$target.gpu`. Only kernel-only builds name a GPU target. |
| Chip or board | library | memory map, startup code, pins, flashing |
| Build mode, optimisation | `$build` | unchanged |

### Linux and the C library (verified)

Today `x86_64-linux` emits a static ELF with no program interpreter and talks
to the kernel directly. A `$extern` call is resolved at its first call: the
runtime starts the system's glibc loader inside the process and uses its
`dlopen`/`dlsym` (`lib/game/dl.jo`). This proposal keeps that as the default:

| Name | Use |
|---|---|
| `x86_64-linux` | default: static, kernel ABI, one binary for every distro; C libraries load at run time where the system has glibc |
| `x86_64-linux-musl` | static with musl linked in, so static C archives (`.a`) can be linked: Alpine, `FROM scratch` images that need C |
| `x86_64-linux-glibc` | an ordinary dynamic glibc executable (program interpreter, `DT_NEEDED`), symbol versions pinned at the floor (`-glibc2.17` for older systems). For distro packaging, and the fallback if run-time loading ever breaks. |

On every other system the C library is the system API (libSystem, kernel32 and
the C runtime, bionic, the BSD libc) and is never named.

When a C call on `x86_64-linux` can't load its library (a musl distro, a
missing `.so`), the run-time error names the library and the two link-time
variants (`-musl`, `-glibc`) that would have caught it at build time.

## 3. `c`, wasm and GPU

**`c`** is the processor that a C compiler picks later.

| Want | Write | `.arch` | `.os` |
|---|---|---|---|
| Portable ISO C11, standard library only | `c` | `'c'` | `'none'` |
| C89 / C99 / C23 | `c89` `c99` `c23` | `'c'` | `'none'` |
| C11 plus POSIX | `c-posix` | `'c'` | `'posix'` |
| C for Linux, Windows or bare metal, CPU unknown | `c-linux` `c-windows` `c-freestanding` | `'c'` | that system |
| C for a **known** target (ESP32-S3, a console SDK) | `$target = 'xtensa_lx7'` and `-o fw.c` | `'xtensa'` | `'freestanding'` |

On `c` targets `.pointer_bits` and `.endian` are `none`. A processor with no
native backend (`xtensa_lx6`, `xtensa_lx7`) builds only as C; without a `.c`
output name the error says so and gives the fix-it.

**wasm.** Browser versus WASI is the system axis, like Linux versus Windows.

| Name | Meaning |
|---|---|
| `wasm32` | browser: JS glue and HTML page, WebGL 2, Web Audio (today's target). `.os` becomes `'web'` (was `'none'`). |
| `wasm64` | browser with memory64 |
| `wasm32-wasi` | WASI preview 1 (wasmtime, wasmer, most hosts) |
| `wasm32-wasi2` | WASI 0.2 components |
| `wasm32-freestanding` | a bare module whose imports are the program's `$extern`s |

**GPU.** GPU functions are part of the host program today: the runtime tries
Vulkan, then GLES, WebGL 2 on the web, and the CPU last. So GPU support comes
from the host target (`$target.gpu`). Only a **kernel-only build** (a file of
GPU functions emitted on its own) names a GPU target: `spirv` (Vulkan),
`metal`, `ptx_sm80` (`ptx` alone is the compiler's floor), `amdgpu_gfx1100`
(`amdgpu` alone is an error: each chip is its own ISA), `wgsl`.

## 4. The `$target` record

`$target`, `.arch` and `.os` exist. Everything else is new. All members are
compile-time constants and conditions on them fold as `.os` conditions do now.
Folding gains bare boolean members, numeric comparisons against literals
(`<? <=? >? >=?`), `LITERAL in? $target.MEMBER` for list members, and
`=? none`.

| Member | Type | Values |
|---|---|---|
| `$target` | string | canonical name: `'x86_64-linux'`, `'cortex_m4f'`, `'aarch64-mac14'` |
| `.arch` | string | ISA family: `x86_64 x86 aarch64 arm riscv64 riscv32 wasm32 wasm64 xtensa c spirv metal ptx amdgpu wgsl` |
| `.cpu` | string | the processor word as resolved: `'x86_64'`, `'x86_64_v3'`, `'cortex_m4f'`, `'apple_m1'`, `'znver4'` (under `native`) |
| `.features` | list of string | `sse4_2 popcnt avx2 fma bmi2 avx512f neon dotprod fp16 sve2 simd128 fpu fpu64 atomics` … |
| `.os` | string | `linux mac windows ios android freebsd openbsd netbsd uefi freestanding web wasi posix none` |
| `.os_version` | number or `none` | the floor: `14` for `mac14`, `33` for `android33`; the default floor when unwritten; `none` where there is none |
| `.libc` | string | `'none'` (Linux default, bare metal, wasm), `'glibc'`, `'musl'`, `'system'` (the system's own) |
| `.simulator` | bool | Apple simulator |
| `.posix` | bool | POSIX files, sockets and threads exist (Linux, Android, Apple, BSDs, `c-posix`) |
| `.apple` | bool | `mac`, `ios` |
| `.bsd` | bool | FreeBSD, OpenBSD, NetBSD |
| `.mobile` | bool | phone or tablet OS: `ios`, `android` |
| `.hosted` | bool | an OS provides files, processes and a heap: false for `freestanding` and `uefi` |
| `.pointer_bits` | int or `none` | 32, 64; `none` on `c` |
| `.endian` | string or `none` | `'little'`, `'big'`; `none` on `c` |
| `.gpu` | list of string | GPU APIs the system offers: Linux, Windows, Android `['vulkan' 'gl']`; Apple `['metal']`; web `['webgl2']`; bare metal `[]` |

`.os_version` compares by component: `$target.os_version >=? 14.2` means 14.2
or later. Compare it only in an arm that already knows the system.

**Whole-name tests.** In a folded condition, `$target =? 'NAME'` is an error
with a fix-it to the member test. A whole-name test silently fails on a
refinement (`x86_64_v3-linux` is not `=? 'x86_64-linux'`). Names in conditions
belong to `$supported_targets`; `$target` as a string is for messages.

```dewy
if $target.os =? 'windows' { ... }                            # as today
if $target.posix { ... }                                       # bare boolean member
if 'avx2' in? $target.features { ... }                         # list member
if $target.os =? 'mac' and $target.os_version >=? 14 { ... }   # numeric compare
if $target.pointer_bits =? 32 { ... }
```

Families as booleans, not a `families` list: they read best in `if`, and each
is one fact. The set is closed; a new family is a new member.

## 5. `$supported_targets` and `| unsupported`

**Patterns.** An entry is any of a name's fields, in order; an omitted field
matches anything. A family word (`posix`, `apple`, `bsd`, `mobile`, `hosted`)
matches targets whose boolean is true. A refinement matches its pattern:
`x86_64_v3-linux-musl` matches `x86_64-linux`, `linux`, `x86_64` and `posix`;
`aarch64-mac15` matches `aarch64-mac14`; `aarch64-mac13` does not.

```dewy
$supported_targets = ['posix' 'windows']                  # desktops, phones, BSDs; not web or bare metal
$supported_targets = ['linux' 'mac' 'windows' 'web']
$supported_targets = ['cortex_m4f' 'cortex_m33f']         # the cores this driver's FPU code assumes
$supported_targets = ['x86_64_v3' 'aarch64']              # an AVX2-only kernel library, plus ARM
```

**`| unsupported`** (from `resources/discussion_points.md`). A platform facility
has type `T | unsupported` in the portable view. Once the target is fixed, the
condition that defines it folds and the type becomes `T` or `unsupported`.

```dewy
# a library module (sketch)
env:dict<string string> | unsupported = if $target.hosted and $target.os not=? 'web' {
    read_environ()
} else { unsupported }
```

- Using an `unsupported` value is a compile error naming the target and the
  deciding fact: `os.env is unsupported on cortex_m4f ($target.hosted is false)`.
  Using a facility is the requirement; there is no `require`.
- `if os.env is? unsupported {...}` folds like any target test.
- **The IDE's target set** is the module's `$supported_targets`, else the main
  file's `$target`, else the host. The editor shows `| unsupported` only when a
  target in the set lacks the facility, so a Linux-only module sees plain
  `dict<string string>`.
- `dewy check` checks a module once per pattern, with one representative
  target each. The cost is paid only by modules that declare several.

## 6. Catalog

"Implies" lists what the name fixes without writing it. Floors are proposals.

| # | Name | What it is | Implies |
|---|---|---|---|
| 1 | `host` | this machine | e.g. `x86_64-linux` |
| 2 | `native` | this machine, this CPU | e.g. `znver4-linux`; not portable |
| 3 | `x86_64-linux` | Linux PC or server | x86-64-v1, ELF, static, no C library linked, C loaded at run time, kernel ≥ 4.4 |
| 4 | `x86_64_v3-linux` | the same for Haswell / Zen and later | AVX2, FMA, BMI2 in `.features` |
| 5 | `znver2-linux` | Steam Deck, tuned | Zen 2 |
| 6 | `x86_64-linux-musl` | static with musl (Alpine, scratch images with C archives) | `.libc` `'musl'` |
| 7 | `x86_64-linux-glibc` | ordinary dynamic glibc executable | program interpreter, glibc symbols ≤ 2.28 |
| 8 | `x86_64-linux-glibc2.17` | the same for very old distros | glibc symbols ≤ 2.17 |
| 9 | `aarch64-linux` | 64-bit ARM Linux: Raspberry Pi 3/4/5 on a 64-bit OS, Graviton, Ampere | ARMv8.0 + NEON |
| 10 | `cortex_a53-linux` | Raspberry Pi 3, tuned | |
| 11 | `cortex_a72-linux` | Raspberry Pi 4, tuned | |
| 12 | `cortex_a76-linux` | Raspberry Pi 5, tuned | ARMv8.2, dotprod, fp16 |
| 13 | `neoverse_n1-linux` | Graviton 2, Ampere Altra | ARMv8.2 + LSE atomics |
| 14 | `aarch64-linux-musl` | Alpine on ARM | |
| 15 | `armv7-linux` | 32-bit ARM Linux, armhf (Pi 2/3/4 on a 32-bit OS) | hard float |
| 16 | `armv6-linux` | Raspberry Pi Zero and 1 | ARMv6 + VFPv2, hard float |
| 17 | `riscv64-linux` | RISC-V boards (VisionFive 2, Milk-V) | RV64GC, LP64D |
| 18 | `riscv64_rva23-linux` | RVA23 boards, with vectors | `v` in `.features` |
| 19 | `x86_64-windows` | Windows x64 | PE, Windows ≥ 10 |
| 20 | `aarch64-windows` | Windows on ARM | PE, Windows 11's ARM level |
| 21 | `x86-windows` | 32-bit Windows | i686 + SSE2 |
| 22 | `aarch64-mac` | Apple silicon Mac | `apple_m1`, Mach-O, macOS ≥ 11, `.gpu` `['metal']` |
| 23 | `aarch64-mac14` | the same, may use macOS 14 APIs | `.os_version` 14 |
| 24 | `x86_64-mac` | Intel Mac | `x86_64_v2`, macOS ≥ 11 |
| 25 | `aarch64-ios` | iPhone and iPad | iOS ≥ 15, `.mobile` |
| 26 | `aarch64-ios17` | the same, iOS 17 floor | |
| 27 | `aarch64-ios-sim` | iOS Simulator on Apple silicon | `.simulator` |
| 28 | `x86_64-ios-sim` | iOS Simulator on an Intel Mac | `.simulator` |
| 29 | `aarch64-android` | Android phone | bionic, API ≥ 24, `.gpu` `['vulkan' 'gl']` |
| 30 | `aarch64-android33` | Android, API 33 floor | |
| 31 | `x86_64-android` | Android emulator, ChromeOS | |
| 32 | `x86_64-freebsd` | FreeBSD | FreeBSD ≥ 13, `.bsd` |
| 33 | `aarch64-freebsd` | FreeBSD on ARM | |
| 34 | `x86_64-openbsd` | OpenBSD | |
| 35 | `x86_64-netbsd` | NetBSD | |
| 36 | `wasm32` | browser | `.os` `'web'`, JS glue + HTML, WebGL 2 |
| 37 | `wasm64` | browser, memory64 | `.pointer_bits` 64 |
| 38 | `wasm32-wasi` | WASI preview 1 | no JS |
| 39 | `wasm32-wasi2` | WASI 0.2 component | |
| 40 | `wasm32-freestanding` | bare wasm module (plugins, embedding) | imports are the program's `$extern`s, not `.hosted` |
| 41 | `cortex_m0p` | RP2040 (Pico), STM32G0 | ARMv6-M, soft float, freestanding |
| 42 | `cortex_m3` | STM32F1 ("Blue Pill") | ARMv7-M, soft float |
| 43 | `cortex_m4f` | STM32F4, nRF52840 | ARMv7E-M, single-precision FPU, hard float |
| 44 | `cortex_m7d` | STM32H7, Teensy 4 | ARMv7E-M, double-precision FPU (`fpu64`) |
| 45 | `cortex_m33f` | RP2350 (Arm cores), nRF5340, STM32U5 | ARMv8-M Mainline, FPU |
| 46 | `riscv32_imc` | ESP32-C3 | RV32IMC, no atomics, no FPU |
| 47 | `riscv32_imac` | ESP32-C6, RP2350 (RISC-V cores) | RV32IMAC |
| 48 | `xtensa_lx6` | ESP32 | builds as C (`-o fw.c`) until there is a backend |
| 49 | `xtensa_lx7` | ESP32-S3 | as above |
| 50 | `x86_64-freestanding` | kernels after a bootloader handoff | ELF, no red zone, no SIMD unless the level says so |
| 51 | `aarch64-freestanding` | bare-metal Pi, hypervisors | ELF |
| 52 | `riscv64-freestanding` | bare-metal RISC-V (today's list) | ELF |
| 53 | `x86_64-uefi` | UEFI application or bootloader | PE32+, not `.hosted` |
| 54 | `aarch64-uefi` | ARM UEFI | PE32+ |
| 55 | `spirv` | kernel-only build: SPIR-V for Vulkan compute | |
| 56 | `metal` | kernel-only build: Metal shading language | |
| 57 | `ptx_sm80` | kernel-only build: CUDA PTX for Ampere | `ptx` alone is the floor |
| 58 | `amdgpu_gfx1100` | kernel-only build: AMD RDNA 3 | |
| 59 | `wgsl` | kernel-only build: WebGPU shader | |
| 60 | `c` | portable C11, standard library only | `.os` `'none'` |
| 61 | `c89` | portable C89 | |
| 62 | `c-posix` | C11 plus POSIX | `.posix` |
| 63 | `c-linux`, `c-windows`, `c-freestanding` | C for that system, CPU unknown | |
| — | `xtensa_lx7` + `-o fw.c` | C with every fact of that target decided | output form, not a target |

Consoles: the name shape (`aarch64-horizon`, `x86_64-orbis`) fits, delivered
by C output and a platform library under NDA. Not in the public catalog.

## 7. Prior art

| Scheme | Example | Taken | Not taken |
|---|---|---|---|
| LLVM triples | `x86_64-unknown-linux-gnu`, `thumbv7em-none-eabihf` | processor first; one string | filler fields (`unknown`, `none`); an overloaded env field; CPU outside the name |
| Rust | `aarch64-apple-darwin` + `-C target-cpu`, `cfg(target_family = "unix")` | the `cfg` facets (`os`, families, `pointer_width`, `feature`) | triple noise; CPU and features as separate flags, so `--target` doesn't say what you get |
| Zig | `x86_64-linux-musl`, `aarch64-macos.14`, `x86_64-linux-gnu.2.28`, `-mcpu` | no vendor; versions on the OS and libc fields; `_v3` spelling; `native` | `-mcpu` as a separate flag; `-gnu` written on every Linux name |
| Go | `GOOS=linux GOARCH=amd64 GOAMD64=v3` | static, libc-free Linux binaries; a small OS list; `unix` tag | several variables instead of one copyable string |
| Swift / Apple | `arm64-apple-ios17.0-simulator` | OS floor on the OS; simulator as a variant | `apple` repeating `ios`; `arm64` |
| .NET RIDs | `linux-musl-x64`, `osx-arm64` | `musl` only when it isn't the default | OS-first order; versioned RIDs (abandoned: the fallback graph exploded). Dewy's versions are floors matched as refinements. |
| Nix | `x86_64-linux`, `aarch64-darwin` | the two-field common case | no way to say musl, a level or a floor |
| TinyGo | `-target=pico` | board names are friendly | a board is a memory map and a flasher: library material |

## 8. How the three brainstorms were resolved

| Question | A | B | C | Here | Why |
|---|---|---|---|---|---|
| Bare `x86_64` | host's OS | error | error + `host` | error + `host` / `native` | A name must mean the same on every machine: files, scripts and `$supported_targets` share it. `--target host` overrides a file's target. |
| Linux default | static, no libc, C at run time | glibc | static; FFI links glibc | static, no libc, C at run time | That is what the compiler does (verified); one binary for every distro. |
| `wasm32` alone | browser | browser | error, `wasm32-web` | browser, `.os` `'web'` | Shortest name for the main wasm use; already documented. |
| CPU level | in the processor field | `$target.cpu =` member | `@v3` suffix | in the processor field | The command line may override only the target, so the level must be in the name; no new punctuation; MCU cores read naturally. |
| Chips | library | target names | library | library | A chip is a memory map, pins and a flasher. |
| Versions | glued | separate field | glued | glued | Compact; reads like "macOS 14". |
| Implied field written | accepted, normalised | error | error | error with fix-it | One spelling per target; no aliases. |
| `c` | portable C, C for a known target by `-o x.c` | arch; `$build.emit` | arch; `$build.backend` | portable C; `-o x.c` | `$build.emit` can't be set from the command line; the output name already picks `.html`. |
| Families | booleans | `family` string + 2 bools | `families` list | booleans | Read best in `if`; one fact each. |
| `$supported_targets` | patterns + families | names, arch, os, family | wildcards `*-linux` | patterns + families | Disjoint vocabularies make wildcards unnecessary. |
| `$host` | record | `$build.host` | `host` name | `host` name only | A build script's own `$target` is the host; host-dependent compile-time code hurts reproducibility. |

## 9. What changes from today

| Today | Proposed |
|---|---|
| `x86_64`, `aarch64`, `riscv64` mean this machine's system (accepted only on that processor) | error with a fix-it; `host` and `native` are new |
| bare `c` errors in practice | portable standard C |
| `wasm32` has `.os` `'none'` | `'web'` |
| `riscv64-windows` listed | removed (no such platform) |
| names split at the first `-` | parsed by vocabulary: levels, cores, versions, variants |
| `$supported_targets` lists full names | entries are patterns and family words |
| `if $target =? "wasm32"` (LANGUAGE.md example) | an error with a fix-it to `$target.os =? 'web'` |
| `.arch`, `.os` only | the members in §4 |

Not changed: the `-` separator, `x86_64`, `aarch64`, `mac`, `c-posix`, `c89`,
`wasm32`, one target per build, and the command-line rule.

## 10. Out of scope (found while working)

- **Run-time CPU dispatch for hand-written intrinsics** (one binary, AVX2 chosen
  at run time). Vectorized loops already do this; a user-level form
  (`if cpu.has('avx2') {...}` compiling its arm with the feature on) is a
  separate feature. **Run-time OS availability** (Swift's `#available`: newer
  APIs on newer systems from one binary) is the same idea for OS floors; one
  future feature could cover both.
- **Windows C runtime**: `$extern` defaults to `msvcrt.dll`; with a Windows 10
  floor, UCRT (`ucrtbase.dll`) would give `fma` and hex `strtod` by default.
- **Run-time C loading needs glibc**: on musl distros `x86_64-linux` programs
  that call C fail at the first call. Locating musl's loader would close it.
- **Multi-target builds** (`--target` repeated): a shell loop or build script
  does the job today.
- **Kernel ABI for `x86_64-freestanding`** (no red zone, no SIMD): fits the
  name; the code-model details belong to the backend.
