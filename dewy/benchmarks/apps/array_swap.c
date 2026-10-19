#include "harness.h"
static int64_t kernel(int64_t *values, int64_t count) {
    int64_t state = 305419896;
    for (int64_t i = 0; i < count; ++i) {
        state = (state * 1664525 + 1013904223) & 2147483647;
        int64_t left_index = (state >> 8) & 1023;
        state = (state * 1664525 + 1013904223) & 2147483647;
        int64_t right_index = (state >> 8) & 1023;
        int64_t kept = values[left_index];
        values[left_index] = values[right_index];
        values[right_index] = kept;
    }
    int64_t hash = 0;
    for (int64_t i = 0; i < 1024; ++i) hash = mix(hash, values[i]);
    return hash;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 10000000);
    int64_t values[1024];
    for (int64_t i = 0; i < 1024; ++i) values[i] = i;
    int64_t started = clock_now();
    int64_t result = kernel(values, count);
    report(result, clock_now() - started);
    return 0;
}
