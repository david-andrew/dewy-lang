#include "harness.h"
#include <string.h>

typedef struct { unsigned char *data; size_t length; } String;

static String make_key(int64_t value) {
    unsigned char *p = malloc(9);
    memcpy(p, "key-0000", 9);
    for (int i = 0; i < 4; ++i) {
        p[7 - i] = 48 + value % 10;
        value /= 10;
    }
    return (String){p, 8};
}

static int compare(String a, String b) {
    size_t n = a.length < b.length ? a.length : b.length;
    int c = memcmp(a.data, b.data, n);
    if (c) return c;
    return (a.length > b.length) - (a.length < b.length);
}

static int64_t find_key(const String *keys, int64_t length, String key) {
    int64_t lo = 0, hi = length;
    while (lo < hi) {
        int64_t mid = lo + (hi - lo) / 2;
        if (compare(keys[mid], key) < 0) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

static int64_t kernel(const String *keys, const String *queries, int64_t count) {
    int64_t result = 0;
    for (int64_t i = 0; i < count; ++i)
        result += find_key(keys, 1024, queries[(i * 17) % 1024]);
    return result;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    String keys[1024], queries[1024];
    for (int i = 0; i < 1024; ++i) {
        keys[i] = make_key(i * 2);
        queries[i] = make_key(i * 2 + i % 2);
    }
    int64_t started = clock_now();
    int64_t result = kernel(keys, queries, count);
    report(result, clock_now() - started);
    for (int i = 0; i < 1024; ++i) {
        free(keys[i].data);
        free(queries[i].data);
    }
    return 0;
}
