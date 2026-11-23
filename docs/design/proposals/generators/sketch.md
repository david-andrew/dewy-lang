# Generators, `lazy` and multi-values: David's sketch (2026-11-23)

David's high-level points:
- No `yield` keyword in the language.
- `lazy` is the primitive for constructing a new generator.
- A generator is just another kind of expression in Dewy. Ordinary functions can return generator expressions, but a wrapping function isn't required (unlike Python).
- Labeled `break` can terminate lazy computations.
- Expressions can produce zero, one or multiple values.
- Multi-values can have heterogeneous types and/or runtime-dependent arities.
- Contexts that consume expressions must handle every possible output shape, arity and type, checked at compile time.
- Multi-values expand implicitly; collections and generators need explicit spreading.
- Loops, conditions and spreading compose naturally into generator pipelines.
- Compiler optimizations should eliminate abstraction overhead where possible.

Clarification (David, 2026-11-23): `lazy` itself creates an implicit scope, whether it is followed by `()`, `{}` or anything else. Names declared inside a lazy body never escape it.

Clarifications from David (2026-11-23):
- Bare metatags as labels are a Dewy feature: a `$name` on its own prefixes what follows, and `break $name` / `continue $name` target it. LANGUAGE.md:5794 already has loop labels ("a loop label prefixes its loop"), and the pre-restart reference has `$rows` on its own line before a loop, with `continue $rows` and `break $rows`. Breaking out of different scopes already exists. Section 19's `$done` prefixing `lazy` is the same feature applied to a lazy body. If something about labels is missing from the current design, add it rather than treating it as a conflict.
- Dewy is generally not whitespace-sensitive (notable exceptions include n-D array literals). The sketch's indented layouts are illustrative formatting only: a loop or `if` body is just the expression that follows the header, on the same line or the next. Don't treat indentation as significant.

His notes on the examples: much of the example text was written by another agent. He skimmed it and saw nothing glaring, but that agent may not have had the full picture of Dewy's features and semantics, so look for issues of that kind. The examples are illustrative of how the feature works. They aren't necessarily idiomatic Dewy where a clearer way exists, though they aren't necessarily unidiomatic either.

```dewy

# ============================================================
# 1. EXPRESSIONS AND MULTI-VALUES
# ============================================================

42                            # One value
(1 2 3)                       # Three values
(1 "hello" true)              # Heterogeneous values

let x = 42                    # Declaration produces void
x += 1                        # Assignment produces void

# Eager multi-value binding
let ab = (1 2)
let abc = (1 "hello" true)

# Dynamic arity is permitted
let variable = if condition
    (1 2)
else
    (3 4 5)

# Conceptual type:
# (int int) | (int int int)
#
# The binding retains the correlation between output
# positions, types, and possible arities.


# ============================================================
# 2. FUNCTION ARGUMENTS AND VALUE PACKS
# ============================================================

add = (a:int b:int) => a+b

add(1 2)                      # 3
add((1 2))                    # 3
add(ab)                       # 3; implicit pack expansion
add(abc)                      # error, too many arguments given & wrong types

# Containers are not value packs.
let arr = [1 2]

# add(arr)                    # Type/shape error
add(arr...)                   # 3; explicit spreading

# Generators are also not value packs themselves.
let gen = lazy (1 2)

# add(gen)                    # Type/shape error
add(gen...)                   # 3; consumes and spreads

# Each consumer must accept every possible output shape.
# add(variable)               # Error: possible 3-arg case


# ============================================================
# 3. DYNAMIC ARITY AND PATTERN MATCHING
# ============================================================

let values = if condition
    (1 2)
else
    (3 4 5)

# Proposed pack-aware match: handles both possible arities.
let total = match values {
    (a:int b:int) => a+b
    (a:int b:int c:int) => a+b+c
}

# Runtime overload dispatch could provide another way to
# consume the same shape union, if that is supported.


# ============================================================
# 4. SPREADING AND COLLECTING
# ============================================================

# POSTFIX ... spreads OUT OF a source.

let a = [1 2 3]
let b = [4 5 6]

let both = [a... b...]        # [1 2 3 4 5 6]
let mixed = [0 a... 4]       # [0 1 2 3 4]

# PREFIX ... collects INTO a destination.

# Illustrative rest-argument collection and forwarding:
forward = (...args) => add(args...)

forward(10 20)                # 30

# ...args collects the supplied arguments.
# args... spreads the collected values into add.
#
# The exact general-purpose collection syntax outside
# parameter/rest contexts is a separate design detail.


# ============================================================
# 5. EAGER LOOPS AND COLLECTIONS
# ============================================================

# Execute immediately
loop i in [0..5)
    printl(i)

# A loop can express values into its surrounding context.
loop i in [0..5)
    i^2

# An container captures the values.
let squares = [loop i in [0..5) i^2]
# [0 1 4 9 16]

# Conditional production
let evens = [
    loop i in [0..10)
        if i % 2 =? 0
            i
]
# [0 2 4 6 8]

# Nested loops
let products = [
    loop a in [1..3)
        loop b in [1..3)
            a*b
]


# ============================================================
# 6. LAZY: GENERAL GENERATOR CONSTRUCTION
# ============================================================

# Lazy transformation of a group of expressions
let gen = lazy (1 2 3)

# General loop-as-lazy shorthand
let gen = lazy i in [0..10) i^2

# Conceptually equivalent:
let gen = lazy (
    loop i in [0..10)
        i^2
)

# Compare three consumption strategies:

let eager = [loop i in [0..100) i^2]
let deferred = lazy i in [0..100) i^2

loop i in [0..100)
    process(i^2)

# Materialize, defer, or consume directly.


# ============================================================
# 7. MIXING ORDINARY EXPRESSIONS WITH LOOPS
# ============================================================

# Eager multi-expression
let xs = (
    1 2 3 4

    loop i in [5..10)
        i^2

    11 12 13

    loop i in [14..20)
        i^3
)

# Lazy version of the same computation
let ys = lazy (
    1 2 3 4

    loop i in [5..10)
        i^2

    11 12 13

    loop i in [14..20)
        i^3
)


# ============================================================
# 8. GENERATOR FUNCTIONS WITHOUT YIELD
# ============================================================

# An ordinary function returning a lazy expression
squares = (n:int) => lazy (
    loop i in [0..n)
        i^2
)
# return type is perhaps `generator<int length=n>` or `(int int int ... n-times ... int int)` or something in that ballpark

let xs = squares(100)

loop x in xs
    printl(x)

# No generator-function declaration or yield required.


# ============================================================
# 9. STATEFUL GENERATORS
# ============================================================

powers_of_two = (n:int) => lazy (
    let x = 1

    loop i in [0..n) (
        x *= 2
        x
    )
)

# Produces 2 4 8 16 ...
# x is private state of the lazy computation.


# ============================================================
# 10. INFINITE GENERATORS
# ============================================================

naturals = () => lazy (
    let n = 0

    loop true (
        n
        n += 1
    )
)

# Generator execution suspends between produced outputs.
# No need to materialize an infinite sequence.


# ============================================================
# 11. HIGHER-ORDER GENERATOR COMPOSITION
# ============================================================

# Map
map = (source f) => lazy (
    loop x in source
        f(x)
)

double = (x:int) => 2*x

let xs = map(squares(10) @double)


# Filter
filter = (source predicate) => lazy (
    loop x in source
        if predicate(x)
            x
)

is_even = (x:int) => x % 2 =? 0

let xs = filter(naturals() @is_even)


# Chain
chain = (a b) => lazy (
    a...
    b...
)

let xs = chain(
    squares(5)
    powers_of_two(5)
)


# Flatmap
flatmap = (source f) => lazy (
    loop x in source
        f(x)...
)

repeat_twice = (x:int) => lazy (x x)

let xs = flatmap([1 2 3] @repeat_twice)
# Produces 1 1 2 2 3 3


# ============================================================
# 12. GENERATOR DELEGATION: YIELD-FROM WITHOUT YIELD
# ============================================================

inner = () => lazy (
    1 2 3
)

outer = () => lazy (
    0
    inner()...
    4
)

# Produces 0 1 2 3 4
#
# The inner generator is consumed incrementally.
# The outer computation suspends during delegation.
# No new yield-from construct is required.


# ============================================================
# 13. PRODUCE A GENERATOR VS SPREAD ITS VALUES
# ============================================================

# The generator itself is expressed as a value.
let nested = lazy (
    0
    inner()
    4
)

# The inner generator's values are reexpressed.
let flattened = lazy (
    0
    inner()...
    4
)

# Likewise, an array is one value unless spread.
let xs = lazy (
    [1 2]
    [3 4]...
)

# First expression produces an array value.
# Second spreads out integers 3 and 4.


# ============================================================
# 14. RECURSIVE GENERATORS
# ============================================================

# Illustrative tree API
inorder = (node) => lazy (
    if node.left isnt? none
        inorder(node.left)...

    node.value

    if node.right isnt? none
        inorder(node.right)...
)

# Recursive traversal with just:
# functions + conditions + lazy + spreading


# ============================================================
# 15. LAZY PIPELINES
# ============================================================

let xs = map(
    filter(
        squares(100)
        @is_even
    )
    @double
)

# Conceptually:
# generate squares -> filter evens -> double
#
# No intermediate collections required.
# The compiler may fuse the pipeline when legal.


# ============================================================
# 16. MULTIPLE ITERATORS
# ============================================================

# Existing multiiterator loop composition
zip = (left right) => lazy (
    loop a in left and b in right
        [a b]
)

# Each step produces an explicit two-element array.
# If desired, a future pack-valued-step version could
# express (a b), with semantics governed by the
# unresolved suspension-granularity decision.


# ============================================================
# 17. EAGER FUNCTION BOUNDARIES REMAIN EAGER
# ============================================================

eager_fn = () => (
    1
    printl("work")
    2
)

let xs = lazy (
    0
    eager_fn()
    3
)

# When execution reaches eager_fn(), that function runs
# to completion before returning its eager output pack.
#
# The surrounding lazy computation cannot suspend
# inside the ordinary function call.


# ============================================================
# 18. LAZY SUBGENERATOR BOUNDARIES
# ============================================================

lazy_fn = () => lazy (
    1
    printl("work")
    2
)

let xs = lazy (
    0
    lazy_fn()...
    3
)

# When reached, lazy_fn() constructs a generator.
# Spreading it advances its computation incrementally.
# "work" prints only when that inner output is reached.


# ============================================================
# 19. LABELED TERMINATION OF LAZY COMPUTATIONS
# ============================================================

take_until = (source stop) => (
    $done

    lazy (
        loop x in source (
            if x =? stop
                break $done

            x
        )
    )
)

# Proposed extension to Dewy's labeled break:
# $done targets the enclosing lazy computation.
#
# break $done terminates that generator.
# No special return or yield needed.


# ============================================================
# 20. LAZY CREATES A CONTROL-FLOW BOUNDARY
# ============================================================

f = () => (
    let xs = lazy (
        let local = 42

        # return 42    # Invalid: cannot return from outer f
        local
    )

    xs
)

# local belongs to the lazy scope.
# It does not escape into f's surrounding scope.
#
# return inside a separately declared nested function
# is still allowed, targeting that nested function.


# ============================================================
# 21. SIDE EFFECTS FOLLOW GENERATOR ADVANCEMENT
# ============================================================

let xs = lazy (
    printl("A")
    1

    printl("B")
    2

    printl("C")
    3
)

# Construct xs: no prints.
# First output: prints A, produces 1.
# Second output: prints B, produces 2.
# If discarded here, C is never printed.


# ============================================================
# 22. HETEROGENEOUS GENERATORS
# ============================================================

let xs = lazy (
    42
    "hello"
    true
)

# Heterogeneous outputs are legal.
# A consuming context must handle every type in sequence.


# ============================================================
# 23. VARIABLE-ARITY GENERATION
# ============================================================

let xs = lazy (
    if condition
        (1 2)
    else
        (3 4 5)
)

# The computation may produce different output shapes.
# A next operation is allowed to return an arity-tagged pack.
#
# Whether each branch's values constitute one generator
# advancement or multiple advancements is still TBD.


# ============================================================
# 24. PRODUCING PLACES
# ============================================================

let xs = lazy (
    loop @x in @values
        @x
)

# @x expresses a place, rather than copying its value.
# Compiler checks determine which escaping-place and
# lifetime situations can safely be supported.


# ============================================================
# 25. THE OPEN SUSPENSION-GRANULARITY QUESTION
# ============================================================

let xs = lazy (
    1
    (2 3)
    4
)

# OPTION A: individual-value advancement
# next -> 1
# next -> 2
# next -> 3
# next -> 4

# OPTION B: group-preserving advancement
# next -> 1
# next -> (2 3)
# next -> 4
#
# I haven't settled on which interpretation to use
# I'm leaning towards the second, but want a solid design pass to consider trade-offs/consequences of either
```

## Also asked

- `defer`: this design doesn't settle whether `defer` is valuable (open item D40 Q5). Build steelman cases for `defer` using these patterns. Earlier analysis (2026-11-14): a function-scoped `defer` fires at `return`, before a returned stream is consumed. A `defer` inside a generator body that fires when the generator finishes or is dropped would run on every way the consumer stops: exhaustion, early `break`, an error mid-stream, or cancellation (D44). D40's alternative is a value with a `$__drop__` hook. The motivating case was an LLM token stream whose full or partial reply must be recorded however the consumer stops.
