#include "harness.h"

/* C has no dictionary: this is the usual hand-written open-addressing table
   from 64-bit keys to 64-bit values, grown at 3/4 full. */
typedef struct { int64_t *keys, *values; uint8_t *used; int64_t capacity, count; } Table;

static uint64_t spread(int64_t key) {
    uint64_t h = (uint64_t)key * 0x9E3779B97F4A7C15ull;
    return h ^ (h >> 32);
}
static void table_init(Table *t, int64_t capacity) {
    t->capacity = capacity;
    t->count = 0;
    t->keys = malloc(sizeof(int64_t) * capacity);
    t->values = malloc(sizeof(int64_t) * capacity);
    t->used = calloc(capacity, 1);
}
static int64_t *table_find(Table *t, int64_t key) {
    uint64_t i = spread(key) & (t->capacity - 1);
    while (t->used[i]) {
        if (t->keys[i] == key) return &t->values[i];
        i = (i + 1) & (t->capacity - 1);
    }
    return NULL;
}
static void table_set(Table *t, int64_t key, int64_t value);
static void table_grow(Table *t) {
    Table old = *t;
    table_init(t, old.capacity * 2);
    for (int64_t i = 0; i < old.capacity; i++)
        if (old.used[i]) table_set(t, old.keys[i], old.values[i]);
    free(old.keys);
    free(old.values);
    free(old.used);
}
static void table_set(Table *t, int64_t key, int64_t value) {
    if ((t->count + 1) * 4 > t->capacity * 3) table_grow(t);
    uint64_t i = spread(key) & (t->capacity - 1);
    while (t->used[i]) {
        if (t->keys[i] == key) {
            t->values[i] = value;
            return;
        }
        i = (i + 1) & (t->capacity - 1);
    }
    t->used[i] = 1;
    t->keys[i] = key;
    t->values[i] = value;
    t->count++;
}

#define DEGREE 4

static int64_t label(int64_t index) { return index * 7919 + 13; }

/* `edges` maps a label to the offset of its DEGREE targets in `targets`. */
static int64_t kernel(Table *edges, const int64_t *targets, int64_t count) {
    Table distance;
    table_init(&distance, 16);
    int64_t *queue = malloc(sizeof(int64_t) * (count + 1));
    int64_t head = 0, tail = 0, hash = 11;
    queue[tail++] = label(0);
    table_set(&distance, label(0), 0);
    while (head < tail) {
        int64_t node = queue[head++];
        int64_t *reached = table_find(&distance, node);
        int64_t *offset = table_find(edges, node);
        if (!reached || !offset) continue;
        int64_t depth = *reached;
        hash = mix(hash, node % 1000 + depth);
        for (int64_t j = 0; j < DEGREE; j++) {
            int64_t target = targets[*offset + j];
            if (!table_find(&distance, target)) {
                table_set(&distance, target, depth + 1);
                queue[tail++] = target;
            }
        }
    }
    return mix(hash, tail);
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 200000);
    Table edges;
    table_init(&edges, 16);
    int64_t *targets = malloc(sizeof(int64_t) * DEGREE * (count + 1));
    int64_t seed = 4242;
    for (int64_t i = 0; i < count; i++) {
        targets[i * DEGREE] = label((i + 1) % count);
        for (int64_t j = 1; j < DEGREE; j++) {
            seed = lcg(seed);
            targets[i * DEGREE + j] = label(seed % count);
        }
        table_set(&edges, label(i), i * DEGREE);
    }
    int64_t started = clock_now();
    int64_t result = kernel(&edges, targets, count);
    report(result, clock_now() - started);
    return 0;
}
