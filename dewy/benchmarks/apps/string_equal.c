#include "harness.h"
#include <string.h>

typedef struct { unsigned char *data; size_t length; } String;
typedef struct { String left, right; } Pair;

static void generate(Pair *pairs) {
    for (int64_t i = 0; i < 128; ++i) {
        size_t n = (i * 17) % 65;
        pairs[i].left = (String){malloc(n ? n : 1), n};
        pairs[i].right = (String){malloc(n ? n : 1), n};
        for (size_t j = 0; j < n; ++j) {
            pairs[i].left.data[j] = (i + j * 7) % 128;
            pairs[i].right.data[j] = pairs[i].left.data[j];
        }
        if (n && i % 3 == 0) {
            size_t at = (i * 13) % n;
            pairs[i].right.data[at] = (pairs[i].right.data[at] + 1) % 128;
        }
    }
}

static int64_t kernel(const Pair *pairs, int64_t count) {
    int64_t result = 0;
    for (int64_t i = 0; i < count; ++i) {
        const Pair *p = &pairs[i % 128];
        int equal = p->left.length == p->right.length &&
            memcmp(p->left.data, p->right.data, p->left.length) == 0;
        result += equal ? i : -i;
    }
    return result;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 10000000);
    Pair pairs[128];
    generate(pairs);
    int64_t started = clock_now();
    int64_t result = kernel(pairs, count);
    report(result, clock_now() - started);
    for (int i = 0; i < 128; ++i) {
        free(pairs[i].left.data);
        free(pairs[i].right.data);
    }
    return 0;
}
