# Parallel v3: three soundness checks

- Scope: static review of proposal-v3 §§3, 4 and 6, D4, `safety_and_concurrency.md` (including its decided rules and implementation limitations), `multi_expressions.md`, and the relevant `LANGUAGE.md` rules. The channel outcome definitions were also checked in `lib/prelude/outcomes.jo` and `channels.dewy`.
- The approved direction is retained: every top-level statement is an item; later items wait for earlier items' data. Examples describe proposed semantics, not claims that today's compiler implements v3. Deliberately rejected programs are identified. No compiler run or throughput measurement is claimed.

## 1. Block dependency graph

- **Verdict: unsound as an unconditional sequential-value promise; sound with the qualifications and analysis requirements below.** Forward edges order ordinary conflicting accesses, but handle observations affect values, failure changes which items execute, and a data DAG is not a proof of deadlock freedom. These are distinct issues from memory safety.

### Handle observations already defeat the literal promise

```dewy
main = () => {
    let counter = atomic(0)
    parallel {
        counter.store(1)
        let seen = counter.load
    }
    printl(seen)
}
```

- Sequentially `seen` is 1; concurrently it may be 0. Atomic access is race-free and intentionally creates no dependency. Calling the store an interleaving “effect” does not make the load's ordinary integer result deterministic. Mutex reads, channel receives, file reads and clocks have the same issue; arithmetic depending on their results inherits it.
- **Fix:** promise source-order equivalence for ordinary storage accesses, with handle/external observations supplied as nondeterministic inputs, on normally completing executions. Equivalently, a block free of such observations and early exits has sequential results, assuming deterministic ordinary operations. Do not promise that handle-derived values match an actual sequential run. This wording preserves the approved semantics and needs no new analysis or taint pass.
- A handle *payload operation* creates no automatic wait. Reading, replacing or constructing the ordinary binding containing a handle still participates in dependencies. A later operation cannot start before the item that creates its handle has completed.

### Places, element fields and method receivers

```dewy
main = () => {
    let xs = [0 0]
    let p = @xs[0]
    parallel {
        p = 7
        let seen = xs[0]
    }
    printl(seen)
}
```

- Sequential `seen` is 7. Comparing names `p` and `xs` misses the conflict. Resolve `p` to its canonical root and frozen selector, `xs[0]`, and add the write/read edge. The selector was evaluated when the place was made, not when each item runs.
- **Existing restriction:** places are not ordinary `Send` values; current parallel/task capture rules conservatively reject shared places. They must not simply be disabled for v3. Accepting this example needs a scoped-place rule whose lifetime and ordering are proved by the block and its join. Until then, rejection is safe.

```dewy
Cell:type = [n:int64]
bump = (@n:int64):>void => { n += 1 }
probe = (i:int64 j:int64):>void => {
    $runtime_checks
    let rows = [Cell[0] Cell[0]]
    parallel {
        bump(@rows[i].n)
        let seen = rows[j].n
    }
    printl(seen)
}
main = () => probe(0 0)
```

- Instantiate `bump`'s write summary at `rows[i].n`; compare it with `rows[j].n`. Unless `i != j` is proved, add a dependency (or retain the current conservative rejection). Do not interpret failure to prove equality as disjointness. Bounds checks alone prove no disjointness. Include reads computing `i`, `j`, receivers and lengths.
- Parent replacement, resizing, element removal, destruction and copy-on-write detachment must be modeled at their relevant owner/storage root. Separate element fields do not make concurrent structural mutation safe. COW implementation bookkeeping must itself support any disjoint access the checker accepts.

```dewy
Counter:type = [
    n:int64
    signal:Atomic<int64>
    bump = ():>void => {
        n += 1
        signal.store(n)
    }
]
main = () => {
    let counter = Counter[0 atomic(0)]
    parallel {
        counter.bump
        let seen = counter.n
    }
    printl(seen)
}
```

- A record containing a handle is not exempt as a whole. The method writes ordinary `counter.n`; the second item must wait. Only the operation on `signal`'s shared atomic payload is exempt. Conversely, two copied records with ordinary fields have independent value semantics; physical COW sharing does not make them semantic aliases.
- **Fix:** method receiver paths and implicit calls are part of the read/write summary. `Send`/`Sync` establishes transfer/sharing safety, not sequential ordering. An arbitrary method or user-defined “handle-like” record cannot opt out of dependencies merely because it is `Sync`.

### Closures and globals

```dewy
main = () => {
    let x = 0
    let set = ($capture @x):>void => { x = 1 }
    parallel {
        set
        let seen = x
    }
    printl(seen)
}
```

- The call writes captured `x`, even though its surface mentions only `set`. Existing race checks reject this shared captured write; unknown callable targets are also conservatively rejected. If v3 accepts it, substitute the closure's captured-place summary into the graph. An unresolved callable is not effect-free: conservatively order all possible affected places or reject it.
- A closure with private mutable state instead writes its own closure environment; repeated calls on the same closure place need ordering. Passing that closure by value gives an independent copy under the existing rules. Do not confuse the two cases.

```dewy
main = () => {
    let x = 0
    parallel {
        x = 7
        let read = () => x
        let seen = read
    }
    printl(seen)
}
```

- `read` snapshots `x` when the closure is constructed. That construction reads `x`, so it waits for the assignment; `seen` then waits for `read`. The expected value is 7. Capturing every item's inputs at block entry would incorrectly freeze 0 before the dependency is satisfied. Initialize an item's captures/arguments at its activation, after its predecessors, while accounting for those evaluations as accesses.

```dewy
let global_count = 0
set_global = ():>void => { global_count = 1 }
read_global = ():>int => global_count
main = () => {
    parallel {
        set_global
        let seen = read_global
    }
    printl(seen)
}
```

- Existing transitive race checks reject the global write; waiting-lane tasks also cannot read an unsynchronized mutable global while their parent runs. This is not an accepted counterexample to today's checker.
- If the new scoped block permits this program, `set_global` must summarize `W(global_count)` and `read_global` must summarize `R(global_count)`. The same applies through callbacks, operators, indexing, formatting and lifecycle hooks. Keeping the current rejection is a valid initial implementation. Merely relaxing the old write prohibition and looking at item syntax is unsound.
- The block DAG cannot order an unrelated task or thread accessing that global. Such outside access still needs the existing race-safety proof or synchronized storage. The block's own join is insufficient.

### Completion, publication and cancellation

```dewy
Failed:type = type of error
reject = ():>void | Failed => Failed
main = () => {
    let x = 0
    parallel {
        {
            x = 1
            reject or_throw
        }
        let seen = x
        printl(seen)
    }
}
```

- The first group is one item. Its write to `x` must not release the second item early: it subsequently fails. **Fix:** dependencies wait for successful completion of the entire predecessor, including required cleanup, not for a declaration/write becoming locally available. Publish binding/result availability with the completion event; a failed/canceled predecessor never satisfies its dependents. Completion publication needs an ordinary happens-before relationship.
- An item cannot later be “canceled” after it has successfully completed and released a dependent. Its completion is final. A dependent of a successfully completed item may already be running when an *independent* sibling fails; it is then subject to cancellation and joining. No rollback is implied.

```dewy
Failed:type = type of error
reject = ():>void | Failed => Failed
run = (@x:int):>void | Failed => {
    parallel {
        reject or_throw
        x = 1
    }
}
main = () => {
    let x = 0
    let result = run(@x)
    printl"{result} {x}"
}
```

- Under the proposed permission for ordered scoped places, the independent assignment can run before failure is observed: `x` can become 1. Sequential execution fails before assigning it. Existing capture restrictions may reject the program today; if accepted in v3, cancellation does not undo it. Two independent failing items can likewise return a different first error from sequential source order.
- **Fix:** explicitly exclude early-exit executions from the sequential-result claim. On failure, stop activation of pending work, request cancellation of running siblings, join them and leave the enclosing function. Serialize the transition from pending to running against cancellation; an item already running may finish under §5. All pending items must become canceled/skipped terminal nodes so joining does not await work that can never start. Do not expose uninitialized post-block bindings on the failing path.
- Exact sequential failure prefixes would require additional control ordering or transactional publication of ordinary writes, not just the proposed dependency rule. Neither follows from `or_throw` or structured joining.

### A forward DAG can deadlock

```dewy
main = () => {
    let ch = channel<int>(1)
    parallel {
        let x = ch.receive ?? 0
        ch.send(x);
    }
    printl(x)
}
```

- Item B cannot start until A produces `x`; A waits for the only send, in B. The scheduling graph is the forward edge A → B. The *wait-for* graph has B → A for completion and A → B for the channel. It cycles. Sequential execution also deadlocks; the example refutes “forward edges imply deadlock freedom,” not sequential equivalence.
- Today's old nonblocking parallel lane rejects the receive. That is not an answer under approved C1, which permits waiting. The documented channel analysis understands spawned-task joins, but does not yet document the new block-item completion nodes. Feed these nodes and their wait edges into the same channel/lock analysis. Reject a demonstrated closed cycle like this one. Capacity, alternate senders, close, branching, cancellation and `select` alternatives matter; “contains a cycle” in an overapproximation is not automatically a proof of deadlock.
- The documented ordinary analysis has unresolved cases and known coverage gaps (fields/containers, recursive expansion, later receives, multiple drainers). It warns in unresolved cases; it does not prove every program deadlock-free. Under `$no_deadlocks`, require certificates for dependency waits as well as channels, locks and joins; unknown cases are errors. A forward completion edge is not a certificate independent of the producer's own waits.
- V3's claimed error for a close unordered with sends is an additional protocol rule to implement. It is not established by the existing documentation's deadlock-cycle checks: an early close can terminate operations without deadlocking.

### Fixed graph rule and compile cost

- For each item, obtain conservative ordinary-place read/write sets, including transitive calls, receiver/index evaluation, closure construction, captures, moves and cleanup. Resolve aliases to roots plus routes. For `i < j`, order `i` before `j` whenever they may overlap and either writes, or `j` needs a binding initialized by `i`. This includes read-before-write anti-dependencies and write-before-write dependencies. Unknown aliasing must not silently remove an edge. Honor existing transfer, lifetime and external-sharing checks separately.
- With all conflicts ordered and ordinary operations deterministic, adjacent independent operations commute; any successful schedule can be rearranged to source order without changing ordinary results. This argument fails for the intentionally unordered handle observations and abnormal exits discussed above.
- Let `N` be relevant checked nodes, `A` summarized access occurrences, `P` indexed places, `K` candidate alias comparisons, `E` emitted dependency edges, and `C_alias` the bounded cost of an alias query. An indexed design costs approximately `O(N + A log P + K·C_alias + E)`, **plus interprocedural summary propagation**, with `O(A + E)` graph storage. A naïve all-item-pairs implementation is quadratic; alias-heavy code and explicitly expanded graphs can still have quadratic output. Forward scheduling itself costs `O(items + E)`.
- Use root/path indexes, last-writer/read-frontier dependencies and cached disjointness facts; fall back to conservative root-level ordering when precise path expansion exceeds a budget. This sacrifices parallelism rather than soundness. Resolve recursive summaries monotonically with widening to a conservative “unknown” footprint when needed; never treat an iteration limit as a completed proof. The cost depends on summary size and propagation count, not just the number of function bodies.
- **Demand-driven:** no block-graph machinery without a block-form `parallel`; summarize only reachable callees needed by those items and reuse per-instance summaries. Start wait analysis only when relevant waits exist; certificates only when requested. The current documented channel analysis is already `O(W²)` for a task's waits and `O(V(V+E))` per cycle-search round. Do not present reusing it as a linear-time or free extension. Batch SCC checking can find cycles in `O(V+E)` after edges exist, but does not make constructing/proving those edges free.
- **200–250k lines/s:** no measured cost is available from this review. The acceptance requirement is demand-triggered summaries, bounded conservative fallback and instruction-count measurements on the existing flagship panel before landing. No whole-program alias solver should be introduced for this rule.

## 2. `?? void` in collectors

- **Verdict: sound with fixes.** Filtering fits the existing multi-expression model. The proposal's blanket “statement” permission and inferred-function prohibition do not follow from that model. Value type and number of expressed values must be separate.

### Nested collectors, block bodies and optionals

```dewy
maybe = (keep:bool):>int? => if keep 7 else none
main = () => {
    let flat = [{ maybe(false) ?? void 9 }]
    let nested = [[maybe(false) ?? void] [maybe(true) ?? void]]
    let parallel_flat = [parallel keep in [false true] {
        maybe(keep) ?? void
        9
    }]
    let retained:array<int?> = [maybe(false) maybe(true)]
    let filtered:array<int?> = [maybe(false) ?? void maybe(true) ?? void]
    printl"{flat} {nested} {parallel_flat} {retained} {filtered}"
}
```

- `flat` is `[9]`; braces forward values to the enclosing collector. `nested` is `[[] [7]]`: an inner `[...]` produces one array value even when empty; it is not flattened or discarded. `parallel_flat` is `[9 7 9]` in input/item order, not `[ [9] [7 9] ]`.
- `retained` contains `none` and 7. `filtered` contains only 7, even though its expected element type is optional. An expected `array<int?>` permits `none`; it does not reverse an explicit filter. Conversely, without `?? void`, a collector must never silently discard optional values.
- An optional *array* filtered by `?? void` contributes a present array as one value, including a present empty array. No implicit spread occurs.

```dewy
Bad:type = type of error
Other:type = type of error
sample = (which:int):>int | none | Bad | Other => {
    if which =? 0 return none
    if which =? 1 return Bad
    if which =? 2 return Other
    return 7
}
main = () => {
    let only_bad:array<int | none | Other> = [loop i in [0..4) sample(i) ??<Bad> void]
    let bad_and_none:array<int | Other> = [loop i in [0..4) sample(i) ??<Bad | none> void]
    let all_failures:array<int> = [loop i in [0..4) sample(i) ?? void]
    printl"{only_bad} {bad_and_none} {all_failures}"
}
```

- Results: `[none Other 7]`, `[Other 7]`, `[7]`. `??<Bad> void` does not drop `none` or `Other`. Use the existing `??` classification of **exceptions, including `none`**, not just descendants of `error`: `Closed` and `Unsent<T>` are exceptions too. Explicit filters still reject a listed kind the operand cannot hold, as the existing rule requires.

### Precise typing and sink rule

- Check the left operand once as an ordinary optional/exception-bearing result; use the existing exception-alternative narrowing, including nominal families and concrete generic exception instances. Do not first coerce away its failures using the collector's expected element type.
- Let `V` be its possible expressed-value alternatives, and let `Z` record whether it can normally express zero values (for example a `void | E` operation). For plain `?? void`, let `F` be all exception alternatives of the operand, including `none`; for `??<E> void`, let `F` be the alternatives matched by `E`. This is a type-checker operation, not new Dewy syntax.
- On an `F` alternative, express zero values and continue normally. On any other value alternative, express that same value. A preexisting void success remains zero values. `never` still exits its path. Thus the output element alternatives are `V \ F`; possible normal counts include zero if `Z` or a filtered alternative is reachable, and one if a retained value alternative is reachable. `void` is **not** an array element, `none`, or a runtime union payload. This rule filters a single operation result, not each value of an arbitrary multivalue group; such a group must be iterated/collected explicitly.
- Allow the result wherever the existing sink accepts its count and element types: a collector, an inferred variable-count body, a drop sink, or a written-void sink **only if it expresses no values on every normal path**. A block nested in a collector inherits that collector sink until another collecting/one-value construct intervenes.
- A fixed-count binding, positional argument expansion, named argument, operand, index, condition, or written one-value result cannot accept a possibly missing value. An explicit attached `;` discards all outputs and is valid in a void statement position. The proposal incorrectly calls every binding/argument a “one-value” place: some accept several values, but their counts must be fixed, which still excludes a 0-or-1 filter.
- Infer a collector's element type from all **retained** contributions using the existing collector common-type/union and conversion rules. Filtered alternatives add no element constraint. Apply an expected `array<U>` to those surviving values. Typed but possibly empty contributions still supply their surviving static type; an actually empty execution does not erase it. If every contribution is statically filtered and no other type evidence exists, require an annotation just as for `[]`; do not invent `array<void>`. Type/cardinality inference must not speculate about how many parallel items actually run.

```dewy
maybe = (keep:bool):>int? => if keep 7 else none
filtered = (keep:bool) => maybe(keep) ?? void
conditional = (keep:bool) => if keep 7
bad = ():>void => { maybe(true) ?? void }
main = () => {
    let a = [filtered(false) filtered(true)]
    let b = [conditional(false) conditional(true)]
    printl"{a} {b}"
}
```

- The intended rejection here is `bad`: it can express 7 despite its written `:>void`. Being syntactically a statement does not discard the successful value. Its fix is `maybe(true) ?? void;` (or simply discard the original expression if neither outcome matters).
- Under the decided multi-expression rules, `filtered` and `conditional` both express a variable number of integers; their collected results are both `[7]`. V3/D4 specifically prohibit the first inferred body, while permitting the equivalent `if`. That exception is type-safe but is a new syntactic restriction, not “no new context rule,” and braces must not accidentally bypass it. **Recommended correction:** drop that provisional exception and use existing count-carrying function types. If D4's exception is retained, document it explicitly as a policy deviation applying through transparent nesting; it is not required for soundness.
- An inferred helper expressing 0..1 values is not an optional-returning helper. Its callable type retains the varying count, so a call through `@filtered` is collected, not accepted as one optional argument. That preserves substitution invariance.
- **Compile cost:** reuse existing sink/count bookkeeping; one exception-partition operation per filtered expression and ordinary collector type joins. With interned union alternatives this is linear in the alternatives visited, cached where appropriate. No global flow, alias, or parallel-specific typing pass is needed. Accumulator allocation is a runtime collector concern. Ordinary code without a filter incurs no new analysis pass; throughput still needs measurement before landing.

## 3. `select` typing

- **Verdict: sound with fixes.** The proposed unions can be type-safe, but the stated positional-pair check is insufficient to guarantee that a result identifies the winning alternative. Typed rest parameters alone also do not make arbitrary function handles selectable.

### Exact result rule

- Define an operation's selected outcome separately from its ordinary callable return type: receive on payload `T` contributes `R = T | Closed`; send contributes `R = Sent | Unsent<T>`. Sending success is deliberately reified as nominal `Sent`; it is not a value of type `void`.
- For positional operation `i`, contribution `B_i = R_i`. For uniquely named operation `name`, contribution `B_i = [name: R_i]`, one exact one-field record. The result is the normalized union of every `B_i`, plus top-level `Canceled`, plus `Timeout` when the timeout option can be a duration. Omitted timeout or statically `none` adds no `Timeout`; a runtime `Duration | none` adds it. `ties` does not alter the type.
- Genuine select cancellation produces top-level `Canceled`, not `[name: Canceled]`. A *payload* whose type contains `Canceled` is still payload, and in a named receive remains inside its record. This requires operation-level status provenance; subtracting `Canceled` from an ordinary return union erases valid payloads. Select must distinguish a received payload from a canceled receive internally.
- `Unsent<T>` remains the documented nominal generic exception carrying `.value:T` and `.reason:Full | Closed | Busy | Canceled`. A union inside `T` does not distribute the wrapper. A selected send failure may carry that wrapper; selection cancellation has its separate top-level alternative. Specify the commitment point so cancellation never turns a committed successful send into an apparent undelivered value.
- “Exactly one operation” means one committed selected operation on an operation-result path; zero on timeout/cancellation. Registering losers must not consume their receive values or deliver their sends. A close outcome is also a selected operation outcome, even though it transfers no payload.

### Small complete examples and their exact types

```dewy
one = (c:Channel<int>) => select(@c.receive)
timed = (c:Channel<int>) => select(@c.receive timeout=1s)
named = (a:Channel<int> b:Channel<string>) => select(left=@a.receive right=@b.receive)
send_union = (c:Channel<int | string> value:int | string) => select(@c.send(value))
mixed = (a:Channel<int> b:Channel<string>) => select(@a.receive @b.send("x"))
main = () => {
    let c = channel<int>(1)
    c.send(7) or_throw
    printl(one(c))
}
```

- `one`: `int | Closed | Canceled`.
- `timed`: `int | Closed | Timeout | Canceled`.
- `named`: `[left: int | Closed] | [right: string | Closed] | Canceled`.
- `send_union`: `Sent | Unsent<int | string> | Canceled`, **not** `Sent | Unsent<int> | Unsent<string> | Canceled`. The different generic wrappers are not interchangeable.
- `mixed`: `int | Closed | Sent | Unsent<string> | Canceled`; its two operation contributions are disjoint.
- These are static signature results. They do not remove `Closed` just because a particular caller has not closed the channel.

### Generic unions, duplicate names and hidden collisions

```dewy
receive_any = <T>(c:Channel<T>) => select(@c.receive)
main = () => {
    let c = channel<Closed>(1)
    c.send(Closed) or_throw
    printl(receive_any<Closed>(c))
}
```

- Instantiating `T = Closed` normalizes `T | Closed | Canceled` to `Closed | Canceled`. This is a sound value type, but cannot distinguish a `Closed` payload from the channel-close outcome. That ambiguity already exists in `Channel<T>.receive`; naming a wait only distinguishes *operations*, not those two outcomes inside one operation. If the intended contract includes distinguishing payload from closure, require `T` disjoint from `Closed` or change the channel outcome representation; neither follows from adding named waits.
- A generic type variable is never proof of disjointness from `Closed`, `Sent`, another type variable, or a record. Two positional receives are rejected even for `Channel<int>` and `Channel<string>`, because both can return `Closed`. Two positional sends are rejected regardless of their payloads because both can return `Sent`.

```dewy
ambiguous = (a:Channel<int> b:Channel<string>) => select(@a.receive @b.receive)
duplicate = (a:Channel<int> b:Channel<string>) => select(reply=@a.receive reply=@b.receive)
main = () => printl"these declarations must be rejected"
```

- Reject duplicate keyword labels before constructing the union; their `Closed` fields overlap anyway. Do not silently overwrite or merge them. `timeout` and `ties` are reserved option names, not arbitrary operation labels.

```dewy
Reply:type = [reply:int]
ambiguous = (a:Channel<Reply> b:Channel<int>) => select(@a.receive reply=@b.receive)
main = () => printl"the mixed positional and named collision must be rejected"
```

- The positional receive can yield `[reply: int]`; the named receive can yield the same record. V3's positional-pair rule checks nothing here. **Fix:** require pairwise distinguishability of **all operation contributions**, including positional-versus-named, and of positional contributions versus the control outcomes. Distinct exact one-field labels distinguish two named contributions even when their payload types coincide. Use actual type/match identity rules, not implicit-conversion possibility, to determine overlap.

```dewy
timeout_payload = (c:Channel<Timeout>) => select(@c.receive timeout=1s)
cancel_payload = (c:Channel<Canceled>) => select(@c.receive)
safe_timeout = (c:Channel<Timeout>) => select(message=@c.receive timeout=1s)
safe_cancel = (c:Channel<Canceled>) => select(message=@c.receive)
main = () => printl"name payloads that collide with control outcomes"
```

- Reject `timeout_payload` and `cancel_payload` under the strengthened origin-distinguishability rule: even a single positional wait collides with a control outcome. The loose value unions alone would be type-safe, but could not say which event happened.
- `safe_timeout`: `[message: Timeout | Closed] | Timeout | Canceled`.
- `safe_cancel`: `[message: Canceled | Closed] | Canceled`.
- A positional `Channel<Timeout>` without a timeout option has no timeout-control collision, so its result `Timeout | Closed | Canceled` is valid: `Timeout` then denotes payload. A named result containing `Timeout` is distinct from top-level `Timeout`.

```dewy
choose = <T>(a:Channel<T> b:Channel<int>) => select(@a.receive @b.send(1))
main = () => printl"choose needs a per-specialization disjointness check"
```

- For `T = string`, `choose` returns `string | Closed | Sent | Unsent<int> | Canceled`. For `T = Closed`, it returns `Closed | Sent | Unsent<int> | Canceled`; still distinct between operations. For `T = Sent`, reject it because either operation can produce `Sent`. For `T = Sent | string`, reject for the same reason. For `T = Canceled`, reject the top-level cancellation collision. `T = Unsent<int>` collides with the other operation's failure wrapper.
- Named waits remove these cross-operation collisions: `select(read=@a.receive write=@b.send(1))` returns `[read: T | Closed] | [write: Sent | Unsent<int>] | Canceled`, subject to the existing `Send` requirements. It still does not distinguish a `Closed` payload from a closed read internally.
- **Decidability:** Dewy specializes generics, so discharge overlap obligations per concrete instance, caching the normalized signature. A reusable unspecialized API must retain a disjointness requirement in its signature or reject an unproved instance; treating `T` as a fresh disjoint nominal type is wrong. For refinements/recursive structures, use a terminating conservative relation `disjoint / overlaps / unknown`; unknown requires names or a proof, not acceptance. Exact semantic intersection of arbitrary predicates is not required or promised.

### What ordinary library implementation actually needs

- A heterogeneous typed rest pack, not `array<one common callable type>`: each entry retains its concrete operation type, result/payload type, optional compile-time name, ownership and original argument order. Named capture must preserve duplicate-name diagnostics and exclude the explicit keyword-only options.
- Generic compile-time traversal of that pack; result-type construction (union fold, name-indexed one-field record construction, conditional `Timeout` inclusion); type inspection and disjointness constraints with call-site errors. Merely accepting arbitrarily many homogeneous parameters is insufficient. Ordinary named-argument lowering must not erase the labels before this computation.
- A constrained operation-handle representation/protocol identifying channel/queue send and receive, their bound receivers, payloads and ownership. Function type `():>T | Closed | Canceled` alone is not evidence that a handle is a channel receive. An ordinary function with that signature could do arbitrary effects. Type erasure must either retain the selectable capability or make the handle ineligible.
- Library-accessible registration/readiness/commit/unregister primitives with one shared selection token, preserving losing-send ownership and never consuming losing receives. Running all handles and canceling losers implements `race`, not `select`. The supplied arguments and bound payload expressions are evaluated once in source order; delaying the operation does not authorize silently dropping those evaluations.
- Existing library methods are not generally first-class handles yet (`LANGUAGE.md`, records/methods). General bound-method handles and partial applications must preserve their operation identity/capability. This is another general prerequisite beyond rest parameters. A private generic operation representation can be a library implementation detail; erasing the public name `Op<T>` does not remove that requirement.
- The wait/certificate analysis must understand alternatives and commitment rather than model every registered operation as a mandatory wait. The existing `$no_deadlocks` documentation explicitly does not yet certify `select`. Until certified, rejecting it under that setting is sound.
- **Compile cost:** for `k` waits with `M` normalized union alternatives, pack folding/name checks are linear in pack/type size with interned labels; naïve cross-contribution overlap checking is `O(M² · C_overlap)`. Bucket by nominal identity and exact record labels, memoize type-pair queries, and use bounded conservative structural/refinement checks. Preserve nested record unions rather than distributing products into exponential combinations. Specialized packs add ordinary per-instantiation cost. Run this only at `select` instantiations (or other library pack constraints that request it), not across every call. No throughput figure follows from these asymptotics; measure on the flagship panel before claiming compatibility with 200–250k lines/s.
