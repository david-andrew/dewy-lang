#include "harness.h"
static int64_t *left, *right;
static int64_t kernel(int64_t rounds) {
    int64_t total = 0;
    int64_t shift = rounds % 2 + 1;
    for (int64_t r = 0; r < rounds; r++) {
        for (int64_t i = 0; i < 1024; i++) total += (left[i+shift] + right[i+shift]) ^ r;
    }
    return total;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 100000);
    left = malloc(1026 * sizeof(*left)); right = malloc(1026 * sizeof(*right));
    for (int64_t i = 0; i < 1026; i++) {left[i] = i; right[i] = i * 3 + 1;}
    int64_t start = clock_now();
    int64_t result = kernel(count);
    report(result, clock_now() - start);
    free(left); free(right);
    return 0;
}
