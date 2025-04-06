.text

.global _start
_start:
    // Stack layout is the same on Linux, but register names are different
    ldr     x0, [sp]            // x0 = argc
    add     x1, sp, #8          // x1 = argv
    add     x2, x1, x0, lsl #3  // x2 = envp (after argv + NULL)

    bl      main                // call main(argc, argv, envp)

    // exit syscall with return value in x0
    mov     x8, #93             // syscall number for exit (Linux AArch64)
    svc     #0

// syscall1(number, arg0)
.global syscall1
syscall1:
    mov     x8, x0      // syscall number
    mov     x0, x1      // arg0
    svc     #0
    ret

// syscall3(number, arg0, arg1, arg2)
.global syscall3
syscall3:
    mov     x8, x0
    mov     x0, x1
    mov     x1, x2
    mov     x2, x3
    svc     #0
    ret

// syscall5(number, arg0, arg1, arg2, arg3, arg4)
.global syscall5
syscall5:
    mov     x8, x0
    mov     x0, x1
    mov     x1, x2
    mov     x2, x3
    mov     x3, x4
    mov     x4, x5
    svc     #0
    ret

// syscall7(number, arg0...arg6)
.global syscall7
syscall7:
    mov     x8, x0
    mov     x0, x1
    mov     x1, x2
    mov     x2, x3
    mov     x3, x4
    mov     x4, x5
    mov     x5, x6
    ldr     x6, [sp, #16]  // 7th arg from stack
    svc     #0
    ret

.section .note.GNU-stack,"",@progbits
