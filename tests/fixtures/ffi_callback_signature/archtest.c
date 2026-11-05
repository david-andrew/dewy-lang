#include <stdint.h>
int32_t invoke(int32_t (*f)(int32_t), int32_t x) { return f(x); }
