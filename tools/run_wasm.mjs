#!/usr/bin/env node
// run_wasm.mjs MODULE.wasm : run a wasm32 module from the Dewy or µDewy
// toolchain outside a browser. The host imports a command line can give are
// provided: `host_log` writes the bytes to standard output, `host_log_int`
// writes a number, `host_exit` ends the process with its status, and
// `host_time`/`host_random` behave as in the browser harness. Any other
// import (DOM, canvas, audio) fails when called. The exit status is `main`'s
// result.
import fs from 'node:fs';

const bytes = fs.readFileSync(process.argv[2]);
const module = new WebAssembly.Module(bytes);

// The imported memory's minimum page count, from the import section.
function memoryPages(data) {
    let at = 8;
    const leb = () => {
        let result = 0, shift = 0, byte;
        do { byte = data[at++]; result += (byte & 0x7f) * 2 ** shift; shift += 7; } while (byte & 0x80);
        return result;
    };
    const name = () => { const length = leb(); at += length; };
    while (at < data.length) {
        const id = data[at++];
        const size = leb();
        const end = at + size;
        if (id === 2) {
            const count = leb();
            for (let i = 0; i < count; i++) {
                name(); name();
                const kind = data[at++];
                if (kind === 0) leb();
                else if (kind === 1) { at++; const flags = leb(); leb(); if (flags & 1) leb(); }
                else if (kind === 2) { const flags = leb(); const minimum = leb(); if (flags & 1) leb(); return minimum; }
                else if (kind === 3) { at += 2; }
            }
        }
        at = end;
    }
    return 1;
}

const memory = new WebAssembly.Memory({ initial: memoryPages(bytes) });
const env = { memory };
for (const entry of WebAssembly.Module.imports(module)) {
    if (entry.module === 'env' && entry.kind === 'function') {
        env[entry.name] = () => { throw new Error(`the host import ${entry.name} is not available outside a browser`); };
    }
}
env.host_log = (pointer, length) => {
    fs.writeSync(1, new Uint8Array(memory.buffer, Number(pointer), Number(length)));
    return length;
};
env.host_log_int = (value) => { fs.writeSync(1, `${value}\n`); return value; };
env.host_exit = (status) => { process.exit(Number(BigInt.asUintN(8, BigInt(status)))); };
env.host_time = () => BigInt(Date.now());
env.host_random = () => BigInt(Math.floor(Math.random() * Number.MAX_SAFE_INTEGER));

const instance = new WebAssembly.Instance(module, { env });
const status = instance.exports.main();
process.exitCode = Number(BigInt.asUintN(8, BigInt(status)));
