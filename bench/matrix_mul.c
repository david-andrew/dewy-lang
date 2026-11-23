#include "harness.h"

enum { DIM = 64, CELLS = 4096 };

static void fill_matrix(double *m, int64_t seed) {
    for (int64_t i = 0; i < CELLS; i++) {
        seed = lcg(seed);
        m[i] = (double)((seed % 17) - 8) * 0.25;
    }
}

static void matmul_block(const double *a, const double *b, double *c) {
    for (int64_t i = 0; i < DIM; i++) {
        int64_t row = i * DIM;
        for (int64_t j = 0; j < DIM; j++) c[row + j] = 0.0;
        for (int64_t k = 0; k < DIM; k++) {
            double aik = a[row + k];
            int64_t brow = k * DIM;
            for (int64_t j = 0; j < DIM; j++)
                c[row + j] = c[row + j] + aik * b[brow + j];
        }
    }
}

static int64_t kernel(double *a, const double *b, int64_t count) {
    double c[CELLS];
    int64_t rounds = count < 64 ? 1 : count / 64;
    int64_t hash = 17;
    for (int64_t r = 0; r < rounds; r++) {
        matmul_block(a, b, c);
        double diag = c[(r % DIM) * DIM + (r % DIM)];
        int64_t scaled = (int64_t)(diag * 16.0);
        int64_t v = scaled < 0 ? -scaled : scaled;
        hash = mix(hash, v % 1000003);
        int64_t idx = r % CELLS;
        double cur = a[idx];
        a[idx] = cur >= 2.0 ? -2.0 : cur + 0.25;
    }
    return hash;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 64000);
    double a[CELLS], b[CELLS];
    fill_matrix(a, 1234);
    fill_matrix(b, 5678);
    int64_t started = clock_now();
    int64_t result = kernel(a, b, count);
    report(result, clock_now() - started);
    return 0;
}
