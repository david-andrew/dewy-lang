# Structural compile speed, round 1

**Pilot the choice of integer formatter before the compiler demands its library
dependencies.** On flagship 100, one error message prints an integer that can only be 0, 1 or
2. Making that fact available at the call removed 14.29M compile instructions (8.71%) and
raised throughput from 140.8k to 144.5k processed lines/s. Flagship 99 has a separate
opportunity worth 28.31M instructions (9.76%) with its line count intact. Specializing literal
format patterns has the largest panel-wide instruction saving, but lowers the panel's measured
throughput.

## Measurement

Base `26ab55590`. Host for every number below was the x86-64 **desktop Intel Core i7-6700**,
local hostname `redfox`. All compiles were fresh, single-process default flagship builds with
`DEWY_EMIT_WORKERS=1`. The compiler itself used its normal release fixed point. The contract
calls for fresh builds from source, so each experiment pays for every library dependency it
reaches. [Compile-speed decision](../../decisions.md)

The earlier demand study found each completed function was already checked once. This round
measures two ways an unnecessary formatter becomes reachable and one case where a single
function body contains repeated work. [Prior demand study](demanded-body-plan-round1.md)

`python3 -m tools.core speed --base HEAD --counter perf` gave 1,697.8M retired user
instructions for 41,481 processed lines across seven flagships, or **153,921 lines/s** at the
gate's reference rate of 6.3G instructions/s. The self-build was 13.515G. At today's line
counts, 99 at 110,864 lines/s needs **44.6%** fewer instructions to reach 200k, and 100 at
140,498 needs **29.8%** fewer. These are the deficits for this revision.

The oracles used copies of the compiler, library and ladder under `~/dev/tmp/speedidea1`. Each
before/after pair used the same compiler, input, library and output paths, replacing source
contents in place. Whole-process numbers are medians of three runs with the speed gate's
hardware counter, rejecting multiplexed counts. The main scratch control was 1,693.782M for
the same 41,481 lines. The path difference from the gate matters, so all reductions below use
their own matched control. Counts came from ordinary builds. Separate `build --time`
invocations supplied line counts. Rates use the actual lines of each variant.

To repeat the word-format measurement, point `DEWY_CORE_LIB` at a copy of `lib` and use
the release compiler to `build` a copy of `100_rtos_kernel/design.dewy`. Wrap that command
in the gate's `count-instructions` helper three times on each side of the one-line edit
below. Sum the root, library and instance counts reported by the separate `--time` run.
The rate is 6.3 billion times that sum divided by median instructions.

To find the work, a scratch compiler split the existing phase counters by function instance,
lowered helper or module, retaining the enclosing bucket across nested calls. Its seven output
binaries matched the uninstrumented compiler byte for byte. Callgrind supplied dynamic call
counts on 99 and 100. All percentages use hardware instructions. A **deletion bound** gives
the named work for free, including dependencies that disappear with its last caller. A
**witness** compiles a narrower implementation of the same operation on the specified inputs.
Neither includes the cost of recognizing eligibility in a production compiler.

## Results

Each cell gives **deletion bound / witness** as a percentage of the whole compile. The panel
uses sums of instructions. A dash means there is no measured eligible witness.

| Rank and design | Flagship 99 | Flagship 100 | Seven-flagship panel |
|---|---:|---:|---:|
| 1. Choose a word formatter from the integer's proven range | 0 / — | 9.07 / 8.71 | 3.04% exposure at the general helper¹ |
| 2. Compile a uniform literal-member loop body once | 14.83 / 9.76 | 0.48 / 0.28 | 2.59 / 1.70 |
| 3. Select the formatter for a validated literal pattern | 9.23 / 8.65 | 0 / 0 | 7.87 / 6.92 |

¹ The 100 deletion removes the formatting **site**. The panel exposure empties just the body
of `__mi_format` everywhere. These oracles have different boundaries. The latter includes
sites whose values may genuinely need arbitrary precision.

### 1. Choose the integer representation before demanding decimal conversion

In 100's `parse_op`, the match that defines `arity` has three literal results. Its
interpolation is the only machine-code path from the program into `__mi_format`. That helper
reaches arbitrary-precision decimal printing, including reciprocal calculation and multi-limb
division. The unrestricted `to_int` input still needs arbitrary-precision parsing. Parsing
alone keeps a smaller set of helpers alive. Conversely, replacing just the slow parse body
with a constant error saved at most 3.89% on 100. This ruled out bounded parsing alone as the
first pilot.

In a scratch copy of `script.dewy`, replacing just `{arity}` with `{int64(arity)}` let the
existing strict checker verify the conversion. Instructions fell from 163.977M to 149.689M and
processed lines from 3,665 to 3,434. Replacing the entire observation with literal text saved
14.874M, the 9.07% deletion bound. The whole-helper deletion shows 7.35% exposure on 96 and
14.18% on 101. Narrowing eight printed counters on 96 saved only 3.83%. On 101 the checker
rejected the cast of the accumulated `right` because its upper bound was unknown. Neither row
is credited to the first pilot.

The original and narrowed binaries matched 100's golden output. Three malformed scripts
exercised the error message itself. Both binaries printed the same operand counts (0, 1 and
2) and exited with status 1. Their `check --obligations` outputs also matched.

The checker already chooses the bundled word writer for a proven positive remainder. Extend
that choice to a local with one dominating definition whose live match arms all return
signed-word literals. Resolve the normal semantic formatter first, as `exact_format_word`
does. Keep the exact type visible to the program and use the word representation only at that
observation. Check the defining write and reject intervening mutation, capture or escape. Use
the existing lowering support for word formatting, including correct handling of boxed values
if the admitted range extends beyond the immediate payload. The initial 0–2 case fits the
payload directly. Work is O(arms) on the first qualifying demand, memoized by definition, with
no new walk for other functions. The implementation risk is an unsound early range or
bypassing a user formatter. Estimated pilot cost is one engineer-day.

### 2. Avoid constructing the copies that reflection later merges

Both loops in 99's `tokens.dewy` visit 113 literal spellings. The compiler already checks a
template and emits a table-driven loop. Between those steps it constructs separate checked
bodies and lowers all 113 copies of each loop. The current matcher found equivalent IR for
both. Callgrind counted **224** invocations of `member_match_body`, two sets of 112
comparisons.

Hardware brackets in `member_lower_block` started after lowering the first member, split
before constructing `MemberMatch`, and stopped before table emission. Lowering remaining
copies cost **9.178M** and building and applying the match cost **6.282M**. Their sum is
**5.32% of 99** before replacement overhead. A lowering-only pilot would have less than 1M
instructions for all replacement work to clear 5%.

For a witness, bind `members(Symbol)` to a local on the loop's source line, then iterate the
resulting value. This compiles a single ordinary loop over the same ordered domain. Rewriting
just the punctuation loop saved 8.69%, just the spelling loop saved 1.03%, and rewriting both
saved 9.76%. Root AST nodes fell from 18,998 to 10,740. All **5,117** processed lines remained
and throughput rose from **111.1k to 123.1k**. The original and rewritten 99 had identical
`check --obligations` output and both matched the ladder golden. The optimistic deletion
removed the loops entirely, including work they alone caused. The analogous experiment on
100's 16-member `OpKind` loop saved 0.28%. Only these three source loops were changed in the
panel estimate. On 99's golden input, all six native execution counts for original and
rewritten binaries were between 4.46M and 4.48M instructions.

Use the existing template admission to prove that a checked body can be parameterized by the
member's string address or singleton ordinal. Record the ordered literal substitutions once,
then check, prove and lower one parameterized body. Admit only when overloads, conversions,
cleanup, emitted checks and proof decisions agree for the whole domain. Preserve the existing
member-specific path for type reflection, singleton-dependent decisions, debugging and any
uncertainty. For an admitted loop with M members, B body nodes and C substituted positions,
aim for O(B + M × C) work. The main risk is losing a member-specific diagnostic or a proof,
even when current final IR happens to match. Estimated cost is three to five engineer-days for
the existing admitted string-loop subset and differential coverage.

### 3. Retain a literal format pattern through helper selection

The checker validates `fmt'02x'(b)` in 99, yet the generic fixed-width writer still calls into
floating-point, exponential and general-format code. The same issue occurs in library source.
On 95, specializing the Dewy formatter alone saved just **0.29%**. The temporary-file name in
`lib/std/files.jo` also formats a word as hexadecimal. Following that last edge raised the
saving to **9.28%**.

The scratch library retained the format entry signatures and specialized the signed and
unsigned word writers to hexadecimal, preserving sign, zero padding, case and the widths used
by the panel. For fixed-point float patterns it called the existing correctly rounded
`__fmt_fixed` with the parsed precision. The Jo temporary-file name used the existing
hexadecimal writer and the RTC timestamp used the fixed writer for its literal `.3f`. The
general text writer stayed in place. The deletion oracle returned empty text at those three
numeric overloads and substituted constant text at the two Jo interpolation sites.

| Flagship | Bound | Witness | Processed lines, before → after | Thousands of processed lines/s, before → after |
|---|---:|---:|---:|---:|
| 95 | 9.86% | 9.28% | 6,286 → 5,528 | 139.0 → 134.7 |
| 96 | 0 | 0 | 3,694 → 3,694 | 139.6 → 139.6 |
| 97 | 8.88% | 8.78% | 6,661 → 5,919 | 146.9 → 143.1 |
| 98 | 7.42% | 6.23% | 12,144 → 11,604 | 206.5 → 210.4 |
| 99 | 9.23% | 8.65% | 5,117 → 4,378 | 111.1 → 104.1 |
| 100 | 0 | 0 | 3,665 → 3,665 | 140.9 → 140.9 |
| 101 | 19.44% | 13.23% | 3,914 → 3,373 | 186.8 → 185.5 |
| **Panel** | **7.87%** | **6.92%** | **41,481 → 38,161** | **154.3 → 152.5** |

In production, carry the validated literal through overload resolution to a small set of
shared writer families. Key selection by the chosen bundled overload, value representation and
pattern features. Keep dynamic patterns, unsupported features, custom formatters and genuine
other callers on their existing paths. Selection is O(pattern length) once per distinct
literal and type. Reuse the current rounding and layout functions. Sign, precision, negative
zero, width and first-class formatter values need differential tests. Estimated cost is two to
four engineer-days for the measured hex and fixed families. The witness saved 117.16M panel
instructions. The eliminated library lines are comparatively cheap. It ranks third for the
stated throughput goal.

## Pilot and stopping rule

Give the finite-match formatter one day. On the **unchanged** 100 source, require **at least
5% fewer instructions and higher actual processed-lines/s**, with the standard per-item speed
gate including the self-build. If the pilot removes the same 231 lines as the witness, it
must save more than 6.30% of instructions to raise throughput. Require identical diagnostics,
obligations and golden output. Exercise fallback for large signed values, reassignment,
escaped locals and custom formatters. Run the focused, quick, twin and kernel gates before
proposing a landing, then the full, independent bootstrap and fixed-point gates for the
batch. Stop this pilot if the conservative eligibility rule misses 100 or consumes the
measured gain.

The three witnesses were also compiled together on the same seven inputs, using only the
proven `arity` site for integer narrowing. They saved **9.46%** of panel instructions
(1,693.782M → 1,533.614M), while throughput moved from **154.3k to 155.8k**. On 99 the
combined result was 116.5k, below the 123.1k from reflection alone. On 100 it was 145.0k. Even
the combined experiment leaves both below 200k.

All seven literal-format binaries matched their ladder golden output. Combining the changes
produced different binaries only on 99 and 100, and both passed their goldens. A repeat run
of the byte-identical 95 binary timed out after its earlier successful run.
