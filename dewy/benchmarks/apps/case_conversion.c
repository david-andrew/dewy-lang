/* Same allocation/copy and eight-byte ASCII algorithm as Dewy's library.
   This comparison includes the UTF-8 fallback, without locale-sensitive C APIs. */
#include "harness.h"
#include <string.h>

static unsigned other_case(unsigned c, int upper) {
    if (upper) {
        if (c >= 0xe0 && c <= 0xfe && c != 0xf7) return c - 32;
        if (c == 0xff) return 0x178;
        if (c >= 0x3b1 && c <= 0x3c9 && c != 0x3c2) return c - 32;
        if (c >= 0x430 && c <= 0x44f) return c - 32;
        if (c >= 0x450 && c <= 0x45f) return c - 80;
    } else {
        if (c >= 0xc0 && c <= 0xde && c != 0xd7) return c + 32;
        if (c == 0x178) return 0xff;
        if (c >= 0x391 && c <= 0x3a9 && c != 0x3a2) return c + 32;
        if (c >= 0x410 && c <= 0x42f) return c + 32;
        if (c >= 0x400 && c <= 0x40f) return c + 80;
    }
    if ((c >= 0x100 && c <= 0x137) || (c >= 0x14a && c <= 0x177)) {
        if (upper && c % 2 == 1) return c - 1;
        if (!upper && c % 2 == 0) return c + 1;
    }
    if ((c >= 0x139 && c <= 0x148) || (c >= 0x179 && c <= 0x17e)) {
        if (upper && c % 2 == 0) return c - 1;
        if (!upper && c % 2 == 1) return c + 1;
    }
    return c;
}

static unsigned char *convert(const unsigned char *s, size_t n, int upper) {
    unsigned char *out = malloc(n ? n : 1);
    memcpy(out, s, n);
    const unsigned lo = upper ? 'a' : 'A', hi = upper ? 'z' : 'Z';
    const uint64_t add_lo = upper ? UINT64_C(0x1f1f1f1f1f1f1f1f) : UINT64_C(0x3f3f3f3f3f3f3f3f);
    const uint64_t add_hi = upper ? UINT64_C(0x0505050505050505) : UINT64_C(0x2525252525252525);
    size_t i = 0;
    while (i < n) {
        if (n - i >= 8) {
            uint64_t word;
            memcpy(&word, out + i, 8);
            if (!(word & UINT64_C(0x8080808080808080))) {
                uint64_t mask = (word + add_lo) & ~(word + add_hi) & UINT64_C(0x8080808080808080);
                if (mask) {
                    word ^= mask >> 2;
                    memcpy(out + i, &word, 8);
                }
                i += 8;
                continue;
            }
        }
        unsigned c = out[i];
        if (c < 128) {
            if (c >= lo && c <= hi) out[i] = c ^ 32;
            ++i;
        } else if (c >= 0xc2 && c <= 0xdf && i + 1 < n && (out[i + 1] & 0xc0) == 0x80) {
            unsigned cp = ((c & 0x1f) << 6) | (out[i + 1] & 0x3f);
            unsigned mapped = other_case(cp, upper);
            if (mapped != cp) {
                out[i] = 0xc0 | (mapped >> 6);
                out[i + 1] = 0x80 | (mapped & 0x3f);
            }
            i += 2;
        } else ++i;
    }
    return out;
}

int main(int argc, char **argv) {
    const unsigned char unit[] = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 _- café Ωω Яя Ёё.";
    int64_t count = size_argument(argc, argv, 20000);
    size_t width = sizeof unit - 1, n = width * count;
    unsigned char *text = malloc(n ? n : 1);
    for (int64_t i = 0; i < count; ++i) memcpy(text + i * width, unit, width);
    int64_t started = clock_now();
    unsigned char *hi = convert(text, n, 1);
    unsigned char *lo = convert(text, n, 0);
    int64_t finished = clock_now(), checksum = 0;
    for (size_t i = 0; i < n; ++i) checksum += hi[i] + lo[i];
    report(checksum, finished - started);
    free(lo);
    free(hi);
    free(text);
    return 0;
}
