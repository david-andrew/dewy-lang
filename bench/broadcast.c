#include "harness.h"
#define N 256
static int64_t *values(int64_t count, int64_t seed) {
    int64_t *out = malloc(count * sizeof(*out));
    for (int64_t i = 0; i < count; i++) {seed = lcg(seed); out[i] = seed % 1000 - 500;}
    return out;
}
static int64_t kernel(int64_t rounds, const int64_t *m, const int64_t *bias, const int64_t *shift) {
    int64_t total = 0;
    int64_t *h = malloc(N * N * sizeof(*h)), *g = malloc(N * N * sizeof(*g));
    for (int64_t r = 0; r < rounds; r++) {
        int64_t k = r % 7;
        for (int64_t i = 0; i < N; i++)
            for (int64_t j = 0; j < N; j++) {
                int64_t v = m[i * N + j] + bias[j] + shift[i] - k;
                h[i * N + j] = v > 0 ? v : 0;
            }
        for (int64_t i = 0; i < N * N; i++) g[i] = h[i] * m[i] - h[i];
        int64_t s = 0;
        for (int64_t i = 0; i < N * N; i++) s += g[i];
        total += s;
    }
    free(h); free(g);
    return total;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000);
    int64_t *m = values(N * N, 1), *bias = values(N, 2), *shift = values(N, 3);
    int64_t start = clock_now();
    int64_t result = kernel(count, m, bias, shift);
    report(result, clock_now() - start);
    free(m); free(bias); free(shift);
    return 0;
}
