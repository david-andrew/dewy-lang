 .text
.global _start
_start:
 xor %ebp,%ebp
 mov %rsp,%rdi
 and $-16,%rsp
 call dewy_host_entry
 ud2
.global dewy_host_setjmp
dewy_host_setjmp:
 mov %rbx,0(%rdi)
 mov %rbp,8(%rdi)
 mov %r12,16(%rdi)
 mov %r13,24(%rdi)
 mov %r14,32(%rdi)
 mov %r15,40(%rdi)
 lea 8(%rsp),%rax
 mov %rax,48(%rdi)
 mov (%rsp),%rax
 mov %rax,56(%rdi)
 xor %eax,%eax
 ret
.global dewy_host_longjmp
dewy_host_longjmp:
 mov 0(%rdi),%rbx
 mov 8(%rdi),%rbp
 mov 16(%rdi),%r12
 mov 24(%rdi),%r13
 mov 32(%rdi),%r14
 mov 40(%rdi),%r15
 mov 48(%rdi),%rsp
 mov %rsi,%rax
 jmp *56(%rdi)
.global dewy_host_stack
dewy_host_stack:
 lea 8(%rsp),%rax
 ret
.section .note.GNU-stack,"",@progbits

