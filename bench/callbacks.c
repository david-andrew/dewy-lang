#include "harness.h"
static int64_t visit(const int64_t *values, int64_t threshold, int64_t bias) {
    int64_t total = 0;
    for (int j = 0; j < 4; j++)
        if (values[j] > threshold) total += values[j] * 3 + bias;
    return total;
}
static int64_t kernel(const int64_t *values, int64_t count) {
    int64_t total = 0;
    for (int64_t i = 0; i < count; i++)
        total += visit(values, i % 8, i % 127);
    return total;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    int64_t values[] = {1, 3, 5, 7};
    int64_t start = clock_now();
    int64_t result = kernel(values, count);
    report(result, clock_now() - start);
    return 0;
}
