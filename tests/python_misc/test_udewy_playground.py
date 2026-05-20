"""Smoke test the in-browser udewy playground compile pipeline.

Builds the web-compiler (`udewy/bootstrap/web_compiler.udewy`) to wasm32,
then runs it via node.js with `wabt.js` standing in for the browser runtime
to make sure source -> WAT -> wasm -> exit code works end to end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from os import environ
from pathlib import Path
from shutil import which

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_COMPILER_SRC = REPO_ROOT / "udewy" / "bootstrap" / "web_compiler.udewy"
WABT_JS = REPO_ROOT / "udewy" / "third_party" / "web" / "artifacts" / "wabt.js"


HARNESS = r"""
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const wabt = await require(process.argv[2])();
const compilerBytes = fs.readFileSync(process.argv[3]);
const watTemplate = fs.readFileSync(process.argv[4], 'utf8');
const source = JSON.parse(process.argv[5]);
const compilerModule = await WebAssembly.compile(compilerBytes);
const memMatch = watTemplate.match(/\(import "env" "memory" \(memory (\d+)\)/);
const pages = memMatch ? Number(memMatch[1]) : 32;

const dec = new TextDecoder();
const enc = new TextEncoder();
const memory = new WebAssembly.Memory({ initial: pages });
const srcBytes = enc.encode(source);
let wat = null;
const log = [];
const env = {
    memory,
    host_log: (p, l) => { log.push(dec.decode(new Uint8Array(memory.buffer, Number(p), Number(l)))); return 0n; },
    host_log_int: (v) => { log.push(String(v)); return 0n; },
    host_exit: (c) => { throw new Error('exit ' + c); },
    host_compile_get_src: (buf, cap) => {
        const n = Math.min(srcBytes.length, Number(cap));
        new Uint8Array(memory.buffer, Number(buf), n).set(srcBytes.subarray(0, n));
        return BigInt(n);
    },
    host_compile_emit_wat: (buf, len) => {
        wat = dec.decode(new Uint8Array(memory.buffer, Number(buf), Number(len)));
        return 0n;
    },
};
for (const imp of WebAssembly.Module.imports(compilerModule)) {
    if (imp.module === 'env' && !(imp.name in env)) env[imp.name] = () => 0n;
}
try {
    const inst = await WebAssembly.instantiate(compilerModule, { env });
    inst.exports.main();
} catch (e) {
    // expected on syntax errors
}
const result = { wat, log: log.join('') };
if (wat) {
    const mod = wabt.parseWat('<test>', wat);
    mod.resolveNames();
    mod.validate();
    const bin = mod.toBinary({ log: false, write_debug_names: false }).buffer;
    mod.destroy();

    const userMem = new WebAssembly.Memory({ initial: 32 });
    let out = '';
    const userEnv = {
        memory: userMem,
        host_log: (p, l) => { out += dec.decode(new Uint8Array(userMem.buffer, Number(p), Number(l))); return 0n; },
        host_log_int: (v) => { out += String(v); return 0n; },
        host_exit: (c) => { throw new Error('exit ' + c); },
    };
    const userMod = await WebAssembly.compile(bin);
    for (const imp of WebAssembly.Module.imports(userMod)) {
        if (imp.module === 'env' && !(imp.name in userEnv)) userEnv[imp.name] = () => 0n;
    }
    try {
        const inst = await WebAssembly.instantiate(userMod, { env: userEnv });
        const exit = inst.exports.main();
        result.exit = String(exit);
        result.out = out;
    } catch (e) {
        result.runtimeError = e.message;
        result.out = out;
    }
}
process.stdout.write(JSON.stringify(result));
"""


@pytest.fixture(scope="session")
def compiler_wasm(tmp_path_factory) -> Path:
    if which("node") is None:
        pytest.skip("node not installed")
    env = {**environ, "PYTHONPATH": str(REPO_ROOT)}
    # Make sure wabt.js exists for the node harness; setup_web.py is the
    # source of truth for that download.
    if not WABT_JS.exists():
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "udewy" / "third_party" / "web" / "setup_web_compiler.py")],
            check=True, env=env, capture_output=True,
        )
    out_dir = tmp_path_factory.mktemp("playground")
    subprocess.run(
        [sys.executable, "-m", "udewy", "-c", "--target", "wasm32", str(WEB_COMPILER_SRC)],
        cwd=out_dir, check=True, env=env,
    )
    html = (out_dir / "__dewycache__" / f"{WEB_COMPILER_SRC.stem}.html").read_text()
    import base64
    import re
    m = re.search(r'<script id="wasm-module"[^>]*>([\s\S]*?)</script>', html)
    assert m, "no wasm-module in compiler HTML"
    wasm_path = out_dir / "compiler.wasm"
    wasm_path.write_bytes(base64.b64decode(m.group(1).strip()))
    wat_path = out_dir / "__dewycache__" / f"{WEB_COMPILER_SRC.stem}.wat"
    return wasm_path, wat_path


def run_pipeline(compiler_wasm, source: str) -> dict:
    wasm_path, wat_path = compiler_wasm
    harness_path = wasm_path.parent / "harness.mjs"
    harness_path.write_text(HARNESS)
    proc = subprocess.run(
        ["node", str(harness_path), str(WABT_JS), str(wasm_path), str(wat_path), json.dumps(source)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(proc.stdout)


def test_playground_compiles_and_runs_hello(compiler_wasm) -> None:
    src = 'let main = ():>int => {\n    __host_log__("hello playground" 16)\n    return 0\n}\n'
    result = run_pipeline(compiler_wasm, src)
    assert result["wat"] is not None, f"no wat emitted; log: {result['log']!r}"
    assert "hello playground" in result["out"]


def test_playground_compiles_arithmetic(compiler_wasm) -> None:
    src = 'let main = ():>int => {\n    let n:int = 7 * 6\n    __log_int__(n)\n    return 0\n}\n'
    result = run_pipeline(compiler_wasm, src)
    assert "42" in result["out"]


def test_playground_surfaces_syntax_errors(compiler_wasm) -> None:
    src = 'let main = ():>int => { return @@@ }\n'
    result = run_pipeline(compiler_wasm, src)
    assert result["wat"] is None
    assert "SyntaxError" in result["log"]


def test_single_file_bundle_contains_everything() -> None:
    """End-to-end: run the artifact-generating script and then invoke
    `udewy -c` directly. The resulting HTML must inline the web-compiler
    wasm, wabt.js, and the host JS via udewy's native link_artifacts
    mechanism -- no Python post-processing involved.
    """
    env = {**environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "udewy" / "third_party" / "web" / "setup_web_compiler.py")],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "udewy", "-c", "--target", "wasm32",
         str(REPO_ROOT / "udewy" / "tests" / "web" / "playground.udewy")],
        cwd=REPO_ROOT, check=True, env=env, capture_output=True,
    )
    html = (REPO_ROOT / "__dewycache__" / "playground.html").read_text()
    assert '<script data-wasm-artifact="web_compiler.wasm"' in html
    assert "WabtModule" in html
    assert "beforeUdewyInstantiate" in html
