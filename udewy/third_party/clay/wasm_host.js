let udewyClayExports = null;

async function loadUdewyClay() {
    if (udewyClayExports !== null) {
        return udewyClayExports;
    }

    const { instance } = await loadLinkedWasm('udewy_clay.wasm', { env: {} });
    udewyClayExports = instance.exports;
    return udewyClayExports;
}

async function beforeUdewyInstantiate(imports) {
    const clay = await loadUdewyClay();
    const wrap = (name) => (...args) => clay[name](...args);

    imports.env.ud_clay_min_memory = wrap('ud_clay_min_memory');
    imports.env.ud_clay_init = wrap('ud_clay_init');
    imports.env.ud_clay_set_layout_dimensions = wrap('ud_clay_set_layout_dimensions');
    imports.env.ud_clay_set_pointer_state = wrap('ud_clay_set_pointer_state');
    imports.env.ud_clay_pointer_over = wrap('ud_clay_pointer_over');
    imports.env.ud_clay_begin_layout = wrap('ud_clay_begin_layout');
    imports.env.ud_clay_end_layout = wrap('ud_clay_end_layout');
    imports.env.ud_clay_open_box = wrap('ud_clay_open_box');
    imports.env.ud_clay_open_box_ex = wrap('ud_clay_open_box_ex');
    imports.env.ud_clay_text_reserve = wrap('ud_clay_text_reserve');
    imports.env.ud_clay_text = (ptr, len, fontSize, r, g, b, a) => {
        if (clay.memory && clay.ud_clay_text_reserve) {
            const dest = clay.ud_clay_text_reserve(len);
            const n = Number(len);
            new Uint8Array(clay.memory.buffer, Number(dest), n)
                .set(new Uint8Array(memory.buffer, Number(ptr), n));
            return clay.ud_clay_text(dest, len, fontSize, r, g, b, a);
        }
        return clay.ud_clay_text(ptr, len, fontSize, r, g, b, a);
    };
    imports.env.ud_clay_close = wrap('ud_clay_close');
    imports.env.ud_clay_render_count = wrap('ud_clay_render_count');
    imports.env.ud_clay_render_type = wrap('ud_clay_render_type');
    imports.env.ud_clay_render_x = wrap('ud_clay_render_x');
    imports.env.ud_clay_render_y = wrap('ud_clay_render_y');
    imports.env.ud_clay_render_width = wrap('ud_clay_render_width');
    imports.env.ud_clay_render_height = wrap('ud_clay_render_height');
    imports.env.ud_clay_render_rect_r = wrap('ud_clay_render_rect_r');
    imports.env.ud_clay_render_rect_g = wrap('ud_clay_render_rect_g');
    imports.env.ud_clay_render_rect_b = wrap('ud_clay_render_rect_b');
    imports.env.ud_clay_render_rect_a = wrap('ud_clay_render_rect_a');
    imports.env.ud_clay_render_text_len = wrap('ud_clay_render_text_len');
    imports.env.ud_clay_render_text_char = wrap('ud_clay_render_text_char');
    imports.env.ud_clay_render_text_size = wrap('ud_clay_render_text_size');
    imports.env.ud_clay_render_text_r = wrap('ud_clay_render_text_r');
    imports.env.ud_clay_render_text_g = wrap('ud_clay_render_text_g');
    imports.env.ud_clay_render_text_b = wrap('ud_clay_render_text_b');
    imports.env.ud_clay_render_text_a = wrap('ud_clay_render_text_a');
}
