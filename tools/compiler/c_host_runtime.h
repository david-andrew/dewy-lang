#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef uint64_t U;
typedef int64_t S;
extern unsigned char gd[], rd[];
extern U initial_stack;
static inline U sc(U n, U a, U b, U c, U d, U e, U f) {
  register U r10 __asm__("r10") = d, r8 __asm__("r8") = e, r9 __asm__("r9") = f;
  U r;
  __asm__ volatile("syscall"
                   : "=a"(r)
                   : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8), "r"(r9)
                   : "rcx", "r11", "memory", "cc");
  return r;
}
extern U dewy_host_setjmp(U) __attribute__((returns_twice));
extern U dewy_host_longjmp(U, U) __attribute__((noreturn));
extern U dewy_host_stack(void);
static inline U f2i(double x) {
  return isnan(x)       ? 0
         : x >= 0x1p63  ? INT64_MAX
         : x <= -0x1p63 ? (U)INT64_MIN
                        : (U)(S)x;
}
static inline U sdiv(U a, U b) {
  if (!b || (a == (U)INT64_MIN && b == UINT64_MAX))
    __builtin_trap();
  return (S)a / (S)b;
}
static inline U srem(U a, U b) {
  if (!b || (a == (U)INT64_MIN && b == UINT64_MAX))
    __builtin_trap();
  return (S)a % (S)b;
}
static inline U udiv(U a, U b) {
  if (!b)
    __builtin_trap();
  return a / b;
}
static inline U urem(U a, U b) {
  if (!b)
    __builtin_trap();
  return a % b;
}
static inline uint8_t ld_uint8_t(U p) {
  uint8_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_uint8_t(U p, uint8_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline uint16_t ld_uint16_t(U p) {
  uint16_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_uint16_t(U p, uint16_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline uint32_t ld_uint32_t(U p) {
  uint32_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_uint32_t(U p, uint32_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline uint64_t ld_uint64_t(U p) {
  uint64_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_uint64_t(U p, uint64_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline int8_t ld_int8_t(U p) {
  int8_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_int8_t(U p, int8_t x) { memcpy((void *)p, &x, sizeof x); }
static inline int16_t ld_int16_t(U p) {
  int16_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_int16_t(U p, int16_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline int32_t ld_int32_t(U p) {
  int32_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_int32_t(U p, int32_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline int64_t ld_int64_t(U p) {
  int64_t x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_int64_t(U p, int64_t x) {
  memcpy((void *)p, &x, sizeof x);
}
static inline float ld_float(U p) {
  float x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_float(U p, float x) { memcpy((void *)p, &x, sizeof x); }
static inline double ld_double(U p) {
  double x;
  memcpy(&x, (void *)p, sizeof x);
  return x;
}
static inline void st_double(U p, double x) { memcpy((void *)p, &x, sizeof x); }
static inline double bf64(U x) {
  double r;
  memcpy(&r, &x, 8);
  return r;
}
static inline float bf32(U x) {
  uint32_t b = x;
  float r;
  memcpy(&r, &b, 4);
  return r;
}
static inline U fb64(double x) {
  U r;
  memcpy(&r, &x, 8);
  return r;
}
static inline U fb32(float x) {
  uint32_t r;
  memcpy(&r, &x, 4);
  return r;
}
static inline U streq(U a, U b) {
  if (a == b)
    return 1;
  U an = a ? ld_uint64_t(a + 8) : 0, bn = b ? ld_uint64_t(b + 8) : 0;
  return an == bn &&
         (!an || memcmp((void *)(a + 24), (void *)(b + 24), an) == 0);
}
static inline void host_copy(void *d, const void *s, U n) {
  if (n && d != s)
    memmove(d, s, n);
}
static inline void host_zero(void *d, int c, U n) {
  if (n)
    memset(d, c, n);
}
