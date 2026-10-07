const memory = new WebAssembly.Memory({ initial: @@MEMORY_PAGES@@ });
let outputElement = null;
let domNextHandle = 1;
let domRootHandle = 0;
const domNodes = new Map();
const domHandles = new WeakMap();

// Canvas state
let canvas = null;
let ctx = null;
let canvasBuffer = null;
let canvasBufferPtr = 0;
let canvasBufferBytes = 0;
let canvasWidth = 0;
let canvasHeight = 0;
let frameCount = 0;
let startTime = 0;
let canvasMode = false;
let wasmInstance = null;
let canvasAspectWidth = 0;
let canvasAspectHeight = 0;

// Audio state (one-shot mode)
let audioCtx = null;
let audioSampleRate = 44100;
let audioNumSamples = 0;
let audioChannels = 1;
let audioBufferPtr = 0;
let audioBufferBytes = 0;
let audioPendingPlay = false;
let audioResumePending = false;
let audioPromptTimer = null;

// Audio streaming state
let audioStreamMode = false;

// WebGL fullscreen shader state
let webglCanvas = null;
let webglContext = null;
let webglProgram = null;
let webglPositionBuffer = null;
let webglMode = false;
let pointerInstalled = false;
let keyboardInstalled = false;
let pointerX = 0;
let pointerY = 0;
let pointerDown = false;
let pointerButtons = 0;
let pointerWheelAccum = 0;
const keysDown = new Set();
const keysPressedFrame = new Set();
const keysReleasedFrame = new Set();
let audioStreamBufferSize = 0;
let audioStreamStarted = false;
let audioScriptNode = null;

// General-purpose audio queue (ring of Int16 samples) driven from WASM.
// Reuses the global `audioCtx` so the existing `requestAudioUnlock()` user-
// gesture path also unlocks queued playback.
let audioQueueRate = 44100;
let audioQueueChannels = 1;
let audioQueueRing = null;
let audioQueueRead = 0;
let audioQueueWrite = 0;
let audioQueueCount = 0;
let audioQueueCapacity = 0;
let audioQueueNode = null;
let audioQueueMode = false;
const AUDIO_QUEUE_BLOCK = 2048;

function audioQueueEnsureContext() {
    if (audioQueueNode) return;
    if (!audioCtx) {
        audioCtx = new AudioContext({ sampleRate: audioQueueRate });
    }
    audioQueueNode = audioCtx.createScriptProcessor(AUDIO_QUEUE_BLOCK, 0, audioQueueChannels);
    // The ring holds interleaved frames: one sample per channel.
    audioQueueNode.onaudioprocess = (e) => {
        const channels = [];
        for (let c = 0; c < audioQueueChannels; c++) channels.push(e.outputBuffer.getChannelData(c));
        for (let i = 0; i < AUDIO_QUEUE_BLOCK; i++) {
            for (let c = 0; c < audioQueueChannels; c++) {
                if (audioQueueCount > 0) {
                    const s = audioQueueRing[audioQueueRead];
                    audioQueueRead = (audioQueueRead + 1) % audioQueueCapacity;
                    audioQueueCount--;
                    channels[c][i] = s / 32768.0;
                } else {
                    channels[c][i] = 0;
                }
            }
        }
    };
    audioQueueNode.connect(audioCtx.destination);
    requestAudioUnlock();
}

// General-purpose 3D GPU state (WebGL1, batched textured+vertex-color)
let gpuMode = false;
let gpuCanvas = null;
let gpuGL = null;
let gpuProgram = null;
let gpuVbo = null;
let gpuQuadIbo = null;
let gpuQuadIboCount = 0;
let gpuStripIbo = null;
let gpuStripIboCount = 0;
let gpuTextures = [null];  // 1-indexed; index 0 reserved
let gpuWhiteTex = null;
let gpuCurrentTex = 0;
let gpuOverlayActive = false;
let gpuSavedDepthTest = true;
let gpuSavedDepthWrite = true;
let gpuSavedBlend = false;
let gpuLocPos = -1;
let gpuLocUV = -1;
let gpuLocColor = -1;
let gpuLocProj = null;
let gpuLocView = null;
let gpuLocSampler = null;
let gpuLocUseTex = null;
let gpuProj = new Float32Array(16);
let gpuView = new Float32Array(16);
let gpuOrthoProj = new Float32Array(16);
let gpuIdentity = new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);

// Double-buffer for audio: WASM writes to one, audio reads from other
let audioWriteBuffer = 0;  // 0 or 1
let audioReadBuffer = 0;
let audioBuffer0Ready = false;
let audioBuffer1Ready = false;
const AUDIO_SCRIPT_BUFFER_SIZE = 8192;  // Larger buffer for less crackling
let AUDIO_BUFFER_0_OFFSET = 0;
let AUDIO_BUFFER_1_OFFSET = 0;

// Buffers the host hands the module (canvas pixels, audio samples) lie past
// the memory the module asked for: its data, static reservations and stack
// fill that, so each buffer grows the memory instead.
let hostMemoryTop = 0;
function hostAlloc(bytes) {
    if (hostMemoryTop === 0) hostMemoryTop = memory.buffer.byteLength;
    const pointer = hostMemoryTop;
    hostMemoryTop += Math.ceil(bytes / 16) * 16;
    if (hostMemoryTop > memory.buffer.byteLength) {
        memory.grow(Math.ceil((hostMemoryTop - memory.buffer.byteLength) / 65536));
    }
    return pointer;
}

const udewyTextEncoder = new TextEncoder();
const udewyTextDecoder = new TextDecoder();

function decodeString(ptr, len) {
    const view = new Uint8Array(memory.buffer);
    const bytes = view.slice(Number(ptr), Number(ptr) + Number(len));
    return udewyTextDecoder.decode(bytes);
}

function domRegister(node) {
    const existing = domHandles.get(node);
    if (existing !== undefined) {
        return existing;
    }
    const handle = domNextHandle++;
    domHandles.set(node, handle);
    domNodes.set(handle, node);
    return handle;
}

function domGet(handle) {
    return domNodes.get(Number(handle));
}

function domFlexAlign(value) {
    switch (Number(value)) {
        case 1: return 'center';
        case 2: return 'flex-end';
        case 3: return 'stretch';
        default: return 'flex-start';
    }
}

function domFlexJustify(value) {
    switch (Number(value)) {
        case 1: return 'center';
        case 2: return 'flex-end';
        case 3: return 'space-between';
        case 4: return 'space-around';
        case 5: return 'space-evenly';
        default: return 'flex-start';
    }
}

function ensureDomRoot() {
    let root = document.getElementById('udewy-dom-root');
    if (!root) {
        root = document.createElement('main');
        root.id = 'udewy-dom-root';
        document.body.insertBefore(root, outputElement || document.body.firstChild);
    }
    document.body.classList.add('dom-mode');
    if (outputElement) {
        outputElement.style.display = 'none';
    }
    domRootHandle = domRegister(root);
    return domRootHandle;
}

function domBytesToBase64(ptr, len) {
    const bytes = new Uint8Array(memory.buffer, Number(ptr), Number(len));
    let binary = '';
    for (let i = 0; i < bytes.length; i += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    }
    return btoa(binary);
}

function domSetFavicon(mime, ptr, len) {
    let link = document.querySelector('link[data-udewy-favicon]');
    if (!link) {
        link = document.createElement('link');
        link.dataset.udewyFavicon = 'true';
        document.head.appendChild(link);
    }
    link.rel = 'icon';
    link.type = mime;
    link.href = `data:${mime};base64,${domBytesToBase64(ptr, len)}`;
}

function decodeI64Array(ptr, count) {
    const values = new Int32Array(Number(count));
    const view = new DataView(memory.buffer);
    const base = Number(ptr);
    for (let i = 0; i < Number(count); i++) {
        values[i] = Number(view.getBigInt64(base + (i * 8), true));
    }
    return values;
}

// Printed text goes to the console a whole line at a time (a program prints
// a line in pieces).
let consoleLine = '';
function appendOutput(text) {
    const lines = (consoleLine + text).split('\n');
    consoleLine = lines.pop();
    for (const line of lines) console.log(line);
}

function flushConsole() {
    if (consoleLine) console.log(consoleLine);
    consoleLine = '';
}

// `host_exit` ends the program: this unwinds the module back to the page,
// which stops calling `main`.
class UdewyExit extends Error {
    constructor(code) {
        super(`exit ${code}`);
        this.code = BigInt(code);
    }
}

// The program has ended, by an exit or a failure. As with an uncaught
// exception in a script, the page is left as it is and the console says why.
function endProgram(err) {
    flushConsole();
    if (!(err instanceof UdewyExit)) {
        console.error(err);
    } else if (err.code === 0n) {
        console.log('Exit code: 0');
    } else {
        console.error(`Exit code: ${err.code}`);
    }
}

// The first call to `main`. A program that set up a canvas, WebGL, the GPU
// or an audio stream is then called again once per animation frame; module
// startup runs only on the first call.
function startUdewy(instance) {
    wasmInstance = instance;
    let result;
    try {
        result = instance.exports.main();
    } catch (err) {
        endProgram(err);
        return;
    }
    flushConsole();
    console.log(`Exit code: ${result}`);
    if (canvasMode || webglMode || gpuMode) {
        document.body.classList.add('canvas-mode');
        requestAnimationFrame(animationLoop);
    } else if (audioStreamMode) {
        requestAnimationFrame(animationLoop);
    }
}

function getDisplayCanvas() {
    return webglCanvas || canvas;
}

function updateCanvasLayout() {
    const displayCanvas = getDisplayCanvas();
    if (!displayCanvas || (!canvasMode && !webglMode)) {
        return;
    }

    if (canvasAspectWidth > 0 && canvasAspectHeight > 0) {
        const targetAspect = canvasAspectWidth / canvasAspectHeight;
        let displayWidth = window.innerWidth;
        let displayHeight = Math.floor(displayWidth / targetAspect);
        if (displayHeight > window.innerHeight) {
            displayHeight = window.innerHeight;
            displayWidth = Math.floor(displayHeight * targetAspect);
        }

        displayCanvas.style.position = 'fixed';
        displayCanvas.style.left = '50%';
        displayCanvas.style.top = '50%';
        displayCanvas.style.transform = 'translate(-50%, -50%)';
        displayCanvas.style.width = `${displayWidth}px`;
        displayCanvas.style.height = `${displayHeight}px`;
    } else {
        displayCanvas.style.position = 'fixed';
        displayCanvas.style.left = '0';
        displayCanvas.style.top = '0';
        displayCanvas.style.transform = 'none';
        displayCanvas.style.width = '100vw';
        displayCanvas.style.height = '100vh';
    }
}

// Keep the GPU canvas backing buffer matched to the window so the rendered
// aspect ratio tracks the window instead of being stretched to fit.
function resizeGpuCanvasToWindow() {
    if (!gpuCanvas) return;
    const w = Math.max(1, Math.floor(window.innerWidth));
    const h = Math.max(1, Math.floor(window.innerHeight));
    if (gpuCanvas.width !== w || gpuCanvas.height !== h) {
        gpuCanvas.width = w;
        gpuCanvas.height = h;
        if (gpuGL) gpuGL.viewport(0, 0, w, h);
    }
}

window.addEventListener('resize', () => {
    resizeGpuCanvasToWindow();
    updateCanvasLayout();
});

function lockCanvasAspect() {
    const displayCanvas = getDisplayCanvas();
    if (displayCanvas) {
        canvasAspectWidth = displayCanvas.width;
        canvasAspectHeight = displayCanvas.height;
    } else if (canvasWidth > 0 && canvasHeight > 0) {
        canvasAspectWidth = canvasWidth;
        canvasAspectHeight = canvasHeight;
    }
    updateCanvasLayout();
}

function unlockCanvasAspect() {
    canvasAspectWidth = 0;
    canvasAspectHeight = 0;
    updateCanvasLayout();
}

function ensureCanvasMemory(width, height) {
    const requiredBytes = width * height * 4;
    if (requiredBytes > canvasBufferBytes) {
        canvasBufferPtr = hostAlloc(requiredBytes);
        canvasBufferBytes = requiredBytes;
    }
}

function hideAudioPrompt() {
    if (audioPromptTimer !== null) {
        clearTimeout(audioPromptTimer);
        audioPromptTimer = null;
    }
    const overlay = document.getElementById('audio-play-overlay');
    if (overlay) {
        overlay.remove();
    }
}

function showAudioPrompt() {
    let overlay = document.getElementById('audio-play-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'audio-play-overlay';
        overlay.style.cssText = 'position:fixed; top:16px; left:16px; z-index:9999; pointer-events:none;';

        const button = document.createElement('button');
        button.id = 'audio-play-btn';
        button.textContent = 'Click to Enable Audio';
        button.style.cssText = 'pointer-events:auto; font-size:1em; padding:0.75em 1em; cursor:pointer; background:rgba(24,24,24,0.92); color:white; border:1px solid rgba(255,255,255,0.18); border-radius:999px; box-shadow:0 4px 16px rgba(0,0,0,0.35);';
        button.onclick = () => {
            requestAudioUnlock(true);
        };

        overlay.appendChild(button);
        document.body.appendChild(overlay);
    }
}

function playAudioBuffer() {
    const buffer = audioCtx.createBuffer(audioChannels, audioNumSamples, audioSampleRate);
    const view = new Int16Array(memory.buffer, audioBufferPtr, audioNumSamples * audioChannels);

    for (let ch = 0; ch < audioChannels; ch++) {
        const channelData = buffer.getChannelData(ch);
        for (let i = 0; i < audioNumSamples; i++) {
            const idx = audioChannels > 1 ? i * audioChannels + ch : i;
            channelData[i] = view[idx] / 32768.0;
        }
    }

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    source.start();
}

function flushPendingAudio() {
    if (!audioCtx || audioCtx.state !== 'running') {
        return;
    }

    hideAudioPrompt();

    if (audioPendingPlay) {
        audioPendingPlay = false;
        playAudioBuffer();
    }

    if (audioStreamMode && !audioStreamStarted && audioScriptNode) {
        audioScriptNode.connect(audioCtx.destination);
        audioStreamStarted = true;
    }
}

function scheduleAudioPrompt() {
    if (audioPromptTimer !== null) {
        return;
    }

    audioPromptTimer = window.setTimeout(() => {
        audioPromptTimer = null;
        if (audioCtx && audioCtx.state !== 'running') {
            showAudioPrompt();
        }
    }, 150);
}

function requestAudioUnlock(forceRetry=false) {
    if (!audioCtx) {
        return;
    }

    if (audioCtx.state === 'running') {
        flushPendingAudio();
        return;
    }

    scheduleAudioPrompt();

    if (audioResumePending && !forceRetry) {
        return;
    }

    audioResumePending = true;
    Promise.resolve(audioCtx.resume())
        .catch(() => null)
        .then(() => {
            audioResumePending = false;
            if (audioCtx && audioCtx.state === 'running') {
                flushPendingAudio();
            } else {
                showAudioPrompt();
            }
        });
}

function getInputCanvas() {
    return getDisplayCanvas();
}

function clampPointer(value, limit) {
    if (limit <= 0) return 0;
    if (value < 0) return 0;
    if (value >= limit) return limit - 1;
    return value;
}

// Map the DOM `buttons` bitmask (1=left, 2=right, 4=middle) onto the game's
// MOUSE_L=1 / MOUSE_M=2 / MOUSE_R=4 convention.
function domButtonsToMask(buttons) {
    let mask = 0;
    if (buttons & 1) mask |= 1;
    if (buttons & 2) mask |= 4;
    if (buttons & 4) mask |= 2;
    return mask;
}

function updatePointerFromEvent(event) {
    if (typeof event.buttons === 'number') {
        pointerButtons = domButtonsToMask(event.buttons);
        pointerDown = (pointerButtons & 1) !== 0;
    }
    const targetCanvas = getInputCanvas();
    if (!targetCanvas) {
        pointerX = Math.floor(event.clientX);
        pointerY = Math.floor(event.clientY);
        return;
    }

    const rect = targetCanvas.getBoundingClientRect();
    const scaleX = rect.width ? targetCanvas.width / rect.width : 1;
    const scaleY = rect.height ? targetCanvas.height / rect.height : 1;
    const localX = Math.floor((event.clientX - rect.left) * scaleX);
    const localY = Math.floor((event.clientY - rect.top) * scaleY);

    pointerX = clampPointer(localX, targetCanvas.width);
    pointerY = clampPointer(localY, targetCanvas.height);
}

function ensurePointerHandlers() {
    if (pointerInstalled) return;
    pointerInstalled = true;

    window.addEventListener('pointermove', (event) => {
        updatePointerFromEvent(event);
    });

    window.addEventListener('pointerdown', (event) => {
        pointerDown = true;
        updatePointerFromEvent(event);
        requestAudioUnlock(true);
    });

    window.addEventListener('pointerup', (event) => {
        pointerDown = false;
        updatePointerFromEvent(event);
    });

    window.addEventListener('pointercancel', () => {
        pointerDown = false;
        pointerButtons = 0;
    });

    // Accumulate wheel notches; the game reads/clears this once per frame.
    window.addEventListener('wheel', (event) => {
        if (canvasMode || webglMode || gpuMode) {
            event.preventDefault();
        }
        // deltaY > 0 is scroll-down; report negative steps so up = positive,
        // matching the SDL backend's wheel sign.
        pointerWheelAccum += (event.deltaY > 0) ? -1 : ((event.deltaY < 0) ? 1 : 0);
    }, { passive: false });

    // Suppress the browser context menu so right-button drag works.
    window.addEventListener('contextmenu', (event) => {
        if (canvasMode || webglMode || gpuMode) {
            event.preventDefault();
        }
    });
}

function clearKeyboardFrameState() {
    keysPressedFrame.clear();
    keysReleasedFrame.clear();
}

function releaseAllKeys() {
    keysDown.clear();
    clearKeyboardFrameState();
}

// While a canvas has the page, keys that would scroll it or move focus act
// only as game input; browser shortcuts (reload, developer tools, any key
// with Ctrl, Alt or Meta) keep working.
const GAME_KEYS = new Set([
    'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', 'Tab', 'Backspace',
    'PageUp', 'PageDown', 'Home', 'End', 'Slash', 'Quote',
]);
function gameKeyDefault(event) {
    if (!(canvasMode || webglMode || gpuMode)) return false;
    if (event.ctrlKey || event.altKey || event.metaKey) return false;
    return GAME_KEYS.has(event.code);
}

function ensureKeyboardHandlers() {
    if (keyboardInstalled) return;
    keyboardInstalled = true;

    window.addEventListener('keydown', (event) => {
        const code = event.code || event.key;
        if (gameKeyDefault(event)) {
            event.preventDefault();
        }
        if (!keysDown.has(code)) {
            keysPressedFrame.add(code);
        }
        keysDown.add(code);
        requestAudioUnlock(true);
    });

    window.addEventListener('keyup', (event) => {
        const code = event.code || event.key;
        if (gameKeyDefault(event)) {
            event.preventDefault();
        }
        if (keysDown.has(code)) {
            keysReleasedFrame.add(code);
        }
        keysDown.delete(code);
    });

    window.addEventListener('blur', releaseAllKeys);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            releaseAllKeys();
        }
    });
}

function compileWebglShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const info = gl.getShaderInfoLog(shader) || 'unknown shader compile error';
        gl.deleteShader(shader);
        throw new Error(info);
    }
    return shader;
}

function createWebglProgram(gl, fragmentSource) {
    const vertexSource = `
attribute vec2 a_position;

void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
`;
    const vertexShader = compileWebglShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = compileWebglShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        const info = gl.getProgramInfoLog(program) || 'unknown program link error';
        gl.deleteProgram(program);
        throw new Error(info);
    }
    return program;
}

function q16ToF32(v) {
    return Number(v) / 65536.0;
}

function gpuEnsureQuadIndices(quadCount) {
    if (gpuQuadIboCount >= quadCount) return;
    const cap = Math.max(quadCount * 2, 64);
    const indices = new Uint16Array(cap * 6);
    for (let i = 0; i < cap; i++) {
        const v = i * 4;
        const o = i * 6;
        indices[o] = v;
        indices[o + 1] = v + 1;
        indices[o + 2] = v + 2;
        indices[o + 3] = v;
        indices[o + 4] = v + 2;
        indices[o + 5] = v + 3;
    }
    if (!gpuQuadIbo) gpuQuadIbo = gpuGL.createBuffer();
    gpuGL.bindBuffer(gpuGL.ELEMENT_ARRAY_BUFFER, gpuQuadIbo);
    gpuGL.bufferData(gpuGL.ELEMENT_ARRAY_BUFFER, indices, gpuGL.STATIC_DRAW);
    gpuQuadIboCount = cap;
}

function gpuEnsureStripIndices(vertCount) {
    if (gpuStripIboCount >= vertCount) return;
    const cap = Math.max(vertCount * 2, 64);
    const triCount = (cap - 2);
    const indices = new Uint16Array(Math.max(triCount, 0) * 3);
    let o = 0;
    for (let i = 0; i + 2 < cap; i++) {
        if ((i & 1) === 0) {
            indices[o++] = i;
            indices[o++] = i + 1;
            indices[o++] = i + 2;
        } else {
            indices[o++] = i + 1;
            indices[o++] = i;
            indices[o++] = i + 2;
        }
    }
    if (!gpuStripIbo) gpuStripIbo = gpuGL.createBuffer();
    gpuGL.bindBuffer(gpuGL.ELEMENT_ARRAY_BUFFER, gpuStripIbo);
    gpuGL.bufferData(gpuGL.ELEMENT_ARRAY_BUFFER, indices, gpuGL.STATIC_DRAW);
    gpuStripIboCount = cap;
}

function gpuMakeFrustum(out, l, r, b, t, n, f) {
    const rl = r - l, tb = t - b, fn = f - n;
    out[0] = (2 * n) / rl;
    out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0;
    out[5] = (2 * n) / tb;
    out[6] = 0; out[7] = 0;
    out[8] = (r + l) / rl;
    out[9] = (t + b) / tb;
    out[10] = -(f + n) / fn;
    out[11] = -1;
    out[12] = 0; out[13] = 0;
    out[14] = -(2 * f * n) / fn;
    out[15] = 0;
}

function gpuMakeOrtho(out, l, r, b, t, n, f) {
    const rl = r - l, tb = t - b, fn = f - n;
    out[0] = 2 / rl;
    out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0;
    out[5] = 2 / tb;
    out[6] = 0; out[7] = 0;
    out[8] = 0; out[9] = 0;
    out[10] = -2 / fn;
    out[11] = 0;
    out[12] = -(r + l) / rl;
    out[13] = -(t + b) / tb;
    out[14] = -(f + n) / fn;
    out[15] = 1;
}

function gpuCreateProgram(gl) {
    const vs = `
attribute vec3 a_pos;
attribute vec2 a_uv;
attribute vec4 a_color;
uniform mat4 u_proj;
uniform mat4 u_view;
varying vec2 v_uv;
varying vec4 v_color;
void main() {
    gl_Position = u_proj * u_view * vec4(a_pos, 1.0);
    v_uv = a_uv;
    v_color = a_color;
}
`;
    const fs = `
precision mediump float;
varying vec2 v_uv;
varying vec4 v_color;
uniform sampler2D u_tex;
uniform float u_use_tex;
void main() {
    vec4 tex = texture2D(u_tex, v_uv);
    vec4 textured = v_color * tex;
    gl_FragColor = mix(v_color, textured, u_use_tex);
}
`;
    const vsh = compileWebglShader(gl, gl.VERTEX_SHADER, vs);
    const fsh = compileWebglShader(gl, gl.FRAGMENT_SHADER, fs);
    const prog = gl.createProgram();
    gl.attachShader(prog, vsh);
    gl.attachShader(prog, fsh);
    gl.linkProgram(prog);
    gl.deleteShader(vsh);
    gl.deleteShader(fsh);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        const info = gl.getProgramInfoLog(prog) || 'gpu program link error';
        gl.deleteProgram(prog);
        throw new Error(info);
    }
    return prog;
}

function gpuBindTextureSlot(slot) {
    const gl = gpuGL;
    let tex;
    if (slot === 0 || !gpuTextures[slot]) {
        tex = gpuWhiteTex;
        gl.uniform1f(gpuLocUseTex, 0.0);
    } else {
        tex = gpuTextures[slot];
        gl.uniform1f(gpuLocUseTex, 1.0);
    }
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.uniform1i(gpuLocSampler, 0);
    gpuCurrentTex = slot;
}

const imports = {
    env: {
        memory: memory,
        // Direct browser APIs
        host_log: (ptr, len) => {
            appendOutput(decodeString(ptr, len));
            return len;
        },
        host_exit: (code) => {
            throw new UdewyExit(code);
        },
        host_time: () => BigInt(Date.now()),
        host_random: () => BigInt(Math.floor(Math.random() * Number.MAX_SAFE_INTEGER)),
        // DOM manipulation
        host_dom_set_text: (ptr, len) => {
            const text = decodeString(ptr, len);
            if (outputElement) {
                outputElement.textContent = text;
            }
            return 0n;
        },
        host_dom_append: (ptr, len) => {
            const text = decodeString(ptr, len);
            if (outputElement) {
                outputElement.textContent += text;
            }
            return len;
        },
        host_dom_clear: () => {
            if (outputElement) {
                outputElement.textContent = '';
            }
            return 0n;
        },
        host_dom_append_int: (value) => {
            if (outputElement) {
                outputElement.textContent += String(value);
            }
            return value;
        },
        host_log_int: (value) => {
            console.log(String(value));
            return value;
        },
        ud_dom_set_title: (titlePtr, titleLen) => {
            document.title = decodeString(titlePtr, titleLen);
            return 0n;
        },
        ud_dom_set_favicon: (mimePtr, mimeLen, dataPtr, dataLen) => {
            domSetFavicon(decodeString(mimePtr, mimeLen), dataPtr, dataLen);
            return 0n;
        },
        ud_dom_root: () => BigInt(ensureDomRoot()),
        ud_dom_body: () => BigInt(domRegister(document.body)),
        ud_dom_clear: (handle) => {
            domGet(handle).replaceChildren();
            return 0n;
        },
        ud_dom_create_element: (tagPtr, tagLen) => {
            return BigInt(domRegister(document.createElement(decodeString(tagPtr, tagLen))));
        },
        ud_dom_create_text: (textPtr, textLen) => {
            return BigInt(domRegister(document.createTextNode(decodeString(textPtr, textLen))));
        },
        ud_dom_append: (parentHandle, childHandle) => {
            domGet(parentHandle).appendChild(domGet(childHandle));
            return childHandle;
        },
        ud_dom_set_text: (handle, textPtr, textLen) => {
            domGet(handle).textContent = decodeString(textPtr, textLen);
            return 0n;
        },
        ud_dom_set_attr: (handle, namePtr, nameLen, valuePtr, valueLen) => {
            domGet(handle).setAttribute(decodeString(namePtr, nameLen), decodeString(valuePtr, valueLen));
            return 0n;
        },
        ud_dom_add_class: (handle, classPtr, classLen) => {
            domGet(handle).classList.add(decodeString(classPtr, classLen));
            return 0n;
        },
        ud_dom_set_style: (handle, propertyPtr, propertyLen, valuePtr, valueLen) => {
            domGet(handle).style.setProperty(decodeString(propertyPtr, propertyLen), decodeString(valuePtr, valueLen));
            return 0n;
        },
        ud_dom_set_flex: (handle, direction, gap, align, justify, wrap) => {
            const style = domGet(handle).style;
            style.display = 'flex';
            style.flexDirection = Number(direction) === 1 ? 'column' : 'row';
            style.gap = `${Number(gap)}px`;
            style.alignItems = domFlexAlign(align);
            style.justifyContent = domFlexJustify(justify);
            style.flexWrap = Number(wrap) !== 0 ? 'wrap' : 'nowrap';
            return 0n;
        },
        // Editor primitives.
        ud_dom_get_text_len: (handle) => {
            const node = domGet(handle);
            const text = (node && 'value' in node) ? node.value : (node ? node.textContent : '');
            return BigInt(udewyTextEncoder.encode(text || '').length);
        },
        ud_dom_get_text: (handle, bufPtr, cap) => {
            const node = domGet(handle);
            const text = (node && 'value' in node) ? node.value : (node ? node.textContent : '');
            const encoded = udewyTextEncoder.encode(text || '');
            const n = Math.min(encoded.length, Number(cap));
            new Uint8Array(memory.buffer, Number(bufPtr), n).set(encoded.subarray(0, n));
            return BigInt(n);
        },
        ud_dom_get_caret: (handle) => {
            const node = domGet(handle);
            if (!node) return 0n;
            const sel = window.getSelection();
            if (!sel || sel.rangeCount === 0) return 0n;
            const range = sel.getRangeAt(0).cloneRange();
            range.selectNodeContents(node);
            range.setEnd(sel.anchorNode || node, sel.anchorOffset || 0);
            return BigInt(udewyTextEncoder.encode(range.toString()).length);
        },
        ud_dom_set_caret: (handle, byteOffset) => {
            const node = domGet(handle);
            if (!node) return 0n;
            const target = Number(byteOffset);
            const sel = window.getSelection();
            if (!sel) return 0n;
            // Walk text nodes counting UTF-8 bytes until we hit the target.
            const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
            let consumed = 0;
            let tn = walker.nextNode();
            const range = document.createRange();
            while (tn) {
                const bytes = udewyTextEncoder.encode(tn.nodeValue || '');
                if (consumed + bytes.length >= target) {
                    // Find char offset for the byte target inside this text node.
                    const remaining = target - consumed;
                    const charOffset = udewyTextDecoder.decode(bytes.subarray(0, remaining)).length;
                    range.setStart(tn, charOffset);
                    range.collapse(true);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    return 0n;
                }
                consumed += bytes.length;
                tn = walker.nextNode();
            }
            // Past the end: caret at end of node.
            range.selectNodeContents(node);
            range.collapse(false);
            sel.removeAllRanges();
            sel.addRange(range);
            return 0n;
        },
        ud_dom_add_event_listener: (handle, eventPtr, eventLen, fnIndex) => {
            const node = domGet(handle);
            if (!node) return 0n;
            const eventName = decodeString(eventPtr, eventLen);
            const idx = Number(fnIndex);
            node.addEventListener(eventName, () => {
                if (!wasmInstance) return;
                const table = wasmInstance.exports.__udewy_fn_table;
                if (!table) return;
                const fn = table.get(idx);
                if (typeof fn === 'function') fn();
            });
            return 0n;
        },
        ud_dom_value: (handle, valuePtr, valueLen) => {
            const node = domGet(handle);
            if (!node) return 0n;
            const text = decodeString(valuePtr, valueLen);
            if ('value' in node) node.value = text;
            else node.textContent = text;
            return 0n;
        },
        ud_dom_focus: (handle) => {
            const node = domGet(handle);
            if (node && node.focus) node.focus();
            return 0n;
        },
        // Canvas graphics
        host_canvas_init: (width, height) => {
            canvasWidth = Number(width);
            canvasHeight = Number(height);
            canvasMode = true;
            if (!canvas) {
                startTime = performance.now();
            }
            
            // Create or resize canvas
            canvas = document.getElementById('canvas');
            if (!canvas) {
                canvas = document.createElement('canvas');
                canvas.id = 'canvas';
                document.body.insertBefore(canvas, document.body.firstChild);
            }
            canvas.width = canvasWidth;
            canvas.height = canvasHeight;
            canvas.style.display = 'block';
            updateCanvasLayout();
            ensurePointerHandlers();
            ctx = canvas.getContext('2d');
            
            // Hide text output in canvas mode
            if (outputElement) {
                outputElement.style.display = 'none';
            }
            
            // The RGBA pixel buffer (4 bytes per pixel), past the module's memory
            ensureCanvasMemory(canvasWidth, canvasHeight);
            
            return BigInt(canvasBufferPtr);
        },
        host_canvas_width: () => BigInt(canvasWidth),
        host_canvas_height: () => BigInt(canvasHeight),
        host_canvas_present: () => {
            if (!ctx || !canvas) return 0n;
            
            // Read pixel data from WASM memory
            const view = new Uint8ClampedArray(memory.buffer, canvasBufferPtr, canvasWidth * canvasHeight * 4);
            const imageData = new ImageData(view, canvasWidth, canvasHeight);
            ctx.putImageData(imageData, 0, 0);
            
            return 0n;
        },
        host_canvas_set_aspect_lock: (enabled) => {
            if (Number(enabled) !== 0) {
                lockCanvasAspect();
            } else {
                unlockCanvasAspect();
            }
            return 0n;
        },
        host_frame_count: () => BigInt(frameCount),
        host_frame_time: () => BigInt(Math.floor(performance.now() - startTime)),
        host_window_width: () => BigInt(window.innerWidth),
        host_window_height: () => BigInt(window.innerHeight),
        host_pointer_x: () => BigInt(pointerX),
        host_pointer_y: () => BigInt(pointerY),
        host_pointer_down: () => (pointerDown ? 1n : 0n),
        host_pointer_buttons: () => BigInt(pointerButtons),
        host_pointer_wheel: () => {
            const steps = pointerWheelAccum;
            pointerWheelAccum = 0;
            return BigInt(steps);
        },
        host_key_down: (ptr, len) => {
            ensureKeyboardHandlers();
            return keysDown.has(decodeString(ptr, len)) ? 1n : 0n;
        },
        host_key_pressed: (ptr, len) => {
            ensureKeyboardHandlers();
            return keysPressedFrame.has(decodeString(ptr, len)) ? 1n : 0n;
        },
        host_key_released: (ptr, len) => {
            ensureKeyboardHandlers();
            return keysReleasedFrame.has(decodeString(ptr, len)) ? 1n : 0n;
        },
        // Audio
        host_audio_init: (sampleRate, numSamples, channels) => {
            audioSampleRate = Number(sampleRate);
            audioNumSamples = Number(numSamples);
            audioChannels = Number(channels);
            // Each sample is i16 (2 bytes), per channel
            const bytes = audioNumSamples * audioChannels * 2;
            if (bytes > audioBufferBytes) {
                audioBufferPtr = hostAlloc(bytes);
                audioBufferBytes = bytes;
            }
            return BigInt(audioBufferPtr);
        },
        host_audio_play: () => {
            if (!audioCtx) {
                audioCtx = new AudioContext({ sampleRate: audioSampleRate });
            }

            audioPendingPlay = true;
            requestAudioUnlock();
            return 0n;
        },
        host_audio_sample_rate: () => BigInt(audioSampleRate),
        // Audio streaming using ScriptProcessorNode with double-buffering
        host_audio_stream_init: (sampleRate, bufferSize) => {
            audioSampleRate = Number(sampleRate);
            audioStreamBufferSize = AUDIO_SCRIPT_BUFFER_SIZE;
            audioChannels = 1;
            audioStreamMode = true;
            audioStreamStarted = false;
            audioWriteBuffer = 0;
            audioReadBuffer = 0;
            audioBuffer0Ready = false;
            audioBuffer1Ready = false;
            if (AUDIO_BUFFER_0_OFFSET === 0) {
                AUDIO_BUFFER_0_OFFSET = hostAlloc(AUDIO_SCRIPT_BUFFER_SIZE * 2);  // samples * 2 bytes
                AUDIO_BUFFER_1_OFFSET = hostAlloc(AUDIO_SCRIPT_BUFFER_SIZE * 2);
            }
            
            if (!audioCtx) {
                audioCtx = new AudioContext({ sampleRate: audioSampleRate });
            }
            
            // Create ScriptProcessorNode with larger buffer
            audioScriptNode = audioCtx.createScriptProcessor(AUDIO_SCRIPT_BUFFER_SIZE, 0, 1);
            
            audioScriptNode.onaudioprocess = (e) => {
                const output = e.outputBuffer.getChannelData(0);
                const bufSize = AUDIO_SCRIPT_BUFFER_SIZE;
                
                // Read from the ready buffer
                let bufferOffset, hasData;
                if (audioReadBuffer === 0 && audioBuffer0Ready) {
                    bufferOffset = AUDIO_BUFFER_0_OFFSET;
                    hasData = true;
                    audioBuffer0Ready = false;
                    audioReadBuffer = 1;
                } else if (audioReadBuffer === 1 && audioBuffer1Ready) {
                    bufferOffset = AUDIO_BUFFER_1_OFFSET;
                    hasData = true;
                    audioBuffer1Ready = false;
                    audioReadBuffer = 0;
                } else if (audioBuffer0Ready) {
                    bufferOffset = AUDIO_BUFFER_0_OFFSET;
                    hasData = true;
                    audioBuffer0Ready = false;
                    audioReadBuffer = 1;
                } else if (audioBuffer1Ready) {
                    bufferOffset = AUDIO_BUFFER_1_OFFSET;
                    hasData = true;
                    audioBuffer1Ready = false;
                    audioReadBuffer = 0;
                } else {
                    hasData = false;
                }
                
                if (hasData) {
                    const view = new Int16Array(memory.buffer, bufferOffset, bufSize);
                    for (let i = 0; i < bufSize; i++) {
                        output[i] = view[i] / 32768.0;
                    }
                } else {
                    // Silence if no buffer ready
                    for (let i = 0; i < bufSize; i++) {
                        output[i] = 0;
                    }
                }
            };
            
            // Return pointer to write buffer 0
            audioBufferPtr = AUDIO_BUFFER_0_OFFSET;
            return BigInt(audioBufferPtr);
        },
        host_audio_stream_write: () => {
            if (!audioStreamMode || !audioCtx) return 0n;

            requestAudioUnlock();
            
            // Mark current write buffer as ready and switch to other buffer
            if (audioWriteBuffer === 0) {
                audioBuffer0Ready = true;
                audioWriteBuffer = 1;
                audioBufferPtr = AUDIO_BUFFER_1_OFFSET;
            } else {
                audioBuffer1Ready = true;
                audioWriteBuffer = 0;
                audioBufferPtr = AUDIO_BUFFER_0_OFFSET;
            }
            
            // Return next buffer pointer for WASM to write to
            return BigInt(audioBufferPtr);
        },
        host_audio_stream_needs_samples: () => {
            // Returns true (-1) if we need more samples, false (0) if buffers are full
            if (!audioStreamMode) return 0n;
            // Need samples if the current write buffer is not marked ready
            if (audioWriteBuffer === 0 && !audioBuffer0Ready) return -1n;
            if (audioWriteBuffer === 1 && !audioBuffer1Ready) return -1n;
            return 0n;
        },
        // WebGL fullscreen fragment shader
        host_webgl_init: (shaderPtr, shaderLen, width, height) => {
            if (webglMode) return 0n;

            const w = Number(width);
            const h = Number(height);
            const fragmentSource = decodeString(shaderPtr, shaderLen);

            webglCanvas = document.getElementById('canvas');
            if (!webglCanvas) {
                webglCanvas = document.createElement('canvas');
                webglCanvas.id = 'canvas';
                document.body.insertBefore(webglCanvas, document.body.firstChild);
            }
            webglCanvas.width = w;
            webglCanvas.height = h;
            webglCanvas.style.display = 'block';
            updateCanvasLayout();
            ensurePointerHandlers();

            webglContext = webglCanvas.getContext('webgl');
            if (!webglContext) {
                console.error('WebGL not supported');
                if (outputElement) {
                    outputElement.textContent = 'WebGL not supported in this browser';
                }
                return -1n;
            }

            try {
                webglProgram = createWebglProgram(webglContext, fragmentSource);
            } catch (err) {
                console.error('WebGL shader setup failed:', err);
                if (outputElement) {
                    outputElement.textContent = `WebGL shader setup failed:
${String(err)}`;
                }
                return -1n;
            }

            webglPositionBuffer = webglContext.createBuffer();
            webglContext.bindBuffer(webglContext.ARRAY_BUFFER, webglPositionBuffer);
            webglContext.bufferData(
                webglContext.ARRAY_BUFFER,
                new Float32Array([
                    -1.0, -1.0,
                    3.0, -1.0,
                    -1.0, 3.0,
                ]),
                webglContext.STATIC_DRAW,
            );

            webglContext.useProgram(webglProgram);
            const positionLocation = webglContext.getAttribLocation(webglProgram, 'a_position');
            if (positionLocation >= 0) {
                webglContext.enableVertexAttribArray(positionLocation);
                webglContext.vertexAttribPointer(positionLocation, 2, webglContext.FLOAT, false, 0, 0);
            }

            if (outputElement) {
                outputElement.style.display = 'none';
            }

            webglMode = true;
            startTime = performance.now();
            updateCanvasLayout();
            return 0n;
        },
        host_webgl_uniform1i: (namePtr, nameLen, value) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform1i(location, Number(value));
            return 0n;
        },
        host_webgl_uniform2i: (namePtr, nameLen, x, y) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform2i(location, Number(x), Number(y));
            return 0n;
        },
        host_webgl_uniform1iv: (namePtr, nameLen, valuesPtr, count) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform1iv(location, decodeI64Array(valuesPtr, count));
            return 0n;
        },
        host_webgl_uniform2iv: (namePtr, nameLen, valuesPtr, count) => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            const name = decodeString(namePtr, nameLen);
            const location = webglContext.getUniformLocation(webglProgram, name);
            if (location === null) return -1n;
            webglContext.useProgram(webglProgram);
            webglContext.uniform2iv(location, decodeI64Array(valuesPtr, Number(count) * 2));
            return 0n;
        },
        host_webgl_render: () => {
            if (!webglMode || !webglContext || !webglProgram) return 0n;

            webglContext.viewport(0, 0, webglCanvas.width, webglCanvas.height);
            webglContext.useProgram(webglProgram);
            webglContext.drawArrays(webglContext.TRIANGLES, 0, 3);
            return 0n;
        },
        // General-purpose batched 3D GPU surface
        host_gpu_init: (width, height) => {
            if (gpuMode) return 0n;
            const w = Number(width);
            const h = Number(height);
            gpuCanvas = document.getElementById('canvas');
            if (!gpuCanvas) {
                gpuCanvas = document.createElement('canvas');
                gpuCanvas.id = 'canvas';
                document.body.insertBefore(gpuCanvas, document.body.firstChild);
            }
            // Back the canvas at the window's real pixel size so the game's
            // per-frame aspect/viewport math matches the display and the
            // content is never stretched. The requested w/h is only a fallback.
            gpuCanvas.width = Math.max(1, Math.floor(window.innerWidth || w));
            gpuCanvas.height = Math.max(1, Math.floor(window.innerHeight || h));
            gpuCanvas.style.display = 'block';
            webglCanvas = gpuCanvas;
            webglMode = true;
            updateCanvasLayout();
            ensurePointerHandlers();
            ensureKeyboardHandlers();

            gpuGL = gpuCanvas.getContext('webgl', { antialias: true, depth: true, alpha: false, preserveDrawingBuffer: false });
            if (!gpuGL) {
                console.error('WebGL not supported');
                return -1n;
            }
            try {
                gpuProgram = gpuCreateProgram(gpuGL);
            } catch (err) {
                console.error('GPU shader setup failed:', err);
                return -1n;
            }
            gpuGL.useProgram(gpuProgram);
            gpuLocPos = gpuGL.getAttribLocation(gpuProgram, 'a_pos');
            gpuLocUV = gpuGL.getAttribLocation(gpuProgram, 'a_uv');
            gpuLocColor = gpuGL.getAttribLocation(gpuProgram, 'a_color');
            gpuLocProj = gpuGL.getUniformLocation(gpuProgram, 'u_proj');
            gpuLocView = gpuGL.getUniformLocation(gpuProgram, 'u_view');
            gpuLocSampler = gpuGL.getUniformLocation(gpuProgram, 'u_tex');
            gpuLocUseTex = gpuGL.getUniformLocation(gpuProgram, 'u_use_tex');

            gpuVbo = gpuGL.createBuffer();
            gpuWhiteTex = gpuGL.createTexture();
            gpuGL.bindTexture(gpuGL.TEXTURE_2D, gpuWhiteTex);
            gpuGL.texImage2D(gpuGL.TEXTURE_2D, 0, gpuGL.RGBA, 1, 1, 0, gpuGL.RGBA, gpuGL.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_MIN_FILTER, gpuGL.NEAREST);
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_MAG_FILTER, gpuGL.NEAREST);
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_WRAP_S, gpuGL.CLAMP_TO_EDGE);
            gpuGL.texParameteri(gpuGL.TEXTURE_2D, gpuGL.TEXTURE_WRAP_T, gpuGL.CLAMP_TO_EDGE);

            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuIdentity);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuIdentity);
            gpuBindTextureSlot(0);

            gpuGL.enable(gpuGL.DEPTH_TEST);
            gpuGL.depthFunc(gpuGL.LEQUAL);
            gpuGL.disable(gpuGL.BLEND);

            if (outputElement) outputElement.style.display = 'none';
            gpuMode = true;
            startTime = performance.now();
            updateCanvasLayout();
            return 0n;
        },
        host_gpu_set_viewport: (w, h) => {
            if (!gpuMode) return 0n;
            gpuGL.viewport(0, 0, Number(w), Number(h));
            return 0n;
        },
        host_gpu_clear: (r_q, g_q, b_q) => {
            if (!gpuMode) return 0n;
            gpuGL.clearColor(q16ToF32(r_q), q16ToF32(g_q), q16ToF32(b_q), 1.0);
            gpuGL.clear(gpuGL.COLOR_BUFFER_BIT | gpuGL.DEPTH_BUFFER_BIT);
            return 0n;
        },
        host_gpu_set_perspective_frustum: (l_q, r_q, b_q, t_q, n_q, f_q) => {
            if (!gpuMode) return 0n;
            gpuMakeFrustum(gpuProj, q16ToF32(l_q), q16ToF32(r_q), q16ToF32(b_q), q16ToF32(t_q), q16ToF32(n_q), q16ToF32(f_q));
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuProj);
            return 0n;
        },
        host_gpu_set_view_matrix: (matPtr) => {
            if (!gpuMode) return 0n;
            const view = new Float32Array(memory.buffer, Number(matPtr), 16);
            for (let i = 0; i < 16; i++) gpuView[i] = view[i];
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuView);
            return 0n;
        },
        host_gpu_set_texture: (texId) => {
            if (!gpuMode) return 0n;
            gpuGL.useProgram(gpuProgram);
            gpuBindTextureSlot(Number(texId));
            return 0n;
        },
        host_gpu_set_blend: (mode) => {
            if (!gpuMode) return 0n;
            const m = Number(mode);
            if (m === 0) {
                gpuGL.disable(gpuGL.BLEND);
            } else if (m === 1) {
                gpuGL.enable(gpuGL.BLEND);
                gpuGL.blendFunc(gpuGL.SRC_ALPHA, gpuGL.ONE_MINUS_SRC_ALPHA);
            } else {
                gpuGL.enable(gpuGL.BLEND);
                gpuGL.blendFunc(gpuGL.SRC_ALPHA, gpuGL.ONE);
            }
            return 0n;
        },
        host_gpu_set_depth_test: (on) => {
            if (!gpuMode) return 0n;
            if (Number(on) !== 0) gpuGL.enable(gpuGL.DEPTH_TEST);
            else gpuGL.disable(gpuGL.DEPTH_TEST);
            return 0n;
        },
        host_gpu_set_depth_write: (on) => {
            if (!gpuMode) return 0n;
            gpuGL.depthMask(Number(on) !== 0);
            return 0n;
        },
        host_gpu_set_line_width: (w_q) => {
            if (!gpuMode) return 0n;
            gpuGL.lineWidth(q16ToF32(w_q));
            return 0n;
        },
        host_gpu_submit: (kind, ptr, count) => {
            if (!gpuMode) return 0n;
            const k = Number(kind);
            const n = Number(count);
            if (n <= 0) return 0n;
            const gl = gpuGL;
            const stride = 9 * 4;
            const verts = new Float32Array(memory.buffer, Number(ptr), n * 9);
            gl.useProgram(gpuProgram);
            gl.bindBuffer(gl.ARRAY_BUFFER, gpuVbo);
            gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STREAM_DRAW);
            gl.enableVertexAttribArray(gpuLocPos);
            gl.vertexAttribPointer(gpuLocPos, 3, gl.FLOAT, false, stride, 0);
            if (gpuLocUV >= 0) {
                gl.enableVertexAttribArray(gpuLocUV);
                gl.vertexAttribPointer(gpuLocUV, 2, gl.FLOAT, false, stride, 12);
            }
            if (gpuLocColor >= 0) {
                gl.enableVertexAttribArray(gpuLocColor);
                gl.vertexAttribPointer(gpuLocColor, 4, gl.FLOAT, false, stride, 20);
            }
            if (k === 0) {
                const quads = (n / 4) | 0;
                gpuEnsureQuadIndices(quads);
                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gpuQuadIbo);
                gl.drawElements(gl.TRIANGLES, quads * 6, gl.UNSIGNED_SHORT, 0);
            } else if (k === 1) {
                gpuEnsureStripIndices(n);
                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gpuStripIbo);
                gl.drawElements(gl.TRIANGLES, Math.max(n - 2, 0) * 3, gl.UNSIGNED_SHORT, 0);
            } else if (k === 2) {
                gl.drawArrays(gl.TRIANGLES, 0, n);
            } else if (k === 3) {
                gl.drawArrays(gl.LINES, 0, n);
            }
            return 0n;
        },
        host_gpu_overlay_begin: (sw, sh) => {
            if (!gpuMode) return 0n;
            const w = Number(sw);
            const h = Number(sh);
            gpuMakeOrtho(gpuOrthoProj, 0, w, h, 0, -1, 1);
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuOrthoProj);
            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuIdentity);
            gpuSavedDepthTest = gpuGL.getParameter(gpuGL.DEPTH_TEST);
            gpuSavedDepthWrite = gpuGL.getParameter(gpuGL.DEPTH_WRITEMASK);
            gpuSavedBlend = gpuGL.getParameter(gpuGL.BLEND);
            gpuGL.disable(gpuGL.DEPTH_TEST);
            gpuGL.depthMask(false);
            // Overlay content (HUD text, panels, speed lines) is alpha-keyed,
            // so blend must be on or transparent texels render as opaque black.
            gpuGL.enable(gpuGL.BLEND);
            gpuGL.blendFunc(gpuGL.SRC_ALPHA, gpuGL.ONE_MINUS_SRC_ALPHA);
            gpuOverlayActive = true;
            return 0n;
        },
        host_gpu_overlay_end: () => {
            if (!gpuMode) return 0n;
            gpuGL.useProgram(gpuProgram);
            gpuGL.uniformMatrix4fv(gpuLocProj, false, gpuProj);
            gpuGL.uniformMatrix4fv(gpuLocView, false, gpuView);
            if (gpuSavedDepthTest) gpuGL.enable(gpuGL.DEPTH_TEST);
            gpuGL.depthMask(!!gpuSavedDepthWrite);
            if (!gpuSavedBlend) gpuGL.disable(gpuGL.BLEND);
            gpuOverlayActive = false;
            return 0n;
        },
        host_gpu_create_texture: (width, height, pixelsPtr, repeat, nearest) => {
            if (!gpuMode) return 0n;
            const gl = gpuGL;
            const w = Number(width);
            const h = Number(height);
            const pixels = new Uint8Array(memory.buffer, Number(pixelsPtr), w * h * 4);
            const tex = gl.createTexture();
            gl.bindTexture(gl.TEXTURE_2D, tex);
            gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(pixels));
            const filter = (Number(nearest) !== 0) ? gl.NEAREST : gl.LINEAR;
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
            const wrap = (Number(repeat) !== 0) ? gl.REPEAT : gl.CLAMP_TO_EDGE;
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrap);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrap);
            gpuTextures.push(tex);
            return BigInt(gpuTextures.length - 1);
        },
        host_gpu_present: () => {
            return 0n;
        },
        host_gpu_window_width: () => BigInt(gpuCanvas ? gpuCanvas.width : 0),
        host_gpu_window_height: () => BigInt(gpuCanvas ? gpuCanvas.height : 0),
        host_audio_queue_init: (sampleRate, channels) => {
            audioQueueRate = Number(sampleRate);
            audioQueueChannels = Number(channels);
            audioQueueCapacity = audioQueueRate * audioQueueChannels * 2;  // ~2 s of buffer
            audioQueueRing = new Int16Array(audioQueueCapacity);
            audioQueueRead = 0;
            audioQueueWrite = 0;
            audioQueueCount = 0;
            try {
                audioQueueEnsureContext();
            } catch (err) {
                console.error('Audio queue init failed:', err);
                return -1n;
            }
            return 0n;
        },
        host_audio_queue_push: (ptr, nBytes) => {
            if (!audioQueueRing) return 0n;
            // Until a gesture unlocks audio nothing plays: samples queued
            // then would all sound late, at once. They are taken and dropped.
            if (!audioCtx || audioCtx.state !== 'running') return nBytes;
            const samples = Number(nBytes) >> 1;
            const view = new Int16Array(memory.buffer, Number(ptr), samples);
            for (let i = 0; i < samples; i++) {
                if (audioQueueCount >= audioQueueCapacity) break;
                audioQueueRing[audioQueueWrite] = view[i];
                audioQueueWrite = (audioQueueWrite + 1) % audioQueueCapacity;
                audioQueueCount++;
            }
            return BigInt(samples * 2);
        },
        host_audio_queue_size: () => BigInt(audioQueueCount * 2),
    }
};

function animationLoop() {
    if ((!canvasMode && !audioStreamMode && !webglMode && !gpuMode) || !wasmInstance) return;

    frameCount++;
    try {
        wasmInstance.exports.main();
    } catch (err) {
        endProgram(err);
        return;
    }
    flushConsole();
    clearKeyboardFrameState();
    requestAnimationFrame(animationLoop);
}

function setupServerLifecycle() {
    if (window.location.protocol !== 'http:' && window.location.protocol !== 'https:') {
        return;
    }

    const heartbeat = () => {
        fetch('/__udewy_heartbeat__', { cache: 'no-store' }).catch(() => {});
    };

    heartbeat();
    const timer = setInterval(heartbeat, 2000);
    const notifyClose = () => {
        clearInterval(timer);
        navigator.sendBeacon('/__udewy_close__', '');
    };

    window.addEventListener('pagehide', notifyClose, { once: true });
    window.addEventListener('beforeunload', notifyClose, { once: true });
}
