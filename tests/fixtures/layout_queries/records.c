// The C side of records.dewy: the same records, printed as "name sizeof alignof".
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdalign.h>
typedef struct {uint8_t x;} A;
typedef struct {uint8_t x; int32_t y;} B;
typedef struct {int64_t x; uint8_t y;} C;
typedef struct {uint8_t a; uint16_t b; uint8_t c;} D;
typedef struct {float f; double d; float g;} E;
typedef struct {bool b; uint8_t *p; int16_t q;} F;
typedef struct {B inner; uint8_t tail;} G;
typedef struct {int16_t xs[3]; uint8_t k;} H;
typedef struct {float xs[5];} I;
typedef struct {C c; D d; E e;} J;
#define P(T) printf(#T " %zu %zu\n", sizeof(T), alignof(T))
int main(void){P(A);P(B);P(C);P(D);P(E);P(F);P(G);P(H);P(I);P(J);}
