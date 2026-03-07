<p align="center">
  <img src="https://raw.githubusercontent.com/david-andrew/dewy-lang/master/assets/udewy_logo_128x128.png" alt="Dewy logo" />
</p>


# The μDewy Subset Programming Language

udewy (μdewy, /mjuː ˈduːi/) is a strict subset of the Dewy programming language, designed for bootstrapping. It serves as an intermediate step in a trusted computing base, providing a language simple enough to implement in assembly while being expressive enough to write a real compiler.

**Key principle**: Any valid udewy program should compile and behave identically under both the udewy compiler and the full Dewy compiler.

## Quick Start

```bash
# Run a udewy program
python -m udewy.p0 udewy/tests/test_hello.udewy

# Compile only (don't run)
python -m udewy.p0 -c udewy/tests/test_hello.udewy

# Select a backend explicitly
python -m udewy.p0 --backend x86_64 udewy/tests/test_hello.udewy
python -m udewy.p0 --backend wasm32 -c udewy/tests/test_hello.udewy
```

The compiler always writes build artifacts into `__dewycache__/`. In normal mode it then runs the produced artifact with the remaining arguments, so it behaves like an interpreter front-end.

Current backends:
- `x86_64` - builds and runs Linux x86_64 executables
- `wasm32` - generates browser-hosted wasm artifacts and a JS launcher
- `riscv` - generates RISC-V assembly, and will assemble/run if the matching cross tools are installed
- `arm` - generates AArch64 assembly, and will assemble/run if the matching cross tools are installed

For `wasm32`, compile-only mode produces `__dewycache__/NAME.html`, `NAME.js`, `NAME.wat`, and `NAME.wasm`. Run mode starts a simple HTTP server rooted at the directory where `udewy` was invoked and opens the generated launcher in the browser.

## Language Overview

udewy treats **everything as 64-bit integers**. Pointers, booleans, characters—all are integers under the hood. There is no type checking at runtime; type annotations exist only to maintain compatibility with full Dewy and to guide parsing.

### Hello World

```udewy
const SYS_WRITE:int = 1
const STDOUT:int = 1

let main = ():>int => {
    let msg:int = "Hello from udewy!\n"
    let len:int = __load__(msg - 8)  # length prefix
    __syscall3__(SYS_WRITE STDOUT msg len)
    return 0
}
```

## Syntax Reference

### Comments

Only line comments are supported:

```udewy
# This is a comment
let x:int = 42  # inline comment
```

### Variables

Variables must be declared with `let` or `const` and require an initializer:

```udewy
let x:int = 42
const BUFFER_SIZE:int = 1024
```

`let` and `const` are semantically identical—there is no enforcement of immutability. Use `const` for documentation purposes.

### Type Annotations

Type annotations follow identifiers with a colon. They are **not checked** but must be present for parsing:

```udewy
let x:int = 10
let ptr:array<int> = some_array
let flag:bool = true
```

Type parameters use angle brackets: `<T>`, `<int|string>`, etc.

### Functions

Functions are declared using lambda syntax assigned to a variable:

```udewy
let add = (a:int b:int):>int => {
    return a + b
}

let greet = ():>void => {
    # ... do something
    return void
}
```

- Parameters are space-separated (no commas)
- Return type annotation uses `:>` syntax
- All functions must explicitly `return` (use `return void` for no return value)
- Functions may only be declared at the top level

#### Function Calls

```udewy
# Named call
result = add(1 2)

# Pipe operator
result = x |> double |> add_one

# Expression call (call result of expression)
let fn_ptr:int = get_handler()
(fn_ptr)(arg1 arg2)
```

### Operators

#### Arithmetic
| Operator | Description |
|----------|-------------|
| `+` | Addition |
| `-` | Subtraction |
| `*` | Multiplication |
| `//` | Integer division |
| `%` | Modulo |

Prefix unary operators bind to expressions:

```udewy
let x:int = -(a + b)
let y:int = not flags
```

#### Comparison (return `true` or `false`)
| Operator | Description |
|----------|-------------|
| `=?` | Equal |
| `not=?` | Not equal |
| `>?` | Greater than |
| `<?` | Less than |
| `>=?` | Greater or equal |
| `<=?` | Less or equal |

#### Bitwise / Logical
| Operator | Description |
|----------|-------------|
| `and` | Bitwise AND (also logical) |
| `or` | Bitwise OR (also logical) |
| `xor` | Bitwise XOR |
| `not` | Bitwise NOT |
| `<<` | Left shift |
| `>>` | Arithmetic right shift |

#### Other
| Operator | Description |
|----------|-------------|
| `\|>` | Pipe (pass left side as first argument to right side) |

#### Precedence

Expressions are parsed **left-to-right**. If a higher-precedence operator follows a lower-precedence one without parentheses, the compiler will error. Use parentheses to clarify:

```udewy
# Error: precedence violation
let bad:int = a + b * c

# OK: explicit grouping
let ok:int = a + (b * c)

# OK: same precedence, left-to-right
let also_ok:int = a + b + c
```

Precedence levels (highest to lowest):
1. `*`, `//`, `%`
2. `+`, `-`
3. `<<`, `>>`
4. `>?`, `<?`, `>=?`, `<=?`
5. `=?`, `not=?`
6. `and`
7. `xor`
8. `or`
9. `|>`

#### Compound Assignment

```udewy
x += 1
x -= 2
x *= 3
x //= 4
x %= 5
x <<= 1
x >>= 1
x and= mask
x or= flags
x xor= bits
```

### Control Flow

#### If / Else

```udewy
if condition {
    # ...
} else if other_condition {
    # ...
} else {
    # ...
}
```

Conditions check if **any bit is set** (non-zero = true, zero = false).

#### Loop

udewy has a single loop construct that loops while a condition is true:

```udewy
let i:int = 0
loop i <? 10 {
    # ...
    i = i + 1
}
```

Use `break` and `continue` as expected:

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

### Literals

#### Numbers

```udewy
let decimal:int = 42
let hex:int = 0xFF
let binary:int = 0b1010
let with_underscores:int = 1_000_000
```

#### Booleans

```udewy
let t:int = true   # 0xFFFF_FFFF_FFFF_FFFF (all bits set)
let f:int = false  # 0x0000_0000_0000_0000 (no bits set)
```

This representation allows `and`/`or` to work correctly as both bitwise and logical operators.

#### Strings

Strings are pointers to data with a length prefix:

```udewy
let msg:int = "Hello\n"
let len:int = __load__(msg - 8)  # get length
let first_char:int = __load8__(msg)  # get first byte
```

Escape sequences: `\n`, `\t`, `\r`, `\\`, `\"`, `\0`

Line continuation with `\` at end of line:

```udewy
let long:int = "This is a very \
long string that spans \
multiple lines"
```

#### Arrays

Array literals create static data with a length prefix:

```udewy
let nums = [1 2 3 4 5]
let len:int = __load__(nums - 8)  # 5
let third:int = __load__(nums + (2 * 8))  # 3
```

Arrays can contain numbers, strings, const identifiers, or function references:

```udewy
let handlers = [on_start on_update on_stop]
let messages = ["error" "warning" "info"]
```

### Type Casts (transmute)

The `transmute` keyword is a no-op in udewy but exists for Dewy compatibility:

```udewy
let ptr:int = some_address transmute int
let arr:int = buffer transmute array<byte>
```

`transmute` preserves the underlying bits while changing the type annotation. It allows udewy code that manipulates raw integers to be valid in the strictly-typed full Dewy.

## Intrinsics

udewy provides low-level intrinsics for memory access and system calls:

### Memory Operations

```udewy
# 64-bit load/store
let val:int = __load__(address)
__store__(value address)

# 8-bit load/store
let byte:int = __load8__(address)
__store8__(byte_value address)

# 16-bit load/store
let word:int = __load16__(address)
__store16__(word_value address)

# 32-bit load/store
let dword:int = __load32__(address)
__store32__(dword_value address)
```

`__load8__`, `__load16__`, and `__load32__` zero-extend their results to 64 bits.

### System Calls

```udewy
__syscall0__(syscall_num)
__syscall1__(syscall_num arg1)
__syscall2__(syscall_num arg1 arg2)
__syscall3__(syscall_num arg1 arg2 arg3)
__syscall4__(syscall_num arg1 arg2 arg3 arg4)
__syscall5__(syscall_num arg1 arg2 arg3 arg4 arg5)
__syscall6__(syscall_num arg1 arg2 arg3 arg4 arg5 arg6)
```

On native backends these lower to the target platform's syscall path. On `wasm32`, they lower to imported JavaScript host functions instead of Linux syscalls.

Common syscall numbers (Linux x86_64):

```udewy
const SYS_READ:int = 0
const SYS_WRITE:int = 1
const SYS_OPEN:int = 2
const SYS_CLOSE:int = 3
const SYS_MMAP:int = 9
const SYS_EXIT:int = 60
```

## Memory Layout

### Strings and Arrays

Both strings and arrays have the same layout:
- 8 bytes: length (number of elements)
- N bytes: data

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

### Simulating Structs

udewy doesn't have structs. Instead, use offset constants:

```udewy
# Define "struct" layout
const PERSON_NAME:int = 0
const PERSON_AGE:int = 8
const PERSON_HEIGHT:int = 16
const PERSON_SIZE:int = 24

# Allocate
let person:int = alloc(PERSON_SIZE)

# Access fields
__store__(name_ptr person + PERSON_NAME)
__store__(25 person + PERSON_AGE)
__store__(180 person + PERSON_HEIGHT)

let age:int = __load__(person + PERSON_AGE)
```

### Helper Functions

For cleaner code, define indexing helpers:

```udewy
let load_i64 = (arr:int idx:int):>int => {
    return __load__(arr + (idx << 3))
}

let store_i64 = (arr:int idx:int val:int):>void => {
    __store__(val arr + (idx << 3))
    return void
}
```

## Compilation Model

The udewy compiler (`p0.py`) is a single-pass compiler that:
1. Tokenizes source (`t0.py`)
2. Parses against a shared backend contract
3. Lets the selected backend emit target-specific artifacts
4. Invokes the backend's build/run path

The `x86_64` backend uses the checked-in `runtime.s` file for its `_start` entry point. Other backends provide their own target-specific entry/build behavior.

### Forward References

Functions can be called before they're defined. Unknown identifiers are treated as forward function references and resolved at the end of compilation.

### Calling Convention

udewy uses the System V AMD64 ABI:
- Arguments in: `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`
- Return value in: `rax`
- Caller-saved: `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8-r11`
- Callee-saved: `rbx`, `rbp`, `r12-r15`

## Self-Hosting

The bootstrapped udewy compiler is in `tests/udewy/udewy.udewy` (~2500 lines). It demonstrates that the language is complete enough for real-world use while remaining simple enough to audit.

```bash
# Build the self-hosted compiler
python -m udewy.p0 -c udewy/tests/udewy.udewy

# Use it to compile a program
./__dewycache__/udewy udewy/tests/test_hello.udewy
```

## Imports

udewy supports importing other udewy files using path literals:

```udewy
import p"utils.udewy"
import p"lib/helpers.udewy"
```

### How It Works

- Paths are relative to the importing file
- Imports are processed recursively (imported files can import other files)
- Each file is only included once (circular imports are handled by tracking what's been imported)
- Imported content is prepended to the source, so definitions in imported files are available to the main file

### Path Literals

The `p"..."` syntax is a path literal, borrowed from full Dewy. In udewy, it behaves identically to a regular string but signals intent:

```udewy
import p"./sibling.udewy"        # relative to current file
import p"../parent/file.udewy"   # parent directory
import p"lib/module.udewy"       # subdirectory
```

### Example

Given two files:

**math.udewy:**
```udewy
let add = (a:int b:int):>int => {
    return a + b
}
```

**main.udewy:**
```udewy
import p"math.udewy"

let main = ():>int => {
    return add(1 2)  # returns 3
}
```

Compiling `main.udewy` will include `math.udewy` automatically.

## Intentional Limitations

udewy deliberately omits features to keep the compiler simple and auditable:

- **No indexing syntax** (`arr[i]`): Would require type information to know element size
- **No value casts** (`as`): Would behave differently than in full Dewy
- **No string interpolation**: Strings are simple byte sequences
- **No closures or nested functions**: Functions only at top level
- **No short-circuit evaluation**: Both sides of `and`/`or` are always evaluated
- **No floating-point**: Everything is 64-bit integers
- **No garbage collection**: Manual memory management via syscalls

## Files

- `p0.py` - Parser and backend-selecting compiler driver
- `t0.py` - Tokenizer
- `backend/` - Target-specific code generators
- `runtime.s` - x86_64 runtime (entry point, syscall wrappers)
- `concept.md` - Original design notes (may be outdated)

## Example: Fibonacci

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

## Example: Memory Allocation with mmap

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
    __store__(42 buffer)
    return __load__(buffer)  # returns 42
}
```

## Pronunciation

The name can be pronounced several ways depending on how you read the Greek letter μ (mu):

| Pronunciation | IPA | Reading |
|---------------|-----|---------|
| MY-kroh dew-ee | /ˌmaɪkroʊ ˈduːi/ | μ as "micro" |
| MYOO dew-ee | /mjuː ˈduːi/ | μ as "mu" |
| YOO dew-ee | /juː ˈduːi/ | μ as "u" |

All are equally correct, and no one is preferred over the others.