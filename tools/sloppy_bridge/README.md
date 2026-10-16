# Checked Dewy → Sloppy backend experiment

This is an opt-in Linux x86-64 experiment, not a replacement production
compiler. It takes the current compiler's **checked and runtime-lowered**
UBC2 stream into Sloppy's register IR, optimizer, allocator and ELF emitter.
It does not translate Dewy source or substitute Sloppy's language semantics.
All Dewy allocation, copying, lifecycle operations, refinements and proof
checks stay in the existing compiler/runtime. Consequently record arrays
are still boxed; this isolates backend benefit from representation changes.

## Reproduce

From the repository root (choose new output directories):

```sh
.venv/bin/python tools/sloppy_bridge/build.py \
  --sloppy-root /var/home/david/dev/slop-lang --output /tmp/dewy-sloppy-emitter \
  --bootstrap
.venv/bin/python -m tools.sloppy_bridge.run dewy/benchmarks/apps/records.dewy \
  --dewy /path/to/current/certified/dewy \
  --emitter /tmp/dewy-sloppy-emitter/dewy-sloppy-emit \
  --output /tmp/dewy-sloppy-particles --release
/tmp/dewy-sloppy-particles/program 1000000

DEWY_SLOPPY_EMITTER=/tmp/dewy-sloppy-emitter/dewy-sloppy-emit \
DEWY_TEST_DRIVER_COMPILER=/path/to/current/certified/dewy \
  tools/certify.sh focused tests/python_misc/test_sloppy_bridge.py
```

The build reads Sloppy commit `235e19a271bccad3fe72e36d03264807a632dc1b`
with `git archive`. It never changes that checkout or reads its dirty compiler
source. `--bootstrap` builds the pinned C seed and three Sloppy generations,
requiring the last two binaries to match before building the emitter. Without
that flag, the checkout's existing binary builds it against the pinned library.
`build.json` records seed and generation hashes separately from source identity.
The archive retains Sloppy's MIT license. No installed compiler is replaced.

Each program build keeps its checked `.ubc`, adapter `.ir`, executable,
frontend/emitter logs and `measurement.json`. Report the frontend/lowering,
Python adaptation and native emission times separately: neither the adapter
nor old frontend is an intended final fast path. OS file caches are retained;
a new output directory means no compiled prelude is reused.

## ABI and supported scope

- 64-bit word operations, signed/unsigned comparisons and division, sized
  loads/stores, direct/indirect SysV calls including stack arguments, globals,
  static data, Linux syscalls and structured control flow.
- Comparisons translate Sloppy's `1` to Dewy's all-one true. Division guards
  preserve µDewy's zero-divisor and signed-overflow behavior. Higher-level
  numeric operations are already lowered by Dewy.
- Dynamic stack allocations stay fresh on every execution, including loops.
  `build.py` makes one explicit patch to the pinned x86 emitter for intrinsic
  1000: aligned stack adjustment, with the existing frame-pointer epilogue.
  Its clobbers are reserved scratch RAX, RSP and flags; it does not spill
  caller-saved registers as though it were a function call.
  Using a fixed Sloppy frame slot here would alias repeated allocations.
- Every function is marked `raw_mem`: Sloppy cannot assume its own typed
  alias classes describe Dewy's runtime pointers.
- Both modes use Sloppy's local optimizer; `release` adds its bounded,
  callee-first inlining, loop-invariant arithmetic and release register
  allocator. It does not run loop versioning or vectorization.

External link artifacts, external symbols, floating-point conversion
intrinsics, breakpoints and other unsupported intrinsics fail explicitly.
Debug metadata is not carried over; `debug` here names Sloppy's development
allocation strategy, not a debugger-capable executable. The private IR file
is a trusted build intermediate, not a public bytecode format or an input
validation/security boundary. Source checks always run before adaptation.

## Validation

The initial 22 tests passed in 10.59 seconds: existing backend evaluation-order and
addressing tests; both allocation modes for division, bit/boolean/shift
semantics, short-circuiting, loop exits, indirect calls, static references and
repeated dynamic stack allocation; checked Dewy record copy/growth and
subtype snapshots; and bounds failures (including an unused invalid function)
that must produce no IR or executable. This is focused experiment coverage,
not full language or bootstrap certification.

The final selection has **33 tests**, adding the existing UBC source cases
(strings, containers, function values, globals and control), alias-sensitive
array arguments, resource copies, move/drop hooks and large static buffers.
It passed in **33.66 seconds using a Sloppy-built Dewy compiler** for source
checking and lowering, and the independently bootstrapped emitter. The bridge
has compiled the complete Dewy compiler, not just the particle application.

The unchanged particle program builds and runs. One initial sample took
1.706 s in the existing frontend/lowering/stream pipeline, 0.155 s in Python
adaptation and 0.016 s in Sloppy codegen. Runtime/layout improvements and
repeated matched measurements are the next experiment, not a claim that this
bridge by itself meets the restart budgets. The comparison runner accepts
`--sloppy-emitter /path/to/dewy-sloppy-emit` to include both bridge modes in
the same checksum-checked C/Sloppy/Dewy experiment.
