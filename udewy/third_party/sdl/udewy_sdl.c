#include <stdint.h>

extern uint32_t SDL_GetMouseState(float *x, float *y);

uint64_t ud_sdl_get_mouse_state(uint64_t x_ptr, uint64_t y_ptr) {
    float x = 0.0f;
    float y = 0.0f;
    uint32_t buttons = SDL_GetMouseState(&x, &y);
    *(uint64_t *)(uintptr_t)x_ptr = (uint64_t)x;
    *(uint64_t *)(uintptr_t)y_ptr = (uint64_t)y;
    return (uint64_t)buttons;
}
