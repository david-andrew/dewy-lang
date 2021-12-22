// How to compile/run:
// $ clang -O3 -emit-llvm -S hello.c
// $ llc -filetype=obj hello.ll
// $ ld.lld hello.o
// $ ./a.out

// or as a single line:
// $ clang -O3 -emit-llvm -S hello.c && llc -filetype=obj hello.ll && ld.lld hello.o && ./a.out

#define SYS_write 1
#define SYS_exit 60
#define stdout 1
#define stderr 2

// write syscall:
//     %rax: syscall number, %rdi: file descriptor, %rsi: buffer, %rdx: number of bytes
//     %rax: return value
int write(char* buf, int len)
{
    int n;
    asm volatile("syscall\n" : "=A"(n) : "a"(SYS_write), "D"(stderr), "S"(buf), "d"(len));
    return n;
}

void puts(char* s)
{
    int len = 0;
    while (s[len]) len++;
    write(s, len);
}

#define buf_size 32
char buf[buf_size];
void puti(unsigned int i)
{
    int len = 0;
    do {
        buf[buf_size - ++len] = '0' + i % 10;
        i /= 10;
    } while (i > 0);
    write(&buf[buf_size - len], len);
}
void putx(unsigned int i)
{
    int len = 0;
    do {
        buf[buf_size - ++len] = '0' + i % 16 > 9 ? 'A' + i % 16 - 10 : '0' + i % 16;
        i /= 16;
    } while (i > 0);
    buf[buf_size - ++len] = 'x';
    buf[buf_size - ++len] = '0';
    write(&buf[buf_size - len], len);
}
void putn() { write("\n", 1); }

// exit syscall:
//     %rax: syscall number, %rdi: exit code
void exit(int code)
{
    // infinite loop until the system ends this process
    for (;;) asm volatile("syscall\n" : : "a"(SYS_exit), "D"(code));
}

// TODO->move to a separate file
int main()
{
    puts("Hello, World!\n");
    puti(42);
    putn();
    putx(0xDEADBEEF);
    putn();
    puti(999);
    putn();
    puts("apple\n");
    puti(42);
    putn();
    puti(200);
    putn();
    return 0;
}

void _start()
{
    int res = main();
    exit(res);
}
