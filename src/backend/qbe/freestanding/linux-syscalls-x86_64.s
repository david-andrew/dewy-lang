.text

# program entry point
.globl _start
_start:
    # Fetch argc, argv, envp from the stack
    movq (%rsp), %rdi               # rdi = argc
    leaq 8(%rsp), %rsi              # rsi = argv (pointer to the first argument)
    leaq 16(%rsp, %rdi, 8), %rdx    # rdx = envp (pointer to environment variables)

    # Call main(argc, argv, envp)
    call __main

    # Handle return value from main (in %rax) and invoke the exit syscall
    movq %rax, %rdi                 # rdi = return value from main (for exit syscall)
    movq $60, %rax                  # syscall number for exit (60)
    syscall


# 1-arg syscall
.globl __syscall1
__syscall1:
        movq %rdi, %rax
        movq %rsi, %rdi
        syscall
        ret


# 2-arg syscall
.globl __syscall2
__syscall2:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        syscall
        ret


# 3-arg syscall
.globl __syscall3
__syscall3:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        syscall
        ret


# 4-arg syscall
.globl __syscall4
__syscall4:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        syscall
        ret


# 5-arg syscall
.globl __syscall5
__syscall5:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        syscall
        ret


# 6-arg syscall
.globl __syscall6
__syscall6:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        movq %r9, %r8
        syscall
        ret


# for security, mark the stack as non-executable
.section .note.GNU-stack,"",@progbits
