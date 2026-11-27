# Refinements, Effects, and Safety

> [Generated coverage](/status/#ref-refinements-and-effects) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Every operation that could fail at run time carries an *obligation*: an index in bounds, a nonzero divisor, a value that fits a narrower integer type, a refinement a value must satisfy, a dictionary key that is present, a nonzero range step. The compiler decides each obligation one of three ways:

- **proven**: the operation compiles to the bare instruction, with no check;
- **refuted**: the operation always fails, which is a compile error;
- **unproven**: a compile error by default, naming the missing relation and the bounds the compiler knows.

Failures the compiler cannot decide by its nature (a file that may be missing, text that may not parse) are values in the result type instead; see [Errors and Forwarding](errors-and-forwarding.md).

## No Traps

By default a program has no hidden runtime checks: every obligation is proven or the program does not compile. A program opts into checks explicitly.

- `$runtime_checks`, at the top of a module, function or block, turns that scope's unproven obligations into runtime checks. A failed check prints a report on standard error and exits with status 101.
- `$prototype` does the same and prints each deferred obligation as a warning, for development.
- `panic(...)` and `$runtime_assert` are explicit checks.
- `dewy check --obligations file.dewy` lists every obligation that compiles to a check, and the setting responsible.

<!-- dewy-example: {"mode":"run","stdout":"2\n","exit":101} -->
```dewy
pick = (xs:array<int64> i:int64):>int64 => {
    $runtime_checks
    xs[i]
}
let values:array<int64> = [1 2 3]
printl(pick(values 1))
printl(pick(values 7))
```

A function that keeps a check may panic, which is its `panics` effect (see [Effects](#effects)). Code without runtime checks cannot call it. Running out of memory, or a system with no random source, reports the failure and exits with status 1; these are environmental failures, not panics.

A library that cannot prove a precondition moves it to its callers with a refined parameter, and a failure it cannot rule out it returns as a value. Exits and runtime assertions belong to applications.

## Refinements

A refinement is a condition in a type's arguments: `int64<(>? 0)>` is the `int64` values above zero.

| Form | Example |
|---|---|
| partial operator, for one comparison | `int64<(>? 0)>`, `uint64<(<? b.length)>` |
| lambda, for several conditions | `int64<i => 0 <=? i and i <=? 4>` |
| the declared name as the value | `d:int64<d >? 0>`, `high:int64<high >=? low>` |
| one-direction chain | `int64<v => 0 <=? v <? 100>` |
| exclusion | `int64 & ~0` |
| membership in a literal range | `int64<(in? 0..9)>` |
| string length, in graphemes | `string<length >? 0>` |
| array length | `array<int64 length <=? 10>` |

Bounds may be integer literals, module constants, `.min` and `.max` of fixed-width types, other scalar parameters, an array or string parameter's `length`, and stable local bindings, each plus or minus a constant. Predicates cannot contain calls or other arithmetic.

`n is? int64<(<? 100)>` tests a refinement at run time and narrows `n` when it holds.

### Refined Parameters

A refined parameter is an obligation at every call and a fact inside the body. Guards, loop ranges, lengths and other refinements prove it at the call:

<!-- dewy-example: {"mode":"run","stdout":"42\n75\n0\n3\nd\n"} -->
```dewy
positive = int64<(>? 0)>
quotient = (n:int64 d:positive):>int64 => n // d
percent = (part:int whole:int64<whole >? 0>):>int => part * 100 // whole
share = (part:int whole:int64):>int => {
    if whole >? 0 return percent(part whole)
    return 0
}
printl(quotient(84 2))
printl(share(3 4))
printl(share(3 0))
small = (n:int64<i => 0 <=? i and i <=? 4>):>int64 => n
printl(small(3))
initial = (s:string<length >? 0>):>string => s[0]
printl(initial("dewy"))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"which breaks its contract `d >? 0`"} -->
```dewy
positive = int64<(>? 0)>
quotient = (n:int64 d:positive):>int64 => n // d
printl(quotient(1 0))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove refinement `d >? 0`"} -->
```dewy
positive = int64<(>? 0)>
quotient = (n:int64 d:positive):>int64 => n // d
ask = (d:int64):>int64 => quotient(10 d)
printl(ask(2))
```

Arguments are evaluated in order and checked before the call. A parameter refinement may name a sibling parameter: `(@xs:array<int64> i:int64<0 <=? i <? xs.length>)` proves `xs[i]` in the body and moves the proof to each caller.

### Refined Results and Field Invariants

A refined result is an obligation at every `return` and a fact at every call. A result may name a parameter; references to a value parameter describe its value at entry, and a result bounded by an `@` parameter's length is checked against its final length:

<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
append = (@xs:array<int64> x:int64):>addr<(<? xs.length)> => {
    let i = xs.length
    xs.push(x)
    return i
}
let ys:array<int64> = []
let at = append(@ys 42)
printl(ys[at])
```

`addr` is a nonnegative index below the target's address-space limit (`2^48` on native targets, `2^32` on WebAssembly). Record fields and array elements may be refined too; constructors, defaults and stores prove them, and reads assume them. See [Field invariants](objects.md#field-invariants).

## Literal Types

An integer literal in a type position is its singleton type, and a union of integer singletons (`-1|1`, `Sign:type = <-1|1>`) is an `int64` whose value set is its invariant. A string literal is likewise a singleton, and a union of them is an enumeration: one word at run time, compared and matched without building text.

- Storing into a literal type is an obligation: a member literal is accepted, another literal is an error, and any other value must be proven a member (`if s is? BasePrefix`).
- `BasePrefix(text)` reads text and gives `BasePrefix | ValidationError`.
- `members(U)` lists a literal union's members; `loop m in members(U)` unrolls over them.
- Enumeration members are unordered: `<?`, `min` and sorting need a key the program chooses.

<!-- dewy-example: {"mode":"run","stdout":"-1\n0o\nnone\nmust be one of '0b' | '0o' | '0x'\nwidth 80\n"} -->
```dewy
flip = (s:-1|1):>-1|1 => if s is? 1 -1 else 1
printl(flip(1))
BasePrefix:type = '0b' | '0o' | '0x'
parse_prefix = (text:string):>BasePrefix? => {
    loop p in members(BasePrefix) { if text =? p return p }
    none
}
printl(parse_prefix("0o"))
printl(parse_prefix("0z"))
let bad = BasePrefix("0q")
if bad is? ValidationError { printl(bad.message) }
Mode:type = 'auto' | int64
show = (m:Mode):>string => match m { <'auto'> => "auto" w:int64 => "width {w}" }
printl(show(80))
```

A literal-typed parameter can select an overload: a method taking `d:0` receives a literal zero ahead of one taking `d:int64 & ~0`.

## Array Contracts and Dependent Indices

`array<int64 length <? 10>` is a growable array with a length contract; `array<int64 length=10>` is a fixed-size array. `push`, `pop`, `extend`, `clear` and `truncate` check the length they leave, so growth under `length <=? 3` needs a guard such as `if xs.length <? 3`:

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3]\n"} -->
```dewy
let bounded:array<int64 length <=? 3> = [1 2]
if bounded.length <? 3 { bounded.push(3) }
printl(bounded)
```

An array may require that its elements are valid indexes of itself by naming its own length in its element refinement. The contract also means `>=? 0` unless it states another lower bound. Every store is checked against the length it leaves; growth, `swap`, `reverse` and sorting keep the contract without a proof per element, and a shrink is an error unless it empties the array or the element values are bounded:

<!-- dewy-example: {"mode":"run","stdout":"1\n"} -->
```dewy
let parent:array<int64<(<? parent.length)>> = [0]
parent.push(parent.length)
let root = parent[parent[1]]
printl(root)
```

A record field's elements can index a sibling array the same way: `next:array<int64<(<? nodes.length)>>`. An array whose elements carry a tighter refinement is accepted by value where looser ones are expected; an `@` parameter needs the same contract.

## Type Facts

A *fact* is one condition, and a block of them, `<facts>`, is a type: `T & <facts>` is `T` where the facts hold. A result type may attach facts about the parameters to each member of a union result. A caller that tests which member it got learns those facts:

<!-- dewy-example: {"mode":"run","stdout":"25\n0\n"} -->
```dewy
positive = (a:int64):>true & <a >? 0> | false & <a <=? 0> => a >? 0
quarter = (n:int64):>int64 => if positive(n) 100 // n else 0
printl(quarter(4))
printl(quarter(0))
```

`void & <facts>` publishes a postcondition every normal exit must establish:

<!-- dewy-example: {"mode":"run","stdout":"6\n"} -->
```dewy
require_below = (i:int64 n:int64):>void & <i <? n> => { if i >=? n exit(2) }
let ys = [5 6 7]
let k = args.length
require_below(k ys.length)
printl(ys[k])
```

Each `return` must prove its arm's facts from guards or the value returned. The facts follow the argument: a fact about a parameter's length becomes a fact about the argument passed. Result facts currently take value parameters only, and need static evidence at each exit. Reassigning the result or an argument ends the facts. The prelude's `startswith` and `endswith` publish their length facts this way.

### Proofs

`$proof` marks a procedure that exists only to establish a fact. Its result is a fact block, checked at every exit. Proofs may contain static assertions, branches, bare returns and direct calls of other proofs (with no cycles). Loops, runtime calls, globals and place parameters are rejected. Proofs are erased after checking:

<!-- dewy-example: {"mode":"check"} -->
```dewy
$proof
ordered = (a:int64 b:int64<(>=? a)> c:int64<(>=? b)>):><a <=? c> => {
    $assert a <=? b
    $assert b <=? c
}
check = (a:int64 b:int64 c:int64) => {
    if a <=? b and b <=? c {
        ordered(a b c)
        $assert a <=? c
    }
}
check(1 2 3)
```

## Making Code Prove

An unproven obligation's error names the missing relation (`i <? xs.length`, `start <=? i`) and shows what is known. These forms supply facts:

- **Loop over values or positions**: `loop x in xs`, `loop i in 0.. and x in xs`, `loop i in [0..xs.length)`. A cursor loop keeps its bound in the condition: `loop i <? xs.length and xs[i] =? " " { i += 1 }`.
- **Guard the whole relation**, lower bound included: `if 0 <=? i <? xs.length`. A position that cannot be negative can say so in its type.
- **Take the missing case as a value**: `xs.get(i) ?? fallback`, `d.get(k) ?? fallback`, `text.get(i) ?? ""`, or return an optional.
- **Slice the Python way**: `xs[$clamp a..b)`.
- **Put the key in first**: `if k not in? d d[k] = 0` before `d[k] += 1`.
- **Give pairs a tuple type** (`array<[int64 int64]>`) so they unpack, and build grids with comprehensions.
- **Use a small boolean helper**: `valid = (i:int xs:array<int>):>bool => 0 <=? i <? xs.length` carries its comparison back to the caller.
- **Compute in `int`** when arithmetic may exceed a fixed width, or state the wrap: `uint32<overflow='wrap'>`.

Facts come from literals, annotations, conditions, loop ranges, successful assertions and contracts. They include integer intervals, exact and minimum lengths, index relations, the order a sum keeps with its operands, narrowed union members and present dictionary keys. Facts hold until a write or call could change them: calls preserve facts only when their effects rule out interference, and an `@` argument keeps only the facts the callee publishes.

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove index is in bounds"} -->
```dewy
at = (xs:array<int64> i:int64):>int64 => xs[i]
printl(at([1 2] 1))
```

The 64-bit counter-progress assumption proves that a 64-bit counter advanced by a loop does not overflow; `$no_assumed_bounds` turns it off. Every length is assumed below the address-space limit.

## Assertions

`$assert condition` states a fact the compiler must prove; nothing runs. A refuted condition is `assertion refuted` and an unknown one `cannot prove assertion`, each with notes on what is known. `$runtime_assert condition` checks at run time: on failure it reports the condition and exits with status 101, and the code after it has the condition as a fact.

Both take an optional message after a comma, `$assert x <? 3, "message"`; the directive owns that comma. A runtime message may interpolate values; a compile-time one is a string literal. `$expect` is the test form (see [Testing](testing.md)).

<!-- dewy-example: {"mode":"run","stdout":"2\n","exit":101} -->
```dewy
let xs:array<int64> = [1 2 3]
$assert xs.length =? 3, "three elements"
item = (ys:array<int64> i:int64):>int64 => {
    $runtime_assert 0 <=? i and i <? ys.length, "index {i} out of range"
    return ys[i]
}
printl(item(xs 1))
printl(item(xs 5))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"assertion refuted"} -->
```dewy
let i = 3
let xs = [1 2 3]
$assert i <? xs.length
```

## Effects

A function's *effect row* follows its result type after `&`. It describes what calling the function does, apart from the value it returns.

| Row | Meaning |
|---|---|
| `reads<x>`, `mutates<x>` | reads or changes the place passed as `@x` (or a field of it) |
| `allocates`, `no allocates` | may allocate; never allocates |
| `no blocks` | no I/O, waits, sleeps or foreign calls |
| `panics`, `no panics` | may panic (inferred); never panics |
| `no_effects` | the empty row |
| `E` with `<E:Effect>` | a row parameter, forwarding a callback's effects |

Omitted rows are inferred from the body. A positive row is a closed upper bound and is what callers see, even if the body does less. A negative row (`no allocates`, `no mutates<Filesystem>`) excludes what it names and leaves the rest inferred. In a row, `no` reaches to the next `&`.

<!-- dewy-example: {"mode":"run","stdout":"41\n42\n42\n3\n"} -->
```dewy
read = (@x:int64):>int64 & reads<x> => x
write = (@x:int64 value:int64):>void & mutates<x> => { x = value }
quiet = (x:int32):>int64 & no_effects => x * 2
let a:int64 = 1
write(@a 41)
printl(read(@a))
printl(quiet(21))

Action:type = <E:Effect>(x:int64:>int64 & E)
apply = <E:Effect>(f:Action<E> x:int64):>int64 & E => f(x)
inc = (x:int64):>int64 & no_effects => if x <? int64.max x + 1 else x
printl(apply(@inc 41))

zeros = (n:int64):>array<int64> & allocates => fill(0 n)
size = (xs:array<int64>):>int64 & no allocates => xs.length
printl(size(zeros(3)))
```

A body that does more than its row allows is an error naming the operation:

<!-- dewy-example: {"mode":"reject","diagnostic":"mutation of 'x' exceeds the closed row"} -->
```dewy
peek = (@x:int64):>int64 & reads<x> => { x = 0; x }
let a:int64 = 1
printl(peek(@a))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"allocation exceeds the closed row (no_effects permits none)"} -->
```dewy
double = (x:int64):>int & no_effects => x * 2
printl(double(2))
```

Field permissions such as `mutates<pair.left>` cover that field and its descendants. Calls translate place permissions by argument, so a callback's `mutates<x>` becomes `mutates<y>` when called with `@y`. Callable types keep their rows through variables, containers and results. Arbitrary-precision `int` arithmetic, interpolation and growth allocate; fixed-width scalar work, length reads and proven indexes do not.

### Panics

A function may panic when it keeps a runtime check, calls `panic` or `$runtime_assert`, or calls a function that may panic. Within one module, such checks are the module's own choice and its other functions may call them. A caller in another module must prove what the callee checks or opt in with `$runtime_checks`. `& no panics` forbids panics outright, local assertions included.

<!-- dewy-example: {"mode":"reject","diagnostic":"calling `at` may panic","fixtures":{"lib.dewy":"at = (xs:array<int64> i:int64):>int64 => {\n    $runtime_checks\n    xs[i]\n}\n"}} -->
```dewy
from lib import at
let values:array<int64> = [1 2 3]
printl(at(values 1))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"its row excludes panics"} -->
```dewy
safe = (xs:array<int64> i:int64):>int64 & no panics => {
    $runtime_assert 0 <=? i and i <? xs.length
    xs[i]
}
printl(safe([1] 0))
```

Library preconditions are the caller's obligations: `xs.first`, `xs.last`, `min_by`, `max_by` and `min(xs)` need a nonempty array, `d[k]` a present key, `pool[h]` a live handle.

### Strict settings

`$no_hidden_costs` holds `$explicit_copies`, no runtime checks, and the default row `no allocates & no panics` for every function declared without its own row. `$bulletproof` adds every remaining strict setting and turns off the compiler's convenience assumptions. Both are described in [Settings](settings.md).

## Unchecked Assumptions

`$unsafe_assume condition [, message]` will introduce a fact without a runtime check, for code where the programmer knows more than the compiler. Its truth is the programmer's responsibility; a condition the compiler can refute is still an error, and writes invalidate the fact as usual. The compiler reports it as not implemented yet.

<!-- dewy-example: {"mode":"design-only","why":"`$unsafe_assume` is decided but the compiler reports it as not implemented yet."} -->
```dewy
read_at = (xs:array<int64> i:int64):>int64 => {
    $unsafe_assume 0 <=? i and i <? xs.length, "validated by the producer"
    return xs[i]
}
```
