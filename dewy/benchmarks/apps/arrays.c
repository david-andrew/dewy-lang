#include "harness.h"

static void prefix_sums(int64_t *values, int64_t count) {
    int64_t total = 0;
    for (int64_t i = 0; i < count; i++) {
        total = (total + values[i]) % 1000000007;
        values[i] = total;
    }
}
static int64_t sieve(int64_t *flags, int64_t count) {
    int64_t found = 0;
    for (int64_t i = 2; i < count; i++) {
        if (flags[i] == 1) {
            found++;
            for (int64_t j = i + i; j < count; j += i) flags[j] = 0;
        }
    }
    return found;
}
static void reverse(int64_t *values, int64_t count) {
    int64_t low = 0, high = count;
    while (low + 1 < high) {
        high--;
        int64_t kept = values[low];
        values[low] = values[high];
        values[high] = kept;
        low++;
    }
}
static int64_t kernel(int64_t *values, int64_t *flags, int64_t count) {
    prefix_sums(values, count);
    reverse(values, count);
    int64_t hash = sieve(flags, count);
    for (int64_t i = 0; i < count; i++) hash = mix(hash, values[i]);
    return hash;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    int64_t *values = malloc(sizeof(int64_t) * (count + 1));
    int64_t *flags = malloc(sizeof(int64_t) * (count + 1));
    int64_t seed = 12345;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        values[i] = seed % 1000;
        flags[i] = 1;
    }
    int64_t started = clock_now();
    int64_t result = kernel(values, flags, count);
    report(result, clock_now() - started);
    return 0;
}
