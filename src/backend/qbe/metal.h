// TODO: this isn't quite right. For now just lean on C-compiler to handle everything.
// i.e. qbe <file>.ssa | gcc -o <file> <file>.o -lc

#ifndef METAL_H
#define METAL_H

// Header Declarations

/* C functions utilized by Dewy in a hosted environment */
/* TBD what to do about bare-metal/freestanding envs, probably just don't include these */

#include <stdint.h>

void _start(); // entry point

// printing to stdout
void __puts(uint8_t* s);
void __putu64(uint64_t u);
void __putu64x(uint64_t x);
void __puti64(int64_t i);
void __putf32(float f);
void __putf64(double d);
void __putl();
uint64_t __getl(uint8_t** dst);
uint64_t __getdl(uint8_t** dst, uint8_t delimiter);



// #define METAL_IMPLEMENTATION  // Uncomment to include implementations

// Implementations (if METAL_IMPLEMENTATION is defined)
#ifdef METAL_IMPLEMENTATION
#include <stdio.h>
#include <stdlib.h>

extern int main(int argc, char** argv);

int* argc;
char** argv;
void _start()
{
    // collect argc and argv from %rsp register
    asm volatile("movq %%rsp, %0\n" : "=r"(argc));
    argv = (char**)((char*)argc + 8);

    int res = main(*argc, argv);
    exit(res);
}

////// writing to stdout //////

void __puts(uint8_t* s) { fputs((char*)s, stdout); }
void __putu64(uint64_t u)
{
    const uint64_t buf_size = 20;
    uint8_t buf[buf_size];
    uint8_t len = 0;
    do {
        buf[buf_size - ++len] = '0' + u % 10;
        u /= 10;
    } while (u > 0);
    fwrite(&buf[buf_size - len], len, 1, stdout);
}
void __putu64x(uint64_t u)
{
    const uint64_t buf_size = 18; // 16 for number, 2 for '0x'
    uint8_t buf[buf_size];
    uint8_t len = 0;
    do {
        uint8_t v = u % 16;
        buf[buf_size - ++len] = u < 10 ? '0' + v : 'A' + v - 10;
        u /= 16;
    } while (u > 0);
    buf[buf_size - ++len] = 'x';
    buf[buf_size - ++len] = '0';
    fwrite(&buf[buf_size - len], len, 1, stdout);
}
void __puti64(int64_t i)
{
    if (i < 0)
    {
        fputc('-', stdout);
        i = -i;
    }
    __putu64((uint64_t)i);
}
void __putf32(float f) { printf("%f", f); }
void __putf64(double d) { printf("%f", d); }
void __putl() { fputc('\n', stdout); }

////// reading from stdin //////
uint64_t __getl(uint8_t** dst) { return __getdl(dst, '\n'); }
uint64_t __getdl(uint8_t** dst, uint8_t delimiter)
{
    uint64_t buf_size = 128; // initial buffer size
    uint64_t count = 0;      // characters read
    uint64_t c;              // current character
    uint8_t* buf = (uint8_t*)malloc(buf_size);
    if (buf == NULL) return -1;
    while ((c = fgetc(stdin)) != EOF && c != delimiter)
    {
        if (count + 1 >= buf_size)
        {
            buf_size *= 2;
            buf = (uint8_t*)realloc(buf, buf_size);
            if (buf == NULL) return -1;
        }
        buf[count++] = c;
    }
    buf[count] = '\0';

    *dst = buf;
    return count;
}

#endif // METAL_IMPLEMENTATION


#endif // METAL_H