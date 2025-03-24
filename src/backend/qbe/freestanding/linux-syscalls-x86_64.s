.text

# program entry point
.globl _start
_start:
    # Fetch argc, argv, envp from the stack
    movq (%rsp), %rdi               # rdi = argc
    leaq 8(%rsp), %rsi              # rsi = argv (pointer to the first argument)
    leaq 16(%rsp, %rdi, 8), %rdx    # rdx = envp (pointer to environment variables)

    # Call main(argc, argv, envp)
    call main

    # Handle return value from main (in %rax) and invoke the exit syscall
    movq %rax, %rdi                 # rdi = return value from main (for exit syscall)
    movq $60, %rax                  # syscall number for exit (60)
    syscall


# 1-arg syscall
.globl syscall1
syscall1:
        movq %rdi, %rax
        movq %rsi, %rdi
        syscall
        ret


# 3-arg syscall
.globl syscall3
syscall3:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        syscall
        ret


# 5-arg syscall
.globl syscall5
syscall5:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        syscall
        ret


# 7-arg syscall
.globl syscall7
syscall7:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        movq %r9, %r8
        movq 16(%rsp), %r9
        syscall
        ret



# for security, mark the stack as non-executable
.section .note.GNU-stack,"",@progbits
