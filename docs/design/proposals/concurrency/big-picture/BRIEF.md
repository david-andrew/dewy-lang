# Big-picture round: Dewy's 80/20 design and parallelism

David owns the Dewy programming language's surface and semantics. The repo is at `/var/home/david/dev/dewy-lang`. Before he decides the concurrency and parallelism surface, he wants a step back. In his words (2026-11-01):

> At a high level, I'm thinking about dewy as a language of 80/20 rules, a language that provides an easy to use common path that covers 80% of the cases, and then also lets you opt into whatever nuance and specifics when you find yourself in the harder 20% case, and you need to push the computer to its full capabilities/etc. — dewy should make unleashing the full capabilities / doing the harder stuff straightforward on top of the easy version. So I'm interested in what that looks like for dewy. Where have other languages landed on all of this, and what corners and edges have they uncovered that give people trouble? What does a language that leaves one wanting for nothing on this front look like?
>
> A slightly different perspective: Moore's law has ended in terms of processor speeds, but computers have technically continued to improve in their capability by pushing out capabilities for parallelism. Parallelism is notoriously hard to do/get right, and many programmers don't even bother. How can dewy make it easy for lazy programmers to unlock all of the power sitting around for minimal buy-in, and support experts to craft truly fast programs without requiring herculean efforts?

## Dewy in brief

- **Goals** (docs/GOALS.md): general-purpose, with Python-like ease, C-like speed, and safety by default with danger opt-in.
  - No traps by default: possible failures are either proven absent or visibly handled.
  - A `$bulletproof` strictest mode can demand proof for every convenience assumption.
  - Compile speed is a north star: 200–250k lines/s.
  - Primary audiences include games, systems, scientific/ML and scripts.
- **Key design rules:**
  - No colored functions. Blocking, allocation and panics are inferred effects; a row like `& no blocks` is written only to *forbid* one.
  - Settings are in-language metatags (`$name`), not CLI flags or env vars.
  - No compiler magic: library features are built on reusable primitives.
  - Ownership: static first, then arenas, with the heap as a last resort. Value semantics with moves by liveness.
- **Syntax:**
  - space-separated arguments;
  - `=?` for equality;
  - zero-argument calls without parentheses;
  - `@f` handles, `@f(x)` partials, `@(place)` places;
  - `or_throw` / `??` / `??<E>`;
  - `match x { p => … }`;
  - `loop <cond> <body>`;
  - no `self`;
  - juxtaposed units (`2s`);
  - tensors and broadcasting operators exist.
- **Concurrency today** (docs/design/safety_and_concurrency.md):
  - an adopted two-lane direction (compute vs waiting);
  - level-triggered `Canceled`, structured spawning, first failure cancels siblings;
  - deterministic reductions;
  - bounded channels;
  - `Mutex`/`lock_all`, `$no_deadlocks` with certificates, `Atomic` with explicit orders;
  - a model-checked expert library (`spsc`, `mpmc`, ...).
- **Latest proposal:** `docs/design/proposals/concurrency/unified/proposal-v2.md`. One `parallel` keyword (loop, comprehension and block), with the strategy inferred from what bodies may wait on, plus library `tasks` and `select`.
  - Reviews of it: `docs/design/proposals/concurrency/unified/sol-check.md` and `docs/design/proposals/concurrency/unified/grok-review.md`.
  - David hasn't decided anything in it. He wants this big-picture pass first, and he's skeptical of accumulating many overlapping loop- or capture-shaped constructs.
- **Already decided by David:**
  - parallel-safety of callback parameters is inferred, with no required tag;
  - failed sends return `Unsent<T>`;
  - `spsc`/`mpmc` exist;
  - there is no legacy to preserve (no users yet).

## Scope

The whole "use all the hardware" picture, not only threads:
- data parallelism across cores;
- SIMD/vectorization;
- GPU and accelerator offload;
- async and waiting I/O;
- memory layout and locality (struct-of-arrays, cache);
- determinism and debuggability;
- tooling: profilers, "why wasn't this parallelized/vectorized" explanations, race detection;
- the ladder from the lazy path to expert control.

Also cover how the 80/20 principle should shape Dewy's design generally, beyond concurrency.

## Format for every output

- Start with a BLUF.
- Use bullets, not paragraphs.
- Ground the abstract points in concrete Dewy sketches.
- Be candid about trade-offs and about what the current proposals get wrong.
- Read-only on the repo. Write only your own output file.
