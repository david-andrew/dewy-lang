#ifndef METAL_C
#define METAL_C

#include "metal.h"
#include <stdio.h>
#include <stdlib.h>

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
    uint8_t* buf = malloc(buf_size);
    if (buf == NULL) return -1;
    while ((c = fgetc(stdin)) != EOF && c != delimiter)
    {
        if (count + 1 >= buf_size)
        {
            buf_size *= 2;
            buf = realloc(buf, buf_size);
            if (buf == NULL) return -1;
        }
        buf[count++] = c;
    }
    buf[count] = '\0';

    *dst = buf;
    return count;
}

#endif