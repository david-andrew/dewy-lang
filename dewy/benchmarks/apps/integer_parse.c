#include "harness.h"
#include <errno.h>
static int64_t kernel(char texts[32][32], int64_t count) {
    int64_t checksum = 0;
    for (int64_t i = 0; i < count; ++i) {
        char *end;
        errno = 0;
        int64_t value = strtoll(texts[i & 31], &end, 10);
        if (errno || *end) return -1;
        checksum += value & 65535;
    }
    return checksum;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 2000000);
    char texts[32][32];
    for (int64_t i = 0; i < 32; ++i) {
        int64_t value = 123456789012345 + i * 23456789;
        snprintf(texts[i], sizeof(texts[i]), "%lld", (long long)(i % 2 ? -value : value));
    }
    int64_t started = clock_now();
    int64_t result = kernel(texts, count);
    report(result, clock_now() - started);
    return 0;
}
