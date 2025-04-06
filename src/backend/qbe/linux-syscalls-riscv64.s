.text

.global _start
_start:
    ld      a0, 0(sp)           // a0 = argc
    addi    a1, sp, 8           // a1 = argv
    slli    t0, a0, 3
    add     a2, a1, t0
    addi    a2, a2, 8           // a2 = envp

    call    main                // main(argc, argv, envp)

    mv      a0, a0              // return value from main already in a0
    li      a7, 93              // syscall number for exit (riscv64)
    ecall

// syscall1(number, arg0)
.global syscall1
syscall1:
    mv      a7, a0
    mv      a0, a1
    ecall
    ret

// syscall3(number, arg0, arg1, arg2)
.global syscall3
syscall3:
    mv      a7, a0
    mv      a0, a1
    mv      a1, a2
    mv      a2, a3
    ecall
    ret

// syscall5(number, arg0...arg4)
.global syscall5
syscall5:
    mv      a7, a0
    mv      a0, a1
    mv      a1, a2
    mv      a2, a3
    mv      a3, a4
    mv      a4, a5
    ecall
    ret

// syscall7(number, arg0...arg6)
.global syscall7
syscall7:
    mv      a7, a0
    mv      a0, a1
    mv      a1, a2
    mv      a2, a3
    mv      a3, a4
    mv      a4, a5
    mv      a5, a6
    ld      a6, 16(sp)          // 7th arg from stack
    ecall
    ret

.section .note.GNU-stack,"",@progbits
