#include "harness.h"
#include <string.h>

/* A bump allocator reset each round, and growable arrays in it that double from 4,
   as Dewy's do. */
typedef struct { char *base, *cursor, *end; } Arena;
static void *arena_alloc(Arena *a, size_t n) {
    n = (n + 15) & ~(size_t)15;
    if (a->cursor + n > a->end) { fprintf(stderr, "arena full\n"); exit(1); }
    void *p = a->cursor;
    a->cursor += n;
    return p;
}
typedef struct { int64_t *data; int64_t length, capacity; } Vec;
static void vec_push(Arena *a, Vec *v, int64_t x) {
    if (v->length == v->capacity) {
        int64_t capacity = v->capacity ? v->capacity * 2 : 4;
        int64_t *data = arena_alloc(a, (size_t)capacity * sizeof *data);
        if (v->length) memcpy(data, v->data, (size_t)v->length * sizeof *data);
        v->data = data;
        v->capacity = capacity;
    }
    v->data[v->length++] = x;
}
typedef struct { Vec *data; int64_t length, capacity; } Table;
static void table_push(Arena *a, Table *t, Vec row) {
    if (t->length == t->capacity) {
        int64_t capacity = t->capacity ? t->capacity * 2 : 4;
        Vec *data = arena_alloc(a, (size_t)capacity * sizeof *data);
        if (t->length) memcpy(data, t->data, (size_t)t->length * sizeof *data);
        t->data = data;
        t->capacity = capacity;
    }
    t->data[t->length++] = row;
}

enum { ROWS = 1000 };

static int64_t round_total(Arena *a, int64_t seed) {
    Table table = {0};
    for (int64_t r = 0; r < ROWS; r++) {
        Vec row = {0};
        for (int c = 0; c < 8; c++) {
            seed = lcg(seed);
            vec_push(a, &row, seed % 1000);
        }
        table_push(a, &table, row);
    }
    int64_t total = 0;
    for (int64_t r = 0; r < table.length; r++) {
        int64_t best = 0;
        for (int64_t c = 0; c < table.data[r].length; c++)
            if (table.data[r].data[c] > best) best = table.data[r].data[c];
        total += best;
    }
    return total;
}

static int64_t kernel(int64_t rounds) {
    Arena a;
    size_t size = 1 << 22;
    a.base = a.cursor = malloc(size);
    a.end = a.base + size;
    int64_t hash = 7;
    for (int64_t k = 0; k < rounds; k++) {
        hash = mix(hash, round_total(&a, k));
        a.cursor = a.base;
    }
    free(a.base);
    return hash;
}

int main(int argc, char **argv) {
    int64_t rounds = size_argument(argc, argv, 1000);
    int64_t started = clock_now();
    int64_t result = kernel(rounds);
    report(result, clock_now() - started);
    return 0;
}
