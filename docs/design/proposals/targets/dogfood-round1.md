# Dogfood: compilation target names (round 1)

Thirteen programs in [programs-r1/](programs-r1/), written against the merged design
in [round1.md](round1.md). Each is graded 1–5 on **O**bvious, **D**iscoverable,
**C**oncise, **S**afe by default and co**M**plete, against the best of Rust,
Zig, Go, Swift and C/CMake for the same job. Library APIs inside the programs
are illustrative; the target surface is what's graded.

## Changes made to the design while dogfooding

| # | Found in | Problem | Change |
|---|---|---|---|
| 1 | 02, 03 (first drafts) | `if $target =? 'x86_64-linux'` silently takes the other arm on `x86_64_v3-linux` or `x86_64-linux-musl`. | In a folded condition, `$target =? 'NAME'` is an error with a fix-it to the member test. Names in conditions belong to `$supported_targets`. |
| 2 | 05 | A Pico user knows "Pico" or "RP2040", not `cortex_m0p`. | `--target rp2040` / `pico` is an error naming the core and the board library, found by looking up `@lib/boards/NAME.dewy` on the error path only (no chip table in the compiler). |
| 3 | 05 | Importing a board library while forgetting `$target` gave a generic "not supported" error. | The `$supported_targets` error for a one-core library names the exact `$target` line to add. |
| 4 | 10 | `xtensa_lx7` with no backend had no path forward. | The error for a processor without a backend gives the fix-it `-o NAME.c`. |
| 5 | 10 | Portable C has no pointer width; testing `.pointer_bits =? 64` was wrong on `c`. | `.pointer_bits` and `.endian` are `none` on `c` targets, and folding accepts `=? none`. |
| 6 | 02, 11 | Choosing shader backends at compile time needed the system's GPU APIs. | `.gpu` (list) kept as a member. |
| 7 | 09 | If `wasm32-wasi`'s floor rose from preview 1 to 0.2, every build would stop running on preview-1 hosts. | `wasi` means preview 1, permanently; `wasi2` is 0.2. |
| 8 | 04 | `cortex_m7f` would assume a double-precision FPU that some M7 parts lack. | `cortex_m7f` = single precision (safe); `cortex_m7d` = double. |
| 9 | 07 | On a musl distro, a C call from an `x86_64-linux` build fails at run time with a vague message. | The run-time error names the library and the link-time variants (`-musl`, `-glibc`). |
| 10 | 13 | `($target.os =? 'mac' and $target.os_version >=? 14) or (...)` is long next to Swift's `#available(macOS 14, iOS 17, *)`. | Facilities carry their own floor as `T | unsupported`; programs test the facility (`if observation.watch isnt? unsupported`). Version arithmetic stays for the rare case. |

## Grades (after the changes)

| # | Program | O | D | C | S | M | Compared with | Notes |
|---|---|---|---|---|---|---|---|---|
| 01 | [CLI for Linux, macOS, Windows](programs-r1/01-wc-cli.dewy) | 5 | 5 | 5 | 5 | 5 | Go `GOOS`/`GOARCH` loop; Rust `--target` + a cross linker | One flag per build and no linker or SDK setup for the three. `$supported_targets` stops an unplanned target. |
| 02 | [Game choosing audio and graphics](programs-r1/02-game-backends.dewy) | 5 | 5 | 5 | 5 | 5 | Rust `cfg(target_os)` + `cfg(target_vendor = "apple")` | Imports inside folded arms; `.apple`, `.mobile`, `.gpu` read plainly. |
| 03 | [SIMD fast path with fallback](programs-r1/03-simd-dot.dewy) | 5 | 5 | 5 | 5 | **4** | Rust `cfg(target_feature)` + `is_x86_feature_detected!`; C `__builtin_cpu_supports` | Loops get AVX2 at run time already. **M 4:** hand-written intrinsics can't be chosen at run time in one binary (outside naming; see round1 §10). `native` and `x86_64_v3-…` are one flag each. |
| 04 | [Cortex-M4F firmware](programs-r1/04-cortex-m4-firmware.dewy) | 5 | 5 | 5 | 5 | 5 | Rust `thumbv7em-none-eabihf` + `memory.x` + `cortex-m-rt`; CMake toolchain files | `cortex_m4f` says the chip family and the FPU; the board library holds the memory map; output by extension. |
| 05 | [RP2040 blink](programs-r1/05-pico-blink.dewy) | 5 | 5 | 5 | 5 | 5 | TinyGo `-target=pico` | First draft D 3 (users must know the core). Changes 2 and 3 make every wrong guess one fix-it away. Same line count as TinyGo. |
| 06 | [ESP32-C3 blink](programs-r1/06-esp32c3-blink.dewy) | 5 | 5 | 5 | 5 | 5 | Rust `riscv32imc-unknown-none-elf` + esp-hal | `riscv32_imc` is the ISA string vendors print; `'atomics' in? $target.features` handles the C3's missing A extension. |
| 07 | [Library declaring targets](programs-r1/07-serial-library.dewy) | 5 | 5 | 5 | **4** | 5 | Rust `cfg` + `compile_error!`; Go build tags | Patterns plus family words in one list; the import error names the library and the build. **S 4:** on a musl distro the default Linux build's C calls fail at run time (today's loader needs glibc; change 9 makes the message clear). The fix is in the runtime, not the names. |
| 08 | [Browser wasm app](programs-r1/08-web-app.dewy) | 5 | 5 | 5 | 5 | 5 | Rust `wasm32-unknown-unknown` + wasm-bindgen; Go `GOOS=js` | `wasm32` alone, `.os =? 'web'`, `--target host` for a native dev loop. |
| 09 | [WASI tool](programs-r1/09-wasi-tool.dewy) | 5 | 5 | 5 | 5 | 5 | Rust `wasm32-wasip1` / `wasip2`; Go `GOOS=wasip1` | `start_process` is `unsupported` there, so the compile error comes before the run. |
| 10 | [C output: ESP32-S3 and portable C](programs-r1/10-c-output.dewy) | 5 | 5 | 5 | 5 | 5 | Nim/Zig C backends; CMake | `-o lamp.c` follows the `.html` precedent; the no-backend error teaches it. `c-posix`, `c89` unchanged from today. |
| 11 | [GPU compute](programs-r1/11-gpu-compute.dewy) | 5 | 5 | 5 | 5 | 5 | CUDA `nvcc -arch=sm_80`; Rust-GPU `spirv-unknown-vulkan1.2` | GPU functions follow the host target; kernel-only builds name the GPU ISA (`ptx_sm80`), with `amdgpu` refusing to guess a chip. |
| 12 | [Cross-compile build file](programs-r1/12-release-build.dewy) | 5 | 5 | 5 | 5 | 5 | Zig `build.zig` target matrix; CMake toolchain files; GoReleaser | Each build is one name; a tuned `x86_64_v3-windows` artifact needs no other flag, which a separate CPU setting could not do under the command-line rule. |
| 13 | [OS floors and the iOS simulator](programs-r1/13-os-floors-sim.dewy) | 5 | 5 | 5 | 5 | **4** | Swift `#available`, deployment targets; Xcode SDK settings | First draft C 4 (version arithmetic); change 10 fixes it. **M 4:** a binary can't use a newer API when the OS it runs on is newer than its floor (Swift can). Run-time availability is outside naming. |

**Lowest grades:** three 4s (03 M, 07 S, 13 M). All three are run-time
features next to target naming (CPU dispatch, C loading on musl, OS
availability), not the names. Every target-surface criterion is 5 after the
ten changes.

## What the comparison languages do better

- **Swift** picks newer OS APIs at run time from one binary (`#available`).
- **Rust / C** pick CPU features per function at run time.
- **TinyGo** flashes the board (`tinygo flash`). Dewy writes `.uf2`/`.bin`;
  flashing tools stay external.

None of these needs a target-naming change; each is its own feature.
