#include <string.h>
#include "harness.h"

typedef struct { int64_t x, y, dx, dy; } Particle;

/* A growable array of fixed-size elements, doubling like Dewy's. */
typedef struct { char *data; int64_t length, capacity; } Array;

static void *push_slot(Array *a, int64_t size) {
    if (a->length == a->capacity) {
        a->capacity = a->capacity ? a->capacity * 2 : 4;
        a->data = realloc(a->data, a->capacity * size);
    }
    return a->data + size * a->length++;
}

static int64_t kernel(int64_t count) {
    Array particles = {0}, numbers = {0}, names = {0};
    int64_t seed = 777;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        Particle p = {seed % 4096, i, seed % 17 - 8, (seed / 32) % 17 - 8};
        *(Particle *)push_slot(&particles, sizeof(Particle)) = p;
        *(int64_t *)push_slot(&numbers, sizeof(int64_t)) = seed % 1000;
        *(const char **)push_slot(&names, sizeof(char *)) = seed % 3 == 0 ? "fizz" : "buzz!";
    }
    /* a sample of the elements, so the pushes dominate */
    int64_t hash = numbers.length + particles.length + names.length;
    for (int64_t j = 0; j < count; j += 61) {
        Particle *p = (Particle *)particles.data + j;
        hash = mix(hash, p->x + p->dy + ((int64_t *)numbers.data)[j] + (int64_t)strlen(((const char **)names.data)[j]));
    }
    return hash;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    int64_t started = clock_now();
    int64_t result = kernel(count);
    report(result, clock_now() - started);
    return 0;
}
