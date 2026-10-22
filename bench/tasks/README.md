# Waiting-lane kernels

`run.py --compiler /absolute/dewy-core --work /absolute/scratch` builds and
interleaves Dewy and C/pthreads runs, verifies checksums, and reports median time
and cancellation-to-join latency. Both run on at most four available CPUs.
Shared-host wall times are descriptive; compile/runtime instruction gates are
separate. Go is optional; the portable reference here uses pthreads.

- `find_first`: two partitions search an array; a match cancels the group. CPU
  loops cooperate at every 1024 elements with a zero-duration sleep.
- `race`: two independent file lookups race, with both lifetimes joined.
- `fanout`: 10,000 spawn requests under a 20 ms deadline. Requests after the
  deadline return cancellation without starting a thread. This measures the
  threads backend's bounded-deadline fan-out, not 10,000 simultaneously live
  threads. Each admitted child does a cancelable 1 ms wait.
