# Self-hosting boundaries

Dewy and Jo lower into one AST, checker and IR: calls between them use the same
ABI. This document records ownership boundaries and the costs that constrain the
remaining cutovers. [GOALS.md](../GOALS.md) is the contract;
[ROADMAP.md](../../ROADMAP.md) owns the work queue. Commit messages record results.

## Mixed-language and bootstrap contract

| Boundary | Rule |
|---|---|
| Imports | Dewy imports `p"x.jo"`, `@lib/...`, or a bare module falling back to `.jo`; Jo uses `use 'x.dewy'`. |
| Places and arrays | Jo `mut` ↔ Dewy `@`; `T[]` ↔ `array<T>`; Jo word `int` ↔ `int64`; `str` ↔ `string`. |
| Positional records | Jo `(str, u8[])` ↔ Dewy `[string array<uint8>]`; no separate Dewy tuple type. |
| Enumeration ABI | A union of string literals maps to a Jo enum in declaration order. Jo orders by ordinal; Dewy orders by text. Preserve that distinction. |
| Bytes | Dewy string indexing counts graphemes; hot scanners borrow byte views. Arbitrary source bytes need the host's unchecked cut. |
| Record construction | Fields with defaults permit Jo's `T()`; otherwise supply every field. Zero-byte defaults rely on the slot's zero fill. |
| Native boundary | `$extern` in either language; raw pointer operations require `$unsafe`. |

The C seed builds generation 1 (`core-bootstrap`) with bootstrap frontends and
no Dewy reader. Generation 1 builds generation 2 (`dewy-core-bootstrap`) with the
full frontend. Both source builds use frozen Jo twins selected by
`tools/compiler/build.py:FROZEN_TWINS`. Generation 2 then builds generation 3
from the Dewy modules; generation 3's self-build must be byte-identical.
Restore bootstrap stubs (frontend, formatter, parser context) with the correct
twins before building generation 2. The reader's twin uses `dewy_reader_seed.jo`.

Every compiler `.dewy` has a frozen twin, imports only the library or other Dewy
leaves, and is explicitly imported by its Jo callers. Change API/layouts in both
twins; never evolve a second parser. `tests/test_selfhost_twins.py` enforces the
inventory, import direction, names and enum ordinals. Differential drivers cover
both build modes; bootstrap, fixed point and `same_output` guard whole-compiler
behavior. A seed cannot consume error unions: host-facing routines return status
records until that boundary moves. It also needs numeric `123` instead of `'{'`.

## Leaves shipped (B3)

All leaf names below are `compiler/*.dewy`; twins are `compiler/*.jo`. “Dewy”
means the normal compiler uses the leaf and bootstrap generations 1–2 use its
twin. Costs are instruction counts from the original cutover, not additive or a
current benchmark; an absent phase measurement is not a claim of zero cost.
`G` means billion instructions; paired counts are Dewy / Jo. Layout-only modules
are grouped. See the ownership sections for the live service contracts.

| Leaf | Frozen twin | Status | Cost / boundary |
|---|---|---|---|
| `zip` | `zip.jo` | Dewy archive writer | Mixed 5.3 MB: 2.065 / 2.065 G; stored 20 MB: 7.527 / 7.527 G. |
| `spelling` | `spelling.jo` | Dewy distance and suggestions | Bounded candidate search; names stay with checker. |
| `leb128` | `leb128.jo` | Dewy shared encoder | One encoder for wasm, DWARF and Mach-O; bounded per word. |
| `base64` | `base64.jo` | Dewy shared encoder | Linear bytes; web and signature callers share it. |
| `line_table` | `line_table.jo` | Dewy state, Jo storage | Word-at-a-time scan; flagship panel within 0.01%. |
| `sha`, `icns` | `sha.jo`, `icns.jo` | Dewy signing/icon leaves | SHA-256: 1.485 / 1.527 G; SHA-1: 0.949 / 1.045 G; mac compiler build −1.5%. |
| `targets` | `targets.jo` | Dewy target queries | Jo retains CLI and host settings; checked slicing remains measurable. |
| `json_doc` | `json_doc.jo` | Dewy parser and writer | 640 KB ×20: 1.398 / 1.568 G; outside flagship panel. |
| `manifest` | `manifest.jo` | Dewy package text | Panel +0.00%; 200-spec parse +35% versus twin; lock parse +1%. |
| `literals` | `literals.jo` | Dewy values, escapes, string chunks | Initial self-build +0.17%; string-chunk cutover lex+parse +0.08%. |
| `dewy_tokens` | `dewy_tokens.jo` | Dewy token layouts and tables | Panel within 0.03%, except enum-table improvement −0.21% on RTOS. |
| `habits` | `habits.jo` | Dewy diagnostic hints | Panel −0.01% to −0.07%; 20k queries 380 / 608 M instructions. |
| `dewy_layout` | `dewy_layout.jo` | Dewy formatter layout | Panel +0.00%; golden-case formatting 1.287 / 1.481 G. |
| `dewy_lex` | `dewy_lex.jo` | Dewy bounded byte scans | Panel ≤+0.06%, lex+parse +0.08%; repository scan ×10: 0.512 / 0.525 G. |
| `module_paths` | `module_paths.jo` | Dewy path/URI text | Panel −0.01% to −0.07%; 14,822 paths ×20: 2.545 / 2.845 G. |
| `dewy_syntax` | `dewy_syntax.jo` | Dewy kind names; old tree retired | No separate syntax-tree construction or projection remains. |
| `dewy_grammar` | `dewy_grammar.jo` | Dewy grammar queries | Panel ≤+0.02%, lex+parse +0.03%; hot caller guards stay inline. |
| `node_store` | `node_store.jo` | Dewy node/layout/list operations | Flagships +0.13%; lex+parse +0.25%, resolve+check +0.29%; borrowed arenas. |
| `intern` | `intern.jo` | Dewy hash/probe/insert | Panel −0.04% to +0.12%; lex+parse −0.04%; new-byte slicing stays Jo. |
| `dewy_lexer` | `dewy_lexer.jo` | Dewy tokenizing loop | O(bytes + amortized interning); presized slots, borrowed tables/host. |
| `dewy_scan` | `dewy_scan.jo` | Dewy bracket/arm scans | O(requested tokens); no whole-file prepass. |
| `dewy_parser` | `dewy_parser.jo` | Dewy context and word cache | Word classification O(1) hit / O(18) miss; report/hint O(1). |
| `dewy_builders` | `dewy_builders.jo` | Dewy pure node construction | Direct node writes; interning/reporting are host services. |
| `dewy_walk` | `dewy_walk.jo` | Dewy collection/kind/copy walks | O(requested subtree); borrow node/list arenas. |
| `dewy_reach` | `dewy_reach.jo` | Dewy member reach/captures | Demand traversal; scope hiding O(scope size × hidden names). |
| `dewy_reader` | `dewy_reader.jo` → `dewy_reader_seed.jo` | Dewy recursive reader | Coarse host services; hot cursor/node fields local. |
| `dewy_reader_state`, `dewy_reader_host`, `dewy_reader_types` | Same stems + `.jo` | Dewy state/service layouts | Shared layouts, no per-entry translated context. |
| `dewy_file` | `dewy_file.jo` | Dewy statement/file lifetime | Temporary result arena; no checker IDs allocated for carriers. |
| `int_domains` | `int_domains.jo` | Dewy write-domain solver | O(log length + demanded writes); 8-delta, 256-value, 64-link limits. |
| `literal_domains` | `literal_domains.jo` | Dewy literal extraction | O(requested subtree), depth-8 conditionals; retain partial output. |
| `text_domains` | `text_domains.jo` | Dewy writes/capture joins | Demand-chain traversal and intermediate result copies. |
| `intervals` | `intervals.jo` | Dewy interval algebra | Linear intersection; coverage O(h² + w*h); gap points sorted. |
| `witness_text` | `witness_text.jo` | Dewy diagnostic text/candidates | Bounded candidates and byte scans; facts-phase cost must be gated. |
| `checker_tokens`, `checker_types`, `refinement_types` | Same stems + `.jo` | Dewy shared checker layouts | Borrow existing records; no translated views or arena relocation. |
| `refine_predicates` | `refine_predicates.jo` | Dewy predicate interning/queries | O(A²*L + P*A*L) interning; linear row queries. |
| `refine_queries` | `refine_queries.jo` | Dewy containment/formals | Requested type occurrences + inference links; depth cap 32. |
| `refine_intervals` | `refine_intervals.jo` | Dewy integer type domains | O(inference links + A log A); retain unsigned upper-half bits. |
| `refine_keys` | `refine_keys.jo` | Dewy finite dictionary keys | Requested edges + emitted keys; reject distances >4096, including wrapped negative spans. |
| `type_queries` | `type_queries.jo` | Dewy equality/occurs-check | O(visited occurrences + inference links); hot root guards stay Jo. |
| `checker_services`, `refine_strings` | `checker_services.jo`, `refine_strings.jo` | Dewy interning interface, set publication/constants | O(S*M²) search; one host call per new member/constant; peak flagship phase +0.115%. |
| `refine_storage` | `refine_storage.jo` | Dewy storage-contract traversal | O(V * D), D≤32; private ancestor stack, unresolved-record callbacks; peak flagship phase +0.054%. |
| `refine_projection` | `refine_projection.jo` | Dewy projection validation | O(path + scanned field runs + inference links); lazy fields, dialect/runtime request and first-error status. |
| `checker_state` | `checker_state.jo` | Dewy local/global/function/context, scope and binder layouts | Stable IDs/ABI; Jo writers borrow the same storage; flagship phase cost ≤+0.163%. |
| `refine_resolve`, `refine_resolve_host` | Same stems + `.jo` | Dewy recursive terms/predicates, typed semantic requests | Demand traversal and existing budgets; resolver increment ≤0.072%, state+resolver peak phase +0.234%. |
| `evaluator_state` | `evaluator_state.jo` | Dewy immutable value, frame, place and scalar-result layouts | Stable IDs/ABI; Jo writers share storage; peak flagship phase +0.0001%. |
| `constant_eval`, `constant_host`, `source_types` | Same stems + `.jo` | Dewy recursive constant-expression evaluation and borrowed source dialects | O(executed syntax + demanded checking/binding); local scalar operations; peak flagship phase +0.103% including layouts. |
| `ir_types` | `ir_types.jo` | Dewy opcode and instruction/function/use-plan layouts | 107 ordinals, 30 fields; direct Jo consumers, no adapters; flagship phase change −0.0037% to +0.0030%. |
| `ir_operands` | `ir_operands.jo` | Dewy final-IR layout construction and flags | O(opcodes) once per process; Jo consumes the table directly; flagship phase change −0.0001% to +0.0005%. |

### Boundary lessons that constrain the next cutover

Borrow arena headers by place; preserve layouts, IDs and enum ordinals. Direct
field reads avoid allocating translated records. A local copy of a dictionary
or array may force copy-on-write on its next mutation. Taking `.ptr` from an
array passed by value copied the array on every lookup (235k instructions);
retaining/releasing a name from a borrowed string array cost about 20 instructions
per lookup. Cache scalar fields locally, but reacquire element pointers after
anything that can grow their arena. Complete a host call before using a borrowed
dictionary as a receiver, avoiding a defensive snapshot around that call.

Construct noncapturing service records once and lend them by place or pointer.
Copying them per identifier can cost more than the scan. Keep hashing and probes
inside a hot lexer; a whole-string callback is appropriate for cold publication.
Each call layer counts: nested hashing under a wrapper cost lex+parse +1.40%,
inlining the wrapper +0.42%, and hashing at the caller +0.01%. Even a short early
return can save all five callee-saved registers. String-chunk calls cost about
70 instructions more than the old inline loop; constructors about 10 per node.

Keep hot guards and field access inline. A byte-load helper missed inlining and
cost +6%; repeated unshared rotate expressions cost +19%. Machine-width offsets
matter: exact `i + 8 < n` cost about 14 instructions per hash word versus one
for `i < n - 8`; checked `(i + 1) & mask` cost about 20 per probe. Policy-typed
operands mixed with ordinary literals can cost about 30 instructions instead of
one. Fixed-size schedules and one doubled word per rotation made SHA viable;
the naive two-shift SHA-256 port cost +51%. Gate generated code, not source size.

Arbitrary bytes remain a boundary requirement: names can contain malformed UTF-8
and NUL. Dewy's checked byte slices/conversions cannot manufacture those strings;
Jo cuts new names, and byte-oriented leaves retain bytes. A proven ten-byte
`byte_slice` still cost 430 versus 355 instructions (release 335 versus 275).
A manual manifest scan cost 9.2 instructions/byte versus library `find`'s 2.4.
Do not replace a cheap library scan or host cut merely to move a line of code.

Rejected cutovers are closed pilot families, not a backlog of tiny optimizations:

| Rejected boundary | Measured cost |
|---|---|
| Whole name-store adapter | Lex+parse +0.382%. |
| Scalar metadata accessors | Facts +0.55%. |
| Standalone string-set renderer | +2.83%. |
| Node field/flag one-liners as leaf calls | Panel +0.80%; resolve+check +2.37%. |
| Per-node syntax unwrap | Lex+parse +0.85%; crypto flagship +0.30%. |
| Unconditional juxtaposition helper | Synthetic-22k parse +0.9%. |
| Name comparison byte pool | 15 instructions saved/hit, 190 added/new name; flagships +0.25%. |
| Split every path stem for malformed-byte safety | Hello +0.73%; lex+parse +0.70%; split only after non-ASCII. |
| Lexer with post-scan interning and pushed records | +11%; direct slot filling and in-loop lookup replace it. |
| Checked-body evaluator through a borrowed arena context | Resolve+check +0.345% to +0.429%; retain Jo execution. |

## Checker ownership and service cutovers

The final Dewy checker owns compilation-lifetime arenas (types, structures,
fields, variants, locals, globals, function instances and declarations), indexed
name/symbol lookup, a stack of active function contexts, and refinement state.
Keep IDs and record layouts stable while moving their definitions and users.
During transition, Jo owns the actual globals and lends their places to Dewy;
a record definition moving languages does not require moving its storage. Do
not translate records, duplicate tables, or copy a context into every query.
Move each arena into a Dewy-owned context only when its writers can share that
context without a hot Jo accessor at every read. Node and intern stores have
compilation lifetime and remain shared services of the parser and checker.

Separate persistent state from nested work. Locals and function instances keep
stable IDs; resolving one function may append another. Save the active context
index, scope mark and the particular refinement binders changed by a nested
operation, then restore them on exit. Never restore a whole arena: declarations,
instances, interned names and checked results created during that operation must
survive. Scopes retain `sc_top[name]`, `sc_prev`, `sc_names` and `sc_syms`: lookup
is O(1), pushing is amortized O(1), and resetting costs the bindings removed.
The function-instance index and module lookup invalidation remain with their
writers. Lowering borrows completed checker records; facts/effects retain their
own state until their separate cutovers.

Evaluation owns its immutable value arena, frames, places, call stack, global
cache and pending calls. Keep it separate from the checker's active function
stack, but in the same compilation lifetime. `ceval` may check an untyped node
and force a body before evaluating it; it is not a pure query. A service request
must therefore return an ID or the exact scalar result, with the caller rereading
node/type fields after it returns. Do not retain element pointers or dictionary
receivers across a callback that can grow their owner. The eventual evaluator
cutover moves its recursive group together, leaving coarse requests for checking
an expression or forcing a body until those checker groups move too.

Services are narrow, typed, noncapturing functions in a record initialized once
by the Jo owner and borrowed by place. Interning accepts a whole existing string
and returns its stable ID, preserving arbitrary bytes and the empty-name sentinel;
it does not enter checking. Parser byte-span lookup still hashes and probes in
its loop and asks Jo only to cut a missing arbitrary-byte name. Do not route
ordinary lexer identifiers through the checker's whole-string service. Resetting
the name store invalidates every name-indexed cache at the same owner boundary.

Lazy field resolution is explicitly reentrant: `check_struct_fields` can resolve
types, check defaults, enter nested function scopes and validate refinements.
Keep its resolved-before-recursion marker and scope/context save/restore with the
resolver. `refine_storage.dewy` borrows `CheckerFieldsHost`, calls it only for an
unresolved record, then rereads the field run. It lends arena *headers*, not
cached element pointers, and keeps its ancestor stack private to that invocation.
Nested validation may enter a fresh walker; it must not clear an outer walk's
stack or snapshot the checker. No callback per already-resolved field is needed.
`refine_projection.dewy` shares that resolver and borrows `CheckerProjectionHost`
only for string-length dialect/runtime requests. It returns the first diagnostic
as a seed-compatible status; Jo retains reporting. Its path remains a value
snapshot, while all arena headers are borrowed across reentrant calls.

`refine_strings.dewy` owns string-set construction/publication and checked member
constants. Its `CheckerInternHost` borrows whole-string interning; the set, type,
structure, variant and node arenas stay with Jo, with the current field count
passed as a scalar. Preserve first-spelled member order, type identity and name-ID
assignment. A cache hit performs no host calls; a new set calls interning once
per member. The existing membership search costs O(S * M²) string comparisons
for S sets of M members, plus text bytes and M arena appends on a miss. A checked
member constant costs one node append and one interning call, with direct field
writes. Keep the frequently used diagnostic renderer in Jo; text for a newly
published structure is built inside the coarse publication operation.

`checker_state.dewy` defines locals, globals, function instances/signatures,
active contexts, the indexed scope stack and refinement binders. Jo writers keep
storage and direct hot reads; nested work restores only changed binder fields.
Symbols and module invalidation stay with their writers. The internal function
flag is `parallel_api`, preserving its ABI slot without a Dewy keyword field.
`refine_resolve.dewy` owns recursive terms and predicates. It borrows node/type/name
headers and binders, retaining direct scalar/literal paths. Its noncapturing host
handles lexical lookup plus constant checking/evaluation, type limits and fatal
diagnostics. These requests may grow arenas or enter a nested resolver; the
caller rereads by ID. Cost is O(visited syntax + emitted atoms), apart from
requested binder/name lookup and semantic work; existing depth/atom budgets stay.
Scope lookup remains O(1), rollback proportional to bindings removed.

`constant_eval.dewy` owns unchecked constant-expression recursion; its host checks
expressions and resolves bindings. Value/frame/place layouts are shared in Dewy,
while the checked execution group stays Jo after its boundary exceeded the budget.
Cost follows executed work, existing immutable-value copies and call-frame depth;
there is no whole-source scan or new fuel limit. A scalar evaluated operation
must not acquire a callback; checking requests may grow shared arenas, so
reacquire elements afterwards. Preserve pending/global caches and restore only
the active evaluation frame and call stack on nested entry.

Each cutover must fit ±0.3% of every flagship phase row, not merely the aggregate
compile. The boundary budget includes reference counting, checked narrowing,
record construction and service dispatch. Prior small adapters exceeded it:
name-store wrapping added 0.382% to lex+parse; scalar metadata added 0.55% to
facts; a separate string-set renderer added 2.83%. Borrowed arenas and direct
field reads avoid those copied-record and per-scalar-call costs. Measure the
coarse cutover before extending it; a service is not permission to reintroduce
those adapters. Every new leaf and service layout has a frozen Jo twin and
independent differential coverage, then bootstrap and fixed-point validation.

## Route beyond the checker

Planning baseline: `3449ea6a1`; physical lines including comments/blanks, excluding
frozen twins and `dewy_reader_seed.jo`. Counts describe migration scope, not
progress. Compiler remainder: 100,194 Jo lines; library: 50,922 in 98 files.

| Remaining subsystem | Jo lines / scope | Dependencies, exposure and boundary risk |
|---|---|---|
| Checker and evaluation | 30,711: `check`, `expr`, `types`, `refine`, `check_constant`, `comptime`, `math_comptime`, decimal/float/unit/temperature rules, juxtaposition, Dewy methods/nodes, places/methods/split, poly closures, sibling types, reflection, prelude | Recursive checker/AST/name/source arenas and lazy reader; hot per expression. High: callbacks can reenter and grow arenas; checked evaluator adapter already failed. |
| Facts/effects and safety | 19,082: `facts`, `effects`, `effect_library`, definite, deadlock, concurrency, isolation, ownership, safe paths, secrets, partition, proofs, witness, string domains, warn-if, pcheck, member replay | Checked bodies/types, refinement and call graph. Hot repeated walks; high: per-node adapters or copied fact dictionaries exceed budget. Coordinate edits before choosing these files. |
| Lowering, IR and generated runtime | 12,240: `lower`, `ir`, `arena`, `math_lower`, `member_lowering`, `parallel_lower`, `draw_context`, `oom`, `ffi` | Checker, safety results, target settings and IR; hot every emitted instruction. High for builder calls; low for shared layouts. Move recursive lowering groups with their scratch state. |
| Optimizer | 8,333: `opt`, `inline`, `loops`, `fused`, `exact`, `exact_guards`, `exact_loop`, `growth`, `copies`, `callback_specialize`, `loop_ordered`, `scanloops` | IR plus some checker/type and lowering metadata. Hot per instruction/pass; high if operands become callbacks. Cut complete function passes, borrowing code/args and indexed tables. |
| x64 | 4,568: `x64`, `x64_ordered` | IR, lowering symbols, types, object output; also exports shared native analysis. Very hot instruction selection and register allocation; high: isolate shared analysis before moving emitters. |
| arm64 | 1,594: `arm64` | IR, x64 shared analysis, lowering and ELF. Hot emission; medium/high: borrow allocator/relocation state once per function. |
| wasm | 1,119: `wasm` | IR, lowering/checker symbols, x64 shared state, LEB128 and packaging leaves. Hot instruction encoding; medium: whole-function encoder, not per-byte host requests. |
| GPU | 4,064: `glsl`, `msl`, `spirv` | Checked AST/types, lowered functions and target libraries. Workload-specific hot paths; high if AST lookup becomes a service. |
| Object/debug writers | 2,835: ELF, Mach-O, PE, DWARF, PDB | Backend code/relocations, names and source positions. Bulk bytes plus per-instruction debug rows; medium: borrow output buffers and line tables. |
| Frontends and parser hosts | 5,919: AST, Jo lex/parse/scan, frontend, Dewy context/direct/directives/fast/FFI/fmt/reader services, lazy bodies, directives | Source/module loading, shared nodes and Dewy reader. Jo parser remains needed for unmigrated modules and bootstrap. High for byte cuts; cold directive services can move together. |
| Driver and tools | 9,729: main, settings, util, errors, icount, fmt, ide, lsp, pkg, repl, watch, new, par | All phases, OS/process/files, source management and editor protocols. Mostly cold orchestration; medium for source/name helpers and diagnostic formatting. |
| Runtime/library | 50,922: recursive `lib/**/*.jo` (core/std/game and top-level libraries/templates) | OS/FFI, allocator, strings/arrays/maps, tasks and graphics. Compiler-used core/std first; other libraries are separate from compiler-source completion. High for allocation/refcount/byte primitives; port whole operations preserving unchecked host byte semantics. |

Order: establish the backend-independent IR boundary, move complete IR passes,
then shared backend analysis and whole-function emitters (wasm, arm64, x64),
followed by object/debug writers. In parallel in the work queue, move checker
recursive groups and safety passes with their state; lowering follows their
stable borrowed records. Finish source/module services, driver/tool entry points
and compiler-used runtime/library modules. GPU and other library ports can follow
without blocking a compiler built from Dewy sources. Retain a Jo compatibility
frontend only if still required for user/library inputs; it can itself be Dewy.
The checked evaluator joins its checker owners rather than retrying the rejected
borrowed-context adapter unchanged.

First three cutovers in this sequence (cost estimates unless marked shipped):

1. **IR schema (shipped):** `Op`, `Ins`, `IrFn`, `IrUsePlan` into `ir_types.dewy` with
   a frozen twin. Keep globals, constants, builders and all hot consumers in
   place. No algorithm or new traversal; measured phase cost −0.0037% to +0.0030%,
   with ordinal/layout/default and mutation differential tests.
2. **Final-IR operand description (shipped):** `ir_operands.dewy` owns layout-table
   construction and flags; Jo keeps storage and direct indexed consumption.
   O(opcodes) once per process, no per-instruction callback. An explicit ABI-order
   opcode list avoids numeric conversion of Dewy string unions. Differential
   tests compare all 107 slots and exceptional operand forms with the frozen
   constructor and independent optimizer walker, in default and release modes.
3. **IR cleanup pass:** `opt_rewrite.dewy` owns the mutually dependent forward
   rewrite, constant folding, strength reduction, CSE, scoped facts and DCE;
   `opt_cleanup.dewy` owns final control compaction, diamonds and retargeting.
   `opt_workspace.dewy` owns their indexed scratch tables. The remaining
   optimizer passes keep their current order and direct shared-table access.
   Budget ±0.3% per flagship phase; measure the whole group before extending
   the cutover to SRA, loop transforms or return sinking.

All three retain the ±0.3% limit on *each* flagship phase row. Schema migration
unblocks direct Dewy IR consumers but does not claim the lowering/optimizer code
has moved. Do not use aggregate speed to hide a phase regression.

No frozen twin is removable under the current C → Jo generation 1 → generation 2
chain: both source builds deliberately select all reachable twins. Once a trusted
Dewy-capable bootstrap replaces that dependency (or the C seed reads these Dewy
sources), pure leaves, shared layouts and then recursive reader/resolver/constant
leaves can lose their twins together with the corresponding `FROZEN_TWINS`
entries. The special reader seed and frontend/context stubs retire with that
chain. Preserve independent bootstrap and fixed-point checks; deleting twins
alone is not self-hosting progress.

## Optimizer ownership boundary

The rewrite/cleanup group has one non-reentrant workspace, preserving the
existing optimizer lifetime. Its independent globals preserve alias information
between scalar updates and arena views. Jo's coarse `optimize` entry runs SRA, binds the
current `IrFn`, opcode tables, target policies and constant-cache views, then
enters Dewy. Its bounded SRA retry happens after Dewy returns. No instruction,
operand, folding or metadata operation calls back into Jo. Jo sibling passes
retain their direct rewrite/register-reset helpers and share the same register
table; those helpers are not adapters on the Dewy execution path.

`opt_ir` borrows the original function for the complete call. Input code stays
stable until final publication; output uses a separate arena. Every arena grow
refreshes its raw pointer, and no register-entry pointer survives a helper that
can create a virtual register. Two instruction slots suffice: the outer forward
transfer uses slot zero, and strength reduction uses slot one with simplification
disabled. The operand view is transient: consume it before decoding another
instruction, and decode DCE operands before replacing the instruction with nop.
Raw opcode ordinals follow `ir_types` exactly; exhaustive descriptor tests compare
them with the independent Jo walker.

The metadata, forward and backward walks remain O(N + U + E), for input
operations, operand uses and emitted operations, plus existing CSE hash probes
and demanded queries. Copy-lifetime scans stop after 4,000 instructions; scalar
range queries follow at most four definition edges. Cleanup retains its existing
diamond/wrapper and sole-slot scans, including their possible quadratic total
cost; no unconditional analysis or extra sweep is introduced. Arithmetic uses
fixed-width wrapping words and signed truncation to preserve Jo's folding rules,
including minimum-integer negation and the zero/minimum division guards.

The frozen workspace, rewrite and cleanup twins remain required by both Jo
bootstrap generations. Their retirement follows the Dewy-capable bootstrap
route above; execution ownership alone does not remove that dependency.

## Parser ownership boundary

The reference expression/statement readers, projection and `DewySyntax` carrier
are retired. `dewy_lexer`, `dewy_reader` and `dewy_file` own tokenization, the
recursive expression/type/body/statement group, and the file loop. Jo prepares
source/lexer tables and completes recursive directive-bundle loading before
entering the file loop; it retains effectful settings, C declarations,
proof/task registration, source-byte access and fatal diagnostics as services.
Parser services never enter a reader. String scanning and lexing are services,
not recursive readers. Ordinary atoms map names through Dewy builders directly.

`ParserContext` owns tokens, cursor, file, depth, flags, diagnostics, word cache,
collection/reach state, token edits and lazy-body tables. Jo lends one context;
node/list and intern stores remain shared places. Save only the state a nested
operation changes:

- Interpolation restores tokens, cursor and comma state.
- Speculative reads restore cursor, node/list/module-result marks, diagnostic
  positions/counts and edits. A failed reading retains its first-report text.
- Statement entry clears the hint position. First parse/projection diagnostics
  retain their original timing; unread forms use the first applicable hint.
- Lazy forcing restores file/depth/flags and applies its recorded edits.
- Persistent caches and already-published results are never wholesale reset.

`dewy_context.jo` shares storage without pulling the reader driver into bootstrap
consumers. The C seed uses a capture-table-only stub; generation 2 restores the
full frozen context. Collection and reach own scopes, waiting names and captures;
member-effect checking reads the same capture table. The inherited-name cache is
interned lazily on first use and cleared with the word cache when names reset.
Keep owned scope snapshots on block paths, not on every scalar visit.

The lexer fills presized slots and refreshes their pointer after growth. Its host
handles missing names, non-ASCII canonicalization, arbitrary-byte cuts and first
diagnostics; ordinary identifiers hash/probe directly. Preserve wrapping 32-bit
token-name conversion and machine-width offsets. Reader loops likewise keep hot
cursors and token/node fields local; Jo enters at coarse body/file boundaries.

File statements return checker-node IDs. Temporary directives/groups use `Node`
records in a separate arena, negative result IDs and their own list runs. They
allocate neither checker IDs nor names, preserving generated names/debug bytes.
Groups retain statement-head offsets; the driver releases temporary results after
each module statement. Gate extensions on first diagnostics, rollback, interpolation,
lazy forcing and byte identity, plus ±0.3% lex+parse on every flagship.

## Decided rules

Moved here from the decisions ledger ([decisions.md](decisions.md)), which keeps
a pointer to each rule. The wording is David's.

### FFI (Q12/Q24)

- FFI (Q12/Q24): `$extern` is a body-position metatag with optional keyword
  arguments (`=> $extern`, `=> $extern(name='Sleep' lib='kernel32')`). It
  replaces the `extern` keyword, which is un-reserved. `$export` (provisional)
  makes a function callable from C, Rust and Python. Calling `$extern` or
  dereferencing a raw `ptr<T>` (provisional; `ptr<T>?` nullable) needs an
  unsafe boundary. The goal is batteries-included Dewy with seamless,
  bidirectional FFI (C, C++, Rust, Python, JS/wasm); header bindgen comes
  later. A blocking-style `net` module returns `| NetError | Canceled`, over
  FFI for now.
- C interop: `$export` may share the line with its definition (a metatag
  applies to the next thing). `$unsafe` applies to the next expression, on the
  same line or the next (`$unsafe strlen(msg.ptr)`); several expressions use
  `$unsafe { ... }`. This replaces the provisional "own line, rest of the
  block" form.

### `$target` and `$build`

- `$target` keeps its spelling. Canonical names with only the fields they need
  (`x86_64`, `aarch64-linux`, `riscv64-freestanding`, `c-linux`, `aarch64-mac`,
  `x86_64-windows`, `wasm32`, …; not LLVM triples), per the archived
  status.md list. OS and arch are selected by compile-time conditions on
  `$target`.
- `$build`: a compile-time record like `$target` (`$build.mode =? 'release'`;
  `$build.debug` was removed 2026-10-23). Project flags (e.g. BOOTSTRAP) are ordinary consts in a build
  module the entry module overrides; no CLI `-D` flags.
- `$build` and `$target` (decided 2026-10-23): namespaces with members (a
  deliberate exception for build facets). Statement position sets, expression
  position checks, as for every metatag: `$build.mode = 'release'`,
  `$target = 'aarch64-linux'`, `if $build.mode =? 'debug' {...}`,
  `if $target.os =? 'windows' {...}`. Boolean members take the bare form for
  true and `=false`. One member per fact: `$build.mode` is `'debug'` (the
  default, what plain `dewy FILE` builds) or `'release'`; `$build.debug` is
  removed. The file is the preferred place to set them; command-line flags
  (`--release`/`--debug`, `--target …`) override the file, and an override that
  contradicts a value set explicitly in the file builds with a warning naming
  both. Only build mode and target can be overridden from the command line;
  safety and semantic metatags (`$runtime_checks`, `$no_hidden_costs`,
  `$bulletproof`, …) are never settable from the command line.
