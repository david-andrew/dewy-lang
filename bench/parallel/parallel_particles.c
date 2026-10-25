#include "../harness.h"
#include <math.h>
#include <omp.h>

typedef struct { double x, y, vx, vy; } Particle;
static Particle step(Particle p, const Particle *others, int64_t n) {
    double ax = 0.0, ay = 0.0;
    for (int64_t i = 0; i < n; i++) {
        double dx = others[i].x - p.x, dy = others[i].y - p.y;
        double r2 = dx*dx + dy*dy + 0.25;
        double scale = 0.001 / (r2 * sqrt(r2));
        ax += dx * scale;
        ay += dy * scale;
    }
    p.vx += ax * 0.01; p.vy += ay * 0.01;
    p.x += p.vx * 0.01; p.y += p.vy * 0.01;
    return p;
}
int main(int argc, char **argv) {
    int64_t n = size_argument(argc, argv, 2048);
    Particle *a = malloc(n * sizeof(*a));
    for (int64_t i = 0; i < n; i++) a[i] = (Particle){i%32, i/32, 0, 0};
    int64_t t = clock_now();
    for (int frame = 0; frame < 4; frame++) {
        /* Match the value-returning Dewy map's allocation per frame. */
        Particle *b = malloc(n * sizeof(*b));
#pragma omp parallel for if(argc<=2) schedule(static)
        for (int64_t i = 0; i < n; i++) b[i] = step(a[i], a, n);
        free(a); a = b;
    }
    int64_t elapsed = clock_now()-t, checksum = 0;
    for (int64_t i = 0; i < n; i++) {
        checksum += (int64_t)(a[i].x*1000000.0);
        checksum += (int64_t)(a[i].y*1000000.0);
        checksum += (int64_t)(a[i].vx*1000000.0);
        checksum += (int64_t)(a[i].vy*1000000.0);
    }
    report(checksum, elapsed);
    free(a);
}
