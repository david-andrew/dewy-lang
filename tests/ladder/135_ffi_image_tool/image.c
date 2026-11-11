/* A small, independently compiled 16-bit image library. */
#include <stddef.h>
#include <stdint.h>

typedef struct { uint16_t r, g, b, alpha; } Pixel;
typedef struct { uint64_t count, red, green, blue; } Stats;

static uint16_t expose(uint16_t value, uint16_t gain) {
    uint32_t scaled = (uint32_t)value * gain;
    return scaled > UINT16_MAX ? UINT16_MAX : (uint16_t)scaled;
}

Pixel image_tone(Pixel source, uint16_t gain) {
    Pixel result = {expose(source.r, gain), expose(source.g, gain),
                    expose(source.b, gain), source.alpha};
    return result;
}

Stats image_scan(const Pixel *pixels, uint64_t count, uint64_t stride, uint64_t alignment) {
    Stats result = {0, 0, 0, 0};
    if (stride != sizeof(Pixel) || alignment != _Alignof(Pixel)) return result;
    for (uint64_t i = 0; i < count; ++i) {
        ++result.count;
        result.red += pixels[i].r;
        result.green += pixels[i].g;
        result.blue += pixels[i].b;
    }
    return result;
}

Stats image_merge(Stats a, Stats b) {
    Stats result = {a.count + b.count, a.red + b.red,
                    a.green + b.green, a.blue + b.blue};
    return result;
}

uint64_t image_rgb(const Pixel *pixels, uint64_t count, uint8_t *buffer, uint64_t capacity) {
    if (count > capacity / 3) return 0;
    for (uint64_t i = 0; i < count; ++i) {
        buffer[i * 3] = (uint8_t)(pixels[i].r >> 8);
        buffer[i * 3 + 1] = (uint8_t)(pixels[i].g >> 8);
        buffer[i * 3 + 2] = (uint8_t)(pixels[i].b >> 8);
    }
    return count * 3;
}

int32_t image_find(const Pixel *pixels, uint64_t count, uint16_t alpha, const Pixel **found) {
    *found = NULL;
    for (uint64_t i = 0; i < count; ++i) {
        if (pixels[i].alpha == alpha) {
            *found = pixels + i;
            return 1;
        }
    }
    return 0;
}

int32_t image_pointer_layout(uint64_t size, uint64_t alignment) {
    return size == sizeof(Pixel *) && alignment == _Alignof(Pixel *);
}
