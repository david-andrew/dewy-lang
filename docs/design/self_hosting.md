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

`node_store.dewy` (the node store: the `Node` record and its kinds `NK`, a new node, a node's
lists as runs of the second array, its children as an array, and a subtree's copy) is the first
of the parsers' two prerequisites; the intern table is the other. The two arrays stay ast.jo's
globals, taken by place (`@store @lists`): Sloppy reads and writes nodes' fields in place at
about 14,700 sites, in every phase, and their code is unchanged (the record's layout and every
field read are the same instructions). Nineteen modules that name `Node` or `NK` `use` the leaf.
The one-line field reads and flag tests (`kid`, `nkids`, `has_flag`, `add_flag`, `clear_flag`,
`set_kid`) stay in ast.jo; NF_* flags stay there too. The differential test runs one Sloppy driver
over the leaf or its twin on 40 random rounds of node building (every kind made, fields set,
lists of up to 40 children, runs, children read back, about 600 copies of subtrees) and compares
every node's fields and the runs with a Python store. Panel: flagships +0.13% (lex+parse +0.25%, resolve+check +0.29%), self-build +0.04%,
synthetic-22k +0.12%; 684 builds identical. What it
met:
- Sloppy can build a Dewy record only when every field has a default, so `Node`'s are `=0`; each
  such default was stored after the slot's zero fill: 19 stores a node, lex+parse +1.57%. A
  default that is the zero bytes (0, 0.0, `false`, an enumeration's first member) is now left
  to the fill, for every record (e4a7d0dd2).
- Sloppy's `kind >= .int_lit and kind <= .ident` (exact.jo) compared a Dewy enumeration's
  members as text, by name, as Dewy does: the scalar-leaf test misfired, facts +5%. Sloppy now
  orders one by position, as its twin's enum (ffbf1fcd5).
- The field one-liners as calls into the leaf cost the panel +0.80% (resolve+check +2.37%):
  `x not=? 0` is an `eq` and a `not` with two zero-extensions where Sloppy's `!=` is one `ne`,
  which takes helpers built on `has_flag` (`is_lit`, `written_at`, ...) over the inliner's size
  limit, so their callers call them (+7.5 M instructions on the panel); a checked `start + i`
  index in a counted loop adds an overflow pre-check of about 40 instructions a call (`kids`, now
  a loop over `[start..start + count)`); a loop leaf taking a place is not inlined into its caller
  in release (`set_list`, now one function); `lists[store[n].list + i]` adds a `jo` (`kid`).
- `int32(x)` into the runs checks each value's range, where Sloppy wrapped silently: two compares
  an element, kept.

`intern.dewy` (the compiler's names: a name's hash, its id found by its bytes, a new name's id)
is the parsers' other prerequisite, so both are now leaves. The table stays util.jo's three
globals (`names`, `name_hash`, `name_tab`), taken by place; `names[id]` and `name_of` are
unchanged at their 800-odd sites. The caller hashes (`hash_bytes`, which prelude.jo's index of the
library's names shares) and, for a new name, cuts its string; util.jo's `intern_sub` is a few
lines that Sloppy inlines into the lexers, its new-name path (`intern_new`) apart. The
differential test runs one Sloppy driver over the leaf or its twin on 25 rounds of names of any
bytes (malformed UTF-8 and NUL included) at different places, lookups that miss by a byte,
names whose probes wrap past the table's end, and a round past 8,192 names, where the table
grows; a Python oracle hashes and keeps the table, slots included. Panel: every item -0.04% to
+0.12% (hello +0.12%, lex+parse -0.04%); 684 builds identical. What it met:
- A string read from an array by place, `let t=texts[id] as array<uint8>`, or passed to a helper,
  is retained and released (about 20 instructions a lookup); `texts.ptr[id]` makes the array
  unique first and retains too. The view written twice in one expression,
  `(texts[id] as array<uint8>).length` and `.ptr`, does neither, at the cost of a second bounds
  check.
- Taking `.ptr` of an array parameter passed by value copies the array at each call (a lookup
  with the three arrays by value took 235 k instructions).
- `i + 8 <? n` on `int64`s is an exact `int` comparison, about 14 instructions a word in the
  hash's loop; `let last=n - 8` and `i <? last` is one. `(i + 1) & mask` checks the narrowing
  back to `int64`, about 20 instructions a probe, where `if i <? mask i + 1 else 0` is a `jo`:
  in name_add's probes this alone was synthetic-22k +0.24%.
- Each call layer counts: the leaf hashing inside name_find, under a wrapper that was not
  inlined, cost lex+parse +1.40% (flagships +0.33%); the wrapper inlined, +0.42%; the hash taken
  by the caller (no nested call, a new name hashed once), +0.01%. `@noinline` on the wrapper
  alone is flagships +0.17% more: a function returning early still saves all five callee-saved
  registers.
- Dewy cannot make a string of bytes it does not check, and a name may hold any (a string
  literal's source): `bytes as string | none` refuses malformed UTF-8, and `byte_slice` panics
  at a continuation byte. So the cut stays Sloppy's (`intern_new`); a Dewy parser interning a
  literal's span needs an unchecked byte range.
- A byte pool for the comparisons (each name's bytes appended, its start and length by id) took
  about 15 fewer instructions a hit but 190 more a new name (five pushes through a place):
  flagships +0.25% more, dropped.

The reference parser's first pieces are the ones that do not recurse: its node constructors
(dewy_syntax.dewy's `syntax_node`, `syntax_op_node` and `syntax_operator`, behind dewy_fast.jo's
one-line `dn_node`, `dn_op_node` and `dn_operator`) and a string's text up to its next
interpolation (literals.dewy's `literal_string_text`, which dn_string calls once a chunk for
both parsers; the interpolations' parsing stays with the parsers). The rest of the reference
parser recurses through the direct parser (`dn_value`, `dn_statement`, an interpolation's
`dc_expr`) and back, so it moves with a parser state record and hooks, or with the direct
parser. The path is cold: a flagship builds 1,300 to 6,900 syntax nodes (the
direct parser makes the rest) and reads 50 to 850 strings. The differential tests run one
Sloppy driver over each leaf or its twin: 17,180 spans of the repository's double-quoted strings
(from each start and after each interpolation) and 3,000 generated ones (escapes good and bad,
braces, malformed UTF-8, NUL, spans starting and stopping anywhere) against an oracle with the
escape rules of the literals test; 120 random build sequences against a Python tree. Panel:
flagships +0.00% to +0.03% (lex+parse +0.08%), every other item within 0.01%; 684 builds
identical. What it met:
- A call into the leaf costs about 70 instructions a string more than the inline loop it
  replaces (on the 99_dewy_frontend flagship, strings averaging 8 bytes, +62 k; 97, averaging
  18, breaks even): the leaf saves its callee-saved registers, and the run goes through
  `extend` (`out.extend(b[run..i))`, which costs less a byte than master's push). Returning
  at the brace cost 12 k more than breaking out of the loop to one exit.
  Reading the bytes through a checked pointer in place of `b[i]` saved nothing.
- The constructors cost about 10 instructions a node: the call layer, and the record pushed
  zero-filled and then stored field by field.
- The C seed compiler reads `'{'` as an unterminated string, so the twin compares with
  `123`.

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
string-literal union as its enum; the intern table is a leaf (`intern.dewy` above), the cut
of a new name left to Sloppy.

## Retiring the reference parser

The direct parser (dewy_direct.jo, `dc_*`) builds checker nodes; the reference grammar
(dewy_fast.jo, `dn_*`) builds `DewySyntax` that the projection (dewy_parse.jo, `dw_*`) turns into
the same nodes. A direct attempt that meets a form it does not take returns 0 and the reference
grammar re-reads that statement. Valid input across the corpus now falls back at 38 roots
(1,196 tokens; 123 and 2,687 before the last pass), the forms below. Error tests fall back at 120
roots: that is how every mistake is still reported.

Valid forms still read by the reference grammar (each to migrate, none needs a new rule):
- slices and indexes: an axis that is a bracketed open range (`a[0 [1..]]`, `m[2 [end,end-1..]]`),
  a member's spread in a loop source (`loop s in [m.keys...].sorted()`);
- refinements: a parameter refined by another (`b:int64<(>=? a)>`) with a proof result
  (`:><a <=? c>`), `int64<(in? (0..3])>`, `array<int64><0 <? length …>`, `uint8<m in? 2..254>`
  as a pattern, `int64 & ~0` in an overload member or a module alias (`nonzero = int64 & ~0`);
- functions: recursive local closures, a closure capturing a member, a function named `spawn`,
  a module partial (`twice = (*2)`), `$intrinsic` bodies, a lambda with type parameters in a
  record literal (`[f=<T>(x:T) => x]`), a type's generic method (`pair = <U>(other:U) => …`),
  grouped overload members (`(((a:T) => a) & …)`), keyword-only `(<value:int64>)` and grouped
  parameter patterns (`((a b):array<int64 length=2>)`), `(a:int64 <string>)` sequence patterns,
  `:>('b' | 'a') | none`;
- flow: a braced loop condition (`loop { … } { … }`, which warns), a `match` value before `;`,
  a `return` ending a comprehension's body, `[parallel …]` as an index, `??` before `=?` in a
  chain (`read() ?? 20 + 22 =? 42`);
- directives: bundle definitions (lib/directives.dewy), `$include_bytes(p"…")`.

What still needs the reference path besides those:
- Diagnostics. The direct parser reports nothing of its own (literal problems in `dn_string`
  aside): each mistake is the reference grammar's `dn_error` or the projection's `dw_fail`,
  `fatal` or `warn` (`[1; 2]`, `loop { ... }` with its body on the next line). Warnings on valid
  input are fallbacks too.
- `DEWY_FRONTEND=old` (`dc_enabled` false) and `compare` (each direct statement re-read by `dn_stmt`,
  projected and compared with `dc_same`; directive lines and settings compare their own
  results). The `tests/test_frontend_*` files run old, direct and compare side by side.
- Consumers that read syntax: `dw_top_declarations` for `$proof`, `$warn_if`,
  `$explicit_allocation_failure` and `$shadowable` (`dc_marker` builds their one-node syntax),
  module settings (`dc_setting`'s compact statement), `$target = …` / `$build.mode = …` in the main
  file (`dw_build_setting`), bundle definitions (`dw_dir_define`, lib/directives.dewy),
  `$intrinsic` bodies (`dw_intrinsic_check`); a deferred statement (`dc_defer_statement`) is
  reference syntax projected by `dw_stmt`; a module-level `$target` chain reads its left-out arms
  with `dn_expr` to note their names (`dw_target_dropped`).
- The formatter (dewy_fmt.jo) uses only the lexer (`dn_lex`, dewy_lex.dewy, dewy_tokens) and
  `dw_kind_name`; the language server (ide.jo) reads checker nodes and diagnostics. Neither
  needs the grammar or the projection.
- lib/directives.dewy holds only bundle definitions, `$name = { $setting  $setting=false
  $default_row = <row> }`, read today by the reference grammar and `dw_dir_define`.

Removal, in order (each step gated by the full suite, the bootstrap and same-output):
1. Close the forms above. Bundles: a direct reader building the `DirBundle` (its row through
  `dc_effect_row` without the leading `&`). `T & ~v` and the `(a b)` groups still routed through
  `dn_value` go with their consumers (`dc_refinement_alias` takes the refinement; `$test` cases
  are read directly now).
2. The direct parser reports its own mistakes: each `return 0` that marks a mistake rather than
  another reading reports the reference's text at its position. Gate: a fallback-free mode that
  stops at any fallback, every `.err` test identical, the error-root survey at zero.
3. Retire `compare` and `old`: delete the `dc_compare` paths, `dc_same*`, `DEWY_FRONTEND`; the
  triple-mode tests keep their programs as single-mode golden tests.
4. Delete the projection: dewy_parse.jo's readers of `DewySyntax` (`dw_expr`, `dw_stmt`, `dw_flow`,
  `dw_block`, `dw_declare`, `dw_type`, `dw_top_declarations`' syntax paths, …). The node builders
  the direct parser calls move to a node-side module first: `dw_finish_function`,
  `dw_range_value`, `dw_bigint_value`, `dw_value_name`, `dw_receiver_field`, `dw_add_receiver`,
  `dw_method_finish`, `dw_register_literal_methods`, `dw_target_name`/`dw_target_field_value`,
  `dw_dir_apply`, `dw_export_at`, `dw_supported_names`, the `dw_ffi_*` helpers.
5. Delete the reference grammar (dewy_fast.jo's `dn_expr`, `dn_stmt`, `dn_atom`,
  `dn_bracketed_from`, …; dewy_syntax.dewy's tree and `target_fold`). Keep the lexer, `dn_string`,
  the token rules (dewy_grammar.dewy: `dn_power`, `dn_can_start`, `dn_juxtaposed`), the edit log
  (`dn_edits_*`) and the file driver (`dewy_fast_file`), which the formatter, the language server
  and the direct parser use.

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
