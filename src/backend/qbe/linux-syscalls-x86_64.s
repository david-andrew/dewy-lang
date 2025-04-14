.text

# program entry point
.globl _start
_start:
    # Fetch argc, argv, envp from the stack
    movq (%rsp), %rdi               # rdi = argc
    leaq 8(%rsp), %rsi              # rsi = argv (pointer to the first argument)
    leaq 16(%rsp, %rdi, 8), %rdx    # rdx = envp (pointer to environment variables)

    # Call main(argc, argv, envp)
    call __main__

    # Handle return value from main (in %rax) and invoke the exit syscall
    movq %rax, %rdi                 # rdi = return value from main (for exit syscall)
    movq $60, %rax                  # syscall number for exit (60)
    syscall


# 0-arg syscall
.globl __syscall0__
__syscall0__:
        movq %rdi, %rax
        syscall
        ret


# 1-arg syscall
.globl __syscall1__
__syscall1__:
        movq %rdi, %rax
        movq %rsi, %rdi
        syscall
        ret


# 2-arg syscall
.globl __syscall2__
__syscall2__:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        syscall
        ret


# 3-arg syscall
.globl __syscall3__
__syscall3__:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        syscall
        ret


# 4-arg syscall
.globl __syscall4__
__syscall4__:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        syscall
        ret


# 5-arg syscall
.globl __syscall5__
__syscall5__:
        movq %rdi, %rax
        movq %rsi, %rdi
        movq %rdx, %rsi
        movq %rcx, %rdx
        movq %r8, %r10
        syscall
        ret


# 6-arg syscall
.globl __syscall6__
__syscall6__:
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
