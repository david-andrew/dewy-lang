#include "harness.h"
#include <string.h>

#define VOCAB 65536
/* Open addressing with dense entries for insertion-order scans. Both tables
   grow at 3/4 full, matching Dewy. Strings use content hashing and equality. */
typedef struct { const char *word; int64_t id, value; uint64_t hash; } Entry;
typedef struct { Entry *entries; int64_t *slots, capacity, count, allocated; int strings; } Table;
static uint64_t hash_id(uint64_t h) {
    h = (h ^ (h >> 33)) * UINT64_C(0xff51afd7ed558ccd);
    h = (h ^ (h >> 33)) * UINT64_C(0xc4ceb9fe1a85ec53);
    return h ^ (h >> 33);
}
static uint64_t hash_word(const char *s) {
    uint64_t h = UINT64_C(14695981039346656037);
    while (*s) { h ^= (unsigned char)*s++; h *= UINT64_C(1099511628211); }
    return h ^ (h >> 29);
}
static Entry *find(Table *t, const char *word, int64_t id, uint64_t h) {
    if (!t->capacity) return NULL;
    int64_t i = h & (t->capacity - 1);
    while (t->slots[i]) {
        Entry *e = &t->entries[t->slots[i] - 1];
        if (e->hash == h && (t->strings ? !strcmp(e->word, word) : e->id == id)) return e;
        i = (i + 1) & (t->capacity - 1);
    }
    return NULL;
}
static void insert(Table *t, const char *word, int64_t id, uint64_t h) {
    if (t->count == t->allocated) {
        t->allocated = t->allocated ? t->allocated * 2 : 8;
        t->entries = realloc(t->entries, t->allocated * sizeof(Entry));
    }
    t->entries[t->count++] = (Entry){word, id, 1, h};
    if (t->count * 4 > t->capacity * 3) {
        t->capacity = t->capacity ? t->capacity * 2 : 8;
        free(t->slots);
        t->slots = calloc(t->capacity, sizeof(int64_t));
        for (int64_t e = 0; e < t->count; e++) {
            int64_t i = t->entries[e].hash & (t->capacity - 1);
            while (t->slots[i]) i = (i + 1) & (t->capacity - 1);
            t->slots[i] = e + 1;
        }
    } else {
        int64_t i = h & (t->capacity - 1);
        while (t->slots[i]) i = (i + 1) & (t->capacity - 1);
        t->slots[i] = t->count;
    }
}
static int64_t kernel(char words[VOCAB][24], int64_t count) {
    Table counts = {.strings=1}, ids = {0};
    int64_t seed = 4242, hits = 0;
    for (int64_t n = 0; n < count; n++) {
        seed = lcg(seed);
        int64_t index = (seed / 32768) % VOCAB, id = index * 7919 + 13;
        const char *word = words[index];
        uint64_t wh = hash_word(word), ih = hash_id(id);
        if (find(&counts, word, 0, wh)) find(&counts, word, 0, wh)->value++;
        else insert(&counts, word, 0, wh);
        if (find(&ids, NULL, id, ih)) find(&ids, NULL, id, ih)->value++;
        else insert(&ids, NULL, id, ih);
        const char *next = words[(index + 1) % VOCAB];
        hits += find(&counts, next, 0, hash_word(next)) != NULL;
        hits += find(&ids, NULL, id + 1, hash_id(id + 1)) != NULL;
    }
    int64_t result = hits;
    for (int64_t i = 0; i < counts.count; i++) {
        Entry *e = &counts.entries[i];
        result = mix(result, find(&counts, e->word, 0, hash_word(e->word))->value);
    }
    for (int64_t i = 0; i < counts.count; i++)
        result = mix(result, counts.entries[i].value + strlen(counts.entries[i].word));
    for (int64_t i = 0; i < ids.count; i++) {
        Entry *e = &ids.entries[i];
        result = mix(result, e->id % 1000 + find(&ids, NULL, e->id, hash_id(e->id))->value);
    }
    for (int64_t i = 0; i < ids.count; i++)
        result = mix(result, ids.entries[i].id % 1000 + ids.entries[i].value);
    free(counts.entries); free(counts.slots); free(ids.entries); free(ids.slots);
    return result;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 2000000);
    char (*words)[24] = malloc(VOCAB * sizeof(*words));
    for (int64_t i = 0; i < VOCAB; i++) snprintf(words[i], 24, "word-%lld", (long long)i);
    int64_t started = clock_now();
    int64_t result = kernel(words, count);
    report(result, clock_now() - started);
    free(words);
    return 0;
}
