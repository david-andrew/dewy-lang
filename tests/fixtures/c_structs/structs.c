// C functions taking and returning small and large structs by value, for
// test_c_structs.py. Checksums weigh each field by its place.
#include <stdint.h>
#include <stdbool.h>
#define K(x) ((int64_t)((x) * 1000))
typedef struct { int32_t a; } S1;
int64_t S1_sum(S1 s) { return K(s.a) * 1; }
S1 S1_make(int32_t a) { S1 s = {a}; return s; }
S1 S1_twice(S1 s) { s.a = (int32_t)(s.a * 2); return s; }
typedef struct { double x; } D1;
int64_t D1_sum(D1 s) { return K(s.x) * 1; }
D1 D1_make(double x) { D1 s = {x}; return s; }
D1 D1_twice(D1 s) { s.x = (double)(s.x * 2); return s; }
typedef struct { float x; float y; } F2;
int64_t F2_sum(F2 s) { return K(s.x) * 1 + K(s.y) * 2; }
F2 F2_make(float x, float y) { F2 s = {x, y}; return s; }
F2 F2_twice(F2 s) { s.x = (float)(s.x * 2); s.y = (float)(s.y * 2); return s; }
typedef struct { double x; double y; } Vec2;
int64_t Vec2_sum(Vec2 s) { return K(s.x) * 1 + K(s.y) * 2; }
Vec2 Vec2_make(double x, double y) { Vec2 s = {x, y}; return s; }
Vec2 Vec2_twice(Vec2 s) { s.x = (double)(s.x * 2); s.y = (double)(s.y * 2); return s; }
typedef struct { float x; float y; float z; } F3;
int64_t F3_sum(F3 s) { return K(s.x) * 1 + K(s.y) * 2 + K(s.z) * 3; }
F3 F3_make(float x, float y, float z) { F3 s = {x, y, z}; return s; }
F3 F3_twice(F3 s) { s.x = (float)(s.x * 2); s.y = (float)(s.y * 2); s.z = (float)(s.z * 2); return s; }
typedef struct { double a; double b; double c; double d; } D4;
int64_t D4_sum(D4 s) { return K(s.a) * 1 + K(s.b) * 2 + K(s.c) * 3 + K(s.d) * 4; }
D4 D4_make(double a, double b, double c, double d) { D4 s = {a, b, c, d}; return s; }
D4 D4_twice(D4 s) { s.a = (double)(s.a * 2); s.b = (double)(s.b * 2); s.c = (double)(s.c * 2); s.d = (double)(s.d * 2); return s; }
typedef struct { int32_t i; float f; } IF;
int64_t IF_sum(IF s) { return K(s.i) * 1 + K(s.f) * 2; }
IF IF_make(int32_t i, float f) { IF s = {i, f}; return s; }
IF IF_twice(IF s) { s.i = (int32_t)(s.i * 2); s.f = (float)(s.f * 2); return s; }
typedef struct { double d; int64_t i; } DI;
int64_t DI_sum(DI s) { return K(s.d) * 1 + K(s.i) * 2; }
DI DI_make(double d, int64_t i) { DI s = {d, i}; return s; }
DI DI_twice(DI s) { s.d = (double)(s.d * 2); s.i = (int64_t)(s.i * 2); return s; }
typedef struct { int64_t i; double d; } ID;
int64_t ID_sum(ID s) { return K(s.i) * 1 + K(s.d) * 2; }
ID ID_make(int64_t i, double d) { ID s = {i, d}; return s; }
ID ID_twice(ID s) { s.i = (int64_t)(s.i * 2); s.d = (double)(s.d * 2); return s; }
typedef struct { uint8_t a; int16_t b; uint8_t c; } B3;
int64_t B3_sum(B3 s) { return K(s.a) * 1 + K(s.b) * 2 + K(s.c) * 3; }
B3 B3_make(uint8_t a, int16_t b, uint8_t c) { B3 s = {a, b, c}; return s; }
B3 B3_twice(B3 s) { s.a = (uint8_t)(s.a * 2); s.b = (int16_t)(s.b * 2); s.c = (uint8_t)(s.c * 2); return s; }
typedef struct { int64_t a; int64_t b; int64_t c; } Big3;
int64_t Big3_sum(Big3 s) { return K(s.a) * 1 + K(s.b) * 2 + K(s.c) * 3; }
Big3 Big3_make(int64_t a, int64_t b, int64_t c) { Big3 s = {a, b, c}; return s; }
Big3 Big3_twice(Big3 s) { s.a = (int64_t)(s.a * 2); s.b = (int64_t)(s.b * 2); s.c = (int64_t)(s.c * 2); return s; }
typedef struct { int32_t a; double b; int8_t c; float d; } Mix4;
int64_t Mix4_sum(Mix4 s) { return K(s.a) * 1 + K(s.b) * 2 + K(s.c) * 3 + K(s.d) * 4; }
Mix4 Mix4_make(int32_t a, double b, int8_t c, float d) { Mix4 s = {a, b, c, d}; return s; }
Mix4 Mix4_twice(Mix4 s) { s.a = (int32_t)(s.a * 2); s.b = (double)(s.b * 2); s.c = (int8_t)(s.c * 2); s.d = (float)(s.d * 2); return s; }
typedef struct { float a; int32_t b; double c; } FID;
int64_t FID_sum(FID s) { return K(s.a) * 1 + K(s.b) * 2 + K(s.c) * 3; }
FID FID_make(float a, int32_t b, double c) { FID s = {a, b, c}; return s; }
FID FID_twice(FID s) { s.a = (float)(s.a * 2); s.b = (int32_t)(s.b * 2); s.c = (double)(s.c * 2); return s; }
typedef struct { uint16_t a; uint8_t b; } U2;
int64_t U2_sum(U2 s) { return K(s.a) * 1 + K(s.b) * 2; }
U2 U2_make(uint16_t a, uint8_t b) { U2 s = {a, b}; return s; }
U2 U2_twice(U2 s) { s.a = (uint16_t)(s.a * 2); s.b = (uint8_t)(s.b * 2); return s; }
double many_vec(Vec2 a, Vec2 b, Vec2 c, Vec2 d, Vec2 e, double f, Vec2 g) { return a.x + b.y + c.x + d.y + e.x * 100 + e.y * 1000 + f * 10000 + g.x * 100000 + g.y; }
int64_t many_ints(int64_t a, int64_t b, int64_t c, int64_t d, int64_t e, B3 s, int64_t g, IF t, int64_t h) { return a + b + c + d + e + B3_sum(s) * 10 + g * 100 + IF_sum(t) * 1000 + h * 100000; }
int64_t big_mixed(int32_t k, Big3 a, double scale, Mix4 m, Big3 b, F3 f) { return k + Big3_sum(a) * 2 + K(scale) + Mix4_sum(m) * 3 + Big3_sum(b) * 5 + F3_sum(f) * 7; }
D4 d4_add(D4 a, D4 b, D4 c) { D4 r = {a.a + b.a + c.a, a.b + b.b + c.b, a.c + b.c + c.c, a.d + b.d + c.d}; return r; }
Big3 big_after(int64_t a, int64_t b, int64_t c, int64_t d, int64_t e, int64_t f, int64_t g, Big3 x) { Big3 r = {a + b + c + d, e + f + g, x.a + x.b + x.c}; return r; }
