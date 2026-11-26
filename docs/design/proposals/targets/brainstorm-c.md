# Dewy Compilation Target Names — Design Proposal (Round 1)

## 10-Line Summary

1. **Minimal hyphenated grammar:** `<arch>[-<os>[<ver>]][-<abi>[<ver>]][-<env>][@<cpu>[±<feat>...]]`, omitting any field implied by the others (`x86_64-linux`, `aarch64-mac14`, `x86_64-linux-musl`, `aarch64-ios17-sim`, `wasm32-web`).
2. **No redundant defaults:** `x86_64-linux-glibc`, `x86_64-windows-msvc`, `aarch64-linux-android`, and `armv7-linux-hardfloat` are compile errors with fix-its; only non-default overrides or version floors (`glibc2.28`) appear.
3. **Explicit `host`, no bare general-purpose arches:** `host` names this machine (portable baseline), `host@native` tunes for this exact CPU, and bare `x86_64`/`aarch64` are errors so source files never silently change OS across machines.
4. **CPU tuning is orthogonal via `@cpu` / `$target.cpu`:** CPU microarchitecture and feature toggles (`@v3`, `@cortex_a72`, `@+avx2`, `@sm_80`) do not fork platform identity, keeping `--target` as the sole target CLI flag while leaving `$target.base` stable.
5. **Dewy stays libc-free by default on Linux:** pure Dewy programs on `x86_64-linux` emit static syscall-only ELFs; C FFI (`$extern`) binds glibc dynamically by default, or static musl on `x86_64-linux-musl`.
6. **`c` is an abstract portable target, while `$build.backend = 'c'` targets concrete CPUs:** `c-posix`, `c89`, `c-linux`, `c-freestanding` emit ISA-agnostic C (`pointer_bits = none`); concrete targets can still emit C without losing arch facts.
7. **WebAssembly separates ISA from host runtime:** `wasm32-web` (browser), `wasm32-wasi` (WASI), and `wasm32-freestanding` (bare `.wasm`), fixing today's anomaly where browser wasm has `$target.os =? 'none'`.
8. **Rich, flat, one-fact-per-member `$target` record:** exposes `base`, `arch`, `os`, `os_version`, `abi`, `abi_version`, `env`, `families`, `pointer_bits`, `endian`, `float_abi`, `object_format`, `cpu`, and `features` for compile-time folding.
9. **Seamless `|unsupported` integration:** platform APIs lower to real types or `unsupported` per concrete target, and join across `$supported_targets` patterns (`'*-linux'`, `'aarch64-mac'`) so IDEs diagnose missing guards without noise.
10. **Scales cleanly to MCUs and GPUs:** `armv6m-freestanding`, `armv7em-freestanding-hardfloat`, `riscv32-freestanding@rv32imc`, `spirv-vulkan1.3`, `metal3.1`, `ptx@sm_80`, and `amdgpu@gfx1100` all obey the same small grammar.

---

> **Legend for new surface items:** Any syntax, target spelling, `$target`/`$build` member, or metatag not currently implemented in `docs/LANGUAGE.md` is marked **[NEW]**.

---

## 1. Grammar

### 1.1 Syntax

```ebnf
target      := "host" [ cpu_spec ]
             | core_target [ cpu_spec ]

core_target := arch_spec [ "-" os_spec [ "-" mod_list ] ]

arch_spec   := ident [ version ]             # version only on versioned 1-field/standard targets: c89, c99, metal3.1
os_spec     := ident [ version ]             # e.g. linux, mac, mac14, ios17, android31, wasi0.2, vulkan1.3
mod_list    := mod_atom ( "-" mod_atom )*
mod_atom    := ident [ version ]             # non-default ABI/env: musl, glibc2.28, gnu, sim, hardfloat, softfloat, x32

cpu_spec    := "@" cpu_model ( feature_mod )*    # [NEW]
             | "@" feature_mod ( feature_mod )*  # [NEW]
cpu_model   := ident                         # baseline, native, v2, v3, v4, cortex_a72, cortex_m4, rv32imc, sm_80, gfx1100
feature_mod := ( "+" | "-" ) ident           # +avx2, -fma, +simd128, +atomics

ident       := [a-z][a-z0-9_]*
version     := [0-9]+ ( "." [0-9]+ )*
```

### 1.2 Field Order and Separators

| Slot | Separator | Position | Role | Examples |
|---|---|---|---|---|
| 1. `arch` | — | Always first | Processor ISA or abstract machine | `x86_64`, `aarch64`, `armv7`, `armv7em`, `riscv64`, `wasm32`, `c`, `spirv`, `metal`, `ptx` |
| 2. `os[ver]` | `-` | Required unless self-describing | OS or runtime host + optional minimum version | `linux`, `mac14`, `windows`, `ios17`, `android31`, `freebsd14`, `uefi`, `freestanding`, `web`, `wasi0.2`, `posix`, `vulkan1.3` |
| 3. `abi[ver]` | `-` | Optional, non-default only | Non-default libc / C ABI, then pointer/float ABI | `musl`, `glibc2.28`, `gnu`, `nolibc`, `x32`, `hardfloat`, `softfloat` |
| 4. `env` | `-` | Optional, non-default only | Execution sub-environment | `sim` (Apple simulators) |
| 5. `@cpu[±feat]` | `@` **[NEW]** | Optional | Microarchitecture profile / ISA extensions | `@v3`, `@armv8.2`, `@native`, `@cortex_a72`, `@rv32imc`, `@sm_80`, `@+simd128` |

When multiple modifiers appear in `mod_list` (which allows >3 fields when genuinely needed, e.g. `armv7-linux-musl-softfloat`), they appear in fixed canonical order: **libc/C ABI → pointer/float ABI → sub-environment**. Out-of-order modifiers (`armv7-linux-softfloat-musl`) are rejected with a fix-it giving the canonical spelling.

**Why these separators:**
- **`-`** separates identity axes, matching Dewy's existing `x86_64-linux`, `aarch64-mac`, `c-posix`.
- **`_`** joins words inside a single identifier (`x86_64`, `aarch64_be`, `cortex_m4`, `apple_m1`, `sm_80`), matching Dewy's existing `x86_64`.
- **Direct version attachment** (`mac14`, `ios17`, `android31`, `glibc2.28`, `wasi0.2`, `vulkan1.3`, `c89`, `metal3.1`) keeps names compact and matches David's existing `c89`. Because valid OS/ABI/arch stems come from a closed table, splitting a trailing numeric version is unambiguous (while ISA widths like `x86_64`, `wasm32`, `armv7` are part of the stem, not versions).
- **`@`** visually separates *platform identity* (left of `@`) from *CPU/feature tuning* (right of `@`), requires no shell quoting in bash/zsh/fish/PowerShell, and keeps `--target` as the single target CLI flag (honoring `docs/LANGUAGE.md`: *"Only the mode and the target come from the command line"*).

### 1.3 Optional Fields, Redundancy Rejection, and Bare Arches

Every field follows two strict rules:

1. **Nothing redundant (canonical spelling enforced):** If a field value is already implied by the preceding fields, writing it is a compile error with a one-line fix-it.
   - `x86_64-linux-glibc` → error: `glibc` is the default on Linux; write `x86_64-linux` (or pin a version like `x86_64-linux-glibc2.28`).
   - `x86_64-windows-msvc` → error: `msvc` is the default on Windows; write `x86_64-windows`.
   - `aarch64-linux-android` → error: `android` implies the Linux kernel and Bionic; write `aarch64-android`.
   - `aarch64-apple-mac` / `aarch64-darwin` → error: write `aarch64-mac`.
   - `armv7-linux-hardfloat` → error: hard-float is the default on `armv7-linux`; write `armv7-linux`.
   - `x86_64-linux@baseline` → error: `@baseline` is the default; write `x86_64-linux`.
   This guarantees one canonical name per target across docs, CI scripts, and `$supported_targets`.

2. **What an omitted field means:**
   - **Omitted `abi`/`env`:** the platform's canonical default (e.g. syscall-only/glibc on Linux, MSVC/Win32 on Windows, Darwin/libSystem on macOS/iOS, Bionic on Android, hard-float on `armv7-linux`, soft-float on `armv7em-freestanding`).
   - **Omitted version:** the toolchain's documented portable default floor (e.g. macOS 13, iOS 16, Android API 26, glibc 2.28, WASI 0.2, Vulkan 1.2, C11).
   - **Omitted `@cpu`:** portable baseline for that `(arch, os)` pair (e.g. `x86_64` SSE2 on Linux/Windows; Apple M1 / ARMv8.5 on `aarch64-mac`; ARMv8.0+NEON on `aarch64-linux`).
   - **Omitted `os`:** valid **only** when the arch uniquely implies its runtime or needs no OS:
     - `host` **[NEW]** → this machine's concrete target (e.g. `x86_64-linux` on Linux x64).
     - `c`, `c89`, `c99`, `c11`, `c23` → portable hosted ISO C (`$target.os =? 'none'`).
     - `metal`, `metal3.1`, `wgsl`, `ptx`, `amdgpu` → single-runtime GPU targets.
   - **Bare general-purpose CPU (`x86_64`, `aarch64`, `riscv64`, `armv7`):** **compile error** (revising the archived sketch and current `compiler/targets.dewy`).

**Why replace bare arch (`x86_64`) with `host` [NEW]:**
In the current compiler (`compiler/targets.dewy:55`), bare `x86_64` only works on an x86-64 host and errors everywhere else (`--target aarch64` on x86-64 Linux fails instead of meaning `aarch64-linux`). Worse, `$target = 'x86_64'` in a source file silently changes OS from Linux to Windows when checked out on another machine. Meanwhile, without an explicit `host` name, a script cannot override a file's `$target = 'wasm32-web'` back to the local machine (`dewy run game.dewy --target host`) without sniffing `uname`.
- **`host` [NEW]** = this machine's OS + arch with portable baseline CPU (`$target` resolves to e.g. `'x86_64-linux'`, never `'host'`).
- **`host@native` [NEW]** = this machine's OS + arch tuned for this exact physical CPU.
- **`--target x86_64`** = error: *"`x86_64` names only a processor; specify a system (e.g. `x86_64-linux`, `x86_64-windows`, `x86_64-freestanding`), or use `host` for this machine (`x86_64-linux`)."*
- **`--target native`** = error: *"`native` is ambiguous; use `host` for this machine's platform or `host@native` to also target this CPU's extensions."*

---

## 2. Fields: In the Name vs. `@cpu` vs. `$build` vs. Derived

| Fact | Where it lives | Rationale |
|---|---|---|
| **Architecture (ISA)** | Target name (slot 1) | Fundamental codegen identity (`x86_64`, `aarch64`, `armv7`, `armv6m`, `armv7em`, `riscv64`, `riscv32`, `wasm32`, `wasm64`, `xtensa`, `c`, `spirv`, `metal`, `ptx`, `amdgpu`, `wgsl`). |
| **Pointer width** | Implied by `arch` (except rare ILP32 ABIs in slot 3) | `x86_64`/`aarch64`/`riscv64`/`wasm64` → 64; `x86`/`armv7`/`riscv32`/`wasm32` → 32; `c-*` → `none`. Only `x86_64-linux-x32` and `aarch64-linux-ilp32` need slot 3. |
| **Endianness** | Implied by `arch` (`_be` suffix only when non-default) | Almost all modern targets are little-endian. Non-default big-endian is an arch variant (`aarch64_be`, `armv7_be`, `ppc64`, `s390x`, `mips`). |
| **OS / runtime** | Target name (slot 2) | Governs syscalls, headers, object format, runtime host (`linux`, `mac`, `windows`, `ios`, `android`, `freebsd`, `openbsd`, `netbsd`, `uefi`, `freestanding`, `web`, `wasi`, `posix`, `vulkan`, `opencl`). |
| **OS min version** | Attached to slot 2 (`mac14`, `ios17`, `android31`, `wasi0.2`, `vulkan1.3`) | Part of the platform API contract (controls availability of OS APIs and Mach-O/ELF deployment metadata). Optional; omitted = portable default. |
| **libc / C ABI** | Target name (slot 3, non-default only) | `musl`, `glibc2.28`, `gnu` (on Windows). See libc analysis below. |
| **Float ABI** | Target name (slot 3, non-default only) | Incompatible calling convention (`r0` vs `s0`). `armv7-linux` & `armv6-linux` default to hard-float (`-softfloat` overrides); `armv7em-freestanding` defaults to soft-float (`-hardfloat` overrides); `armv6m` has no FPU. |
| **Simulator / sub-env** | Target name (slot 4, non-default only) | `aarch64-ios-sim` vs `aarch64-ios` share arch and OS but have incompatible Mach-O platform tags (`PLATFORM_IOSSIMULATOR` vs `PLATFORM_IOS`) and SDKs. |
| **CPU feature level / microarch** | `@cpu[±feat]` suffix **[NEW]** and `$target.cpu` **[NEW]** | Does not change ABI or object format (except RISC-V/Xtensa ISA profiles). Keeping it behind `@` preserves `$target.base` equality and avoids combinatorial explosion. |
| **Object format** | Derived read-only (`$target.object_format` **[NEW]**) | Uniquely determined by OS/arch (`linux`/`bsd`/`android`/`freestanding` → `elf`; `mac`/`ios` → `macho`; `windows`/`uefi` → `pe`; `wasm*` → `wasm`; `spirv` → `spirv`; `c*` → `c`). Never written in the name. |
| **Output artifact kind** | `$build.output` **[NEW]** (not target name) | `'exe'`, `'lib'`, `'dylib'`, `'obj'`, `'bin'` (raw flat binary for bootloaders/MCUs). Same target can build an executable or a shared library. |
| **Static vs dynamic linking** | `$build.link` **[NEW]** (with target-appropriate defaults) | Packaging policy, not platform identity. `x86_64-linux` (pure Dewy) is always static; with FFI, glibc defaults to dynamic and `musl` defaults to static. |
| **Codegen backend (native vs C)** | `$build.backend` **[NEW]** (`'native'` default, `'c'`) | Lets a concrete target like `ppc64le-linux` emit C without pretending `c` is its arch (see §3). |
| **Board / SoC peripherals** | Library / board package (not target name) | Thousands of MCUs share 6–7 ISA profiles (`armv6m`, `armv7em`, `riscv32`, `xtensa`). Linker scripts and MMIO registers belong in board libraries (e.g. `rp2040`, `stm32f4`), not compiler targets. |

### 2.1 Does Dewy Need a libc at All?

**For pure Dewy programs on Linux: no.** Today, Dewy already issues direct Linux syscalls (`compiler/host_target.dewy`, `lib/core/os.jo`) and only emits `PT_INTERP` / `DT_NEEDED libc.so.6` (`lib/game/dl.jo`) when a program uses `$extern` C FFI or loads system libraries (Vulkan, ALSA, Wayland, X11, sockets via `lib/net.dewy`).

That gives Dewy a clean, zero-ceremony story for libc on every OS:

- **Linux (`x86_64-linux`, `aarch64-linux`, `riscv64-linux`):**
  - If the program uses **no C FFI**, the compiler emits a **static, libc-free ELF** (zero `PT_INTERP`, runs on glibc, musl, Alpine, and `FROM scratch` containers identically!).
  - If the program uses **`$extern` / system `.so` libraries**, default `x86_64-linux` dynamically links against **glibc** (`/lib64/ld-linux-x86-64.so.2`, `libc.so.6`).
  - To pin a minimum glibc symbol floor for older distros: `x86_64-linux-glibc2.28`.
  - To link C libraries against **musl** (statically by default, or dynamic with `$build.link = 'dynamic'` for Alpine): `x86_64-linux-musl`.
  - To *enforce* at compile time that no C library / dynamic loader is ever linked (e.g. minimal init/container binary): `x86_64-linux-nolibc` **[NEW]** (`$target.abi =? 'none'`; any `$extern` referencing libc is a compile error).
- **macOS / iOS (`aarch64-mac`, `aarch64-ios`):** Apple does not guarantee stable raw syscall numbers; `libSystem.B.dylib` *is* the OS ABI. Implied automatically; never named.
- **Windows (`x86_64-windows`, `aarch64-windows`):** `kernel32.dll` / Win32 / MSVC ABI is the OS ABI. Implied automatically; only MinGW/GNU C ABI requires `-gnu` (`x86_64-windows-gnu`).
- **Android (`aarch64-android`):** Bionic (`libc.so`) is the only OS ABI. Implied automatically.
- **BSDs (`x86_64-freebsd`, `x86_64-openbsd`, `x86_64-netbsd`):** Each BSD ships one canonical base libc (`libc.so`). Implied automatically.
- **Freestanding / UEFI / Wasm:** No libc (`$target.abi =? 'none'`).

### 2.2 Detailed Notes on Specialized Target Families

- **Embedded MCUs:** Use official ARM M-profile ISA names (`armv6m`, `armv7m`, `armv7em`, `armv8m`) instead of Rust's cryptic `thumbv7em-none-eabihf`. Every M-profile core is Thumb-only (so `thumb` is redundant), and keeping `-freestanding` leaves clean room for RTOS targets (`armv7em-zephyr`, `armv7em-freertos`).
  - RP2040 (dual Cortex-M0+): `armv6m-freestanding@cortex_m0plus` (or plain `armv6m-freestanding`).
  - Cortex-M4 with hardware FPU (STM32F4, nRF52840): `armv7em-freestanding-hardfloat@cortex_m4` (or `armv7em-freestanding-hardfloat`, implying `fpv4_sp_d16`).
  - Cortex-M7 with double-precision FPU (Teensy 4.1, STM32H7): `armv7em-freestanding-hardfloat@cortex_m7` (`fpv5_dp_d16`).
  - ESP32-C3 (RISC-V without atomics): `riscv32-freestanding@rv32imc`.
  - ESP32-C6 / RP2350 Hazard3 (RISC-V with atomics): `riscv32-freestanding@rv32imac`.
  - ESP32 / ESP32-S3 (Xtensa): `xtensa-freestanding@esp32` / `xtensa-freestanding@esp32s3`.
- **GPU Targets:** Dewy has two GPU modes:
  1. **Embedded shaders / compute kernels** (like `compute(fn)` today) compiled inside a CPU host program; while compiling the kernel body, `$target` switches to the kernel target (e.g. `spirv-vulkan1.3`, `metal3.1`, `wgsl`).
  2. **Standalone GPU compilation** (`dewy build kernel.dewy --target spirv-vulkan1.3 -o kernel.spv`, `--target ptx@sm_80`, `--target metal3.1`, `--target amdgpu@gfx1100`, `--target wgsl`).
  - `spirv` requires an environment (`spirv-vulkan`, `spirv-vulkan1.3`, `spirv-opencl`) because SPIR-V execution/memory models differ across runtimes. `metal`, `ptx`, `amdgpu`, and `wgsl` each have one canonical runtime, so 1 field suffices (`ptx@sm_80`, `metal3.1`, `amdgpu@gfx1100`, `wgsl`).
- **UEFI:** `x86_64-uefi`, `aarch64-uefi`, `riscv64-uefi` — implies PE/COFF, EFI calling convention (MS x64 on x86-64, AAPCS64 on AArch64), no libc.
- **Consoles:** Games are a primary customer (`docs/GOALS.md`). Steam Deck runs standard `x86_64-linux@znver2`. NDA consoles (Switch, PS5, Xbox) won't ship proprietary SDKs in the open compiler, but their targets fit the exact same `<arch>-<os>` grammar (`aarch64-switch`, `x86_64-ps5`, `x86_64-xbox`) via external target definitions without special cases.

---

## 3. What Is `c`? And What Is `wasm`?

### 3.1 `c`: Portable Target vs. Concrete-Target Backend

Treating `c` *only* as an arch loses concrete-target C emission; treating `c` *only* as an `--emit c` backend flag loses portable ISA-independent C. Dewy wants **both**, and they are cleanly distinct:

| Goal | Spelling | `$target.arch` | `$target.pointer_bits` | `$target.endian` | What gets emitted |
|---|---|---|---|---|---|
| **Portable C** (runs on any CPU, like SQLite or Dewy's bootstrap seed) | `--target c-posix`, `--target c89`, `--target c-linux`, `--target c-freestanding` | `'c'` | `none` | `'unknown'` | Architecture-independent C (`size_t`, `sizeof(void*)`, no arch-specific assumptions). |
| **C codegen for a concrete CPU** (bootstrapping, inspecting codegen, or targeting an arch without a native emitter) | `--target ppc64le-linux` with `$build.backend = 'c'` **[NEW]** | `'ppc64le'` | `64` | `'little'` | C specialized for `ppc64le-linux` with concrete layouts, FFI, and arch-gated branches resolved. |

**Why `c` stays in slot 1 for portable C:** When compiling Dewy to portable C, there genuinely *is* no concrete CPU ISA—the C abstract machine **is** the target architecture. Keeping `c`, `c89`, `c99`, `c11`, `c-posix`, `c-linux`, `c-windows`, `c-mac`, and `c-freestanding` matches David's archived sketch verbatim, while `$target.pointer_bits = none` and `$target.endian = 'unknown'` statically prevent portable C code from smuggling in 64-bit or little-endian assumptions!
- **Default C standard:** bare `c` / `c-posix` / `c-linux` / `c-freestanding` defaults to **C11** (needed for `<stdatomic.h>` and `_Alignas`); `c89`, `c99`, `c23` (and `c89-posix`, `c99-freestanding`) select a specific standard.

### 3.2 `wasm`: Separate ISA (`wasm32`/`wasm64`) from Runtime (`web`/`wasi`/`freestanding`)

Today (`compiler/targets.dewy`), bare `wasm32` means "browser WebAssembly" with `$target.os =? 'none'`. That breaks down as soon as WASI and freestanding `.wasm` exist: a browser has DOM, WebGL, WebAudio, Fetch, and URL query params (very much a rich host environment!), whereas freestanding `.wasm` has *none* of those, and WASI has POSIX-like descriptors, clocks, and sockets.

**Proposal:** Apply the exact same `<arch>-<os>` rule to WebAssembly as to every other ISA:

| Target | Meaning | `$target.arch` | `$target.os` | Output artifact |
|---|---|---|---|---|
| `wasm32-web` **[NEW]** | Browser WebAssembly (HTML/JS/WebGL/WebAudio) | `'wasm32'` | `'web'` | `.html` / `.wasm`+`.js` |
| `wasm32-wasi` **[NEW]** | WASI (defaults to WASI 0.2 / Preview 2) | `'wasm32'` | `'wasi'` | `.wasm` component |
| `wasm32-wasi0.1` **[NEW]** | WASI Preview 1 (legacy runtimes) | `'wasm32'` | `'wasi'` | `.wasm` core module |
| `wasm32-freestanding` **[NEW]** | Raw `.wasm` (audio worklet, game plugin, custom host) | `'wasm32'` | `'freestanding'` | raw `.wasm` |
| `wasm64-web`, `wasm64-wasi`, `wasm64-freestanding` **[NEW]** | Memory64 (64-bit pointers) variants | `'wasm64'` | `'web'`/`'wasi'`/`'freestanding'` | same |

- **Features on wasm** use `@`: e.g. `wasm32-web@+simd128` or `wasm32-wasi@+simd128+threads`.
- **What about bare `wasm32`?** Recommend making bare `wasm32` a compile error with a clear migration hint (*"specify `wasm32-web`, `wasm32-wasi`, or `wasm32-freestanding`"*). See Open Issue #2 for the alternative of keeping bare `wasm32` as a shorthand for `wasm32-web`.

---

## 4. The `$target` Record

Following `docs/design/self_hosting.md` (*"one member per fact; statement position sets, expression position reads"*):

### 4.1 Writable vs. Read-Only Members

Only two settings can be written (once, at the top level of the main file; overridden by `--target`):
- `$target = 'aarch64-mac14'` — sets the target (existing).
- `$target.cpu = 'v3'` **[NEW]** — optionally sets the CPU/feature spec independently of OS (e.g. `$target.cpu = 'native'` in a benchmark script that runs on any OS, or overridden by `@cpu` in `--target`).

All other members are read-only compile-time constants derived from the resolved target:

| Member | Type | Example (`x86_64-linux@v3`) | Example (`aarch64-ios17-sim`) | Example (`armv7em-freestanding-hardfloat`) | Example (`c-posix`) | Status |
|---|---|---|---|---|---|---|
| `$target` | `string` | `'x86_64-linux'` | `'aarch64-ios17-sim'` | `'armv7em-freestanding-hardfloat'` | `'c-posix'` | Existing |
| `$target.full` | `string` | `'x86_64-linux@v3'` | `'aarch64-ios17-sim'` | `'armv7em-freestanding-hardfloat'` | `'c-posix'` | **[NEW]** |
| `$target.base` | `string` | `'x86_64-linux'` | `'aarch64-ios-sim'` | `'armv7em-freestanding-hardfloat'` | `'c-posix'` | **[NEW]** |
| `$target.arch` | `string` | `'x86_64'` | `'aarch64'` | `'armv7em'` | `'c'` | Existing |
| `$target.os` | `string` | `'linux'` | `'ios'` | `'freestanding'` | `'posix'` | Existing |
| `$target.os_version` | `TargetVersion \| none` | `none` | `[17 0 0]` | `none` | `none` | **[NEW]** |
| `$target.abi` | `string` | `'glibc'` *(FFI default; pure Dewy is libc-free)* | `'darwin'` | `'none'` | `'c11'` | **[NEW]** |
| `$target.abi_version` | `TargetVersion \| none` | `[2 28 0]` | `none` | `none` | `none` | **[NEW]** |
| `$target.env` | `string` | `'none'` | `'sim'` | `'none'` | `'none'` | **[NEW]** |
| `$target.families` | `array<string>` | `['unix' 'posix' 'hosted' 'cpu']` | `['apple' 'darwin' 'unix' 'posix' 'mobile' 'simulator' 'hosted' 'cpu']` | `['bare_metal' 'embedded' 'cpu']` | `['c' 'posix' 'unix' 'hosted']` | **[NEW]** |
| `$target.pointer_bits` | `int \| none` | `64` | `64` | `32` | `none` | **[NEW]** |
| `$target.endian` | `'little' \| 'big' \| 'unknown'` | `'little'` | `'little'` | `'little'` | `'unknown'` | **[NEW]** |
| `$target.float_abi` | `'hard' \| 'soft' \| 'none'` | `'hard'` | `'hard'` | `'hard'` | `'none'` | **[NEW]** |
| `$target.object_format` | `string` | `'elf'` | `'macho'` | `'elf'` | `'c'` | **[NEW]** |
| `$target.cpu` | `string` | `'v3'` | `'baseline'` | `'baseline'` | `'none'` | **[NEW]** |
| `$target.features` | `array<string>` | `['sse' 'sse2' 'avx' 'avx2' 'fma' 'bmi2']` | `['neon' 'fp16' 'crc' 'aes']` | `['thumb2' 'dsp' 'fpv4_sp_d16']` | `[]` | **[NEW]** |

**Crucial invariant for `@cpu`:** `$target` excludes `@cpu` (`$target` is `'x86_64-linux'` for both `x86_64-linux` and `x86_64-linux@v3`, and `'wasm32-web'` for both `wasm32-web` and `wasm32-web@+simd128`), so writing `$target = 'x86_64-linux@v3'` and writing `$target = 'x86_64-linux'` + `$target.cpu = 'v3'` produce identical `$target` records, and `if $target =? 'wasm32-web'` never breaks when SIMD or CPU tuning is added. `$target.full` **[NEW]** returns the complete string including `@cpu` for diagnostics and build logs; `$target.base` **[NEW]** strips OS/ABI versions too (`'aarch64-mac'` for `'aarch64-mac14'`).

`TargetVersion` **[NEW]** is a compile-time `[major:int minor:int patch:int]` record supporting lexicographic `>=?`, `>?`, `<=?`, `<?`, `=?` against `[14 0]` / `[2 28]` (omitted trailing components default to `0`). Compile-time short-circuit `and` narrows `$target.os_version` when the OS implies a version (e.g. `$target.os =? 'mac' and $target.os_version >=? [14 0]`).

### 4.2 Standard Target Families (`$target.families`) **[NEW]**

| Family | Included targets |
|---|---|
| `'posix'` | `linux`, `mac`, `ios`, `tvos`, `watchos`, `visionos`, `android`, `freebsd`, `openbsd`, `netbsd`, `c-posix` |
| `'unix'` | Same as `'posix'` (minus any future non-Unix POSIX layer) |
| `'apple'` / `'darwin'` | `mac`, `ios`, `tvos`, `watchos`, `visionos` (`'apple'` also includes `metal`) |
| `'bsd'` | `freebsd`, `openbsd`, `netbsd`, `dragonfly` |
| `'mobile'` | `ios`, `android`, `watchos` |
| `'simulator'` | `*-sim` targets |
| `'hosted'` | Desktop, server, mobile OSes, `wasi`, `c-*` (except `c-freestanding`) |
| `'bare_metal'` | `*-freestanding`, `*-uefi`, `wasm*-freestanding`, `c-freestanding` |
| `'embedded'` | MCU profiles (`armv6m`, `armv7m`, `armv7em`, `armv8m`, `riscv32-freestanding`, `xtensa-freestanding`, `avr-freestanding`) |
| `'wasm'` | `wasm32-*`, `wasm64-*` |
| `'browser'` | `wasm32-web`, `wasm64-web` |
| `'cpu'` | All CPU/Wasm targets (non-GPU) |
| `'gpu'` | `spirv-*`, `metal*`, `ptx`, `amdgpu`, `wgsl` |

### 4.3 Compile-Time Folding Rules

The existing compile-time folding condition language (`docs/LANGUAGE.md:6194`) expands to:
- Equality / membership: `=?`, `not=?`, `in?`, `not in?` on `$target`, `$target.base`, `$target.arch`, `$target.os`, `$target.abi`, `$target.env`, `$target.endian`, `$target.float_abi`, `$target.object_format`, `$target.cpu`, `$target.pointer_bits`, `$target.families`, `$target.features`, `$build.mode`.
- Ordering: `>=?`, `>?`, `<=?`, `<?` on `$target.os_version`, `$target.abi_version`, `$target.pointer_bits` **[NEW]**.
- Capability checks: `expr is? unsupported`, `expr isnt? unsupported` **[NEW]**.
- Boolean combinators: `not`, `and`, `or`.
- Misspelled known field/arch/os/family/feature names remain compile errors (preserving Dewy's typo protection).
- Dead arms remain unchecked; the live arm splices into the enclosing scope.

### 4.4 `$supported_targets` Matching and Connection to `|unsupported`

Today `$supported_targets` only accepts exact full target names, which does not scale to 30+ targets, OS versions, and `@cpu` profiles.

**Extended `$supported_targets` rules [NEW]:**
1. **Subsumption:** Listing `'aarch64-mac'` accepts `aarch64-mac`, `aarch64-mac14`, and `aarch64-mac14@apple_m3`. Listing `'aarch64-mac14'` accepts `aarch64-mac14` and `aarch64-mac15`, and rejects `aarch64-mac13`.
2. **Component wildcards:** `'*-linux'` matches any arch on Linux (including `x86_64-linux-musl`, `aarch64-linux@cortex_a72`); `'x86_64-*'` matches any OS on x86-64.
3. **Family predicates:** `'family:posix'` or `'family:hosted'` **[NEW]** (prefixed with `family:` so `'posix'` cannot collide with OS names, or alternatively a compile-time requirement `$require_target 'posix' in? $target.families` **[NEW]** — see Open Issue #5).

**How `|unsupported` collapses (David's `resources/discussion_points.md` design):**
1. **Library definition:** A platform library defines optional capabilities via compile-time `$target` branches whose unsupported arm binds the `unsupported` sentinel **[NEW]** (carrying a diagnostic reason string):
   ```dewy
   # In @lib/std/env:
   if 'hosted' in? $target.families or $target.os =? 'web' {
       env = (name:string):>string? => __os_env(name)
   } else {
       env = unsupported("environment variables are unavailable on {$target}")
   }
   ```
2. **Concrete compilation (`dewy build --target x86_64-linux`):** The compile-time `if` collapses completely. `env` has type `(name:string):>string?` on Linux and type `unsupported` on `armv7em-freestanding`. Calling an `unsupported` binding is an immediate type error naming the reason string.
3. **Multi-target / IDE checking:** When the IDE checks a module with `$supported_targets = ['*-linux' 'armv7em-freestanding']` (or `dewy check --all-supported`), the checker evaluates the module against the declared target set:
   - Capabilities available on **all** targets in `$supported_targets` collapse to their plain type (zero noise!).
   - Capabilities available on **some** targets in `$supported_targets` get type `T | unsupported`. Using them without a guard (`if env isnt? unsupported` or `if 'hosted' in? $target.families`) is an immediate diagnostic listing which supported targets lack it.
   - Inside an editor, setting `$target = '...'` (in a main file) or `$supported_targets = [...]` (in a library) is the exact IDE-facing target declaration David asked for in `resources/discussion_points.md`—no separate IDE config syntax required!

---

## 5. Catalog of Concrete Targets (55 Real-World Targets)

| # | Use case | Proposed name | Implied / derived facts |
|---|---|---|---|
| 1 | Linux x86-64 (standard desktop/server) | `x86_64-linux` | 64-bit LE, ELF, SSE2 baseline; pure Dewy = static syscall-only ELF, FFI = dynamic glibc (default floor 2.28) |
| 2 | Linux x86-64 portable for older distros (Debian 10 / RHEL 8) | `x86_64-linux-glibc2.28` | Same as #1, explicit glibc ≤ 2.28 symbol version floor |
| 3 | Linux x86-64 modern CPUs (Haswell+ / AVX2 / FMA / BMI2) | `x86_64-linux@v3` | Same ABI as #1, enables x86-64-v3 ISA features at compile time |
| 4 | Linux x86-64 static musl (`FROM scratch` / Alpine) | `x86_64-linux-musl` | 64-bit LE, ELF, static musl libc by default |
| 5 | Linux x86-64 strictly zero-libc | `x86_64-linux-nolibc` | 64-bit LE, ELF, static syscall-only; libc `$extern` is a compile error |
| 6 | Linux x86-64 x32 ABI (64-bit regs, 32-bit pointers) | `x86_64-linux-x32` | `pointer_bits = 32`, LE, ELF, x32 syscall/C ABI |
| 7 | Linux AArch64 (servers, Graviton, generic ARM64) | `aarch64-linux` | 64-bit LE, ELF, ARMv8.0+NEON, pure Dewy static / FFI glibc |
| 8 | Linux AArch64 ARMv8.2-A server baseline (Graviton 2+ / LSE atomics) | `aarch64-linux@armv8.2` | Same ABI as #7, enables ARMv8.2-A + LSE atomics + FP16 |
| 9 | Linux AArch64 static musl | `aarch64-linux-musl` | 64-bit LE, ELF, static musl |
| 10 | Linux AArch64 big-endian (networking appliances) | `aarch64_be-linux` | 64-bit BE (`endian = 'big'`), ELF |
| 11 | Raspberry Pi 3/4/5 (64-bit Raspberry Pi OS, portable) | `aarch64-linux` | Runs on all 64-bit Pis (Pi 3/4/5) |
| 12 | Raspberry Pi 4 (64-bit, tuned) | `aarch64-linux@cortex_a72` | `aarch64-linux` + Cortex-A72 scheduling/features |
| 13 | Raspberry Pi 5 (64-bit, tuned) | `aarch64-linux@cortex_a76` | `aarch64-linux` + ARMv8.2-A / Cortex-A76 features |
| 14 | Raspberry Pi 2/3/4 (32-bit Raspberry Pi OS) | `armv7-linux` | 32-bit LE, ELF, hard-float EABI (`eabihf` implied), VFPv3-D16 |
| 15 | Raspberry Pi 1 / Zero (32-bit Raspberry Pi OS) | `armv6-linux` | 32-bit LE, ELF, ARMv6 + VFPv2 hard-float EABI |
| 16 | ARMv7 Linux without hardware float (musl, 4-field example) | `armv7-linux-musl-softfloat` | 32-bit LE, ELF, static musl, soft-float EABI (`eabi`) |
| 17 | IBM Z / mainframe Linux (big-endian) | `s390x-linux` | 64-bit BE (`endian = 'big'`), ELF |
| 18 | Apple Silicon Mac (M1–M4, default floor) | `aarch64-mac` | 64-bit LE, Mach-O, `libSystem`, ARMv8.5+NEON baseline, default macOS floor |
| 19 | Apple Silicon Mac (macOS 14 Sonoma minimum) | `aarch64-mac14` | Same as #18, `os_version = [14 0 0]` |
| 20 | Intel Mac | `x86_64-mac` | 64-bit LE, Mach-O, `libSystem`, x86-64-v2 baseline (all supported Intel Macs) |
| 21 | iPhone / iPad (iOS 17 minimum) | `aarch64-ios17` | 64-bit LE, Mach-O (`PLATFORM_IOS`), `libSystem`, `families` includes `apple`, `mobile` |
| 22 | iOS Simulator on Apple Silicon Mac | `aarch64-ios17-sim` | 64-bit LE, Mach-O (`PLATFORM_IOSSIMULATOR`), `env = 'sim'` |
| 23 | iOS Simulator on Intel Mac | `x86_64-ios17-sim` | 64-bit LE, Mach-O (`PLATFORM_IOSSIMULATOR`), `env = 'sim'` |
| 24 | Android phone (ARM64, default API floor) | `aarch64-android` | 64-bit LE, ELF, Bionic libc, Linux kernel, NEON |
| 25 | Android phone (ARM64, API 31 / Android 12+) | `aarch64-android31` | Same as #24, `os_version = [31 0 0]` |
| 26 | Android 32-bit ARM (`armeabi-v7a`) | `armv7-android` | 32-bit LE, ELF, Bionic, Thumb-2 + VFPv3-D16 (Android softfp ABI implied) |
| 27 | Android Emulator (x86-64 host) | `x86_64-android` | 64-bit LE, ELF, Bionic |
| 28 | Windows x64 (native) | `x86_64-windows` | 64-bit LE, PE/COFF, MSVC/Win32 ABI (`kernel32.dll`, UCRT) |
| 29 | Windows ARM64 (Snapdragon X / Surface) | `aarch64-windows` | 64-bit LE, PE/COFF, MSVC/Win32 ABI, NEON |
| 30 | Windows x64 MinGW/GNU ABI | `x86_64-windows-gnu` | 64-bit LE, PE/COFF, GNU/MinGW ABI |
| 31 | Browser WebAssembly (standard) | `wasm32-web` | 32-bit LE, Wasm, browser JS/HTML/WebGL/WebAudio host |
| 32 | Browser WebAssembly with SIMD128 | `wasm32-web@+simd128` | Same as #31, enables 128-bit Wasm SIMD instructions |
| 33 | WASI CLI / server / plugin (Preview 2) | `wasm32-wasi` | 32-bit LE, Wasm, WASI 0.2 Component Model (explicit: `wasm32-wasi0.2`) |
| 34 | WASI Preview 1 (legacy runtimes) | `wasm32-wasi0.1` | 32-bit LE, Wasm, WASI Preview 1 core module |
| 35 | Bare WebAssembly (audio worklet, embedded sandbox) | `wasm32-freestanding` | 32-bit LE, raw `.wasm`, no JS glue, no WASI imports |
| 36 | 64-bit Memory64 WASI | `wasm64-wasi` | 64-bit LE, Wasm Memory64, WASI 0.2 |
| 37 | Cortex-M4 with hardware float (STM32F4, nRF52840) | `armv7em-freestanding-hardfloat` | 32-bit LE, ELF, Thumb-2 + DSP + `fpv4_sp_d16` hard-float ABI, no OS |
| 38 | Cortex-M7 with double-precision FPU (Teensy 4.1) | `armv7em-freestanding-hardfloat@cortex_m7` | Same ABI as #37 + `fpv5_dp_d16` double-precision FPU |
| 39 | RP2040 (Raspberry Pi Pico, dual Cortex-M0+) | `armv6m-freestanding` | 32-bit LE, ELF, ARMv6-M Thumb, soft-float implied (no FPU); `@cortex_m0plus` optional |
| 40 | ESP32-C3 (RISC-V MCU) | `riscv32-freestanding@rv32imc` | 32-bit LE, ELF, RV32IMC (multiply + compressed, no atomics/FPU), soft-float |
| 41 | ESP32 / ESP32-S3 (Xtensa MCU) | `xtensa-freestanding@esp32` | 32-bit LE, ELF, Xtensa LX6 (`@esp32s3` for LX7 + PIE SIMD) |
| 42 | RISC-V 64-bit Linux SBC (VisionFive 2, Banana Pi F3) | `riscv64-linux` | 64-bit LE, ELF, RV64GC + LP64D hard-float ABI |
| 43 | FreeBSD x86-64 / AArch64 | `x86_64-freebsd`, `aarch64-freebsd` | 64-bit LE, ELF, FreeBSD base libc, `bsd`+`posix` families (`x86_64-freebsd14` for min version) |
| 44 | OpenBSD x86-64 | `x86_64-openbsd` | 64-bit LE, ELF, OpenBSD base libc, `bsd`+`posix` families |
| 45 | UEFI x86-64 / AArch64 bootloader/app | `x86_64-uefi`, `aarch64-uefi` | 64-bit LE, PE/COFF (EFI subsystem), MS x64 / AAPCS64 ABI, no libc |
| 46 | Bare-metal x86-64 (OS kernel) | `x86_64-freestanding` | 64-bit LE, ELF, no OS, no libc |
| 47 | Steam Deck (SteamOS) | `x86_64-linux@znver2` | Standard `x86_64-linux` ABI tuned for AMD Zen 2 |
| 48 | Vulkan compute / graphics shader | `spirv-vulkan1.3` | SPIR-V 1.6 / Vulkan 1.3 memory model, `families = ['gpu' 'shader']` |
| 49 | Apple Metal compute / shader | `metal3.1` | Metal 3.1 AIR / `.metallib`, `families = ['apple' 'gpu' 'shader']` |
| 50 | NVIDIA CUDA / PTX (Ampere) | `ptx@sm_80` | 64-bit LE PTX targeting SM 8.0, `families = ['gpu' 'compute']` |
| 51 | AMD GPU ROCm (RDNA 3) | `amdgpu@gfx1100` | 64-bit LE HSACO ELF targeting RDNA 3, `families = ['gpu' 'compute']` |
| 52 | WebGPU shader | `wgsl` | WGSL text/module, `families = ['gpu' 'shader']` |
| 53 | Portable C for any POSIX OS | `c-posix` | Abstract ISA (`pointer_bits = none`, `endian = 'unknown'`), C11 + POSIX headers |
| 54 | Portable ISO C89 / Freestanding C | `c89`, `c-freestanding` | Abstract ISA; `c89` uses ISO C89 stdlib (`os = 'none'`), `c-freestanding` uses `<stdint.h>`/`<stddef.h>` only |
| 55 | This machine (portable / tuned) | `host`, `host@native` | Resolves to host's concrete target (`x86_64-linux`, `aarch64-mac`, etc.) |

---

## 6. Prior Art Comparison

| System | Example names | What it gets right for Dewy | What it gets wrong for Dewy |
|---|---|---|---|
| **LLVM triples** | `x86_64-unknown-linux-gnu`, `aarch64-apple-darwin`, `thumbv7em-none-eabihf` | Universal industry vocabulary for ISA/ABI concepts; well-documented backend semantics. | Fixed 3–4 slots force junk fillers (`unknown`, `pc`, `apple`, `none`); packs unrelated axes into slot 4 (`gnueabihf`, `android31`); mixes vendor with OS. |
| **Rust** | `x86_64-unknown-linux-gnu` + `-C target-cpu=x86-64-v3 -C target-feature=+avx2` | Separates target identity from CPU/feature tuning; rich `cfg(target_family = "unix")`, `target_pointer_width`, `target_endian`; defaults musl to static linking. | Inherits LLVM's noisy triples verbatim; cryptic MCU names (`thumbv7em-none-eabihf`); requires multiple `-C` flags that clash with Dewy's minimal CLI; no OS/glibc min-version in the target name. |
| **Zig** | `x86_64-linux-gnu.2.28`, `aarch64-macos.14`, `x86_64-linux-musl` + `-mcpu=x86_64_v3` | Drops the vendor slot! First-class OS and glibc minimum versions right in the target string; clean separation of `-mcpu`; treats `native` cleanly; supports freestanding/UEFI/WASI smoothly. | Still requires writing `-gnu` on Linux (`x86_64-linux-gnu` vs Dewy's `x86_64-linux`) and `-msvc` on Windows; uses a separate `-mcpu` flag; `native` mixes host platform with host CPU unless split into target vs cpu. |
| **Go** | `GOOS=linux GOARCH=amd64 GOAMD64=v3` | Radically simple mental model; clean orthogonal CPU level (`GOAMD64=v3`, `GOARM=7`); great `unix` build tag; zero vendor noise. | Separate env vars instead of a single composable target string; no ABI/libc axis (`CGO_ENABLED=0` is a leaky side-channel); cannot express MCUs, simulators, glibc floors, or GPUs cleanly. |
| **Swift / Apple** | `arm64-apple-ios17.0-simulator`, `arm64-apple-macos14` | Explicit OS version and `-simulator` sub-environment; ergonomic `#available` / deployment target model. | Still carries redundant `apple` vendor; trailing `.0`; `arm64` vs `aarch64` split; Apple-centric (weak story for Linux musl, MCUs, freestanding). |
| **.NET RIDs** | `linux-musl-x64`, `osx-arm64`, `win-x64` | Short, readable, non-redundant; hierarchical fallback graph (`ubuntu.24.04-x64` → `linux-x64` → `unix`). | OS-first order conflicts with Dewy's existing arch-first convention; conflates distro marketing names (`ubuntu.24.04`) with ABI floors (`glibc2.28`); no bare-metal, GPU, or CPU-feature story. |
| **Debian multiarch** | `x86_64-linux-gnu`, `arm-linux-gnueabihf`, `x86_64-linux-gnux32` | Drops `unknown` vendor; compact and practical for Linux packaging. | Linux/GNU-centric; glues libc + float ABI + pointer ABI into unreadable portmanteaus (`gnueabihf`, `gnux32`). |
| **Nix** | `x86_64-linux`, `aarch64-darwin` | Proves 2-field `<arch>-<os>` covers ~90% of real desktop/server builds cleanly! | Too coarse once you need musl, glibc versions, simulators, MCUs, WASI vs browser wasm, or GPUs (Nix has to bolt on separate `pkgsStatic` / `pkgsMusl` / `pkgsCross` namespaces). |

**Synthesis for Dewy:** Take Nix's 2-field default (`x86_64-linux`, `aarch64-mac`), Zig's vendorless OS/glibc versioning (`mac14`, `glibc2.28`), Rust's rich compile-time target facts (`families`, `pointer_bits`, `endian`, `features`), and unify CPU tuning behind `@cpu` so the entire specification still travels in one string.

---

## 7. Gating Examples

All snippets use Dewy syntax (`docs/LANGUAGE.md`: space-separated array literals, `=?`, `not=?`, `in?`, `is?`, `isnt?`, `:>`, `=>`, `$extern`, `$unsafe`). Newly proposed members/tags are noted in comments.

### 7.1 Platform File I/O (Hosted vs. WASI vs. `unsupported`)

```dewy
# file_io.dewy — compile-time platform dispatch with `unsupported` fallback
FileError:type = type of error & [message:string]

if 'posix' in? $target.families {                     # [NEW: $target.families]
    $extern(name='open')
    __open = (path:string flags:int32 mode:uint32):>int32
    $extern(name='read')
    __read = (fd:int32 buf:ptr<uint8> count:uint64):>int64
    $extern(name='close')
    __close = (fd:int32):>int32

    read_bytes = (path:string):>array<uint8> | FileError => $unsafe {
        let fd = __open(path 0 0)
        if fd <? 0 { return FileError[message="cannot open {path}"] }
        let out:array<uint8> = []
        let chunk:array<uint8 length =? 4096> = fill(uint8(0) 4096)
        loop true {
            let n = __read(fd chunk.ptr 4096)
            if n <=? 0 or n >? 4096 { break }
            out.extend(chunk[..n))
        }
        __close(fd);
        out
    }
} else if $target.os =? 'windows' {
    import p"@lib/core/windows.jo" as win
    read_bytes = (path:string):>array<uint8> | FileError => win.read_file_bytes(path)
} else if $target.os =? 'wasi' {                      # [NEW: 'wasi' os]
    import p"@lib/core/wasi_fs.dewy" as wasi_fs
    read_bytes = (path:string):>array<uint8> | FileError => wasi_fs.read_file_bytes(path)
} else {
    # Collapses to `unsupported` on bare-metal and wasm32-web; calling it is a compile error.
    read_bytes = unsupported("filesystem I/O is not available on {$target}")  # [NEW: unsupported]
}
```

### 7.2 Audio Backend Choice (Desktop, Mobile, Web, and Versioned API)

```dewy
# audio_backend.dewy — selects native audio driver per OS/family/version
$supported_targets = [
    '*-linux' '*-mac' '*-ios' '*-windows' '*-android' 'wasm32-web'  # [NEW: wildcards & wasm32-web]
]

if $target.os =? 'web' {                              # [NEW: 'web' os]
    import p"backends/webaudio.dewy" as driver
} else if 'apple' in? $target.families {              # [NEW: $target.families]
    # Use AVAudioEngine on macOS 14+ / iOS 17+, AudioQueue on older releases
    if ($target.os =? 'mac' and $target.os_version >=? [14 0]) or     # [NEW: $target.os_version]
       ($target.os =? 'ios' and $target.os_version >=? [17 0]) {
        import p"backends/avaudio.dewy" as driver
    } else {
        import p"backends/audioqueue.dewy" as driver
    }
} else if $target.os =? 'windows' {
    import p"backends/wasapi.dewy" as driver
} else if $target.os =? 'android' {
    import p"backends/aaudio.dewy" as driver
} else if $target.os =? 'linux' {
    import p"backends/alsa_pipewire.dewy" as driver
}

play_buffer = (samples:array<float32>):>void => driver.submit(samples)
```

### 7.3 SIMD Fast Path with Compile-Time Specialization and Runtime Dispatch Fallback

```dewy
# dot.dewy — compile-time SIMD via $target.features, plus runtime dispatch on baseline x86_64
from p"@lib/std/cpu.dewy" import (cpu_has)            # runtime CPUID/auxval probe

dot_scalar = (a:array<float32> b:array<float32>):>float32 => {
    let acc:float32 = 0.0
    loop i in [0..min(a.length b.length)) { acc += a[i] * b[i] }
    acc
}

dot = (a:array<float32> b:array<float32>):>float32 => {
    if 'avx2' in? $target.features and 'fma' in? $target.features {   # [NEW: $target.features]
        # Statically enabled (e.g. x86_64-linux@v3 or host@native): zero runtime check
        return dot_avx2_fma(a b)
    } else if 'neon' in? $target.features {
        return dot_neon(a b)
    } else if 'simd128' in? $target.features {
        # Enabled for wasm32-web@+simd128
        return dot_wasm_simd128(a b)
    } else if $target.arch =? 'x86_64' and $target.os not=? 'freestanding' {
        # Portable x86_64 binary: check CPUID at runtime and dispatch
        if cpu_has('avx2') and cpu_has('fma') { return dot_avx2_fma(a b) }
        return dot_scalar(a b)
    } else {
        return dot_scalar(a b)
    }
}
```

### 7.4 Embedded vs. Hosted Allocation (`$no_hidden_costs` + `bare_metal`)

```dewy
# ring_log.dewy — fixed static storage on embedded MCUs, growable heap buffer on hosted OSes
if 'bare_metal' in? $target.families {                # [NEW: $target.families]
    $no_hidden_costs

    LogBuffer:type = [
        bytes:array<uint8 length =? 1024>
        head:int32
        len:int32
    ]

    make_log = ():>LogBuffer => LogBuffer[bytes=fill(uint8(0) 1024) head=0 len=0]

    log_push = (@buf:LogBuffer byte:uint8):>void => {
        let idx = (buf.head + buf.len) % 1024
        buf.bytes[idx] = byte
        if buf.len <? 1024 { buf.len += 1 } else { buf.head = (buf.head + 1) % 1024 }
    }
} else {
    LogBuffer:type = [bytes:array<uint8> cap:int64]

    make_log = ():>LogBuffer => LogBuffer[bytes=[] cap=65536]

    log_push = (@buf:LogBuffer byte:uint8):>void => {
        if buf.bytes.length >=? buf.cap and buf.bytes.length >? 0 { buf.bytes.remove(0); }
        buf.bytes.push(byte);
    }
}
```

### 7.5 Library Declaring Supported Targets and Capability Gating (`|unsupported`)

```dewy
# config.dewy — portable config loader supporting desktop, WASI, and embedded targets
$supported_targets = [
    '*-linux' '*-mac' '*-windows' 'wasm32-wasi' 'armv7em-freestanding-hardfloat'  # [NEW: wildcards]
]

import p"@lib/std/env.dewy" as sys_env
import p"file_io.dewy" as io

# Because `armv7em-freestanding-hardfloat` is in `$supported_targets`, the IDE types
# `sys_env.env` and `io.read_bytes` as `T | unsupported` here, requiring the guards below.
load_config = (fallback:string):>string => {
    let path = if sys_env.env isnt? unsupported {     # [NEW: isnt? unsupported]
        sys_env.env("APP_CONFIG") ?? "/etc/app.conf"
    } else {
        ""
    }
    if io.read_bytes isnt? unsupported and path.length >? 0 {
        let data = io.read_bytes(path)
        if data is? array<uint8> { return string_from_utf8(data) ?? fallback }
    }
    fallback
}
```

### 7.6 Multi-Platform Build Targeting Three Platforms

Dewy avoids external build DSLs and `-D` CLI flags (`docs/LANGUAGE.md:6247`): shared app logic lives in a library module, and either thin entry files set `$target` (overridable via `--target host` during local dev) or a small Dewy release script invokes the compiler across the target matrix:

```dewy
# game_app.dewy — shared entry logic for Linux, macOS 14+, and Browser WebAssembly
$supported_targets = ['x86_64-linux' 'aarch64-mac14' 'wasm32-web']   # [NEW: mac14, wasm32-web]

# main_web.dewy (sets default target for web builds; override locally with `dewy run main_web.dewy --target host`)
$target = 'wasm32-web@+simd128'                       # [NEW: wasm32-web, @+simd128]
$build.mode = 'release'
import p"game_app.dewy" as app
main = () => app.start()
```

```dewy
# build_release.dewy — builds all three release artifacts in one Dewy script
import p"@lib/std/process.dewy" as proc

const RELEASE_TARGETS:array<[name:string out:string]> = [
    [name='x86_64-linux-glibc2.28' out='dist/game-linux-x64']      # [NEW: glibc2.28]
    [name='aarch64-mac14'          out='dist/game-mac-arm64']      # [NEW: mac14]
    [name='wasm32-web@+simd128'    out='dist/game-web.html']       # [NEW: wasm32-web@+simd128]
]

main = () => {
    loop t in RELEASE_TARGETS {
        printl("building {t.name} -> {t.out}")
        let res = proc.run('dewy' ['build' 'main.dewy' '--release' '--target' t.name '-o' t.out]) or_throw
        if res.code not=? 0 {
            eprintl("failed for {t.name} (exit {res.code})")
            proc.exit(res.code);
        }
    }
}
```

---

## 8. Open Issues

### 1. Bare general-purpose arch (`x86_64`) vs. explicit `host`
- **Recommendation:** Reject bare `x86_64`/`aarch64`/`riscv64` with a fix-it error, and introduce `host` (and `host@native`).
- **Strongest argument against:** Reverses David's archived sketch and current `compiler/targets.dewy`. Someone who writes `--target aarch64` on Linux *could* plausibly mean "cross-compile to `aarch64` on my current OS (`aarch64-linux`)"—convenient on the CLI even if banned inside source files' `$target = ...`.

### 2. `wasm32-web` vs. keeping bare `wasm32` for browser WebAssembly
- **Recommendation:** Require `wasm32-web`, `wasm32-wasi`, and `wasm32-freestanding` so every ISA follows `<arch>-<os>` and `$target.os` is `'web'` rather than `'none'`.
- **Strongest argument against:** Browser games are a flagship Dewy use case (`dewy build --target wasm32` is already documented and memorable). Making bare `wasm32` mean `wasm32-web` (while setting `$target.os =? 'web'`, and using `wasm32-wasi` / `wasm32-freestanding` for the other two) saves 4 characters on the most common web command, at the cost of one special-case omission rule.

### 3. Inline `@cpu` suffix in `--target` vs. a separate `--cpu` CLI flag
- **Recommendation:** Support `@cpu` inline (`x86_64-linux@v3`, `host@native`) *and* `$target.cpu = 'v3'` in source, keeping `--target` as the sole target flag on the CLI while keeping `$target` itself free of `@cpu` (with `$target.full` for the complete spec).
- **Strongest argument against:** `@` introduces a third punctuation mark into target strings, and having `$target` return `'x86_64-linux'` when the user wrote `$target = 'x86_64-linux@v3'` means reading `$target` doesn't round-trip the exact string written unless you read `$target.full`. A separate `--cpu` flag + `$target.cpu` avoids `@` altogether, at the cost of adding another CLI flag beyond `--target` and `--release`/`--debug`.

### 4. Version syntax: attached (`mac14`, `glibc2.28`) vs. dot-separated (`mac.14`, `glibc.2.28`)
- **Recommendation:** Attached (`mac14`, `ios17`, `android31`, `glibc2.28`, `wasi0.2`, `vulkan1.3`, `c89`, `metal3.1`), matching David's `c89` and everyday writing ("macOS 14", "glibc 2.28").
- **Strongest argument against:** Dot-separated (`mac.14`, `glibc.2.28`, `wasi.0.2`, like Zig) makes the lexer/grammar completely table-free and uniform even for future OS/ABI names ending in digits (e.g. `ps5.2` vs `ps52`—note `ps5` followed by a version would collide without a separator!). If Dewy ever adds targets whose OS names end in digits (`ps5`, `win32`), dot separation avoids ambiguity.

### 5. Embedded ARM MCU names: ISA profiles (`armv7em-freestanding-hardfloat`) vs. core names (`cortex_m4f-freestanding`)
- **Recommendation:** Use official ARM ISA profile names (`armv6m`, `armv7m`, `armv7em`, `armv8m`) in slot 1 and optional core tuning in `@cpu` (`@cortex_m4`, `@cortex_m7`, `@cortex_m0plus`).
- **Strongest argument against:** Embedded developers think in cores ("Cortex-M4F", "Cortex-M0+"), not ISA revisions ("ARMv7E-M vs ARMv7-M"). Almost nobody remembers whether Cortex-M4 is `armv7m` or `armv7em` without looking it up, whereas `cortex_m4f` is immediately obvious—though using core names in slot 1 multiplies arch names (M0, M0+, M3, M4, M4F, M7, M23, M33, M55, M85) that share identical ABIs.

### 6. `$supported_targets` family syntax: pattern strings (`'family:posix'`) vs. boolean predicates (`$require_target`)
- **Recommendation:** Support subsumption and `*` wildcards in `$supported_targets = ['*-linux' '*-mac']`, and use a boolean compile-time assertion (e.g. `$require_target 'posix' in? $target.families` **[NEW]**) for family/feature requirements instead of inventing a mini-DSL inside strings.
- **Strongest argument against:** Having two ways to declare module support (`$supported_targets` for lists of names/wildcards and `$require_target` for predicates) splits one concept across two directives; allowing `$supported_targets` itself to accept either a list of patterns or a boolean expression (`$supported_targets = 'posix' in? $target.families`) keeps one directive, though it makes the directive's type polymorphic (`array<string> | bool`).

### 7. Default C standard for bare `c` / `c-posix`: C11 vs. C99
- **Recommendation:** Default bare `c` / `c-posix` / `c-linux` / `c-freestanding` to **C11** (for standard `<stdatomic.h>` and `_Alignas`), with `c89`, `c99`, `c23` available explicitly.
- **Strongest argument against:** C99 has broader support in tiny/vintage embedded C compilers (some still lack C11 atomics), and `c-freestanding` users often expect C99.
