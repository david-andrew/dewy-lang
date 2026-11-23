#include "harness.h"
#include <string.h>

enum { HASH_SIZE = 4096, HASH_MASK = 4095 };

typedef struct { uint8_t *data; int64_t length, capacity; } Bytes;

static void bytes_reserve(Bytes *b, int64_t cap) {
    if (cap > b->capacity) {
        b->data = realloc(b->data, (size_t)cap);
        b->capacity = cap;
    }
}

static inline void bytes_push(Bytes *b, uint8_t v) {
    if (b->length == b->capacity) {
        int64_t cap = b->capacity ? b->capacity * 2 : 64;
        b->data = realloc(b->data, (size_t)cap);
        b->capacity = cap;
    }
    b->data[b->length++] = v;
}

static Bytes compress_bytes(const uint8_t *src, int64_t n) {
    Bytes out = {0};
    bytes_reserve(&out, n + 64);
    int64_t table[HASH_SIZE];
    for (int64_t k = 0; k < HASH_SIZE; k++) table[k] = -1;
    int64_t i = 0;
    while (i < n) {
        int64_t best_len = 0, best_dist = 0;
        if (i + 3 <= n) {
            int64_t h = (((int64_t)src[i] * 131 + src[i + 1]) * 131 + src[i + 2]) & HASH_MASK;
            int64_t cand = table[h];
            table[h] = i;
            if (cand >= 0 && i - cand <= 255 && i - cand > 0) {
                int64_t mlen = 0;
                int64_t limit = n - i < 127 ? n - i : 127;
                while (mlen < limit && src[cand + mlen] == src[i + mlen]) mlen++;
                if (mlen >= 4) {
                    best_len = mlen;
                    best_dist = i - cand;
                }
            }
        }
        if (best_len >= 4) {
            bytes_push(&out, (uint8_t)(128 + best_len));
            bytes_push(&out, (uint8_t)best_dist);
            i += best_len;
        } else {
            int64_t lit_start = i, lit_len = 0;
            while (i < n && lit_len < 127) {
                if (i + 3 <= n) {
                    int64_t h = (((int64_t)src[i] * 131 + src[i + 1]) * 131 + src[i + 2]) & HASH_MASK;
                    int64_t cand = table[h];
                    if (cand >= 0 && i - cand <= 255 && i - cand > 0 &&
                        src[cand] == src[i] && src[cand + 1] == src[i + 1] &&
                        src[cand + 2] == src[i + 2] && i + 3 < n && src[cand + 3] == src[i + 3])
                        break;
                    table[h] = i;
                }
                i++;
                lit_len++;
            }
            bytes_push(&out, (uint8_t)lit_len);
            for (int64_t k = 0; k < lit_len; k++) bytes_push(&out, src[lit_start + k]);
        }
    }
    return out;
}

static Bytes decompress_bytes(const uint8_t *packed, int64_t n, int64_t orig_len) {
    Bytes out = {0};
    bytes_reserve(&out, orig_len > 0 ? orig_len : 1);
    int64_t i = 0;
    while (i < n) {
        int64_t tag = packed[i++];
        if (tag >= 128) {
            int64_t mlen = tag - 128;
            int64_t dist = packed[i++];
            int64_t start = out.length - dist;
            for (int64_t k = 0; k < mlen; k++) bytes_push(&out, out.data[start + k]);
        } else {
            for (int64_t k = 0; k < tag; k++) bytes_push(&out, packed[i++]);
        }
    }
    return out;
}

static int64_t kernel(const uint8_t *src, int64_t n) {
    Bytes packed = compress_bytes(src, n);
    Bytes unpacked = decompress_bytes(packed.data, packed.length, n);
    int64_t hash = mix(7, packed.length);
    int64_t ok = unpacked.length == n ? 1 : 0;
    for (int64_t i = 0; i < n; i++) {
        if (ok == 1 && unpacked.data[i] != src[i]) ok = 0;
        if (i % 32 == 0) hash = mix(hash, unpacked.data[i]);
    }
    free(packed.data);
    free(unpacked.data);
    return mix(hash, ok);
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 1000000);
    Bytes src = {0};
    bytes_reserve(&src, count > 0 ? count : 1);
    int64_t seed = 777;
    const char *p0 = "event=tick level=info ";
    const char *p1 = "event=sync level=warn ";
    const char *p2 = "status=ok code=200\n";
    while (src.length < count) {
        seed = lcg(seed);
        int64_t kind = seed % 4;
        const char *p = kind == 0 ? p0 : kind == 1 ? p1 : kind == 2 ? p2 : NULL;
        if (p) {
            for (; *p && src.length < count; p++) bytes_push(&src, (uint8_t)*p);
        } else {
            for (int64_t k = 0; k < 6 && src.length < count; k++) {
                seed = lcg(seed);
                bytes_push(&src, (uint8_t)(48 + seed % 10));
            }
            if (src.length < count) bytes_push(&src, 32);
        }
    }
    int64_t started = clock_now();
    int64_t result = kernel(src.data, src.length);
    report(result, clock_now() - started);
    free(src.data);
    return 0;
}
