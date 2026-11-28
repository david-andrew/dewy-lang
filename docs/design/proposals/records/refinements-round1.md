# Records, round 1: an inferred field keeps its value's refinement

An inferred record literal stores each field's plain base type, so refinements are lost:

```dewy
Count:type = int64<n => 1 <=? n and n <=? 400>
mk = (c:Count) => [cells = c]       # today: [cells:int64]
need = (c:Count) => c
need(mk(5).cells)                   # error: cannot prove `mk(5).cells <=? 400`
```

`argparse.parse` builds its result this way, so it loses every range it has just checked.
Ladder 151 (`tests/ladder/151_ring_traffic`) checks each argument again, and can't hand the
record to a helper. Several documents say the field keeps its refined type: LANGUAGE.md
("Command-line arguments", whose example types the fields), the library's own header ("the
field keeps that type"), D48, and the design note `argparse_and_reflection.md`. This round
asks whether the documents or the semantics should change.

**Verdict:** the semantics should change. Option A: a field takes its value's declared type,
outer refinement included. It passes both questions of the two-question test, the design
already implies it, and it adds no syntax, so it can be taken without asking David. No item
for open_decisions.md.

## What the compiler does today

These were probed on this branch's head (scratch programs; the results are below):

| Code | Field type today |
|---|---|
| `[cells = c]`, `c:Count` | `int64`: the outer refinement is dropped |
| `[a = xs]`, `xs:array<Count>` | `array<Count>`: kept (`r.a.push(0)` is refuted) |
| `[o = m]`, `m:Count?` | `Count?`: kept (`r.o = 0` is refuted) |
| `[s = s]`, `s:Sign`, `Sign:type = <-1\|1>` | `int64`: dropped (an integer literal union is a refinement) |
| `[m = m]`, `m:'a'\|'b'` | `'a'\|'b'`: kept (a string literal union is its own type) |
| `[c c]` (array literal), `Box(c)` (inferred `T`) | `array<int64>`, `Box<int64>`: dropped |
| `let y = c` | `int64`, with the range kept as a fact (`y = 0` compiles) |
| `ret = (c:Count) => c` | the caller knows `1..400`: an unannotated function's result facts reach its callers |
| `let r:[cells:Count] = …`, then passed where `[cells:int64]` is wanted | accepted: a record converts by value to a looser shape |
| `[a = xs as array<int64>]`, `[o = c as int64]` | plain: `as` widens |

So only the **outermost** refinement of a scalar is dropped, and only on its way into a
literal or a binding. Anything nested inside the value keeps its declared contract, mutation
of that contract is already checked, and inside one function, facts hide the loss. It shows only
when the record crosses a function boundary, which is the whole job of argparse's result.

## What David and the design already say

- **`argparse_and_reflection.md` (decided with David, 2026-09-02):** "A refined `T` is
  validated at parse time and the field carries the refinement statically afterwards", and the
  result type is "`[… tabsize:int64<0 <? value <=? 16> …]`. Nothing in the checker knows the word
  'argparse': the type comes from ordinary inference over `parse`'s body." The decided design
  names this outcome and says ordinary inference produces it. The library's `take` already
  returns `T` (the descriptor's type argument, `Count`), so a field that takes its value's type
  gives exactly the documented record.
- **refinement.md §2:** "Ordinary inferred literals/lengths remain facts, not permanent
  assignment types." A literal's value doesn't become a field type under option A.
- **refinement.md, decided rules (invariants):** "Public interfaces use written contracts;
  inferred facts stay private." Under A only written contracts move into the field: a binding's
  annotation, a parameter's type, a declared result, a type argument. A guard's fact doesn't.
- **refinement.md §4 and LANGUAGE.md, "Refinements also apply to record fields":**
  constructors, defaults, conversions and stores check field contracts; `@` access needs an
  equivalent contract; "immutable value forgetting is safe". Everything A needs for soundness
  exists.
- **LANGUAGE.md, records:** "Without an expected type, named fields infer an anonymous record.
  Anonymous record types agree by field names and types." It doesn't say the types are plain.
- **`resources/discussion_points.md`, "Refinement types / subtyping":** David's notes cover
  spelling only (`int & <x => x >? 0>`, partial operators, named-property conditions). Nothing
  on inference.
- **D48** (open) builds on the documented behavior: its intro says "the field keeps its
  refinement", and Q5's `argparse.Parsed<Spec>` is "the record type `parse` gives". Its backup
  program's `prune` slices with `a.keep`, an `int64<(>=? 1)>`, inside a handler. Under A, D48
  is right as written; under B, its examples need guards.

## The options

### A. A field takes its value's declared type (recommended)

1. Without an expected type, a record literal's field takes its value's type as written
   contracts give it: a binding's annotation, a parameter's type, a function's declared
   result, a type argument (argparse's `T`), a declared field or element type. Today the
   nested contracts are kept and the outer one is dropped; under A the outer one is kept too.
2. **Facts are not types.** A literal (`[n = 5]`), arithmetic (`[n = a + 1]`) and a value a
   guard proved (`if x >? 0 [n = x]`) give the base type, as today. A `let` keeps forgetting
   its own outer refinement (its facts cover the function it lives in).
3. **Dependent atoms are dropped.** An atom naming another binding (`b:int64<(>=? a)>`,
   `i:uint64<(<? xs.length)>`) would mean nothing outside that binding's scope. The field keeps
   the closed atoms (literals, module consts, `.min`/`.max`); `addr` stays `addr`. A self-length
   array contract is forgotten, as `let c = p` already forgets it. Rebinding to a sibling field
   (`[low = a high = b]` giving `high:int64<(>=? low)>`) is not attempted.
4. **Values with several sources** (`if`, `match`, `??`): if every arm has the same type, the
   field takes it. Otherwise, if one arm's declared type admits every other arm, the field
   takes that type. This is judged as array element conversion judges it: literals by their
   value, other arms by their constant bounds. A literal is never the candidate itself.
   Otherwise the field gets the base type.
   `if serial 1 else a.jobs ?? 4` gives `Jobs`; `if serial 0 else a.jobs` gives `int64`.
   Construction is never an error.
5. Integer literal unions (`Sign`) are refinements and are kept; string literal unions already are.

**Soundness.** A store into such a field is a store into a refined field, and that is
already checked: `r.cells = 0` is refuted and `r.cells = n` needs a proof. An `@` pass to a
plainer shape is already rejected. Whole-record replacement checks the new record. Copying
keeps the type, and passing by value to a looser shape forgets the contract safely: the value
is an immutable share. No new route into refined storage opens.

**Compatibility.** Every literal that compiles today still compiles, with the same type or a
tighter one. Three things can fail that compiled before: a later store, an `@` pass to a
plainer shape, or reassigning a whole inferred record with plainer values. Program 06 shows
the typical case: a mutable state record seeded from checked options. There are no users yet,
and the test suite will find any cases in the tree.

**Inference stability.** A field's type depends only on the declared types of the values
written into it. Adding or removing a guard, a literal, or arithmetic in the caller never
changes it. Changing a declared type does, as it would in TypeScript, Swift or Rust.

**Messages.** A failed store, or an `@` pass into a field whose refinement was inferred, adds
a note naming the value the field took its type from, and offers both fixes:

```
error: cannot prove refinement `state.lives - 1 >=? 1`: missing lower bound
    state.lives -= 1
note: state.lives is a Lives (1 to 9): the record took the type of `args.lives` (line 21)
help: to let it hold any int64, write `lives = args.lives as int64` there, or declare the record's type
```

Today's message ends at "the contract is declared here", which is the right note for a
declared field but not enough for an inferred one. Messages should also print the alias
(`Count`). Some already print `int64<refinement>` (see "Found outside this item").

**Compile cost.** No new analysis. The checker skips one erasure, and a field with several
sources compares a few constant bounds per arm. There will be more distinct anonymous record
types (`[cells:Count]` beside `[cells:int64]`), so a generic used on both is specialized
twice. Lowering already erases refinements (`representation_type`), so instances could share
code if the panel shows a cost. Obligations go down: re-guards disappear, and a field-typed
operand discharges from its type without a fact graph. Expect neutral on the flagship panel,
and measure it when implementing (rule 4).

### A2. Fields keep their value's refinement as precisely as known

`[n = 5]` would be `n:int64<(=? 5)>` and `if x >? 0 [n = x]` gives `n:int64<(>? 0)>`: facts
become field types. Rejected. Every counter seeded from a literal breaks (`[score = 0]`, then
`score += 1`). A record's public type changes whenever a guard upstream changes, which
contradicts "inferred facts stay private" and makes inference unstable. Messages would cite
contracts no one wrote. It is graded below for comparison only.

### B. Keep plain fields and fix the documents

LANGUAGE.md, D48 and the design note would say the parsed record's fields are their base
types. argparse would then need another way to give a typed record:

- **The program re-checks** (ladder 151 today). Safe, since every gap is a compile error, but it
  duplicates what the help text already promises, and it can't pass the record on with its
  guarantees.
- **The program annotates** `let args:[cells:Count cars:Count …] = argparse.parse(…)`. It
  repeats the spec field by field, and `Parsed<Spec>` would still be plain.
- **The library declares its result** as a type computed from the spec. That is a mapped type,
  which the design note rules out on purpose ("no object comprehension as a feature, no
  mapped types").
- **An annotation inside the literal** (`[cells:Count = c]`, or `$field(f.name):T = …` in the
  unrolled loop) is new syntax, and today's parser rejects it ("`:` gives a type here").

Outside argparse, B means every function that returns a small record built from checked
values has to write its result type or declare a named type. `[a = xs]` keeps `array<Count>`
while `[a = c]` loses `Count`, and B leaves that inconsistency in place.

### C1. Field facts cross function boundaries, types stay plain

Extend the result summaries that unannotated scalar functions already publish (`ret` above) to
the fields of an inferred record. This changes no types, so mutation stays free. But facts only
reach direct callers. A helper's parameter (`a:argparse.Parsed<Args>`), a record stored in an
array or dictionary, and anything across a module's public interface lose them, and the last
is exactly where `argparse.parse` sits ("inferred facts stay private"). The grades below
assume, generously, that summaries do cross into the program from the library.

### C2. A, except that a field the function itself writes stays plain

This takes the friction out of program 06: `state.lives -= 1` would make `lives` an `int64`.
The rule is syntactic: any write to the field in the function, including an `@` pass of the
record. Rejected for now. A record's type, including the type a function returns, would then
depend on writes anywhere in the function body. A write that keeps the value in range (program
13's `cfg.jobs = 1`) would still drop the contract, and the error would surface at a distant
caller. A contract checked at the boundary would disappear without anything in the source
saying so, where A makes dropping it visible (`as int64`). Today only empty containers settle
from later writes. C2 isn't a pure relaxation either: 13 compiles under A and fails under C2.
A narrower version, where only a write the checker can't prove in range makes the field plain,
would let facts decide types, and the design keeps those apart.

### Not proposed

- **Array literal elements** (`[w h]` from two `Positive`s stays `array<int64>`). Arrays seeded
  from one checked value and then grown (`let frontier = [root]`, `frontier.push(next)`) are
  common, and a refined element type would turn every push into an obligation. Writing the
  element type is one name (`:>array<Positive>`). Records are different: an anonymous record's
  type is long, and argparse's can't be written at all.
- **Inferring a type argument from a refined value** (`Box(c)` giving `Box<Count>`).
  refinement.md says by-value generics forget (`T = B`). argparse doesn't need it, because its
  `T` comes from the descriptor's written type argument.

## The two-question test

1. **Is the common path easy, ergonomic and fast?** Yes under A. The argparse record, config
   bundles, geometry results and parsed-entry lists keep what was checked. Helpers taking
   `argparse.Parsed<Args>` or a written shape get it with no guard. Nothing runs at run time,
   and the re-guards and their obligations go away.
2. **When it doesn't fit, is adjusting straightforward?** Yes. A field that should hold any
   value of its base (a counter seeded from a checked option) takes `as int64` at the field, or
   the record gets a declared type. The error names the field, where its type came from, and
   both fixes.

Both pass, and the design already states the outcome (the 2026-09-02 note, refinement.md's two
rules above), with no new syntax. **The coordinator can take A without asking David.** It
makes D48's text true as written, so no D48 question changes. LANGUAGE.md, records section,
gains one sentence when A lands:

> An inferred field takes its value's declared type, refinement included: with `c:Count`,
> `[cells = c]` is `[cells:Count]`. A literal, arithmetic or a guarded value gives the plain
> type; `c as int64` or an annotation keeps a field plain.

Ladder 151 then drops its re-guard comment and line, and passes `args` to its helpers.

## Dogfood

Thirteen programs are in [programs-r1/](programs-r1/). Each is written as option A would have
it, with margin notes where B, C1 or C2 differ. Each is graded 1–5 on obvious, discoverable,
concise, safe by default and complete, against Python (argparse, dataclasses), Go (flag,
structs), Rust (clap, newtypes), TypeScript (branded types: `{cells: c}` infers
`{cells: Count}`, as A does) and Swift (ArgumentParser, tuples keep their element types).

Checked against today's compiler: 01, 04, 05, 09, 10 and 12 were checked with A's types
written as annotations (and 01 with `Parsed` written out), and pass cleanly. Under today's
plain fields, 04, 05, 09, 10 and 12 as written fail at the line their `(b)` note marks. The
store error A gives in program 06 was produced by today's compiler from a declared field.
The rest use library calls that don't exist yet (images, HTTP, `Parsed`).

| Program | What it exercises | A | A2 | B | C1 | C2 |
|---|---|---|---|---|---|---|
| 01 ring_traffic | ladder 151 with helpers taking the record | 5 5 5 5 5 | 5 5 5 5 5 | 3 3 2 5 3 | 3 3 3 5 3 | 5 5 5 5 5 |
| 02 thumbnail | refined args passed to a library's refined parameters | 5 5 5 5 5 | 5 5 5 5 5 | 3 3 3 5 3 | 3 3 3 5 3 | 5 5 5 5 5 |
| 03 server_config | checked env settings returned as a bundle | 5 5 4 5 5 | 5 5 4 5 5 | 4 4 3 5 5 | 5 5 4 5 4 | 5 5 4 5 5 |
| 04 geometry | `size(w h)` of positives, division by fields | 5 5 5 5 5 | 5 5 5 5 5 | 4 3 4 5 5 | 5 5 5 5 4 | 5 5 5 5 5 |
| 05 paginate | a window record, a computed field beside refined ones | 5 5 4 5 5 | 5 5 4 5 5 | 4 3 3 5 5 | 5 5 4 5 4 | 5 5 4 5 5 |
| 06 lives_game | mutable state seeded from checked options | 4 5 4 5 5 | 2 3 3 5 4 | 4 3 4 5 4 | 5 5 5 5 5 | 5 5 5 5 5 |
| 07 histogram | bucket count as a length and a divisor in helpers | 5 5 5 5 5 | 5 5 5 5 5 | 3 3 3 5 3 | 4 4 4 5 3 | 5 5 5 5 5 |
| 08 retry_policy | refined and computed fields, a generic consumer | 5 5 4 5 4 | 5 5 4 5 5 | 3 3 3 5 4 | 5 5 4 5 4 | 5 5 4 5 4 |
| 09 grid | grid dimensions through a loop-carried `g = step(g)` | 5 5 4 5 4 | 5 5 4 5 4 | 3 3 3 5 4 | 4 4 4 5 4 | 5 5 4 5 4 |
| 10 progress | a style record from an annotated local | 5 5 4 5 5 | 5 5 4 5 5 | 4 3 3 5 5 | 5 5 4 5 4 | 5 5 4 5 5 |
| 11 jobs_arms | a field with several sources (`if`, `??`, literals) | 4 4 5 5 5 | 4 4 5 5 5 | 3 3 3 5 4 | 3 3 3 5 3 | 4 4 5 5 5 |
| 12 log_levels | an array of inferred records indexing by a field | 5 5 5 5 5 | 5 5 5 5 5 | 4 3 4 5 5 | 3 3 4 5 3 | 5 5 5 5 5 |
| 13 build_settings | a record adjusted in range, then returned | 5 5 5 5 5 | 5 5 5 5 5 | 3 3 3 5 4 | 3 3 3 5 3 | 3 3 4 5 4 |

Averages: **A 4.83**, A2 4.75, B 3.77, C1 4.12, C2 4.77. A gets all 5s on six programs, B on
none.

Where the grades fall:

- **B (3.77).** Every argparse program re-checks ranges its help already prints (01, 02, 07, 11,
  13). The re-check sits where the plain type surfaces, often far from the spec, and only
  covers the function it is in: ladder 151 has to pass three guarded numbers instead of the
  record. Discoverable is 3 almost everywhere, because the error says the field may be 0 and not
  that the literal dropped the type. Outside argparse, each function returning a small record
  writes its shape twice (03, 04, 05, 09, 10, 12). Safe stays 5: nothing unsafe runs, it just
  fails to compile.
- **C1 (4.12).** Fine where the record goes straight from producer to consumer (03, 04, 05, 08,
  10). It fails at the first helper parameter (01, 02, 11, 13) and in collections (12), which
  are the argparse cases it was meant to fix.
- **A2 (4.75).** Equal to A except where it is worse (06: `score = 0` becomes the type `0`) or
  better (08: the computed `cap` would carry its range). Its instability doesn't show in
  single programs, but it is the reason to reject it.
- **C2 (4.77).** Better than A on 06 only, and worse on 13, where a write that keeps the value
  in range drops the contract and the error surfaces in the caller.

What stays under 5 under A:

- **06 (obvious 4, concise 4).** `lives = args.lives as int64` is needed for a field meant to
  count down to 0. TypeScript's branded types and Swift's wrapper types ask for the same step.
  Python, Go and Rust (with a plain integer field) don't, but none of them checked the range in
  the first place.
- **11 (obvious 4, discoverable 4).** The several-sources rule is one more rule. Its failure
  is soft (the field is plain, and the error at the use says why), never an error at the
  literal.
- **Concise 4 on 03, 05, 08, 09, 10.** A helper that takes an anonymous record spells its shape
  in the parameter. This is inherent to anonymous records and the same under every option.
  Declaring a type fixes it, as in Go, Rust and Swift.
- **Complete 4 on 08 and 09.** A computed field (`cap = min(60000 base * 32)`) and a length
  relation (`cells.length =? w * h`) aren't carried by A. Only A2, which is rejected, carries
  the first, and a declared result carries it too. No option carries the second: it needs
  dependent length contracts, which are deferred.

## Found outside this item

- **Joins of differently refined nested values take the first arm's type.**
  `if q xs else ys` with `xs:array<Count>` and `ys:array<Small>` is an error, "expected
  array<Count>, found array<Small>". Neither admits the other, so it should give the base
  `array<int64>`. Where one admits the other it already works (`array<Count>` beside
  `array<int64>`). A's rule 4 is the same rule for fields.
- **Messages print `int64<refinement>`** instead of the alias. For example: "argument 'c' expects
  array<int64<refinement>>, found array<int64>". A makes refined field types more common in
  messages, so this matters more.
- **`argparse.Parsed` doesn't exist yet** (D48 Q5). Programs 01, 02, 07, 11 and 13 use it.
- When A is implemented, confirm that `take(…) or_throw<UsageError>` leaves `T` itself in the
  unrolled literal (the instantiated `Count`), not its base. That is the one link between A's
  rule and argparse's documented record.
