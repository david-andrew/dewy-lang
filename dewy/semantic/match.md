# `match`

Decided with David on 2026-08-28.

## Form

`match <scrutinee> <arm | { arms }>`, a member of the ordinary flow chain, so
`else` attaches outside the arms and interleaves with `if`/`loop`:

```dewy
match v {
    answer:42        => 'the answer'
    i:int<i <? 100>  => 'small'
    big:int          => 'big'
} else if other { … } else { … }
```

An arm is a function-literal-shaped expression `<signature> => <body>`: the
left of `=>` is a parameter signature and the arm matches when the scrutinee
*satisfies* that signature. The forms:

| arm | matches when | binds |
|---|---|---|
| `name:T` | the value `is? T` (a member of the union, a singleton `42`, `"fast"`) | `name`, narrowed to `T` |
| `name:T<refinement>` | `is? T` and the refinement holds — the refinement is the arm's **guard** | `name`, with the refinement as a fact |
| `<T>` | `is? T` | nothing |
| `name` | always (the catch-all) | `name` at the scrutinee's type — shadows whatever `name` meant, as a parameter would; `_` is the idiom, any other name warns, saying whether it shadows a type or a value (`name:T` binds with a type; `<T>` matches a type) |
| `[f g:T h:1]` | the value is the object member with those fields, and each typed/literal field satisfies its type | `f`, `g`, `h` to the fields |
| `(p q r)` | the scrutinee is a sequence of that arity and each element satisfies its pattern; `<T>` and named patterns mix freely | per element |

Patterns are types, so "does it match" is the type system's subtyping and
refinement machinery: a bare-typed arm is a `TypeTest`, a literal arm a
`TypeTest` on a union member or an equality on a word, a refinement a
comparison, an object pattern a `TypeTest` on the object member plus
comparisons on its fields. Arms are tried top to bottom; the first that
matches wins (guards make "most specific" ill-defined).

## Desugaring

The scrutinee is read once: a bare identifier is used as is (so the arms
narrow *it*, and a `<T>` arm sees the identifier narrowed), any other
expression is bound to a hidden local. Each arm becomes an `if` arm whose
condition is the signature test (type test `and` guards, built in the arm's
own narrowed context) and whose body is a scoped block that first declares
the pattern's names (`let name = scrutinee`, `let f = scrutinee.f`) and then
the arm body. The chain then goes through the ordinary flow checking, so
narrowing, value production, divergence, and `else` are unchanged, and the
lowering needs nothing new.

## Totality

A chain that contains a `match` must be **total**: every member of the
scrutinee's type must be covered by the arms, or the chain must end in
`else`. Coverage is computed on value sets, so guards count when the type
lets them:

- a bare-typed arm covers its member(s) whole; a catch-all covers everything;
- a literal arm covers one value; a guarded arm covers the interval its
  propositions denote (every refinement proposition is `<subject> <op>
  <constant>`, so an arm's coverage is always an interval with holes);
- an integer member is covered when the arms' intervals union to its whole
  range — finite for fixed widths and singleton unions (`-1|1`, `int8`),
  unbounded for `int`/`bigint` (covered by e.g. `<? 0`, `=? 0`, `>? 0`);
- an object member is covered by an unconstrained pattern, or when one of
  its fields' value sets is covered by the field patterns across arms
  (`[sign:1 …]` and `[sign:-1 …]` cover `[sign:-1|1 …]`);
- a sequence scrutinee is covered by an arm that covers every element.

The diagnostic names the first uncovered member or value. An arm that adds
nothing to the coverage of any member is **unreachable** and is an error:
no dead code paths, in the same spirit as no traps.

## Not in the first cut

Nested object patterns inside sequence patterns, string-valued guards, and
binding a narrowed *and renamed* whole value alongside a shape (`[…] as b`).
