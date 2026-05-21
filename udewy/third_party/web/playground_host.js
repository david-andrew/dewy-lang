// Browser-side bridge for the udewy playground page.
//
// The playground page (compiled from playground.udewy) declares
// `extern host_playground_run`. This file installs that import via the
// `beforeUdewyInstantiate(imports)` hook. Everything it needs -- the
// web-compiler wasm, wabt.js, and this script itself -- is inlined into
// the playground HTML via udewy's `link_artifacts` mechanism: the wasm
// shows up as `<script data-wasm-artifact="web_compiler.wasm" ...>` and
// wabt.js is concatenated into the same host script block.

(() => {
    let wabtPromise = null;
    let compilerModulePromise = null;
    const textDecoder = new TextDecoder();
    const textEncoder = new TextEncoder();

    function loadWabt() {
        if (!wabtPromise) {
            if (typeof WabtModule !== 'function') {
                wabtPromise = Promise.reject(new Error('wabt.js not loaded'));
            } else {
                wabtPromise = WabtModule();
            }
        }
        return wabtPromise;
    }

    // Parse just enough of a wasm binary to extract the min-pages of the
    // first imported memory. We need this because WebAssembly.Module.imports
    // doesn't surface the limits descriptor and we have to provide a memory
    // import of at least the declared size.
    function readWasmMemoryPages(bytes) {
        let p = 8;
        function readLeb() {
            let r = 0, s = 0;
            while (true) {
                const b = bytes[p++];
                r |= (b & 0x7f) << s;
                if ((b & 0x80) === 0) return r;
                s += 7;
            }
        }
        function skipString() { const n = readLeb(); p += n; }
        while (p < bytes.length) {
            const id = bytes[p++];
            const size = readLeb();
            const end = p + size;
            if (id === 2) {
                const count = readLeb();
                for (let i = 0; i < count; i++) {
                    skipString();
                    skipString();
                    const kind = bytes[p++];
                    if (kind === 0) { readLeb(); }
                    else if (kind === 1) { p += 1; const f = bytes[p++]; readLeb(); if (f & 1) readLeb(); }
                    else if (kind === 2) { const f = bytes[p++]; const min = readLeb(); return min; }
                    else if (kind === 3) { p += 2; }
                }
            }
            p = end;
        }
        return null;
    }

    function loadCompilerModule() {
        if (!compilerModulePromise) {
            const el = document.querySelector('script[data-wasm-artifact="web_compiler.wasm"]');
            if (!el) {
                compilerModulePromise = Promise.reject(new Error('web compiler wasm not embedded in page'));
            } else {
                const bin = atob(el.textContent.trim());
                const bytes = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                const pages = readWasmMemoryPages(bytes) ?? 32;
                compilerModulePromise = WebAssembly.compile(bytes).then(m => ({ module: m, pages }));
            }
        }
        return compilerModulePromise;
    }

    // Compile a udewy source string by spinning up a fresh compiler wasm
    // instance, feeding it the source bytes, and capturing the WAT it
    // emits. Returns { ok, wat, log }.
    async function compileSource(source) {
        const { module: compilerModule, pages } = await loadCompilerModule();
        const stderrChunks = [];
        let watOutput = null;
        const memory = new WebAssembly.Memory({ initial: pages });
        const srcBytes = textEncoder.encode(source);

        function read(ptr, len) {
            return textDecoder.decode(new Uint8Array(memory.buffer, Number(ptr), Number(len)));
        }

        const env = {
            memory,
            host_log: (ptr, len) => { stderrChunks.push(read(ptr, len)); return 0n; },
            host_log_int: (v) => { stderrChunks.push(String(v)); return 0n; },
            host_exit: (code) => { throw new Error(`host_exit(${code})`); },
            host_compile_get_src: (buf, cap) => {
                const n = Math.min(srcBytes.length, Number(cap));
                new Uint8Array(memory.buffer, Number(buf), n).set(srcBytes.subarray(0, n));
                return BigInt(n);
            },
            host_compile_emit_wat: (buf, len) => {
                watOutput = read(buf, len);
                return 0n;
            },
        };
        for (const imp of WebAssembly.Module.imports(compilerModule)) {
            if (imp.module === 'env' && !(imp.name in env)) {
                env[imp.name] = (...args) => 0n;
            }
        }

        let trap = null;
        try {
            const instance = await WebAssembly.instantiate(compilerModule, { env });
            instance.exports.main();
        } catch (e) {
            trap = e;
        }

        const log = stderrChunks.join('');
        if (watOutput) {
            return { ok: true, wat: watOutput, log };
        }
        return { ok: false, wat: null, log: log || (trap ? trap.message : 'unknown error') };
    }

    async function assembleWat(wat) {
        const wabt = await loadWabt();
        const module = wabt.parseWat('<playground>', wat);
        try {
            module.resolveNames();
            module.validate();
            return module.toBinary({ log: false, write_debug_names: false }).buffer;
        } finally {
            module.destroy();
        }
    }

    // Minimal iframe shim. Receives wasm bytes and runs them with a small
    // host env. User programs only get host_log/host_log_int/host_exit;
    // they don't see dom.udewy in this minimal playground.
    const IFRAME_HTML = `<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body { margin: 0; padding: 0; height: 100%; background: #ffffff; color: #232734; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
#out { padding: 1rem; white-space: pre-wrap; margin: 0; font-size: 0.9rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
</style></head><body><pre id="out"></pre><script>
(function() {
    const out = document.getElementById('out');
    const decoder = new TextDecoder();
    function emit(text) { out.textContent += text; }

    function readWasmMemoryPages(b) {
        let p = 8;
        function rl() { let r = 0, s = 0; while (true) { const x = b[p++]; r |= (x & 0x7f) << s; if ((x & 0x80) === 0) return r; s += 7; } }
        function skipStr() { const n = rl(); p += n; }
        while (p < b.length) {
            const id = b[p++], sz = rl(), end = p + sz;
            if (id === 2) {
                const n = rl();
                for (let i = 0; i < n; i++) {
                    skipStr(); skipStr();
                    const k = b[p++];
                    if (k === 0) rl();
                    else if (k === 1) { p += 1; const f = b[p++]; rl(); if (f & 1) rl(); }
                    else if (k === 2) { p++; return rl(); }
                    else if (k === 3) p += 2;
                }
            }
            p = end;
        }
        return null;
    }

    window.addEventListener('message', async (ev) => {
        const data = ev.data;
        if (!data || data.kind !== 'udewy-run') return;
        const bytes = new Uint8Array(data.bytes);
        out.textContent = '';
        const pages = readWasmMemoryPages(bytes) ?? 32;
        const memory = new WebAssembly.Memory({ initial: pages });
        function readStr(p, l) { return decoder.decode(new Uint8Array(memory.buffer, Number(p), Number(l))); }
        const env = {
            memory,
            host_log: (p, l) => { emit(readStr(p, l)); return 0n; },
            host_log_int: (v) => { emit(String(v)); return 0n; },
            host_exit: (c) => { throw new Error('exit ' + c); },
        };
        let module;
        try {
            module = await WebAssembly.compile(bytes);
        } catch (e) {
            emit('CompileError: ' + e.message + '\\n');
            return;
        }
        for (const imp of WebAssembly.Module.imports(module)) {
            if (imp.module === 'env' && !(imp.name in env)) env[imp.name] = () => 0n;
        }
        try {
            const instance = await WebAssembly.instantiate(module, { env });
            const result = instance.exports.main();
            if (result !== undefined && result !== 0n) emit('\\nexit ' + result + '\\n');
        } catch (e) {
            emit('\\nRuntime error: ' + e.message + '\\n');
        }
    });
    parent.postMessage({ kind: 'udewy-iframe-ready' }, '*');
})();
<\/script></body></html>`;

    function recreateIframe() {
        const host = document.getElementById('udewy-iframe-host');
        if (!host) return null;
        host.replaceChildren();
        const iframe = document.createElement('iframe');
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = '0';
        iframe.setAttribute('sandbox', 'allow-scripts');
        iframe.setAttribute('srcdoc', IFRAME_HTML);
        host.appendChild(iframe);
        return iframe;
    }

    function setStatus(text, isError) {
        const status = document.getElementById('udewy-status');
        if (!status) return;
        status.textContent = text;
        status.style.background = isError ? '#fdecea' : '#f0fbf4';
        status.style.color = isError ? '#a3261a' : '#1f6f3d';
    }

    async function runProgram(source) {
        setStatus('Compiling...', false);
        let compileResult;
        try {
            compileResult = await compileSource(source);
        } catch (e) {
            setStatus('Compiler error: ' + e.message, true);
            return;
        }
        if (!compileResult.ok) {
            setStatus(compileResult.log || 'Compile failed.', true);
            return;
        }
        let wasmBytes;
        try {
            wasmBytes = await assembleWat(compileResult.wat);
        } catch (e) {
            setStatus('wat2wasm error: ' + e.message, true);
            return;
        }
        const iframe = recreateIframe();
        if (!iframe) {
            setStatus('Could not create iframe runner.', true);
            return;
        }
        const ready = new Promise(resolve => {
            const onMessage = (ev) => {
                if (ev.data && ev.data.kind === 'udewy-iframe-ready' && ev.source === iframe.contentWindow) {
                    window.removeEventListener('message', onMessage);
                    resolve();
                }
            };
            window.addEventListener('message', onMessage);
        });
        await ready;
        iframe.contentWindow.postMessage({ kind: 'udewy-run', bytes: wasmBytes.buffer || wasmBytes }, '*');
        setStatus('Running. Compile log:\n' + (compileResult.log || '(no diagnostics)'), false);
    }

    // Editor keyboard shortcuts:
    //   Ctrl/Cmd+Enter: trigger the Run button from anywhere on the page.
    //   Plain Enter inside the editor: insert a newline plus the same
    //   leading whitespace the current line had. Goes through execCommand
    //   so the editor's input listener still fires (re-highlighting +
    //   caret-restore).
    function handlePlaygroundKeys(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
            const btn = document.getElementById('udewy-run');
            if (btn) {
                e.preventDefault();
                btn.click();
            }
            return;
        }
        if (e.key === 'Tab' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
            const editor = document.getElementById('udewy-editor');
            if (!editor || !editor.contains(e.target)) return;
            e.preventDefault();
            document.execCommand('insertText', false, '    ');
            return;
        }
        if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
        const editor = document.getElementById('udewy-editor');
        if (!editor || !editor.contains(e.target)) return;
        const sel = window.getSelection();
        if (!sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        const pre = range.cloneRange();
        pre.selectNodeContents(editor);
        pre.setEnd(range.endContainer, range.endOffset);
        const offset = pre.toString().length;
        const text = editor.textContent;
        let lineStart = offset;
        while (lineStart > 0 && text[lineStart - 1] !== '\n') lineStart--;
        let indent = '';
        for (let i = lineStart; i < text.length; i++) {
            if (text[i] !== ' ' && text[i] !== '\t') break;
            indent += text[i];
        }
        e.preventDefault();
        document.execCommand('insertText', false, '\n' + indent);
    }
    document.addEventListener('keydown', handlePlaygroundKeys);

    window.beforeUdewyInstantiate = async (imports) => {
        const playgroundMemory = imports.env.memory;
        imports.env.host_playground_run = (srcPtr, srcLen) => {
            const src = textDecoder.decode(new Uint8Array(playgroundMemory.buffer, Number(srcPtr), Number(srcLen)));
            runProgram(src);
            return 0n;
        };
    };
})();
