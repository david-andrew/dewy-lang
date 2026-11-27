# Newcomer friction, round 1: five snags that follow from decided design

A newcomer-friction pass found five places where an ordinary first attempt is a compile
error. None is a bug: each follows from a decided rule. This round checks what David already
said, applies the two-question test, tests the spellings cold, and dogfoods 13 programs. The
result is open decision D49 (three questions); one snag is taken without asking and one is
already answered.

| # | Snag | Verdict |
|---|---|---|
| 1 | `end` can't name a field | D49 Q1 (a): allow `end` and `new` as field names |
| 2 | `=> x += 1` needs braces | D49 Q2 (a): a `=>` body may be one assignment |
| 3 | `loop x in a ?? b` needs parentheses | answered 2026-10-23; dropped |
| 4 | `(r:int) =>` rejected for `array<int64>` | taken: a callback accepts what a call accepts |
| 5 | literal arms need `<"room">` | D49 Q3 (b): bare literal arms, and a shadowing bare name becomes an error |

## What David already said

- **Tensors decision (2026-10-21, `tensors.md` "`end` and `new`"):** "`end` and `new` are
  reserved: `end` is the last index inside an index; `new` inserts a singleton axis". The
  decision names their meaning inside brackets. LANGUAGE.md extends the reservation to "a
  variable, function, parameter, field, method, loop or pattern binding, or import alias". The
  field part is the one this round questions, so Q1 is type (a).
- **The library already uses the field.** The regex `Match` (`lib/std/regex.jo`, documented in
  LANGUAGE.md) has `start` and `end`, so `m.end` is ordinary Dewy that no user record can
  offer. The archived reference's `Span` example used `start`/`stop`, which avoided the clash
  without discussing it.
- **Precedence (decisions.md, 2026-10-23):** "Operator precedence starts from the archived
  Python implementation's table, adjusted only where it would confuse; deviations are reported
  to David." That table puts assignment below `=>`. The archived reference writes
  `increment = () => (value += 1)` and `grow = (by:int64) => { stop += by }`. Q2 is a deviation,
  so it goes to David as type (a).
- **Loops (decisions.md, 2026-10-23):** "No local precedence exception for
  `loop c in s as array<uint8>` … write `loop c in (s as array<uint8>)`." Snag 3's
  recommendation (let a loop header's source extend down to `and`/`or`) is that same kind of
  loop-local exception, for `??` instead of `as`. It is answered, and dropped.
- **`match` (match.md, decided 2026-08-28):** an arm is a signature; a literal arm is `<42>` or
  `answer:42`; a bare name is the catch-all and binds. David's earlier notes
  (`resources/discussion_points.md`, "Match case syntax") sketched `5 => 'five'` and
  `[a b 3] => …` as literal arms, and added: "If you want to match against values stored in
  variables, you might do something with `=?`." Bare literal arms would be new syntax, so Q3 is
  type (b). It returns to his first sketch, and bare names keep the decided meaning.
- **Callables (LANGUAGE.md, effects.md):** "Parameters are contravariant and results
  covariant." A direct call already converts an `int64` argument to an `int` parameter
  (`f = (x:int) => …; f(y)` for `y:int64` runs today). Snag 4 is the same rule applied to a
  callback, so it is taken without asking (below).

## Running today

Each snag already has a precise diagnostic except the lambda case of snag 2:

| Input | Today |
|---|---|
| `Span:type = [start:int end:int]` | "'end' is reserved, not a name: inside brackets it is the last index … (use `end_`)" |
| `<'+'> => n += 1` | "an arm whose body assigns needs braces, `pattern => {target = value}` …" |
| `let add = (v:int) => total += v` | "expected an expression, found '+='" (and in an argument, "could not parse the statement") |
| `grow = (by:int) => stop += by` as a method row | **accepted, and runs** |
| `loop x in cached ?? [1 2]` | "`??` binds more loosely than `in` … parenthesize the source, as in `loop x in (a ?? b)`" |
| `xs.sorted(key=(r:int) => -r)` on `array<int64>` | "parameter type int does not match expected int64" |
| `laps.map(@lap_text)` with `lap_text = (ms:int64?) => …` | accepted: `T` to `T?` already works |
| `"room" => 1` | "a value in a pattern goes in angle brackets: `<"room"> => ...`" |
| `from_json<Event>` of `{"end":10}` into `[… end_:int]` | "missing field 'end_', which has no default" |

The last row is why snag 1 fails the second test: a JSON object with an `"end"` key (calendar
events, LSP ranges, most span-carrying APIs) cannot be read into a typed record at all, because
`from_json` maps field names to keys and has no renaming. The workaround is the dynamic `Json`
tree by hand (programs 05 and 11 show what that costs: 14 and 23 lines against 1).

## Q1. `end` and `new` as field names

**Two-question test.** Fails both. The common path (a span, an event, a range, a diff) reaches
for `start`/`end` and `old`/`new` first, as Python, Rust, Go, TypeScript and Swift all allow.
Adjusting is a rename when the program owns the names, but it is impossible when the names come
from outside: JSON keys, a protocol, or the library's own `Match.end`.

**Proposal.** `end` and `new` may name a data field. They keep every other reservation:
variable, function, parameter, method, loop or pattern binding, import alias.

| Where | Allowed |
|---|---|
| `Span:type = [start:int end:int]`, `s.end`, `s.end = 9` | yes |
| `Span[start=2 end=5]`, `Span(end=5)`, `[s... end=9]` | yes: the field's name, not a binding |
| `from_json<Span>` / `to_json` with key `"end"` | yes |
| `[start end as stop] = s`, an arm `[end:0] => …` | yes: the field is named and nothing binds `end` |
| `[start end] = s` | error: it would bind `end`; the message suggests `end as stop` |
| `f = (end:int) => …`, `let new = …`, `loop end in …` | error, as today |
| a method named `end` or `new` | error, as today |

Inside the type's own methods, fields are reached bare (there is no `self`):

- outside brackets, a bare `end` is the field: `width = () => end - start`;
- inside brackets, `end` is the last index everywhere else, so `text[start..end)` in such a
  method has two readings. It is a compile error naming both, with the fix
  `let stop = end` before the index (or `xs.length - 1` for the last index).

The error, not either silent reading, is the point: one cold reader (c) flagged exactly that
line as a trap, and the other two read `end` as the field, while outside such a method `end` in
brackets is the last index. Making the field win silently changes `xs[end]` inside methods;
making the index win silently slices to the end of the text.

**Considered.** Allowing parameters too (`slice(start=1 end=4)`, Python's `str.find(sub,
start, end)`): the body would then hold a binding `end` beside `xs[end]`, everywhere, not just
in one type's methods. Not proposed. A field-to-key rename for `from_json` (`$json_key`) solves
the JSON half for any key (including `"content-type"`), but leaves `Match.end` unavailable to
user types and the common span record awkward; it's worth having for keys that aren't names at
all, as a separate item.

**Reversible:** yes; nothing that compiles today changes meaning.

## Q2. A `=>` body that is one assignment

**Two-question test.** The match-arm form fails the first test for state machines, counters and
parsers: `"INFO" => infos += 1` is the line every language writes (Rust `"INFO" => infos += 1,`,
Swift `case "INFO": infos += 1`, Python `case "INFO": infos += 1`). Adjusting is easy once the
diagnostic says "braces". The inconsistency matters more: a method row already accepts
`grow = (by:int) => stop += by`, but a `let` or argument lambda doesn't, and its error is the
generic "could not parse". Because it's a precedence deviation, it goes to David.

**Proposal.** When the target of an assignment or compound assignment is a `=>` function, the
assignment becomes that function's body: `p => t op= v` reads `p => (t op= v)`. A function is
never an assignable place, so nothing that compiles today changes meaning. It covers match
arms, lambdas and method rows alike:

```dewy
match level { "INFO" => infos += 1  "WARN" => warns += 1  _ => skipped += 1 }
each_target(cfg (s h $capture @targets) => targets += 1)
grow = (by:int) => end += by
```

- The body gives nothing, as `{ t op= v }` does today.
- Two statements still take braces: `"coin" => { credit += c  state = 'paying' }`.
- In an argument list, `v => last = v` is not a named argument (its left side isn't a name), so
  it is the lambda `v => (last = v)`.
- `f = x => y = 3` reads `f = (x => (y = 3))`.
- A lambda that changes a captured local still needs `$capture @name`. That decided safety rule
  is most of what a newcomer meets in the lambda case. Rust's `move`/`&mut` is the analogue, so
  the grades don't count it.

**Considered.** Moving assignment above `=>` in the table breaks `f = x => x + 1`. Making `=>`'s
right side extend down to assignment would also swallow `|>` (`xs |> x => x + 1 |> f`), which
the table deliberately keeps outside. The tree rotation touches only the case that is an error
today.

**Reversible:** yes.

## Snag 3 (dropped): `loop x in a ?? b`

Answered by David's 2026-10-23 ruling, quoted above. The diagnostic gives the fix in one step.
I hit it myself writing program 05 and fixed it from the message. For the record, all three cold
readers read `loop x in cached ?? []` as iterating `cached ?? []`, with confidence 4, 3 and 5
(reader b doubted the binding). It is the confusing case David's rule allows adjusting, but the
adjustment he chose for the same shape was none. Not re-raised.

## Snag 4 (taken): a callback accepts what a call accepts

Rule: a function value fits a function type when each expected parameter type converts to the
value's parameter type implicitly, as a call's argument would, and the value's result converts
to the expected result. So `(r:int) => -r` fits `(int64):>K`, and `(ms:int64?) => …` fits
`(int64):>…` as it does today. The compiler converts on entry (a widening `int64` to `int` is
free where word storage is proven) and on exit. It's the documented "parameters are
contravariant and results covariant", applied with the call's conversions, so it passes both
tests and needs no question. Until it lands, the diagnostic could say "write `(r:int64)` or
leave the parameter unannotated". Compiler work, out of this docs-only round.

## Q3. Bare literal arms

**Two-question test.** The common path fails: every language matches a string as
`"room" =>` / `case "room":`, and none brackets it. All three cold readers read `"room" =>`
correctly (confidence 4, 4 and 5). All three were unsure that `<"room">` is even legal
(confidence 2, 2 and 2). Adjusting is easy (the diagnostic names `<"room">`), but it is new
syntax, so it goes to David.

**Proposal.** A literal, or a `|` of literals, on the left of an arm is shorthand for the
bracketed form: strings, integers (negatives included), `true`, `false` and `none`.

| Shorthand | Same as |
|---|---|
| `"room" => …` | `<"room"> => …` |
| `0 => "zero"  1 \| 2 => "few"` | `<0>`, `<1 \| 2>` (the left of an arm is a type, so `\|` is a union, never bitwise) |
| `'idle' => …` over `'idle' \| 'paying'` | `<'idle'>` |
| `none => 0` | `<none>` |
| `("users" id "posts") => …` | `(<"users"> id <"posts">)` inside a sequence pattern |

- `<T>`, `name:T` and `name:"quit"` don't change. Coverage and unreachability are the
  bracketed form's.
- **With it, a bare name that shadows a value becomes an error** (today a warning). With
  `"room" =>` comparing, `ROOM =>` looks as if it compares too: two of the three readers read
  it as comparing. Rust and Swift do compare a constant there, and Python binds. Keep
  match.md's meaning, binding, but refuse the misleading case: "the bare name `ROOM` matches
  every value and would hide the value `ROOM`; `_` is the catch-all, `room:T` binds with a
  type". A fresh name still warns, as now. (Comparing with a named constant has no arm form
  today: string-valued guards are "not in the first cut" in match.md. That's a separate gap.)
- `"room" => 1` isn't a valid lambda (a parameter list can't be a literal), so nothing that
  compiles today changes.

**Considered.** Bare names comparing with constants in scope (Rust's rule): it changes the
decided catch-all meaning and makes an arm's meaning depend on what is in scope. Not proposed.

**Reversible:** yes.

## Cold read (names tested)

Twelve snippets, shuffled, to three fresh readers with no context beyond a short Dewy primer:
a Sonnet, b Haiku, c Fable. Kit: `~/dev/tmp/naming-1107/r34/`.

| Snippet | a | b | c | Verdict |
|---|---|---|---|---|
| `match cmd { "room" => look() … _ => … }` | right, 4 | right, 4 | right, 5 | pass |
| `match cmd { <"room"> => look() … }` | right, 2, "not in the stated syntax" | right, 2 | right, 2, "redundant" | readable, not guessable |
| `match n { 0 => … 1 \| 2 => … other => … }` | right, 4 | right, 4 | right, 4 (doubt: bitwise?) | pass |
| `Span:type = [start:int end:int]`, `s.end` | field, 3 | field, 3 | field, 4 | pass |
| `Change:type = [old new]`, `c.new` | field, 3 | field, 3 | field, 4 | pass |
| `xs[end]`, `xs[1..end]` | last element, 2 | last element, 2 | last element, 3 | (control) |
| `text[start..end)` in a method of a type with field `end` | field, 3 | field, 2 | field, but "collides with the index word: expect an error", 2 | supports Q1's error |
| `ROOM => look()  "quit" => stop()` | binds, 2 | compares, 3 | compares (flags the risk), 2 | trap: supports Q3's error |
| `(v) => total += v` and `"up" => y -= 1` | assigns, 3/3 | assigns, 3/3 | assigns, 3/4 | pass |
| `loop x in cached ?? []` | `cached ?? []`, 4 | same, 3 | same, 5 | (dropped item) |
| `xs.sorted(key=(r:int) => -r)` on `int64` | "might mismatch", 3 | "leaning no", 3 | "leaning no", 3 | readers expect friction |

Confidence 3 on the field rows comes from "`end` may be reserved", not from a misreading.

## Dogfood (dogfooded)

Thirteen programs in `programs-r1/`, written in the proposed form. Each one's header gives the
lines that differ today. Every program's today-form ran on the current compiler before it was
edited, with `$runtime_checks` where bounds proofs weren't the topic. I graded them myself, 1 to 5, on obvious, discoverable, concise, safe by
default and complete, against Python, Go, Rust, TypeScript and Swift. The lowest criterion sets
the grade.

| Program | Exercises | Today | After | What decides it |
|---|---|---|---|---|
| 01 tokenizer | span field, literal arms, method on a span | 3 | 4 | the method's `text[start..end)` needs `let stop = end` |
| 02 adventure | string commands, counters | 4 | 5 | `<"look"> => { looks += 1 }` |
| 03 router | literals in sequence patterns | 3 | 5 | `(<"users"> id <"posts">)` |
| 04 leaderboard | `int64` scores sorted by key | 4 | 5 | `(s:int)` rejected |
| 05 calendar | JSON events with `"end"` | 2 | 5 | `from_json` can't read the export; dynamic tree by hand |
| 06 deploy plan | loops over optional lists, counting lambda | 4 | 4 | braces; the decided `(a ?? b)` parentheses remain |
| 07 settings diff | `[old new]` change records, `none` in a sequence | 4 | 5 | `before`/`after` fields, `<none>` |
| 08 RPN calculator | literal arms | 4 | 5 | brackets on every arm |
| 09 vending machine | literal-union states, arms over strings | 4 | 5 | brackets on every arm |
| 10 highlight | regex `Match.end` beside a user span | 3 | 5 | `Mark.stop` beside `m.end` in one function |
| 11 LSP diagnostics | protocol ranges with `"end"` | 2 | 5 | 23 lines of dynamic `Json` to read one reply |
| 12 INI parser | error spans, literal arms | 4 | 5 | `stop`, brackets |
| 13 log summary | four counter arms, `int64` keys | 3 | 5 | braces on four one-assignment arms, `(s:int64)` |

Mean: 3.38 today, 4.85 after. The two 4s are inherent:

- **01:** a type with an `end` field can't use the bare last-index `end` inside its own
  methods' brackets. Without `self`, a bare field and a reserved word share one spelling there.
  The error and a one-line hoist are the honest cost. Julia, whose `end` Dewy follows, forbids
  the field outright.
- **06:** `loop h in (s.hosts ?? defaults)` keeps the parentheses David decided on 2026-10-23.
  Python (`for h in hosts or []`) and Swift (`for h in hosts ?? []`) don't need them. Not
  re-raised.

## Found along the way (out of scope)

- A one-element sequence pattern, `("users")` or `(<"users">)`, doesn't parse ("could not parse
  the statement"), so program 03 matches whole paths as strings instead.
- A lambda whose body assigns gets the generic parse error in `let` and argument position, while
  a match arm gets the precise one. Worth fixing whatever Q2's answer is.
- Method rows already accept `=> stop += by` (program-tested). If Q2 is declined, that
  acceptance becomes the inconsistency to fix the other way.
- `from_json` has no field-to-key rename, so keys that aren't Dewy names (`"content-type"`,
  `"@id"`) can't be read into a typed record either.
- A tuple sort key needs its result type written (`key=(p):>[int64 int64] => [...]`); the
  diagnostic says so.
- Comparing a match scrutinee with a named constant has no arm form (string-valued guards are
  not in the first cut).
