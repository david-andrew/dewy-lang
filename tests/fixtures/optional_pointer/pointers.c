/* The C side of test_optional_pointer.py: nullable pointers filled, read and
 * returned by C, with no C library (the same file is cross-built for aarch64). */
#include <stdint.h>

typedef struct { int32_t tag; int32_t *first; int32_t *second; } Pair;

static int32_t values[4] = {11, 22, 33, 44};

/* a T** out-parameter: the slot gets the address of the wanted value, or NULL */
int32_t find_value(int32_t want, int32_t **out) {
    for (int i = 0; i < 4; i++)
        if (values[i] == want) { *out = &values[i]; return 1; }
    *out = 0;
    return 0;
}

/* an array of nullable pointers: even slots point at values, odd slots are NULL */
void fill_slots(int32_t **out, int64_t n) {
    for (int64_t i = 0; i < n; i++) out[i] = (i % 2 == 0) ? &values[i % 4] : 0;
}

int32_t read_or_minus_one(int32_t *p) { return p ? *p : -1; }

/* the successor of p in values, NULL after the last; NULL starts the walk */
int32_t *next_value(int32_t *p) {
    if (!p) return &values[0];
    if (p == &values[3]) return 0;
    return p + 1;
}

/* a record with nullable pointer fields, filled and read by C */
void fill_pair(Pair *out, int32_t tag) { out->tag = tag; out->first = &values[1]; out->second = 0; }

int32_t pair_sum(const Pair *p) {
    return p->tag + (p->first ? *p->first : 0) + (p->second ? *p->second : 0);
}

/* a callback taking and returning a nullable pointer */
int32_t *apply(int32_t *(*f)(int32_t *), int32_t *p) { return f(p); }
