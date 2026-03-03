# μDewy (Micro-Dewy) Implementation Details

This document outlines the design decisions for **μDewy** (Micro-Dewy), a strict, simplified subset of the Dewy programming language.

**Goal:** Provide a language that is high-level enough to write an operating system kernel and basic tools, yet simple enough to be parsed by a tiny, auditable bootstrap compiler (Stage 2) written in assembly or hex machine code.

---

## 1. Core Philosophy
*   **Valid Dewy:** All μDewy code must be valid Full Dewy code. It should be compilable by the final Stage 3 compiler without modification.
*   **No Magic:** The Stage 2 compiler performs almost no semantic analysis. It treats everything as a 64-bit integer (machine word).
*   **LL(1) Grammar:** The syntax is restricted to be predictive with 1-token lookahead, eliminating the need for backtracking or complex parsing logic.

---

## 2. Syntax Restrictions

### Lexical Rules
*   **Identifiers:** ASCII only (a-z, A-Z, 0-9, _).
*   **Strings:** Simple double-quoted `"..."` only. No interpolation (`{}`), no heredocs, no raw strings.
*   **Numbers:** Decimal integers (`123`), Hex (`0x1A`), and Booleans (`true`/`false`). No floats.
*   **Comments:** Line comments (`#`) only. No block comments.
*   **Whitespace:** Ignored (newlines are whitespace). explicit `;` for statement termination is recommended/required for parsing simplicity.

### Syntactic Simplifications
*   **No Operator Precedence:** All binary operations must be **fully parenthesized**.
    *   *Full:* `a + b * c`
    *   *Micro:* `(a + (b * c))`
*   **No Juxtaposition:** Explicit function calls only.
    *   *Full:* `printl"hello"`
    *   *Micro:* `printl("hello") ` or `("hello" |> printl)`. multi-arg functions probably use former `something(arg1, arg2, arg3)`, tbd if we'd support `(arg1, arg2, arg3) |> something`
*   **Strict Control Flow:** `if`, `loop`, `else` must always use `{}` blocks.
    *   *Micro:* `if (cond) { ... } else { ... }`

---

## 3. Type System & Variables

### The "Everything is an Integer" Rule
The Stage 2 compiler does **zero type checking**. Every variable is treated as a raw 64-bit integer (machine word).
*   **Integer:** Holds the value (e.g., `42`).
*   **Boolean:** Holds `1` (`true`) or `0` (`false`).
*   **Pointer (String/Array/Struct):** Holds the **memory address** of the data.

### Scoping
*   **Local Variables:** Allocated on the stack (relative to base pointer, e.g., `[RBP - 8]`).
*   **Global Variables:** Allocated at fixed memory addresses in the `.data` / `.bss` section.
*   **Implementation:** The compiler maintains a stack of symbol tables.
    *   *Enter Block:* Push new table.
    *   *Exit Block:* Pop table.
    *   *Resolution:* Check current table $\to$ parent table $\to$ ... $\to$ global.

### Type Annotations
*   **Syntax:** `let x: int = 5;`
*   **Behavior:** The Stage 2 compiler **parses and ignores** type annotations.
    *   This keeps the compiler simple (skip tokens between `:` and `=`).
    *   Crucially, it documents the code for the human writing the OS.
    *   It allows the Stage 3 (Full) compiler to verify correctness later.

---

## 4. Functions

### Declaration Syntax
To ensure the grammar is LL(1) and unambiguous, **function declarations must use explicit argument and return types**.

*   **Pattern:** `let name = (arg: type, ...):> return_type => { ... }`
*   **Parsing Logic:**
    *   `(` $\to$ `arg` $\to$ **`:`** confirm function definition.
    *   `(` $\to$ `arg` $\to$ **`op`** confirm expression.
    *   `(` $\to$ `)` $\to$ **`:>`** confirm empty-arg function.
*   **Empty Args:** `let f = ():> void => { ... }`

### Function Pointers
*   Functions are defined at the **root level only** (no closures/capturing).
*   A function variable simply holds the address of the code label.
*   **Calling:** `f(x)` compiles to `CALL [f_address]`.

### Recursion
*   Allowed via proper scoping (see Section 3).
*   Example: `fib(n-1)` resolves `fib` from the global scope.

---

## 5. Data Structures

### Strings
*   **Representation:** Pointer to a **length-prefixed** memory block (Pascal-style).
    *   `[Length64][Byte 0][Byte 1]...`
*   **Literals:** `let s = "hello"`
    *   Compiler emits length + bytes to `.data` section.
    *   Substitutes literal with address `0xADDR`.
*   **Operations:** No operator overloading.
    *   `s1 + s2` $\to$ Adds addresses (Garbage).
    *   `s1 =? s2` $\to$ Checks pointer equality.
    *   **Must implement/call:** `str_eq(s1, s2)`, `str_cat(s1, s2)`.

### Arrays
*   **Representation:** Pointer to a **length-prefixed** memory block.
    *   `[Length64][Item 0 (64-bit)][Item 1 (64-bit)]...`
*   **Allocation:**
    *   *Runtime:* `new_array(size)` uses a bump allocator (global pointer that increments).
    *   *Literal:* `[1, 2, 3]` emitted to `.data` section.
*   **Indexing:** Pointer arithmetic.
    *   `arr[i]` $\to$ `LOAD [arr + 8 + (i * 8)]`

### Unit / Void
*   **Value:** `()` as a value/expression is **disallowed**.
*   **Return:** Void functions return `0` / undefined register value.
*   **Statement:** `do_something();` is a statement, not an expression.

---

## 6. Booleans & Logic
*   **True:** Literal `1`.
*   **False:** Literal `0`.
*   **Comparison Operators:** `=?`, `>?`, `<?` return `1` or `0`.
*   **Control Flow:** `if (cond)` checks `cond != 0`.
*   **Safety:** `true + 5` is valid in Stage 2 (results in `6`), but will be caught by Stage 3.

---

## 7. Example Program (μDewy)

```udewy
# Global function declaration
# Explicit types required for disambiguation
let str_eq = (s1: int, s2: int):> bool => {
    # 1. Read lengths (first 8 bytes)
    # Note: __peek__ is a hypothetical intrinsic/asm for memory access
    let len1: int = __peek__(s1);
    let len2: int = __peek__(s2);
    
    if (len1 not=? len2) { return false; }
    
    # ... loop and compare bytes ...
    return true;
};

let main = ():> void => {
    let msg1: string = "status";
    let msg2: string = "status";
    
    # Pointer equality check
    if (msg1 =? msg2) { 
        ("Same pointer" |> printl);
    }

    # Content equality check
    if (str_eq(msg1, msg2)) {
        ("Same content" |> printl);
    }
    
    # Recursion Example
    let val: int = 10;
    if (val >? 5) {
        let result: int = (val |> fib);
        (result |> printl);
    }
};
```
