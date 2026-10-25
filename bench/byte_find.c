#include "harness.h"
#include <string.h>

static int64_t kernel(const unsigned char *p, size_t n, int64_t count) {
    int64_t result = 0;
    for (int64_t i = 0; i < count; ++i) {
        const unsigned char *at = memchr(p, i % 2 == 0 ? '\n' : '!', n);
        result += at ? at - p : -1;
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
