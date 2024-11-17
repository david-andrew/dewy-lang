/**
 * Until we have QBE as completely standalone,
 * we will use C to provide portable access to
 * a few base functions.
 * 
 * Usage:
 * qbe myprog.ssa > myprog.s && gcc shim.c myprog.s -o myprog && ./myprog
 * note that myprog.ssa should contain a $main function
 * ```qbe
 * export function w $main(l %argc, l %argv, l %envp) { ... }
 * ```
 * noting that %argc, %argv, and %envp are optional
 * 
 * Other notes:
 * - to increment argv/envp to the next pointer, you must add 8
 * -
 * 
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>


// declarations
uint64_t __cstrlen(uint8_t* s);
void __putcstr(uint8_t* s);
void __write(uint8_t* s, uint64_t len);
void __putu64(uint64_t u);
void __putu64x(uint64_t x);
void __puti64(int64_t i);
void __putf32(float f);
void __putf64(double d);
void __putl();
uint64_t __getl(uint8_t** dst);
uint64_t __getdl(uint8_t** dst, uint8_t delimiter);
void* __malloc(uint64_t size);
void __free(void* ptr);
void* __realloc(void* ptr, uint64_t size);


// future extensions
void* __fopen(uint8_t* path, uint8_t* mode);
void __fclose(void* stream);
uint64_t __fread(void* stream, uint8_t* buffer, uint64_t size);
void __fwrite(void* stream, uint8_t* buffer, uint64_t size);
uint64_t __fgetc(void* stream);
void __fputc(void* stream, uint8_t c);
uint64_t __fseek(void* stream, int64_t offset, uint8_t whence);
uint64_t __ftell(void* stream);
uint64_t __stat(uint8_t* path, uint64_t* size, uint64_t* mtime);
uint8_t __unlink(uint8_t* path);
void __memcpy(uint8_t* dest, uint8_t* src, uint64_t size);
void __memset(uint8_t* dest, uint8_t value, uint64_t size);
void __exit(uint64_t code);
uint64_t __system(uint8_t* command);
uint64_t __time(); //return microseconds?
// struct {uint64_t s; uint64_t n} __precise_time(){} //return uint128_t of nanoseconds?
//threading stuff/synchronization


// implementations
uint64_t __cstrlen(uint8_t* s)
{
    uint64_t len = 0;
    while (s[len] != '\0') len++;
    return len;
}
void __putcstr(uint8_t* s) { fputs((char*)s, stdout); }
void __write(uint8_t* s, uint64_t len) { fwrite(s, len, 1, stdout); }
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
        uint8_t v = u & 0xF;   
        buf[buf_size - ++len] = v < 10 ? '0' + v : 'A' + v - 10;
        u >>= 4;
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

void* __malloc(uint64_t size) { return malloc(size); }
void __free(void* ptr) { free(ptr); }
void* __realloc(void* ptr, uint64_t size) { return realloc(ptr, size); }