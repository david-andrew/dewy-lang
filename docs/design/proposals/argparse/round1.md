# Argument parsing, round 1: the provisional choices and what users will miss

The library landed on 2026-11-27 (`lib/argparse.dewy`, LANGUAGE.md "Command-line arguments",
[argparse_and_reflection.md](../../argparse_and_reflection.md)) with five choices made
provisionally. This round checks them against what David already wrote, runs the library as
landed, tests the new names cold, and dogfoods twelve programs. The result is open decision D48.

## What David already said

- **`resources/discussion_points.md`, "Command-line arguments".** Arguments are `name=value`
  and bare positionals, values follow Dewy syntax, and the command line is untrusted input:
  reading it must be side-effect free, with no evaluation unless the user opts in loudly. The
  text readers keep that: `T(text)` reads, never evaluates, and an environment value (Q3) goes
  through the same reader. His idea of whole Dewy literals as values (`arg2=r\''[1 2 3]'`) is
  discussed under "Not proposed".
- **decisions.md, 2026-11-07:** the renames "`int(text)` and `float64(text)` for `to_int` and
  `to_float` wait for" the naming-style study (D38). Item 1 takes `int(text)` early, so it is a
  type (a) question (Q1).
- **decisions.md, 2026-10-23:** `to_int` returns a specific failure saying why (`NotAnInteger`,
  `TooManyDigits`), and `??<Missing|ParseError>` was the example of defaulting chosen failures.
- **D11 (open):** convention 7 reads every type through `T(text)` giving `T | ValidationError`;
  Q3 asks how a user type declares its reader (`__read__`), Q2 asks for `check=`, and Q5 already
  asks for `ValidationError` as the one name, replacing `ParseError`. Item 2 is therefore D11
  Q5, not a new question, and user types in a spec read through whatever D11 Q3 decides.
- **The design note (decided 2026-09-02):** `name=value`, `-t=2` and never `-t 2`, no
  `--name value` (it makes `--flag positional` ambiguous), `parse` and `try`, help with each
  type spelled in Dewy, and "help= can give way to a field doc".

## The five provisional choices

| # | Choice | Verdict |
|---|---|---|
| 1 | Builtin types read text (`int64(text)` and the rest) | Q1: keep, and fold `to_int`/`to_float` into them |
| 2 | `ValidationError`, not `ParseError` | already D11 Q5, same recommendation |
| 3 | `T.spelling` | Q7: rename to `T.type_text` (`spelling` failed the cold read) |
| 4 | Anonymous specs keep name order | taken: an anonymous spec with two or more positionals becomes a compile error |
| 5 | `--ignore-case` names `ignore_case`; `--name=value` accepted; a valued argument given twice is an error; `-h` reserved; an array positional takes the remaining words | taken: each passes both tests |

Item 4 is a safety bug as landed. Running

```dewy
let spec = [source = argparse.Positional<string>() dest = argparse.Positional<string>()]
argparse.try(spec ["cp" "s" "d"])        # source=d dest=s
```

reads `cp s d` backwards, silently, because an anonymous record's fields are in name order.
Making record literals keep their written order would change type identity
(`[a:int b:int]` and `[b:int a:int]` are one type), so the library rejects the anonymous case
at compile time instead: "declare the spec as a type, `Args:type = [...]`, so its positionals
keep their order".

## Found by running the library as landed

Programs 01 and 07 run unchanged on the landed library apart from the taken items below; the
others need the proposals. Running them found:

- `-i` never existed in `find`: `ignore_case` and `invert` both start with `i`, and `invert`'s
  own `short='v'` still blocked the letter. A flag with an explicit short no longer competes.
- `find TODO a.txt --max-count 1` says "unknown flag --max-count", although `max_count` exists.
  It now says "max_count takes a value: max_count=1 or --max-count=1".
- `max_count=0` says "must be int64<value => 1 <=? value>", and help prints that type in its
  column, overflowing it. A command's user is not necessarily a Dewy programmer: a refined
  integer's message and help say its range in words ("must be 1 or more", "1 to 16"), and long
  types wrap onto their own line. Choices still list as `'tokens' | 'ast'`.
- Unknown names get no suggestion (`--dry-rn`). They now suggest the nearest field.
- Combined shorts (`-in`) are refused. Flags now combine; a valued short still takes `=`.
- The documented `match argparse.try(...) { e:argparse.UsageError => …  args => … }` warns
  that the bare name `args` matches everything, and the parsed record has no type name to
  write instead (Q5).
- A field whose type has no text reader fails inside the library's generic code
  ("Duration needs its field '_lo', which has no default"). Convention 7 promises
  `Duration(text)`; until then the error should name the field and say the type has no reader.
  Refined floats aren't supported yet ("unsupported refinement term"). Both are implementation
  gaps, outside this design.

## Dogfood

Twelve programs in [programs-r1/](programs-r1/), each a realistic tool, graded 1–5 on obvious,
discoverable, concise, safe by default and complete, against Python argparse and click, Go
flag and cobra, Rust clap, TypeScript (commander, yargs) and Swift ArgumentParser.
"Landed" is the program as it must be written today (subcommands faked with a mode
positional, environment and cross-field checks by hand); "proposed" is the program as written,
with D48's answers.

| Program | What it exercises | Landed O D C S Cm | Proposed |
|---|---|---|---|
| 01 find | positional + array, flags, shorts, optional refined | 4 4 5 5 4 | 5 5 5 5 5 |
| 02 convert | three positionals, literal-union units, a cross-field rule | 5 5 4 4 4 | 5 5 5 5 5 |
| 03 migrate-config | `out=` vs `--in-place`, `--backup` needs `--in-place`, `-n` | 5 5 4 4 3 | 5 5 5 5 5 |
| 04 backup | four modes, shared options, env store | 3 3 3 3 2 | 5 5 4 5 5 |
| 05 bench | env default, `Duration`, list filter | 5 5 4 4 3 | 5 5 5 5 5 |
| 06 serve | `Port` from `PORT`, `--no-cache`, `--version`, value check | 4 4 4 4 3 | 5 5 5 5 5 |
| 07 rename | `SRC... DEST`-style middle array, `--`, `-n` | 5 5 5 5 5 | 5 5 5 5 5 |
| 08 logq | literal-union level, `Duration?`, list of choices | 5 4 4 5 4 | 5 5 5 5 5 |
| 09 fetch | args passed to a helper, `--quiet` vs `--verbose` | 5 5 4 4 4 | 5 5 5 5 5 |
| 10 csvcut | `columns=1,3`, `--no-header`, optional positional | 4 4 4 5 4 | 5 5 5 5 5 |
| 11 genpass | default-true flags, optional refined | 4 4 5 5 4 | 5 5 5 5 5 |
| 12 todo | three commands, env file, positional refined id | 3 3 3 3 2 | 5 5 5 5 5 |

Averages: landed 4.08, proposed 4.98.

Where the landed grades fall:

- **Subcommands (04, 12).** Faking modes with `mode = Positional<'create'|'list'|…>` and one
  spec accepts every option in every mode: `backup list --dry-run` is silently ignored (safe
  3), help mixes all modes (discoverable 3), and each handler re-checks what applies.
  Python, Go cobra, clap, click and Swift all have subcommands. Q2.
- **Cross-field rules (02, 03, 06, 09).** Exclusive or dependent options are checked by hand
  after parsing, and the usage then has to be printed by hand too. Q4.
- **Environment fallbacks (04, 05, 06, 12).** Reading `env("PORT")` by hand invites
  `int64(env("PORT") ?? "") ?? 8000`, which silently ignores a bad value. clap, click, cobra
  (through viper) have it. Q3.
- **Passing the parsed record on (02, 03, 04, 09, 12).** Its type has no name, so a helper
  either repeats every field's type or is generic. Q5.
- **Lists in one word (05, 08, 10).** `columns=1 columns=3` where `cut -f1,3` is expected. Q6.
- **Default-true flags (06, 10, 11).** `no_symbols = Flag()` and `if not args.no_symbols`; now
  `symbols = Flag(default=true)` with `--no-symbols` (taken).
- **01** loses on the bugs found above; **07** was already all 5.

What stays under 5: **04 concise 4**. Four handlers each write `args:argparse.Parsed<XArgs>`,
where clap and Swift derive the parsed type from the declaration itself, so one name serves
both. That is inherent to specs as descriptor values (decided 2026-09-02): the spec's fields
hold descriptors, not values, so it can't also be the parsed type. The alternative, plain typed
fields carrying metatags (`port:Port = 8000 $named(env="PORT")`), would need field metatags
read by reflection, which is new syntax and redoes the decided design. It is noted here, not
proposed. An alias (`Create:type = argparse.Parsed<CreateArgs>`) brings it to one name per
command.

## Proposals (the questions in D48)

**Q1 (a). Builtin types read text.** `int64(text)`, `uint8(text)`, `int(text)`,
`float64(text)`, `bool(text)` (only `true`/`false`), refined integers (read, then tested) and
literal unions give `T | ValidationError`, through a type parameter too. `to_int` and
`to_float` go in the same change: no second spelling. `int(text max_digits=…)` keeps the limit,
and the two failures David chose to keep, `NotAnInteger` and `TooManyDigits`, become kinds of
`ValidationError`, so `??<TooManyDigits>` still works and a generic `T | ValidationError` covers
both. This takes ahead of D38 the rename held for it. That rename is a change of word, not of
separator, so D38's answer can't change it.
*Considered:* the design note's `int64 &= (text:string):>int64 | ParseError`. It would let a
library add readers to builtins, but `&=` on a builtin type name needs new parser support, and
every builtin would be declared in the prelude anyway. A user type's reader is D11 Q3.

**Q2 (b). Subcommands: `argparse.dispatch` over a table of `argparse.Subcommand`.**

```dewy
main = (argv:array<string>) => argparse.dispatch(argv about="a to-do list" [
    add = argparse.Subcommand(AddArgs @add help="add an item")
    list = argparse.Subcommand(ListArgs @list_items help="show the items")
])
```

The first word picks the field by name. The rest of the command line is read with that
field's spec and handed to its handler, and `dispatch` returns the handler's result. `--help`
before the word lists the commands, and after it shows that command's usage. Shared options are
a spec joined with `&` (`AddArgs:type = Common & [...]`, records merge), and an option every
command's spec has may also come before the word (`backup --verbose create …`). A
`Subcommand` given a table instead of a spec and handler nests (`git remote add`).
`check=` (Q4) and `version=` work on `dispatch` and on a `Subcommand`.
*Considered:* a union of specs, `argparse.parse(AddArgs | ListArgs argv)`, matched by type.
The result would need to record which spec produced it, and the table reads like the specs
themselves.
*Names (cold read 32):* `dispatch` with `Subcommand` read best (5, 3, 5); `run` with `Command`
also passed (5, 3, 4).

**Q3 (b). Environment fallback: `env="PORT"`.** The command line wins, then the environment
variable, then the default. The value goes through the same reader, and a bad one names its
source: "PORT=abc: must be a whole number". Help shows "(default 8000, env PORT)". Taken from
clap's `env` and click's `envvar`. *Names:* `env`, `from_env` and `environment` all passed, and
one reader wondered whether `environment` meant a whole environment.

**Q4 (b). One rule across arguments: `check=`.** `parse(Args argv check=@problem)` calls
`problem(args)` after every field is read. A `string` result is a usage error, printed with
the usage and exit code 2; `none` passes. It has the same spelling and shape as D11 Q2's
`check=` for shapes. One mechanism covers mutually exclusive options, options that need each
other, at-least-one-of, and value checks such as "is a folder". Python's
`add_mutually_exclusive_group`, clap's `conflicts_with`/`requires` and cobra's
`MarkFlagsMutuallyExclusive` each cover only part of that. *You give up:* help doesn't list the
exclusions by itself, so the rule's message says them. *Names:* `check` and `validate` passed.

**Q5 (b). `argparse.Parsed<Spec>` names the parsed record.**
`download = (url:string args:argparse.Parsed<Args>) => …`. It is the record `parse` gives for
that spec. How the library spells it is internal: the checker already infers this record from
the unrolled loop, and `Parsed` exposes the same computation in type position. *Names:*
`Parsed` (4, 3, 4) and `Values` passed; `Result` failed, because it was read as
success-or-error.

**Q6 (b). One word for a list, when the author says so: `separator=","`.**
`columns = argparse.Named<array<int64>>(separator="," …)` accepts `columns=1,3` as well as
`columns=1 columns=3`. Only the author knows the values can't hold a comma, so it is per field
and off by default (as clap's `value_delimiter`). *Names (cold read 33):* `separator` read 4,
4, 4; `split` and `delimiter` passed lower; `also_split_on` was uneven (5, 2, 5).

**Q7 (c). `T.type_text`, not `T.spelling`.** The type as Dewy writes it, a compile-time
string, beside the existing `T.name`. Cold read 31 (21 lines, three readers): `type_text` 3/3
with the highest confidence; `written` and `as_written` 3/3 with less; `spelling` failed (one
reader took it as the alias name, one hedged); `source_name` and `full_name` failed. *Considered:*
letting a type interpolate, `"{T}"`, as Swift and Go print types. It is shorter, but makes
printing a type by mistake silent.

## Taken (each passes both tests)

- An anonymous spec with two or more positionals is a compile error naming the fix (item 4).
- `--ignore-case` names `ignore_case`; `--name=value` is accepted beside `name=value`; a valued
  argument given twice is an error (Python keeps the last silently, clap errors); `-h` and
  `--help` are reserved; an array positional takes the words later positionals don't need
  (`rename FIND REPLACE FILES...`, `cp SRC... DEST`).
- The fixes found by running it: explicit shorts don't block first letters; a valued name used
  as a flag says how to give the value; unknown names suggest the nearest; a refined integer's
  message and help say its range in words; long help types wrap.
- Flags combine (`-in`), as in every library compared.
- `Flag(default=true)` is turned off by `--no-NAME` (or `NAME=false`), shown that way in help.
  All three cold readers expected `--no-color` (cold read 32).
- `version="1.4.0"` on `parse` and `dispatch` adds `--version` (prints, exits 0).

## Not proposed

- **`--name value`.** It was decided against on 2026-09-02, and the taken error message
  teaches `name=value`.
- **Counting flags (`-vvv`).** No program needed them; `verbose=2`, or a literal union
  `log='quiet'|'normal'|'debug'`, says more.
- **Whole Dewy literals as values** (David's `arg2=r\''[1 2 3]'`). Shells split
  `only=[lex parse]` into two words and zsh, macOS's default shell, rejects the bare brackets as
  a bad pattern, so it always needs quotes, and string elements need quotes inside them too
  (`"only=['lex' 'parse']"`). Repetition and Q6 cover lists. Records as values can come later
  through the same readers (`from_json<T>`-style strict Dewy text) if a program needs them.
- **Shell completions, man pages, config files, interactive prompts for missing values.**
  Completions and man pages can be generated later from the same spec (`fields(S)`), with no
  change to it. Config files are `from_json<T>` plus Q3's precedence. Prompts belong to
  `input_field`.

## Name tests

Kit `~/dev/tmp/naming-1107/`, rounds r31–r33, three fresh context-free readers each (Sonnet,
Haiku, Fable), shuffled lines, names only. Results files: `r31/names-result31.md`,
`r32/names-result32.md`, `r33/names-result33.md`. Every name in D48 read correctly; `spelling`,
`source_name`, `full_name` and `Result` were dropped.
