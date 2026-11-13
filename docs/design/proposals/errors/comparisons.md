# Peer comparisons and evidence

These are reviewer judgments about the written standard-library idioms, not benchmarks, user studies, or compiled application tests. The files in peers/ are original illustrative code. They isolate the same error-handling tasks; their parsers, network adapters and scheduling choices are not claimed equivalent workloads. Third-party libraries can improve the boilerplate and reporting scores, especially in Rust and Swift. This is not a ranking of whole languages.

Order: **O** obvious, **D** discoverable, **C** concise, **S** safe by default, **K** complete for the stated scenario. The scorecard in dogfood.md links to these rows. Every score below 5 has an explicit reason and a local line citation here. A 5 means no material problem in the paper idiom for that dimension, not empirical proof.

## Primary references checked

- Python has group partitioning and distinguishes ExceptionGroup from BaseExceptionGroup; except* retains unmatched subgroups. See [built-in exception groups](https://docs.python.org/3/library/exceptions.html#exception-groups) and [except*](https://docs.python.org/3/reference/compound_stmts.html#except-clause). [TaskGroup documentation](https://docs.python.org/3/library/asyncio-task.html#task-groups) separately specifies cancellation/grouping; no claim that all cancellation is an ordinary Exception.

- Go supplies Join and recursive Is/As; its single-error Unwrap is distinct from multi-error unwrapping. See [errors package](https://pkg.go.dev/errors).

- Rust Error::source exposes one cause, and Backtrace is an explicit capture facility with supported/disabled states. See [Error](https://doc.rust-lang.org/std/error/trait.Error.html), [Backtrace](https://doc.rust-lang.org/std/backtrace/struct.Backtrace.html), and [Drop](https://doc.rust-lang.org/std/ops/trait.Drop.html). The local enum is an application choice, not a claim that every Rust library needs exactly this enum.

- JavaScript specifies AggregateError/errors and cause; TypeScript documents SuppressedError for using disposal and unknown catches. See [ECMAScript AggregateError](https://tc39.es/ecma262/multipage/fundamental-objects.html#sec-aggregate-error-objects), [TypeScript resource management](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html), and [catch-variable typing](https://www.typescriptlang.org/tsconfig/useUnknownInCatchVariables.html). These are separate from host AbortSignal policies.

- Swift supports custom Error types, Result and structured task groups; cancellation is cooperative. See [Error](https://docs.swift.org/latest/documentation/swift/error/), [Result implementation](https://github.com/swiftlang/swift/blob/main/stdlib/public/core/Result.swift), and [task groups](https://docs.swift.org/latest/documentation/swift/taskgroup/). Failures/Context in the example are local types, not asserted standard-library names.

Comparative deductions below are inferences from those APIs and the exact local examples, not quotations from their maintainers.

## Python

<a id="python-01"></a>

**01 Cleanup pair — 4/4/3/4/5.** [python.py:14](peers/python.py). O4/D4: retaining both failures requires catching BaseException and choosing a group; C3: two try blocks and a pending primary; S4: the cancellation-safe combination is a handwritten cleanup policy, not ordinary finally behavior.

<a id="python-02"></a>

**02 Form validation — 5/5/4/4/5.** [python.py:28](peers/python.py). C4: collect-and-raise replaces simple exception flow; S4: add_note mutates the caught exception, so other holders see the new field context.

<a id="python-03"></a>

**03 Batch files — 5/4/4/4/5.** [python.py:44](peers/python.py). D4/C4: preserve earlier failures with an explicit BaseException branch; S4: cancellation preservation depends on the test on line 52 rather than an enforced default.

<a id="python-04"></a>

**04 Parallel items — 5/4/4/4/5.** [python.py:128](peers/python.py). D4/C4: futures must be read individually and errors accumulated; S4: the programmer must retain each failed result and must not replace the loop with first-result propagation.

<a id="python-05"></a>

**05 Library context — 5/5/5/4/5.** [python.py:68](peers/python.py). S4: the note preserves the error type but mutates aliases. The operation otherwise fits the transparent-context scenario directly.

<a id="python-06"></a>

**06 CLI diagnostics — 5/5/5/4/4.** [python.py:80](peers/python.py). S4: the default traceback includes source text/locations, which needs a disclosure policy in a CLI; K4: constructed-but-never-raised validation errors have no construction traceback (lines 106–109).

<a id="python-07"></a>

**07 Retry history — 5/4/4/4/5.** [python.py:84](peers/python.py). D4/C4: explicit accumulation and a cancellation branch; S4: changing BaseException to Exception loses the accumulated history on cancellation.

<a id="python-08"></a>

**08 Cancellation boundary — 4/4/4/4/5.** [python.py:11](peers/python.py). O4/D4: BaseExceptionGroup chooses a different family depending on its children; C4: the explicit stop policy is still needed in batch/retry (lines 44–55, 84–95); S4: broad BaseException handlers can default cancellation.

<a id="python-09"></a>

**09 Selective recovery — 4/4/5/5/5.** [python.py:99](peers/python.py). O4/D4: except* is a separate handling form to learn. C/S/K5: lines 100–103 automatically keep the unmatched subtree, including when recovery raises.

<a id="python-10"></a>

**10 Domain cause — 5/5/5/5/5.** [python.py:73](peers/python.py). All five are supported by lines 74–77: a recognizable explicit raise-from boundary retains the lower-level exception; an ordinary Exception catch excludes asyncio cancellation.

<a id="python-11"></a>

**11 Occurrence origins — 4/4/4/4/3.** [python.py:106](peers/python.py). O4/D4: traceback means raised history, not object construction; C4: creation origins need extra capture machinery; S4: treating this as an origin report misattributes construction; K3: both results here are None.

<a id="python-12"></a>

**12 Bounded validation — 5/5/4/4/4.** [python.py:112](peers/python.py). C4: cap and omitted counter are manual; S4/K4: lines 113–125 bound diagnostic count but neither input storage nor physical allocation. This is the same limitation charged to Dewy.

## Go

<a id="go-01"></a>

**01 Cleanup pair — 4/4/5/4/5.** [go.go:11](peers/go.go). O4/D4: deferred code changes a named result after return body(); S4: retaining close errors depends on this particular defer; a plain defer close() drops them. The chosen idiom is compact and complete for ordinary errors.

<a id="go-02"></a>

**02 Form validation — 5/5/5/4/5.** [go.go:16](peers/go.go). S4: errors are ordinary return values and the caller may ignore the final Join result; no enforced propagation follows from this function signature.

<a id="go-03"></a>

**03 Batch files — 5/4/4/4/5.** [go.go:23](peers/go.go). D4/C4: a separate slice and errors.Is cancellation branch; S4: omitting line 30 converts cancellation into another batch issue.

<a id="go-04"></a>

**04 Parallel items — 4/4/3/4/5.** [go.go:37](peers/go.go). O4/D4: indexed channel results restore input order; C3: goroutines, channel, record and join loop; S4: worker creation is unbounded in this idiom and needs a pool/cap for large inputs.

<a id="go-05"></a>

**05 Library context — 5/5/5/5/4.** [go.go:48](peers/go.go). K4: wrapping is concise and errors.Is/As can inspect through it, but the outer concrete identity changes; it is not transparent notes on the same error kind.

<a id="go-06"></a>

**06 CLI diagnostics — 4/3/3/4/3.** [go.go:85](peers/go.go). O4/D3/C3: location collection and symbolization require a custom Located wrapper; S4: default text printing has no uniform disclosure policy; K3: lines 85–91 capture PCs but do not provide the full group/cause/location reporter (line 98).

<a id="go-07"></a>

**07 Retry history — 5/4/4/4/5.** [go.go:50](peers/go.go). D4/C4: accumulated slice plus explicit stop branch; S4: cancellation is an ordinary error and preserving it depends on line 57.

<a id="go-08"></a>

**08 Cancellation boundary — 4/4/4/3/5.** [go.go:94](peers/go.go). O4/D4/C4: the caller must know to search the wrapped tree first; S3: deleting this check lets the ordinary fallback erase cancellation and all siblings.

<a id="go-09"></a>

**09 Selective recovery — 4/3/3/4/4.** [go.go:67](peers/go.go). O4/D3/C3: custom Unwrap() []error traversal; S4: recoverOnly must explicitly rejoin rest (line 82); K4: this split flattens group structure and treats singly wrapped causes as indivisible, rather than preserving arbitrary nested group metadata.

<a id="go-10"></a>

**10 Domain cause — 5/5/5/4/5.** [go.go:48](peers/go.go). S4: %w can wrap context.Canceled into an ordinary error without any enforced forwarding policy; lines 94–96 supply the missing application convention. The causal link itself is first-class.

<a id="go-11"></a>

**11 Occurrence origins — 4/3/3/4/4.** [go.go:88](peers/go.go). O4/D3/C3: origin capture requires an explicit wrapper and PCs; S4: capture at this call can be mistaken for original construction; K4: ordinary errors.New/foreign errors contain no such location unless adapted.

<a id="go-12"></a>

**12 Bounded validation — 5/5/4/4/4.** [go.go:103](peers/go.go). C4: count cap and summary are manual; S4/K4: a slice-size bound does not guarantee allocation success or bound input memory.

## Rust

<a id="rust-01"></a>

**01 Cleanup pair — 4/4/3/4/4.** [rust.rs:33](peers/rust.rs). O4/D4: an explicit fallible close is distinct from Drop; C3: a custom aggregate type and two-result join; S4: forgetting this explicit completion loses the close result; K4: ordinary Drop cannot return that result (line 100).

<a id="rust-02"></a>

**02 Form validation — 5/4/4/5/5.** [rust.rs:39](peers/rust.rs). D4/C4: Vec accumulation is direct, but the Many error variant and Error implementation (lines 4–32) are application/library work. Result preserves the failure path.

<a id="rust-03"></a>

**03 Batch files — 5/4/3/4/5.** [rust.rs:53](peers/rust.rs). D4/C3: enum, box, accumulator and manual cancellation walk; S4: cancellation behavior depends on the custom canceled function and explicit branch.

<a id="rust-04"></a>

**04 Parallel items — 4/4/3/4/4.** [rust.rs:70](peers/rust.rs). O4/D4/C3: scoped thread handles plus ordered joins are more machinery; S4: one thread per input needs a bound/pool; K4: a worker panic takes the expect path outside the many-error contract.

<a id="rust-05"></a>

**05 Library context — 5/4/4/5/4.** [rust.rs:12](peers/rust.rs). D4/C4: a Context variant and Error::source implementation are supplied locally; K4: the outer enum variant changes, unlike a type-preserving diagnostic note.

<a id="rust-06"></a>

**06 CLI diagnostics — 4/3/3/4/3.** [rust.rs:18](peers/rust.rs). O4/D3/C3: source() exposes one chain and Many needs a separate walker; S4: the example Display delegates to Debug (line 15), potentially exposing payloads; K3: no common full tree/location renderer is supplied by this Error implementation.

<a id="rust-07"></a>

**07 Retry history — 5/4/4/4/5.** [rust.rs:104](peers/rust.rs). D4/C4: custom Failure, history and stop predicate; S4: forwarding cancellation depends on the application convention in canceled(), not Result itself.

<a id="rust-08"></a>

**08 Cancellation boundary — 4/3/3/3/4.** [rust.rs:45](peers/rust.rs). O4/D3/C3: recursive matching across this application enum; S3: new variants/wrappers can hide cancellation unless the policy is updated; K4: this is an application protocol, not a universal runtime cancellation carrier.

<a id="rust-09"></a>

**09 Selective recovery — 4/3/3/4/4.** [rust.rs:81](peers/rust.rs). O4/D3/C3: hand-written consuming partition; S4: callers must explicitly propagate the rest; K4: the helper flattens Many and keeps Context indivisible, so preserving arbitrary group context needs more implementation.

<a id="rust-10"></a>

**10 Domain cause — 5/4/4/5/5.** [rust.rs:18](peers/rust.rs). D4/C4: implementing a domain variant and source() takes boilerplate. The type system and explicit enum keep the causal boundary reviewable.

<a id="rust-11"></a>

**11 Occurrence origins — 4/4/4/5/4.** [rust.rs:93](peers/rust.rs). O4/D4/C4: track_caller, Location and Backtrace must be attached explicitly; K4: existing errors passed to locate get the wrapper call site, not a retroactive original construction site.

<a id="rust-12"></a>

**12 Bounded validation — 5/4/4/4/4.** [rust.rs:119](peers/rust.rs). D4/C4: custom Row/Omitted variants plus count cap; S4/K4: Vec count bounds do not establish physical allocation success or total input bounds.

## TypeScript

<a id="typescript-01"></a>

**01 Cleanup pair — 4/4/5/4/4.** [typescript.ts:8](peers/typescript.ts). O4/D4: using disposal builds SuppressedError, distinct from AggregateError; S4: the cancellation walker must understand both (lines 18–23); K4: callers need two aggregation shapes and compatible disposal runtime support.

<a id="typescript-02"></a>

**02 Form validation — 5/5/4/4/5.** [typescript.ts:12](peers/typescript.ts). C4: collect then explicitly throw; S4: an arbitrary catch can swallow the group, and no result union requires the caller to account for it.

<a id="typescript-03"></a>

**03 Batch files — 5/4/4/4/5.** [typescript.ts:25](peers/typescript.ts). D4/C4: unknown reasons, context wrappers and explicit cancellation walker; S4: line 31 is a handwritten cancellation-preservation convention.

<a id="typescript-04"></a>

**04 Parallel items — 5/5/5/4/5.** [typescript.ts:37](peers/typescript.ts). S4: allSettled records rejection reasons but does not give cancellation special treatment; ordinary later catch/fallback can erase it. It directly provides input-ordered all-results aggregation.

<a id="typescript-05"></a>

**05 Library context — 5/5/5/4/4.** [typescript.ts:43](peers/typescript.ts). S4: an arbitrary cause including cancellation can become an ordinary Error; K4: this changes outer identity, so it is causal wrapping rather than transparent type-preserving context.

<a id="typescript-06"></a>

**06 CLI diagnostics — 4/3/3/4/4.** [typescript.ts:77](peers/typescript.ts). O4/D3/C3: three tree edge forms require a custom reporter (implementations at lines 6, 10, 44); S4: mutable error objects/causes can form cycles or contain arbitrary data; K4: stack is a host convention, not a structured portable origin field.

<a id="typescript-07"></a>

**07 Retry history — 5/4/4/4/5.** [typescript.ts:62](peers/typescript.ts). D4/C4: explicit history and cancel-walk; S4: omitting the cancel branch keeps retrying after cancellation.

<a id="typescript-08"></a>

**08 Cancellation boundary — 4/3/3/3/4.** [typescript.ts:18](peers/typescript.ts). O4/D3/C3: an application cancellation class and tree walker; S3: normal catch includes cancellation; K4: native AbortSignal/DOMException conventions need adapters (line 81).

<a id="typescript-09"></a>

**09 Selective recovery — 4/3/3/4/4.** [typescript.ts:46](peers/typescript.ts). O4/D3/C3: no built-in typed split, so recursive reconstruction is handwritten; S4: caller must rethrow the rest; K4: lines 52–56 preserve standard fields but not arbitrary subclasses/custom metadata.

<a id="typescript-10"></a>

**10 Domain cause — 5/5/5/4/5.** [typescript.ts:43](peers/typescript.ts). S4: cause accepts any value, including cancellation, without enforcing forwarding. The standard Error options directly express a domain cause.

<a id="typescript-11"></a>

**11 Occurrence origins — 4/4/4/4/4.** [typescript.ts:78](peers/typescript.ts). O4/D4/C4: extracting an origin requires host stack parsing/source maps; S4: mutable stack text can be changed; K4: Error constructor sites are customary stack data, not the structured target-independent field proposed for Dewy.

<a id="typescript-12"></a>

**12 Bounded validation — 5/5/4/4/4.** [typescript.ts:82](peers/typescript.ts). C4: manual cap and omitted counter; S4/K4: limits on number of Errors neither bound source input nor guarantee memory for them.

## Swift

<a id="swift-01"></a>

**01 Cleanup pair — 4/4/3/4/4.** [swift.swift:10](peers/swift.swift). O4/D4: close must run after capturing body failure; C3: two do/catch blocks and a custom group; S4: callers must remember explicit fallible close; K4: scope destruction does not supply this result-combining policy.

<a id="swift-02"></a>

**02 Form validation — 5/4/4/5/5.** [swift.swift:16](peers/swift.swift). D4/C4: ordinary array accumulation plus a custom Failures type (line 2). The final throw is explicit and the validation scenario is covered.

<a id="swift-03"></a>

**03 Batch files — 5/4/4/4/5.** [swift.swift:28](peers/swift.swift). D4/C4: accumulated errors and custom context/cancellation helpers; S4: ordinary catch catches CancellationError, so line 34 must enforce stopping.

<a id="swift-04"></a>

**04 Parallel items — 4/4/3/4/5.** [swift.swift:40](peers/swift.swift). O4/D4/C3: indexed Result task values, sorting and partitioning; S4: tasks and result storage need an application bound, and cancellation must remain a deliberate policy.

<a id="swift-05"></a>

**05 Library context — 5/4/4/5/4.** [swift.swift:3](peers/swift.swift). D4/C4: define a Context error type yourself; K4: it changes the outer dynamic type, rather than annotating the original error transparently.

<a id="swift-06"></a>

**06 CLI diagnostics — 4/3/3/4/3.** [swift.swift:67](peers/swift.swift). O4/D3/C3: a custom location wrapper plus custom group/context structures; S4: an unconstrained generic print needs a payload disclosure policy; K3: these types alone do not give a generic complete group/cause/trace renderer (line 88).

<a id="swift-07"></a>

**07 Retry history — 5/4/4/4/5.** [swift.swift:75](peers/swift.swift). D4/C4: array history, custom context and cancellation predicate; S4: line 82 must explicitly stop ordinary catch from retrying cancellation.

<a id="swift-08"></a>

**08 Cancellation boundary — 4/3/3/3/5.** [swift.swift:22](peers/swift.swift). O4/D3/C3: explicit recursive cancellation test; S3: ordinary catch treats CancellationError like other errors. This helper covers the shown custom wrappers, so K is 5 for that scoped scenario.

<a id="swift-09"></a>

**09 Selective recovery — 4/3/3/4/4.** [swift.swift:57](peers/swift.swift). O4/D3/C3: custom type-erased split; S4: caller must retain the rest; K4: group structure is flattened and Context remains indivisible.

<a id="swift-10"></a>

**10 Domain cause — 5/4/4/5/5.** [swift.swift:3](peers/swift.swift). D4/C4: a custom domain error with a cause member. This is a direct typed representation, though no standard cause traversal is implied.

<a id="swift-11"></a>

**11 Occurrence origins — 4/4/4/5/4.** [swift.swift:72](peers/swift.swift). O4/D4/C4: explicit #fileID/#line wrapper; K4: it records the wrapping call, not earlier construction unless each producer calls it there.

<a id="swift-12"></a>

**12 Bounded validation — 5/4/4/4/4.** [swift.swift:91](peers/swift.swift). D4/C4: custom group plus manual bound/summary; S4/K4: array element counts do not establish total memory or allocation success.
