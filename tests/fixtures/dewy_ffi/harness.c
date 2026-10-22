/* A small C library a Dewy program binds with `$extern` and calls back with `$export`. */
#include <stddef.h>
#include <stdint.h>

int32_t apply_twice(int32_t (*f)(int32_t), int32_t x) { return f(f(x)); }

int64_t fold(const int64_t *xs, int32_t n, int64_t (*step)(int64_t, int64_t), int64_t start) {
    for (int32_t i = 0; i < n; i++) start = step(start, xs[i]);
    return start;
}

const char *greeting(void) { return "hello from C"; }

int64_t *find(int64_t *xs, int32_t n, int64_t value) {
    for (int32_t i = 0; i < n; i++)
        if (xs[i] == value) return xs + i;
    return NULL;
}

void scale(double *out, int32_t n, double by) {
    for (int32_t i = 0; i < n; i++) out[i] *= by;
}

int32_t is_null(const void *p) { return p == NULL; }
