#ifndef METAL_H
#define METAL_H

/* C functions utilized by Dewy in a hosted environment */
/* TBD what to do about bare-metal/freestanding envs, probably just don't include these */

#include <stdint.h>

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

#endif