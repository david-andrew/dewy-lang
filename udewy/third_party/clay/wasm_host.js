let udewyClayExports = null;

function createUdewyClayFallback() {
    const state = {
        width: 0,
        height: 0,
        commands: [],
        stack: [],
        pointerX: 0,
        pointerY: 0,
    };

    const num = (value) => Number(value);
    const word = (value) => BigInt(Math.trunc(value));

    function currentChildBox(parent, width, height, widthMode, heightMode) {
        if (!parent) {
            return { x: 0, y: 0, width, height };
        }
        if (widthMode === 1) {
            width = Math.max(0, parent.x + parent.width - parent.padding - parent.cursorX);
        }
        if (heightMode === 1) {
            height = Math.max(0, parent.y + parent.height - parent.padding - parent.cursorY);
        }
        const x = parent.cursorX;
        const y = parent.cursorY;
        if (parent.direction === 1) {
            parent.cursorY += height + parent.gap;
        } else {
            parent.cursorX += width + parent.gap;
        }
        return { x, y, width, height };
    }

    const openBoxEx = (id, width, height, widthMode, heightMode, direction, padding, gap, r, g, b, a) => {
        const parent = state.stack.length > 0 ? state.stack[state.stack.length - 1] : null;
        const box = currentChildBox(parent, num(width), num(height), num(widthMode), num(heightMode));
        const pad = num(padding);
        const next = {
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            direction: num(direction),
            padding: pad,
            gap: num(gap),
            cursorX: box.x + pad,
            cursorY: box.y + pad,
        };
        state.commands.push({
            type: 1,
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            r: num(r),
            g: num(g),
            b: num(b),
            a: num(a),
            id: num(id),
        });
        state.stack.push(next);
        return 0n;
    };

    return {
        ud_clay_min_memory: () => 0n,
        ud_clay_init: (width, height) => {
            state.width = num(width);
            state.height = num(height);
            return 1n;
        },
        ud_clay_set_layout_dimensions: (width, height) => {
            state.width = num(width);
            state.height = num(height);
            return 0n;
        },
        ud_clay_set_pointer_state: (x, y) => {
            state.pointerX = num(x);
            state.pointerY = num(y);
            return 0n;
        },
        ud_clay_pointer_over: (id) => {
            const target = num(id);
            const hit = state.commands.some((command) => (
                command.id === target &&
                state.pointerX >= command.x &&
                state.pointerY >= command.y &&
                state.pointerX < command.x + command.width &&
                state.pointerY < command.y + command.height
            ));
            return hit ? 1n : 0n;
        },
        ud_clay_begin_layout: () => {
            state.commands = [];
            state.stack = [];
            return 0n;
        },
        ud_clay_end_layout: () => word(state.commands.length),
        ud_clay_text_reserve: () => 0n,
        ud_clay_text: (ptr, len, fontSize, r, g, b, a) => {
            const text = decodeString(ptr, len);
            const parent = state.stack.length > 0 ? state.stack[state.stack.length - 1] : null;
            const size = num(fontSize);
            const box = currentChildBox(parent, Math.ceil(text.length * size * 0.7), size + 4, 0, 0);
            state.commands.push({
                type: 3,
                x: box.x,
                y: box.y,
                width: box.width,
                height: box.height,
                r: num(r),
                g: num(g),
                b: num(b),
                a: num(a),
                fontSize: size,
                text,
            });
            return 0n;
        },
        ud_clay_open_box: (id, width, height, direction, padding, gap, r, g, b, a) => {
            return openBoxEx(id, width, height, 0n, 0n, direction, padding, gap, r, g, b, a);
        },
        ud_clay_open_box_ex: openBoxEx,
        ud_clay_close: () => {
            state.stack.pop();
            return 0n;
        },
        ud_clay_render_count: () => word(state.commands.length),
        ud_clay_render_type: (index) => word(state.commands[num(index)].type),
        ud_clay_render_x: (index) => word(state.commands[num(index)].x),
        ud_clay_render_y: (index) => word(state.commands[num(index)].y),
        ud_clay_render_width: (index) => word(state.commands[num(index)].width),
        ud_clay_render_height: (index) => word(state.commands[num(index)].height),
        ud_clay_render_rect_r: (index) => word(state.commands[num(index)].r),
        ud_clay_render_rect_g: (index) => word(state.commands[num(index)].g),
        ud_clay_render_rect_b: (index) => word(state.commands[num(index)].b),
        ud_clay_render_rect_a: (index) => word(state.commands[num(index)].a),
        ud_clay_render_text_len: (index) => word(state.commands[num(index)].text.length),
        ud_clay_render_text_char: (index, charIndex) => word(state.commands[num(index)].text.charCodeAt(num(charIndex))),
        ud_clay_render_text_size: (index) => word(state.commands[num(index)].fontSize),
        ud_clay_render_text_r: (index) => word(state.commands[num(index)].r),
        ud_clay_render_text_g: (index) => word(state.commands[num(index)].g),
        ud_clay_render_text_b: (index) => word(state.commands[num(index)].b),
        ud_clay_render_text_a: (index) => word(state.commands[num(index)].a),
    };
}

async function loadUdewyClay() {
    if (udewyClayExports !== null) {
        return udewyClayExports;
    }

    try {
        const response = await fetch('udewy_clay.wasm');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const bytes = await response.arrayBuffer();
        const { instance } = await WebAssembly.instantiate(bytes, { env: {} });
        udewyClayExports = instance.exports;
    } catch (err) {
        console.warn('Using JS Clay demo fallback:', err);
        udewyClayExports = createUdewyClayFallback();
    }
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
