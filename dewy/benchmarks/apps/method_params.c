#include "harness.h"
typedef struct { int64_t *weights; int64_t bias; } Row;
static int64_t weight(const int64_t *values, int64_t at) { return values[at]; }
static int64_t score(Row row, int64_t at) { return weight(row.weights, at) + row.bias; }
static int64_t kernel(const Row *rows, int64_t count) {
    int64_t total = 0;
    for (int64_t i = 0; i < count; i++) total += score(rows[i % 128], i % 4);
    return total;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 10000000);
    Row rows[128]; int64_t values[128][4];
    for (int64_t i = 0; i < 128; i++) {
        for (int64_t j = 0; j < 4; j++) values[i][j] = i + j;
        rows[i] = (Row){values[i], i * 3};
    }
    int64_t start = clock_now();
    int64_t result = kernel(rows, count);
    report(result, clock_now() - start);
    return 0;
}
