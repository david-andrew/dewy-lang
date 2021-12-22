#ifndef METAL_C
#define METAL_C

#include "metal.h"
#include <stdio.h>

void __puts(uint8_t* s) { fputs((char*)s, stdout); }
void __putu64(uint64_t u)
{
    const int buf_size = 20;
    uint8_t buf[buf_size];
    uint8_t len = 0;
    do {
        buf[buf_size - ++len] = '0' + u % 10;
        u /= 10;
    } while (u > 0);
    fwrite(&buf[buf_size - len], len, 1, stdout);
}
void putu64x(uint64_t u)
{
    const int buf_size = 18; // 16 for number, 2 for '0x'
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
void putf32(float f) { printf("%f", f); }
void putf64(double d) { printf("%f", d); }
void putl() { fputc('\n', stdout); }

#endif