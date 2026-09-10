# Resource exhaustion and the no-traps promise

Recorded 2026-09-10 from a language-design discussion. **This is an open design
problem and a sketch of possible directions, not a specification, accepted
resource model, implementation plan, or commitment to new syntax.** It does not
amend the existing no-traps rule. The environmental boundary, resource contracts,
and failure mechanisms described below remain to be designed and evaluated.

Related: [no traps](no_traps.md), [user-managed storage](user_managed_storage.md),
[value semantics](value_semantics.md), [safety and concurrency](safety_and_concurrency.md),
[idiomatic facts](idiomatic_facts.md), [refinements and effects](../../site/reference/src/refinements-and-effects.md),
and [errors and forwarding](../../site/reference/src/errors-and-forwarding.md).

## The problem

Dewy aims to prove ordinary operation preconditions at compile time, leaving bare
operations with no runtime safety checks. Failures that cannot be ruled out are
explicit values that the program handles. Stack exhaustion exposes an unresolved
foundation of that promise: even a well-typed call needs available storage.

Avoiding heap allocation does not establish that an object can be allocated.
Stack, arena, static, and caller-owned placement can improve cost, predictability,
and analyzability, but still require storage. Similarly, promoting an abstract
integer to a big integer avoids fixed-width arithmetic overflow by potentially
requiring more memory. Stack and heap exhaustion need a coherent policy beneath
representation choices.

The desired experience is that common calls, small objects, indexing, and ordinary
recursion do not acquire pervasive error alternatives or require routine `unsafe`
claims. Straightforward cases should be proven with little or no additional
programmer evidence. Harder computations should have an honest way to fail when
they reach a real limit, without corrupting memory or introducing a hidden abort.

## Factors any solution must balance

- **Programmer ergonomics.** Keep common operations direct. Avoid error unions,
  manual budgets, proof annotations, or `unsafe` at nearly every call. When failure
  is possible, make its handling and propagation clear at meaningful touch points.
- **Compile-time safety and zero runtime checking cost where proven.** Preserve
  the value of static proofs. Explore acquiring or checking capacity once for a
  whole computation instead of checking every call and object construction.
- **Honest guarantees.** Distinguish needing bounded resources from actually
  possessing them. Explain environmental assumptions and unknown analysis results;
  do not describe guarded crashes or relocating allocations as eliminating failure.
- **Stable interfaces and modular reasoning.** Helpers, generic code, callbacks,
  and libraries need reusable contracts. A backend optimization or improved solver
  should not silently change a public return type or add caller obligations.
- **Useful recursion.** Support common bounded recursion and guaranteed tail calls
  without making arbitrary recursive proofs a prerequisite for everyday use.
- **Implementation cost and predictability.** Balance analysis complexity, compile
  time, runtime checks, code size, memory overhead, and worst-case behavior. A
  conservative analysis should still produce useful explanations.
- **Portability and interoperability.** Account for target layouts, native and
  managed execution, foreign calls, callbacks, threads, and interrupts/signals.
  Guarantees must state what parts of execution the compiler and runtime control.
- **Reliable recovery.** Failure reporting, propagation, and cleanup also need
  resources. Define partial initialization, side effects, and resource lifetimes
  without assuming exhaustion automatically rolls back a computation.

Unrestricted growing computation, finite storage, no dynamic enforcement, and a
guarantee against exhaustion cannot all be provided together. The open question
is where to place the necessary restrictions, proofs, acquisition, and checks so
that the common experience stays simple.

## Possible direction: acquire capacity, then use it under a proof

One candidate principle is:

> Once required resources have been acquired, operations proven to fit those
> resources cannot fail for lack of that capacity. Acquiring additional resources
> can fail explicitly.

This resembles proven indexing: an existing array and a valid index establish
that access is permitted. Acquired storage and a bound on its use could establish
that a call or construction needs no resource-failure alternative.

Conceptually, with explanatory notation rather than proposed Dewy syntax:

```text
acquire workspace for computation -> Workspace | ResourceUnavailable
run computation using workspace  -> Answer
```

The second operation is infallible only with respect to the covered resources and
under its input and capacity contracts. Other declared failures remain possible.
Workspace could include stack and temporary/object storage; it is not necessarily
one contiguous allocation or a programmer-visible parameter on every helper.

The compiler might infer a constant requirement for a fixed computation, or a
requirement parameterized by input size. Acquisition could occur at task startup,
request admission, or preparation for an algorithm. Many small allocations could
share one acquisition check and resource proof. Embedded execution might instead
establish capacity through its configured memory layout.

Accounting must respect simultaneous use: a resource cannot be promised twice,
active recursive callers retain their storage, and concurrent tasks need valid
partitions or a coordinated allocation mechanism. Lifetimes, alignment, storage
reuse, result escape, and ownership all affect what capacity is really available.
Successfully returning an object must not leave it in a released workspace.

Whether this can usually be inferred, whether explicit capabilities are needed,
and how resource ownership survives copying and calls are open questions. Acquiring
all capacity up front can also waste memory or reject work that would fit in its
actual execution; conservative reservation has a cost of its own.

## What static stack analysis could establish

For a closed acyclic call graph with bounded per-function stack use, a conservative
bound is essentially a longest-path calculation:

```text
needed(f) = own_stack_bound(f) + max(needed(each possible callee))
```

This simplified formula assumes consistent accounting for calls and frames.
Sequential calls do not all remain active together. A more precise analysis can
use the caller's live stack at each call site instead of its overall local peak.

Backend accounting must include alignment, saved registers, argument areas,
expression temporaries, return storage, and compiler-generated calls. Source-level
facts can supply size and depth bounds, but source locals alone do not determine
machine stack usage. Dynamic stack allocation can accumulate inside loops even
without recursion. Foreign or indirect calls need sound summaries or conservative
target sets; unresolved calls cannot simply contribute zero.

Promising recursive cases include bounded decreasing integers, bounded tree or
parser nesting depth, and divide-and-conquer with a proven size relationship.
Guaranteed tail calls can prevent frame accumulation, but must be guaranteed in
every supported build mode when correctness relies on them, including relevant
cleanup and lifetime behavior. Proving termination alone does not prove that the
stack fits: a finite list can still exceed the available recursion depth.

Diagnostics should distinguish **proven to fit**, **proven to exceed**, and
**not proven to fit**. A conservative upper bound above a budget does not prove an
execution exceeds that budget. Unknown bounds should identify the missing size,
depth, callee, or environmental assumption. A strict contract could reject an
unknown bound without falsely reporting inevitable overflow.

## Computations without useful static bounds

Possible mechanisms include checked recursive descent, growable stack segments,
or explicit/compiler-managed storage for pending work. Each needs a defined
failure path when capacity or further acquisition runs out. Growable stacks and
heap continuations move the limiting resource; they do not remove it.

A possible interface distinction is between operations that **run within supplied
resources**, whose implementations must meet that contract, and operations that
**may acquire or exhaust resources**, whose interfaces expose failure. Inference
could ease local code while published contracts stay stable. Losing a proof for a
fixed contract should diagnose that implementation, not silently change its public
result from `T` to `T | ResourceExhausted`. Exact inference and portability rules
are unresolved.

Dewy's current direction keeps errors in returned unions and separate from
effects; forwarding is not stack unwinding. An ambient resource-failure effect
handled at an outer execution boundary is another conceivable design, but would
be a substantive extension requiring explicit control-flow and cleanup semantics.
It must not be presented as already implied by Dewy's effects or error forwarding.
Ordinary error values plus coarse capacity acquisition are a candidate that stays
closer to the existing direction. How much propagation burden remains needs to be
tested on real programs.

In either approach, checks must precede consuming capacity needed for failure
handling. Reserve or prove enough space for error construction, returns, cleanup,
and any permitted recovery. Catching an already-exhausted native stack is not a
complete recovery design. Guard pages and stack probing can prevent corruption
but do not by themselves satisfy the no-hidden-abort rule. FFI and cleanup that
allocate or recurse need explicit treatment. Recovery need not undo prior side
effects, but must preserve the language's validity and lifetime guarantees.

## The environmental boundary remains open

“Within the program's sphere of influence” is a useful starting point, but calling
all resource limits external would conceal failures generated code can control.
A candidate distinction is:

| Situation | Possible responsibility |
| --- | --- |
| External termination, hardware failure, or an environment that stops honoring its execution guarantees | Outside the continued-execution guarantee, with assumptions stated explicitly |
| A request for more resources is refused | Explicit failure value |
| Execution would exceed resources already assigned to it | Prove impossible, or detect before crossing the limit and return failure |

An OS-chosen stack limit does not make uncontrolled recursive stack exhaustion
equivalent to an external kill. Conversely, a language cannot guarantee continued
execution after the environment forcibly terminates it.

Target ABI knowledge gives layout rules, not a universal usable stack budget.
Thread configuration, entry from foreign code, asynchronous activity, and runtime
overhead affect availability. Reserving virtual address space need not establish
that future backing-memory requests will succeed. Any acquisition guarantee must
state what the target actually provides and what remains an environmental
assumption. Startup failure before application code has resources to run also
needs an explicit place in this model.

One possible refinement of the aspiration is: **no runtime safety checks where
static proof and established capacity suffice; explicit resource failure where
additional capacity is needed; stated assumptions about continued execution.**
Whether to adopt that wording, where failures must be handled, and which resource
guarantees belong in ordinary Dewy versus a stricter execution profile remain open.

## Useful references and evaluation cases

- [GNATstack examples](https://docs.adacore.com/live/wave/gnatstack/html/gnatstack_ug/Examples.html)
  illustrate call-chain accounting and incomplete bounds from cycles, dynamic
  frames, and missing call information.
- [Clang's `musttail`](https://clang.llvm.org/docs/AttributeReference.html#musttail)
  illustrates guaranteed tail calls and the constraints such a guarantee needs.
- [Linux thread creation](https://man7.org/linux/man-pages/man3/pthread_create.3.html)
  and [Windows thread stack size](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-stack-size)
  describe configuration and reservation/commitment considerations.
- [GCC instrumentation options](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html)
  distinguish stack checking and stack-clash protection from a recovery contract.

Evaluate candidate designs against small object-heavy helpers, bounded and
unbounded parsers, recursive tree traversal, big-integer arithmetic, reusable
library callbacks, concurrent tasks, and foreign entry points. Compare source
noise, inferred proofs, failure visibility, generated checks, reserved memory,
and behavior across build modes and targets. Reporting stack use and unknown
boundaries could be useful before any particular language policy is chosen.
