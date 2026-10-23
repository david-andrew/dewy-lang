#include "harness.h"
#include <string.h>

typedef struct {
    uint8_t **names;
    int64_t *lengths, *hashes, *slots, count, mask;
} NameTable;

static int64_t hash_bytes(const uint8_t *p, int64_t n) {
    uint64_t h = (uint64_t)n * 0x9E3779B97F4A7C15ull;
    int64_t i = 0;
    while (i + 8 < n) {
        uint64_t w;
        memcpy(&w, p + i, 8);
        h = (h ^ w) * 0xBF58476D1CE4E5B9ull;
        h ^= h >> 31;
        i += 8;
    }
    while (i < n) {
        h = (h ^ p[i]) * 0x100000001B3ull;
        i++;
    }
    h *= 0xBF58476D1CE4E5B9ull;
    return (int64_t)((h ^ (h >> 32)) >> 1);
}

static int64_t intern(NameTable *t, const uint8_t *p, int64_t n) {
    int64_t h = hash_bytes(p, n), at = h & t->mask;
    while (t->slots[at] != 0) {
        int64_t id = t->slots[at] - 1;
        if (t->hashes[id] == h && t->lengths[id] == n && memcmp(t->names[id], p, n) == 0) return id;
        at = (at + 1) & t->mask;
    }
    int64_t id = t->count++;
    t->names[id] = malloc(n + 1);
    memcpy(t->names[id], p, n);
    t->lengths[id] = n;
    t->hashes[id] = h;
    t->slots[at] = id + 1;
    return id;
}

static int64_t kernel(const uint8_t *text, int64_t length) {
    NameTable t = {malloc(16384 * sizeof(uint8_t *)), malloc(16384 * 8), malloc(16384 * 8), calloc(16384, 8), 0, 16383};
    int64_t result = 7, i = 0;
    while (i < length) {
        int64_t start = i;
        while (i < length && text[i] != 32) i++;
        result = mix(result, intern(&t, text + start, i - start));
        i++;
    }
    return mix(result, t.count);
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    uint8_t *text = malloc(count * 13 + 8);
    int64_t length = 0, seed = 99;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        int64_t word = seed % 5003, size = word % 12 + 1, letters = word;
        for (int64_t j = 0; j < size; j++) {
            text[length++] = 97 + letters % 26;
            letters = letters / 3 + j;
        }
        text[length++] = 32;
    }
    int64_t started = clock_now();
    int64_t result = kernel(text, length);
    report(result, clock_now() - started);
    return 0;
}
