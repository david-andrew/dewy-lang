# Trusted Computing Base
Goal is 100% auditable software chain up to full DewyOS

## Stage 0: Monitor
a tiny machine-code monitor written in hexadecimal. This program does exactly one thing: reads ASCII hexadecimal characters from standard input, loads them into memory as executable bytes, and jumps to them.

### Bootstrapping
manually entered one byte at a time on the host system

### Input:
ASCII hexidecimal characters from stdin. e.g.

```
8a 87 14 3f f9 b1 e1 bd d7 28 09 79 57 c3 87 bb
73 d7 e7 3e af fb 16 d1 77 0b f4 48 66 81 ff b1 
c2 7d 3a b1 8b 9a 36 34 7e cf d9 76 6d 0e fb e3 
d6 2d 2a cb 15 e3 13 93 30 79 93 8e dc c2 78 44 
bc b1 06 f2 59 16 b1 87 96 cd 5a 7a 15 0c 12 f8 
91 e8 50 26 d6 a5 c8 c7 d3 1a 1a 1a 99 56 67 e1 
57 83 d7 69
```

Grammar
```
input ::= (junk* hex)* junk*
hex ::= [0-9A-Fa-f]
junk ::= ~hex
```

> Note: this is necessarily not valid dewy syntax. Conforming to dewy syntax is unproductive at this level

### Output:
No output. Directly executes bytes loaded.

### Expected size: 
~300 bytes of hex

### Audit Burden
Almost zero. A person with an ISA manual can verify 300 bytes of hex in an afternoon.

### Prior Art
hex0 from the live-bootstrap project.



## Stage 1: Assembler
Using Stage 0, write a minimal Assembler. It doesn't need to support the whole CPU architecture, just the instructions intended to be use. It supports named labels and basic macros.

### Bootsrapping
Write out the bytes for the assembler code, and then pass them into stdin of stage 0

### Input
Assembly program code written out in ascii passed into stdin


```dewy
; x86_64"
; ------------------------------------------------------------
; Mock bytecode interpreter core (x86-64, AT&T-ish neutral style)
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

> would be cool if the input to this stage could be valid dewy. But might still be unproductive--TBD, e.g. string prefix funcs might be able to validate stuff, etc. These are seeming more like polyglot programs rather than valid dewy prgrams because the stage1 interpreter doesn't interpret the plumbing that is needed to have dewy run them correctly (i.e. piping a string into a function). And the fact that comment characters are used strategically.



### Output
(TBD) probably just execute the assembly program passed in

### Expected Size
~1000 lines of raw machine code (i.e. assembly in hex format)

### Audit Burden
Very low. It's essentially a dictionary mapping string mnemonics to byte opcodes.

### Prior Art
6502 ASM
GNU AS
etc.


## μDewy: Strict Dewy Subset Language
udewy will be a strict subset of the full dewy programming language. It will be about as powerful as the B programming language, e.g. everything is an integer under the hood, basic flow control and function definitions, etc. Most interactions will be behind function interfaces designed to make stuff more ergonomic (and also support making udewy programs compatible with full dewy).

### Bootsrapping
TBD exact details. Will be written in the assembly supported by stage 1. But probably will also interact with OS functionality like file loading, memory, etc.

### Input
udewy source code

### Output
binary executable

### Expected Size
~2-5k lines of assembly (depending on backend support, etc. Probably aim lower and pick a single backend)

### Audit Burden
Medium Low. udewy is designed to be very simple. The grammar is LL(1) so a basic recursive descent parser can be utilized, and the subset of included features from dewy is deliberately minimal, simplifying the required implementation machinery.

### Prior Art
B programming language
Project Oberon / Oberon Programming Language

Also relevant is how project oberon interleaves OS functionality into the bootstrap process for each of the language layers
```
ROM monitor / firmware
        ↓
machine bootstrap loader
        ↓
very small runtime + module loader
        ↓
basic kernel services (memory, files, devices)
        ↓
text system and UI
        ↓
compiler
        ↓
tools and applications
```
E.g. we'll need to think about how the OS is interleaved in our trusted computing base. This is because the Oberon Programming Language (and presumably udewy) will need to make use of various OS features like interacting with files, stdin/stdout, etc.


## TBD mDewy: milli-dewy,
if need extra layer between μDewy and full Dewy, mDewy would be it
- structs (dot accessing members)
- arrays with known element sizes
- C-level type checking
- tbd other necessary features for max power, min impl requirements
### Bootsrapping

### Input

### Output

### Audit Burden

### Prior Art



## Dewy: Fully Features Programming Language

### Bootsrapping

### Input

### Output

### Audit Burden

### Prior Art




## Open Questions
- what architecture/ISA will be the primary target? perhaps target riscv, and then can cross compile to anything else?
- how will the OS be interleaved in the language bootstrapping? depends on what features udewy needs for the full compiler. likely:
    - files/file loading
    - stdin/stdout
    - basic memory allocation