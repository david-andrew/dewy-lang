# Fork-join kernels

Build the compiler with `python3 -m tools.core path`, then pass its printed path:

```
python3 bench/parallel/run.py --compiler PATH --runs 5 --instructions --cycles
```

The runner pins to distinct physical cores, interleaves Dewy and GCC `-O3`
OpenMP runs, checks matching results, and reports load. `--previous PATH` adds
an older compiler. `--small --runs 1 --workers 1 2` checks all kernel checksums
quickly. `--gate` exits unsuccessfully below 0.9× OpenMP at any requested worker count
or above 1.1× the sequential time; it also requires 2/4-worker speedups
to reach 0.9× OpenMP's speedup over its own one-worker time. Use it on a quiet host. Artifacts stay under `build/forkjoin-bench` by default.
An extra argument to a kernel selects its sequential implementation; worker
count comes from `DEWY_THREADS` or `OMP_NUM_THREADS`.

The kernels are recursive fib(32), a 16M-element sum with fixed 4096-element
reduction leaves, 1024² matmul with 32² output tiles, twenty 1024² Jacobi steps,
recursive mergesort of 262144 integers, and four all-pairs updates of 2048 particles
from `examples/parallel_particles.dewy`. Tile sizes describe the numerical
algorithm, not scheduler chunk sizes. All checksums are computed in source
order. Dewy kernels retain the existing `parallel_*` entry points. Mergesort
requires mutable slice support; older compilers cannot build that kernel.

These comparisons include representation costs. Both mergesorts use two
preallocated flat buffers; Dewy passes checked, borrowed slice descriptors
through its recursive calls and disjoint fork arms. Both Jacobi kernels swap
two preallocated flat grids; Dewy shares the input as a read-only borrow and
partitions output rows across a recursive binary fork. Matmul hoists tile-row and input-row index bases so the existing
vectorizer can recognize the inner loop. OpenMP fib and mergesort use explicit
serial cutoffs of 20 and 2048 respectively. Dewy has no user-selected scheduler
cutoff. Fib's sequential path is naive recursion in both languages. Report these
differences when interpreting the gap; do not attribute all of it to scheduling.

The runner reports T1/Tseq, speedups relative to each implementation's T1,
and sample ranges. Optional hardware cycles are indicative on a shared host.
Instruction counts cover the whole process, including initialization and
checksum work. On a loaded host use them to test overhead claims; pinned wall
times alone do not establish the scaling gate.

`--instruction-gate --workers 1` checks the 1.1× overhead limit using instructions
instead of time. It implies `--instructions`; `--gate` continues to check wall
time, throughput and scaling independently. `--report PATH` saves raw samples,
medians, checksums and failures outside the source tree, including completed
kernels if a later kernel fails.

For scheduler attribution, run the separate diagnostic harness:

```
python3 bench/parallel/profile.py --compiler PATH --work ~/dev/tmp/forkjoin-profile \
  --runs 3 --workers 1 2 4 --depths 4 8 --report ~/dev/tmp/forkjoin-profile/report.json
```

It copies the runtime into the work directory and counts forks, joins,
heartbeat polls, clock reads, promotions, successful steals, serial frontiers,
range leaves and serial jobs/items in padded per-worker rows. Production builds
contain no instrumentation or profiling switches. Instrumented runs are only
for counters: they perturb heartbeat timing and are never used for instruction
or wall-clock gates. `--counters-only` avoids needing a hardware counter or
Valgrind for those runs.

Separate, uninstrumented builds disable promotion while retaining fork/join
and shared allocation, or vary the internal scalar frontier depth. Compare
their instructions with the ordinary build at the same worker count, and with
the one-worker/serial rows from `run.py`. These are controlled ablations, not
an additive instruction decomposition: promotion changes the amount of work
that enters the scheduler. In particular, zero one-worker forks/promotions
means that T1/Tseq's remaining gap comes from dispatch, collection,
representation or checks, not deque operations. The frontier depth is a
diagnostic runtime edit, not a user-selected scheduling cutoff. For mergesort,
OpenMP's 2048 cutoff creates 255 tasks at the default size; compare this with
the measured Dewy promotions and clock reads, not just recursion depth.

The **Fork-join stage-one benchmark** Actions workflow runs the wall gate at
1/2/4 workers on a hosted Linux runner, records its CPU topology, runs diagnostic
counters separately, and checks one-worker instructions with the hardware
counter or Valgrind fallback. It uploads reports even when a gate fails. Start
it with `workflow_dispatch`, or push a dedicated `bench/forkjoin/**` branch to
exercise a workflow that has not yet reached the default branch. Ordinary
development pushes do not trigger this benchmark.

Standard hosted x86 runners can expose two physical cores and four SMT
threads. The workflow explicitly uses `--allow-smt`: select one CPU per core
first, then siblings, and record both lists plus `uses_smt` in the report. Its
four-worker result then compares the same SMT resources for both languages;
it does not establish four-physical-core scaling. Without this flag, requesting
more workers than physical cores remains an error.
