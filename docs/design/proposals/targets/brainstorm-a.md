# Dewy target names — brainstorm round 1

## Summary (10 lines)

1. A name is `PROCESSOR-SYSTEM-VARIANT`, joined by `-`, with `_` inside a field. Fields are written only when the others don't imply them (`wasm32`, `cortex_m4f`, `x86_64-linux`, `aarch64-ios-sim`).
2. Each field has its own vocabulary and the vocabularies don't overlap, so a name parses by vocabulary, not by position. That lets a partial name (`linux`, `windows`, `aarch64`) work both as a build request and as a pattern.
3. An omitted field takes the only value the others allow. Failing that it takes the host's value (on general-purpose CPUs), and failing that the processor's documented default: wasm32→`web`, MCU cores→`freestanding`, `c`→standard C.
4. The processor field can be an ISA (`aarch64`), an ISA level (`x86_64_v3`) or a core (`cortex_a76`, `cortex_m4f`, `apple_m1`). From it come `$target.arch`, `.cpu`, `.features`, endianness, pointer width and float ABI. Chips and boards (RP2040, Pico) belong to libraries, not target names.
5. A version is glued to the field it qualifies: `aarch64-mac14`, `aarch64-android29`, `wasm32-wasi2`, `x86_64-linux-gnu2.28`, `c89`. With no version, the field gets the compiler's documented floor.
6. Linux needs no libc field. `x86_64-linux` is a static executable that talks to the kernel and loads system C libraries at run time, which is what the compiler already does. `-musl` and `-gnu` exist only for linking C at link time.
7. `c` is the "processor still unknown" value. A bare `c` means portable ISO C, `c-posix` any POSIX system, `c89` C89. Emitting C *for a known target* is an output choice (`-o x.c`), not a target, and it is how Dewy reaches ESP32 Xtensa and the consoles.
8. GPU code belongs to the host target: `$target.gpu` lists shader backends, implied by the OS. Standalone kernel builds (`spirv`, `ptx_sm80`, `msl`) are the only GPU names.
9. `$target` gains new members: `cpu`, `features`, `os_version`, `env`, `pointer_bits`, `address_bits`, `endian`, `gpu`, plus boolean families `posix`, `apple`, `bsd`, `mobile`, `hosted`. `$host` describes the machine doing the compiling. All of them fold at compile time.
10. `$supported_targets` takes patterns (`['posix' 'windows' 'web']`). It also declares the IDE's target set: a facility typed `T|unsupported` collapses per target, using an unsupported one is a compile error, and the editor only flags facilities that some declared target lacks.

Every member name, field value and CLI form below that does not exist today is marked **(new)**. None of them have been cold-tested yet (AGENTS rule 6). That has to happen before anything goes to open_decisions.md.

---

## 1. Grammar

```
name      = processor [ "-" system ] { "-" variant }
processor = PROC_WORD [ "_" level ]  [ version ]       # x86_64, x86_64_v3, cortex_m4f, c89
system    = SYS_WORD  [ version ]                      # linux, mac14, android29, wasi2
variant   = VAR_WORD  [ version ]                      # musl, gnu2.28, sim, soft
version   = DIGITS [ "." DIGITS ]                      # glued, no separator
```

- **Separator:** `-` between fields (as today). `_` joins words inside a field (`x86_64`, `cortex_m4f`, `x86_64_v3`). A dot appears only inside a version.
- **Order:** processor, system, then variants. The order is fixed for the canonical spelling. Parsing still works by vocabulary, and the compiler rewrites an out-of-order name to canonical with a fix-it (`linux-x86_64` → "did you mean `x86_64-linux`").
- **Disjoint vocabularies:** no word is both a processor and a system, or both a system and a variant. Versions are found by stripping the longest known word: `c89` → `c` + `89`, and `riscv64` stays whole because `riscv64` is a word.
- **Omitted fields.** The same rule applies everywhere:
  1. If the given fields allow only one value, that value is used. `wasm32` alone is the browser. `web` alone is `wasm32`. `ptx` is CUDA. `cortex_m4f` is bare metal. `ios` alone is `aarch64-ios`.
  2. Otherwise a build target takes **the host's value**. On an x86_64 Linux box, `--target aarch64` gives `aarch64-linux`, `--target windows` gives `x86_64-windows`, and `--target musl` gives `x86_64-linux-musl`. This keeps the sketch's "bare arch = this machine's OS" and adds the mirror case, "bare OS = this machine's processor".
  3. Otherwise the processor's **documented default** is used (table below). Anything else is an error that names the missing field.
- **In a pattern** (`$supported_targets`, see §4), an omitted field means *any*. `aarch64` matches every aarch64 target.
- **Canonical spelling** is the shortest name that doesn't depend on the host. Defaults are dropped and the system is always written unless the processor implies it. `$target` (the string) always holds the canonical name. `--target aarch64` on Linux reads back as `'aarch64-linux'`.
- **Explicit defaults** (`x86_64_v2-linux`, `aarch64-mac11`) are accepted and normalised away. They matter in patterns, where `x86_64-linux-gnu` is narrower than `x86_64-linux`.

**Names for "this machine" (new):**

| Name | Means |
|---|---|
| *(nothing set)* | `host`: the default, as today |
| `host` **(new)** | This machine's processor family, system and environment at the **default CPU level**, so the binary runs on similar machines. Use it on the CLI to override a file's `$target = 'wasm32'`. |
| `native` **(new)** | `host` plus *this* CPU's exact features (`$target.cpu` becomes e.g. `znver4`). Not portable. Same idea as Rust and Zig `-mcpu=native`. |

`targets.dewy` currently rejects `native` and points to the default. This proposal gives it the meaning other compilers have taught users to expect.

**Default system per processor:**

| Processor class | Default system | Why |
|---|---|---|
| `x86_64` `x86` `aarch64` `arm` `riscv64` `ppc64le` `loongarch64` | the host's (error if the host's OS doesn't run on it, e.g. `riscv64` on a Mac) | general-purpose CPUs |
| `wasm32` `wasm64` | `web` | Dewy's web games are the main wasm customer |
| `cortex_m*` `riscv32*` `xtensa*` `avr` | `freestanding` | in practice, no general OS runs on them |
| `c` (any dialect) | `stdc` **(new)**: ISO C hosted library only | portable C output (see §3) |
| `spirv` / `ptx` / `amdgpu` / `msl` | `vulkan` / `cuda` / `hsa` / `metal` | each has exactly one |

---

## 2. Fields: what goes in the name and what doesn't

Test used here: **a fact goes in the name if it changes what binary you get or what the program may call, and it is chosen at build time.** Facts implied by the name are `$target` members, not name fields. Facts that don't change the program (optimisation level, output path, debug info) are `$build` settings or CLI flags.

| Fact | Where | Spelling / rule |
|---|---|---|
| Architecture (ISA) | **name**, processor | `x86_64 x86 aarch64 arm riscv64 riscv32 wasm32 wasm64 xtensa ppc64le loongarch64 c` (+ GPU words). Keep `aarch64` (as today), not `arm64`: `arm64` gets an error with a hint, as it does now. |
| CPU feature level / core | **name**, processor level | x86: `x86_64_v2/v3/v4` (psABI levels). ARM: cores `cortex_a53/a72/a76`, `apple_m1…m4`, or levels `aarch64_v8_2`, `aarch64_v9` **(new)**. RISC-V: extension strings or profiles `riscv32_imc`, `riscv64_rva23`. MCUs: cores `cortex_m0p/m3/m4/m4f/m7f/m33f`, `xtensa_lx6/lx7`. `native` resolves to a core. |
| Individual extra features (`+avx512f`) | **not in the name** | Use a level or core. If one is really needed, see open issue 3. |
| Default CPU level | implied | `x86_64`→`x86_64_v2`. `aarch64`→v8.0, **but `aarch64-mac` implies `apple_m1`** and `aarch64-windows` implies the level Windows 11 on ARM requires. `riscv64`→rv64gc. |
| OS | **name**, system | `linux mac windows ios tvos watchos visionos android freebsd openbsd netbsd uefi web wasi freestanding` + source-only `posix stdc` |
| OS minimum version | **name**, glued to system | `mac14`, `ios17`, `android29` (API level, as in NDK triples), `windows10`, `freebsd14`, `wasi2`. Omitted: the compiler's documented floor (today's Mach-O header already says macOS 11.0). |
| libc / C ABI | **name**, variant, *only where there is a choice* | Linux: none by default (see below), `musl`, `gnu[ver]`. Windows: default MSVC ABI + UCRT; `gnu` (MinGW archives) only if someone needs it. Apple, Android (bionic), BSDs, WASI: implied. |
| Simulator / ABI flavour | **name**, variant | `sim` (Apple simulators). `soft` (soft-float on a core that has an FPU: rare). |
| Pointer width | implied by processor | `wasm32/wasm64`, `riscv32/64`. x32 and `aarch64_ilp32` are dead or niche; watchOS `arm64_32` would be the processor `aarch64_32` if it's ever needed. |
| Endianness | implied by processor | Big-endian ISAs are separate words (`ppc64` vs `ppc64le`, `aarch64_be`), as in LLVM. |
| Float ABI | implied by core / system | `arm-linux` = hard-float (armhf). `cortex_m4f` = hard, `cortex_m0p` = soft. Override with variant `soft`. |
| Object format | implied by system | ELF (linux, bsd, freestanding), Mach-O (apple), PE (windows, uefi), wasm. Raw/`.hex`/`.uf2` is an **output** choice chosen by `-o` extension, following the `.html`/`.exe` precedent. |
| Runtime environment (wasm) | **name**, system | `web` (browser, JS glue, HTML), `wasi[ver]`, `freestanding` (bare module: imports are only the program's `$extern`s) |
| GPU API | **not in the name** (implied by OS) | `$target.gpu` (§4). Standalone kernel builds have their own names (§5). |
| Chip / board memory map (RP2040, STM32F411, ESP32-C3) | **not in the name** | A board library supplies the linker memory map and startup code (`import p"@lib/boards/pico.dewy"`). The target is the core: `cortex_m0p`. See open issue 9. |
| Build mode, optimisation, debug info | `$build` | unchanged |
| Kernel code model (no red zone, no SIMD) | implied by `freestanding` on x86_64 | open issue 14 |

### Does Dewy need a libc?

On Linux it doesn't, and it already doesn't use one. `host_target.dewy` uses raw syscalls, and `lib/game/dl.jo` boots the system's dynamic loader at run time so it can `dlopen` libGL, Vulkan, ALSA and Wayland. **So `x86_64-linux` means: a static executable that runs on any Linux kernel at or above the floor, whose C libraries are found at run time, whatever libc the system uses.** That is Go's model with cgo off, but dynamic C still works. It is the best 80% path: one binary for every distro and no glibc version mismatch. The libc variant only matters when C is linked *at link time*:

| Name | Use |
|---|---|
| `x86_64-linux` | default: static, kernel ABI, C loaded at run time |
| `x86_64-linux-musl` | static with musl linked in, so static `.a` C archives can be linked (Alpine, `FROM scratch` containers that need C) |
| `x86_64-linux-gnu2.28` | ordinary dynamic glibc executable (PT_INTERP, DT_NEEDED). Versioned symbols are pinned at 2.28 or older, as Zig does. |

Other systems need the platform's C library because it *is* the system API: libSystem on Apple, kernel32/ucrtbase on Windows, bionic on Android, libc on the BSDs, where syscalls aren't a stable ABI. There the library is implied and never named.

---

## 3. What is `c`? (and wasm web vs WASI)

The sketch's `c-linux`, `c-posix` and `c89` mix two things together:

1. **Portable C source** for a machine that is unknown at Dewy-compile time. A C compiler picks the processor later.
2. **C as a backend** for a machine that *is* known. Dewy has no native backend for it (ESP32 Xtensa, PowerPC, consoles behind NDA'd toolchains), or the user wants C to feed into an existing build.

**Proposal: `c` stays a processor value meaning "processor unknown until a C compiler runs". Case 2 is an output form, not a target.**

| Want | Write | `$target.arch` | `$target.os` |
|---|---|---|---|
| Portable ISO C11, standard library only | `c` | `'c'` | `'stdc'` **(new)** |
| Same in C89 | `c89` (dialect = version glued to `c`) | `'c'` | `'stdc'` |
| C11 + POSIX (any Unix) | `c-posix` | `'c'` | `'posix'` |
| C for Linux on an unknown CPU | `c-linux` | `'c'` | `'linux'` |
| C for bare metal on an unknown CPU | `c-freestanding` | `'c'` | `'freestanding'` |
| C99 + Windows | `c99-windows` | `'c'` | `'windows'` |
| C for a **known** target (ESP32, a console) | `--target xtensa_lx6 -o fw.c` (output extension `.c`, or a `.c` output when there's no backend for the processor) | `'xtensa'` | `'freestanding'` |

Consequences:

- Only on `c*` targets are `pointer_bits`, `endian` and `features` unknown. They read as `none` there, and a condition on them is an error until it's guarded with `$target.arch =? 'c'`. The emitted C uses `<stdint.h>` and checks `sizeof(void*) <= 8` with a `_Static_assert`.
- **Change from the sketch:** bare `c` means *portable standard C*, not "C for this machine's OS". C output is for portability, and C for the host is never what you want (build natively instead). The other reading is open issue 7.
- `posix` and `stdc` are system values that only make sense with `c`, since a native binary can't target "some POSIX". They double as **pattern** words (§4): `posix` matches every target whose `$target.posix` is true.

**wasm.** The difference between the browser and WASI is the **system**, the same axis as Linux vs Windows: different imports, different facilities, different `|unsupported` sets.

| Name | Meaning |
|---|---|
| `wasm32` (= `wasm32-web`, also reachable as `web`) | browser: JS glue + HTML page, WebGL2 or WebGPU, Web Audio, no threads (today's target) |
| `wasm64` | browser with memory64 |
| `wasm32-wasi` | WASI preview 1 (wasmtime, wasmer, most hosts) |
| `wasm32-wasi2` | WASI 0.2 / components |
| `wasm32-freestanding` | bare module whose imports are only the program's `$extern`s (plugins, embedding) |

**Change:** `$target.os` for `wasm32` becomes `'web'`, not `'none'`. Then `if $target.os =? 'web'` reads as what it means, and `if $target =? 'wasm32'` stops being the idiom (it would wrongly match code meant for WASI).


---

## 4. The `$target` record

Existing today: the string value, `.arch` and `.os`. Everything else is **(new)**. Every member is a compile-time constant. Conditions on them fold, so the dead arm is never checked, as `$target.os` conditions already work. Folding gains three forms: bare boolean members, numeric comparisons (`<? <=? >? >=?`) against literals, and `LITERAL in? $target.MEMBER` for list members.

| Member | Type | Values / example | Status |
|---|---|---|---|
| `$target` | string | canonical name: `'x86_64-linux'`, `'cortex_m4f'`, `'aarch64-mac14'` | existing (value now canonical) |
| `.arch` | string | ISA family: `x86_64 x86 aarch64 arm riscv64 riscv32 wasm32 wasm64 xtensa c` … | existing |
| `.cpu` | string | resolved level or core: `'x86_64_v2'`, `'cortex_a76'`, `'apple_m1'`, `'znver4'` (under `native`) | new |
| `.features` | list of string | `sse4_2 avx2 fma bmi2 avx512f neon dotprod fp16 sve2 simd128 fpu fpu64 atomics` … | new |
| `.os` | string | `linux mac windows ios tvos watchos visionos android freebsd openbsd netbsd uefi web wasi freestanding posix stdc` | existing (wasm32: `'web'`, was `'none'`) |
| `.os_version` | number | `14` (`mac14`), `29` (`android29`), the floor when unwritten; `0` for freestanding | new |
| `.env` | string | variant: `'musl' 'gnu' 'sim' 'soft'` or `'none'` | new |
| `.posix` `.apple` `.bsd` `.mobile` `.hosted` | bool | families. `hosted` = an OS provides files/processes (false for `freestanding`, `uefi`, wasm `freestanding`) | new |
| `.pointer_bits` | int | 32 / 64 (`none` on `c`) | new |
| `.address_bits` | int | 48 native, 32 wasm32 (the range LANGUAGE.md already ties `int`/`addr` to) | new |
| `.endian` | string | `'little'` / `'big'` | new |
| `.gpu` | list of string | shader backends this build carries: linux/windows/android `['vulkan' 'gl']`, apple `['metal']`, web `['webgl2']` (later `webgpu`), MCU `[]` | new |
| `$host` | same record | the machine doing the compiling (build scripts, compile-time file reads, "is this a cross build": `$target not=? $host`) | new |

**Families** (one fact per member):

| OS | posix | apple | bsd | mobile | hosted |
|---|---|---|---|---|---|
| linux | ✓ | | | | ✓ |
| android | ✓ | | | ✓ | ✓ |
| mac | ✓ | ✓ | | | ✓ |
| ios / tvos / watchos / visionos | ✓ | ✓ | | ✓ (ios, watchos) | ✓ |
| freebsd / openbsd / netbsd | ✓ | | ✓ | | ✓ |
| windows | | | | | ✓ |
| web | | | | | ✓ (but no files or processes: see `|unsupported`) |
| wasi | | | | | ✓ |
| uefi / freestanding | | | | | |

### How gating reads

```dewy
if $target.os =? 'windows' { ... }                         # existing form
if $target.posix { ... }                                    # new: bare boolean member
if 'avx2' in? $target.features { ... }                      # new: literal in? list member
if $target.os =? 'mac' and $target.os_version >=? 14 { ... }  # new: numeric compare
if $target.pointer_bits =? 32 { ... }
```

### Connecting to `|unsupported`

This is David's idea from discussion_points (~3400), made concrete with this record:

1. **Platform facilities are typed by `$target` conditions in the library.** A facility is a value whose type depends on the target. In the portable view it is `T|unsupported`. Once the target is fixed, the condition folds and the type collapses to `T` or to `unsupported`:

   ```dewy
   # lib/core/os.dewy (sketch)
   env:dict<string string>|unsupported = if $target.hosted and $target.os not=? 'web' {
       __read_environ()
   } else { unsupported }
   ```

2. **Using an `unsupported` value is a compile error** that names the target and the deciding fact:
   `error: os.env is unsupported on cortex_m4f (no operating system: $target.hosted is false)`.
   You don't write a separate `require(...)`: using the facility is the requirement, exactly as the discussion note concludes. Checking it explicitly (`if os.env is? unsupported {...}`) folds like any target test.
3. **The IDE's "expected target" is `$supported_targets`.** It's already the module's declaration of where it may run. With patterns (below), it is also the set the editor checks against. The editor shows `T|unsupported` only when *some* target in the set lacks the facility, so a Linux-only module sees plain `dict<string string>`. With no declaration, the IDE uses the main file's `$target`, or failing that the host. `dewy check` checks once per pattern, using a representative concrete target, so the work is demand-driven and costs N× check only for modules that ask for N.

### `$supported_targets` patterns

The member already exists. Its entries become **patterns** instead of full names (new semantics):

- A pattern is any subset of fields, using the same vocabulary. Omitted fields match anything.
- A pattern may also be a family word: `posix`, `apple`, `bsd`, `mobile`, `hosted`.
- A target is accepted if it matches any entry.

```dewy
$supported_targets = ['posix' 'windows']            # any hosted desktop or phone, not web or bare metal
$supported_targets = ['linux' 'mac' 'windows' 'web']
$supported_targets = ['cortex_m4f' 'cortex_m33f']   # the cores this driver's FPU code assumes
$supported_targets = ['x86_64_v3' 'aarch64']        # an AVX2-only kernel library, plus ARM
```

A refinement still matches. `x86_64_v3-linux-musl` matches `'linux'`, `'x86_64'` and `'posix'`.


---

## 5. Catalog

"Implies" lists what the name fixes without writing it. Default floors are proposals.

| # | Name | What it is | Implies |
|---|---|---|---|
| 1 | `x86_64-linux` | Linux PC or server | cpu `x86_64_v2`, ELF, static, no link-time libc, C libraries loaded at run time, kernel ≥ floor (e.g. 4.4) |
| 2 | `x86_64_v3-linux` | same, for Haswell / Zen 1 and later | AVX2, FMA, BMI2 in `.features` |
| 3 | `x86_64-linux-musl` | fully static with musl (Alpine, scratch containers, static C archives) | env `musl` |
| 4 | `x86_64-linux-gnu2.28` | ordinary dynamic glibc binary (RHEL 8+, Debian 10+) | PT_INTERP, versioned symbols ≤ 2.28 |
| 5 | `native` | this machine, every feature of this CPU | e.g. `znver4-linux`, not portable |
| 6 | `aarch64-linux` | 64-bit ARM Linux: Raspberry Pi 3/4/5 on a 64-bit OS, Graviton, Ampere | armv8.0, little-endian, ELF |
| 7 | `cortex_a76-linux` | Raspberry Pi 5, tuned | armv8.2 + dotprod, fp16 |
| 8 | `cortex_a72-linux` | Raspberry Pi 4, tuned | armv8.0, A72 scheduling |
| 9 | `arm-linux` | 32-bit ARM Linux, Debian armhf (Pi 2/3/4 on a 32-bit OS) | armv7-a, hard-float, NEON |
| 10 | `arm_v6-linux` | Pi Zero / Pi 1 on Raspberry Pi OS 32-bit | ARMv6 + VFP, hard-float (Raspbian's armhf) |
| 11 | `riscv64-linux` | RISC-V Linux SBC (VisionFive 2, Milk-V) | rv64gc, lp64d |
| 12 | `riscv64_rva23-linux` | RVA23 boards, with vector | `v` in features |
| 13 | `aarch64-mac` | Apple silicon Mac | cpu `apple_m1`, Mach-O, libSystem, macOS ≥ 11, gpu `metal` |
| 14 | `aarch64-mac14` | same, may call macOS 14 APIs | `os_version` 14 |
| 15 | `x86_64-mac` | Intel Mac | `x86_64_v2`, macOS ≥ 11 |
| 16 | `aarch64-ios` (or just `ios`) | iPhone / iPad device | iOS ≥ floor (e.g. 15), `mobile`, `apple` |
| 17 | `aarch64-ios-sim` | iOS Simulator on an Apple-silicon Mac | env `sim` |
| 18 | `x86_64-ios-sim` | iOS Simulator on an Intel Mac | env `sim` |
| 19 | `aarch64-android` (or just `android`) | Android phone | bionic, API ≥ floor (e.g. 24), gpu `vulkan` + `gl` |
| 20 | `aarch64-android33` | Android, API 33 floor | `os_version` 33 |
| 21 | `x86_64-android` | Android emulator / ChromeOS | |
| 22 | `x86_64-windows` | Windows x64 | PE, MSVC ABI, UCRT, Windows ≥ 10 |
| 23 | `aarch64-windows` | Windows on ARM (Snapdragon X) | the ARM level Windows 11 requires, PE |
| 24 | `x86-windows` | 32-bit Windows (legacy) | i686 + SSE2 |
| 25 | `wasm32` (or `web`) | browser | os `web`, JS glue + HTML, gpu `webgl2`, no threads |
| 26 | `wasm64` | browser, memory64 | `pointer_bits` 64 |
| 27 | `wasm32-wasi` | WASI preview 1 (wasmtime, wasmer) | no JS, `hosted` |
| 28 | `wasm32-wasi2` | WASI 0.2 component | component model |
| 29 | `wasm32-freestanding` | bare wasm module (plugins) | imports = the program's `$extern`s |
| 30 | `cortex_m4f` | Cortex-M4 with FPU: STM32F4, nRF52840 | thumbv7em, hard-float, freestanding, ELF |
| 31 | `cortex_m0p` | RP2040 (Pi Pico), STM32G0 | thumbv6m, soft-float; board library gives the memory map; `-o fw.uf2` |
| 32 | `cortex_m33f` | RP2350, nRF5340, STM32U5 | armv8-m.main + FPU + TrustZone |
| 33 | `cortex_m7f` | STM32H7, Teensy 4 | thumbv7em; double-precision FPU shows as `fpu64` in features where the core has it |
| 34 | `riscv32_imc` | ESP32-C3 | rv32imc, freestanding |
| 35 | `riscv32_imac` | ESP32-C6, RP2350's Hazard3 cores | rv32imac |
| 36 | `xtensa_lx6` | ESP32 (original) | freestanding; C output (`-o fw.c`) until there's a backend |
| 37 | `xtensa_lx7` | ESP32-S3 | as above |
| 38 | `x86_64-freestanding` | kernels, after a bootloader handoff | ELF, no red zone, no SIMD unless the cpu level says so (issue 14) |
| 39 | `aarch64-freestanding` | bare-metal Pi, hypervisors | ELF |
| 40 | `x86_64-uefi` | UEFI application or bootloader | PE32+, MS x64 ABI, not `hosted` |
| 41 | `aarch64-uefi` | ARM UEFI | PE32+ |
| 42 | `x86_64-freebsd` | FreeBSD | libc implied, FreeBSD ≥ floor (e.g. 13) |
| 43 | `aarch64-freebsd` | FreeBSD on ARM | |
| 44 | `x86_64-openbsd`, `x86_64-netbsd` | other BSDs | `bsd` |
| 45 | `spirv` | standalone Vulkan SPIR-V kernel module | system `vulkan` (`spirv-vulkan1.3` for a version floor) |
| 46 | `msl` | Metal Shading Language source module | system `metal` (`msl-metal3`) |
| 47 | `ptx_sm80` | CUDA PTX for Ampere | system `cuda`. Plain `ptx` is the compiler's floor (e.g. sm_52). |
| 48 | `amdgpu_gfx1100` | AMD RDNA3 code object | system `hsa` |
| 49 | `c` | portable C11, standard library only | arch `c`, os `stdc` |
| 50 | `c89` | portable C89 | as above, C89 dialect |
| 51 | `c-posix` | C11 + POSIX | os `posix` |
| 52 | `c-linux`, `c-windows`, `c-freestanding` | C for that system on an unknown CPU | |
| 53 | `x86_64-linux` + `-o prog.c` | C source with every x86_64-linux fact already decided | output form, not a target |
| 54 | `aarch64-horizon`, `x86_64-orbis` … | consoles (NDA): the name shape is reserved, delivered by C output + platform layer | not public |

GPU names (45–48) are only `--target` values for **kernel-only builds**: a file of GPU functions emitted as a `.spv`, `.ptx` or `.metal`. Ordinary programs never name them. A game built for `aarch64-mac` emits MSL for its shaders because `$target.gpu` is `['metal']`, the same way the compiler's `glsl`/`msl`/`spirv` modules are picked today.


---

## 6. Prior art

| Scheme | Example | Gets right (taken) | Gets wrong for Dewy |
|---|---|---|---|
| **LLVM triples** | `x86_64-unknown-linux-gnu`, `thumbv7em-none-eabihf`, `arm64-apple-macosx14.0` | Universal. Processor first. Arch spellings carry endianness and ISA version (`thumbv7em`, `ppc64le`). | Fixed slots force filler (`unknown`, `pc`, `none`). The vendor field is mostly redundant. The env field is overloaded: libc, float ABI, simulator, Android, MSVC. CPU level and features sit outside the name, and OS versions are inside it only on Apple. |
| **Rust** | `aarch64-apple-darwin` + `-C target-cpu=native -C target-feature=+avx2`, `cfg(target_os = "linux")`, `cfg(target_family = "unix")`, `target_pointer_width`, `target_feature` | The `cfg` facet set is excellent. Dewy's `$target` members mirror it (`os`, families, `pointer_bits`, `features`). Tiered support lists. | Names inherit triple noise (`x86_64-pc-windows-msvc`). `target-cpu` is outside the name, so `--target` alone doesn't say what binary you get. `unix` and `windows` families are special-cased. |
| **Zig** | `x86_64-linux-musl`, `aarch64-macos.14`, `x86_64-linux-gnu.2.28`, `-mcpu=x86_64_v3+avx512f` | Drops the vendor. Versions attach to the OS or libc field (Dewy glues them, without the dot). Pins the glibc symbol version. Cross builds by default. `native`. `_v3` CPU spellings (adopted). | `-mcpu` is a separate flag. The ABI field is still needed for MCUs (`thumb-freestanding-eabihf`), where Dewy uses the core (`cortex_m4f`). Version ranges (`linux.5.10...6.1`) are heavy. |
| **Go** | `GOOS=linux GOARCH=amd64 GOAMD64=v3`, `GOARM=7`, `//go:build linux && amd64`, `_windows.go` | Two simple axes. Level as a small knob. **Static, libc-free Linux binaries** (Dewy's default). The `unix` build tag. | `darwin`, `amd64`, and env vars instead of one name, so a target is not one copyable string. `GOOS=ios`/`android` hacks. No OS floors in the name (only a `go.mod` toolchain policy). |
| **Swift / Apple** | `arm64-apple-ios17.0-simulator`, `arm64-apple-ios14.0-macabi` | **OS floor glued to the OS** and **simulator as an env** (both adopted). | `apple` repeats what `ios` says. `arm64` vs everyone else's `aarch64`. |
| **.NET RIDs** | `linux-x64`, `linux-musl-x64`, `osx-arm64`, `win-arm64` | Short, no vendor. `musl` only when it isn't the default (adopted). | Arch comes last, unlike everyone else. **Versioned RIDs (`win10-x64`, `ubuntu.20.04-x64`) were abandoned because the compatibility graph exploded.** That lesson is why Dewy's versions are *floors*, matched as refinements, never identities (issue 6). |
| **Debian multiarch** | `x86_64-linux-gnu`, `arm-linux-gnueabihf`, `aarch64-linux-gnu` | No vendor. | ABI suffix needed on every name. Float ABI is buried in `gnueabihf`. |
| **Nix systems** | `x86_64-linux`, `aarch64-darwin` | Two fields: almost exactly Dewy's common case. | The short form can't say musl, a CPU level or an OS floor, so Nix falls back to full LLVM-style `crossSystem` records. Dewy's optional third field and glued versions close that gap. |
| **TinyGo** | `-target=pico`, `-target=esp32c3` | Board names are the UX embedded users love. | A board is a memory map, pins and a flasher. That's library material. Dewy keeps cores in the name and boards in `@lib/boards` (issue 9). |

---

## 7. Gating examples

The syntax follows LANGUAGE.md. Member uses marked (new) are from §4. The library APIs inside the examples are illustrative only.

### 7.1 Platform file I/O (a standard-library module)

```dewy
# lib/core/fs_raw.dewy
$supported_targets = ['posix' 'windows' 'wasi']

if $target.os =? 'windows' {
    $extern(name='CreateFileW' lib='kernel32')
    create_file_w = (name:ptr<uint16> access:uint32 share:uint32 sec:ptr<uint8>? disposition:uint32 flags:uint32 template:ptr<uint8>?):>ptr<uint8>
    open_read = (path:string):>Handle | IOError => windows_handle(create_file_w(wide(path) GENERIC_READ 1 none 3 0 none))
} else if $target.os =? 'linux' {
    # no libc: straight to the kernel, as host_target.dewy does
    open_read = (path:string):>Handle | IOError => $unsafe fd_handle(syscall(2 data(__zstr(path)) 0 0))
} else {
    # other POSIX systems and WASI: the system C library is the API
    $extern
    open = (path:string flags:int32):>int32
    open_read = (path:string):>Handle | IOError => fd_handle(open(path 0))
}
```

### 7.2 Audio backend choice

```dewy
if $target.os =? 'web' {
    import p"audio/web_audio.dewy" as backend
} else if $target.apple {                                   # new member
    import p"audio/core_audio.dewy" as backend
} else if $target.os =? 'windows' {
    import p"audio/wasapi.dewy" as backend
} else if $target.os =? 'android' {
    import p"audio/aaudio.dewy" as backend
} else if $target.os =? 'linux' or $target.bsd {            # new member
    import p"audio/alsa_pulse.dewy" as backend              # loaded at run time
} else {
    import p"audio/none.dewy" as backend                    # play: ... | unsupported
}
```

On `cortex_m4f`, a game that calls `audio.play(sound)` gets this error: *`audio.play` is unsupported on cortex_m4f (no audio backend for system freestanding)*. A program that never plays sound builds fine.

### 7.3 SIMD fast path with fallback

```dewy
dot = (a:array<float32> b:array<float32>):>float32 => {
    if 'avx2' in? $target.features {                        # new: x86_64_v3 and up, or native
        return dot_avx2(a b)
    } else if 'neon' in? $target.features {                 # every aarch64 target
        return dot_neon(a b)
    } else if 'simd128' in? $target.features {              # wasm32 with SIMD (in the default web level)
        return dot_simd128(a b)
    }
    dot_scalar(a b)
}
```

`x86_64-linux` (default `v2`) compiles only the scalar arm. `x86_64_v3-linux` and `native` on a modern PC compile only the AVX2 arm. Choosing a path at run time inside one binary is a separate feature (issue 11).

### 7.4 Embedded vs hosted allocation

```dewy
if $target.hosted {                                         # new member
    scratch = () => Arena(capacity=64 * 1024 * 1024)        # from the OS heap
} else {
    # bare metal: no heap; a fixed region the board library's linker map reserves
    from p"@lib/boards/board.dewy" import (free_sram)
    scratch = () => Arena.over(free_sram)
}

sample_buffer:array<float32, 256> = ...                     # same code on both from here on
```

### 7.5 A library declaring what it supports

```dewy
# lib/serial/serial.dewy
$supported_targets = ['linux' 'mac' 'windows' 'freebsd']    # new: patterns, not full names

open_port = (name:string baud:int):>Port | SerialError => {
    if $target.os =? 'windows' { return win_open(name baud) }
    posix_open(name baud)                                   # every remaining target is POSIX
}
```

```
$ dewy build game.dewy --target wasm32
error: lib/serial/serial.dewy supports linux, mac, windows, freebsd; this build is wasm32 (os web)
  --> game.dewy:3  import p"@lib/serial/serial.dewy"
```

Inside this module, the IDE treats `os.env` as `dict<string string>` (every listed system has one). In a module whose set includes `'web'`, it shows `dict<string string> | unsupported`.

### 7.6 One game, three platforms

```dewy
# main.dewy
$supported_targets = ['x86_64-windows' 'aarch64-mac' 'wasm32']
$build.mode = 'release'

main = () => {
    let w = window('Dunes' 1280 720) or_throw
    if $target.os =? 'web' { show_click_to_start(w) }       # browsers need a gesture before audio
}
```

```sh
for t in x86_64-windows aarch64-mac wasm32; do
    ./tools/dewy build main.dewy --target $t -o out/$t/dunes
done
# out/x86_64-windows/dunes.exe   out/aarch64-mac/dunes   out/wasm32/dunes.html
```

**(new, optional)** `--target` could repeat: `dewy build main.dewy --target x86_64-windows --target aarch64-mac --target wasm32 -o out/` would make one output per target (issue 16).

### 7.7 OS version floor

```dewy
$target = 'aarch64-mac14'
...
if $target.os =? 'mac' and $target.os_version >=? 14 {     # new: numeric compare folds
    import p"mac/new_api.dewy" as present                   # API added in macOS 14
} else {
    import p"mac/legacy.dewy" as present
}
```

The library side, with the `|unsupported` idea: `metal_fx:MetalFX | unsupported` is `unsupported` below its macOS floor. On `aarch64-mac` (floor 11), using it gives *`metal_fx` needs macOS ≥ 13; this build's floor is 11 (raise it: `$target = 'aarch64-mac13'`)*.

### 7.8 Pointer width, and C output

```dewy
if $target.arch =? 'c' {
    # portable C: processor unknown; pointer_bits is none here, so this test comes first
    Hash:type = uint64
} else if $target.pointer_bits =? 64 {
    Hash:type = uint64
} else {
    Hash:type = uint32                                      # wasm32, arm-linux, Cortex-M, riscv32
}
```


---

## Open issues

Each has my recommendation and the strongest argument against it.

1. **Should a bare processor or bare OS take the host's other field (`aarch64` → `aarch64-linux` on Linux, `windows` → `x86_64-windows`), even in a main file?**
   *Recommend:* yes, everywhere. `$target` and the build line always show the canonical expansion (`building for aarch64-linux`).
   *Against:* `$target = 'windows'` in a committed file builds different binaries on an ARM laptop and an x86 desktop. Files ought to be reproducible, which argues for allowing shorthand only on the CLI.

2. **Default x86-64 level: `v1` or `v2`?**
   *Recommend:* `v2` (SSE4.2, POPCNT). Windows 11 24H2 and RHEL 9 already require it, and nearly every PC still in use has it.
   *Against:* QEMU's default `qemu64` CPU model and some CI VMs report only v1. A default build would crash with SIGILL in those environments, which is the worst kind of first impression.

3. **CPU level or core in the processor field (`x86_64_v3-linux`), rather than a separate `$target.cpu = …` setting or a `-mcpu` flag?**
   *Recommend:* in the name, so one copyable string describes the binary. That fits "only mode and target come from the CLI". Allow no `+feature` lists: if a level or core isn't enough, add a core name.
   *Against:* names multiply (`cortex_a76-linux`, `x86_64_v3-linux-musl`). Patterns and canonicalisation have to understand levels as refinements. Rust and Zig both chose a separate knob.

4. **`aarch64` or `arm64`?**
   *Recommend:* `aarch64` (it's what Dewy uses now, and LLVM, Linux `uname`, Rust and Zig agree). `arm64` errors with a hint.
   *Against:* Apple, Microsoft, Go, Debian and .NET all say `arm64`, and most users type `arm64` first. One accepted alias would cost nothing.

5. **`mac` or `macos`?**
   *Recommend:* keep `mac` (today's spelling, short, a plain word).
   *Against:* next to `ios`, `tvos` and `watchos`, the pattern says `macos`. Apple, Zig and Swift all use `macos`.

6. **Versions glued to the field (`aarch64-mac14`, `android29`) rather than a separate field (`aarch64-mac-14`)? And are they part of target identity?**
   *Recommend:* glued, and only as floors that match as refinements, so `aarch64-mac14` satisfies `$supported_targets = ['aarch64-mac']`. That avoids .NET's abandoned versioned-RID graph.
   *Against:* `android29` reads as "Android 29", but it means API level 29, which is Android 10. Users will get it wrong.

7. **Bare `c` = portable ISO C (proposed), or "C for this machine's OS" (sketch)?**
   *Recommend:* portable ISO C (`os 'stdc'`). Nobody wants C for the host. C output exists for portability.
   *Against:* it breaks the one clean rule, "a bare processor means this machine's system". Every other processor follows that rule.

8. **Linux default: static, no link-time libc, system C libraries loaded at run time.**
   *Recommend:* yes. It's what the compiler does today, and it gives one binary for every distro.
   *Against:* glibc doesn't support being loaded into a static executable. The `dl.jo` bootstrap depends on loader internals, so a glibc or musl change could break every shipped Dewy game at once. Go and Zig steer clear of this for that reason.

9. **Chips and boards (`rp2040`, `pico`, `esp32c3`) as target names?**
   *Recommend:* no. The target is the core (`cortex_m0p`). Boards are libraries that supply the memory map, startup code and flashing. If they test well, chip names could later become documented *aliases* that expand to core + board import.
   *Against:* embedded users think in boards. TinyGo's `-target=pico` is the UX they praise, and "which core is my chip?" is a lookup a beginner shouldn't have to make.

10. **Is GPU a device axis implied by the host target, rather than a program target?**
    *Recommend:* yes. `$target.gpu` is derived from the OS. Only kernel-only builds name `spirv`, `ptx_sm80` or `msl`.
    *Against:* a program that wants Vulkan on macOS (through MoltenVK), or GL instead of Vulkan on Linux, has no knob. `$target.gpu` would then need to be settable, which is a new `$build`-style member.

11. **Runtime CPU dispatch (one binary, AVX2 path picked at run time).**
    *Recommend:* not part of target naming. Later, a separate construct (for example a runtime `cpu.has('avx2')` that the optimiser can clone over) while `$target.features` stays the compile-time floor.
    *Against:* games ship one `.exe`. With only compile-time gating, they must either give up AVX2 or ship several builds, so the "C-like speed" goal pushes for dispatch now.

12. **Families as boolean members (`$target.posix`) or a list (`'posix' in? $target.families`)?**
    *Recommend:* booleans. They read best in `if` and follow "one fact per member".
    *Against:* families are open-ended (`unix`, `desktop`, `console`, `embedded` …). Each one becomes a new member name needing approval, where a list grows quietly.

13. **wasm32's OS is `web` (today it is `none`).**
    *Recommend:* `web`.
    *Against:* the same JS-glue module also runs in Node, Deno and Bun, where there's no DOM. `js` might be the more accurate system name, with `web` as a refinement of it.

14. **What ABI does `x86_64-freestanding` mean?**
    *Recommend:* kernel-safe (no red zone, no SIMD unless the cpu level opts in), as Rust's `x86_64-unknown-none` is. Variant `-user` **(new)** for freestanding code that runs in user space.
    *Against:* most freestanding users who aren't writing a kernel (sandboxed runtimes, unikernels with their own FPU save) lose SIMD by default. That's a speed trap the "fast by default" goal dislikes.

15. **Windows C runtime: `msvcrt.dll` (today) or UCRT (`ucrtbase.dll`)?** This was discovered while reading `dewy_ffi_attrs.dewy` and is outside the naming scope.
    *Recommend:* UCRT, since the floor is Windows 10, which ships it. `fma` and hex `strtod` then work without `lib='ucrtbase'`.
    *Against:* MinGW-built C libraries that users link may expect `msvcrt`, and mixing CRTs across DLL boundaries breaks `FILE*` and `malloc`/`free` pairs.

16. **Multi-target builds: should `--target` repeat (§7.6)?**
    *Recommend:* yes, with `-o DIR/` and one output per target named by its extension (`.exe`, `.html`, none).
    *Against:* it complicates "the CLI overrides the file's one `$target`". A shell loop already does the job, and CI matrices want one target per job anyway.

17. **`$host` as a new record.**
    *Recommend:* add it, with the same members as `$target`. Compile-time code that reads files, and `dewy test` deciding whether it can run what it built, need it.
    *Against:* it invites host-dependent compile-time logic, which hurts reproducibility. Most uses are better served by `$target not=? $host` being a build-tool concern, not a language one.

**Before any of these reach open_decisions.md:** run the new names (`host`, `native`, `stdc`, `web`, `.cpu`, `.features`, `.os_version`, `.env`, `.hosted`, `.apple`, `.bsd`, `.mobile`, `.pointer_bits`, `.address_bits`, `.gpu`, `$host`, the `_vN` level spelling) through the cold-reader naming kit, and dogfood ten programs per AGENTS rule 6.
