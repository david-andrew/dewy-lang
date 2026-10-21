# Fork-join kernels

Build the compiler with `python3 -m tools.core path`, then pass its printed path:

```
python3 bench/parallel/run.py --compiler PATH --runs 5 --instructions
```

The runner pins to distinct physical cores, interleaves Dewy and GCC `-O3`
OpenMP runs, checks matching results, and reports load. `--previous PATH` adds
an older compiler. `--small --runs 1 --workers 1 2` checks all kernel checksums
quickly. `--gate` exits unsuccessfully below 0.9× OpenMP at any requested worker count
or above 1.1× the sequential time; use it on a quiet host. Artifacts stay under `~/dev/tmp/astra-forkjoin/bench` by default.
An extra argument to a kernel selects its sequential implementation; worker
count comes from `SLOPPY_THREADS` or `OMP_NUM_THREADS`.

The kernels are recursive fib(32), a 16M-element sum with fixed 4096-element
reduction leaves, 1024² matmul with 32² output tiles, twenty 1024² Jacobi steps,
and recursive mergesort of 262144 integers. Tile sizes describe the numerical
algorithm, not scheduler chunk sizes. All checksums are computed in source
order. Dewy kernels retain the existing `parallel_*` entry points so an older
compiler can measure precisely the same source; syntax is covered separately.

These comparisons include representation costs. Dewy mergesort returns arrays
at each recursive node, while C uses two flat buffers. Dewy Jacobi copies and
updates interior rows each step, sharing unchanged boundary rows; C swaps two
flat grids. Matmul hoists tile-row and input-row index bases so the existing
vectorizer can recognize the inner loop. OpenMP fib and mergesort use explicit
serial cutoffs of 20 and 2048 respectively. Dewy has no user-selected scheduler
cutoff. Fib's sequential path is naive recursion in both languages. Report these
differences when interpreting the gap; do not attribute all of it to scheduling.

Instruction counts cover the whole process, including initialization and
checksum work. On a loaded host use them to test overhead claims; pinned wall
times alone do not establish the scaling gate.
