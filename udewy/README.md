<p align="center">
  <img src="https://raw.githubusercontent.com/david-andrew/dewy-lang/master/assets/udewy_logo_128x128.png" alt="Dewy logo" />
</p>


# The μDewy Subset Programming Language

udewy (μdewy, "micro-dewy") is a strict subset of the Dewy programming language, designed for bootstrapping. It serves as an intermediate step in a trusted computing base, providing a language simple enough to implement in assembly while being expressive enough to write a real compiler.

**Key principle**: Any well-formed udewy program should compile and behave identically under both the udewy compiler and the full Dewy compiler.

This document serves as the **definitive specification** for the udewy language. There is no implementation-defined behavior; all semantics are fully specified here.

## Quick Start

```bash
# Run a udewy program (default x86_64 target)
python -m udewy.p0 udewy/tests/test_hello.udewy

# Compile only (don't run)
python -m udewy.p0 -c udewy/tests/test_hello.udewy

# Target a different backend
# For wasm32, this opens the generated HTML in your browser
python -m udewy.p0 --target wasm32 udewy/tests/test_hello.udewy
python -m udewy.p0 --target riscv udewy/tests/test_hello.udewy
python -m udewy.p0 --target arm udewy/tests/test_hello.udewy
```

The compiler produces artifacts in `__dewycache__/`.

> NOTE: long-term goals is for the default compile target to match the host machine/OS

### Supported Targets

| Target | Output | Requirements |
|--------|--------|--------------|
| `x86_64` (default) | Linux ELF executable | GNU as, ld |
| `wasm32` | Single HTML with embedded WASM | wat2wasm (wabt) |
| `riscv` | RISC-V 64-bit executable | riscv64-linux-gnu toolchain, qemu-riscv64 |
| `arm` | AArch64 executable | aarch64-linux-gnu toolchain, qemu-aarch64 |

### Hello World

```udewy
# SYS_WRITE and STDOUT are builtin constants provided by the x86_64 backend
let main = ():>int => {
    let msg:int = "Hello from udewy!\n"
    let len:int = __load__(msg - 8)
    __syscall3__(SYS_WRITE STDOUT msg len)
    return 0
}
```

---

# Part 1: Core Language Specification

## 1.1 Lexical Structure

### Character Set

udewy source files are encoded in ASCII. UTF-8 is compatible in contexts where extended characters are allowed (e.g. string literals).

Valid ASCII characters:
- Letters: `A-Z`, `a-z`
- Digits: `0-9`
- Symbols: `! " # % & ' ( ) * + , - . / : ; < = > ? @ [ \ ] ^ _ { | } ~`
- Whitespace: space (0x20), tab (0x09), carriage return (0x0D), newline (0x0A)

### Whitespace

Whitespace characters (space, tab, carriage return, newline) are ignored except as token separators. There are no significant indentation or newline rules.

### Comments

Only line comments are supported. A `#` character begins a comment that extends to the end of the line:

```udewy
# This is a comment
let x:int = 42  # inline comment
```

Block comments are not supported.

### Identifiers

Identifiers consist of letters, digits, and underscores, and must begin with a letter or underscore:

```
identifier ::= [a-zA-Z_][a-zA-Z0-9_]*
```

Identifiers are case-sensitive. The following are reserved keywords and cannot be used as identifiers:

```
let  const  if  else  loop  break  continue  return
import  extern  transmute  and  or  xor  not  true  false  void
```

> NOTE: `import` is a preprocessing-only directive. It is recognized before any actual code; any `import` that reaches tokenization is an error.

### Number Literals

udewy supports three number formats. All produce 64-bit integer values. Underscore separators (`_`) are allowed anywhere within the digit sequence for readability.

**Decimal integers:**
```udewy
42
1_000_000
0
```

**Hexadecimal integers** (prefix `0x`, digits case-insensitive):
```udewy
0xff
0x1a2b_3c4d
0xDEAD_BEEF
```

**Binary integers** (prefix `0b`):
```udewy
0b1010
0b1111_0000
```

All number literals are unsigned and must fit within 64 bits.

### Boolean Literals

Boolean values are represented as specific 64-bit integer patterns:

| Literal | Value | Bit Pattern |
|---------|-------|-------------|
| `true` | -1 (signed) / 18446744073709551615 (unsigned) | `0xFFFF_FFFF_FFFF_FFFF` (all bits set) |
| `false` | 0 | `0x0000_0000_0000_0000` (no bits set) |

This representation allows bitwise operators (`and`, `or`, `xor`, `not`) to function correctly as both bitwise and logical operators.

### String Literals

Strings are enclosed in double quotes. Strings may span multiple lines:

```udewy
let msg:int = "Hello, World!"
let multi:int = "This string
spans multiple lines"
```

**Escape sequences:** A backslash followed by certain characters produces special values:

| Escape | Value | Description |
|--------|-------|-------------|
| `\n` | 10 | Newline (line feed) |
| `\t` | 9 | Horizontal tab |
| `\r` | 13 | Carriage return |
| `\0` | 0 | Null byte |
| `\<newline>` | (none) | Line continuation - the newline is skipped |
| `\<other>` | `<other>` | Any other character produces that character literally |

The last rule means `\"` produces a double-quote character and `\\` produces a backslash.

**Line continuation:** A backslash immediately before a newline causes that newline to be skipped:

```udewy
let long:int = "\
This is a very \
long string that appears \
on one line"
```

**Memory layout:** String literals are stored in static memory with an 8-byte length prefix. The variable holds a pointer to the first character (after the length). See [Memory Layout](#16-memory-layout).

### Path Literals

Path Literals use the `p"..."` syntax. They are only recognized by the import preprocessor and are not part of the regular token stream or parser grammar:

```udewy
import p"utils.udewy"
import p"../lib/helpers.udewy"
```

Path literals support the same escape sequences as regular strings.

### The `void` Keyword

`void` is a special keyword representing the absence of a meaningful value. It is primarily used in:

```udewy
return void              # return from a void function
let f = ():>void => {}   # declare a void-returning function
```

---

## 1.2 Type System

### Runtime Representation

udewy treats **everything as 64-bit integers** at runtime. Pointers, booleans, characters—all are integers under the hood. There is no runtime type checking.

### Type Annotations

Type annotations are syntactically required in variable declarations and function signatures but are **not checked** by the udewy compiler. They exist to:
1. Maintain compatibility with full Dewy (which does check types)
2. Document programmer intent
3. Guide certain parsing decisions

**Variable type annotation** (`:type`):
```udewy
let x:int = 42
```

**Parameterized types** (`:type<param>` or `<param>` alone):
```udewy
let arr:array<int> = [1 2 3]
let mixed<int|string> = value    # type param without colon
```

The content inside `<>` is not validated. This allows complex type expressions that udewy couldn't otherwise parse:
```udewy
let x<(int & Something<10>) | undefined> = 10
```

**Function return type** (`:>type`, `:>type<param>` or `:> <param>`):
```udewy
let add = (a:int b:int):>int => { return a + b }
let get_value = ():>result<int> => { ... }
let flexible = ():> <A&B|C<int>> => { ... }  # complex return type
```

### The `transmute` Keyword

`transmute` is a bit-preserving type cast that is a no-op in udewy:

```udewy
let ptr:int = some_address transmute int
let arr:int = buffer transmute array<byte>
```

`transmute` preserves the underlying bits while changing the type annotation. It allows udewy code that manipulates raw integers to be valid in the strictly-typed full Dewy.

**Syntax:** `<expr> transmute <type>`

Where `<type>` can be an identifier, an identifier with type parameters, or just type parameters:
```udewy
expr transmute int
expr transmute array<int>
expr transmute <T|U>
```

---

## 1.3 Expressions

### Operator Precedence

udewy parses expressions **left-to-right** with a precedence violation check. If a higher-precedence operator follows a lower-precedence one without explicit parentheses, the compiler will error.

Precedence levels (highest to lowest):

| Level | Operators | Description |
|-------|-----------|-------------|
| 7 | `*`, `//`, `%` | Multiplicative |
| 6 | `+`, `-` | Additive |
| 5 | `<<`, `>>` | Shift |
| 4 | `=?`, `not=?`, `>?`, `<?`, `>=?`, `<=?` | Comparison |
| 3 | `and` | Bitwise/logical AND |
| 2 | `xor` | Bitwise/logical XOR |
| 1 | `or` | Bitwise/logical OR |
| 0 | `\|>` | Pipe |

**Examples:**
```udewy
# Error: precedence violation (+ before *)
let bad:int = a + b * c

# OK: explicit grouping
let ok:int = a + (b * c)

# OK: left-to-right, same or decreasing precedence
let also_ok:int = a * b + c
let chain:int = a + b + c
```

### Unary Operators

| Operator | Description | Semantics |
|----------|-------------|-----------|
| `-` | Negation | Two's complement negation: `0 - x` |
| `not` | Bitwise/logical NOT | Inverts all 64 bits |

Unary operators bind tightly to their operand:
```udewy
let x:int = -(a + b)
let y:int = not flags
```

### Arithmetic Operators

| Operator | Description | Semantics |
|----------|-------------|-----------|
| `+` | Addition | 64-bit wrapping addition |
| `-` | Subtraction | 64-bit wrapping subtraction |
| `*` | Multiplication | 64-bit wrapping multiplication |
| `//` | Integer division | Signed 64-bit division, truncated toward zero |
| `%` | Modulo | Signed 64-bit remainder |

Division and modulo use **signed** interpretation. Division by zero behavior is backend-dependent (typically causes a fault).

### Shift Operators

| Operator | Description | Semantics |
|----------|-------------|-----------|
| `<<` | Left shift | Shift left, fill with zeros |
| `>>` | Right shift (unsigned) | Logical shift right, fill with zeros |

The shift amount is masked to the low 6 bits (0-63).

**Important:** The `>>` operator performs an **unsigned (logical) shift**, filling vacated bits with zeros regardless of the sign bit. For arithmetic (signed) right shift that preserves the sign bit, use the `__signed_shr__` intrinsic.

### Comparison Operators

All comparison operators return `true` (`0xFFFF_FFFF_FFFF_FFFF`) or `false` (`0x0000_0000_0000_0000`).

| Operator | Description | Semantics |
|----------|-------------|-----------|
| `=?` | Equal | True if operands are bit-identical |
| `not=?` | Not equal | True if operands differ in any bit |
| `>?` | Greater than | **Signed** comparison |
| `<?` | Less than | **Signed** comparison |
| `>=?` | Greater or equal | **Signed** comparison |
| `<=?` | Less or equal | **Signed** comparison |

**Note:** Relational comparisons (`>?`, `<?`, etc.) interpret operands as **signed** 64-bit integers.

### Bitwise/Logical Operators

| Operator | Description | Semantics |
|----------|-------------|-----------|
| `and` | Bitwise AND | 64-bit bitwise AND |
| `or` | Bitwise OR | 64-bit bitwise OR |
| `xor` | Bitwise XOR | 64-bit bitwise XOR |

Due to the boolean representation (`true` = all 1s, `false` = all 0s), these operators work correctly as both bitwise and logical operators.

**Important:** There is **no short-circuit evaluation**. Both operands of `and` and `or` are always evaluated. This is a significant divergence from full Dewy, which short-circuits.

### Pipe Operator

The pipe operator `|>` passes the left operand as the first argument to the function on the right:

```udewy
result = x |> double |> add_one
# equivalent to: add_one(double(x))
```

The right operand must evaluate to a function pointer.

### Parentheses and Grouping

Parentheses override precedence and grouping:

```udewy
let x:int = (a + b) * c
```

### Array Literals

Array literals are enclosed in square brackets with space-separated elements:

```udewy
let nums = [1 2 3 4 5]
let handlers = [on_start on_update on_stop]
let messages = ["error" "warning" "info"]
```

Elements may be:
- Number literals
- String literals
- Identifiers referencing compile-time stable values or functions

A value is **compile-time stable** when the compiler can determine it completely during compilation and knows that the binding cannot later change. In practice this includes:
- Number literals
- String literals
- Array literals
- Static storage addresses produced by `__static_alloca__(...)`
- Backend-provided builtin constants
- `const` bindings initialized from other compile-time stable values
- Function identifiers, since functions are top-level only and cannot be redefined or reassigned

Top-level `let` and `const` bindings may also use non-stable initializer expressions. Those initializers are lowered into a synthetic startup pass that runs once before `main`, in declaration order. Such bindings remain ordinary runtime globals, so they do **not** count as compile-time stable unless their initializer was already compile-time stable.

Array literals are stored in static memory with an 8-byte length prefix. See [Memory Layout](#16-memory-layout).

### Function Calls

**Named call:**
```udewy
result = add(1 2)
```

**Expression call** (calling a computed function pointer):
```udewy
let fn_ptr:int = get_handler()
(fn_ptr)(arg1 arg2)
```

Arguments are space-separated (no commas).

---

## 1.4 Statements

### Variable Declarations

Variables must be declared with `let` or `const`, require a **type annotation**, and require an initializer:

```udewy
let x:int = 42
const BUFFER_SIZE:int = 1024
let data<array<int>> = [1 2 3]
```

`let` declares a mutable binding. `const` declares an immutable binding and cannot be assigned after its initializer.

At local scope, the initializer must be a normal expression. `extern` initializers are not allowed inside function bodies.

### Assignment

Simple assignment:
```udewy
x = 42
```

The assignment target must be a `let` binding. Assigning to a `const` is a compile-time error.

**Compound assignment** operators combine a binary operation with assignment:

| Operator | Equivalent |
|----------|------------|
| `x += y` | `x = x + y` |
| `x -= y` | `x = x - y` |
| `x *= y` | `x = x * y` |
| `x //= y` | `x = x // y` |
| `x %= y` | `x = x % y` |
| `x <<= y` | `x = x << y` |
| `x >>= y` | `x = x >> y` |
| `x and= y` | `x = x and y` |
| `x or= y` | `x = x or y` |
| `x xor= y` | `x = x xor y` |

### If / Else

```udewy
if condition {
    # then branch
} else if other_condition {
    # else-if branch
} else {
    # else branch
}
```

Braces are **always required**. Conditions check if **any bit is set** (non-zero = true, zero = false).

> **Well-formedness note:** Full Dewy requires conditions to be strictly `bool` typed. Using a non-bool value as a condition (e.g., `if some_int { ... }`) will fail Dewy type-checking even though it compiles in udewy.

### Loop

udewy has a single loop construct that loops while a condition is true:

```udewy
let i:int = 0
loop i <? 10 {
    # body
    i = i + 1
}
```

The condition is evaluated before each iteration. Braces are required.

### Break and Continue

Within a loop:
- `break` exits the innermost loop immediately
- `continue` jumps to the next iteration (re-evaluates condition)

```udewy
loop true {
    if done {
        break
    }
    if skip_this {
        continue
    }
    # ...
}
```

### Return

All functions must explicitly return using `return`:

```udewy
return value     # return a value
return void      # return from a void function
```

The return expression is **mandatory**. Use `return void` for functions that don't return a meaningful value.

### Import Directives

Import directives bring definitions from other udewy files into scope:

```udewy
import p"utils.udewy"
import p"lib/helpers.udewy"
import p"../third_party/libfoo.a"
```

**Semantics:**
- Paths are relative to the importing file's directory
- Imports are recognized only in the leading prelude at the top of a file
- Imports ending in `.udewy` are treated as udewy source and processed recursively
- Imported paths with any other suffix are treated as direct external link artifacts, not source
- Native artifacts are expected to be fully prepared for the final backend link step; native targets hand them directly to the system linker
- Each imported source file or artifact path is only included once
- Imported udewy source is prepended to the source being compiled
- After preprocessing, import directives are removed from the source before tokenization and parsing
- `import` remains a reserved word; if it reaches tokenization, the tokenizer reports an error

---

## 1.5 Functions

### Declaration

Functions are declared using lambda syntax assigned to a variable:

```udewy
let add = (a:int b:int):>int => {
    return a + b
}

let greet = ():>void => {
    # do something
    return void
}
```

- **All parameters must have type annotations** (e.g., `a:int`)
- **Return type annotation is required** using `:>` syntax (e.g., `:>int`)
- Parameters are space-separated (no commas)
- All functions must explicitly `return`
- Functions may only be declared at **top level** (no nested functions)

### External Declarations

udewy supports top-level external declarations for functions and globals provided by linked artifacts:

```udewy
let SDL_Init = (flags:int):>bool => extern
let SDL_Quit = ():>void => extern
let errno:int = extern
```

Extern declarations use the same syntax as ordinary top-level declarations, but replace the function body or initializer with the `extern` keyword.

**Rules:**
- Extern declarations are only valid at **top level**
- Local extern declarations are a compile-time error
- Extern functions participate in normal forward-reference resolution by name
- Extern globals and functions are resolved by the native linker, not by udewy source imports
- Backends that do not support native external linking may reject `extern`

### Forward References

Functions can be called before they are defined. Unknown identifiers during parsing are treated as forward function references and resolved at the end of compilation. If a forward reference remains undefined, compilation fails.

### Calling Convention

Functions follow platform-specific calling conventions (see backend addendums). Arguments are passed in registers and/or on the stack depending on the backend.

### No Closures

udewy does not support closures. Functions cannot capture variables from enclosing scopes. All functions operate only on their parameters, global variables, and locally declared variables.

---

## 1.6 Memory Layout

### Overview

udewy uses a simple, uniform memory layout. All values are 64-bit integers. Complex data structures are built using pointers and manual offset calculations.

### Strings and Arrays

Both strings and arrays share the same layout in memory:

```
┌─────────────────┬────────────────────────┐
│ Length (8 bytes)│ Data (N × element_size)│
└─────────────────┴────────────────────────┘
```

- **Length prefix:** 8 bytes containing the number of elements (not byte count)
- **Data:** The actual content
  - Strings: 1 byte per character (ASCII)
  - Arrays: 8 bytes per element (all elements are 64-bit)

When you use a string or array literal, the variable holds a pointer to the **start of the data** (after the length). Access the length at `ptr - 8`:

```udewy
let arr = [10 20 30]
#        ┌─────────┬────┬────┬────┐
# Memory │ len=3   │ 10 │ 20 │ 30 │
#        └─────────┴────┴────┴────┘
#                  ↑
#                  arr points here

let len:int = __load__(arr - 8)      # 3
let first:int = __load__(arr)        # 10
let second:int = __load__(arr + 8)   # 20
```

### Static vs Dynamic Data

**String and array literals** are stored in static memory (the data section). This has important implications:

1. They are **mutable** - values can be overwritten
2. They are **shared** - all uses of the same literal reference the same memory
3. They persist across function calls (no stack allocation)

```udewy
let put_int = (n:int):>void => {
    let buf = [0 0 0 0 0 0 0 0]  # static buffer
    # buf contains values from previous calls!
    # ...
}
```

For fresh storage, allocate memory dynamically using syscalls (see examples).

### Simulating Structs

udewy doesn't have built-in structs. Use offset constants:

```udewy
const PERSON_NAME:int = 0
const PERSON_AGE:int = 8
const PERSON_HEIGHT:int = 16
const PERSON_SIZE:int = 24

let person:int = alloc(PERSON_SIZE)

__store__(name_ptr person + PERSON_NAME)
__store__(25 person + PERSON_AGE)
__store__(180 person + PERSON_HEIGHT)

let age:int = __load__(person + PERSON_AGE)
```

---

## 1.7 Scoping

### Block Scope

Variables are block-scoped. A new scope is created for:
- Function bodies
- If/else branches
- Loop bodies

Variables declared in an inner scope shadow variables with the same name in outer scopes.

### Name Resolution

When an identifier is referenced, it is resolved by searching:
1. Current block scope
2. Enclosing block scopes (innermost to outermost)
3. Function parameters
4. Global scope (top-level constants, globals, and functions)

If not found in any scope, it is treated as a forward reference to a function.

### Global Scope

Top-level declarations are in global scope and visible throughout the file (including before their declaration point due to forward reference handling).

---

# Part 2: Core Intrinsics

Intrinsics are built-in operations that compile to target-specific instructions. They are called like functions but are handled specially by the compiler.

## 2.1 Memory Operations

These intrinsics provide direct memory access:

| Intrinsic | Description |
|-----------|-------------|
| `__load__(addr)` | Shorthand for `__load_u64__(addr)` |
| `__load_u8__(addr)` | Load unsigned 8-bit value from `addr`, zero-extend to 64-bit |
| `__load_u16__(addr)` | Load unsigned 16-bit value from `addr`, zero-extend to 64-bit |
| `__load_u32__(addr)` | Load unsigned 32-bit value from `addr`, zero-extend to 64-bit |
| `__load_u64__(addr)` | Load unsigned 64-bit value from `addr` |
| `__load_i8__(addr)` | Load signed 8-bit value from `addr`, sign-extend to 64-bit |
| `__load_i16__(addr)` | Load signed 16-bit value from `addr`, sign-extend to 64-bit |
| `__load_i32__(addr)` | Load signed 32-bit value from `addr`, sign-extend to 64-bit |
| `__load_i64__(addr)` | Load signed 64-bit value from `addr` |
| `__store__(val addr)` | Shorthand for `__store_u64__(val addr)` |
| `__store_u8__(val addr)` | Store low 8 bits of `val` to `addr`, return 0 |
| `__store_u16__(val addr)` | Store low 16 bits of `val` to `addr`, return 0 |
| `__store_u32__(val addr)` | Store low 32 bits of `val` to `addr`, return 0 |
| `__store_u64__(val addr)` | Store 64-bit `val` to `addr`, return 0 |
| `__store_i8__(val addr)` | Store low 8 bits of `val` to `addr`, return 0 |
| `__store_i16__(val addr)` | Store low 16 bits of `val` to `addr`, return 0 |
| `__store_i32__(val addr)` | Store low 32 bits of `val` to `addr`, return 0 |
| `__store_i64__(val addr)` | Store 64-bit `val` to `addr`, return 0 |
| `__alloca__(size)` | Allocate `size` bytes of temporary storage and return an 8-byte-aligned address |
| `__static_alloca__(size)` | Allocate `size` bytes of writable static storage and return its address |

Signed and unsigned 64-bit loads/stores are identical at runtime; both spellings exist to make programmer intent explicit. `__load__`/`__store__` are convenience shorthands for the unsigned 64-bit forms. For stores, signedness affects only intent and documentation; the stored bit pattern is the low `N` bits of `val`.

`__alloca__(size)` reserves temporary storage whose lifetime lasts until the current function returns. The returned address is aligned to at least 8 bytes, and native backends may round the reserved size up further to preserve ABI stack alignment. Native backends typically implement this with function-local stack storage; the wasm backend uses a function-scoped stack region in linear memory.

`__static_alloca__(size)` reserves writable storage in the program's static data area. The storage is zero-initialized, has a single shared instance for the entire program, and is not tied to any function call frame. Its `size` argument must be a compile-time stable integer value, which may be provided directly as a number literal or indirectly through a `const` binding or backend-provided builtin constant.

## 2.2 Arithmetic Operations

| Intrinsic | Description |
|-----------|-------------|
| `__signed_shr__(val bits)` | Arithmetic (signed) right shift; fills vacated bits with the sign bit |
| `__unsigned_idiv__(lhs rhs)` | Unsigned 64-bit division |
| `__unsigned_mod__(lhs rhs)` | Unsigned 64-bit remainder |
| `__unsigned_lt__(lhs rhs)` | Unsigned less-than comparison |
| `__unsigned_gt__(lhs rhs)` | Unsigned greater-than comparison |
| `__unsigned_lte__(lhs rhs)` | Unsigned less-than-or-equal comparison |
| `__unsigned_gte__(lhs rhs)` | Unsigned greater-than-or-equal comparison |

Use `__signed_shr__` when you need sign-preserving right shift. The `>>` operator always performs unsigned (logical) shift. Likewise, `//`, `%`, and relational operators remain signed by default; use the unsigned intrinsics when you need unsigned interpretation.

---

# Part 3: Well-Formedness and Divergence

This section documents all cases where udewy behavior can diverge from full Dewy. Writing well-formed udewy requires programmer diligence in these areas.

## 3.1 Type Mismatches (udewy compiles, Dewy rejects)

These patterns compile in udewy but would be rejected by full Dewy's type checker:

| Pattern | Issue |
|---------|-------|
| `if some_int { ... }` | Condition must be `bool` in Dewy |
| `let x:int = true + 5` | Arithmetic on booleans |
| `let p:int = arr + 8` | Pointer arithmetic without casts |
| `some_fn(arg1 arg2) transmute int` | Transmute on wrong type |

## 3.2 Semantic Differences (both compile, different behavior)

These patterns compile in both udewy and Dewy but may behave differently:

| Pattern | udewy Behavior | Dewy Behavior |
|---------|---------------|---------------|
| `x >> n` (x is signed) | Unsigned shift (zeros fill) | Signed shift (sign bit fills) |
| `a and b` / `a or b` | Both sides always evaluated | Short-circuit evaluation |
| `str1 =? str2` | Compares pointers | May compare content |
| Integer overflow | Wraps silently | May trap or wrap |

## 3.3 Programmer Diligence Required

To write well-formed udewy:

1. **Use `__signed_shr__`** when arithmetic shift is needed for signed values
2. **Avoid relying on short-circuit evaluation** - side effects in `and`/`or` operands will always occur
3. **Implement content comparison functions** for string/array equality
4. **Use unsigned intrinsics explicitly** when raw unsigned interpretation matters
5. **Use parentheses liberally** to make precedence explicit
6. **Test with increasing compiler strictness** as the Dewy compiler matures

---

# Part 4: Compilation Model

## 4.1 Overview

The udewy compiler is a **single-pass compiler** with:
1. Import preprocessing (recursive file inclusion)
2. Tokenization
3. Parsing with direct code emission
4. Backend-specific assembly/output generation

## 4.2 Import Processing

Before tokenization, leading import directives are processed:

1. Parse the leading import prelude at the beginning of the file
2. For each import, recursively process the imported file
3. Prepend imported content to the main source
4. Remove import directives from the source being compiled
5. Track imported files to prevent duplicate inclusion

## 4.3 Backend Architecture

udewy's compilation model is designed to be **modular with respect to target platforms**. A backend encapsulates all target-specific concerns:

- **Architecture:** CPU instruction set (x86_64, RISC-V, AArch64, WASM, etc.)
- **Operating System:** System call interface and conventions (Linux, Windows, macOS, bare metal, browser, etc.)
- **Output Format:** Executable format (ELF, PE, Mach-O, WASM, etc.)

### Parser / Backend Boundary

The parser (`p0.py`) is responsible for parsing udewy source and translating the result into calls on the abstract `Backend` interface. It should not contain target-specific logic or special-case knowledge about concrete backends.

Concrete backends are responsible for responding to those abstract operations in whatever way is appropriate for their target. They may differ in calling conventions, instruction selection, intrinsic support, output format, and runtime environment, but those differences should be expressed through the `Backend` protocol rather than through extra coupling with the parser.

In general, the parser and the concrete backends should only know about each other through what is described by `Backend` in `backend/common.py`. Changes to `Backend` should therefore be relatively rare and made only when they provide a clear architectural benefit, such as substantially simplifying the parser/backend relationship, removing complexity, or enabling an important capability that cleanly belongs in the shared abstraction.

udewy-native programs that do not rely on `extern` declarations use udewy's own entry point and do not require C runtime startup code. When `extern` declarations are used, the final link additionally depends on whatever artifacts are provided to satisfy those extern symbols.

### Backend Responsibilities

Each backend implements the parser protocol and provides:

1. **Code generation** - Emit target-specific instructions
2. **Calling convention** - How functions pass arguments and return values
3. **Platform intrinsics** - OS-specific operations (syscalls, host functions, etc.)
4. **Memory model** - Address space layout and constraints

### Intrinsic Categories

Intrinsics fall into two categories:

1. **Core intrinsics** - Implemented by all backends (memory operations, `__signed_shr__`, unsigned arithmetic/comparison intrinsics)
2. **Platform intrinsics** - Provided by specific backends for their target environment
3. **Builtin constants** - Backends can provide named constants automatically available to programs

For example:
- Linux backends provide `__syscall0__` through `__syscall6__` intrinsics, plus builtin constants for syscall numbers (`SYS_WRITE`, `SYS_EXIT`, etc.) and common flags
- The WASM browser backend provides `__host_log__`, `__host_time__`, etc. for browser interaction
- A hypothetical Windows backend would provide different intrinsics for Win32 API calls

### Builtin Constants

Linux backends automatically provide constants for:
- **Syscall numbers**: `SYS_READ`, `SYS_WRITE`, `SYS_OPEN`, `SYS_CLOSE`, `SYS_EXIT`, etc.
- **File descriptors**: `STDIN`, `STDOUT`, `STDERR`
- **Open flags**: `O_RDONLY`, `O_WRONLY`, `O_RDWR`, `O_CREAT`, `O_TRUNC`, `O_APPEND`
- **Memory mapping flags**: `PROT_READ`, `PROT_WRITE`, `PROT_EXEC`, `MAP_SHARED`, `MAP_PRIVATE`, `MAP_ANONYMOUS`

These constants are available without explicit declaration:

```udewy
# No need to declare SYS_WRITE - it's provided by the x86_64 backend
let msg = "Hello\n"
let len = __load__(msg - 8)
__syscall3__(SYS_WRITE STDOUT msg len)
```

Note: Syscall numbers differ between architectures. x86_64 uses the traditional Linux syscall numbers, while RISC-V and AArch64 use the newer unified syscall table (e.g., `SYS_OPENAT` instead of `SYS_OPEN`).

### Writing Portable Code

To write udewy programs that work across multiple backends:

1. Use only core intrinsics for direct operations
2. Create a **platform abstraction layer** - a set of wrapper functions that call the appropriate platform intrinsics
3. Import the correct platform module for your target

Example structure:
```
program.udewy          # main program using platform API
├── platform_api.udewy # abstract interface (print, alloc, exit, etc.)
├── platform_linux_x86_64.udewy  # Linux x86_64 implementation
├── platform_linux_riscv.udewy   # Linux RISC-V implementation
├── platform_wasm.udewy          # Browser WASM implementation
└── platform_windows.udewy       # (future) Windows implementation
```

## 4.4 Backend Selection

The target backend is selected at compile time via the `--target` flag:

```bash
python -m udewy.p0 --target <backend> program.udewy
```

Available backends are documented in the addendums. New backends can be added by implementing the backend protocol defined in `backend/common.py`.

## 4.5 Forward References

Unknown identifiers during parsing are assumed to be forward references to functions. At the end of compilation, all references must be resolved or an error is reported.

---

# Part 5: Formal Grammar

```
source_file     ::= import_directive* program

import_directive ::= 'import' path_string
path_string     ::= 'p' STRING

program         ::= top_level_stmt*

top_level_stmt  ::= fn_decl
                  | const_decl

fn_decl         ::= ('let' | 'const') IDENT '=' '(' param_list ')' fn_type_annot '=>' (block | 'extern')

const_decl      ::= ('let' | 'const') IDENT type_annot '=' (const_expr | 'extern')

param_list      ::= (IDENT type_annot)*

fn_type_annot   ::= ':>' IDENT type_param?
                  | ':>' type_param
type_annot      ::= ':' IDENT type_param?
                  | type_param
type_param      ::= '<' type_content '>'

block           ::= '{' statement* '}'

statement       ::= var_decl
                  | assign_stmt
                  | if_stmt
                  | loop_stmt
                  | 'break'
                  | 'continue'
                  | return_stmt
                  | expr

var_decl        ::= ('let' | 'const') IDENT type_annot '=' expr

assign_stmt     ::= IDENT '=' expr
                  | IDENT compound_op expr

compound_op     ::= '+=' | '-=' | '*=' | '//=' | '%=' 
                  | '<<=' | '>>=' | 'and=' | 'or=' | 'xor='

if_stmt         ::= 'if' expr block else_clause?
else_clause     ::= 'else' 'if' expr block else_clause?
                  | 'else' block

loop_stmt       ::= 'loop' expr block

return_stmt     ::= 'return' expr

expr            ::= prefix_expr (binop prefix_expr)* cast_annot?

prefix_expr     ::= '-' prefix_expr
                  | 'not' prefix_expr
                  | atom

atom            ::= NUMBER
                  | STRING
                  | 'true'
                  | 'false'
                  | 'void'
                  | IDENT
                  | IDENT '(' arg_list ')'
                  | '(' expr ')' ('(' arg_list ')')?
                  | '[' array_elem* ']'

arg_list        ::= expr*
array_elem      ::= NUMBER | STRING | IDENT  # IDENT must resolve to a compile-time stable value or function

cast_annot      ::= 'transmute' (IDENT type_param? | type_param)

binop           ::= '+' | '-' | '*' | '//' | '%'
                  | '<<' | '>>'
                  | '=?' | 'not=?' | '>?' | '<?' | '>=?' | '<=?'
                  | 'and' | 'or' | 'xor'
                  | '|>'

const_expr      ::= NUMBER | STRING | IDENT | '[' array_elem* ']'

# Lexical elements
IDENT           ::= [a-zA-Z_][a-zA-Z0-9_]*
NUMBER          ::= decimal | hex | binary
decimal         ::= [0-9][0-9_]*
hex             ::= '0x' [0-9a-fA-F_]+
binary          ::= '0b' [01_]+
STRING          ::= '"' string_char* '"'
string_char     ::= <any char except '"' or '\'>
                  | '\' <any char>
```

> NOTE: `import_directive` and `path_string` are consumed during preprocessing and do not appear in the token stream seen by the parser. The word `import` remains reserved, so any surviving `import` is rejected during tokenization.

---

# Part 6: Intentional Limitations

udewy deliberately omits features to keep the compiler simple and auditable:

- **No indexing syntax** (`arr[i]`): Would require type information to know element size
- **No value casts** (`as`): Would require type-aware conversion
- **No string interpolation**: Strings are simple byte sequences
- **No closures or nested functions**: Functions only at top level
- **No function overloading**: Each function name has exactly one definition
- **No short-circuit evaluation**: Both sides of `and`/`or` are always evaluated
- **No floating-point**: Everything is 64-bit integers
- **No garbage collection**: Manual memory management via syscalls

---

# Part 7: Examples

## Fibonacci

```udewy
let fib = (n:int):>int => {
    if n <? 2 {
        return n
    } else {
        return fib(n - 1) + fib(n - 2)
    }
}

let main = ():>int => {
    return fib(10)  # returns 55
}
```

## Memory Allocation with mmap

```udewy
# SYS_MMAP, PROT_*, MAP_* constants are provided by the x86_64 backend

let alloc = (size:int):>int => {
    return __syscall6__(SYS_MMAP 0 size (PROT_READ or PROT_WRITE) (MAP_PRIVATE or MAP_ANONYMOUS) (0 - 1) 0)
}

let main = ():>int => {
    let buffer:int = alloc(4096)
    __store__(42 buffer)
    return __load__(buffer)  # returns 42
}
```

---

# Backend Addendums

The following addendums document the currently implemented backends. Each backend targets a specific combination of:

- **Architecture** - The CPU instruction set
- **Operating System** - The system call interface and runtime environment

New backends can be added for other architecture/OS combinations by implementing the backend protocol. For example, future backends might include:
- x86_64 Windows (PE executables, Win32 API)
- x86_64 macOS (Mach-O executables, Darwin syscalls)
- AArch64 macOS (Apple Silicon)
- Bare metal / embedded targets
- Other browser runtimes (Node.js, Deno)

Each addendum specifies the platform intrinsics and conventions for that backend. Programs targeting multiple platforms should use a platform abstraction layer as described in [Section 4.3](#43-backend-architecture).

---

# Addendum A: x86_64 Linux Backend

## A.1 Target Description

- **Architecture:** x86_64 (AMD64)
- **Operating System:** Linux
- **Output Format:** ELF executable via GNU assembler
- **Calling Convention:** System V AMD64 ABI

## A.2 Calling Convention

| Purpose | Registers |
|---------|-----------|
| Arguments (1-6) | `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` |
| Return value | `rax` |
| Caller-saved | `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8`-`r11` |
| Callee-saved | `rbx`, `rbp`, `r12`-`r15` |

Additional arguments beyond 6 are passed on the stack.

## A.2.1 Codegen Notes

The x86_64 backend still follows udewy's logical value-stack model, but it does not map every `save_value()` directly to a machine `push`.

- The current visible expression result stays in `rax`.
- A small prefix of the logical saved-value stack is cached in callee-saved registers before falling back to spill slots on the real stack.
- When a call has more than 6 arguments, the extra arguments are written into an outbound stack-argument area and the first 6 are placed in `rdi`, `rsi`, `rdx`, `rcx`, `r8`, and `r9`.
- Call lowering also keeps the machine stack aligned to the ABI-required 16-byte boundary.

## A.2.2 `__alloca__` Alignment

- `__alloca__` returns an address aligned to 8 bytes.
- Successive small allocations therefore advance in 8-byte units on this backend.
- The backend still pads the machine stack as needed at call boundaries to satisfy the System V ABI.

## A.2.3 Mixed GP / FP Extern Intrinsics

The x86_64 backend supports mixed integer/pointer and floating-point extern calls through the intrinsic family:

```udewy
__call_extern_xmm_mixed_1__(fn type0 value0)
__call_extern_xmm_mixed_2__(fn type0 value0 type1 value1)
...
__call_extern_xmm_mixed_8__(fn type0 value0 ... type7 value7)
```

Rules:
- `fn` is an extern function reference
- each `typeN` must be a compile-time integer literal
- `0` means pass `valueN` through the normal integer/pointer calling convention
- `1` means treat the low 32 bits of `valueN` as raw `f32` bits and pass them in the next XMM argument register
- `2` means treat all 64 bits of `valueN` as raw `f64` bits and pass them in the next XMM argument register

This backend also provides:

```udewy
__i64_to_f32_bits__(value)
__i64_to_f64_bits__(value)
```

These convert a signed integer value into IEEE-754 `f32` / `f64` bit patterns, returned as ordinary udewy integers.

## A.3 Syscall Intrinsics

```udewy
__syscall0__(num)
__syscall1__(num arg1)
__syscall2__(num arg1 arg2)
__syscall3__(num arg1 arg2 arg3)
__syscall4__(num arg1 arg2 arg3 arg4)
__syscall5__(num arg1 arg2 arg3 arg4 arg5)
__syscall6__(num arg1 arg2 arg3 arg4 arg5 arg6)
```

Syscall convention:
- Syscall number in `rax`
- Arguments in `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`
- Return value in `rax`

## A.4 Builtin Constants

The x86_64 backend provides the following constants automatically (no declaration needed):

**Syscall Numbers:**
| Constant | Value | Description |
|----------|-------|-------------|
| `SYS_READ` | 0 | Read from file descriptor |
| `SYS_WRITE` | 1 | Write to file descriptor |
| `SYS_OPEN` | 2 | Open file |
| `SYS_CLOSE` | 3 | Close file descriptor |
| `SYS_STAT` | 4 | Get file status |
| `SYS_FSTAT` | 5 | Get file status by fd |
| `SYS_LSEEK` | 8 | Reposition file offset |
| `SYS_MMAP` | 9 | Map memory |
| `SYS_MUNMAP` | 11 | Unmap memory |
| `SYS_BRK` | 12 | Change data segment size |
| `SYS_IOCTL` | 16 | Device control |
| `SYS_PIPE` | 22 | Create pipe |
| `SYS_DUP` | 32 | Duplicate fd |
| `SYS_DUP2` | 33 | Duplicate fd to specific number |
| `SYS_GETPID` | 39 | Get process ID |
| `SYS_FORK` | 57 | Create child process |
| `SYS_EXECVE` | 59 | Execute program |
| `SYS_EXIT` | 60 | Exit process |
| `SYS_WAIT4` | 61 | Wait for process |
| `SYS_KILL` | 62 | Send signal |
| `SYS_GETCWD` | 79 | Get current directory |
| `SYS_CHDIR` | 80 | Change directory |
| `SYS_MKDIR` | 83 | Create directory |
| `SYS_RMDIR` | 84 | Remove directory |
| `SYS_CREAT` | 85 | Create file |
| `SYS_UNLINK` | 87 | Delete file |
| `SYS_GETUID` | 102 | Get user ID |
| `SYS_GETGID` | 104 | Get group ID |
| `SYS_GETEUID` | 107 | Get effective user ID |
| `SYS_GETEGID` | 108 | Get effective group ID |
| `SYS_CLOCK_GETTIME` | 228 | Get time |
| `SYS_EXIT_GROUP` | 231 | Exit all threads |

**File Descriptors:**
| Constant | Value |
|----------|-------|
| `STDIN` | 0 |
| `STDOUT` | 1 |
| `STDERR` | 2 |

**Open Flags:**
| Constant | Value |
|----------|-------|
| `O_RDONLY` | 0 |
| `O_WRONLY` | 1 |
| `O_RDWR` | 2 |
| `O_CREAT` | 64 |
| `O_TRUNC` | 512 |
| `O_APPEND` | 1024 |

**Memory Mapping:**
| Constant | Value |
|----------|-------|
| `PROT_NONE` | 0 |
| `PROT_READ` | 1 |
| `PROT_WRITE` | 2 |
| `PROT_EXEC` | 4 |
| `MAP_SHARED` | 1 |
| `MAP_PRIVATE` | 2 |
| `MAP_FIXED` | 16 |
| `MAP_ANONYMOUS` | 32 |

---

# Addendum B: RISC-V 64 Linux Backend

## B.1 Target Description

- **Architecture:** RISC-V 64-bit (RV64)
- **Operating System:** Linux
- **Output Format:** ELF executable
- **Calling Convention:** RISC-V LP64 ABI

## B.2 Calling Convention

| Purpose | Registers |
|---------|-----------|
| Arguments (1-8) | `a0`-`a7` |
| Return value | `a0` |
| Callee-saved | `s0`-`s11`, `ra` |
| Stack pointer | `sp` (16-byte aligned) |

Additional arguments beyond 8 are passed on the stack.

## B.2.1 Codegen Notes

The RISC-V backend uses the same basic strategy as x86_64: it preserves udewy's logical value-stack behavior, but keeps the shallow part of that stack in registers.

- The current visible expression result stays in `a0`.
- A small prefix of saved values is cached in callee-saved registers before deeper values spill to the real stack.
- Calls place the first 8 arguments in `a0`-`a7` and marshal any remaining arguments into an outbound stack area.
- Call lowering maintains the required 16-byte stack alignment at the actual call instruction.

## B.2.2 `__alloca__` Alignment

- `__alloca__` returns an address aligned to 16 bytes.
- Successive small allocations therefore advance in 16-byte units on this backend.
- This stronger alignment matches the backend's stack-alignment requirements.

## B.3 Syscall Intrinsics

Same syntax as x86_64:
```udewy
__syscall0__(num)
__syscall1__(num arg1)
# ... etc.
```

Syscall convention:
- Syscall number in `a7`
- Arguments in `a0`-`a5`
- Return value in `a0`

## B.4 Builtin Constants

The RISC-V backend provides constants automatically. RISC-V Linux uses the unified "new-style" syscall table.

**Syscall Numbers:**
| Constant | Value | Description |
|----------|-------|-------------|
| `SYS_GETCWD` | 17 | Get current directory |
| `SYS_DUP` | 23 | Duplicate fd |
| `SYS_DUP3` | 24 | Duplicate fd with flags |
| `SYS_IOCTL` | 29 | Device control |
| `SYS_MKDIRAT` | 34 | Create directory (relative) |
| `SYS_UNLINKAT` | 35 | Delete file (relative) |
| `SYS_FTRUNCATE` | 46 | Truncate file |
| `SYS_FACCESSAT` | 48 | Check file access |
| `SYS_CHDIR` | 49 | Change directory |
| `SYS_OPENAT` | 56 | Open file (relative) |
| `SYS_CLOSE` | 57 | Close fd |
| `SYS_PIPE2` | 59 | Create pipe |
| `SYS_LSEEK` | 62 | Seek in file |
| `SYS_READ` | 63 | Read from fd |
| `SYS_WRITE` | 64 | Write to fd |
| `SYS_FSTAT` | 80 | Get file status |
| `SYS_EXIT` | 93 | Exit process |
| `SYS_EXIT_GROUP` | 94 | Exit all threads |
| `SYS_KILL` | 129 | Send signal |
| `SYS_GETPID` | 172 | Get process ID |
| `SYS_GETUID` | 174 | Get user ID |
| `SYS_GETEUID` | 175 | Get effective user ID |
| `SYS_GETGID` | 176 | Get group ID |
| `SYS_GETEGID` | 177 | Get effective group ID |
| `SYS_BRK` | 214 | Change data segment size |
| `SYS_MUNMAP` | 215 | Unmap memory |
| `SYS_CLONE` | 220 | Create process |
| `SYS_EXECVE` | 221 | Execute program |
| `SYS_MMAP` | 222 | Map memory |
| `SYS_WAIT4` | 260 | Wait for process |

**Note:** RISC-V uses `*at` syscalls (e.g., `SYS_OPENAT` instead of `SYS_OPEN`). Use `AT_FDCWD` (-100) as the directory fd for current directory.

File descriptor, open flag, and mmap constants are the same as x86_64 (see Addendum A).

---

# Addendum C: AArch64 Linux Backend

## C.1 Target Description

- **Architecture:** AArch64 (ARM 64-bit)
- **Operating System:** Linux
- **Output Format:** ELF executable
- **Calling Convention:** AAPCS64

## C.2 Calling Convention

| Purpose | Registers |
|---------|-----------|
| Arguments (1-8) | `x0`-`x7` |
| Return value | `x0` |
| Callee-saved | `x19`-`x28`, `sp`, `fp` |
| Link register | `lr` (`x30`) |

Additional arguments beyond 8 are passed on the stack.

## C.2.1 Codegen Notes

The AArch64 backend also keeps the parser-visible stack model, but uses registers for the shallow saved-value stack instead of immediately spilling everything.

- The current visible expression result stays in `x0`.
- A small prefix of saved values is cached in callee-saved registers, with deeper values spilling to stack slots.
- Calls place the first 8 arguments in `x0`-`x7` and place overflow arguments in the outbound call stack area.
- Because AArch64 already requires 16-byte stack alignment and the backend spills in 16-byte slots, this path stays naturally aligned.

## C.2.2 `__alloca__` Alignment

- `__alloca__` returns an address aligned to 16 bytes.
- Successive small allocations therefore advance in 16-byte units on this backend.
- This stronger alignment matches the backend's stack-alignment requirements.

## C.2.3 Mixed GP / FP Extern Intrinsics

The AArch64 backend supports the same mixed extern intrinsic family as x86_64:

```udewy
__call_extern_xmm_mixed_1__(fn type0 value0)
__call_extern_xmm_mixed_2__(fn type0 value0 type1 value1)
...
__call_extern_xmm_mixed_8__(fn type0 value0 ... type7 value7)
```

Rules:
- `0` passes the value through the general-purpose argument registers `x0`-`x7`
- `1` treats the low 32 bits as raw `f32` bits and passes them in the next floating-point argument register
- `2` treats all 64 bits as raw `f64` bits and passes them in the next floating-point argument register

This backend also provides:

```udewy
__i64_to_f32_bits__(value)
__i64_to_f64_bits__(value)
```

These convert signed integers to `f32` / `f64` bit patterns while keeping udewy's runtime representation as integers.

## C.3 Syscall Intrinsics

Same syntax as x86_64. Invoked via `svc #0`.

Syscall convention:
- Syscall number in `x8`
- Arguments in `x0`-`x5`
- Return value in `x0`

## C.4 Builtin Constants

AArch64 Linux uses the same unified syscall table as RISC-V Linux. All builtin constants (syscall numbers, file descriptors, flags) are identical to RISC-V (see Addendum B).

---

# Addendum D: WASM32 Browser Backend

## D.1 Target Description

- **Architecture:** WebAssembly 32-bit
- **Environment:** Web browser
- **Output Format:** WAT (WebAssembly Text) converted to WASM, embedded in HTML
- **Memory Model:** Linear memory with imported JavaScript memory object

## D.2 Value Representation

- All udewy values are `i64` in WASM
- Memory addresses are `i64` but truncated to `i32` at every memory operation
- Strings and arrays use the same length-prefixed layout as native backends

## D.2.1 `__alloca__` Alignment

- `__alloca__` returns an address aligned to 8 bytes.
- Successive small allocations therefore advance in 8-byte units on this backend.
- Because wasm uses a linear-memory bump pointer rather than a native ABI stack, it does not need the stronger 16-byte rule used by some native backends.

## D.3 Host Function Intrinsics

Instead of syscalls, the WASM backend provides browser-focused host functions:

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__host_log__(ptr len)` | 2 | Output text to browser console |
| `__host_exit__(code)` | 1 | Signal program exit |
| `__host_time__()` | 0 | Current timestamp in milliseconds |
| `__host_random__()` | 0 | Random 64-bit integer |

> These are subject to change

## D.4 DOM Intrinsics

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__dom_set_text__(ptr len)` | 2 | Set output element text content |
| `__dom_append__(ptr len)` | 2 | Append text to output element |
| `__dom_clear__()` | 0 | Clear output element |
| `__dom_append_int__(value)` | 1 | Append integer as text |
| `__log_int__(value)` | 1 | Log integer to console |

## D.5 Canvas Graphics Intrinsics

The WASM backend provides intrinsics for canvas-based graphics with animation support:

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__canvas_init__(width height)` | 2 | Initialize canvas and return RGBA pixel buffer pointer |
| `__canvas_width__()` | 0 | Get current canvas width |
| `__canvas_height__()` | 0 | Get current canvas height |
| `__canvas_present__()` | 0 | Copy pixel buffer to canvas (display frame) |
| `__canvas_set_aspect_lock__(enabled)` | 1 | Enable or disable aspect-ratio locking using a udewy `bool` |
| `__frame_count__()` | 0 | Get current animation frame number |
| `__frame_time__()` | 0 | Get milliseconds since canvas initialization |
| `__window_width__()` | 0 | Get browser window inner width |
| `__window_height__()` | 0 | Get browser window inner height |

**Usage:**

1. Call `__canvas_init__(width height)` to create a canvas and get a pointer to the pixel buffer
2. Optionally call `__canvas_set_aspect_lock__(true)` to keep the displayed canvas centered at its current aspect ratio as the browser window resizes
3. Call `__canvas_set_aspect_lock__(false)` later if you want to return to unrestricted fullscreen scaling
4. Write RGBA pixels (4 bytes per pixel) to the buffer: `[R, G, B, A, R, G, B, A, ...]`
5. Call `__canvas_present__()` to display the frame
6. The runtime automatically calls `main()` each animation frame when canvas mode is active

`__canvas_set_aspect_lock__(enabled)` expects a udewy boolean value, normally passed as the `true` or `false` literals. Internally, any non-zero value enables the lock and `0` disables it.

When aspect lock is enabled, the runtime uses the canvas's current backing dimensions, typically the `width` and `height` passed to `__canvas_init__()`, as the aspect ratio to preserve.

**Example:**

```udewy
let buffer:int = 0
let width:int = 320
let height:int = 240

let set_pixel = (x:int y:int r:int g:int b:int):>int => {
    let offset:int = ((y * width) + x) * 4
    let addr:int = buffer + offset
    __store_u8__(r addr)
    __store_u8__(g addr + 1)
    __store_u8__(b addr + 2)
    __store_u8__(255 addr + 3)
    return 0
}

let main = ():>int => {
    buffer = __canvas_init__(width height)
    let t:int = __frame_time__()
    
    # Draw something based on time...
    
    __canvas_present__()
    return 0
}
```

## D.6 Pointer Input Intrinsics

The WASM backend exposes basic pointer state for browser-interactive programs:

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__pointer_x__()` | 0 | Get the current pointer x coordinate in canvas pixels |
| `__pointer_y__()` | 0 | Get the current pointer y coordinate in canvas pixels |
| `__pointer_down__()` | 0 | Get whether the primary pointer button is currently down |

When a canvas or WebGL surface is active, coordinates are reported relative to that surface and scaled to its backing pixel resolution.

## D.7 Keyboard Input Intrinsics

The WASM backend also exposes keyboard state using browser `KeyboardEvent.code` strings such as `ArrowLeft`, `ArrowRight`, `KeyW`, and `Space`:

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__key_down__(code_ptr code_len)` | 2 | Get whether a key is currently held down |
| `__key_pressed__(code_ptr code_len)` | 2 | Get whether a key transitioned from up to down since the last animation frame |
| `__key_released__(code_ptr code_len)` | 2 | Get whether a key transitioned from down to up since the last animation frame |

These intrinsics are intended for animated WASM programs running under canvas or WebGL, where `main()` is called once per frame.

## D.8 WebGL Shader Intrinsics

The WASM backend also provides a minimal WebGL path for fullscreen fragment shader demos driven by udewy strings and integer uniforms:

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__webgl_init__(shader_ptr shader_len width height)` | 4 | Compile a fragment shader string and initialize a fullscreen WebGL canvas |
| `__webgl_uniform1i__(name_ptr name_len value)` | 3 | Set an `int` uniform on the active shader program |
| `__webgl_uniform2i__(name_ptr name_len x y)` | 4 | Set an `ivec2` uniform on the active shader program |
| `__webgl_uniform1iv__(name_ptr name_len values_ptr count)` | 4 | Set an `int[count]` uniform array from udewy memory |
| `__webgl_uniform2iv__(name_ptr name_len values_ptr count)` | 4 | Set an `ivec2[count]` uniform array from udewy memory |
| `__webgl_render__()` | 0 | Draw the active fullscreen shader |

**Usage:**

1. Store your fragment shader source as a normal udewy string
2. Use `__load__(shader - 8)` to recover its byte length
3. Call `__webgl_init__(shader shader_len width height)` once
4. Update uniforms each frame with `__webgl_uniform1i__`, `__webgl_uniform2i__`, `__webgl_uniform1iv__`, or `__webgl_uniform2iv__`
5. Call `__webgl_render__()` to draw

The runtime provides a built-in passthrough vertex shader with an `a_position` attribute, so user programs only need to supply fragment shader code.

## D.9 Build Options

```bash
# Default: single HTML file with embedded base64 WASM
python -m udewy.p0 -c --target wasm32 program.udewy

# Run the embedded HTML directly in your browser
python -m udewy.p0 --target wasm32 program.udewy

# Serve over HTTP instead of opening file:// directly
python -m udewy.p0 --target wasm32 --serve-wasm program.udewy

# Split mode: separate .wasm file (served automatically when run)
python -m udewy.p0 -c --target wasm32 --split-wasm program.udewy
python -m udewy.p0 --target wasm32 --split-wasm program.udewy
```

When served with `--serve-wasm` or `--split-wasm`, the local server exits automatically after the browser tab closes.

---

# Addendum E: External Libraries

This addendum documents the external native libraries currently supported by the repository's checked-in helper code and setup scripts.

## E.1 SDL

The SDL integration lives under `udewy/third_party/sdl/`.

**Current backend support:**

- Supported today: `x86_64` Linux
- Not currently supported by this SDL setup: `riscv`, `arm`, `wasm32`

The current SDL bundle is built locally by `udewy/third_party/sdl/setup_sdl.py` for the host Linux machine and stages host-native artifacts into `udewy/third_party/sdl/artifacts/`. Because those artifacts are native link inputs for the current machine, they are only wired up for the x86_64 Linux backend in the current repository workflow.

### E.1.1 Using SDL

Get started like this:

```bash
# Build the local SDL bundle and generate the default udewy icon module
python udewy/third_party/sdl/setup_sdl.py

# Generate a custom icon module next to your source image
# This writes my_icon.udewy and exports the default symbol MY_ICON
python udewy/third_party/sdl/generate_udewy_icon.py my_icon.png
```

Import the SDL wrapper from your udewy program:

```udewy
import p"../third_party/sdl/sdl.udewy"
```

The wrapper provides the low-level SDL extern declarations together with a few convenience helpers written in udewy, including `SDL_SetWindowIconFromUdewyData(window icon_data)` and `SDL_SetDefaultWindowIcon(window)`.

### E.1.2 Generated Icon Modules

The SDL helper can load packed icon data from a generated `.udewy` module without adding any new language semantics.

By default, `generate_udewy_icon.py` writes the generated module using the input filename with a `.udewy` extension and exports a symbol matching that filename stem in uppercase. For example:

```bash
python udewy/third_party/sdl/generate_udewy_icon.py my_icon.png
# writes my_icon.udewy
# exports MY_ICON
```

Use `--symbol` if you want to override the exported symbol name, or pass an explicit output path if you want the generated `.udewy` file somewhere else.

The generated module exports one `array<uint64>` symbol. Its layout is:

- word 0: icon magic
- word 1: format/version word
- word 2: width
- word 3: height
- word 4: packed-word count
- words 5+: packed pixels, two pixels per `uint64`, written as `0xRRGGBBAA_RRGGBBAA`

The generator writes eight packed words per line for readability, but the runtime format is just a normal udewy array literal.

Use a generated icon module from SDL code like this:

```udewy
import p"../third_party/sdl/sdl.udewy"
import p"./my_icon.udewy"

let main = ():>int => {
    let title:int = "icon demo\0"
    let window:int = SDL_CreateWindow(title 640 480 SDL_WINDOW_RESIZABLE)
    SDL_SetWindowIconFromUdewyData(window MY_ICON)
    # ...
}
```

`sdl.udewy` also imports a generated default icon module and exposes it as `SDL_DEFAULT_WINDOW_ICON_DATA`. Programs that want the bundled logo can call `SDL_SetWindowIconFromUdewyData(window SDL_DEFAULT_WINDOW_ICON_DATA)` or `SDL_SetDefaultWindowIcon(window)`.

On Linux desktops, successful `SDL_SetWindowIcon` calls do not guarantee that the dock or launcher will show the new icon. This repository's SDL setup is Wayland-first, and compositor support still determines whether runtime icon changes appear in task switchers or docks.

For the `python -m udewy path/to/program.udewy` workflow on GNOME/Wayland, udewy also prepares a desktop-entry fallback:

- the desktop file is written directly to `~/.local/share/applications/<app_id>.desktop`
- the basename before `.desktop` must match the SDL app ID
- the `Icon=` entry points at an absolute PNG path
- udewy sets `SDL_APP_ID` before launching the compiled binary so GNOME can match the running window to that desktop entry

---

# Misc
## Pronunciation

The name can be pronounced several ways depending on how you read the Greek letter μ (mu):

| Reading      | Pronunciation  | IPA              |
|--------------|----------------|------------------|
| μ as "micro" | MY-kroh dew-ee | /ˌmaɪkroʊ ˈduːi/ |
| μ as "mu"    | MYOO dew-ee    | /mjuː ˈduːi/     |
| μ as "u"     | YOO dew-ee     | /juː ˈduːi/      |

All are equally correct.

---

# Files

- `p0.py` - Parser
- `t0.py` - Tokenizer
- `backend/` - Target-specific code generators
  - `x86_64.py` - x86_64 Linux
  - `riscv.py` - RISC-V 64 Linux
  - `arm.py` - AArch64 Linux
  - `wasm.py` - WebAssembly browser
  - `common.py` - Backend protocol definition
- `tests/` - Test programs
- `bootstrap/` - Self-hosted compiler modules
