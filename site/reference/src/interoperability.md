# Host Interoperability

> [Generated coverage](/status/#ref-interoperability) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Dewy calls C functions directly and lets C call Dewy functions through function pointers. There is no binding generator and no wrapper library: a declaration states the C signature, and an `$unsafe` boundary marks each place where a person, not the compiler, vouches for what foreign code does.

## Foreign Declarations: `$extern`

A function declaration prefixed with `$extern` is a C function. It has no body and no `=>`. Optional keyword arguments give the C symbol name and the library:

<!-- dewy-example: {"mode":"run","stdout":"5\ntrue\n"} -->
```dewy
$extern
strlen = (s:ptr<uint8>):>uint64
$extern
getenv = (name:string):>ptr<uint8>?
$extern(name='Sleep' lib='kernel32')
sleep_ms = (ms:uint32):>void

main = ():>void => $unsafe {
    let text:array<uint8> = bytes("hello")
    text.push(0)
    printl(strlen(text.ptr))
    printl(getenv("SURELY_NOT_SET_ANYWHERE") is? none)
}
```

Library lookup:

- No `lib=`, or `lib='c'`: the C library (`libc.so.6`, `libSystem`, `msvcrt.dll`). `lib='m'` is the math library.
- Another bare name is the system's usual file for it: `lib='z'` is `libz.so` on Linux and `libz.dylib` on macOS; `lib='kernel32'` is `kernel32.dll`.
- A name with a dot or a slash is used as written: `lib='libsqlite3.so.0'`.
- Windows' `msvcrt.dll` predates C99 (no `fma`, no hexadecimal floats in `strtod`); name `lib='ucrtbase'` for those.

The library is loaded when the function is first called. A web build imports the function from the page under its Dewy name; Dewy has no spelling yet for the JavaScript that supplies it.

## Types at the Boundary

An `$extern` signature uses C's types:

| Dewy | C |
|---|---|
| `int8` … `int64`, `uint8` … `uint64`, `float32`, `float64`, `bool` | the fixed-width type |
| `ptr<T>` | `T *`, never null |
| `ptr<T>?` | `T *` that may be null; null is `none` |
| a record of C-layout fields | a `struct`, by pointer or by value |
| `string` (parameter only) | a zero-terminated `char *` |
| a function type (parameter only) | a C function pointer |

`int` is rejected, since its size is not fixed. A record holding a string, an array or another managed value has no C layout, and a pointer to one is rejected.

<!-- dewy-example: {"mode":"reject","diagnostic":"`int` cannot cross the C boundary"} -->
```dewy
$extern
labs = (x:int):>int
main = () => printl($unsafe labs(1))
```

A C function's result is the claim of its declaration: one declared `ptr<T>` must not return null, and a refined result is trusted to satisfy its refinement. A parameter cannot state a refinement; check the value in Dewy first.

<!-- dewy-example: {"mode":"run","stdout":"65\n"} -->
```dewy
$extern
toupper = (c:int32):>int32<b => b >=? 0 and b <=? 255>
main = () => printl(uint8($unsafe toupper(97)))
```

## Raw Pointers

- `p[i]` reads and writes the `i`th `T` from `p`.
- `p + n` is `n` elements on.
- `p as ptr<U>` reinterprets it.
- `xs.ptr` (provisional spelling) points to an array's elements, for C to read or fill. It is valid until the array next changes length or is replaced. An empty array's pointer is not null either.

`ptr<T>?` is one word wherever it sits (zero is `none`), so C can fill a `T **` out-parameter, an array of pointers or a record field in place:

<!-- dewy-example: {"mode":"run","stdout":"12\n97\n"} -->
```dewy
$extern
strtol = (s:ptr<uint8> stop_at:ptr<ptr<uint8>?> base:int32):>int64
main = ():>void => $unsafe {
    let text:array<uint8> = bytes("12ab")
    text.push(0)
    let stop:array<ptr<uint8>?> = [none]
    printl(strtol(text.ptr stop.ptr 10))
    let rest = stop[0]
    if rest isnt? none { printl(rest[0]) }   # 'a'
}
```

## C Structs

A record of fixed-width numbers, bools, pointers and such records has C's layout: its fields in order, each at its natural alignment. C fills one in place through a pointer, and it also crosses by value, passed in registers or memory as the C compiler would (System V on x86-64 Linux, AAPCS64 on arm64).

<!-- dewy-example: {"mode":"run","stdout":"9 2\n"} -->
```dewy
DivT:type = [quot:int32 rem:int32]
$extern
div = (numerator:int32 denominator:int32):>DivT
main = ():>void => $unsafe {
    let d = div(47 5)
    printl(d.quot d.rem)
}
```

Passing a struct by value is not built yet on Windows, in a web build, as an argument to a variadic C function, in a C function type or in an `$export` function: pass a `ptr<T>` there. On macOS a by-value struct must fit in the argument registers.

`size_of<T>` and `align_of<T>` give a type's size and alignment in bytes as compile-time integers. For a C-layout record they are C's `sizeof` and `alignof`, padding included. For other types they report Dewy's own representation on the target.

<!-- dewy-example: {"mode":"run","stdout":"16 8 4\n"} -->
```dewy
TimeVal:type = [seconds:int64 microseconds:int64]
printl(size_of<TimeVal> align_of<TimeVal> size_of<int32>)
```

## The Unsafe Boundary

Calling an `$extern` function, naming it as a value, and reading or writing through a `ptr<T>` need an unsafe boundary:

- `$unsafe expression`, on its line or the line above;
- `$unsafe { … }` around several;
- `$unsafe` before a declaration, for that declaration.

No bundle of settings may hold `$unsafe`. A safe wrapper confines it:

<!-- dewy-example: {"mode":"run","stdout":"true\n"} -->
```dewy
$extern
getpid = ():>int32
pid = ():>int32 => $unsafe getpid()
main = () => printl(pid() >? 0)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"needs an unsafe boundary"} -->
```dewy
$extern
getpid = ():>int32
main = () => printl(getpid())
```

## Effects

A foreign call is opaque to effect rows: a function with a closed row, such as `& no_effects`, cannot call one. A foreign call may block, so a `parallel` body cannot call one either; tasks can. A row written on the `$extern` declaration itself is trusted, as part of the unsafe claim:

<!-- dewy-example: {"mode":"run","stdout":"5\n"} -->
```dewy
$extern
labs = (x:int64):>int64 & no_effects
magnitude = (x:int64):>int64 & no_effects => $unsafe labs(x)
printl(magnitude(-5))
```

On Linux, a program with tasks that calls C loads the C library on its main thread before its first task.

## Exported Functions: `$export`

`$export` before a module function gives it the C calling convention, so C can call it through a function pointer. `$export(name='sym')` names its symbol where the target exports one; WebAssembly builds export it to the page. Native executables do not export symbols yet, so C reaches an exported function only through a pointer that Dewy passes. `@f` passes it where a C function type is expected.

<!-- dewy-example: {"mode":"run","stdout":"[1 3 5 9]\n"} -->
```dewy
$extern
qsort = (base:ptr<int32> count:uint64 size:uint64 compare:((a:ptr<int32> b:ptr<int32>):>int32)):>void

$export
ascending = (a:ptr<int32> b:ptr<int32>):>int32 => $unsafe {
    if a[0] <? b[0] -1 else if a[0] >? b[0] 1 else 0
}

main = ():>void => {
    let xs:array<int32> = [5 3 9 1]
    $unsafe qsort(xs.ptr uint64(xs.length) size_of<int32> @ascending)
    printl(xs)
}
```

An exported function takes and returns the same kinds of values as an `$extern` one, `ptr<T>?` included.

## Compiler Intrinsics

`$intrinsic` before a declaration with no body names a function the compiler provides. Any name the compiler does not provide is an error.

<!-- dewy-example: {"mode":"run","stdout":"1.4142135623730951\n"} -->
```dewy
$intrinsic
sqrt = (x:float64):>float64
printl(sqrt(2.0))
```

## Targets

Native executables call C on Linux, macOS and Windows. A web build runs as WebAssembly in the page, and its foreign functions come from the page. See [Targets](targets.md) for the target list.
