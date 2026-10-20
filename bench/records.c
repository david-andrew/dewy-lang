#include "harness.h"

typedef struct { int64_t x, y, dx, dy; } Particle;

#define BOX 4096

static void step(Particle *particles, int64_t count) {
    for (int64_t i = 0; i < count; i++) {
        Particle *p = &particles[i];
        int64_t x = p->x + p->dx;
        int64_t y = p->y + p->dy;
        if (x < 0 || x >= BOX) {
            p->dx = -p->dx;
            x = p->x;
        }
        if (y < 0 || y >= BOX) {
            p->dy = -p->dy;
            y = p->y;
        }
        p->x = x;
        p->y = y;
    }
}
static int64_t kernel(Particle *particles, int64_t count, int64_t rounds) {
    for (int64_t round = 0; round < rounds; round++) step(particles, count);
    int64_t hash = 3;
    for (int64_t i = 0; i < count; i++) hash = mix(mix(hash, particles[i].x), particles[i].y);
    return hash;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 100000);
    Particle *particles = malloc(sizeof(Particle) * (count + 1));
    int64_t seed = 2024;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        particles[i].x = seed % BOX;
        seed = lcg(seed);
        particles[i].y = seed % BOX;
        seed = lcg(seed);
        particles[i].dx = seed % 17 - 8;
        particles[i].dy = (seed / 32) % 17 - 8;
    }
    int64_t started = clock_now();
    int64_t result = kernel(particles, count, 50);
    report(result, clock_now() - started);
    return 0;
}
