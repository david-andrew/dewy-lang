# Runtime-chosen settings, round 6

Round 5 stands except where this file says otherwise. No new spelling. `$fast_math = false` is the spelling LANGUAGE.md already has.

## What `$program.max_memory` counts

Reserved bytes of live Dewy heap blocks, not pages. The page is bookkeeping.

A block allocated while a memory cap is on the stack charges its **reserved size** to every budget then in force. That size is the allocator's size class of the request plus its 16-byte header: the smallest `32 << c` that holds it, so 32, 64, 128, and so on, up through 256KiB. A request above 256KiB reserves the mapping rounded up to 64KiB. Free subtracts the same number on that same `live` atomic. A block allocated with no memory cap on the stack is not charged and not recorded.

The size-class slabs (4MiB chunks, shared across caps and threads, including their free slots and thread-local freelists) are not charged. A capped scope that has not allocated charges nothing. It does not pin a page per size class, and a worker does not pin one either. A 24-byte string reserves 64 bytes (40 bytes with the header, class 64). Returned to an outer caller, it keeps 64 bytes on the inner budget and on every outer budget until it is freed. It does not keep the slab. Thousands of handlers that each return one small string share slabs; each string is its own size class on the budgets that were in force, plus one side-table word (the budget pointer) for that block. Uncapped blocks have no word.

The once-per-build warning, at the first reachable `$program.max_memory`, says that:

> this cap counts reserved bytes of Dewy heap blocks allocated while a memory cap is on the stack (N sites). A block charges its size class (32 bytes and up, or a 64KiB-rounded mapping above 256KiB), not the slab it sits on. A returned block keeps those bytes until it is freed. Bookkeeping is one word per such live block.

A core cap still does not warn. `int64` is 8 bytes, so the arrays in `04_request_memory.dewy` are large mappings, not slabs: 500_000 of them reserve 4_063_232 bytes, and 6MiB holds one of those and not two. 8_000_000 reserve 64_028_672 bytes, over 32MiB.

## Generics and IEEE

A generic instance is compiled in the caller's module, under the caller's code vector, when the generic does not set that setting itself. A concrete function in another module is still not recompiled, and inlining does not change that.

The library pins IEEE with `$fast_math = false` on the function. That is a constant code setting, so it covers the whole function. The caller's `$fast_math` does not reach that instance, and there is no warning.

When a caller's `$fast_math` does reach a generic from another module, one warning per build for that function, at the first such call:

> `lib.add3` is compiled under this call's `$fast_math`. It is a generic from another module and may rely on IEEE. Pin it with `$fast_math = false` on `add3`.

`$no_nan` and `$no_inf` use the same rule. A same-module generic does not get this warning. A generic that already writes `$fast_math` (on) is fast for every caller, which is the library offering the fast body, as `fast_add` does for a concrete function.

## Function values and policy

A function value captures the zone, gap, fold, rules, and zone source in force where the value is **created**. The call runs under those frames. A library that sets `$time.zone = zone"UTC"` and then calls the value does not change what that value's `today` means. Caps and schedules do not capture. They follow the caller that runs the value: the stack at the call, or the chain at `spawn` for a task. They limit resources. The value's own cap or schedule, written on its function, still narrows or applies inside it.

Creation is the `@`. `let f = @work` and `table = [@index @quiet]` capture at those `@`s, which for a top-level table is the header then in force, not the zone of whoever later calls the slot. Passing a top-level function as an argument creates the handle at that argument, in the caller, before the callee's zone is entered. A direct call, `render(r)`, is not a handle. It sees the caller's policy, including a zone the caller just set.

`@audit` written under `$time.zone = r.zone` captures that zone. `utc.run(@audit)` can set UTC for `run`'s own code and cannot retarget `audit`. A handle created where no zone is set, then passed into `run`, keeps that absence. Its `today` is not UTC.

A known `@lib.stamp` under a runtime zone is still the compile error at that `@` when `stamp` reaches a zone-less literal. The caller's zone does not flow into a handle created somewhere else, so an open function parameter is not an error merely because the caller has a runtime zone. Direct calls keep the round 5 check.

## What changed from round 5

- A memory cap charged whole pages, so a small returned value pinned a slab on every budget in the chain. It charges the block's reserved bytes. The slab is not charged.
- A generic from another module is still compiled under the caller's `$fast_math`, and that now warns. `$fast_math = false` on the generic pins IEEE.
- Policy on a function value is the frames at the `@`. Caps and schedules stay with the caller that runs it. Round 5's "open parameter under a runtime zone is always an error" is withdrawn for handles.
