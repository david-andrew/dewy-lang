# Targets round 1: cold read of the new names

Three fresh readers with no context guessed the meaning of 39 snippets (target
names, `$target` members and `$supported_targets` patterns), shuffled, names
only.

- 37 of 39 read correctly by all three, including `host`, `web`/`wasm32`,
  `wasi`/`wasi2`, `sim`, `musl`, `glibc2.28`, `x86_64_v3`, the Cortex-M and
  RISC-V core words (`cortex_m4f`, `cortex_m7d`, `riscv32_imc`), the GPU words,
  `uefi`, `c-posix`, `c89`, every boolean family member and the patterns
  `['posix' 'windows']` and `['hosted' 'cortex_m4f']`.
- `native`: one reader read "this exact CPU", one read "native code as opposed
  to C or wasm", one was unsure. Failed.
- `$target.gpu`: all three read a boolean "this is a GPU build". Failed.
- Readers assumed `x86_64-linux` links glibc. It is a static executable with no
  C library linked, which runs on every distribution; no rename.

Second round, candidates for the two failures:

| Candidate | Result |
|---|---|
| `host_tuned` | all three: this machine's exact CPU and features, may not run elsewhere |
| `this_cpu` | all three correct |
| `native` | one correct, one "the host platform" with no tuning, one unsure |
| `host_exact` | read as also pinning the exact OS and C library versions |
| `$target.gpu_apis` | all three: list of GPU APIs (`vulkan`, `metal`, ...) |
| `$target.graphics_apis` | read as rendering APIs only |

Taken: `host_tuned` (pairs with `host`) and `$target.gpu_apis`.
