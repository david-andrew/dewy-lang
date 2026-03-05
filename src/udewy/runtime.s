# udewy runtime for x86_64 Linux
# Provides: _start entry point, syscall wrappers

.text

# Program entry point
.globl _start
_start:
    # Clear rbp for clean stack traces
    xorq %rbp, %rbp
    
    # Fetch argc, argv, envp from the stack
    movq (%rsp), %rdi               # rdi = argc
    leaq 8(%rsp), %rsi              # rsi = argv (pointer to the first argument)
    leaq 16(%rsp, %rdi, 8), %rdx    # rdx = envp (pointer to environment variables)

    # Align stack to 16 bytes (required by System V ABI)
    andq $-16, %rsp

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
    movq %r9, %r8
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
    # 6th arg is on stack at 8(%rsp) due to return address
    movq 8(%rsp), %r9
    syscall
    ret


# Memory load/store intrinsics (for external linking if needed)

# Load 64-bit value from address
.globl __load__
__load__:
    movq (%rdi), %rax
    ret


# Store 64-bit value to address
.globl __store__
__store__:
    movq %rdi, (%rsi)
    ret


# Load byte from address (zero-extended)
.globl __load8__
__load8__:
    movzbq (%rdi), %rax
    ret


# Store byte to address
.globl __store8__
__store8__:
    movb %dil, (%rsi)
    ret


# Mark stack as non-executable
.section .note.GNU-stack,"",@progbits
