/* Shared by the C counterparts: the same size argument, clock and checksum
   step as harness.dewy. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static int64_t size_argument(int argc, char **argv, int64_t fallback) {
    if (argc < 2) return fallback;
    int64_t value = 0;
    for (const char *p = argv[1]; *p; p++) {
        if (*p < '0' || *p > '9') return fallback;
        value = value * 10 + (*p - '0');
        if (value > 1000000000) return fallback;
    }
    return value;
}

static int64_t clock_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

static inline int64_t mix(int64_t hash, int64_t value) { return (hash * 31 + value) % 1000000007; }

static inline int64_t lcg(int64_t seed) { return (seed * 1103515245 + 12345) % 2147483648; }

static void report(int64_t result, int64_t nanoseconds) {
    printf("%lld %lld\n", (long long)result, (long long)nanoseconds);
}
