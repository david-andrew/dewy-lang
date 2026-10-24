# Self-hosting readiness: zip pilot (2026-10-21, base da5fbd36, branch wt/selfhost)

Pilot: `tests/fixtures/selfhost/zip.dewy` is compiler/zip.jo hand-translated to Dewy, plus
its helpers (`put16`/`put32` from elf.jo, `append_bytes` from util.jo). `zip_jo.jo` drives the
real `compiler/zip.jo`. `tests/test_selfhost_zip.py` checks that both write identical archives,
in default and release builds, and checks them with Python `zipfile`. The inputs include an
empty file, deflated text, random bytes and a Unicode filename.

## Result

**zip.dewy compiles and runs today, with no private syntax.** It needs only representation
rewrites, and its archives are byte-identical to Sloppy's. Instruction counts (icount):

| workload | dev Dewy / Sloppy | release Dewy / Sloppy |
|---|---|---|
| zip: 3 MB random + 2.3 MB text | 2.065 / 2.065 G | 1.927 / 1.927 G |
| zip: 20 MB, stored path | 7.527 / 7.527 G | 6.863 / 6.862 G |
| lexer kernel (byte classifier, 3.2 MB of compiler source, x20) | 1.968 / 1.906 G (+3.3%) | 1.936 / 1.930 G (+0.3%) |
| IR kernel (1M-node record arena: build, then mutating fold x10) | 0.601 / 0.601 G | 0.478 / 0.478 G |

The two kernels were scratch experiments, and their outputs matched. As a
pilot, zip.jo is almost trivial: it never touches enum tags, pointer types, `extern`, OS
gating, tuples crossing languages, or a whole-module translation. The kernel parity shows
that the code generator is not the obstacle. The obstacles are surface and bootstrap.

## Constructs zip.jo needs (Sloppy -> Dewy)

| Sloppy | Dewy today | Class |
|---|---|---|
| global `int[]`, ranges, `xor`/`>>`/`&`, hex | works; `int` -> explicit `int64` (Sloppy `int` wraps, Dewy `int` promotes) | A |
| tuple `(str, u8[])[]`, `f.0`/`f.1` | `array<[string array<uint8>]>`, `f[0]`/`f[1]` (an array type with a type per position; round 4) | A |
| `when not BOOTSTRAP:` | dropped: stage0 never compiles Dewy, so the gate is meaningless here | see `$target` |
| closure capturing loop locals | works (snapshots) | A |
| `mut u8[]` | `@b:array<uint8>` / `put16(@h v)`, also across Sloppy<->Dewy | A |
| `len(str)`, `loop c in str` (bytes) | `s as array<uint8>` (specified view; measured zero-copy). `loop c in (s as array<uint8>)` converts the source | A |
| `data(out)+n`, `mem_copy` | the literal form compiles via undocumented Sloppy prelude leakage; `out.extend(src)` is documented and costs the same | A |
| `deflate` (lib/game/image.jo) | `from p"@lib/game/image.jo" import deflate` (it also leaks in unimported) | A |
| `write_bytes -> bool` | `write_bytes(path out) is? int64` | A |

## Compiler-wide gaps (probed; counts from the 10-20 audit)

| Gap | Class |
|---|---|
| `$target` / `$supported_targets` (modules-and-imports.md "Targets") | **a**, implemented |
| OS axis: `TARGET == "windows"` x44, macos, linux. The design's `$target` names only backends | **c** |
| Build-mode flags `BOOTSTRAP`/`DEBUG`/`WATCH`/`PROGRAM_NAME`: no spelling | **c** |
| Pointer type spelling (87 `*u8` types): `ptr<T>`, `p[i]`, `p + n`, `p as ptr<U>` under `$unsafe` (LANGUAGE.md "Foreign functions") | **a**, implemented |
| `extern` + `@lib`/`@symbol`: `=> $extern(name=... lib=...)` | **a**, implemented |
| Payload-free `enum` (557 variants): typed `const` tags today; designed nominal families | A / b |
| Byte-character literals (`'('`, 1194 uses): `b'('` | **a**, implemented |
| Path import without selection: the design splats it, the implementation (and tests) qualify it as `stem.name` | **a/c**: contradicts current behaviour, so David decides |
| Tuples crossing languages: Sloppy `(str, u8[])` is Dewy's `[string array<uint8>]` both ways (round 4: no separate tuple concept) | **a**, implemented |

## Mixed-language transition (FFI / host ABI)

There is no foreign boundary. Both frontends lower into one AST, checker and IR, so a call
across the languages is an ordinary call.

- **Dewy -> Sloppy**: `from p"x.jo" import f`, `@lib/...`, or a bare-name module (a Dewy importer
  falls back to `.jo`).
- **Sloppy -> Dewy**: `use 'lib.dewy'` (verified: Sloppy calls a Dewy `put16` through `mut`).
- **Type mapping**: `mut` <-> `@`; `T[]` <-> `array<T>`; `u8` <-> `uint8`; Sloppy `int` takes
  `int64`; `str` <-> `string` (Dewy indexes graphemes, so pass bytes on hot paths).
- **Enumerations**: a Dewy union of string literals (`Phase:type = 'lex' | 'parse'`) is a
  Sloppy enum to Sloppy code: `match p: lex:`, `.lex`, `Phase.lex`, `int(p)`, `Phase(1)`, table
  keys. Its members are numbered in the order its set was first written, so a twin's
  `enum Phase:` lists them in that order (`tests/test_selfhost_twins.py`).
- **C**: `$extern` in either language.
- **Bootstrap blocker for Dewy inside the compiler**: generation 1 (stage0 ->
  `core-bootstrap`) has no Dewy frontend (`bootstrap/frontend.jo`), and it builds generation
  2 from `compiler/`. So `use 'zip.dewy'` in wasm.jo would break `--bootstrap` unless a Sloppy
  twin is substituted for generation 2 too. That substitution is the frozen-twin step in
  miniature.

## `$target` in the design, and what is now implemented

- **Value**: a compile-time string naming the backend: `x86_64`, `riscv`, `arm`, `c`,
  `wasm32`. Here x64 (all OSes) is `x86_64`, arm64 is `arm` and wasm is `wasm32`.
- **Folding**: `=?` / `not =?` against a literal, and `in?` / `not in?` against a literal
  list, combined with `not`/`and`/`or`, fold while lowering.
- **Gated `if`**: it compiles only the live arm and splices it into the enclosing scope, at
  module level (imports and declarations) or in a block. Dead arms are never checked.
- **Mixed conditions**: a condition mixing `$target` with runtime values stays an ordinary
  `if`.
- **Misspellings**: an unknown target literal is an error.
- **`$supported_targets = [...]`**: once per module, at file scope; any other target is an
  error.
- **Tests**: `tests/cases/target/*` (native and web), plus `tests/test_target_names.py`
  (x86_64, wasm32 and arm64 under qemu).

## Leaves shipped (B3)

`zip.dewy` (the web build's archive), `spelling.dewy` (the checker's "did you mean"
distance), `leb128.dewy` (the one LEB128 encoder of the wasm, DWARF and Mach-O
writers, formerly three) and `base64.dewy` (the web page's module and icon, and the
macOS signature's hashes, formerly two encoders). Rules, enforced by `tests/test_selfhost_twins.py`: every
`compiler/*.dewy` has its `FROZEN_TWINS` entry; it imports only the library and the
compiler's other Dewy modules, never a Sloppy one; its twin defines no name it lacks; each `.jo` module calling it
`use`s it (Dewy names reach only their importers, unlike Sloppy's shared namespace). Each
pair has a differential test (`tests/test_selfhost_*.py`) against an independent
Python oracle in default and release builds. Compiler output stayed byte-identical
(734 builds: examples and ladder, native, `--release`, `-g`, wasm32, aarch64-mac,
x86_64-windows; `python3 -m tools.compiler.same_output` checks this against a base commit).

`line_table.dewy` (each file's line starts and the last line found: `line_col`) is
the first stateful leaf. A leaf owns its state type (`LineTable`) and takes it by place
(`@t`); Sloppy keeps the one global (`src_lines: LineTable` in util.jo) and passes it in.
The type has no defaults, so the zero value is the empty table and the Sloppy global runs no
initializer in module order. Its word-at-a-time newline scan matches Sloppy's instruction
count (`speed`: flagship panel within 0.01%).

`sha.dewy` (SHA-256 and SHA-1: the macOS signature's page hashes, its LC_UUID and the
bundle's sealed icon) and `icns.dewy` (the bundle's icon) are the first hot leaves. Words
are `uint32<overflow='wrap'>`; the schedule and constants are `array<... length=64>`,
which drops their bounds checks. Like for like (rotations as two shifts and an or), the
Dewy SHA-256 needed +51% of Sloppy's instructions. The shipped one rotates by shifting the
word doubled into a `uint64<overflow='wrap'>`, computing that once per sigma: 1.485 / 1.527 G
(release 1.407 / 1.491 G) hashing 10 MB by pages. SHA-1 is 0.949 / 1.045 G. An aarch64-mac
build of the compiler takes 1.5% fewer instructions and writes the same bytes.

`targets.dewy` (the target names: their tables, a name's processor and system, and why a
requested target cannot be built) is the first text leaf and the first user of
`s.byte_slice(a b)`. The rest of the old targets.jo is `settings.jo`'s: the host's name
(read from the compiler's own executable) and the command line's and main file's
settings, globals that Sloppy code sets. Its gaps:
- A proven `byte_slice` still calls the library's checked `__dewy_byte_slice`, which
  checks the bounds and both boundary bytes again before the string slice checks the
  bounds once more: about 430 instructions a 10-byte slice against Sloppy's 355 (release
  335 / 275).
- The facts do not know that the byte after an ASCII byte starts a character, so after a
  guard `b[i] =? b'-'`, `name.byte_slice(0 i)` is proven but `name.byte_slice(i + 1 n)` is
  a run-time check. Its diagnostic prints that end as an empty `` `` ``.

`json_doc.dewy` (the language server's JSON: a message read into a tree of nodes, its
values read back, text quoted and values written again) also reads `dewy-core test DIR`'s
per-file result lines, so main.jo's second JSON decoder is gone. It is the first leaf with
an enumeration (`JsonKind`, a union of string literals; Sloppy never names its members),
records in an array arena changed through a place (`doc.nodes[v].key=k`), mutual
recursion over two places (`@doc @r`), and `match` on bytes and over the enumeration
without an `else`. It compiled as first written. Parsing a 640 KB `didChange` message 20
times takes 1.398 G against its twin's 1.568 G (release 1.198 / 1.216 G); the language
server is outside the flagship panel. The differential test found a hang in the old
parser: inside a list, a byte that no value starts with (`[}`) read as an empty number
without moving on. That is now no value, which ends the list. What it met:
- A Dewy record whose fields have no defaults has no `T()` in Sloppy (Dewy requires every
  field without a default); Sloppy writes `JsonDoc([])`.
- About 60 run-time bounds checks remain (the leaf is cold). A scan position kept in a
  record field reached by place (`r.at`) carries no facts. Refining the field
  (`at:int64<at >=? 0>`) leaves 44, but then each `r.at+=1` gets a wrap check, and after
  `let start=r.at` and a scan, `r.text.byte_slice(start r.at)` cannot prove
  `start <=? r.at`. A local scan position, copied back, would prove them.

`manifest.dewy` (a program's packages as text: the build block's specs, dewy.lock's pins,
a URL's cache directory and default name; pkg.jo keeps git, the cache and the files) is the
first leaf with a dictionary (`pkg_lock_read` gives a `dict<string string>`, a `{str: str}`
to Sloppy) and records pushed by place (`@specs:array<PkgSpec>`), and the first to cut text
with the library's members (`split` with a limit, `trim`, `remove_prefix`, `replace`,
`contains`, `sorted`, `join`). It compiled as first written, but for a parenthesis the
compiler asked for (`loop c in (s as array<uint8>)`). Panel: +0.00% on every item; 684 builds
identical. Reading 200 specs is +35% on its twin (release +31%), the lock file +1%. What it met:
- Malformed UTF-8: both frontends take it in sources and Sloppy slices it anywhere, but
  `byte_slice` panics when a slice starts on a continuation byte, as one after an ASCII
  delimiter can in malformed text. `split`, `trim`, `remove_prefix` and `replace` pass such
  bytes through unchecked, so the leaf cuts with them and keeps `byte_slice` to ASCII ends.
  With no unchecked byte range (`bytes as string` validates), the slice's check and the
  library's pass-through disagree about what a string may hold.
- A byte loop (`b[i] =? 10 and b[i + 1] =? b'b' ...`) takes 9.2 instructions a byte
  (release 11.2) against the library `find`'s 2.4: the bounds checks stay in the loop though
  `check --obligations` reports none, and release spills the length. `pkg_block_at` scans
  every main file, so it asks `contains` first, which matches the twin.
- Facts (cold here, so checked at run time): `if xs.is_empty {return}` then `xs[0]`;
  `parts[parts.length - 1]` of a `split` (never empty); `s.byte_slice(0 if n <? 12 n else 12)`
  (an `if` expression's bound); `j <=? n` after `let j=i + 1 loop j <? n and b[j] not=? 10 {j+=1}`.
- Both readers of commits (the lock file's, `git ls-remote`'s) now keep only whole commits
  (40 lowercase hexadecimal digits), so a pin's 12-digit form cuts ASCII; a garbled pin is
  resolved again instead of fetched.

`literals.dewy` (a Dewy literal's text to its value: a whole number in any base as a word
or as 2^32 limbs, a based string's packed bytes, a string's escapes, and what is wrong
with an interpolation's format spec) is the first leaf of the front end proper and the
first with error values: `type of error` kinds with payloads, a positional result inside
an error union (`:>[string int64]|LiteralUnsupported`, taken apart with
`let [a b]=... or_throw`), `match` on unions with payloads, and a closure. The C seed
compiler, which builds the twin, has no unions, so an error union cannot cross into the
compiler yet: the functions Sloppy calls `match` their result into a `LiteralProblem` the
caller passes by place. dewy_fast.jo's string loop calls the leaf only at a backslash, and
dewy_direct.jo keeps its inline decimal path. Panel: self-build +0.17% (it compiles the
leaf), every other item within 0.04%; 684 builds identical. Through one Sloppy driver over
either module, 4000 numbers take 44.0 M instructions against the twin's 51.2 M (release
36.5 / 40.2 M), 4000 format specs 10.7 / 11.1 M; an escape costs about 95 instructions
more than the twin's (release 125), of which an error-union result and its `match` are
about 37 (31) against a status record by place. What it met:
- An array literal where a union or an optional holds a positional array type
  (`:>[string int64]|Bad`, `[int64 int64]|none`) built an array and failed to check. It
  now takes the positional type when the union holds no array (expr.jo
  `literal_union_member`).
- One arm for several bytes, `<b'u'|b'U'> => ...`, is refused: an integer singleton union
  may miss at most 24 values between its ends, and `U` and `u` are 32 apart. The leaf
  tests them with an `if` before the `match`.
- A string's `length` counts characters, so a prefix check `text.length <? 3` passes
  `"0é"`; the leaf compares bytes.
- Malformed UTF-8 again: an unknown escape or format type was echoed as its first byte
  alone, which made the message malformed too. Both twins now show the whole character, or
  `byte 128` for a byte inside one.

`dewy_tokens.dewy` (the Dewy frontend's 124 tokens: each one's spelling, the token a
spelling is, and the tokens related to one, `not=?` to `=?` and `.+` to `+`) is the first leaf
whose enumeration Sloppy code names throughout: five modules (the lexer, both parsers, the
formatter, the foreign-function spellings) write `.kw_xor`, `DewyToken(i)` and
`int(DewyToken.kw_or_throw)`, and the lexer's tables are indexed by it. `dn_word_assign`,
which reads the source through a pointer, moved to dewy_fast.jo, its one user. It compiled as
first written. Panel: every item within 0.03% but 100_rtos_kernel, -0.21% (see below);
684 builds identical. Called 12.4 M times from one Sloppy driver over either module, each
function takes its twin's instructions (`dn_token_kind` +0.6%). What it met:
- A Dewy `match` on an enumeration with literal arms (`<'lparen'> => "("`) compared the value
  with each arm in turn, where Sloppy's arms on the same enum dispatch through a jump or
  lookup table: `dn_token_text` took 118 instructions a call more than its twin,
  `dn_token_undot` 57 and `dn_token_assignment` 43; the panel's lex+parse grew 0.5%. Such
  an arm is now the variant pattern Sloppy's is (expr.jo `check_match`), so Dewy programs get
  the tables too (`tests/test_match_enumeration_table.py`): compiling 100_rtos_kernel, whose
  report matches on 37 such arms, takes 0.21% fewer instructions. No program of
  same_output's corpus has one. A match giving an `int` keeps its compares: lower.jo's
  lookup table (`gen_match_lookup`, taken when every arm is a constant) writes the constants
  as plain words, which an `int` does not hold. It already gives wrong values on an integer
  scrutinee: `let n=match x {<1> => 10 <2> => 20 <3> => 30 _ => 0}` with `x:int64` gives 5, 10
  and 15 (open, the lowering's).
- `members(DewyToken)` lists the members in text order, not as numbered, so the Dewy driver's
  table is compared sorted; the numbering is checked through the Sloppy driver over the leaf.
- It is the first leaf a bootstrap module uses (dewy_fmt.jo, which step 1 replaces with a
  stub): build.py put the compiler's dewy_fmt.jo back for step 2 without its twins, so the
  seed read the leaf. It now names the twin there, and the leaf again from step 3.

`habits.dewy` (what a name from another language is here, `append` to "`push`", for Dewy and
Sloppy programs and for a map's members, and whether a hint is written for Sloppy) and
spelling.dewy's `did_you_mean` (the nearest candidate) take the checker's "did you mean" hints out
of check.jo, which keeps a habit's fit to the receiver and the interned names. The first leaf
with a set (`set[... surface...]`) and `min_by` with a key closure; the four tables are `match`es
on string literal arms. It compiled as first written. Cold, but reached: overload resolution words
a "no parameter named" message for each version it rejects, so flagships 97 and 98 each ask
twelve times for `key`. A first draft read the tables into arrays of pairs on each call, 46 k
instructions a call (97 +0.14%, check +0.22%); the matches cost what the old global arrays' scan
did. Panel: every item -0.01% to -0.07% (the Sloppy tables were globals built at start); 684
builds identical. 20000 lookups of a missing name, each with a nearest-name choice, take 380 M
instructions against the twin's 608 M (release 348 / 899 M; the twin builds its arrays each call).
What it met:
- The old word scan for Sloppy-shaped hints began a word at any byte from 0x80 but continued
  only over ASCII, so a hint with a non-ASCII letter never ended (no hint had one). Both twins
  read ASCII words.
- Later duplicates in the tables (Scratch's `clone`, Processing's `size`, a second `index` and
  `parse_int`, Dewy's second `str`, `float` and `items`) never matched; they are gone, as
  unreachable arms would be refused.

`dewy_layout.dewy` (`dewy-core fmt`'s layout of Dewy text: indentation by the brackets open and
by continued statements, the spaces between lexemes, and the lines kept as written) is the
first leaf that imports another (`from p"dewy_tokens.dewy" import ...`; twins' imports are
swapped like any module's) and the first whose record the compiler's hot path builds: the lexeme
(`DewyLexeme`) and its kinds (`DewyKind`) moved into dewy_tokens.dewy, and the lexer fills an
array of them through a pointer. dewy_fmt.jo keeps the lexing. The state (the open delimiters,
their lines' levels, the angle brackets) was four globals and is a record by place. It gives
bytes, which dewy_fmt.jo takes as they are (`str_from_bytes`). It compiled as first written, but
for `end`, which is reserved. Panel: +0.00% on every item, the self-build included; 684 builds
identical. `fmt --check` over tests/cases takes 1.287 G against master's 1.481 G (legacy_corpus
1.171 / 1.334 G), and 8762 files (the repository's Dewy and disturbed copies) format identically.
The differential test lexes as dn_lex does in Python (the tokens and spellings read from
dewy_tokens.dewy) and lays out independently. What it met:
- A first draft built the text with `byte_slice`, which panics where Sloppy slices malformed
  UTF-8 anywhere (see `manifest.dewy`): `fmt` stopped on a line starting `\x80abc`, which the
  lexer takes as a name. Bytes moved as bytes need no boundaries, and cost 13% less.
- dewy_fmt.jo is a bootstrap module, so step 1 has no user of the leaf: `use_frozen_twins`
  skips such a module there (`stubbed`).
- `T('member')` on a union of string literals was not a conversion, and its hint was wrong;
  `let c=Color('red')` converts since 5c97ea170.

`dewy_lex.dewy` (the Dewy lexer's scanners: a quoted string's end past its interpolations,
nested strings and comments, an interpolation's closing brace, a block comment's end and a
skipped library body's end, with the state they keep, the brace a mistake notes and the
mistake) is the first leaf the lexer's loop calls, and the first that reads source through a
pointer: each entry point checks its span once, and `dx_` forms take the bytes for dn_lex, which
has checked its own. A mistake is recorded in the state (`DewyLexer`, a Sloppy global passed by
place) and the scanner gives -1; dewy_fast.jo reports it. The parser (a string's
interpolations, a format spec's colon), the prompt and the editor's comment scan share the
scanners; lex.jo's copy of the block-comment scan is gone. It compiled as first written but for
`end`, which is reserved. Panel: within +0.06% on every item (lex+parse +0.08%); lexing the
repository's Dewy sources ten times takes 0.512 G against master's 0.525 G.

`module_paths.dewy` (paths as the compiler keeps them: a path's normal form, directory, stem
and extension, a Windows path's spelling; a module's identity; the file `use 'x'` or `p"x"`
names, a package's file, the files a named import may be and the hint for a Python module's
name; the language server's file URIs; the run cache's name hash) is the module loader's text,
the front end's first stage. It reads no disk: the callers probe its candidates. The leaf is
pure, so one Sloppy driver runs over the leaf or its twin, and the differential test gives both
any bytes, malformed UTF-8 included. Fourteen modules call it (ide.jo's `ide_norm` is
`path_norm`; util.jo's `strip_ext`, `os_path` and `is_abs_path` moved), and it imports
`json_hex` from json_doc.dewy. It compiled as first written. Panel: every item -0.01% to
-0.07%; 684 builds identical. 20 rounds over the repository's 14822 paths (each a module key,
stem, directory and `use` path) take 2.545 G instructions against the twin's 2.845 G (release
2.118 / 2.400 G). What it met:
- A slice starting after a `/` panics where the next byte continues a character in malformed
  text (see `manifest.dewy`); the differential test found it in `path_stem`. Splitting the path
  instead cost hello +0.73% and lex+parse +0.70% (a module's name is its path's stem, for every
  library file), so the name is split off only after a byte from 0x80.
- The `$target.os =? 'windows'` arm is never checked in a Linux build, so a `+` joining text
  there (an error in Dewy) surfaced only in a Windows build of the compiler. That arm's work is
  `windows_path`, which the test runs on every system.

`dewy_syntax.dewy` (the Dewy parser's syntax tree: the node record `DewySyntax`, a node's
children, the reading an ambiguous node takes, the operator a node applies, the kind names, and
the `$target` and `$build` conditions that fold while the tree is projected, with the settings'
places) is the first leaf over the parser's output, and the first to recurse over a union: the
fold is `bool | none` (none: not a target condition). dewy_fast.jo builds the nodes into Sloppy's
global array, which every query takes by place (`@tree`); dewy_parse.jo's `dw_child`, `dw_op`,
`dw_target_live`, ... (about 700 call sites) are one-line calls into it. A mistake (an ambiguous
expression, an unknown target, `$build.debug`) is kept in a `SyntaxProblem` by place, the first
one only, and the leaf gives up; the caller reports it where `fatal` was. The differential test
builds 160 random trees of the parser's shapes (operands inline or listed, an operator as a
child, combined assignments, groups, ambiguous readings) and asks 124 k questions; its oracle
stops at the first mistake by raising, so it checks that giving up never changes which mistake
is reported. It compiled as first written. Panel: every item -0.06% to +0.05%; 684 builds
identical. What it met:
- Calling the leaf's `syntax_unwrap` for every node cost the panel's lex+parse +0.85% (96_ct_crypto
  +0.30%): a call per node where most are neither a group nor ambiguous. That test stays inline in
  `dw_unwrap`, which is now cheaper than master's.
- A Dewy record whose fields have no defaults has no `T()` in Sloppy (see `json_doc.dewy`):
  the tree's two sentinels are written out.

`dewy_grammar.dewy` (the grammar's rules over the lexemes, which both parsers follow: each
operator's binding power and grouping, the prefix powers, which way a comparison chain runs,
where an expression may start and a range's bound follow, when operands written together
multiply and when they may not, the operators a parenthesized right operand makes a function
of, the metatags with their own argument grammar, the hint for another language's operator,
`<<` as two openers, and an interpolation's format-spec colon). The parsers' loops stay: the
direct parser builds the checker's nodes and interns names, the reference parser the syntax
tree, and each falls back on the other, so neither moves before the node store and the
intern table do. Lexemes are taken by place with the position read (`@tokens at`). The
differential test checks the binding powers against docs/LANGUAGE.md's table (each
row's order, a prefix's operand against the rows above it, the right-grouping rows; they
agree) and follows the other rules from juxtaposition.md and the guide, over 400 random lexeme
runs and 3000 interpolation texts. It compiled as first written. Panel: every item within
+0.02% (lex+parse +0.03%); 684 builds identical. What it met:
- The juxtaposition test as one call (`dn_juxtaposed`) cost synthetic-22k's parse +0.9%: most
  unspaced `(` are calls after a name, which the inline test (a number or a group before)
  rules out without the call, as Sloppy's inlined helpers did.
- `op =? 'caret' or op =? 'dot_caret' or ...` costs a compare an arm where a `match` on the
  enumeration with a `true` arm is a table load, and a three-`if` prefix power is not inlined:
  as written first, lex+parse +0.25%; as `match`es, +0.03%.
- `byte_slice` panics where a spec after the colon starts with a byte inside a character
  (malformed text, see `manifest.dewy`), where Sloppy slices: such bytes read as `z`, which no
  spec gives a meaning to either. A spec costs about 155 instructions more than the twin's
  (`byte_slice`, and bounds checks in the scan), 15 an interpolation without one: hello +0.02%.

The whole lexer was ported first (dn_lex's loop, keywords found by their bytes, names
interned by the caller): lexing took +11% (+28 instructions a lexeme; synthetic-22k +0.74%,
lex+parse +0.83%), so the loop stays in Sloppy. Its loop alone matched Sloppy's; the cost was
around it, in codegen gaps (all open):
- Indexing an array keeps its bounds check where the index is proven, even with `--release`:
  `loop i <? n {... b[i] ...}` with `n=b.length`. A pointer read under `$unsafe` drops it.
- A `const` table's address is loaded again in every iteration of a loop that indexes it
  (`DX_CLASSES[p[i]]`), and an `array<T length=N>` has no `.ptr`; passing the table as a
  parameter keeps it in a register.
- `out.push(Lexeme[...])` zero-fills the slot, then stores every field: about 14 instructions
  a lexeme over Sloppy's stores into a presized array. Presizing with `fill` and storing
  through `.data()` or by index spilled more.
- A small function returning early still saves and restores its callee-saved registers
  (`dx_word`, the keyword test: about 12 of its 35 instructions a word).
- The interning table is Sloppy's, so names were interned in a pass after the leaf (about 8
  instructions a lexeme); a function-typed parameter (`intern:<(s:string at:int64 n:int64):>int64>`)
  cost more than the pass.

Open gaps from these leaves, by cost:
- A literal beside a policy-typed operand (`w + 1`, `w & 0xFF`, `w xor 0xFFFFFFFF`) goes
  through `int` and `__mi_low_word`, about 30 instructions in place of one. Plain `uint32`
  does not.
- Wrap lowering zero-extends after every 32-bit operation, even shr/and/or/xor, whose
  results already fit. It keeps a dead `and -1` after a constant shift and never forms a
  rotate.
- A loop counter is `int`, so `at + t * 4` with `at:int64` is checked `int` arithmetic
  (+21%) unless it is written `let q:int64=...`.
- A one-line helper with four checked byte loads is not inlined (+6%). Repeated pure calls
  are not shared (+19% when each rotation doubles its own word).
- Sloppy's style, `int64` with `& 0xFFFFFFFF` masks, costs 3x: the mask's bound does not
  reach the exact additions through array elements.

Gaps met on the way, and since closed: `bytes as string ?? ""` converts to
`string | none` and falls back; `fill(v n)` is documented; Sloppy takes a Dewy
string-literal union as its enum. Still open: the intern table (`hash_bytes`) as a leaf
costs +0.5–0.8% on the panel (lex+parse +2%): a new name needed a byte-range substring
Dewy lacked (copy loop, UTF-8 check, conversion: ~600 instructions against Sloppy's ~250;
`byte_slice` now, at about 1.2x Sloppy's, see `targets.dewy` above), and
Sloppy retains a string passed beside a `mut` place (~20 instructions a call).

## Decided rules

Moved here from the decisions ledger ([decisions.md](decisions.md)), which keeps
a pointer to each rule. The wording is David's.

### FFI (Q12/Q24)

- FFI (Q12/Q24): `$extern` is a body-position metatag with optional keyword
  arguments (`=> $extern`, `=> $extern(name='Sleep' lib='kernel32')`). It
  replaces the `extern` keyword, which is un-reserved. `$export` (provisional)
  makes a function callable from C, Rust and Python. Calling `$extern` or
  dereferencing a raw `ptr<T>` (provisional; `ptr<T>?` nullable) needs an
  unsafe boundary. The goal is batteries-included Dewy with seamless,
  bidirectional FFI (C, C++, Rust, Python, JS/wasm); header bindgen comes
  later. A blocking-style `net` module returns `| NetError | Canceled`, over
  FFI for now.
- C interop: `$export` may share the line with its definition (a metatag
  applies to the next thing). `$unsafe` applies to the next expression, on the
  same line or the next (`$unsafe strlen(msg.ptr)`); several expressions use
  `$unsafe { ... }`. This replaces the provisional "own line, rest of the
  block" form.

### `$target` and `$build`

*The canonical target names below (and the `$build`/`$target` namespaces,
2026-10-23) are later than the value list under "`$target` in the design, and
what is now implemented" above (`x86_64`, `riscv`, `arm`, `c`, `wasm32`) and
supersede it. Q24's splat import (`import p"x.dewy"` with no selection) is
decided; the table row above that calls it undecided predates it.*

- `$target` keeps its spelling. Canonical names with only the fields they need
  (`x86_64`, `aarch64-linux`, `riscv64-freestanding`, `c-linux`, `aarch64-mac`,
  `x86_64-windows`, `wasm32`, …; not LLVM triples), per the archived
  status.md list. OS and arch are selected by compile-time conditions on
  `$target`.
- `$build`: a compile-time record like `$target` (`$build.mode =? 'release'`;
  `$build.debug` was removed 2026-10-23). Project flags (e.g. BOOTSTRAP) are ordinary consts in a build
  module the entry module overrides; no CLI `-D` flags.
- `$build` and `$target` (decided 2026-10-23): namespaces with members (a
  deliberate exception for build facets). Statement position sets, expression
  position checks, as for every metatag: `$build.mode = 'release'`,
  `$target = 'aarch64-linux'`, `if $build.mode =? 'debug' {...}`,
  `if $target.os =? 'windows' {...}`. Boolean members take the bare form for
  true and `=false`. One member per fact: `$build.mode` is `'debug'` (the
  default, what plain `dewy FILE` builds) or `'release'`; `$build.debug` is
  removed. The file is the preferred place to set them; command-line flags
  (`--release`/`--debug`, `--target …`) override the file, and an override that
  contradicts a value set explicitly in the file builds with a warning naming
  both. Only build mode and target can be overridden from the command line;
  safety and semantic metatags (`$runtime_checks`, `$no_hidden_costs`,
  `$bulletproof`, …) are never settable from the command line.
