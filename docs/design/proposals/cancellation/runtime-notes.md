# Cancellation in the runtime: notes from "Getting Canceled"

Source: Andrew Kelley, "Getting Canceled", Software You Can Love 2026 (<https://www.youtube.com/watch?v=5zIOfBLQ3U4>). These notes are about implementation. None of them changes D44's semantics, and these choices are ours to make.

## What the talk says

1. **Cancellation exists for two reasons.**
   - To avoid work whose result will be discarded. This is purely a resource saving, and it applies to any task.
   - To get a task out of a wait that will never return. This prevents deadlock, and it applies only to concurrent tasks.

   In Dewy, the first is the losers of `race` and `first_ok`. The second is `within`, Ctrl-C handlers, and a `parallel` that leaves early.
2. **A cancellation point is a point of contention.** Every check is a shared-memory load, and it caps speedup by Amdahl's law. A hot loop shouldn't check on every iteration, but if it never checks, the canceller has to wait for the loop to finish. This supports an explicit `check_cancel()` (D41 Q1) over checks the compiler inserts on its own.
3. **The natural place to check is a blocking system call.**
   - Such calls already return `EINTR` when a signal arrives. Programs must retry on `EINTR` anyway, because resizing a terminal sends `SIGWINCH`, so the retry loop is the place to check the flag.
   - The mechanism: the canceller atomically sets a flag on the target, then signals the target thread. The target's syscall returns `EINTR`, the target sees the flag, and it returns `Canceled`.
   - The signal handler can do nothing at all, because the delivery alone causes the `EINTR`.
4. **That mechanism has a race.** If the signal arrives after the flag check but before the syscall instruction, it is handled and lost. The syscall then blocks with nothing left to wake it.
5. **musl's fix** puts the syscall in a small assembly wrapper with labels around the window from "flag checked" to "syscall entered".
   - Its signal handler checks whether the interrupted program counter lies inside that window. If it does, the handler rewrites the saved program counter to the cancel path.
   - Nothing ever waits. musl attaches this to `pthread_cancel`'s semantics, which kill the thread with no cleanup, so as shipped it is unusable for this purpose. An extension returns `ECANCELED` instead.
6. **Zig's fix**, chosen because it must also work over other libcs such as macOS's: the canceller keeps resending the signal, with backoff starting at a few microseconds, until the target acknowledges. The canceller blocks only when the target is inside the window.
7. **Other points from the talk:**
   - A thread in uninterruptible sleep can't be cancelled at all; cancellation is cooperative.
   - Applications shouldn't install signal handlers, because handlers are global state. That belongs in the standard library.
   - Windows works "completely differently", through low-level `ntdll` calls.
   - The primitive Kelley wishes existed: "send a signal to another thread that queues an `EINTR` on the next syscall."

## What Dewy's runtime does today

**Linux** (`lib/std/tasks.jo`):
- It sends a no-op real-time signal with `tgkill`, once per task, from `__task_interrupt_group`.
- Generated syscalls check `__task_canceled()` on each `EINTR` retry (`compiler/lower_group.dewy` ~2320).
- The comment on `__task_interrupt` says "Repeated acknowledgement closes the check/syscall race", but the signal is sent only once, and no acknowledgement or resend was found.
- What actually covers the race is polling:
  - futex waits time out every 1 ms (`__task_wait`, channels, `mpmc`);
  - `sleep` runs in slices of at most 1 ms.

**macOS and Windows:**
- There is no signal; a cancelled task's waits notice "within a millisecond" by polling.
- A wait blocked in a syscall that isn't sliced can't be interrupted.

**Loops with no cancellation check.** Some hand-written `EINTR` retry loops don't check for cancellation, so a cancelled task blocked there waits for input. One example is `__stdin_line` in `lib/core/os.jo`. Each such loop needs auditing.

## Recommendations for the D44 runtime work

1. **Close the race properly on Linux, the musl way, without the `pthread_cancel` part.**
   - Dewy's compiler emits its own syscall instructions, with no libc on Linux. It can therefore record, per cancellable syscall site, the window between the flag check and the syscall.
   - The handler then becomes an `SA_SIGINFO` handler that redirects the saved program counter when it falls inside a recorded window. No waiting and no retry are needed.
   - The handler needs the program-counter field of `ucontext`, per architecture (x86-64 and arm64).
2. **Elsewhere, the Zig way.** On macOS (through libc) and anywhere a window can't be recorded, resend the signal with backoff until the target acknowledges.
3. **Wake runtime-owned waits directly instead of signalling.**
   - Channel, mutex, `select` and task-join waits sleep on a futex word that the runtime knows. Record that word in the task's state, and have the canceller wake it.
   - `sleep` becomes one timed futex wait on a per-task word, instead of 1 ms slices.
   - With 1 and 2 in place, drop the 1 ms timeouts. They cost a wakeup per waiting task per millisecond, which spends battery and adds latency.
4. **Keep the `EINTR` retry loops, and make each one check the current request and recompute the remaining timeout.** Restarting a timed wait with its full timeout after each `SIGWINCH` would push its deadline later.
5. **Handle cleanup shielding through the current request.**
   - Cleanup and `protect_from_cancel` bodies run under a fresh request (D44).
   - A cancel signal that lands during cleanup gives `EINTR`. The check then reads the thread's current request, which isn't closed, so the call retries. No masking is needed.
6. **Make `check_cancel()` one relaxed load** of the current request's closed flag, kept in thread-local state. A closed parent request is propagated to its children when it closes, so the check stays O(1).
7. **Windows:** use the `ntdll`-level mechanism (alertable waits, or cancelling synchronous I/O) rather than polling. To be designed when the Windows backend needs it.
8. **Document the limits.** A thread in uninterruptible sleep, or inside a foreign call that doesn't return, delays its group's join. That is why `within`, `protect_from_cancel` and cleanup grace have limits.
9. **Not from the talk: an evented backend.** On an `io_uring` backend, cancelling an in-flight operation (`IORING_OP_ASYNC_CANCEL`) gives the "queue an `EINTR`" behaviour Kelley wants, with no signal.
