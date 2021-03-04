#ifndef MAST_H
#define MAST_H

// #include <stdint.h>
// #include <stdbool.h>
#include <stddef.h>

#include "object.h"
#include "charset.h"

typedef enum {
    mast_epsilon,
    // mast_codepoint,
    mast_charset,
    mast_count, 
    // mast{count::int, repeat::bool}
    // count exactly is mast{count=N, repeat=false}
    // star is mast{count=1, repeat=true} | \e
    // plus is mast{count=1, repeat=true}
    // range is mast{lower, true} - mast{upper+1, true}
    // option is #expr | \e
    mast_or,
    mast_cat, //or mast_string
    mast_reference,


} mast_type;

typedef struct
{
    void* body; //either a mast** or a mast_leaf*
    size_t size;
} mast;

typedef struct
{
    charset class;
} mast_leaf;

#endif