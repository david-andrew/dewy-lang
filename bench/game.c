#include "harness.h"

typedef struct { double x, velocity; int64_t hits; } Ball;

static Ball tick(Ball state, double dt) {
    Ball next = state;
    next.x += next.velocity * dt;
    if (next.x > 10.0) {
        next.x = 20.0 - next.x;
        next.velocity = -next.velocity;
        next.hits++;
    }
    if (next.x < 0.0) {
        next.x = -next.x;
        next.velocity = -next.velocity;
        next.hits++;
    }
    return next;
}

static Ball simulate(Ball start, int64_t frames) {
    Ball state = start;
    for (int64_t frame = 0; frame < frames; frame++) state = tick(state, 0.125);
    return state;
}

int main(int argc, char **argv) {
    int64_t frames = size_argument(argc, argv, 5000000);
    int64_t started = clock_now();
    Ball final = simulate((Ball){1.0, 4.0, 0}, frames);
    int64_t result = mix(mix((int64_t)(final.x * 2.0), (int64_t)final.velocity), final.hits);
    report(result, clock_now() - started);
    return 0;
}
