#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CLAY_DISABLE_SIMD
#define CLAY_IMPLEMENTATION
#include "clay.h"

#define UD_CLAY_ARENA_BYTES (16u * 1024u * 1024u)

static unsigned char ud_clay_arena_memory[UD_CLAY_ARENA_BYTES];
static Clay_RenderCommandArray ud_clay_last_commands;
static int ud_clay_initialized;

static uint32_t ud_clay_float_to_u32(float value) {
    if (value <= 0.0f) {
        return 0;
    }
    return (uint32_t)(value + 0.5f);
}

static Clay_Color ud_clay_color(uint32_t r, uint32_t g, uint32_t b, uint32_t a) {
    Clay_Color color = {(float)r, (float)g, (float)b, (float)a};
    return color;
}

static Clay_ElementId ud_clay_element_id(uint32_t id) {
    Clay_ElementId element_id = {id, 0, id, {true, 0, 0}};
    return element_id;
}

static Clay_Dimensions ud_clay_measure_text(
    Clay_StringSlice text,
    Clay_TextElementConfig *config,
    void *user_data
) {
    (void)user_data;
    float font_size = config && config->fontSize ? (float)config->fontSize : 16.0f;
    float letter_spacing = config ? (float)config->letterSpacing : 0.0f;
    Clay_Dimensions dimensions = {
        ((float)text.length * font_size * 0.55f) + ((float)text.length * letter_spacing),
        config && config->lineHeight ? (float)config->lineHeight : font_size,
    };
    return dimensions;
}

uint64_t ud_clay_min_memory(void) {
    return Clay_MinMemorySize();
}

uint64_t ud_clay_init(uint64_t width, uint64_t height) {
    uint32_t min_memory = Clay_MinMemorySize();
    if (min_memory > UD_CLAY_ARENA_BYTES) {
        return 0;
    }

    Clay_Arena arena = Clay_CreateArenaWithCapacityAndMemory(
        UD_CLAY_ARENA_BYTES,
        ud_clay_arena_memory
    );
    Clay_Dimensions dimensions = {(float)width, (float)height};
    Clay_Context *context = Clay_Initialize(arena, dimensions, (Clay_ErrorHandler){0});
    Clay_SetMeasureTextFunction(ud_clay_measure_text, 0);
    ud_clay_initialized = context != 0;
    return (uint64_t)(uintptr_t)context;
}

uint64_t ud_clay_set_layout_dimensions(uint64_t width, uint64_t height) {
    Clay_SetLayoutDimensions((Clay_Dimensions){(float)width, (float)height});
    return 0;
}

uint64_t ud_clay_begin_layout(void) {
    if (!ud_clay_initialized) {
        return 0;
    }
    Clay_BeginLayout();
    return 0;
}

uint64_t ud_clay_end_layout(uint64_t delta_ms) {
    float delta_seconds = (float)delta_ms / 1000.0f;
    ud_clay_last_commands = Clay_EndLayout(delta_seconds);
    return (uint64_t)ud_clay_last_commands.length;
}

uint64_t ud_clay_open_box(
    uint64_t id,
    uint64_t width,
    uint64_t height,
    uint64_t direction,
    uint64_t padding,
    uint64_t gap,
    uint64_t r,
    uint64_t g,
    uint64_t b,
    uint64_t a
) {
    if (id == 0) {
        Clay__OpenElement();
    } else {
        Clay__OpenElementWithId(ud_clay_element_id((uint32_t)id));
    }

    Clay_ElementDeclaration declaration = {0};
    declaration.layout.sizing.width = CLAY_SIZING_FIXED((float)width);
    declaration.layout.sizing.height = CLAY_SIZING_FIXED((float)height);
    declaration.layout.layoutDirection = direction ? CLAY_TOP_TO_BOTTOM : CLAY_LEFT_TO_RIGHT;
    declaration.layout.childGap = (uint16_t)gap;
    declaration.layout.padding = (Clay_Padding){
        (uint16_t)padding,
        (uint16_t)padding,
        (uint16_t)padding,
        (uint16_t)padding,
    };
    declaration.backgroundColor = ud_clay_color((uint32_t)r, (uint32_t)g, (uint32_t)b, (uint32_t)a);

    Clay__ConfigureOpenElementPtr(&declaration);
    return 0;
}

uint64_t ud_clay_close(void) {
    Clay__CloseElement();
    return 0;
}

uint64_t ud_clay_render_count(void) {
    return (uint64_t)ud_clay_last_commands.length;
}

static Clay_RenderCommand *ud_clay_command(uint64_t index) {
    return Clay_RenderCommandArray_Get(&ud_clay_last_commands, (int32_t)index);
}

uint64_t ud_clay_render_type(uint64_t index) {
    return (uint64_t)ud_clay_command(index)->commandType;
}

uint64_t ud_clay_render_x(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->boundingBox.x);
}

uint64_t ud_clay_render_y(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->boundingBox.y);
}

uint64_t ud_clay_render_width(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->boundingBox.width);
}

uint64_t ud_clay_render_height(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->boundingBox.height);
}

uint64_t ud_clay_render_rect_r(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->renderData.rectangle.backgroundColor.r);
}

uint64_t ud_clay_render_rect_g(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->renderData.rectangle.backgroundColor.g);
}

uint64_t ud_clay_render_rect_b(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->renderData.rectangle.backgroundColor.b);
}

uint64_t ud_clay_render_rect_a(uint64_t index) {
    return ud_clay_float_to_u32(ud_clay_command(index)->renderData.rectangle.backgroundColor.a);
}
