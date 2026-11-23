#include "harness.h"

static void insertion_sort(int64_t *a, int64_t lo, int64_t hi) {
    for (int64_t i = lo + 1; i <= hi; i++) {
        int64_t key = a[i];
        int64_t j = i - 1;
        while (j >= lo && a[j] > key) {
            a[j + 1] = a[j];
            j--;
        }
        a[j + 1] = key;
    }
}

static void qsort_range(int64_t *a, int64_t lo, int64_t hi) {
    while (hi - lo > 16) {
        int64_t mid = lo + ((hi - lo) >> 1);
        if (a[mid] < a[lo]) { int64_t t = a[lo]; a[lo] = a[mid]; a[mid] = t; }
        if (a[hi] < a[lo]) { int64_t t = a[lo]; a[lo] = a[hi]; a[hi] = t; }
        if (a[hi] < a[mid]) { int64_t t = a[mid]; a[mid] = a[hi]; a[hi] = t; }
        int64_t pivot = a[mid];
        int64_t i = lo, j = hi;
        for (;;) {
            while (a[i] < pivot) i++;
            while (a[j] > pivot) j--;
            if (i >= j) break;
            int64_t t = a[i]; a[i] = a[j]; a[j] = t;
            i++;
            j--;
        }
        if (j - lo < hi - j) {
            qsort_range(a, lo, j);
            lo = j + 1;
        } else {
            qsort_range(a, j + 1, hi);
            hi = j;
        }
    }
    if (hi > lo) insertion_sort(a, lo, hi);
}

static int64_t kernel(int64_t *data, int64_t n) {
    if (n > 1) qsort_range(data, 0, n - 1);
    int64_t hash = 7, ordered = 1;
    for (int64_t i = 0; i < n; i++) {
        if (i > 0 && data[i - 1] > data[i]) ordered = 0;
        if (i % 16 == 0) hash = mix(hash, data[i] % 1000003);
    }
    return mix(hash, ordered);
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 500000);
    int64_t *data = malloc((size_t)(count > 0 ? count : 1) * sizeof *data);
    int64_t seed = 1337;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        data[i] = seed ^ ((i * 2654435761LL) % 2147483648LL);
    }
    int64_t started = clock_now();
    int64_t result = kernel(data, count);
    report(result, clock_now() - started);
    free(data);
    return 0;
}
