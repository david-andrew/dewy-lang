#include "harness.h"

static int64_t kernel(const uint8_t *text, int64_t length) {
    int64_t words = 0, lines = 0, total = 0, hash = 5, i = 0;
    while (i < length) {
        int64_t byte = text[i];
        if (byte == 10) {
            lines++;
            i++;
        } else if (byte == 32) {
            i++;
        } else if (byte >= 48 && byte <= 57) {
            int64_t value = 0;
            while (i < length && text[i] >= 48 && text[i] <= 57) {
                value = value * 10 + text[i] - 48;
                i++;
            }
            total = (total + value) % 1000000007;
        } else {
            int64_t word = 0;
            while (i < length && text[i] >= 97 && text[i] <= 122) {
                word = (word * 131 + text[i]) % 1000000007;
                i++;
            }
            words++;
            hash = mix(hash, word);
        }
    }
    return mix(mix(mix(hash, words), lines), total);
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    uint8_t *text = malloc(count * 8 + 8);
    int64_t length = 0, seed = 99;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        int64_t size = seed % 7 + 1;
        int digits = (seed / 8) % 3 == 0;
        for (int64_t j = 0; j < size; j++) {
            seed = lcg(seed);
            text[length++] = digits ? 48 + seed % 10 : 97 + seed % 26;
        }
        text[length++] = i % 12 == 11 ? 10 : 32;
    }
    int64_t started = clock_now();
    int64_t result = kernel(text, length);
    report(result, clock_now() - started);
    return 0;
}
