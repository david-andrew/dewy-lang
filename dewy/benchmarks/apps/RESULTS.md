# Application benchmark results

Each section is one run of `./run.py` on an otherwise idle machine. `udewy`
is the µDewy route and `native` the native x86-64 route (the first two
sections, from before the native route was the default, call them `default`
and `optimizing`); `C` is the counterpart. Kernel times are the best and the median of the rounds;
`vs C` compares best kernel times at the same input. Compile times use the
cached checked prelude; the fresh figure is given with each section.

## Baseline: revision 51bb1ed8 (2026-10-03)

The first native emitter: registers, address modes, calls built in place.
Fresh compile (prelude not cached): 4.4 s.

machine: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz; Linux 6.18.44-ogc1.1.fc44.x86_64
C: `cc -O2` (cc (GCC) 16.2.1 20260819 (Red Hat 16.2.1-2)); rounds: best of 5

| workload | build | compile s | compile MiB | input | kernel ms | median | vs C | whole run ms | run MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| helpers | default | 0.69 | 131 | 200000 | 410.9 | 418.9 | 6.30x | 412.2 | 0.4 |
| helpers | optimizing | 0.60 | 127 | 200000 | 404.3 | 406.1 | 6.20x | 404.9 | 0.4 |
| helpers | C | 0.07 | 31 | 200000 | 65.2 | 65.8 | 1.00x | 66.4 | 1.6 |
| helpers | default | 0.69 | 131 | 2000000 | 4687.1 | 4697.6 | 6.49x | 4687.7 | 0.4 |
| helpers | optimizing | 0.60 | 127 | 2000000 | 4708.8 | 4755.0 | 6.52x | 4709.4 | 0.4 |
| helpers | C | 0.07 | 31 | 2000000 | 721.9 | 723.7 | 1.00x | 723.3 | 1.6 |
| arrays | default | 0.66 | 132 | 1000000 | 61.0 | 61.9 | 4.36x | 108.0 | 23.4 |
| arrays | optimizing | 0.58 | 127 | 1000000 | 56.7 | 57.5 | 4.05x | 98.8 | 23.4 |
| arrays | C | 0.08 | 31 | 1000000 | 14.0 | 16.6 | 1.00x | 24.9 | 16.8 |
| arrays | default | 0.66 | 132 | 10000000 | 691.0 | 707.2 | 3.13x | 1194.6 | 280.8 |
| arrays | optimizing | 0.58 | 127 | 10000000 | 647.9 | 661.1 | 2.93x | 1101.2 | 280.8 |
| arrays | C | 0.08 | 31 | 10000000 | 220.9 | 223.0 | 1.00x | 310.8 | 154.2 |
| records | default | 0.66 | 132 | 100000 | 116.1 | 117.0 | 13.00x | 131.8 | 8.0 |
| records | optimizing | 0.59 | 127 | 100000 | 83.6 | 88.2 | 9.35x | 97.6 | 8.0 |
| records | C | 0.08 | 31 | 100000 | 8.9 | 9.1 | 1.00x | 12.1 | 4.7 |
| records | default | 0.66 | 132 | 1000000 | 1193.1 | 1198.1 | 9.87x | 1332.3 | 76.8 |
| records | optimizing | 0.59 | 127 | 1000000 | 873.3 | 878.8 | 7.23x | 1003.6 | 76.8 |
| records | C | 0.08 | 31 | 1000000 | 120.8 | 122.7 | 1.00x | 142.8 | 32.2 |
| text | default | 0.73 | 132 | 1000000 | 62.3 | 62.9 | 3.79x | 229.5 | 12.9 |
| text | optimizing | 0.62 | 127 | 1000000 | 58.0 | 58.3 | 3.53x | 222.9 | 12.9 |
| text | C | 0.10 | 32 | 1000000 | 16.4 | 17.0 | 1.00x | 34.3 | 6.5 |
| text | default | 0.73 | 132 | 10000000 | 627.7 | 636.5 | 3.85x | 2283.3 | 111.8 |
| text | optimizing | 0.62 | 127 | 10000000 | 580.9 | 586.5 | 3.56x | 2197.0 | 111.8 |
| text | C | 0.10 | 32 | 10000000 | 163.2 | 164.6 | 1.00x | 325.6 | 49.3 |
| graph | default | 0.68 | 134 | 200000 | 152.8 | 156.0 | 2.98x | 232.7 | 55.3 |
| graph | optimizing | 0.61 | 129 | 200000 | 138.6 | 141.3 | 2.70x | 209.9 | 55.3 |
| graph | C | 0.11 | 33 | 200000 | 51.3 | 52.7 | 1.00x | 79.2 | 33.4 |
| graph | default | 0.68 | 134 | 1000000 | 1249.6 | 1253.3 | 4.09x | 1688.4 | 255.7 |
| graph | optimizing | 0.61 | 129 | 1000000 | 1106.6 | 1117.4 | 3.63x | 1512.8 | 255.6 |
| graph | C | 0.11 | 33 | 1000000 | 305.2 | 308.7 | 1.00x | 440.7 | 135.8 |

Reading it:

- `helpers` and `text` were dominated by division: every `%` and `//` by a
  constant was a 64-bit `idiv` behind the checks for a zero divisor and the
  overflowing case, where C multiplies by a reciprocal.
- `records` spent about 45% of its kernel in the calls that test whether the
  array and the record are shared, made on every field write; reads repeat
  the chain of loads from the array to the record.
- `arrays` pays for the same test on every element store.
- `graph` is the prelude's dictionary against a table specialised to
  integer keys; both routes are within 10% of each other because the time is
  in the prelude's probe and insert, which neither route specialises.
- Setup, outside the kernels, is slow where it pushes one element at a time
  (`text` builds 55 million bytes that way: 1.6 s against C's 0.16 s).

## Division by constants, tests for sharing in place, value numbering (2026-10-03)

The revision after the baseline: a constant divisor becomes a multiplication
or a shift; the test for a shared array or record is built in place, with
only the copy out of line; an operation or load already computed where its
result still stands is not computed again (see `../../bootstrap/OPTIMIZER.md`).
Fresh compile: 4.4 s.

| workload | build | compile s | compile MiB | input | kernel ms | median | vs C | whole run ms | run MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| helpers | default | 4.41 | 113 | 200000 | 414.5 | 418.1 | 6.25x | 415.0 | 0.2 |
| helpers | optimizing | 0.56 | 127 | 200000 | 108.6 | 115.9 | 1.64x | 113.6 | 0.4 |
| helpers | C | 0.08 | 31 | 200000 | 66.3 | 67.8 | 1.00x | 67.6 | 1.6 |
| helpers | default | 4.41 | 113 | 2000000 | 4849.0 | 4852.0 | 6.73x | 4849.6 | 0.4 |
| helpers | optimizing | 0.56 | 127 | 2000000 | 1208.1 | 1214.2 | 1.68x | 1208.6 | 0.4 |
| helpers | C | 0.08 | 31 | 2000000 | 720.9 | 722.7 | 1.00x | 722.3 | 1.6 |
| arrays | default | 0.65 | 132 | 1000000 | 57.6 | 58.2 | 4.13x | 102.3 | 23.4 |
| arrays | optimizing | 0.56 | 127 | 1000000 | 35.3 | 36.6 | 2.54x | 70.0 | 23.4 |
| arrays | C | 0.09 | 31 | 1000000 | 13.9 | 14.4 | 1.00x | 24.5 | 16.8 |
| arrays | default | 0.65 | 132 | 10000000 | 614.2 | 617.6 | 2.77x | 1073.0 | 280.8 |
| arrays | optimizing | 0.56 | 127 | 10000000 | 412.0 | 438.3 | 1.86x | 770.3 | 280.8 |
| arrays | C | 0.09 | 31 | 10000000 | 221.5 | 225.9 | 1.00x | 311.8 | 154.2 |
| records | default | 0.65 | 133 | 100000 | 94.8 | 96.5 | 10.79x | 109.5 | 8.0 |
| records | optimizing | 0.62 | 128 | 100000 | 53.8 | 57.0 | 6.12x | 64.7 | 8.0 |
| records | C | 0.08 | 31 | 100000 | 8.8 | 9.0 | 1.00x | 11.7 | 4.7 |
| records | default | 0.65 | 133 | 1000000 | 983.5 | 992.6 | 8.12x | 1120.8 | 76.8 |
| records | optimizing | 0.62 | 128 | 1000000 | 568.3 | 571.5 | 4.69x | 669.7 | 76.8 |
| records | C | 0.08 | 31 | 1000000 | 121.2 | 123.0 | 1.00x | 143.5 | 32.1 |
| text | default | 0.67 | 132 | 1000000 | 64.4 | 64.8 | 3.83x | 222.4 | 12.9 |
| text | optimizing | 0.62 | 127 | 1000000 | 32.2 | 32.4 | 1.91x | 127.2 | 12.9 |
| text | C | 0.09 | 32 | 1000000 | 16.8 | 17.0 | 1.00x | 34.8 | 6.3 |
| text | default | 0.67 | 132 | 10000000 | 649.6 | 651.2 | 3.99x | 2191.3 | 111.8 |
| text | optimizing | 0.62 | 127 | 10000000 | 323.1 | 324.4 | 1.99x | 1236.4 | 111.8 |
| text | C | 0.09 | 32 | 10000000 | 162.7 | 164.1 | 1.00x | 324.8 | 49.4 |
| graph | default | 0.67 | 135 | 200000 | 149.5 | 152.0 | 2.87x | 223.9 | 55.3 |
| graph | optimizing | 0.59 | 129 | 200000 | 135.5 | 138.4 | 2.60x | 201.5 | 55.3 |
| graph | C | 0.11 | 33 | 200000 | 52.0 | 52.3 | 1.00x | 80.2 | 33.4 |
| graph | default | 0.67 | 135 | 1000000 | 1224.5 | 1236.6 | 4.03x | 1641.0 | 255.6 |
| graph | optimizing | 0.59 | 129 | 1000000 | 1111.3 | 1176.1 | 3.66x | 1484.9 | 255.6 |
| graph | C | 0.11 | 33 | 1000000 | 304.0 | 306.0 | 1.00x | 439.9 | 135.9 |

Against the baseline the optimizing route's larger-input kernels moved:
`helpers` 4709 → 1208 ms (6.5× → 1.7× of C), `arrays` 648 → 412 ms
(2.9× → 1.9×), `records` 873 → 568 ms (7.2× → 4.7×), `text` 581 → 323 ms
(3.6× → 2.0×), `graph` unchanged (3.6×). The default route gains from the
in-place sharing test where it applies (`records` 1193 → 984 ms).

Open, by workload: `records` needs records stored flat in their array
(dense aggregate arrays, Phase 3 in the roadmap) and the sharing test hoisted
out of loops that cannot share; `graph` needs the dictionary's probe
specialised by key type; `helpers` and `arrays` need bounds checks and
remaining moves removed; setup needs a cheaper `push`.

## Native route by default; growth test in place; wider power-of-two division (2026-10-03)

`_reserve_array` is split as the sharing tests were, so a `push` with room
makes no call; division by a power of two up to 2⁶² is a shift (the
generators' `% 2147483648` was still an `idiv`). Fresh compile: 2.9 s; a
compile with the prelude cached is 0.45 s on the native route, which starts
no backend process.

| workload | build | compile s | compile MiB | input | kernel ms | median | vs C | whole run ms | run MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| helpers | udewy | 0.54 | 130 | 200000 | 435.9 | 444.1 | 6.61x | 436.4 | 0.4 |
| helpers | native | 0.44 | 125 | 200000 | 108.0 | 108.8 | 1.64x | 108.5 | 0.4 |
| helpers | C | 0.07 | 31 | 200000 | 66.0 | 66.8 | 1.00x | 66.9 | 1.6 |
| helpers | udewy | 0.54 | 130 | 2000000 | 4912.8 | 4936.9 | 6.80x | 4913.4 | 0.4 |
| helpers | native | 0.44 | 125 | 2000000 | 1213.5 | 1222.6 | 1.68x | 1214.1 | 0.4 |
| helpers | C | 0.07 | 31 | 2000000 | 722.2 | 727.1 | 1.00x | 723.5 | 1.6 |
| arrays | udewy | 0.53 | 131 | 1000000 | 53.5 | 54.8 | 3.78x | 91.3 | 23.4 |
| arrays | native | 0.46 | 126 | 1000000 | 32.5 | 33.8 | 2.29x | 55.0 | 23.4 |
| arrays | C | 0.08 | 31 | 1000000 | 14.2 | 14.6 | 1.00x | 24.5 | 16.8 |
| arrays | udewy | 0.53 | 131 | 10000000 | 612.8 | 620.7 | 2.77x | 1020.3 | 280.8 |
| arrays | native | 0.46 | 126 | 10000000 | 411.7 | 425.1 | 1.86x | 671.1 | 280.8 |
| arrays | C | 0.08 | 31 | 10000000 | 221.5 | 225.4 | 1.00x | 313.3 | 154.2 |
| records | udewy | 0.53 | 131 | 100000 | 95.8 | 97.8 | 10.86x | 110.3 | 8.0 |
| records | native | 0.51 | 126 | 100000 | 53.0 | 56.3 | 6.01x | 61.8 | 8.0 |
| records | C | 0.08 | 31 | 100000 | 8.8 | 8.9 | 1.00x | 12.0 | 4.7 |
| records | udewy | 0.53 | 131 | 1000000 | 991.4 | 993.6 | 8.20x | 1123.6 | 76.8 |
| records | native | 0.51 | 126 | 1000000 | 566.4 | 571.9 | 4.68x | 646.8 | 76.8 |
| records | C | 0.08 | 31 | 1000000 | 121.0 | 121.8 | 1.00x | 142.8 | 32.2 |
| text | udewy | 0.55 | 131 | 1000000 | 61.0 | 61.8 | 3.66x | 206.7 | 12.9 |
| text | native | 0.47 | 126 | 1000000 | 32.8 | 33.1 | 1.97x | 84.3 | 12.9 |
| text | C | 0.09 | 32 | 1000000 | 16.7 | 16.8 | 1.00x | 34.4 | 6.5 |
| text | udewy | 0.55 | 131 | 10000000 | 618.7 | 632.1 | 3.81x | 2043.9 | 111.8 |
| text | native | 0.47 | 126 | 10000000 | 318.1 | 324.4 | 1.96x | 783.3 | 111.8 |
| text | C | 0.09 | 32 | 10000000 | 162.3 | 168.3 | 1.00x | 324.5 | 49.3 |
| graph | udewy | 0.54 | 133 | 200000 | 148.7 | 150.8 | 2.86x | 221.6 | 55.3 |
| graph | native | 0.46 | 127 | 200000 | 133.6 | 134.6 | 2.57x | 192.2 | 55.3 |
| graph | C | 0.11 | 33 | 200000 | 52.0 | 52.5 | 1.00x | 80.4 | 33.4 |
| graph | udewy | 0.54 | 133 | 1000000 | 1219.5 | 1233.9 | 4.03x | 1624.8 | 255.5 |
| graph | native | 0.46 | 127 | 1000000 | 1099.6 | 1105.0 | 3.63x | 1432.4 | 255.6 |
| graph | C | 0.11 | 33 | 1000000 | 302.5 | 307.6 | 1.00x | 437.8 | 135.9 |

Kernels are as in the previous section; setup moved: `text`'s whole run at
the larger input went 1236 → 780 ms and `arrays`' 770 → 662 ms.

## wasm32 under node (2026-10-03)

The same programs for wasm32, run by `tools/run_wasm.mjs` on node 26 (V8),
best of three, small inputs. The host's clock counts milliseconds.

| workload | µDewy route | native route |
|---|---:|---:|
| helpers | 586 ms | 459 ms |
| arrays | 74 ms | 65 ms |
| records | 62 ms | 39 ms |
| text | 98 ms | 81 ms |
| graph | 188 ms | 169 ms |

Checksums agree with x86-64. For comparison, the x86-64 native route runs
the same kernels in 108, 32, 53, 26 and 132 ms (previous section); where
the wasm32 time goes has not been measured yet.

