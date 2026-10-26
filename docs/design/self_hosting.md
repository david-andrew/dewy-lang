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
resolver. A Dewy storage walker calls the service only for an unresolved record,
then rereads the field run from the shared arena. It lends arena *headers*, not
cached element pointers, and keeps its ancestor stack private to that invocation.
Nested validation may enter a fresh walker; it must not clear an outer walk's
stack or snapshot the checker. No callback per already-resolved field is needed.

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

The next three cutovers, in dependency order, are:

1. Lazy field service and storage-contract traversal, followed by projection
   validation once its type/error services are available. Storage walks retain
   O(V * D) ancestor checks and O(D) space, D capped at 32, and resolve each record
   at most once through its existing marker. Projection costs its path plus the
   scanned field runs; resolution's checking cost belongs to the resolver, not
   a hidden prepass. Callback count is unresolved records, never visited fields.
2. Checker local/function/scope layouts and refinement binders, then the recursive
   term/predicate resolver with typed lookup, type-resolution, diagnostic and
   evaluation requests. Borrow indexed state and keep direct scalar/literal paths
   in the recursive group; only terms needing semantic work call the host. Retain
   the existing depth/atom budgets, O(visited syntax + emitted atoms) apart from
   demanded lookup/type resolution/evaluation. Scope lookup stays O(1); rollback
   costs only popped bindings. Moving definitions must add no record translation
   or new analysis pass.
3. Evaluation's value/frame/place layouts and its recursive execution group.
   Keep checker entry at coarse expression/body forcing boundaries, then remove
   those host edges as the corresponding checker groups move. Cost follows the
   executed program, its existing immutable-value copies and call-frame depth;
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
