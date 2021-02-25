#ifndef CHARSET_H
#define CHARSET_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

typedef struct
{
    uint32_t start;
    uint32_t stop;
} urange;


typedef struct
{
    urange* ranges;
    size_t size;
    size_t capacity;
} charset;

// charset* add_range(charset* s, urange r);
void charset_sort(charset* s);
bool charset_contains(charset* s, uint32_t c);



#endif