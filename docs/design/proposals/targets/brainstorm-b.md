# Dewy compilation targets (round 1)

Names are hyphen-separated facts in the order architecture, system, then only an extra the default does not already imply (a non-default ABI, a version floor, the simulator).
`x86_64-linux` means glibc and ELF; musl, no libc, MinGW, a macOS or iOS floor, an Android API level, WASI, and the iOS simulator are written because each one changes the contract.
A bare processor is an error, not "this machine": omitting `--target` is this machine, and `$build.host` is its canonical name.
`wasm32` stays the browser target; `wasm32-wasi` and `wasm32-freestanding` name the other runtimes, and `$target.os` for `wasm32` is `browser`.
Portable C stays a pseudo-architecture (`c89`, `c-posix`, `c-linux`); C that implements one real ABI is `$build.emit = 'c'` on that target, not a second name.
CPU level stays out of the name (`$target.cpu = 'v3'`, default `baseline`); a chip with one instruction set is a single token (`rp2040`, `esp32c3`) and still exposes `.arch` and `.os`.
The `$target` record keeps `arch` and `os`, and adds `abi`, `family`, `posix`, `apple`, `pointer_bits`, `endian`, `format`, `float_abi`, `cpu`, `features`, `min_version`, `chip`, and `simulator`, folded in `if` the way `os` is today.
A platform API has type `T | unsupported` and collapses once the target is known, so using a missing API is a compile error; there is no `require` syntax.
`$supported_targets` accepts a full name or an architecture, a system, a family, `posix`, or `apple`.
The public names already in the language (`x86_64-linux`, `aarch64-mac`, `x86_64-windows`, `wasm32`, `c-posix`, `c89`) stay; the two meaning changes are bare-arch-as-host, and `wasm32`'s system value.

This file is one independent pass. It does not look at the other brainstormers. Nothing in the repo was edited.

## What changes from today

| Today (LANGUAGE.md and `compiler/targets.dewy`) | This proposal |
|---|---|
| `x86_64` means this machine's system | Not a target. Error, with a fix-it of the host's full name when the processor matches |
| `wasm32` has `$target.os =? 'none'` | Same name, `$target.os =? 'browser'` |
| One dash, two fields, split at the first `-` | A closed vocabulary: later tokens are an ABI, a version, or `simulator` |
| `c` is an architecture, including bare `c` | `c` stays an architecture; bare `c` is an error, same as bare `x86_64` |
| CPU, libc, pointer width, endian, format are invisible | They are members. Only a non-default libc/ABI is spelled in the name |
| `$supported_targets` is a list of full names | Full names still work; an architecture, system, family, `posix`, or `apple` matches every concrete target with that fact |

`new` below means a member, a setting, or a behavior the compiler does not have yet. Target-name vocabulary (`musl`, `wasi`, `rp2040`, …) is the subject of this note, not new syntax.

## 1. Grammar

A target name is lowercase ASCII. The processor token may contain underscores (`x86_64`) or digits (`thumbv7em`, `wasm32`). Fields are separated by `-`. There is no vendor field.

```
name     = complete | arch '-' os | arch '-' os '-' extra
extra    = abi | version | role | abi '-' version | version '-' role | abi '-' version '-' role
complete = a catalog name with no dash: wasm32, wasm64, c89, metal, amdgpu,
           nvptx64, thumbv6m, thumbv7m, thumbv7em, rp2040, esp32, esp32c3, esp32s3
abi      = musl | none | mingw
version  = digits | digits '.' digits | 'api' digits
role     = simulator
```

Tokens are classified by a closed list, not by position. `musl` is an ABI, `14` and `14.2` and `api34` are versions, `simulator` is a role. Any other third token is an error that names the legal ones. Order is fixed: ABI, then version, then role. `aarch64-ios-simulator-17` is an error whose fix-it is `aarch64-ios-17-simulator`.

`arch` and `os` are the vocabularies in the field tables below. `c89` is a complete name, not `c` plus a system: ISO C89 has no system.

### What an omitted field means

Omission means a **declared default**, the same one on every machine. It never means "whatever this computer is."

| You wrote | The gap is filled with |
|---|---|
| nothing (`--target` absent, no `$target =`) | This machine. The stored name is the full canonical name, such as `x86_64-linux` |
| a processor that has a declared default system (`wasm32`, `thumbv7em`, `nvptx64`, `metal`, `amdgpu`) | That default. The short name is the canonical name |
| a processor with no default (`x86_64`, `aarch64`, `c`, `spirv`, `armv7`, `riscv64`) | Nothing. This is an error, not a guess |
| `arch-os` | That pair's default ABI and default version floor |
| a chip token | That chip's processor, system, and CPU. The canonical string stays the chip |

Declared defaults for a bare processor:

| Processor | Default system | Why the short name is enough |
|---|---|---|
| `wasm32`, `wasm64` | `browser` | The game/web target. Other runtimes write `-wasi` or `-freestanding` |
| `thumbv6m`, `thumbv7m`, `thumbv7em` | `freestanding` | These profiles are not hosted. An RTOS later is `thumbv7em-zephyr`, not a change to the short name |
| `nvptx64` | `cuda` | PTX as Dewy users meet it |
| `amdgpu` | the ROCm HSA runtime | The gfx chip is `$target.cpu`, not a name field |
| `metal` | `metal` | One runtime |
| `x86_64`, `x86`, `aarch64`, `armv6`, `armv7`, `riscv32`, `riscv64`, `c`, `spirv` | none | More than one real system exists, or would |

Defaults once the system is written:

| System | Default ABI (omitted) | Default version floor |
|---|---|---|
| `linux` | `gnu` (glibc, dynamic) | the member stays 0 in the name; see open issues for the sysroot floor |
| `windows` | `msvc` (the Windows ABI) | 0, meaning the Windows 10 x64 ABI |
| `mac` | `apple` | 11.0 on `aarch64`, 10.15 on `x86_64` |
| `ios` | `apple` | 16.0 |
| `android` | `bionic` | API 24 |
| `freebsd`, `openbsd`, `netbsd` | the system libc | 0 |
| `freestanding`, `uefi`, `browser`, `wasi` | `none` | 0 |

Writing a field that equals the default is an error with a fix-it of the short name. `x86_64-linux-gnu`, `wasm32-browser`, `thumbv7em-freestanding`, and `aarch64-mac-11` each have one spelling, the short one. Unknown names keep today's shape of diagnostic (`arm64` suggests `aarch64-…`, `macos` suggests `aarch64-mac`, `wasm` suggests `wasm32`).

### This machine

There is no target named `native` or `host`. Those strings are errors. The fix-it for `native` is to drop `--target`.

`new` `$build.host` is the canonical name of the machine running the compiler (`x86_64-linux`, `aarch64-mac`, …). It is read-only. `if $target =? $build.host` is the "built for this machine" test, and it folds.

A bare processor is not a shorthand for "the host system, but this processor." `--target aarch64` on an x86-64 Linux box does **not** mean `aarch64-linux`. The user writes `aarch64-linux`. The diagnostic can still say "this machine is `x86_64-linux`; the same system on that processor is `aarch64-linux`."

`$target = 'x86_64'` in a file is the same error as the flag. Source and the command line share one grammar. The stored `$target` string is always a canonical name, never a processor alone, which is already what LANGUAGE.md requires of the value.

### Parsing examples

| Input | Result |
|---|---|
| `x86_64-linux` | legal |
| `x86_64-linux-musl` | legal, ABI musl |
| `x86_64-linux-none` | legal, Linux syscalls, no libc |
| `x86_64` | error |
| `x86_64-linux-gnu` | error, fix-it `x86_64-linux` |
| `wasm32` | legal, browser |
| `wasm32-wasi` | legal |
| `aarch64-ios-17-simulator` | legal |
| `aarch64-ios-simulator-17` | error, fix-it `aarch64-ios-17-simulator` |
| `rp2040` | legal complete name |
| `c89` | legal complete name |
| `c` | error |
| `spirv` | error, fix-it `spirv-vulkan` |
| `native` | error, omit the target instead |

The current compiler splits on the first dash (`target_arch_of` / `target_os_of` in `compiler/targets.dewy`). That has to become this vocabulary parse. `c89` is already a special case there; it stays one.

## 2. Fields

A fact goes in the **name** only when another target with the shorter name would be a different contract: different instructions, different system calls, different C ABI, different SDK, or a different device map. A fact that is implied, or that only changes speed, is a **member**.

| Fact | Where | Rule |
|---|---|---|
| Instruction family and pointer width | Architecture token | `x86_64` vs `x86`, `wasm32` vs `wasm64`, `riscv64` vs `riscv32`, `aarch64` vs `armv7`. Not a separate width field |
| System or runtime | System token, unless the architecture's default already says it | Includes `browser`, `wasi`, `uefi`, `freestanding`, `cuda`. "System" means where the program runs, not "has a kernel" |
| libc / C ABI | Trailing ABI token, only when not the default | Linux default is glibc. Dewy does not need a libc to run; the name still tells you which C ABI you link and match |
| OS or SDK minimum | Trailing version, only for `mac`, `ios`, `android` | These pick a sysroot and an availability set. Other systems leave the floor in `$target.min_version` |
| CPU level (`v3`, `cortex-a76`, `native`) | `$target.cpu`, not the name | Same ABI, different speed. A `v3` binary still *is* `x86_64-linux` |
| Enabled ISA features | `$target.features`, derived from the CPU plus the architecture baseline | Gated with `in?` |
| Endianness | `$target.endian` | Every catalog target here is little-endian. A future big-endian machine is a different architecture token (`aarch64be`), not a `-be` field |
| Float ABI | Baked into the architecture token, copied onto `$target.float_abi` | `thumbv7em` is hard-float, `thumbv6m` has no FPU, `armv7` is hard-float. No `eabihf` suffix |
| Object format | `$target.format` | ELF, Mach-O, PE, wasm, C source, or a raw image. Implied by the system |
| Vendor (`unknown`, `pc`, `apple`) | Nowhere | `mac` and `ios` already say Apple |
| Board with one ISA | The whole name | `rp2040`, `esp32c3`. Peripherals are the contract |
| Board with two ISAs | Not a single token | RP2350 is Arm or RISC-V; no `rp2350` name until one is chosen (open issues) |
| GPU device | Its own target, a second compilation | Not a field of `x86_64-linux` |
| Consoles | Not in the catalog | A port is `freestanding` plus a chip, or a future name. No `switch` / `ps5` tokens |
| x32 (ILP32 on x86-64) | Not in the catalog | If it ever matters the architecture token is `x32`, because the width is not the `x86_64` contract |
| Fat / universal binaries | Not a name | Two compilations, then the platform's lipo. One `dewy` invocation, one target |

Dewy and libc, said once: the language runtime may use raw system calls even on `x86_64-linux`. The name is the platform you are allowed to depend on. `x86_64-linux` may call glibc and must honor the x86-64 SysV ABI. `x86_64-linux-musl` may call musl and is the static Alpine target. `x86_64-linux-none` may use Linux system calls only; `$target.posix` is false there because the POSIX C library is absent, while `$target.os` is still `linux`.

Windows `msvc` means the Windows x64 (or ARM64) calling convention and PE, not "link the UCRT." MinGW is the non-default and is spelled `mingw`, not `gnu`: `gnu` on Windows is toolchain jargon, and the field is supposed to describe itself.

Float ABI is not a free choice on the hosted targets. 32-bit ARM Linux in this catalog is hard-float (`armv6`, `armv7`), which is the Raspberry Pi OS and Debian armhf default. Soft-float is not offered; adding it later is a new architecture token, not a suffix on `armv7-linux`.

CPU baselines, so "default" is a real machine and not a moving host:

| Architecture | `baseline` means |
|---|---|
| `x86_64` | x86-64-v1 (SSE2), the psABI floor |
| `aarch64` | ARMv8.0-A |
| `armv7` | ARMv7-A, VFPv3, hard float, Thumb-2 interworking as the Linux ABI requires |
| `armv6` | ARM1176, VFPv2, hard float |
| `riscv64` | RV64GC |
| `riscv32` | RV32GC |
| `thumbv7em` | Thumb-2 plus a hardware FPU (Cortex-M4F / M7 class) |
| `thumbv6m`, `thumbv7m` | no FPU |
| `wasm32` | the WebAssembly 1.0 MVP. Threads, SIMD, and bulk memory are features, off unless `$target.cpu` or a feature list turns them on |

`new` setting, main file only, same statement/expression split as `$build.mode`:

```dewy
$target.cpu = 'v3'
```

Legal values include `baseline` (the default), `v2`, `v3`, `v4` on `x86_64`, `native`, and a core name (`cortex-a76`, `cortex-m4`, `gfx1100`, `rv32imc`). `native` means the compiler host's CPU. It is explicitly non-reproducible, and it does not change the target name. No `--cpu` flag: the 2026-10-23 rule is that only the build mode and the target are overridable from the command line. A flag is an open issue, not part of this proposal.

Object format, endianness, pointer width, and float ABI are implied members, never arguments.

## 3. What `c` is

`c` stays a pseudo-architecture, as in the sketch and in `compiler/targets.dewy`. Portable C is a place the program runs: the "instruction set" is C, and the system token says which APIs the generated C may call.

| Name | Meaning | `$target.os` | `$target.pointer_bits` |
|---|---|---|---|
| `c89` | ISO C89, no POSIX, no extensions | `none` | 0 |
| `c-posix` | POSIX.1, sizes come from the C compiler that later compiles the output | `posix` | 0 |
| `c-linux` | Linux APIs allowed, still source | `linux` | 0 |
| `c-mac` | macOS APIs allowed | `mac` | 0 |
| `c-windows` | Win32 APIs allowed | `windows` | 0 |
| `c-freebsd` | FreeBSD APIs allowed | `freebsd` | 0 |
| `c-freestanding` | A freestanding C implementation, modern enough for Dewy's runtime, no hosted library | `freestanding` | 0 |

`pointer_bits = 0` means "not chosen." Generated C uses `int32_t` and `int64_t` for Dewy's sized integers and does not bake in `sizeof(void*)`. Code that needs a width tests `$target.pointer_bits =? 0` or just uses `int32` / `int64`.

Bare `c` is an error. The sketch's "C for this machine" is `$build.emit = 'c'` on the host target, or an explicit `c-linux` / `c-posix`.

`new` `$build.emit` is `'native'` (default) or `'c'`. Set it in the main file:

```dewy
$target = 'x86_64-linux'
$build.emit = 'c'
```

That writes C with the **x86-64 Linux ABI**: LP64, little-endian, glibc types, ELF assumptions. `$target.arch` stays `x86_64`, not `c`. Pointer width is 64. This is the backend. `c-posix` is the portability target. They are different jobs and both stay.

A Linux-only arm that emits a system-call number must exclude C source:

```dewy
if $target.os =? 'linux' and $target.arch not =? 'c' { }
```

`$target.os =? 'linux'` alone also matches `c-linux`, which is what you want for "Linux headers exist" and the wrong test for "emit `syscall`."

Wasm is the same shape, not a special case of C. The architecture is `wasm32` or `wasm64`. The default system is the browser, so it is unwritten. WASI and freestanding are written.

| Name | Runs in | `$target.os` | `$target.family` |
|---|---|---|---|
| `wasm32` | the browser, with the JS glue a Dewy web game already uses | `browser` | `wasm` |
| `wasm64` | the browser, 64-bit pointers | `browser` | `wasm` |
| `wasm32-wasi` | WASI preview 1 | `wasi` | `wasm` |
| `wasm64-wasi` | WASI preview 1, 64-bit | `wasi` | `wasm` |
| `wasm32-freestanding` | imports the program defines, no JS and no WASI | `freestanding` | `wasm` |

`wasm32-wasi` means preview 1, the one current tools run. A break to the component model would be a new suffix, not a silent change (open issues). `$target =? 'wasm32'` and `--target wasm32` keep working. The member change is `$target.os`: `browser`, not `none`.

GPU targets are their own compilations. A game that also ships a kernel lists both names in `$supported_targets` and splits with `if $target.family =? 'gpu'`.

| Name | What it is |
|---|---|
| `spirv-vulkan` | SPIR-V for Vulkan compute. `spirv` alone is an error: OpenCL would be a different system |
| `metal` | Apple GPU shaders. One token, like `wasm32` |
| `nvptx64` | NVIDIA PTX, 64-bit, CUDA runtime. The SM version is `$target.cpu` (`sm_80`), defaulting to a stated baseline when a backend exists |
| `amdgpu` | ROCm HSA. The chip is `$target.cpu` (`gfx1100`) |

## 4. The `$target` record

`$target` in expression position is the canonical name string. `$target.arch` and `$target.os` stay. The following members are `new`.

| Member | Type | Values |
|---|---|---|
| `$target.abi` | string | `gnu`, `musl`, `msvc`, `mingw`, `bionic`, `apple`, `system`, `wasi`, `none` |
| `$target.family` | string | `unix`, `windows`, `wasm`, `bare`, `gpu`, `c` |
| `$target.posix` | bool | POSIX file, socket, and thread APIs exist |
| `$target.apple` | bool | `mac` or `ios` |
| `$target.pointer_bits` | int | 32, 64, or 0 for portable C |
| `$target.endian` | string | `little` or `big` |
| `$target.format` | string | `elf`, `macho`, `pe`, `wasm`, `c`, `raw`, `spirv`, `ptx`, `metal` |
| `$target.float_abi` | string | `hard`, `soft`, `none` |
| `$target.cpu` | string | `baseline`, `v3`, `native`, a core name |
| `$target.features` | array\<string\> | `sse2`, `avx2`, `neon`, `sve`, `atomics`, `simd128`, … |
| `$target.min_version` | int | 0 if this system has no floor in the name. Scale below |
| `$target.chip` | string | `''`, or `rp2040`, `esp32`, `esp32c3`, `esp32s3` |
| `$target.simulator` | bool | iOS simulator (and the same idea later) |

`new` `$build.host` (string) and `$build.emit` (`native` | `c`) sit on `$build` because they describe the compilation, not the machine the program runs on. `$build.mode` is unchanged.

Family and the two bools:

| System | family | posix | apple |
|---|---|---|---|
| `linux` with abi `gnu` or `musl` | `unix` | true | false |
| `linux` with abi `none` | `unix` | false | false |
| `mac` | `unix` | true | true |
| `ios` | `unix` | false | true |
| `android` | `unix` | true | false |
| `freebsd`, `openbsd`, `netbsd` | `unix` | true | false |
| `windows` | `windows` | false | false |
| `browser`, `wasi` | `wasm` | false | false |
| `freestanding`, and every chip | `bare` | false | false |
| `uefi` | `bare` | false | false |
| `vulkan`, `cuda`, `metal`, and `amdgpu`'s runtime | `gpu` | false | false |
| `c89`, `c-posix`, `c-linux`, other `c-*` | `c` | true only for `c-posix` and for `c-` plus a POSIX system (`c-linux`, `c-mac`, `c-freebsd`) | true only for `c-mac` |

`posix` means those three API groups exist, not "the UNIX trademark" and not "`fork` works." `fork` is its own API and is `unsupported` on iOS and on Android apps even when `$target.posix` is true. iOS is `apple` and `unix` and not `posix`, because the app sandbox is the wrong thing to enter through a POSIX check. Android's bionic is included: the check people write is files and sockets.

Version scale (`$target.min_version`):

| System | Encoding | Example |
|---|---|---|
| `mac`, `ios` | major × 100 + minor | 14.2 → `1402`, default 11.0 → `1100` |
| `android` | API level | API 34 → `34`, default `24` |
| anything else | 0 unless the main file sets it | |

Compare a floor only in an arm that already knows the system. `1400` and `34` are not the same kind of number.

Folding widens the rule LANGUAGE.md already states for `arch` and `os`. These are `new` only in that the folder learns more members and two more types; the operators stay `=?`, `not =?`, `in?`, `not in?`, `<?`, `<=?`, `>?`, `>=?`, `not`, `and`, `or`.

- Strings fold against string literals.
- Bools fold against `true` and `false`, and a bare `if $target.posix` folds.
- Ints fold against integer literals.
- `'avx2' in? $target.features` folds, because the feature list is a compile-time constant.
- A misspelled member or a misspelled literal is an error, as today.
- The dead arm is not checked, as today.

`$supported_targets` stays a file-scope list, set once, and a module compiled for a target that matches nothing in the list is an error. `new` matching rule: an entry matches when it equals the canonical name, or equals `.arch`, `.os`, or `.family`, or is the word `posix` or `apple` and that bool is true. CPU level is ignored, because it is not part of the name. A chip matches an architecture entry: `rp2040` matches `"thumbv6m"`.

```dewy
$supported_targets = ["posix" "windows" "wasm32"]
```

That module accepts glibc and musl Linux, the BSDs, macOS, Android, every Windows ABI, and browser wasm. It rejects `x86_64-linux-none`, iOS, freestanding, and WASI. Exact names still work and are the right list when a library has actually been built for three machines and no others.

### `| unsupported`

This is David's discussion-points idea, with no extra syntax.

A platform API in the standard library has type `T | unsupported` while the target is not concrete. Compiling for a concrete target collapses it: the feature exists, and the type is `T`, or it does not, and the type is `unsupported`. Calling, reading, or otherwise using an `unsupported` value is a compile error that names the feature and the target (`sys.env is unsupported on thumbv6m`). The use is the requirement. There is no `require`, no `sys.platform.supports`, and no `assert` that strips the union.

The IDE uses the same rule. The main file's `$target =` is the expected target. With no setting, the IDE uses the host, which is also the compiler's default. A module whose `$supported_targets` matches several targets keeps `T | unsupported` except inside a folded arm, so a POSIX call written in the open is noisy until it sits in `if $target.posix`, and a Windows-only import in the other arm is unchecked on Linux. That is the existing dead-arm rule, pointed at the editor.

## 5. Catalog

Thirty-plus targets people build, in the proposed spelling. "Implies" is the contract, not a second name. Every row is little-endian. `cpu` is `baseline` unless the row says otherwise. Format is the usual one for that system (ELF, Mach-O, PE, wasm, raw, C, SPIR-V, PTX, Metal).

| Name | What it is | Implies |
|---|---|---|
| `x86_64-linux` | PC and server Linux, glibc | abi `gnu`, posix, unix, 64-bit, SSE2 |
| `x86_64-linux-musl` | Alpine and other static musl | abi `musl`, posix, unix, 64-bit |
| `x86_64-linux-none` | Linux system calls, no C library | abi `none`, not posix, unix, 64-bit |
| `aarch64-linux` | 64-bit ARM Linux: Pi 3/4/5 with a 64-bit OS, Graviton, Ampere | abi `gnu`, posix, ARMv8.0-A. Pi 5 sets `$target.cpu = 'cortex-a76'`; Pi 4, `cortex-a72`; Pi 3, `cortex-a53` |
| `aarch64-linux-musl` | Alpine on ARM64 | abi `musl`, posix |
| `armv7-linux` | 32-bit ARM Linux, hard float: 32-bit Raspberry Pi OS, Debian armhf | pointer 32, float `hard`, posix. This is the Pi 3/4 when the OS is 32-bit |
| `armv6-linux` | Raspberry Pi 1 and Zero | pointer 32, float `hard`, cpu baseline ARM1176 |
| `riscv64-linux` | RV64GC Linux boards (VisionFive, Milk-V, HiFive) | abi `gnu`, posix, 64-bit |
| `x86_64-windows` | 64-bit Windows | abi `msvc`, PE, family windows, not posix |
| `aarch64-windows` | Windows on ARM | abi `msvc`, PE, family windows |
| `x86_64-windows-mingw` | MinGW interop | abi `mingw`, PE. The default Windows name is not this |
| `aarch64-mac` | Apple silicon Mac | min 11.0 (`min_version` 1100), Mach-O, apple, posix |
| `x86_64-mac` | Intel Mac | min 10.15 (`min_version` 1015), apple, posix |
| `aarch64-mac-14` | Apple silicon, macOS 14 SDK floor | `min_version` 1400. Libraries match `mac` or `apple`; they do not list this name |
| `aarch64-ios` | iPhone and iPad devices | min 16.0, apple, not posix, Mach-O |
| `aarch64-ios-17` | device, iOS 17 floor | `min_version` 1700 |
| `aarch64-ios-simulator` | Simulator on Apple silicon | `simulator` true, min 16.0, arch still `aarch64` |
| `aarch64-ios-17-simulator` | Simulator, iOS 17 floor | `simulator` true, `min_version` 1700 |
| `x86_64-ios-simulator` | Simulator on Intel Macs | `simulator` true, arch `x86_64` |
| `aarch64-android` | Android phones | abi `bionic`, API 24, posix, unix, not apple |
| `aarch64-android-api34` | Android 14 phones | `min_version` 34 |
| `armv7-android` | 32-bit ARM Android | pointer 32, bionic, API 24 |
| `x86_64-android` | Android emulator on PCs | bionic, API 24, 64-bit |
| `aarch64-freebsd` | FreeBSD on ARM64 | abi `system`, posix, unix |
| `x86_64-freebsd` | FreeBSD on x86-64 | abi `system`, posix |
| `x86_64-openbsd` | OpenBSD | abi `system`, posix |
| `x86_64-netbsd` | NetBSD | abi `system`, posix |
| `wasm32` | Browser wasm, today's game target | os `browser`, pointer 32, family wasm, WebAssembly 1.0 |
| `wasm32-wasi` | CLI wasm, WASI preview 1 | os `wasi`, pointer 32 |
| `wasm32-freestanding` | Wasm with only the imports you declare | os `freestanding`, family wasm |
| `wasm64-wasi` | 64-bit WASI | pointer 64, os `wasi` |
| `thumbv6m` | Cortex-M0 and M0+, no FPU | os `freestanding`, pointer 32, float `none`, family bare. The canonical name is the short one |
| `thumbv7m` | Cortex-M3, no FPU | freestanding, float `none` |
| `thumbv7em` | Cortex-M4F and M7 with a hardware FPU | freestanding, float `hard`. `$target.cpu = 'cortex-m4'` picks the core |
| `rp2040` | Raspberry Pi Pico | arch `thumbv6m`, os `freestanding`, chip `rp2040`, cpu `cortex-m0plus`, float `none`. The string `$target` is `rp2040` |
| `esp32` | Original ESP32 | arch `xtensa`, freestanding, chip `esp32`, cpu `lx6` |
| `esp32c3` | ESP32-C3 | arch `riscv32`, freestanding, chip `esp32c3`, cpu `rv32imc` (no A, no F). Not the same features as generic `riscv32` |
| `esp32s3` | ESP32-S3 | arch `xtensa`, freestanding, chip `esp32s3`, cpu `lx7` |
| `riscv32-freestanding` | Generic RV32GC, no vendor chip | arch `riscv32`, float as the G profile specifies, chip `''` |
| `aarch64-freestanding` | A kernel or a bare Pi, no userspace | family bare, abi `none`, format `raw` |
| `x86_64-freestanding` | Bare x86-64 | family bare, format `raw` |
| `x86_64-uefi` | UEFI application | os `uefi`, format `pe`, family bare, abi `none` |
| `aarch64-uefi` | UEFI on ARM64 | os `uefi`, format `pe` |
| `spirv-vulkan` | Vulkan compute | arch `spirv`, os `vulkan`, family gpu |
| `metal` | Metal shaders | arch `metal`, os `metal`, family gpu |
| `nvptx64` | CUDA | arch `nvptx64`, os `cuda`, family gpu, 64-bit |
| `amdgpu` | ROCm | arch `amdgpu`, family gpu, cpu names the gfx chip |
| `c-posix` | C source for any POSIX | arch `c`, os `posix`, pointer 0, format `c`, posix |
| `c89` | Strict ISO C89 | arch `c`, os `none`, pointer 0, not posix |
| `c-linux` | C source that may call Linux | arch `c`, os `linux`, pointer 0, posix |
| `c-windows` | C source that may call Win32 | arch `c`, os `windows`, family `c` |
| `c-freestanding` | Freestanding C | arch `c`, os `freestanding`, pointer 0 |

Raspberry Pi, named the way people buy them:

| Board and OS | Target | `$target.cpu` |
|---|---|---|
| Pi 1, Zero | `armv6-linux` | `baseline` |
| Pi 3 / 4, 32-bit OS | `armv7-linux` | `baseline` |
| Pi 3, 64-bit OS | `aarch64-linux` | `cortex-a53` |
| Pi 4, 64-bit OS | `aarch64-linux` | `cortex-a72` |
| Pi 5 | `aarch64-linux` | `cortex-a76` |
| Pico | `rp2040` | implied |

## 6. Prior art

| System | Shape | What Dewy should keep | What Dewy should not take |
|---|---|---|---|
| LLVM triples | `arch-vendor-os-env` | The idea of one string | `unknown` and `pc`, and `gnu` on every Linux triple. The environment slot mixes libc, object format, and float ABI, so people add a fifth field anyway |
| Rust | `arch-vendor-os-abi`, plus `target-cpu` and `target-feature` | CPU features outside the ABI name; `thumbv7em` as an architecture; a closed target list | The vendor; `none-eabihf` as the way to say "bare metal, hard float"; names so long that `if cfg!` hides in build scripts instead of ordinary code |
| Zig | `arch-os-abi`, `-mcpu` | The closest shape: no vendor, ABI last, `x86_64-linux-musl`, `wasm32-wasi` | Writing `gnu` when it is the default; one enormous enum that includes every micro-architecture as a target |
| Go | `GOOS` + `GOARCH` + `GOAMD64` | A tiny OS list, a tiny arch list, the AMD64 level as its own knob, first-class `android` and `ios` | Two variables instead of a name you can store and compare; `amd64` / `arm64` instead of the names Dewy already shipped (`x86_64`, `aarch64`) |
| Swift / Apple | `arm64-apple-ios17.0-simulator` | The version and `simulator` are in the name, because they select the SDK | `apple` repeated in every Apple target; `arm64` rather than `aarch64`; a four-field form for the common case |
| .NET RIDs | `linux-musl-x64`, `win-arm64`, `osx-arm64` | Musl is a qualifier on Linux, not a different OS; short names; a graph of "more specific wins" | OS-first order; `x64` / `osx`; fallback graphs (Dewy matches a declared fact, it does not search a RID chain) |
| Debian multiarch | `x86_64-linux-gnu`, `arm-linux-gnueabihf` | The triple people already read on a distro | `gnu` and `gnueabihf` as mandatory noise. Dewy's `armv7-linux` is that Debian target with the noise omitted |
| Nix | `x86_64-linux`, `aarch64-darwin` | The short form Dewy already has | `darwin` (Dewy already says `mac`); no musl, no iOS, no embedded, no version |

Go's split and Zig's single string are the two serious models. Dewy wants one string, because `$target`, `--target`, and `$supported_targets` are already one string. Go's *discipline* (OS and arch are small, the CPU level is not an OS) is what the member list is for.

## 7. Gating examples

### Platform file I/O

`posix` covers Linux glibc, musl, macOS, the BSDs, and Android. The no-libc Linux target has the system calls and not the C library. The dead arms are not typechecked for this target.

```dewy
read_file = (path:string) => array<uint8> | unsupported {
    if $target.os =? 'linux' and $target.abi =? 'none' {
        return linux_syscall_read(path)
    } else if $target.posix {
        return posix_read(path)
    } else if $target.os =? 'windows' {
        return win32_read(path)
    } else if $target =? 'wasm32' {
        return web_read(path)
    } else {
        return unsupported
    }
}
```

On `thumbv6m`, every arm that calls an API is dead or returns `unsupported`, and a caller that uses the result without handling `unsupported` does not compile.

### Audio backend

The same shape as the example already in LANGUAGE.md, with the system test on the member.

```dewy
if $target =? 'wasm32' {
    import p"web_audio.dewy" as audio
} else if $target.apple {
    import p"apple_audio.dewy" as audio
} else if $target.os =? 'linux' {
    import p"pipewire_audio.dewy" as audio
} else if $target.os =? 'windows' {
    import p"wasapi_audio.dewy" as audio
} else {
    import p"silent_audio.dewy" as audio
}
```

### SIMD, with a scalar fallback

```dewy
$target.cpu = 'v3'

sum = (xs:array<float32>) => float32 {
    if 'avx2' in? $target.features {
        return sum_avx2(xs)
    } else if 'neon' in? $target.features {
        return sum_neon(xs)
    } else {
        return sum_scalar(xs)
    }
}
```

`v3` on `x86_64` puts `avx2` in the feature list, so the other two arms are not compiled. The same source on `aarch64-linux` at `baseline` takes the NEON arm (NEON is mandatory in ARMv8.0-A, so it is on for `aarch64` even at `baseline`). A `thumbv6m` build takes the scalar arm. No name change.

### Hosted heap vs a freestanding bump allocator

```dewy
alloc = (n:int) => ptr<uint8> | unsupported {
    if $target.family =? 'bare' {
        return bump_alloc(n)
    } else if $target.posix or $target.os =? 'windows' {
        return heap_alloc(n)
    } else {
        return unsupported
    }
}
```

`rp2040` and `x86_64-uefi` are `bare` and take the bump path. `wasm32` is `wasm`, not `bare` and not `posix`, so this function is `unsupported` there and the game uses the web allocator in a wasm arm instead.

### A library says what it supports

A POSIX-and-Windows networking library, and a Pico-only GPIO file. The GPIO file's chip test is how a driver refuses a generic M0 that is not the RP2040's peripheral map. A library that is fine on any M0 lists `"thumbv6m"` and then also matches `rp2040`.

```dewy
$supported_targets = ["posix" "windows"]
```

```dewy
$supported_targets = ["rp2040"]

gpio_init = (pin:int) => {
    if $target.chip =? 'rp2040' {
        rp2040_gpio(pin)
    }
}
```

### One source, three platforms

Dewy still builds one target per invocation. The file names the three it is willing to build; the command line picks one. CPU and emit stay in the file when a particular build wants them, because they are not command-line flags under the current rule.

```dewy
$supported_targets = ["x86_64-linux" "aarch64-mac" "wasm32"]

main = () => {
    if $target =? 'wasm32' {
        start_canvas()
    } else if $target.os =? 'mac' {
        start_cocoa()
    } else {
        start_x11()
    }
}
```

```sh
dewy build main.dewy --target x86_64-linux -o game
dewy build main.dewy --target aarch64-mac -o game-mac
dewy build main.dewy --target wasm32 -o game-web
```

A fourth command, `--target aarch64-linux`, fails naming `main.dewy` and the three names it lists. That is the current `$supported_targets` behavior, unchanged.

### Version floor and a CUDA kernel

Two shorter ones, same mechanism. The kernel file is a second compilation, not a modifier on the host name.

```dewy
if $target.os =? 'ios' and $target.min_version >=? 1700 {
    use_swift_ui_bridge()
} else if $target.apple {
    use_appkit_bridge()
}
```

```dewy
$supported_targets = ["nvptx64" "x86_64-linux" "aarch64-linux"]

if $target.family =? 'gpu' {
    export kernel = (xs:array<float32>) => { device_sum(xs) }
}
```

## 8. Open issues

Each recommendation is the one this note would ship. The sentence after it is the strongest reason not to.

1. **Bare `x86_64` is an error, not the host system.** Recommend the error. A name that means Linux on one computer and Windows on another cannot live in `$supported_targets` or in a script, and the compiler already rejects a bare processor that is not the host. Against: cross-compiling to the same OS on another processor is the common case, and `--target aarch64` meaning `aarch64-linux` on a Linux box is shorter; the sketch promised that reading.

2. **The default Linux ABI in the name is glibc, not "no libc."** Recommend glibc, spelled by omitting the ABI. Distro compilers, FFI, and the 80% path are glibc; musl and the syscall-only target opt in. Against: Dewy does not need a libc, so the default name describes an ABI the runtime may never touch, and `x86_64-linux-none` is the more honest "Dewy on Linux."

3. **`wasm32`'s system member becomes `browser`, the name stays `wasm32`.** Recommend that. The string in LANGUAGE.md and in the game template keeps working, and `none` was a placeholder. Against: `browser` is not an operating system, and any code that already tested `$target.os =? 'none'` for wasm (legal today, even if the guide's own example tests the full name) changes meaning.

4. **CPU level is `$target.cpu`, not part of the name.** Recommend leaving it out. `x86_64-linux` and a `v3` build of it are one ABI and should be one `$supported_targets` entry; Go and Rust both made this split. Against: distributors already ship x86-64-v3 as a different artifact (RHEL 10), and a package index that keys only on the target name cannot tell the two apart. The artifact filename can carry `v3` without the language pretending it is a different machine.

5. **No `--cpu` and no `--emit`.** Recommend source settings only (`$target.cpu = 'v3'`, `$build.emit = 'c'`), on the main file. The decided rule is that the command line overrides mode and target and nothing else. Against: a CI matrix that varies the CPU level now has to rewrite the file, which is worse than a flag, and emit-as-C is exactly the kind of thing a script wants to pass.

6. **Redundant fields are errors, not aliases.** Recommend one spelling, with a fix-it (`x86_64-linux-gnu` → `x86_64-linux`, `wasm32-browser` → `wasm32`). Against: Rust and Zig accept the long form, and a warning-plus-canonicalize would let copied triples keep compiling while `$target` still shows the short string.

7. **Chip names are complete targets.** Recommend `rp2040` and `esp32c3` as the canonical strings, with `.arch` and `.os` filled in, and `$supported_targets` architecture entries matching them. Against: a library that listed only `thumbv6m-freestanding` in the old mental model now has two strings for one ABI, and a user who prints `$target` on the Pico sees `rp2040` rather than the architecture they think they cross-compiled.

8. **`$supported_targets` matches an architecture, a system, a family, `posix`, or `apple`.** Recommend the wider match. Listing forty full names is how libraries rot, and exact names remain for the strict case. Against: an entry `linux` also accepts `x86_64-linux-none` and `armv6-linux`, which the author has not tested; a match that accepted only the default ABI would be safer and would surprise people who expected musl to count as Linux.

9. **Android is `posix`; iOS is not.** Recommend that split. The bool is "files, sockets, threads," which bionic has and the iOS app sandbox should not be entered through. Against: bionic is missing enough of POSIX that a true bool will admit code that then fails to link, and iOS does have a POSIX-ish userspace, so the split is a judgment call wearing a type.

10. **glibc version stays out of the name.** Recommend `$target.min_version` as a main-file int (238 for 2.38) when someone needs a floor, default 0, meaning "whatever this sysroot is." Apple and Android keep the version in the name because it selects the SDK. Against: a glibc floor decides whether the binary runs on Debian 11 just as macOS 14 decides whether it runs on Sonoma, so hiding only the Linux floor will produce "works on my machine" builds. A tighter rule, not recommended above, is that the compiler sets `$target.min_version` from the sysroot even when the name is silent.

11. **WASI preview 1 owns `wasm32-wasi`.** Recommend preview 1. It is what the current tools run. Against: preview 2 / the component model is where WASI is going, and spending the unsuffixed name on preview 1 repeats the `wasm32` default problem in two years. The escape, if this loses, is `wasm32-wasi1` and `wasm32-wasi2`, with no unsuffixed form.

12. **Both `c-posix` and `$build.emit = 'c'`.** Recommend keeping the sketch's portable targets and adding emit for "C of this concrete ABI." Against: two ways to get C, and a program that meant "be portable" will set the emit flag on `x86_64-linux` and think it shipped `c-posix`. The member `$target.arch =? 'c'` is the difference, and it is easy to forget.

13. **No `rp2350` name yet.** Recommend waiting until the Arm and RISC-V boots are separate names (`thumbv8m` plus a chip, and a RISC-V chip token). Against: the Pico 2 is a board people already have, and a single token with `$target.cpu` choosing the ISA matches how `$target.cpu` works everywhere else. It doesn't: the two ISAs are different architectures, not levels of one architecture.

14. **`family`, `posix`, `apple`, `abi`, `min_version`, `chip`, `simulator`, `float_abi`, `format`, `pointer_bits`, `endian`, `features`, `cpu`.** Recommend these member names. They have not been through the naming check (three cold readers, names only). Against: `family` collides with the everyday word, `apple` is a vendor bool sitting next to a rule that vendors are not fields, and `abi` on FreeBSD as `system` is vague. `posix` will be read as "the whole POSIX spec" no matter what the table says.
