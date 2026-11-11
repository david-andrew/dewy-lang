#include <stdint.h>
#include <stdlib.h>

typedef struct { uint8_t tag; int32_t value; } Small;
typedef struct { double x; double y; } Pair;
typedef struct { Small small; Pair pair; } Nested;
typedef struct { int64_t a, b, c, d; } Large;
typedef struct { int32_t values[2]; } Two;
typedef struct { int32_t id; double weight; } Mixed;
typedef struct { float x, y, z; } Triple;

Small small_next(Small x) { x.value += x.tag; return x; }
Pair pair_scale(Pair x, double factor) { return (Pair){x.x * factor, x.y * factor}; }
Nested nested_next(Nested x) { x.small.value += 1; x.pair.y += x.pair.x; return x; }
Large large_next(Large x) { return (Large){x.a + 1, x.b + 2, x.c + 3, x.d + 4}; }
void small_fill(Small *out, uint8_t tag, int32_t value) { *out = (Small){tag, value}; }
int32_t small_sum(const Small *xs, int32_t count) {
    int32_t total = 0;
    for (int32_t i = 0; i < count; ++i) total += xs[i].value;
    return total;
}
int32_t *new_int(int32_t value) {
    int32_t *p = malloc(sizeof *p);
    if (p) *p = value;
    return p;
}
void delete_int(int32_t *p) { free(p); }
Two two_next(Two x) { return (Two){{x.values[0] + 1, x.values[1] + 2}}; }
Mixed mixed_next(Mixed x) { return (Mixed){x.id + 2, x.weight * 2}; }
Triple triple_next(Triple x) { return (Triple){x.x + 1, x.y + 2, x.z + 3}; }
int64_t small_after_six(int64_t a, int64_t b, int64_t c,
                        int64_t d, int64_t e, int64_t f, Small x) {
    return a + b + c + d + e + f + x.value;
}
