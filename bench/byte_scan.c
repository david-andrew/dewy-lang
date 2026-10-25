#include "harness.h"
#include <string.h>

static int64_t scan(const unsigned char *p, size_t n, unsigned char c) {
    size_t i = 0;
    while (i < n && p[i] != c) ++i;
    return i == n ? -1 : (int64_t)i;
}

static int64_t kernel(const unsigned char *p, size_t n, int64_t count) {
    int64_t result = 0;
    for (int64_t i = 0; i < count; ++i) {
        result += scan(p, n, i % 2 == 0 ? '\n' : '!');
    }
    return result;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 20000);
    unsigned char text[4096];
    memset(text, 'a', sizeof text - 1);
    text[sizeof text - 1] = '\n';
    int64_t started = clock_now();
    int64_t result = kernel(text, sizeof text, count);
    report(result, clock_now() - started);
    return 0;
}
