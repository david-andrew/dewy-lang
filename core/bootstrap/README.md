# Optional legacy syntax parser

`dewy_parse.c.gz` is a compressed, generated C translation of the Dewy syntax
parser and its runtime dependencies. It is about 0.7 MB compressed (6.7 MB of C),
and compiles standalone on Linux x86-64. Core builds with `--legacy-parser` decompress it and
compile with `cc -std=c99 -O1 ... -lm`. No Dewy binary, old library checkout,
network download, or Python language implementation is involved at runtime.

The default compiler uses `compiler/dewy_fast.jo` in process and does not build
or execute this seed. `DEWY_CORE_FRONTEND=legacy` explicitly selects the old
parser for investigation; there is no automatic fallback. `dewy_parse.json` records
C/archive hashes, generator seed identities, the generation command, and a
source snapshot. These identify provenance, not a byte-equality acceptance gate.

To inspect the C:

```sh
gzip -dc core/bootstrap/dewy_parse.c.gz > /tmp/dewy_parse.c
```

When changing the native parser or its driver, regenerate the snapshot with a
working native compiler pair from the earlier implementation:

```sh
python3 -m tools.sloppy_core.regenerate_parser \
  --dewy /path/to/native/dewy --udewy /path/to/native/udewy
```

Then build with `--legacy-parser` and check the relevant behavior. The original parser source remains
in `dewy/bootstrap/parser/`, with its driver in `tools/sloppy_core/parse.dewy`.
Maintaining that legacy frontend still uses the earlier implementation; building and
using the default compact compiler does not. `--dewy` and `--parser` on the builder
allow testing a freshly compiled parser or reusing a particular parser binary.

`frontend.jo` is separate: it substitutes the implementation-language frontend
while the C stage zero builds the first core compiler. That compiler then builds
the Dewy frontend and the resulting compiler builds itself.
