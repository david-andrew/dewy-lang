let udewyClayExports = null;

function createUdewyClayFallback() {
    const state = {
        width: 0,
        height: 0,
        commands: [],
        stack: [],
    };

    const num = (value) => Number(value);
    const word = (value) => BigInt(Math.trunc(value));

    function currentChildBox(parent, width, height) {
        if (!parent) {
            return { x: 0, y: 0, width, height };
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
        ud_clay_begin_layout: () => {
            state.commands = [];
            state.stack = [];
            return 0n;
        },
        ud_clay_end_layout: () => word(state.commands.length),
        ud_clay_open_box: (id, width, height, direction, padding, gap, r, g, b, a) => {
            const parent = state.stack.length > 0 ? state.stack[state.stack.length - 1] : null;
            const box = currentChildBox(parent, num(width), num(height));
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
        },
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
    imports.env.ud_clay_begin_layout = wrap('ud_clay_begin_layout');
    imports.env.ud_clay_end_layout = wrap('ud_clay_end_layout');
    imports.env.ud_clay_open_box = wrap('ud_clay_open_box');
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
}
