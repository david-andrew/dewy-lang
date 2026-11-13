# Inspecting a callable: round 1

Status: proposed language/library contracts, not implemented or accepted. Read round 2 and round 3 for amendments. The examples use proposed modules and are design specimens, not compiler-tested programs.

## Four minimal uses

Each operation is inside its enclosing function; nominal types remain at module scope.

```dewy
import p"@lib/std/database.dewy" as database
Account:type = [id:string balance:int]
const schema = [accounts=database.collection<Account>(key=(a) => a.id
    indexes=[database.index((a) => a.balance)])]
main = () => {
    let db = database.open(schema p"accounts.db") or_throw
    let rows = db.accounts.where((a) => a.balance <? 0).all or_throw
    loop a in rows { printl(a.id) }
}
```

The lambda receives an Account and returns bool. A library recognizes a field comparison and creates an index plan; unknown code remains ordinary Dewy. A missing or incompatible index warns and scans. The balance index must not change primary-key result order.

```dewy
import p"@lib/std/compute.dewy" as compute
Word:type = uint32<overflow='wrap'>
main = () => {
    let pixels:array<Word> = [1 2 3 4294967295]
    let adjusted = compute.map(pixels (x:Word):>Word => x*3+1) or_throw
    printl(adjusted)
}
```

`compute.map` is a proposed ordinary library API: an independent CPU array in and out, a GPU kernel internally when exactly equivalent, an ordinary CPU map otherwise. The first pilot uses wrapping words deliberately. It does not reinterpret today's `gpu` upload or quietly convert float64 to float32. Device and allocation failures remain values where the selected resource policy requires them.

```dewy
import p"@lib/std/check.dewy" as check
check_invoice = (subtotal:int tax:int paid:int) => {
    check.that(() => subtotal + tax =? paid) or_throw
}
main = () => check_invoice(100 20 119) or_throw
```

On failure, the test library reports the comparison and its evaluated operands, e.g. `subtotal + tax =? paid; left=120; right=119`. It never repeats a call to obtain a nicer message. This is a test assertion returning an error value, not a replacement for the compiler's fact-producing `$assert` or `$runtime_assert`.

```dewy
import p"@lib/std/diff.dewy" as diff
main = () => {
    let slope = diff.derivative((x:float64):>float64 => x*x+3.0*x)
    let at_two = slope(2.0) or_throw
    printl(at_two) # 7.0
}
```

The derivative library builds and evaluates a mathematical derivative graph. It does not substitute a derivative for the caller's original function. Supported primitives have documented differentiation rules; unknown calls cause a compile diagnostic, never a finite-difference answer disguised as exact autodiff.

## Scope and acceptance

Owned files: this directory only. Budget: about three hours. Non-goals: implementing a compiler pass, database engine, GPU driver, complete AD system, new general macro syntax, repository edits, commits, or approving names.

Acceptance: one explicit typed inspection boundary; phase/capture/privacy rules; a real comprehension-to-planner path; unknown-code behavior; exact-result limitations; at least ten contextual programs; line-cited grades against six peers; researched prior art; and an explicit account of irreducible compiler support. A paper can meet these design deliverables without claiming the mechanisms exist.

## 1. The parameter type requests inspection

Provisional module `@lib/std/code.dewy` supplies `code.Function<F>`, where F is an ordinary function type. A library declares a parameter such as `predicate:code.Function<(Account:>bool)>`. The caller passes an ordinary lambda or `@named_function`. First the argument is checked against F with the same overloads, parameter types, refinements, effects and capture rules as any callback. Only then is its description attached. Account never becomes a symbolic proxy.

The wrapper contains two things in distinct phases:

- `body`: a compile-time-only immutable typed description, or an opaque reason when no body is available.
- `call`: the original executable callable, carrying the ordinary captured environment. `predicate.call(a)` is always available when F permits the call.

This is an intrinsic-backed library type, like type/field reflection, **not** a record userspace can implement from today's callable ABI. Users can implement their own planners, interpreters and wrappers over it. Reifying a function body itself requires the compiler. Saying otherwise would conceal precisely the missing facility.

No inspection metatag is added. A `$inspect` parameter tag would retain the function type but hide phase-specific members in an annotation; a `const` parameter would incorrectly imply runtime captures are compile-time values; quote/splice syntax would create another expression language. A wrapper type exposes the contract in signatures and can survive forwarding or storage.

A literal lambda can implicitly form Function<F> only at an expected Function<F> boundary. Both `f:F` and `f:Function<F>` overloads with otherwise equal rank are ambiguous: the compiler does not prefer inspection. Authors should publish one callback overload. The conversion must never repair an otherwise ill-typed lambda.

Ordinary inferred bindings retain provenance through aliases and generic forwarding. Explicit storage as F erases the inspection descriptor; converting back yields an opaque wrapper, not a whole-program decompilation promise. A dynamic function choice can use an opaque executable fallback. An explicit Function<F> local can retain a choice of descriptors for bounded specialization. These rules apply across modules as well as within one file.

## 2. What is described

Expose a versioned semantic representation after name/type resolution and before optimization. It is neither source tokens nor backend SSA. An indexed immutable graph retains source spans, resolved binding identity, result types, effect/cost summaries, selected semantic settings and ordered control edges. Optional source text is for diagnostics only, never for resolving names.

The initial node vocabulary covers parameters, literals, captured slots, local bindings, assignment, field/index reads, conversions, resolved operators, direct/indirect calls, short-circuit conjunction/disjunction, conditional/match branches, blocks, loops, return/throw and cleanup regions. Multi-values retain their arity. Unsupported newer forms are opaque nodes, not falsely simplified expressions. An inaccessible subtree is also opaque.

A field has its declared field identity and type, not just `"balance"`. A call has the selected callable identity and instantiated signature, not just `"sin"`. Overloaded `+` remains a call to that operation. Exact integer addition, wrapping addition, rational division and IEEE operations are distinguishable. `and`, `or` and `??` carry lazy edges. Defaults are explicit ordered evaluation nodes. Checked narrowing, allocations and cleanup are not erased.

Node identifiers are local to the descriptor and cannot be manufactured to name unrelated code. Child edges preserve scope; helpers cannot capture a caller variable by guessing a string. A library may copy descriptions into its own query/derivative data, but cannot mutate them, insert declarations, splice tokens, change bindings, or ask the compiler to compile arbitrary replacement Dewy.

A referenced function does not recursively disclose every callee's body. Public signatures and effect summaries are available; opening bodies follows ordinary visibility and explicit description availability. A library cannot walk the import graph for private implementation code merely because it sees a call. Unavailable calls are valid residual operations.

## 3. Captures and phases

Capture snapshots are taken when the lambda is created, as LANGUAGE.md:559–641 requires. Translation never reruns its construction. The body describes a runtime capture as a typed slot; compiling a query never reads the live threshold. The plan's comparison binds that slot when the recipe is formed and uses it when the recipe executes.

Literal constants may appear as typed constant nodes. `const` alone does not grant compile-time availability (LANGUAGE.md:516–542). Runtime `const threshold = input_int(...)` is still a runtime slot. Mutable shared captures, module mutable reads and stateful closure updates are represented honestly, and disqualify ordinary database predicates. Merely having a descriptor proves neither purity nor termination.

Runtime parameter values do not enter specialization keys. A loop creating 10,000 queries with different thresholds shares one body plan and has 10,000 ordinary binding environments. Copy/move/escape behavior of the wrapper is exactly that of its original callable; no extra copy of a move-only capture is introduced.

## 4. A conservative translation contract

A database library accepts only predicates already proved pure, deterministic and total under its public contract. Unknown arithmetic/call semantics, mutable captures, I/O and possible observable failures cannot be guessed away. Missing proofs diagnose the callback requirement and suggest an explicit ordinary loop after materialization.

For supported nodes, a comptime function builds ordinary plan data. A backend must implement each node's Dewy meaning, including exact int, optional values, text comparison and row order. Unsupported nodes remain local residuals. Translate a conjunct only if reordering it cannot skip an effect, failure or divergence. Limits, pages and aggregates remain after the residual stage where they occur in the reference evaluator.

A runtime optimization may choose among equivalent plans. A structural diagnostic names the unsupported expression and local work; execution explain reports the actual index/scan choice. A page size limits output, not scanning. The database's existing `max_scanned` proposal remains a separate service budget, not proof of bounded CPU, bytes or I/O.

The executable fallback is never recovered by interpreting an approximate tree: it is the original compiled callback. Fallback choice is made before execution, not after a partially completed effectful attempt. The API may have a strict operation for callers requiring translation; a default query should instead warn and run correctly.

## 5. Comprehensions need their own protocol

Inspection of `where` does not let an iterator see its caller's `if`. Propose **one new dunder metatag**, `$__collect__ = ...`, on a source type. It is an assigned function, matching the accepted dunder convention. It receives a typed collection recipe containing source identity, filter and projection Function wrappers, and returns a library execution plan or declines. The compiler uses the source's ordinary iterator if absent or declined.

Only an eager array comprehension with one by-value source and pure, total, single-valued filter/projection is eligible in the first contract. The compiler type-checks the ordinary loop first. No database names occur in this rule. A virtual array, persistent collection or remote table can use the same hook.

`[loop a in db.accounts if a.balance <? 0 a]` becomes a reference collection recipe with Account predicate and identity projection. The source expression evaluates once. At that same execution boundary a database source acquires one snapshot. The hook sees the filter at compile time, builds the same plan as `where`, and execution immediately yields the ordinary array in source order. It does not return a deferred query or change the type of `[]`.

For side effects, shared mutable reads, live `@source`, compound/nested loop headers, `break`, `continue`, nonlocal exits, mixed literal elements or multi-value yields, retain the original lowering. Emit a useful performance warning for a planning-capable source if its filter cannot be pushed; do not reject valid ordinary code because a planner is limited. Future extensions must preserve exact exit targets and collection multiplicity, not wrap arbitrary control flow in lambdas that retarget `return`.

This protocol is new compiler behavior as well as a library hook. Calling it an existing iterator method would be false: today's `next` contract (LANGUAGE.md:4781–4802) sees no filter or projection. Existing `iterable<T>` alone cannot supply one.

## 6. Assertions and differentiation without source generation

An assertion library can build a typed evaluator over supported pure expressions, recording each evaluated node once in evaluation order. It returns the ordinary bool and a failure report. Skipped branches have no values. A body it cannot instrument falls back to calling the original thunk once and reporting its source location/result, with a diagnostic about lost operand detail. Secrets retain redaction.

The AD library constructs its own typed derivative graph and an ordinary closure interpreting that graph. Constant graph specialization can remove interpreter dispatch later; no code-splice operation is needed for correctness. Unsupported operations fail at construction, because running the original function does not compute a derivative. Nondifferentiable runtime inputs yield a derivative-domain error. No silent numerical differencing.

GPU translation similarly emits backend program bytes as data and runs them through a library driver. Returning bytes is not inserting declarations into the caller. Exact-word operations form the first translation subset. Strict floating-point compatibility is a backend obligation, not an inference from the presence of a float type.

## 7. Safety, diagnostics and cost

Inspection runs in Dewy's pure compile-time evaluator: no I/O, environment access, host pointers, mutable global state, nondeterministic iteration or runtime local reads. Body access observes language visibility; a private node does not become public because the caller has permission to execute it. Runtime secrets must not enter diagnostic payloads or SQL source strings.

Demand reification only at inspection boundaries. Intern each semantic graph once per concrete instantiation, reuse child indices, and retain explicit opaque nodes rather than recursively expanding every call. Let N be exposed nodes plus edges: descriptor construction and one indexed traversal should be O(N) time and space. Optimizers must declare their own costs; exponential specialization is not permitted by this framing.

Use bounded planner work with warnings and ordinary fallback on exhaustion. The current comptime evaluator has no mandatory limit (LANGUAGE.md:5043); adding a limit specifically for optional planning requires an explicit contract, not a claim it already exists. Do not change unrelated demanded constant evaluation by accident. Details need the second pass.

Diagnostics should include call site, callback node, semantic reason, chosen fallback, and expected work. Example: `account_filter.dewy:12: exact integer operation not supported by backend; evaluate predicate locally; candidate count unknown; max_scanned bounds visits only`. A false “index used” guarantee is worse than a conservative warning.

## Prior art: borrow the useful boundary, not all its machinery

The judgments in the last column are design judgments for Dewy. Sources were read for this round; no comparative compiler benchmarks were run.

| Mechanism | What to borrow | What not to copy for this task |
|---|---|---|
| [C# expression trees](https://learn.microsoft.com/en-us/dotnet/csharp/advanced-topics/expression-trees/) and [restrictions](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/expression-tree-restrictions) | An expected parameter type lets an ordinary lambda arrive as typed data; executable/tree distinction is visible in API types. | Tree conversion excludes statement lambdas and many constructs. Dewy should retain opaque executable fallback rather than make all callbacks fit a frozen expression subset. |
| [LINQ provider fallback in EF Core](https://learn.microsoft.com/en-us/ef/core/querying/client-eval) | Separate server translation from local evaluation and explain the boundary. | EF rejects unsupported non-projection translation at runtime; its earlier broad client fallback could be unexpectedly expensive. Dewy needs earlier warnings plus explicit service budgets. |
| [Scala 3 quotes](https://docs.scala-lang.org/scala3/guides/macros/quotes.html) | Typed code and level consistency prevent reading runtime locals at compile time. | Quotes, splices and macro contexts are more machinery than an ordinary callback consumer needs; do not add all of staging to get a query predicate. |
| [Julia macros/generated functions](https://docs.julialang.org/en/v1/manual/metaprogramming/) | Ordinary-language metaprograms and cached type specialization. Generated functions are restricted to pure behavior and know argument types. | Parse-time macros do not know types; generated functions return code and have world-age/phase constraints. Avoid returning replacement Dewy ASTs and specializing on runtime captures. |
| [Zig comptime](https://ziglang.org/documentation/master/#comptime) and [branch quota](https://ziglang.org/documentation/master/#setEvalBranchQuota) | Reuse ordinary evaluation, type values and explicit work accounting. | Computing a function's output or reflecting its signature does not expose its body. Comptime alone is not the solution to this brief. |
| [Rust procedural macros](https://doc.rust-lang.org/reference/procedural-macros.html) | Explicit expansion boundaries and spans help tooling. | Token streams are not a typed callback body; proc macros are unhygienic and have host resources. Do not grant reflection libraries arbitrary build-time I/O or replacement syntax. |
| [Lisp quote](https://www.lispworks.com/documentation/HyperSpec/Body/s_quote.htm) | Suppressing evaluation gives program-shaped data with a simple model. | Quoted lists/symbols alone do not encode Dewy's resolved field identities, type obligations, effects or private authority. No new quotation punctuation is needed here. |
| [Python AST](https://docs.python.org/3/library/ast.html), [inspect](https://docs.python.org/3/library/inspect.html#inspect.getsource), [Pony queries](https://docs.ponyorm.org/queries.html) | Pony shows that native comprehensions/lambdas are an attractive query surface; Python exposes convenient tree traversal. | Recovering source/code at runtime is a weaker contract than compile-time typed identity; source availability and grammar versions matter. Do not depend on finding the caller's source file in production. |
| [Kotlin compiler plugins](https://kotlinlang.org/docs/custom-compiler-plugins.html) | Typed compiler integration can make rich library surfaces possible. | The documented plugin API is unstable and plugins can change resolution and generated code. A versioned restricted data interface is preferable to shipping a compiler plugin for each database. |
| [Swift result builders](https://raw.githubusercontent.com/swiftlang/swift-evolution/main/proposals/0289-result-builders.md) and [expression macros](https://raw.githubusercontent.com/swiftlang/swift-evolution/main/proposals/0382-expression-macros.md) | Builders translate structured blocks through library operations; macros have declared interfaces and syntax expansion. | Builders do not expose arbitrary typed expression internals; syntax macros and builder-specific control transforms would add more surface than these callbacks need. |
| [JAX tracing](https://docs.jax.dev/en/latest/jit-compilation.html), [control flow](https://docs.jax.dev/en/latest/control-flow.html) | An ordinary function can feed AD and accelerator libraries; traces are useful program data. | Tracing executes Python, misses ordinary side effects in the resulting graph, and dynamic branching requires constraints/special operations. Never run an unknown Dewy callback merely to discover it. |
| [Template Haskell](https://downloads.haskell.org/ghc/latest/docs/users_guide/exts/template_haskell.html) | Typed quotations make the staged result contract explicit. | Typed/untyped quotes, splices and declaration generation solve a much broader problem. Read-only inspection should not quietly approve that entire feature set. |

## Alternatives without inspection

**Typed field descriptors** are sufficient for equality/range/membership predicates, compound order and projection. Reflection can build a record whose `balance` member constructs a typed predicate using an ordinary method. This is the smallest useful database pilot and owns both the evaluator and plan. It does not satisfy the literal `a.balance <? 0` Account lambda/comprehension. Comparisons currently return bool (LANGUAGE.md:2440–2458), so a predicate-valued `<?` is not a free library trick. Dynamic filters from a UI naturally favor explicit descriptors even after inspection exists.

**Symbolic execution through overloading** works for straight-line generic numeric expressions whose operations accept a symbolic scalar. Forward dual numbers can provide useful AD with no body inspection. It does not transparently cover a function explicitly typed float64, real bool branches, short circuit, mutation or an opaque helper. Sampling branches is unsound. David's symbolic-type notes (discussion_points.md:1158–1191) explicitly recognize the value of a restricted symbolic domain; retain that complementary library path.

**Use existing GPU array fusion** for numerical elementwise kernels already expressible there. Inspection is not needed to justify every accelerator workload. However, LANGUAGE.md:3448–3450 permits CPU/GPU numerical differences, so it cannot establish this brief's strict equivalence guarantee.

**Caller explicitly passes a plan** when the program itself wants a dynamic query language. A lambda wrapper improves ordinary source ergonomics; it should not replace deliberate first-class predicate objects.

## What is actually new

| Candidate | Existing construct reused | New obligation |
|---|---|---|
| `code.Function<F>` | Function types, contextual lambda inference, handles, captures, generic specialization | Compiler-backed body provenance, safe conversion, static descriptor alongside runtime closure |
| Descriptor members/variants | Records, unions, indexed arrays, field reflection, compile-time loops | A stable read-only semantic schema and authority checks |
| `$__collect__ = ...` | Assigned dunder metatags, ordinary iteration/collection | General eager-comprehension protocol; filter/projection reach source planner |
| Query/AD/assert/GPU translators | Ordinary comptime/library functions, data structures, runtime executors | Libraries and backend conformance; no general Dewy AST compiler |

The earlier reflection design expressly excludes AST/source-generation macros (argparse_and_reflection.md:98–108). This proposal preserves that exclusion but adds typed code inspection, which is still a new language decision. The older exploratory snippet notes (discussion_points.md:2760–2798) are inspiration, not permission to implement quote/splice.

One intrinsic-backed library type and one dunder hook is the smallest candidate here that covers both literal callback and literal comprehension demands. It is not zero compiler support, and its privacy, validation and cost boundaries still deserve adversarial review.
