# Encoder edge cases for the direct x86-64 object path, compared per
# symbol against gas (tests/python_misc/test_direct_objects.py). Every form
# the µDewy x86-64 backend emits, at the boundaries encoders get wrong:
# displacements 0 and +/-128, rbp/r13 bases (explicit displacement),
# rsp/r12 bases (SIB byte), immediates at the imm8 and imm32 edges, movabs
# constants, and REX with high and byte registers.
.text
.globl _start

_start:
    xorq %rbp, %rbp
    movq (%rsp), %rdi
    leaq 8(%rsp), %rsi
    andq $-16, %rsp
    call __main__
    movq %rax, %rdi
    movq $231, %rax
    syscall

.section .text.moves,"ax",@progbits
.globl moves
moves:
    movq %rax, %rbx
    movq %r8, %r15
    movq %rsp, %rbp
    movq (%rax), %rcx
    movq (%rbp), %rcx
    movq (%r13), %rcx
    movq (%rsp), %rcx
    movq (%r12), %rcx
    movq 1(%rax), %rcx
    movq 127(%rax), %rcx
    movq 128(%rax), %rcx
    movq -128(%rbp), %rcx
    movq -129(%rbp), %rcx
    movq 2147483647(%r12), %r9
    movq -2147483648(%rsp), %r10
    movq %rdx, -8(%rbp)
    movq %r14, 16(%rsp)
    movq %r11, 200(%r13)
    movq $0, %rax
    movq $-1, %r8
    movq $2147483647, %rcx
    movq $-2147483648, %rdx
    movq $2147483648, %rsi
    movq $-2147483649, %rdi
    movq $5, 24(%rbp)
    movq $-7, (%r12)
    movabsq $81985529216486895, %rax
    movabsq $-1, %r15
    movl (%rax), %eax
    movl 12(%r12), %r12d
    movl %r13d, %r13d
    movw %r12w, (%rax)
    movb %al, (%rbx)
    movb %r12b, 3(%rbp)
    movb %sil, (%rax)
    movb %dil, -1(%rsp)
    movb %spl, (%r8)
    movzbq %al, %rax
    movzbq %sil, %rdx
    movzbq (%rax), %rcx
    movzbq 9(%r12), %r13
    movzwq (%rax), %rax
    movsbq -3(%rbp), %rax
    movswq (%rbx), %rcx
    movslq 4(%rsp), %r9
    leaq -8(%rbp), %rax
    leaq (%r12), %r12
    leaq 1000(%r13), %rsp
    ret

.section .text.arithmetic,"ax",@progbits
.globl arithmetic
arithmetic:
    addq %rax, %rbx
    addq %r9, %r10
    addq (%rax), %rcx
    addq %rdx, 8(%rbp)
    addq $1, %rax
    addq $127, %rax
    addq $128, %rax
    addq $128, %rbx
    addq $-128, %rcx
    addq $-129, %r8
    addq $2147483647, %rax
    subq $64, %rsp
    subq $4096, %rsp
    subq 16(%rbp), %rax
    andq $-16, %rsp
    andq $255, %rax
    andq %r8, %rax
    orq %rcx, %rax
    orq $1, %r11
    xorq %rax, %rax
    xorq %r12, %r12
    xorq $-1, %rax
    cmpq %rbx, %rax
    cmpq $0, %rax
    cmpq $1000, %rax
    cmpq $1000, %rcx
    cmpq $5, 8(%rbp)
    cmpq $500, (%r12)
    cmpq -8(%rbp), %rax
    testq %rax, %rax
    testq %r15, %r8
    imulq %rbx, %rax
    imulq 8(%rbp), %r9
    imulq $3, %rax
    imulq $1000, %r10
    imulq $-2, %rcx
    negq %rax
    negq %r14
    notq %rdx
    cqto
    idivq %rcx
    idivq %r11
    divq %rbx
    shlq $1, %rax
    shlq $5, %r8
    shrq $63, %rax
    sarq $1, %rdx
    sarq %cl, %rax
    shlq %cl, %r12
    shrq %cl, %rbx
    ret

.section .text.control,"ax",@progbits
.globl control
control:
    pushq %rbp
    pushq %r12
    popq %r12
    popq %rbp
.Lback:
    cmpq %rax, %rbx
    sete %al
    setne %cl
    setl %sil
    setle %dil
    setg %r12b
    setge %r8b
    setb %al
    setbe %al
    seta %al
    setae %al
    je .Lforward
    jne .Lback
    jz .Lforward
    jnz .Lback
    jl .Lforward
    jle .Lforward
    jg .Lforward
    jge .Lforward
    jb .Lforward
    jbe .Lforward
    ja .Lforward
    jae .Lforward
    jmp .Lback
    jmp .Lforward
.Lforward:
    call moves
    call control
    call external_function
    call *%r11
    call *%rax
    jmp arithmetic
    leaq .str0(%rip), %rax
    movq .global1(%rip), %rcx
    movq %rax, .global1(%rip)
    movq $9, .global1(%rip)
    cmpq $2, .global1(%rip)
    cmpq $300, .global1(%rip)
    addq .global1+8(%rip), %rax
    int3
    ret
    .balign 16
    ret

# SSE moves and conversions for float arguments, with high registers on
# either side (REX.R/REX.B after the mandatory prefix).
.section .text.floats,"ax",@progbits
.globl floats
floats:
    movq %rax, %xmm0
    movq %r9, %xmm9
    movq %xmm0, %rax
    movq %xmm12, %r10
    movd %eax, %xmm3
    movd %r11d, %xmm3
    movd %xmm0, %eax
    movd %xmm10, %eax
    cvtsi2ss %rax, %xmm0
    cvtsi2sd %r8, %xmm15
    cvttss2si %xmm0, %rax
    cvttsd2si %xmm9, %r12
    ret

.section .text.__main__,"ax",@progbits
.globl __main__
__main__:
    movq $0, %rax
    ret

.data
.hidden __dso_handle
.weak __dso_handle
__dso_handle:
    .quad 0
.section .data..str0,"aw",@progbits
.globl .str0
.str0:
    .quad 11
    .byte 48, 46, 48, 255, 0
.section .data..global1,"awR",@progbits
.globl .global1
.global1:
    .quad .str0+8
    .quad -5
    .quad 9223372036854775807
    .quad .global1
    .quad external_data-16
    .balign 8
    .byte 1
    .balign 8
    .quad 3
.section .bss..static1,"aw",@nobits
.balign 8
.globl .static1
.static1:
    .zero 48
.extern external_function
.extern unused_external
.section .note.GNU-stack,"",@progbits
