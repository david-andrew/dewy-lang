# Compile-Time Facilities and Metatags

Dewy uses ordinary language values and expressions at compile time where possible rather than defining unrelated macro, type, and project languages.

## Type Values

Types are compile-time values of type `type`. Aliases, parameterized type constructors, physical dimensions, and refinements use this model. See [Types and Conversions](types-and-conversions.md).

`type of Parent` is generative: every evaluation creates a fresh nominal child. All other type algebra, including `&`, is non-generative. Binding a generated type once gives it stable identity; aliases and structural intersections retain that identity rather than minting another one.

## Import Values

Source imports accept exact compile-time structural path values. Runtime-computed values cannot alter the source module graph. See [Modules and Imports](modules-and-imports.md).

## Metatags

A `$name` metatag declares scope-level metadata. Its exact interpretation depends on the recognized name and context.

Loop labels use a bare metatag:

```dewy
{
    $rows

    loop row in rows {
        if retry_row()
            continue $rows
        if finished()
            break $rows
    }
}
```

The name applies to loops directly in that scope rather than attaching textually to only the next loop. It is visible throughout the scope, cannot duplicate or shadow an active label, and does not cross a function boundary.

Configuration metatags may bind a compile-time value:

```dewy
$no_prelude = true
```

`$no_prelude` affects only its containing module.

Directive metatags are forms with their own argument grammar rather than scope metadata: `$assert cond [, message]`, `$runtime_assert cond [, message]`, and `$expect cond [, message]` take a condition and an optional message (see [Assertions](refinements-and-effects.md#assertions)); `$include_bytes(p"…")` reads a file at compile time; `$target` is the compile-time target name. `$test` (or `$test(cases=…)`) on its own line marks the function declaration after it as a test (see [Testing](testing.md)).

## General Compile-Time Evaluation

The direction is for compile-time execution to reuse Dewy semantics while enforcing termination, purity, reproducibility, capability, and diagnostic requirements appropriate to compilation.

The complete evaluation boundary, user-defined metatag model, generated declarations, syntax extension facilities, and artifact APIs remain provisional. Implementations must reject unsupported compile-time operations rather than silently defer them to runtime when that would change meaning.
