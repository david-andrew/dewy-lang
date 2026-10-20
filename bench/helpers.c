#include "harness.h"

static int64_t gcd(int64_t a, int64_t b) {
    while (b != 0) {
        int64_t rest = a % b;
        a = b;
        b = rest;
    }
    return a;
}
static int64_t collatz(int64_t value) {
    int64_t steps = 0;
    while (value > 1 && steps < 200) {
        value = value % 2 == 0 ? value / 2 : 3 * value + 1;
        steps++;
    }
    return steps;
}
static int64_t clamp(int64_t value, int64_t low, int64_t high) {
    return value < low ? low : value > high ? high : value;
}

static int64_t kernel(int64_t count) {
    int64_t hash = 7;
    for (int64_t i = 1; i <= count; i++) {
        hash = mix(hash, gcd(i, 360360));
        hash = mix(hash, collatz(i));
        hash = mix(hash, clamp(i % 1000 - 500, -100, 100) + 100);
    }
    return hash;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 200000);
    int64_t started = clock_now();
    int64_t result = kernel(count);
    report(result, clock_now() - started);
    return 0;
}
