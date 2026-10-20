#include "harness.h"

static int64_t classify(int64_t code) {
    switch (code) {
        case 0: return 17;
        case 1: return 4;
        case 2: return 91;
        case 3: return 6;
        case 4: return 22;
        case 5: return 37;
        case 6: return 8;
        case 7: return 53;
        case 8: return 11;
        case 9: return 68;
        case 10: return 2;
        case 11: return 79;
        case 12: return 41;
        case 13: return 13;
        case 14: return 97;
        case 15: return 29;
        case 16: return 59;
        case 17: return 3;
        case 18: return 83;
        case 19: return 31;
        case 20: return 7;
        case 21: return 73;
        case 22: return 43;
        case 23: return 19;
        default: return 5;
    }
}

static int64_t kernel(int64_t count) {
    int64_t state = 305419896;
    int64_t checksum = 0;
    for (int64_t i = 0; i < count; i++) {
        state = (state * 1664525 + 1013904223) & 2147483647;
        checksum += classify((state >> 16) & 31);
    }
    return checksum;
}
int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 10000000);
    int64_t started = clock_now();
    int64_t result = kernel(count);
    report(result, clock_now() - started);
    return 0;
}
