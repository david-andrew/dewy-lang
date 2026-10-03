# October 3 runtime-assertion review

This bounded review supports the
[Phase 1.2 evaluation task](../../ROADMAP.md#native-compiler-as-a-fact-system-ergonomics-benchmark-2026-10-03).
It samples the native compiler's assertion patterns and records seven small
proof probes. It does not classify every assertion or measure their aggregate
performance cost.

The hosted rerun used committed source at
`ded467545a5b4532f1456ebfe5f08b0befe8c1b6` in an isolated checkout. Native probes
reused the cached, hosted-built native program driver from the preceding review;
[observations](observations/runtime_asserts.json) record its binary SHA-256,
cached build-input digest and build options. A fresh native bootstrap was not
built for this review. The driver checks and emits each independent entry module;
generated programs are not executed. These are acceptance observations, not
runtime correctness tests, throughput measurements or certification of later
revisions. The rerun used a fresh scratch prelude cache and the isolated
checkout's library. Binaries, caches and temporary paths are omitted.

## Observed proof boundaries

Both implementations agreed on all seven probes:

| Probe | Result | What it establishes |
| --- | --- | --- |
| Refined index parameter | Accept | An index contract referring to the argument's array length suffices locally. |
| Reject nonpositive `int64`, then divide | Accept | The word-integer guard establishes nonzero. |
| Reject nonpositive `bigint`, then divide | Reject | The analogous numerical implication does not establish the required nonzero union alternative. |
| Reject exactly zero `bigint`, then divide | Accept | Explicit zero exclusion establishes that alternative. |
| Index hexadecimal digits with `uint64 and 15` | Reject | The mask's `0..15` range is not inferred. |
| Index hexadecimal digits with `uint64 % 16` | Accept | The remainder bound suffices. |
| Equal-length sibling fields in a writable record | Reject | The proposed relation could be invalidated by assignment; the diagnostic suggests an immutable record. |

The bitmask and positive-`bigint` cases are concrete missing-inference acceptance
cases. The mutable record rejection is a sound boundary, requiring a preservation
design rather than simply accepting the declaration.

## Compiler consumers and interpretation

- [Cache hashing](../../bootstrap/invocation/cache.dewy) masks a hexadecimal
  digit with `15`, then asserts it fits the 16-character alphabet.
- [`fixed_constant`](../../bootstrap/semantic/check.dewy) rejects a nonpositive
  denominator, then asserts nonzero before big-integer division.
- [HIR arena access](../../bootstrap/semantic/hir.dewy) accepts a plain `addr`
  in `node_at`, while `append_node` returns an index refined against the arena
  length. IDs travel through other interfaces and stored fields as plain
  addresses. A stronger getter contract moves obligations to those consumers;
  preserving their evidence is the relevant evaluation, beyond the local probe.
- [SSA writing](../../bootstrap/backend/udewy/ssa_udewy.dewy) checks stored IDs
  against several parallel arrays. Establishing arena provenance, array-length
  correspondence and preservation across mutations is broader work than a
  local scalar bound. [Integer-token conversion](../../bootstrap/semantic/syntax.dewy)
  likewise relies on prior lexer validation that its plain string parameter
  does not carry as a contract.

These samples expose missing inference, discarded interface evidence and
representation invariants. Intentional runtime validation is another category
for the proposed audit; this review does not determine the proportion in each.
Assess programmer effort after helper extraction, record/container storage and
mutation, and check negative cases where an ID belongs to another arena or a
mutation breaks a relationship. A successful remedy establishes or preserves
evidence; replacing a runtime assertion with an unchecked assumption does not
demonstrate a proof improvement. The general requirements already appear in
[idiomatic facts](../../semantic/idiomatic_facts.md).

## Reproducing

[The probe script](probes/runtime_asserts.py) writes generated sources and results
to an external scratch directory. From a checkout with the project's Python
environment available:

```sh
proof_scratch=$(mktemp -d /tmp/dewy-proof-probes.XXXXXX)
.venv/bin/python dewy/audits/2026-10-03/probes/runtime_asserts.py \
  --output-dir "$proof_scratch"
```

For native comparison, add `--native-driver /absolute/path/to/program-driver`.
Use the driver produced by `build_program_driver` in
`tests/python_misc/test_bootstrap_structural_text.py` for the desired checkout;
that helper reuses a content-keyed executable or builds one when needed. The
script uses the fixture's entry-file/library/prelude-cache protocol and records
the supplied binary identity. Hosted-only results omit the native fields.
Compare acceptance and the reason for rejection; diagnostics and inferred
coverage can change as the checker evolves. Unexpected native exit statuses,
timeouts and hosted implementation exceptions fail the probe run.
