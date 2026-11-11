# Assumption opt-outs: examples and calls for David

- **Recommend a namespace for library trust:** `$library.require_asserts`, `.require_checks`, `.require_memory`, `.require_drop_hooks`. Each bare member enables one obligation; `=false` disables it, subject to the enclosing bundle's existing contradiction rule. Keep the four obligations independently selectable.
- **Keep failure values separate from effects.** `panics` describes a possible exit; adding it does not turn that exit into a recoverable error. Do not invent one catch-all `RuntimeFailure` value.
- **Do not approve `$explicit_runtime_failure` as currently described.** It conflates shape/OOM handling, runtime correctness and unresolved stack exhaustion. Keep `$explicit_allocation_failure`; specify the remaining runtime obligations before naming their switch.
- **Make environmental refusal return ordinary error alternatives.** For input, distinguish EOF, I/O failure and cancellation. A strict caller cannot prove that stdin will supply another number.
- **Recommend `$no_assumed_finite_inputs` → `$prove_finite_inputs`** and `$verify_certified_protocols` → `$verify_protocols`. Both are useful independently of `$bulletproof`.
- **Recommend errors for unconfined paths in `$bulletproof`,** while preserving today's warning outside that bundle. This is lexical confinement, not protection against symlinks.
- **Reject unsupported audited waits in the proof-demanding configuration; remove range truncation there.** Accept checked adapters/protocols and range-size proofs instead. Scheduler fairness, terminating local work and cooperative external peers remain explicit theorem premises.
- **Scope/budget:** one read-only design pass; only this scratch document is owned. No implementation, repository edits, commits or new proof language. All spellings and diagnostics below are proposals for approval, not implemented behavior.

## Reading the examples

- Row numbers follow the table in [assumptions.md](/docs/design/assumptions.md). Authority: [no traps](/docs/design/no_traps.md), [effects](/docs/design/effects.md), [resources](/docs/design/resource_exhaustion.md), [decisions](/docs/design/decisions.md), and the earlier [review](docs/design/proposals/bulletproof/report.md).
- **In each first code block, remove the proposed directive to get today's accepted fragment.** Other directives shown are existing syntax. Diagnostics labelled **Proposed** are exact suggested wording, not captured compiler output. Repairs use current expression/type syntax; new APIs or proof infrastructure are identified explicitly.
- These examples isolate individual obligations. Combining them with `$bulletproof` adds its other allocation, copying, float and wait requirements. A repair of one site does not certify the whole runtime.
- Syntax check: 18 standalone blocks passed the existing compiler with proposed directives removed; the confinement warning was expected. The two contextual insertions were inspected. No proposed proof mechanism or diagnostic was executed.

## 1. `$no_trusted_library_asserts`

- **Trust today — row 3:** library `assert`/`unreachable` state invariants and do not contribute `panics`.
- **Example:** collecting a UI label's graphemes reaches the library's assertion that its UTF-8 decoder found a valid boundary.

```dewy
$no_trusted_library_asserts
labels = (text:string):>array<string> => graphemes(text)
```

- **Proposed:** `error: labels -> graphemes: cannot prove library assertion 'next_byte >= 0'; validate UTF-8 before this call`. Point to the assertion in `lib/std/graphemes.jo` and the caller.
- **Programmer writes:** validate foreign bytes, handle malformed input, then collect.

```dewy
labels = (bytes:array<uint8>):>array<string> | none => {
    let text = bytes as string | none
    if text is? none return none
    graphemes(text)
}
```

- **Necessary library work:** the decoder must establish a checked UTF-8 invariant that `graphemes` preserves. Today's validation works at runtime, but the cross-function invariant proof is not implemented. Merely replacing `assert` with `$assert` does not manufacture a proof. Unprovable internal `unreachable` sites need the same treatment.
- **Users:** foreign-data processing, security and certification; useful alone, not only in `$bulletproof`.
- **Name/recommendation:** use `$library.require_asserts`. It means **prove assertions**, not ban assertion syntax. Keep it separate from checks: this removes an invariant axiom, whereas tag 4 removes an implicit-check policy exemption.

## 2. `$explicit_runtime_failure`

- **Trust today — row 4:** oversized shapes/OOM and the runtime core are environmental, outside `panics`.
- **Example:** image dimensions are nonnegative, but their product can exceed int64 or available memory.

```dewy
$explicit_runtime_failure
grid = (rows:int64<(>=? 0)> cols:int64<(>=? 0)>):>NDArray<float64> =>
    zeros(rows cols)
```

- **Already available:** `$explicit_allocation_failure` adds `OutOfMemory` to allocating functions; `__nd_count` routes shape-product overflow to that same failure. That covers this failure category, not every runtime-core assumption. WebAssembly currently still terminates on allocation refusal.
- **Proposed for the extra core requirement:** `error: grid -> zeros -> __alloc_z: runtime memory-safety and failure contract has not been verified`. Adding `OutOfMemory` cannot discharge a missing correctness proof.
- **Programmer writes:** bound admitted dimensions and expose allocation refusal. This is current syntax and the application side of the repair:

```dewy
$explicit_allocation_failure
grid = (rows:int64 cols:int64):>NDArray<float64> | OutOfMemory | none => {
    if rows <? 0 or cols <? 0 or rows >? 1024 or cols >? 1024 return none
    zeros(rows cols)
}
```

- **Remaining repair:** use a runtime whose allocator/shape implementation has checked contracts. There is no existing user annotation that proves the whole core. Bounded dimensions also do not prove that stack capacity is available.
- **Users:** embedded systems, recoverable services and certification; useful independently of `$bulletproof`.
- **Name/recommendation:** reject this umbrella name for now. Keep the existing allocation switch; use a separate, precisely scoped proof member such as `$runtime.require_proofs` only after defining coverage. Stack exhaustion remains an open resource-design question, not a new union alternative decided by this note.

## 3. `$explicit_environment_failure`

- **Trust today — row 5:** library `__environment_failure` may terminate when input, drivers or the test-runner environment refuse service.
- **Example:** EOF before a number currently terminates, despite a no-runtime-check caller.

```dewy
$explicit_environment_failure
main = ():>void | Canceled => {
    let n = input_int("count? ") or_throw
    printl(n)
}
```

- **Proposed API result:** `input_int` returns `int | EndOfInput | FileError | Canceled`; `EndOfInput` is a **proposed new error type**. Invalid numeric lines can retain the existing retry behavior. `input_float` gets the analogous result. The shown caller must add `EndOfInput | FileError` to its declared result, or handle them locally.
- **Current-API repair:** choose `read_line`, which already returns EOF and I/O failure, then parse explicitly:

```dewy
read_count = ():>int | none | FileError | Canceled | NotAnInteger | TooManyDigits => {
    let line = read_line() or_throw
    to_int(line)
}
```

- Callers handle `none` as EOF and the named errors, or translate them into application errors. `or_throw` forwards values by returning; it is not exception unwinding.
- **Users:** unattended services, command-line tools, driver recovery and tests; valuable without `$bulletproof`.
- **Name/recommendation:** the original name is understandable; retain it provisionally. Prefer specific library errors over one `EnvironmentFailure` bucket. Drivers/pipes need corresponding API changes; no switch can make every environment failure recoverable without a failure path.

## 4. `$no_implicit_library_checks`

- **Trust today — row 6:** library obligations keep implicit runtime checks even when user code requires static proof.
- **Example:** counting UI graphemes reaches `__grapheme_page_lookup`, whose packed-table indexing uses the library's implicit-check policy.

```dewy
$no_implicit_library_checks
label_size = (text:string):>int64 => text.length
```

- **Proposed, if the table invariant lacks a proof:** `error: label_size -> __grapheme_page_lookup: cannot prove packed-table index is in bounds; implicit library checks are disabled`. Point to `table[8704 + page * 256 + (scalar & 255)]` in `lib/std/graphemes.jo`.
- **Library author writes:** an explicit failure-returning read, rather than a hidden bounds exit:

```dewy
table_byte = (table:array<uint8> index:int64):>uint8 | none => {
    if index <? 0 or index >=? table.length return none
    table[index]
}
```

- The library must propagate/handle `none` explicitly; preserving the existing `text.length` signature instead requires proving the shipped table's layout and page bounds. For that preferred repair, the application keeps `label_size` unchanged against the verified library. A caller guard on the text's length cannot establish an internal table invariant.
- **Users:** timing-sensitive embedded kernels and certification; useful alone. Outside a static policy, the opt-out should still follow the scope's explicit runtime-check policy, as `$no_assumed_bounds` does.
- **Name/recommendation:** `$library.require_checks` in the shared namespace; document it as “require check obligations to follow the caller's policy.” It does not mean every possible returned failure needs static elimination.

## 5. `$no_trusted_library_memory`

- **Trust today — row 7:** bundled-library raw-memory code is assumed not to retain arena storage past its lifetime.
- **Example:** output inside a scratch allocation passes arena-owned storage into trusted library machinery.

```dewy
$no_trusted_library_memory
main = ():>void => {
    let scratch = Arena[]
    let count = $allocator(@scratch) {
        let xs:array<int64> = [1 2 3]
        printl(xs)
        xs.length
    }
    scratch.reset()
    printl(count)
}
```

- **Proposed:** `error: printl: library raw-memory call has no checked non-retention contract for arena storage; move this call outside the allocator expression or use a verified implementation`.
- **Programmer writes:** remove the inner `printl(xs)`; report the scalar `count` after the expression, as shown. If all values must be reported, return them from the expression and print the promoted copy afterward; explicit-copy policy may require `.copy()`.
- **Necessary library work:** the arena allocator's own memory primitives also need checked provenance/lifetime contracts. Moving output repairs the output edge; it does not verify the allocator. Foreign calls can retain pointers, so an unchecked “does not retain” annotation would simply recreate this assumption.
- **Users:** arena-heavy servers, embedded systems and security audits; useful outside `$bulletproof`.
- **Name/recommendation:** `$library.require_memory`; specify the present scope as arena escape/non-retention. Do not advertise it as a complete proof of all memory safety. Share checked primitive contracts with the runtime work in tag 2.

## 6. `$check_library_drop_hooks`

- **Trust today — row 8:** the library's drop hooks, such as a lock guard's word release, are assumed unable to fail.
- **Example:** releasing the place implicitly drops the hidden `__Held` guard.

```dewy
$check_library_drop_hooks
bump = (m:Mutex<int64>):>void => {
    let value = @(m.lock())
    value += 1
}
```

- **Proposed:** `error: implicit drop of __Held -> release -> __lock_release_word: no proven no-failure summary`. Point to the last use and the library hook, including early exits that run it.
- **Programmer/library author writes:** keep `bump` unchanged and supply a verified library release implementation. The hook's existing syntax can state part of its contract:

```dewy
# Inside the library's __Held declaration; contract addition is proposed.
$__drop__
release = ():>void & no allocates & no panics => __lock_release_word(word)
```

- That declaration must be checked against the raw-word primitive; it is not an assertion the checker may trust. The full existing hook verifier also excludes opaque behavior, spawning, detachment, escaping storage and unresolved effects. The hook has no caller error-return channel: adding `ReleaseFailed` to `bump` cannot fix implicit cleanup.
- **Users:** concurrent services and certification, including code without `$bulletproof`. Lock-order proof and no-failure cleanup proof are separate obligations.
- **Name/recommendation:** `$library.require_drop_hooks`. “Check” undersells the required proof; retain this independent member because cleanup has stronger constraints than ordinary calls.

## 7. `$no_assumed_finite_inputs`

- **Trust today — row 11:** `$no_inf` assumes incoming parameters, fields, elements and call results are finite; `$no_nan` already demands incoming-value evidence.
- **Example:** forwarding a parsed measurement can admit infinity without performing any arithmetic.

```dewy
$no_inf

$no_assumed_finite_inputs
same = (x:float64):>float64 => {
    x
}
main = ():>void => { same(to_float("1.5") ?? 0.0); }
```

- **Proposed:** `error: argument x to same is not proven finite under $no_inf; guard the incoming value before the call`. The missing fact is about the parser's result, even though this particular string is finite.
- **Programmer writes:** validate at the boundary, outside the finite-only scope:

```dewy
accept = (x:float64):>float64 => {
    if -1e300 <? x <? 1e300 return same(x)
    0.0
}
```

- Here `same` keeps the two tags inside its body; `accept` is outside their scope. The guard rejects NaN and both infinities and deliberately limits magnitude. A recognized `is_finite(x)` guard would accept every finite float, but its proof recognition must be implemented; the function merely existing is not enough.
- **Users:** numerical code, telemetry, financial calculations and embedded control; meaningful alongside `$no_inf`, not only in `$bulletproof`. Arithmetic inside the scope still needs its own overflow proof.
- **Name/recommendation:** `$prove_finite_inputs`; extend the existing `$no_nan` entry-obligation mechanism. No new finite-number type is required for this pilot.

## 8. `$verify_certified_protocols`

- **Trust today — row 14:** `$no_deadlocks` accepts `serve`/`pipeline` protocol implementations on the library's claim about their waits.
- **Example:** a service call and a bounded feedback pipeline are accepted today:

```dewy
$no_deadlocks
$verify_certified_protocols
square = (n:int):>int => n*n
main = ():>void | Closed | Canceled => {
    let total = serve(@square (s:Service<int int>):>int | Closed | Canceled =>
        s.request(3)) or_throw
    let seeds:array<int> = [6]
    let path = pipeline(2 seeds (n:int):>int => n+1
        (r:int):>array<int> => if r <? 9 [r] else []) or_throw
    printl"{total} {path}"
}
```

- **Proposed when proof is absent:** `error: serve: no checked protocol proof matches this implementation and target`; likewise for `pipeline`.
- **Programmer writes:** the same calls against a library with checked proofs; no new call syntax. Library authors discharge the request/reply and window/flight invariants, including close, cancellation, draining and callback restrictions. The compiler binds evidence to the actual primitive implementation and verifies its premises at each use.
- A model check of a few fixed capacities is not proof for arbitrary capacity. Use a parameterized proof or an explicitly bounded model whose bounds are enforced at the call; unknown proof fails closed. A checksum alone proves identity, not deadlock freedom.
- **Users:** audited concurrent services and certification; useful with `$no_deadlocks` independently of `$bulletproof`.
- **Name/recommendation:** `$verify_protocols`; “verify certified” is redundant. Keep it separate from generic library memory/check obligations because the proof concerns scheduling and protocol state.

## Decision (a): should `$bulletproof` reject unconfined whole paths?

- **Trust today — row 10:** a path taken whole has no selected base to escape. `$confine_external_paths` removes that assumption but currently only warns; `$bulletproof` includes it without strengthening severity.
- **Today's quiet fragment:** remove `$confine_external_paths` below. With that existing opt-out, this program still compiles, with a warning. `$bulletproof` inherits that warning severity, although other bundle members may independently reject this program.

```dewy
$confine_external_paths
main = ():>void => {
    let argv = args()
    if argv.length =? 0 return
    let f = p(argv[0])
    printl(f.exists)
}
```

- **Proposed path diagnostic:** `error: f is not proven to stay inside a base required by $bulletproof; use root.confine(f) or guard with root.contains(f)`. Other bundle obligations, such as allocation failure, still apply independently.
- **Programmer writes** before the file operation, to discharge the path obligation:

```dewy
let root = p"/srv/data"
if not root.contains(f) return
printl(f.exists)
```

- Alternatively, `(root.confine(f) or_throw).exists` requires propagating/handling `PathEscape`. Literal paths already receive `SafePath`; this proposal does not enforce one global application root. Lexical confinement also does not stop a symlink inside the base pointing outside; `open_beneath` is explicitly not built.
- `contains` currently allocates, and strict effect checking can also reject `exists`. Full `$bulletproof` acceptance needs verified effect summaries and a containment implementation using explicit acquired capacity or no allocation; the path guard alone does not solve those separate costs.
- **Users:** sandboxed file services/security reviews; warning-strength confinement remains useful outside `$bulletproof`.
- **Name/recommendation:** retain `$confine_external_paths`; make missing proof an error under `$bulletproof` without promoting unrelated warnings. This changes decided warning semantics and needs David's approval. Do not silently permit `$confine_external_paths=false` inside an active contradictory bundle; opting out of the bundle explicitly relinquishes that guarantee.

## Decision (b): audited waits and the parallel-range cap

- **Trust today — rows 13 and 1:** a person's `$audited_wait` claim certifies an external wait; a parallel range of at least 2^63 values silently counts as 2^63−1. These need different repairs.

### Audited external waits

- **Today**, accepted with `$no_deadlocks` (also reachable under `$bulletproof`):

```dewy
$no_deadlocks
$extern
usleep = (us:uint32):>int32
$audited_wait
nap = ():>int32 => {
    $unsafe usleep(1000)
}
```

- **Proposed in the proof-demanding bundle:** `error: nap uses $audited_wait, a human claim rather than a checked wait proof; use a verified adapter`.
- **Programmer writes** for this delay, using the existing scheduler operation:

```dewy
$no_deadlocks
nap = ():>void | Canceled => sleep(1ms)
```

- The strict configuration must also check the scheduler primitive's wait contract; changing the call's name cannot substitute for that proof. Other FFI needs an adapter verified not to depend on program tasks/locks. A timeout does not prove this, and `& no_effects` on an extern must not become an alternative unchecked escape hatch.
- **Users/name/recommendation:** certification; retain `$audited_wait` as the honest name for the ordinary human-audit lane. Add a separate proof requirement, provisionally `$waits.require_proofs`, included in `$bulletproof`, rather than changing what an audit claims. No accepted adapter-proof syntax exists yet.

### Parallel ranges

- **Today**, even with the existing opt-out:

```dewy
$no_assumed_bounds
visit = (lo:int64 hi:int64):>void => {
    parallel i in [lo..hi] { let ignored = i }
}
```

- `visit(0 9223372036854775807)` denotes 2^63 iterations; the internal counter caps it. Do not run this example to observe the issue; the cap is directly in `lib/std/thread.jo`.
- **Proposed:** `error: parallel range count is not proven to fit int64 without truncation; bound the range or partition it into proven-size chunks`.
- **Programmer writes**, for a batch capped at one million items:

```dewy
$no_assumed_bounds
visit = (hi:int64):>void => {
    if hi <? 0 or hi >? 1000000 return
    parallel i in [0..hi) { let ignored = i }
}
```

- Larger intentional ranges need overflow-safe chunking that preserves every element, or a future explicit size-error API. Do not silently clamp or equate “impractical” with “impossible.” Actual collection OOM remains separate from iteration count.
- **Users/name/recommendation:** exact enumeration, security and certification; extend the already approved `$no_assumed_bounds` to cover this listed assumption. No additional tag is needed. A normal range-size proof should suffice; do not build a new general proof language for this cap.
