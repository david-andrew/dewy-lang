# Resource exhaustion and the no-traps promise

Recorded 2026-09-10 from a language-design discussion. **This is an open design problem and a sketch of possible directions, not a specification, accepted resource model, implementation plan, or commitment to new syntax.** It does not amend the existing no-traps rule. The environmental boundary, resource contracts, and failure mechanisms described below remain to be designed and evaluated.

Related: [no traps](no_traps.md), [user-managed storage](user_managed_storage.md), [value semantics](value_semantics.md), [safety and concurrency](safety_and_concurrency.md), [idiomatic facts](idiomatic_facts.md), [refinements and effects](../../site/reference/src/refinements-and-effects.md), and [errors and forwarding](../../site/reference/src/errors-and-forwarding.md).

## The problem

Dewy aims to prove ordinary operation preconditions at compile time, leaving bare operations with no runtime safety checks. Failures that cannot be ruled out are explicit values that the program handles. Stack exhaustion exposes an unresolved foundation of that promise: even a well-typed call needs available storage.

Avoiding heap allocation does not establish that an object can be allocated. Stack, arena, static, and caller-owned placement can improve cost, predictability, and analyzability, but still require storage. Similarly, promoting an abstract integer to a big integer avoids fixed-width arithmetic overflow by potentially requiring more memory. Stack and heap exhaustion need a coherent policy beneath representation choices.

The desired experience is that common calls, small objects, indexing, and ordinary recursion do not acquire pervasive error alternatives or require routine `unsafe` claims. Straightforward cases should be proven with little or no additional programmer evidence. Harder computations should have an honest way to fail when they reach a real limit, without corrupting memory or introducing a hidden abort.

## Factors any solution must balance

- **Programmer ergonomics.** Keep common operations direct. Avoid error unions, manual budgets, proof annotations, or `unsafe` at nearly every call. When failure is possible, make its handling and propagation clear at meaningful touch points.
- **Compile-time safety and zero runtime checking cost where proven.** Preserve the value of static proofs. Explore acquiring or checking capacity once for a whole computation instead of checking every call and object construction.
- **Honest guarantees.** Distinguish needing bounded resources from actually possessing them. Explain environmental assumptions and unknown analysis results; do not describe guarded crashes or relocating allocations as eliminating failure.
- **Stable interfaces and modular reasoning.** Helpers, generic code, callbacks, and libraries need reusable contracts. A backend optimization or improved solver should not silently change a public return type or add caller obligations.
- **Useful recursion.** Support common bounded recursion and guaranteed tail calls without making arbitrary recursive proofs a prerequisite for everyday use.
- **Implementation cost and predictability.** Balance analysis complexity, compile time, runtime checks, code size, memory overhead, and worst-case behavior. A conservative analysis should still produce useful explanations.
- **Portability and interoperability.** Account for target layouts, native and managed execution, foreign calls, callbacks, threads, and interrupts/signals. Guarantees must state what parts of execution the compiler and runtime control.
- **Reliable recovery.** Failure reporting, propagation, and cleanup also need resources. Define partial initialization, side effects, and resource lifetimes without assuming exhaustion automatically rolls back a computation.

Unrestricted growing computation, finite storage, no dynamic enforcement, and a guarantee against exhaustion cannot all be provided together. The open question is where to place the necessary restrictions, proofs, acquisition, and checks so that the common experience stays simple.

## Possible direction: acquire capacity, then use it under a proof

One candidate principle is:

> Once required resources have been acquired, operations proven to fit those resources cannot fail for lack of that capacity. Acquiring additional resources can fail explicitly.

This resembles proven indexing: an existing array and a valid index establish that access is permitted. Acquired storage and a bound on its use could establish that a call or construction needs no resource-failure alternative.

Conceptually, with explanatory notation rather than proposed Dewy syntax:

```text
acquire workspace for computation -> Workspace | ResourceUnavailable
run computation using workspace  -> Answer
```

The second operation is infallible only with respect to the covered resources and under its input and capacity contracts. Other declared failures remain possible. Workspace could include stack and temporary/object storage; it is not necessarily one contiguous allocation or a programmer-visible parameter on every helper.

The compiler might infer a constant requirement for a fixed computation, or a requirement parameterized by input size. Acquisition could occur at task startup, request admission, or preparation for an algorithm. Many small allocations could share one acquisition check and resource proof. Embedded execution might instead establish capacity through its configured memory layout.

Accounting must respect simultaneous use: a resource cannot be promised twice, active recursive callers retain their storage, and concurrent tasks need valid partitions or a coordinated allocation mechanism. Lifetimes, alignment, storage reuse, result escape, and ownership all affect what capacity is really available. Successfully returning an object must not leave it in a released workspace.

Whether this can usually be inferred, whether explicit capabilities are needed, and how resource ownership survives copying and calls are open questions. Acquiring all capacity up front can also waste memory or reject work that would fit in its actual execution; conservative reservation has a cost of its own.

## What static stack analysis could establish

For a closed acyclic call graph with bounded per-function stack use, a conservative bound is essentially a longest-path calculation:

```text
needed(f) = own_stack_bound(f) + max(needed(each possible callee))
```

This simplified formula assumes consistent accounting for calls and frames. Sequential calls do not all remain active together. A more precise analysis can use the caller's live stack at each call site instead of its overall local peak.

Backend accounting must include alignment, saved registers, argument areas, expression temporaries, return storage, and compiler-generated calls. Source-level facts can supply size and depth bounds, but source locals alone do not determine machine stack usage. Dynamic stack allocation can accumulate inside loops even without recursion. Foreign or indirect calls need sound summaries or conservative target sets; unresolved calls cannot simply contribute zero.

Promising recursive cases include bounded decreasing integers, bounded tree or parser nesting depth, and divide-and-conquer with a proven size relationship. Guaranteed tail calls can prevent frame accumulation, but must be guaranteed in every supported build mode when correctness relies on them, including relevant cleanup and lifetime behavior. Proving termination alone does not prove that the stack fits: a finite list can still exceed the available recursion depth.

Diagnostics should distinguish **proven to fit**, **proven to exceed**, and **not proven to fit**. A conservative upper bound above a budget does not prove an execution exceeds that budget. Unknown bounds should identify the missing size, depth, callee, or environmental assumption. A strict contract could reject an unknown bound without falsely reporting inevitable overflow.

## Computations without useful static bounds

Possible mechanisms include checked recursive descent, growable stack segments, or explicit/compiler-managed storage for pending work. Each needs a defined failure path when capacity or further acquisition runs out. Growable stacks and heap continuations move the limiting resource; they do not remove it.

A possible interface distinction is between operations that **run within supplied resources**, whose implementations must meet that contract, and operations that **may acquire or exhaust resources**, whose interfaces expose failure. Inference could ease local code while published contracts stay stable. Losing a proof for a fixed contract should diagnose that implementation, not silently change its public result from `T` to `T | ResourceExhausted`. Exact inference and portability rules are unresolved.

Dewy's current direction keeps errors in returned unions and separate from effects; forwarding is not stack unwinding. An ambient resource-failure effect handled at an outer execution boundary is another conceivable design, but would be a substantive extension requiring explicit control-flow and cleanup semantics. It must not be presented as already implied by Dewy's effects or error forwarding. Ordinary error values plus coarse capacity acquisition are a candidate that stays closer to the existing direction. How much propagation burden remains needs to be tested on real programs.

In either approach, checks must precede consuming capacity needed for failure handling. Reserve or prove enough space for error construction, returns, cleanup, and any permitted recovery. Catching an already-exhausted native stack is not a complete recovery design. Guard pages and stack probing can prevent corruption but do not by themselves satisfy the no-hidden-abort rule. FFI and cleanup that allocate or recurse need explicit treatment. Recovery need not undo prior side effects, but must preserve the language's validity and lifetime guarantees.

## The environmental boundary remains open

“Within the program's sphere of influence” is a useful starting point, but calling all resource limits external would conceal failures generated code can control. A candidate distinction is:

| Situation | Possible responsibility |
| --- | --- |
| External termination, hardware failure, or an environment that stops honoring its execution guarantees | Outside the continued-execution guarantee, with assumptions stated explicitly |
| A request for more resources is refused | Explicit failure value |
| Execution would exceed resources already assigned to it | Prove impossible, or detect before crossing the limit and return failure |

An OS-chosen stack limit does not make uncontrolled recursive stack exhaustion equivalent to an external kill. Conversely, a language cannot guarantee continued execution after the environment forcibly terminates it.

Target ABI knowledge gives layout rules, not a universal usable stack budget. Thread configuration, entry from foreign code, asynchronous activity, and runtime overhead affect availability. Reserving virtual address space need not establish that future backing-memory requests will succeed. Any acquisition guarantee must state what the target actually provides and what remains an environmental assumption. Startup failure before application code has resources to run also needs an explicit place in this model.

One possible refinement of the aspiration is: **no runtime safety checks where static proof and established capacity suffice; explicit resource failure where additional capacity is needed; stated assumptions about continued execution.** Whether to adopt that wording, where failures must be handled, and which resource guarantees belong in ordinary Dewy versus a stricter execution profile remain open.

## Security implications of candidate approaches

This section extends the open problem to adversarial inputs and shared services. The aim is to assess which security properties each candidate could establish, without equating memory safety, trap-freedom, and resistance to denial of service (DoS).

### Memory safety and availability are different guarantees

A stack buffer overflow writes outside an object's bounds; stack exhaustion consumes the space available to active calls and temporary storage. Preventing the first does not prove the second impossible. Memory-safe code can still consume excessive stack, heap, CPU time, or other finite resources, or reach an explicit panic or abort. When an attacker controls the input that triggers this behavior, loss of availability can be a security vulnerability even when no arbitrary memory access occurs.

Rust's safe/unsafe boundary concerns undefined behavior and the contracts required to prevent it, rather than guaranteeing that useful work completes within a resource budget. Safe callers also depend on the soundness of unsafe implementations beneath their APIs: “the application uses only safe calls” does not establish that a vulnerability's entire causal chain excludes unsafe code or FFI. The same distinction would apply to Dewy's compiler, runtime, allocators, and trusted libraries. See the [Rustonomicon's description of the safe/unsafe boundary](https://doc.rust-lang.org/nomicon/safe-unsafe-meaning.html).

Representative advisories, checked on 2026-09-10, illustrate distinct mechanisms:

| Example | Mechanism and relevance to Dewy |
| --- | --- |
| [`time`, RUSTSEC-2026-0009](https://rustsec.org/advisories/RUSTSEC-2026-0009.html) | Crafted RFC 2822 input could exhaust the stack. The fix imposed a recursion limit and returned an error when reached: a concrete example of bounding a parser's work and exposing failure. |
| [`quick-xml`, RUSTSEC-2026-0195](https://rustsec.org/advisories/RUSTSEC-2026-0195.html) | Namespace processing allocated internal storage before the consumer could reject an event; concurrent readers compounded memory demand. The fix added a configurable declaration limit and an error. Limits must cover library work before it occurs, not only the result visible to a caller. |
| [`quick-xml`, RUSTSEC-2026-0194](https://rustsec.org/advisories/RUSTSEC-2026-0194.html) | Duplicate-attribute checking performed quadratic work, consuming CPU without a crash or memory exhaustion. An I/O timeout could not interrupt the synchronous computation. A no-traps memory policy alone would not address this. |
| [`quinn-proto`, RUSTSEC-2024-0373](https://rustsec.org/advisories/RUSTSEC-2024-0373.html) | Connection-state cleanup could leave inconsistent state and cause a reachable panic. Correct failure and cleanup behavior is part of the security boundary. |

These are examples, not a census or an audit proving that each implementation has no unsafe code in its causal chain. Do not infer vulnerability percentages from them or adopt speculative breakdowns from the motivating discussion. RustSec advisories and CVEs are not identical populations; disclosure and audit selection also affect any historical comparison.

Availability-only impact is not automatically low severity: RustSec rates the cited `time` issue Medium and the cited `quick-xml` and `quinn-proto` issues High. Exploitability, authentication requirements, affected workloads, isolation, and recovery determine practical impact. Preventing a memory-corruption route to code execution is a substantial security benefit, but reliable remote service disruption remains important.

### What the resource approaches would and would not protect

| Candidate | Potential security benefit | Remaining exposure or cost |
| --- | --- | --- |
| Static bound plus acquired capacity | Can rule out the covered exhaustion during admitted work, without repeated runtime checks. | A finite bound may still be too expensive to admit. Many individually bounded jobs can exhaust a shared pool; conservative reservations can themselves reduce availability. |
| Explicit checked limits and returned errors | Can reject hostile nesting, growth, or size requests before exhausting a shared resource. | Limits must apply before expensive work, and returning an error does not guarantee cheap cleanup or sensible caller handling. |
| Growable stacks or heap continuations | Can avoid a fixed native-stack limit and provide a controlled growth-failure path. | Unbounded growth transfers the attack to another resource unless budgets are enforced. Moving recursion to a loop can also preserve excessive CPU work. |
| Guarded exhaustion followed by process abort | Can contain memory corruption if the platform protections and generated code are correct. | Still permits process-wide DoS and conflicts with the proposed no-hidden-abort ambition. A guard is not a recovery policy. |
| Failure contained within a request or task | Can preserve unrelated work and let application code reject or defer the offending job. | Requires valid cleanup, resource isolation, bounded scheduling interference, and defined effects on shared state. A task boundary alone does not supply these properties. |

The security distinction is between **capacity physically available** and **capacity this work is allowed to consume**. A request should not necessarily receive all currently free memory. Candidate policies may need per-request, per-tenant, and process-wide limits, bounded concurrency and queues, and admission control before costly processing. Nested calls should consume the enclosing allowance; spawning tasks, entering libraries, or opening a new workspace must not silently reset a quota or bypass aggregate accounting. This is a question of resource authority as well as sizes and lifetimes.

Input-size limits can be useful, but must be related to peak internal memory, output expansion, nesting, and work amplification. A short compressed payload, adversarial graph, or large integer computation can require much more work or storage than the input bytes suggest. A checked contract such as “this input needs at most B bytes” is distinct from the application policy “this requester may consume B bytes.” Both may be necessary.

### Recovery and enforcement are security-sensitive code

Failure must occur before exhausting the resources required to return and clean up. The budget needs to cover hidden work such as copying, formatting, recursive destruction, allocator metadata, and library callbacks. Error reporting should not allocate an unbounded diagnostic containing attacker input, and repeated failures should not produce unlimited logs or immediate retry loops. Partial updates must leave valid state; applications may also require transactional or fail-closed behavior, neither of which follows merely from an error union. In particular, exhaustion during authorization or validation must not be treated as successful validation.

Resource-limit checks, counters, and size calculations must themselves be overflow-safe. Proofs and enforcement must describe the code actually emitted, including cleanup and indirect calls. An unchecked resource summary, FFI contract, or `unsafe` claim is a trust obligation, not evidence that an adversarial bound holds. Test guard/probe coverage and failure paths as well as ordinary successful execution. These mechanisms need to preserve memory safety even when an attacker repeatedly hits the limit.

Excluding forced external termination from the language guarantee should not excuse avoidable attacker-induced pressure that predictably makes the OS kill the process. The language cannot prevent an arbitrary external kill; its runtime and libraries can still aim to reject oversized or over-budget work before reaching global exhaustion. Precisely which protection is guaranteed versus delegated to deployment policy remains open.

### No traps does not establish bounded work or general security

A program can be memory-safe, use a bounded stack, never trap, and still monopolize a worker indefinitely. Termination proofs do not establish acceptable execution time, and a stack proof says nothing by itself about heap retention, lock contention, file descriptors, network amplification, or total CPU work. Deadlock freedom, fairness, and responsiveness require additional reasoning or enforcement.

An adjacent design question is whether work budgets, cancellation points, or isolated execution should complement memory budgets. Static cost bounds could eliminate some dynamic accounting; general computations may need metering or effective preemption. A timeout that depends on the busy computation yielding is not sufficient for arbitrary synchronous or foreign code. How cancellation preserves invariants and permits bounded cleanup must be part of any such proposal, rather than treating forced task termination as automatically safe.

Authentication, authorization, cryptographic correctness, path handling, injection prevention, and confidentiality (including side channels) remain separate security obligations. They can produce severe vulnerabilities without memory corruption or a trap. Dewy's refinements may express useful application invariants, but this resource sketch establishes none of those policies automatically. Making resource failures explicit can improve availability defenses; it is not a claim that compiled programs are secure against all inputs.

### Security criteria for evaluating a solution

In addition to the ergonomic and runtime-cost comparisons above, evaluate crafted deep nesting, expanded output, adversarial CPU complexity, repeated failures, simultaneous near-budget requests, and resource use hidden inside callbacks or cleanup. Check whether rejection precedes expensive work, whether the failing job releases its capacity, and whether unrelated jobs remain responsive. Measure peak aggregate resources and rejection/cleanup cost, not only per-function frame size or successful throughput.

Candidate designs should make clear which guarantees are compiler-checked, which are enforced at runtime, which are application policies, and which depend on the target or trusted implementation. Security pressure should not make ordinary recursion routinely `unsafe`, nor should ergonomic defaults conceal unlimited attacker-controlled consumption. Finding useful defaults and reusable contracts that satisfy both remains part of this open design problem.

## Useful references and evaluation cases

- [GNATstack examples](https://docs.adacore.com/live/wave/gnatstack/html/gnatstack_ug/Examples.html) illustrate call-chain accounting and incomplete bounds from cycles, dynamic frames, and missing call information.
- [Clang's `musttail`](https://clang.llvm.org/docs/AttributeReference.html#musttail) illustrates guaranteed tail calls and the constraints such a guarantee needs.
- [Linux thread creation](https://man7.org/linux/man-pages/man3/pthread_create.3.html) and [Windows thread stack size](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-stack-size) describe configuration and reservation/commitment considerations.
- [GCC instrumentation options](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html) distinguish stack checking and stack-clash protection from a recovery contract.

Evaluate candidate designs against small object-heavy helpers, bounded and unbounded parsers, recursive tree traversal, big-integer arithmetic, reusable library callbacks, concurrent tasks, and foreign entry points. Compare source noise, inferred proofs, failure visibility, generated checks, reserved memory, and behavior across build modes and targets. Reporting stack use and unknown boundaries could be useful before any particular language policy is chosen.
