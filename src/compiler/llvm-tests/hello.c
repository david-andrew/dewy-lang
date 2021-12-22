// How to compile/run:
// $ clang -ffreestanding -O3 -emit-llvm -S hello.c
// $ llc -filetype=obj hello.ll
// $ ld.lld hello.o
// $ ./a.out

// or as a single line:
// $ clang -ffreestanding -O3 -emit-llvm -S hello.c && llc -filetype=obj hello.ll && ld.lld hello.o && ./a.out

// eventually this will just be an object file we link to that contains all the core OS functionality (i.e. syscalls)

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

// exit syscall:
//     %rax: syscall number, %rdi: exit code
void exit(int code)
{
    // infinite loop until the system ends this process
    for (;;) asm volatile("syscall\n" : : "a"(SYS_exit), "D"(code));
}

// stdout print functions. TODO->allow for stderr vs stdout via fd parameter in fput functions, and then wrap with these
int strlen(char* s)
{
    int i = 0;
    while (s[i++])
        ;
    return i;
}
void puts(char* s) { write(s, strlen(s)); }
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
void putl() { write("\n", 1); }

// TODO->move to a separate file
int main(int argc, char** argv)
{
    puts("Hello, World!\n");
    puti(42);
    putl();
    putx(0xDEADBEEF);
    putl();
    puti(999);
    putl();
    puts("apple\n");
    puti(42);
    putl();
    puti(200);
    putl();
    return 0;
}

char* test_argv[] = {"apple",     "banana",      "carrot",    "durian", "elderberry", "fig",
                     "grape",     "huckleberry", "jackfruit", "kiwi",   "lemon",      "mango",
                     "nectarine", "orange",      "papaya",    "quince", "raspberry",  "strawberry",
                     "tangerine", "watermelon",  "xylophone", "yam",    "zucchini"};
int test_argc = sizeof(test_argv) / sizeof(char*);
void _start()
{
    int res = main(test_argc, test_argv);
    exit(res);
}
