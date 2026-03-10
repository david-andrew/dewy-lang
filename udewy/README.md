<p align="center">
  <img src="https://raw.githubusercontent.com/david-andrew/dewy-lang/master/assets/udewy_logo_128x128.png" alt="Dewy logo" />
</p>


# The μDewy Subset Programming Language

udewy (μdewy, "micro-dewy") is a strict subset of the Dewy programming language, designed for bootstrapping. It serves as an intermediate step in a trusted computing base, providing a language simple enough to implement in assembly while being expressive enough to write a real compiler.

**Key principle**: Any valid udewy program should compile and behave identically under both the udewy compiler and the full Dewy compiler.

This document serves as the **definitive specification** for the udewy language. There is no implementation-defined behavior; all semantics are fully specified here.

## Quick Start

```bash
# Run a udewy program (default x86_64 target)
python -m udewy.p0 udewy/tests/test_hello.udewy

# Compile only (don't run)
python -m udewy.p0 -c udewy/tests/test_hello.udewy

# Target a different backend
python -m udewy.p0 --target wasm32 udewy/tests/test_hello.udewy
python -m udewy.p0 --target riscv udewy/tests/test_hello.udewy
python -m udewy.p0 --target arm udewy/tests/test_hello.udewy
```

The compiler produces artifacts in `__dewycache__/`.

### Supported Targets

| Target | Output | Requirements |
|--------|--------|--------------|
| `x86_64` (default) | Linux ELF executable | GNU as, ld |
| `wasm32` | Single HTML with embedded WASM | wat2wasm (wabt) |
| `riscv` | RISC-V 64-bit executable | riscv64-linux-gnu toolchain, qemu-riscv64 |
| `arm` | AArch64 executable | aarch64-linux-gnu toolchain, qemu-aarch64 |

### Hello World

```udewy
const SYS_WRITE:int = 1
const STDOUT:int = 1

let main = ():>int => {
    let msg:int = "Hello from udewy!\n"
    let len:int = __load64__(msg - 8)
    __syscall3__(SYS_WRITE STDOUT msg len)
    return 0
}
```

---

# Part 1: Core Language Specification

## 1.1 Lexical Structure

### Character Set

udewy source files are encoded in ASCII. UTF-8 is compatible in contexts where extended characters are allowed (string literals).

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
import  transmute  and  or  xor  not  true  false  void
```

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
let long:int = "This is a very \
long string that appears \
on one line"
```

**Memory layout:** String literals are stored in static memory with an 8-byte length prefix. The variable holds a pointer to the first character (after the length). See [Memory Layout](#15-memory-layout).

### Path Literals

Path literals use the `p"..."` syntax and behave identically to regular strings but signal that the content represents a file path:

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
let ptr:array<int> = some_array
```

**Parameterized types** (`:type<param>` or `<param>` alone):
```udewy
let arr:array<int> = [1 2 3]
let mixed<int|string> = value    # type param without colon
```

The content inside `<>` is parsed but not validated. This allows complex type expressions that udewy couldn't otherwise parse:
```udewy
let x<int|undefined> = 10  # type param alone, no colon before <>
```

**Function return type** (`:>type` or `:> <param>`):
```udewy
let add = (a:int b:int):>int => { return a + b }
let get_value = ():>result<int> => { ... }
let flexible = ():> <A|B|C> => { ... }  # complex return type
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
- Identifiers referencing constants or functions

Array literals are stored in static memory with an 8-byte length prefix. See [Memory Layout](#15-memory-layout).

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

`let` and `const` are **semantically identical**—there is no enforcement of immutability. Use `const` to document values that should not change.

### Assignment

Simple assignment:
```udewy
x = 42
```

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

### Import

Import statements bring definitions from other udewy files into scope:

```udewy
import p"utils.udewy"
import p"lib/helpers.udewy"
```

**Semantics:**
- Paths are relative to the importing file's directory
- Imports are processed recursively (imported files can import other files)
- Each file is only included once (circular imports are handled by tracking what's been imported)
- Imported content is prepended to the source

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

let len:int = __load64__(arr - 8)      # 3
let first:int = __load64__(arr)        # 10
let second:int = __load64__(arr + 8)   # 20
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

__store64__(name_ptr person + PERSON_NAME)
__store64__(25 person + PERSON_AGE)
__store64__(180 person + PERSON_HEIGHT)

let age:int = __load64__(person + PERSON_AGE)
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
| `__load8__(addr)` | Load byte from `addr`, zero-extend to 64-bit |
| `__load16__(addr)` | Load 16-bit value from `addr`, zero-extend to 64-bit |
| `__load32__(addr)` | Load 32-bit value from `addr`, zero-extend to 64-bit |
| `__load64__(addr)` | Load 64-bit value from `addr` |
| `__store8__(val, addr)` | Store low 8 bits of `val` to `addr`, return 0 |
| `__store16__(val, addr)` | Store low 16 bits of `val` to `addr`, return 0 |
| `__store32__(val, addr)` | Store low 32 bits of `val` to `addr`, return 0 |
| `__store64__(val, addr)` | Store 64-bit `val` to `addr`, return 0 |

**Note:** All loads zero-extend (not sign-extend) to 64 bits.

## 2.2 Arithmetic Operations

| Intrinsic | Description |
|-----------|-------------|
| `__signed_shr__(val, bits)` | Arithmetic (signed) right shift; fills vacated bits with the sign bit |

Use `__signed_shr__` when you need sign-preserving right shift. The `>>` operator always performs unsigned (logical) shift.

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
4. **Track signedness manually** for relational comparisons
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

Before parsing, import statements are processed:

1. Parse import statements at the beginning of the file
2. For each import, recursively process the imported file
3. Prepend imported content to the main source
4. Track imported files to prevent duplicate inclusion

## 4.3 Backend Architecture

udewy's compilation model is designed to be **modular with respect to target platforms**. A backend encapsulates all target-specific concerns:

- **Architecture:** CPU instruction set (x86_64, RISC-V, AArch64, WASM, etc.)
- **Operating System:** System call interface and conventions (Linux, Windows, macOS, bare metal, browser, etc.)
- **Output Format:** Executable format (ELF, PE, Mach-O, WASM, etc.)

### Backend Responsibilities

Each backend implements the parser protocol and provides:

1. **Code generation** - Emit target-specific instructions
2. **Calling convention** - How functions pass arguments and return values
3. **Platform intrinsics** - OS-specific operations (syscalls, host functions, etc.)
4. **Memory model** - Address space layout and constraints

### Intrinsic Categories

Intrinsics fall into two categories:

1. **Core intrinsics** - Implemented by all backends (memory operations, `__signed_shr__`)
2. **Platform intrinsics** - Provided by specific backends for their target environment

For example:
- Linux backends provide `__syscall0__` through `__syscall6__`
- The WASM browser backend provides `__host_log__`, `__host_time__`, etc.
- A hypothetical Windows backend would provide different intrinsics for Win32 API calls

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
program         ::= top_level_stmt*

top_level_stmt  ::= import_stmt
                  | fn_decl
                  | const_decl

import_stmt     ::= 'import' path_string

fn_decl         ::= ('let' | 'const') IDENT '=' '(' param_list ')' fn_type_annot '=>' block

const_decl      ::= ('let' | 'const') IDENT type_annot '=' const_expr

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
array_elem      ::= NUMBER | STRING | IDENT

cast_annot      ::= 'transmute' (IDENT type_param? | type_param)

binop           ::= '+' | '-' | '*' | '//' | '%'
                  | '<<' | '>>'
                  | '=?' | 'not=?' | '>?' | '<?' | '>=?' | '<=?'
                  | 'and' | 'or' | 'xor'
                  | '|>'

const_expr      ::= NUMBER | STRING | '[' array_elem* ']'

# Lexical elements
IDENT           ::= [a-zA-Z_][a-zA-Z0-9_]*
NUMBER          ::= decimal | hex | binary
decimal         ::= [0-9][0-9_]*
hex             ::= '0x' [0-9a-fA-F_]+
binary          ::= '0b' [01_]+
STRING          ::= '"' string_char* '"'
path_string     ::= 'p' STRING
string_char     ::= <any char except '"' or '\'>
                  | '\' <any char>
```

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
const SYS_MMAP:int = 9
const PROT_READ:int = 1
const PROT_WRITE:int = 2
const MAP_PRIVATE:int = 2
const MAP_ANONYMOUS:int = 32

let alloc = (size:int):>int => {
    return __syscall6__(SYS_MMAP 0 size (PROT_READ or PROT_WRITE) (MAP_PRIVATE or MAP_ANONYMOUS) (0 - 1) 0)
}

let main = ():>int => {
    let buffer:int = alloc(4096)
    __store64__(42 buffer)
    return __load64__(buffer)  # returns 42
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

## A.3 Syscall Intrinsics

```udewy
__syscall0__(num)
__syscall1__(num, arg1)
__syscall2__(num, arg1, arg2)
__syscall3__(num, arg1, arg2, arg3)
__syscall4__(num, arg1, arg2, arg3, arg4)
__syscall5__(num, arg1, arg2, arg3, arg4, arg5)
__syscall6__(num, arg1, arg2, arg3, arg4, arg5, arg6)
```

Syscall convention:
- Syscall number in `rax`
- Arguments in `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`
- Return value in `rax`

## A.4 Common Syscall Numbers (x86_64 Linux)

```udewy
const SYS_READ:int = 0
const SYS_WRITE:int = 1
const SYS_OPEN:int = 2
const SYS_CLOSE:int = 3
const SYS_STAT:int = 4
const SYS_FSTAT:int = 5
const SYS_LSEEK:int = 8
const SYS_MMAP:int = 9
const SYS_MUNMAP:int = 11
const SYS_BRK:int = 12
const SYS_EXIT:int = 60
const SYS_EXIT_GROUP:int = 231
```

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

## B.3 Syscall Intrinsics

Same syntax as x86_64:
```udewy
__syscall0__(num)
__syscall1__(num, arg1)
# ... etc.
```

Syscall convention:
- Syscall number in `a7`
- Arguments in `a0`-`a5`
- Return value in `a0`

## B.4 Common Syscall Numbers (RISC-V Linux)

```udewy
const SYS_READ:int = 63
const SYS_WRITE:int = 64
const SYS_OPENAT:int = 56
const SYS_CLOSE:int = 57
const SYS_MMAP:int = 222
const SYS_EXIT:int = 93
const SYS_EXIT_GROUP:int = 94
```

**Note:** RISC-V Linux uses different syscall numbers than x86_64. Programs using syscalls must use the correct constants for the target architecture.

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

## C.3 Syscall Intrinsics

Same syntax as x86_64. Invoked via `svc #0`.

Syscall convention:
- Syscall number in `x8`
- Arguments in `x0`-`x5`
- Return value in `x0`

## C.4 Common Syscall Numbers (AArch64 Linux)

```udewy
const SYS_READ:int = 63
const SYS_WRITE:int = 64
const SYS_OPENAT:int = 56
const SYS_CLOSE:int = 57
const SYS_MMAP:int = 222
const SYS_EXIT:int = 93
const SYS_EXIT_GROUP:int = 94
```

**Note:** AArch64 Linux syscall numbers are the same as RISC-V Linux.

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

## D.3 Host Function Intrinsics

Instead of syscalls, the WASM backend provides browser-focused host functions:

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__host_log__(ptr, len)` | 2 | Output text to browser console |
| `__host_exit__(code)` | 1 | Signal program exit |
| `__host_time__()` | 0 | Current timestamp in milliseconds |
| `__host_random__()` | 0 | Random 64-bit integer |

> These are subject to change

## D.4 DOM Intrinsics

| Intrinsic | Args | Description |
|-----------|------|-------------|
| `__dom_set_text__(ptr, len)` | 2 | Set output element text content |
| `__dom_append__(ptr, len)` | 2 | Append text to output element |
| `__dom_clear__()` | 0 | Clear output element |
| `__dom_append_int__(value)` | 1 | Append integer as text |
| `__log_int__(value)` | 1 | Log integer to console |

> These are subject to change

## D.5 Build Options

```bash
# Default: single HTML file with embedded base64 WASM
python -m udewy.p0 -c --target wasm32 program.udewy

# Split mode: separate .wasm file (requires HTTP server)
python -m udewy.p0 -c --target wasm32 --split-wasm program.udewy
```

---

# Pronunciation

The name can be pronounced several ways depending on how you read the Greek letter μ (mu):

| Pronunciation | IPA | Reading |
|---------------|-----|---------|
| MY-kroh dew-ee | /ˌmaɪkroʊ ˈduːi/ | μ as "micro" |
| MYOO dew-ee | /mjuː ˈduːi/ | μ as "mu" |
| YOO dew-ee | /juː ˈduːi/ | μ as "u" |

All are equally correct.

---

# Files

- `p0.py` - Parser and code generator
- `t0.py` - Tokenizer
- `backend/` - Target-specific code generators
  - `x86_64.py` - x86_64 Linux
  - `riscv.py` - RISC-V 64 Linux
  - `arm.py` - AArch64 Linux
  - `wasm.py` - WebAssembly browser
  - `common.py` - Backend protocol definition
- `tests/` - Test programs
- `bootstrap/` - Self-hosted compiler modules
