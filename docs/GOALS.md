# Language goals

Recorded 2026-10-17.

This is what Dewy should be able to do. It is not a status report, and it does
not decide which implementation or which order of work gets there. The roadmap
orders the work. Value semantics and explicit copies have their own design notes.

## Ordinary programs

A binding names a value. Assignment, argument passing, and return give the
receiver its own value. Sharing is either unobservable or written in the source:
`@` at the parameter and at the call names a place.

Closures follow the same rule. An ordinary capture takes a snapshot, and copying
a stateful closure gives the copy independent private state. Shared captures are
explicit. Copying a callback must not silently introduce shared mutable state.
Capture declarations belong alongside ordinary parameters: `$capture` selects
the enclosing scope as the binding's source, and `@` explicitly selects sharing.

Ordinary programs should be comfortable to write. Common code should run well
without pervasive annotations. A whole program, including the compiler, should
compile from source quickly enough to stay in the edit loop: a compiler build
in seconds, not minutes. Fresh compilation is the model. A persistent cache is
not the way the language stays fast.

The rough compilation target is 250,000 lines per second for Dewy programs
(clarified 2026-10-18). Measure fresh whole-program builds on representative
sources, with hardware, build mode, source-counting method and included library
work recorded. Report small-program latency separately from large-program
throughput; generated padding and repeated trivial declarations do not establish
useful application throughput.

Games are a primary customer. Dense data, a game loop, and interactive native
and web programs should be natural to write. A straightforward program should
be able to match the speed of the same algorithm in C or Rust, or improve on it
where Dewy's semantics enable better optimization. Reaching that ordinary
performance should not require expert annotations.

## Storage

Copy-on-write is the default way ordinary arrays and strings implement value
semantics. It stays there. It is the right default when a buffer is often
shared and rarely written, and when a unique buffer can be mutated in place
after one check. It does not become the mechanism for every value. Small
values stay inline. Game and application code remains on this default.

Some programs need a stronger promise. A function can be required not to
allocate, not to detach a shared buffer, and not to panic, and a large value
can be required not to copy itself at an unknown time. Operating systems,
embedded software, realtime work, and audio are in this set. A module can ask
for that lane. An unproven copy, allocation, or panic is then a compile error,
and the author writes an explicit copy, a view, or a move. A buffer proved
unique is mutated in place. Game code never has to enter this mode.

That stricter lane is where hidden exits and hidden cost become compile-time
facts. On the ordinary path, a bounds failure may still be a runtime check
until a program forbids it. Safety for systems work is the checked absence of
those operations, not only a panic with a clear message.

## Performance

The default compiler should produce useful machine code and compile quickly.
Further optimization may spend compile time to make a program faster. An
expert may annotate placement, ownership, and the strict lane when a domain
needs predictability or speed the default does not promise.

## Where the details live

- Value semantics, and why copy-on-write is reserved for the collections where
  it pays: [`design/value_semantics.md`](design/value_semantics.md)
- The strict lane's `$explicit_copies` directive and copy policy:
  [`design/value_semantics.md`](design/value_semantics.md)
- Work queue, acceptance ladder and measured targets: [`ROADMAP.md`](../ROADMAP.md)
