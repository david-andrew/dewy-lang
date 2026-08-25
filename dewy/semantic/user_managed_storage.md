# User-managed storage and lifecycle hooks

BLUF: Dewy should keep ordinary values on the compiler-managed static/arena/owned-storage path. As an explicit systems escape hatch, a library should be able to define resource-bearing value types such as `Rc<T>`, `Weak<T>`, `Arc<T>`, owning boxes, pools, and foreign handles. This needs a small unsafe allocation and lifecycle substrate; it should not make `@` into a general escaping pointer.

This document records a provisional direction, not settled surface syntax or an implemented feature.

## Relationship to value and place semantics

An `Rc<T>` is itself a Dewy value. Its representation will usually be a small handle to a separately allocated control block. Copying the `Rc<T>` value creates another handle to the same payload and retains that payload; releasing a handle decrements the count. Sharing the payload is therefore explicit in the type, even though ordinary assignment still has value behavior.

```dewy
let first = Rc.new([1 2 3])
let second = first          # copy the handle; retain the shared payload
```

The two bindings hold independent handle values. Rebinding `second` cannot rebind `first`, but both handles intentionally designate the same immutable payload. A structural object containing an `Rc<T>` field gets the same behavior recursively: copying the object retains that field's shared payload.

`@` has a different job. `@rc` selects the place occupied by the `rc` handle so a callee can replace that handle in the caller's binding. It does not by itself select or share the allocation behind the handle. Access to the payload should come from `Rc` operations which produce a lifetime-bounded read-only place, or a mutable place after proving that the allocation is uniquely held.

The compiler may reuse its place ABI internally when it passes source and destination storage to lifecycle hooks. That is a lowering convenience, not a reason to conflate these surface meanings:

- a place borrows existing storage and does not own it;
- an owning handle keeps an allocation alive;
- a move transfers ownership when the source will not be used again;
- a copy creates another semantic value and performs whatever retain operation its type requires.

## Minimal language and runtime substrate

### 1. Deterministic lifecycle hooks

A resource-bearing type needs compiler-recognized operations for:

- initializing a destination by copying an existing value;
- transferring an existing value into a destination without retaining it;
- releasing a fully initialized value exactly once;
- replacing an initialized destination, which is release followed by copy or transfer.

The exact names and declaration syntax remain open. They may eventually resemble `__copy__`, `__move__`, and `__drop__`, but ordinary function-call rules are not enough by themselves: passing a value to its own release operation must not first copy it. The compiler can invoke these hooks with internal, nonescaping places for the relevant storage. (perhaps this indicates a reasonable case for metatagged methods, e.g. `$__copy__`, `$__move__`, `$__drop__`, since meta tags are supposed to indicate special behaviors, it might make sense for methods that need to deal with the arguments in a special way to be defined as such. TBD)

Release must run on every path that ends a value's lifetime: normal scope exit, return, loop exit, exception forwarding, reassignment, and cleanup after partially completed aggregate construction. A release hook must not return an error, forward an exception, or otherwise replace the control flow already in progress.

Lifecycle hooks cannot be unrestricted observable callbacks if the compiler is to preserve Dewy's move and copy-elision freedoms. Their contract must permit a retain immediately balanced by a release to be removed, and a last-use copy to become a move. At minimum, arbitrary I/O and unrelated mutation should be rejected in these hooks; the precise effect restriction belongs with the effect-system design. A reference-count inspection API, if provided, reports a useful snapshot rather than making transient compiler-elided retain/release pairs observable language semantics.

### 2. Allocator and layout capabilities

Safe libraries need an unsafe foundation that can:

- obtain an allocation with an explicit size and alignment;
- release that exact allocation;
- initialize a typed value in previously uninitialized storage;
- read, write, and project fields through a typed allocation handle;
- distinguish uninitialized, initialized, moved-from, and released storage well enough to prevent double release and reads of uninitialized memory;
- query compile-time layout information such as `size_of<T>`, `align_of<T>`, and eventually a complete `layout_of<T>`.

The primitive result should preferably be an opaque allocation capability rather than an integer address. Converting it to a raw address, doing unchecked address arithmetic, constructing a handle from raw storage, or releasing storage manually should require an explicit `unsafe` boundary. The public `Rc<T>` API can then be safe while its small implementation core carries the proof obligations.

Allocation failure must have an explicit contract. It may be a returned exception value, a separately named infallible allocator that terminates, or both; it must not accidentally emerge as an invalid handle.

### 3. Scoped payload access

An owning handle must be able to lend access to its payload without transferring ownership. This is where the place machinery is useful, but the returned place has a lifetime bounded by a live handle and therefore needs more than today's nonescaping `@` arguments.

The eventual borrowing model needs to express:

- a read-only place into `T`, valid no longer than the `Rc<T>` used to obtain it;
- a mutable place only when `Rc` proves unique ownership, or when another type explicitly supplies checked interior mutation;
- the inability to release or replace the last owning handle while a payload place is live;
- no safe way to store or return a payload place beyond the lifetime that justifies it.

Exact signatures are intentionally omitted until lifetime-bearing places and read-only place syntax are designed. Conceptually, ordinary `Rc<T>` access produces a scoped read of `T`; a `get_mut(@rc)`-like operation may produce a scoped mutable place only when the strong count is one. Shared mutation should be a separate, visible abstraction rather than an accidental consequence of `Rc`.

### 4. Atomic operations for cross-thread handles

A single-threaded `Rc<T>` only needs ordinary integer counter operations. A cross-thread `Arc<T>` additionally needs atomic read/modify/write operations, selected memory-order guarantees, and a type/effect rule describing which payloads and handles may cross concurrent boundaries. Those are independent extensions: lack of atomics should not block a useful single-threaded `Rc`.

## Reference-counted control block

A library implementation would conceptually allocate a control block shaped like:

```dewy
# Illustrative design shape, not settled declarations.
RcState<T> = [
    strong: uint
    weak: uint
    value: T
]
```

An `Rc<T>` handle points to that block. Its lifecycle and operations follow these rules:

1. `new(value)` allocates and fully initializes a block with one strong owner.
2. Copying an `Rc` increments the strong count and copies the handle bits.
3. Transferring an `Rc` copies the handle bits without changing the count and leaves no live source value to release.
4. Releasing the last strong handle releases `T` exactly once.
5. The control block remains while weak handles exist; releasing the last weak handle frees it.
6. Upgrading a weak handle succeeds only while a strong owner exists.
7. Counter overflow never wraps into premature release; it must be diagnosed or terminate according to a defined low-level policy.

Reference-counted cycles are not collected by this mechanism. `Weak<T>` is therefore part of a complete library design, not an optional optimization. More general cycle collection can remain a separate userland facility built on broader tracing hooks later.

## Recommended staging

1. Settle and implement deterministic release plus compiler-internal copy/transfer initialization for resource-bearing values.
2. Replace the stale `__malloc__`/`__free__` placeholders with a typed allocation/layout substrate under `unsafe`.
3. Implement a minimal owning `Box<T>`-like library type to validate initialization, movement, aggregate fields, returns, and all cleanup paths.
4. Add lifetime-bounded read-only payload places and unique mutable access.
5. Implement `Rc<T>` and `Weak<T>` in the library as the proof that the substrate is sufficient.
6. Add atomics and concurrency contracts before attempting `Arc<T>`.

This order keeps the compiler's default arena-oriented roadmap intact. User-managed storage is an opt-in facility for lifetimes and sharing patterns that the default strategy cannot express cleanly, not a fallback applied to every dynamic value.

## Open design questions

- How a type opts into compiler-invoked lifecycle hooks, and the final hook names.
- The smallest effect contract that makes lifecycle optimization sound without preventing useful cleanup.
- Surface syntax for read-only and lifetime-bounded places.
- Whether explicit user-written moves are needed for predictable systems costs, in addition to moves inferred from last use.
- The typed allocation-capability representation and how much layout reflection safe generic code may use.
- The policy for allocation failure and reference-count overflow.
- How resource-bearing values participate in compile-time evaluation and static storage.
