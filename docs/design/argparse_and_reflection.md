# Argument parsing and compile-time reflection

Design note, 2026-09-02, decided with David. Not started: argparse is not
blocking the bootstrap front end, and the reflection work it needs is a
commitment to make deliberately. This records the design so that when it is
picked up nothing has to be re-derived.

## The library shape

Argument parsing is a library (`library/argparse.dewy`), imported as a
namespace. The spec is a compile-time object *value* of descriptors; each
descriptor carries the argument's type, default, short alias, and help text
in one place — nothing about an argument is defined away from its
definition.

```dewy
import p"../../library/argparse.dewy" as argparse

const Args = [
    path    = argparse.Positional<Path>(help="the file to tokenize")
    verbose = argparse.Flag(help="print each token")                       # -v derived
    tabsize = argparse.Named<int64<0 <? value <=? 16>>(default=4 short='t' help="spaces per tab")
    mode    = argparse.Named<'tokens'|'ast'>(default='tokens' help="what to print")
    include = argparse.Named<array<Path>>(default=[] help="extra files, repeatable")
]

main = (argv:array<string>) => {
    let args = argparse.parse(Args argv about="tokenize a dewy file")
    if args.verbose printl"tokenizing {args.path}"     # args.verbose:bool, args.path:Path
}
```

**Descriptors.** Three: `Positional<T>`, `Named<T>`, `Flag`. A literal union
as `T` is a choice list (`Named<'tokens'|'ast'>`; no separate `Choice`,
help lists the members). `array<T>` is repeatable. A refined `T` is
validated at parse time and the field carries the refinement statically
afterwards. `T?` is optional without a default.

**The command line is a constructor call.** Tokens fill the spec the way an
object literal fills a type (`positional_objects.dewy`): bare tokens fill
`Positional` fields in declaration order, `name=value` fills any field by
name (positionals included), defaults fill the rest, a required field left
empty is a usage error. Flags: `--verbose`, `-v`, `verbose=true|false`. A
short on a valued argument mirrors the preferred form: `-t=2`, not `-t 2`
(`--name value` is deliberately unsupported: it makes `--flag positional`
ambiguous). A token matching `^[A-Za-z_][A-Za-z0-9_]*=` is named; `--` ends
option parsing. `--help`/`-h` prints the generated usage: one line per field
with its type spelled in Dewy, default, choices, refinement, help.

**Shorts.** `short=` on any descriptor; flags without one get the first
letter of the name when it is unique among the flags; `short=none` opts
out. When `doc"…"` strings become attachable to fields, `help=` can give way
to a field doc.

**Failure.** Two functions, because a runtime boolean cannot change a
return type: `argparse.parse(Args argv …):>Args` prints the message and the
usage and exits 2 (`:>never` on that path, so the result needs no
unwrapping); `argparse.try(Args argv …):>Args | UsageError` for a program
that wants to do something else. `UsageError` carries the message and the
rendered help.

**Result type.** Strongly typed, derived field by field from the
descriptors: `[path:Path verbose:bool tabsize:int64<0 <? value <=? 16>
mode:'tokens'|'ast' include:array<Path>]`. Nothing in the checker knows the
word "argparse": the type comes from ordinary inference over `parse`'s
body, below.

## Not compiler magic: `parse` in ordinary Dewy

```dewy
let parse = <S>(spec:S argv:array<string> about:string="") => {
    let scan = scan_arguments(argv)                     # runtime: name=value, --flag, -f, -t=2, positionals, --
    if scan.help { print_usage(spec about) exit(0) }
    let args = [loop f in fields(S) $field(f.name) = take(spec.$field(f.name) f.name scan)]   # unrolled
    reject_leftovers(scan)                              # unknown names, extra positionals → usage error
    return args
}

let take = (d:Flag name:string scan:Scan):>bool => scan.flag(name d.short)
let take = <T>(d:Named<T> name:string scan:Scan):>T => match scan.named(name d.short) {
    text:string => convert(T text) or_usage_error"{name}"
    <none> => d.default
}
let take = <T>(d:Positional<T> name:string scan:Scan):>T => …

let convert = <T>(text:string):>T | ParseError => …     # `T(text)`: the type's own string constructor
int64 &= (text:string):>int64 | ParseError => …          # parsers are converting constructors
Path  &= (text:string):>Path => p(text)
```

Descriptor dispatch is the overload set `take` (exists). String-to-`T` is
the `&=` converting constructor (exists for user types, `type_methods.dewy`).
The result type is inferred from the unrolled literal (exists). The three
things that do not exist are below.

## The compiler features, each general

Decided framing: these are the first, restricted form of compile-time
execution — restricted to iteration over type-derived sequences,
compile-time strings, and type values — not a separate reflection
mechanism. Dewy's planned compile-time execution (Jai-style: run ordinary
code at compile time, no macro language) *consumes* these primitives; it
does not replace them. Later, "arbitrary comptime" lifts the restriction on
what the evaluator runs; nothing here is throwaway. Macros as AST/source
generation are ruled out on purpose: a second language, hygiene, opaque
generated code, and error attribution that every macro author must do by
hand — whereas an instantiated generic is ordinary code the checker reports
on at the user's line.

1. **Computed field names, and compile-time loops in literals.**
   `$field(name)` reads or writes an object field by name; `name` **must be
   a compile-time string**. `[$field("x") = 1]` is `[x = 1]`. In a loop it is
   therefore only legal when the loop unrolls at compile time (`fields(S)`,
   `members(U)`, a constant array of strings) — after unrolling the literal
   is a plain literal with known fields, so its type is ordinary inference:
   no object comprehension as a feature, no mapped types. A runtime name is
   an error: *an object's fields are fixed at compile time; a runtime name
   makes a dictionary.* (An earlier sketch wrote `f.name = value` inside the
   literal; that is a member assignment on `f`, hence the metatag.
   `spec[f]` as sugar for `spec.$field(f.name)` can come later.)
2. **`fields(S)` and `members(U)`.** Compile-time sequences: the fields of an
   object type (descriptors with `.name`, a compile-time string, and
   `.type`) and the members of a literal union (each usable as its
   singleton value — `loop m in members(T) if text =? m return m`). `loop`
   over either unrolls per instantiation inside a generic.
3. **`T(text)` inside a generic** resolves the *instantiated* type's
   constructors, and `&=` may add converting constructors to builtin types
   from the library (`int64 &= (text:string):>int64 | ParseError`).
4. **Validation-backed refinements.** `v is? int64<0 <? value <=? 16>` as a
   runtime check that narrows to the refined type (the reference currently
   lists this as not implemented). Storing into the refined field then
   needs no new machinery: the guard is the proof the bounds analysis
   already accepts. Independently useful for anything reading numbers from
   the outside world.
5. **Two small gaps found while probing (2026-09-02):** constructing through
   a namespace import (`argparse.Named<int64>(default=4)` — "runtime use of
   an imported type is not yet handled"; the type position works) and a
   literal union as a type argument (`Named<'tokens'|'ast'>` — "type
   parameterization is not yet handled").

Order when picked up: 5, 4, 3 (each lands as a usable feature on its own),
then 2 and 1 together (the reflection core, the only purely new feature),
then the library, a fixture, docs, and `tok src.dewy --verbose` in t0's
`main` as the proof. Roughly five slices. Decided against: a
compiler-synthesized `argparse` builtin as a stopgap (would be deleted when
the real thing lands); dict → object conversion (a `dict<string V>` has one
value type and loses which field carries which — it works in JavaScript
because JS objects are not statically shaped). If the bootstrap needs argv
parsing before this lands, a hand-written `name=value` scanner in t0's
`main` prejudges nothing.
