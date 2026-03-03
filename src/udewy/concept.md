# μDewy
super strict subsets of dewy that are parsable by early stages in the trusted computing base. Goal is 100% auditable software chain up to full DewyOS

## Stage 0: raw byte in memory -> read ascii bytes from stdin
a tiny machine-code monitor written in hexadecimal. This program does exactly one thing: reads ASCII hexadecimal characters from standard input, loads them into memory as executable bytes, and jumps to them.
- Audit burden: Almost zero. A person with an ISA manual can verify 300 bytes of hex in an afternoon.
- Prior Art: hex0 from the live-bootstrap project.

> This will necessarily not be valid dewy
> would be cool if the stdin that it reads could be valid dewy

```dewy
# ignore comment lines starting with #
# non-comment lines, ignore anything not a hexidecimal digit
# todo: can't use hex string with 0x b/c 0 interpreted as hex for monitor input
# potentially could use 0x if we design whatever programs to work with an extra 0 at the start
# allowing it to be a based string means we could include comments in the string
0x"
8a 87 14 3f f9 b1 e1 bd d7 28 09 79 57 c3 87 bb
73 d7 e7 3e af fb 16 d1 77 0b f4 48 66 81 ff b1 
c2 7d 3a b1 8b 9a 36 34 7e cf d9 76 6d 0e fb e3 
d6 2d 2a cb 15 e3 13 93 30 79 93 8e dc c2 78 44 
bc b1 06 f2 59 16 b1 87 96 cd 5a 7a 15 0c 12 f8 
91 e8 50 26 d6 a5 c8 c7 d3 1a 1a 1a 99 56 67 e1 
57 83 d7 69 
" |> __run_hx_monitor__ # careful to use identifier without any hex chars
```


## Stage 1 ascii bytes -> read assembly
Using Stage 0, write a minimal Assembler. It doesn't need to support the whole CPU architecture, just the instructions intended to be use. It supports named labels and basic macros.
- Audit burden: Very low. It's essentially a dictionary mapping string mnemonics to byte opcodes.

> would be cool if the input to this stage could be valid dewy

```dewy
; " 
; ------------------------------------------------------------
; Mock bytecode interpreter core (x86-64, AT&T-ish neutral style)
; This is a *fragment* intended as "assembly instructions" mock-up.
; ------------------------------------------------------------

; Opcode values (mock)
%define OP_PUSH_IMM  0x01
%define OP_ADD       0x02
%define OP_PRINT     0x03
%define OP_HALT      0xFF

; Registers used:
;   rsi = ip (instruction pointer into bytecode)
;   rdi = stack_base
;   rcx = sp_offset (bytes)
;   rax, rbx, rdx = temporaries

interp_loop:
    ; fetch opcode byte
    movzx   eax, byte [rsi]      ; eax = opcode (zero-extend)
    inc     rsi                  ; ip++

    ; bounds-check opcode for jump table (mock: 0..3, else trap)
    cmp     eax, 3
    ja      bad_opcode

    ; dispatch via jump table
    lea     rdx, [rel op_table]
    mov     rdx, [rdx + rax*8]
    jmp     rdx

; -------------------------
; OP 0: (unused in this mock)
op_unused:
    jmp     interp_loop

...... <etc> ......

; " |> __run_x86_64__
```

just a note that these are seeming more like polyglot programs rather than valid dewy prgrams because the stage0/stage1 interpreters don't interpret the plumbing that is needed to have dewy run them correctly (i.e. piping a string into a function). And the fact that comment characters are used strategically. 

Basically stage0 and stage1 might be better off just directly being bytes and assembly without also being valid dewy

## Stage 2: assembler -> μdewy
A very very strict subset of dewy designed to be simple enough that a parser could be implemented in assembly
Restrictions:
- only `#` comments
- `|>` for all function calls
- `*` for multiply
- all returns must include an expression (`void` if want no return)
- other operators: `|>`, `*`, `//`, `%`, `+`, `-`, `.`, `=?`, `not=?`, `>?`, `<?`, `>=?`, `<=?`, `and`, `or`, `not`, `<<`, `>>`, `~`
    - `~` is separate from `not`. `~` inverts all bits, `not` inverts a boolean (i.e. just the last bit)
    - `and`, and `or` probably can serve as both bitwise and logical
- ~~all expressions must be fully parenthesized to indicate precedence. (tbd) consider allowing skipping parenthesis, and things are just parsed from left to right regardless (note that it allows programs to deviate in behavior if we include multiple operators of different precedence in the same expression). ~~ Expressions need not be parenthesized, but expressions will always be parsed from left to right. Perhaps we can track if an expression ever consumed a lower precedence operator before a higher precedence one, and error out
- ~~semicolons are probably mandatory for ending expressions~~ no semicolons at all
- ~~(tbd) commas are mandatory for separating arguments in functions. also array literals~~ no commas at all
- strict flow syntax `if (cond) {} else {}`, `if (cond) {} else if (cond) {} else {}` etc.
- data types (everything is an integer under the hood!):
    - `string` (no interpolation)
    - `int64`
    - `array<int64>`
    - (maybe) basic structs with named members...
- all variables are declared with `let name = ...` pattern. no destructuring. no using variables immediately without declaring them first. declarations must have an initial value
    - can also use `const`, but there is no enforcement of `let` vs `const`
- ~~no typing? or super minimal typing mandatory in all relevant places. no type checking. maybe also no type unions (e.g. something can't be int|undefined?.. but that would be pretty hard to go without.)~~
    - require type annotations in variable declarations, function signatures, and return type. Actual value is ignored, but type annotations are used to guide parsing.
- all fn arguments are position only
- ~~ranges don't support step size. also require bounds parenthesis/brackets~~ no ranges
- no express feature. must use return. Return must include an expression (`void` if want to not return anything)
- functions may only be declared at the top level


Some example programs:
```udewy
if (x =? 1) {
    printl("One")
}

```

```udewy
let i:int = 0
loop i <? 100 {
    if i % 15 =? 0 {
        printl("FizzBuzz")
    } else {
        if i % 3 =? 0 {
            printl("Fizz")
        } else if i % 5 =? 0 {
            printl("Buzz")
        } else {
            printl(int2str(i))
        }
    }
}
```


```udewy
if (x >? 5) and (x <? 10) {
    printl("x is in range")
}
```


```udewy
let fib = (n:int):>int => {
    if (n < 2) {
        return n
    } else {
        return fib(n - 1) + fib(n - 2)
    }
};
printl(int2str(fib(10)))
```


```udewy
# 1. Root level function (pointer stored in 'is_even')
let is_even = (n:int):>bool => {
    # 3. Boolean operators return 0 or 1
    return n % 2 =? 0
}

let main = ():>void => {
    # 1. Scoping: 'result' is local to main
    let result:bool = false
    
    # 2. Function pointer usage
    result = is_even(42)
    
    # 3. If checks for != 0
    if (result) {
        printl("It is even")
    }
}
```



udewy
```
# A helper function you would implement in the subset
# It takes two pointers (int64s) and returns 1 if contents match, 0 otherwise
let str_eq = (s1:string s2:string):>bool => {
    # 1. Check length (first 8 bytes at the pointer)
    # Note: using a hypothetical `peek` intrinsic or assembly insert for memory access
    let len1:int = s1.length
    let len2:int = s2.length
    
    if len1 not=? len2 { return false }
    let i:int = 0
    loop i <? len1 {
        if s1[i] not=? s2[i] { return false }
        i = i + 1
    }

    return true
}

let main = ():>void => {
    let msg1:string = "status"
    let msg2:string = "status"
    
    # This works because they likely point to the same interned address 
    # OR they are different addresses and this returns false (pointer inequality)
    if msg1 =? msg2 { 
        printl("Same pointer")
    }

    # This is the robust way to do it in Stage 2
    if (str_eq(msg1 msg2)) {
        printl("Same content")
    }
}
```

## Stage 3: udewy -> full dewy compiler
...