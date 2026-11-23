#include "harness.h"

typedef struct { int64_t priority, payload; } Event;
typedef struct { Event *data; int64_t length, capacity; } Heap;

static void heap_push(Heap *h, Event item) {
    if (h->length == h->capacity) {
        int64_t cap = h->capacity ? h->capacity * 2 : 8;
        h->data = realloc(h->data, (size_t)cap * sizeof *h->data);
        h->capacity = cap;
    }
    int64_t i = h->length++;
    while (i > 0) {
        int64_t p = (i - 1) >> 1;
        if (h->data[p].priority <= item.priority) break;
        h->data[i] = h->data[p];
        i = p;
    }
    h->data[i] = item;
}

static Event heap_pop(Heap *h) {
    Event top = h->data[0];
    Event last = h->data[--h->length];
    int64_t n = h->length;
    if (n > 0) {
        int64_t i = 0;
        for (;;) {
            int64_t left = i * 2 + 1;
            if (left >= n) break;
            int64_t best = left;
            int64_t right = left + 1;
            if (right < n && h->data[right].priority < h->data[left].priority) best = right;
            if (last.priority <= h->data[best].priority) break;
            h->data[i] = h->data[best];
            i = best;
        }
        h->data[i] = last;
    }
    return top;
}

static int64_t kernel(int64_t count) {
    Heap heap = {0};
    int64_t seed = 4242, hash = 13;
    for (int64_t i = 0; i < count; i++) {
        seed = lcg(seed);
        heap_push(&heap, (Event){seed % 1000003, i});
        seed = lcg(seed);
        heap_push(&heap, (Event){seed % 1000003, i + count});
        if (heap.length > 0) {
            Event ev = heap_pop(&heap);
            hash = mix(hash, (ev.priority + ev.payload) % 1000003);
        }
    }
    while (heap.length > 0) {
        Event ev = heap_pop(&heap);
        hash = mix(hash, (ev.priority + ev.payload) % 1000003);
    }
    free(heap.data);
    return hash;
}

int main(int argc, char **argv) {
    int64_t count = size_argument(argc, argv, 500000);
    int64_t started = clock_now();
    int64_t result = kernel(count);
    report(result, clock_now() - started);
    return 0;
}
