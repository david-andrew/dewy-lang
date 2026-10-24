// Sloppy web runtime: instantiates the embedded wasm module and provides its imports.
"use strict";
const sloppy = (() => {
  const isNode = typeof window === "undefined";
  let mem = null, exports = null;
  const logEl = isNode ? null : document.getElementById("log");
  const dec = new TextDecoder();
  let pending = ["", ""];
  const u8 = () => new Uint8Array(mem.buffer);
  const str = (p, n) => dec.decode(u8().subarray(Number(p), Number(p) + Number(n)));
  function out(fd, text) {
    pending[fd - 1] += text;
    let i;
    while ((i = pending[fd - 1].indexOf("\n")) >= 0) {
      const line = pending[fd - 1].slice(0, i);
      pending[fd - 1] = pending[fd - 1].slice(i + 1);
      if (isNode) (fd === 2 ? process.stderr : process.stdout).write(line + "\n");
      else {
        (fd === 2 ? console.error : console.log)(line);
        if (logEl) { const d = document.createElement("div"); d.textContent = line; if (fd === 2) d.style.color = "#f77"; logEl.appendChild(d); }
      }
    }
  }
  class Exit extends Error { constructor(code) { super("exit " + code); this.code = code; } }
  // an error to show: its message and where it was (Firefox's and Safari's stacks leave the
  // message out; Chrome's start with it)
  const errorText = (e) => {
    if (!e || !e.stack) return String(e);
    const m = String(e);
    return e.stack.includes(m) ? e.stack : m + "\n" + e.stack;
  };
  // a panic's call trace, as a native program prints it: the wasm frames of the browser's (or
  // node's) stack, found in the module's "sloppy_lines" section (compiler/wasm.jo: where the
  // program's own calls are). Browsers that give no offsets (Safari) show only the message.
  let wmod = null, callAt = null;
  function readLines() {
    const m = new Map();
    const secs = wmod ? WebAssembly.Module.customSections(wmod, "sloppy_lines") : [];
    if (!secs.length) return m;
    const b = new Uint8Array(secs[0]);
    let i = 0;
    const num = () => { let x = 0, sh = 0, c; do { c = b[i++]; x += (c & 127) * 2 ** sh; sh += 7; } while (c & 128); return x; };
    const strs = () => { const n = num(), a = []; for (let k = 0; k < n; k++) { const l = num(); a.push(dec.decode(b.subarray(i, i + l))); i += l; } return a; };
    const fileNames = strs(), fnNames = strs();
    let at = 0;
    for (let n = num(); n > 0; n--) { at += num(); const f = num(), line = num(), fn = num(); m.set(at, [fileNames[f], line, fnNames[fn]]); }
    return m;
  }
  const fnShown = (s) => s.startsWith("init_") ? "the top level of " + s.slice(5) : s === "lambda" ? "a function literal"
    : s === "op_index" ? "[] (indexing)" : s === "op_set" ? "[]= (indexing)" : s.startsWith("op_") ? "an operator (" + s.slice(3) + ")" : s;
  function panicTrace() {
    let st = "";
    const lim = Error.stackTraceLimit;
    try { Error.stackTraceLimit = 64; st = new Error().stack || ""; } catch (e) {}
    Error.stackTraceLimit = lim;
    if (!callAt) callAt = readLines();
    let shown = 0, lastFn = "";
    for (const m of st.matchAll(/wasm-function\[\d+\]:0x([0-9a-f]+)/g)) {
      const e = callAt.get(parseInt(m[1], 16));
      if (!e) continue;
      if (shown === 24) { out(2, "    ... and more\n"); lastFn = ""; break; }
      out(2, (shown === 0 ? "    in " : "    called from ") + fnShown(e[2]) + " (" + e[0] + ":" + e[1] + ")\n");
      shown++;
      lastFn = e[2];
    }
    // (the page calls update and draw each frame)
    if (lastFn === "update" || lastFn === "draw") out(2, "    called by the game loop, each frame\n");
  }
  const sockets = [];
  const rtcs = [];
  const env = {
    __wasm_write: (fd, p, n) => out(Number(fd), str(p, n)),
    __wasm_exit: (code) => { if (Number(code) === 101) panicTrace(); throw new Exit(Number(code)); },
    __wasm_now: () => performance.now(),
    // (a timer that cannot run while the program does: how long since it last could)
    __wasm_busy: () => isNode ? 0 : performance.now() - lastBreak,
    __wasm_clock: () => Date.now(),
    __wasm_tz: (ms) => -new Date(ms).getTimezoneOffset() * 60,
    __wasm_grow: (n) => BigInt(mem.grow(Number(n))),
    // environment variables: the page's URL parameters (?DEWY_STATS=1, or ?stats)
    __wasm_env: (np, nn, op, cap) => {
      const name = str(np, nn);
      let v = null;
      if (isNode) v = process.env[name] ?? null;
      else {
        const q = new URLSearchParams(location.search);
        let key = name;
        v = q.get(name);
        if (v === null && name.startsWith("DEWY_")) { key = name.slice(5).toLowerCase(); v = q.get(key); }
        // (a parameter written in other letters: ?join= for env("JOIN"))
        if (v === null) for (const [k, x] of q) if (k.toLowerCase() === name.toLowerCase()) { key = k; v = x; break; }
        // (?stats alone is on; ?STUN= with its = is the empty text)
        if (v === "" && !location.search.includes(key + "=")) v = "1";
      }
      if (v === null) return -1n;
      return give(new TextEncoder().encode(v), op, cap);
    },
    // files: the page's own (sloppy.files: path -> Uint8Array), or under node the real ones
    // standard input: node's own; in a page, a box asking for a line (the answer is shown in the
    // output too, after what the program printed); cancelling it ends the input
    __wasm_read_stdin: (p, n) => {
      if (stdin.length === 0) {
        if (isNode) {
          if (!nodeFs) return -1n;
          const b = new Uint8Array(65536);
          let r = 0;
          try { r = nodeFs.readSync(0, b, 0, b.length, null); } catch (e) { return -1n; }
          if (r <= 0) return 0n;
          stdin = b.subarray(0, r);
        } else {
          if (typeof window.prompt !== "function") return -1n;
          const asked = pending[0];
          let t = null;
          try { t = window.prompt(asked.length > 0 ? asked : "Input:", ""); } catch (e) { t = null; }
          if (t === null) return 0n;
          out(1, t + "\n");
          stdin = new TextEncoder().encode(t + "\n");
        }
      }
      const k = Math.min(stdin.length, Number(n));
      u8().set(stdin.subarray(0, k), Number(p));
      stdin = stdin.subarray(k);
      return BigInt(k);
    },
    // (a failure is -errno, as Linux's: -2 no such file, -13 denied, -21 a directory)
    __wasm_read_file: (pp, pn, op, cap) => {
      const path = str(pp, pn);
      if (nodeFs) { try { return give(new Uint8Array(nodeFs.readFileSync(path)), op, cap); } catch (e) { return fsErrno(e); } }
      if (path in files) return give(files[path], op, cap);
      return pageKind(path) === 2 ? -21n : -2n;
    },
    __wasm_write_file: (pp, pn, dp, dn) => {
      const path = str(pp, pn), d = u8().slice(Number(dp), Number(dp) + Number(dn));
      if (nodeFs) { try { nodeFs.writeFileSync(path, d); return 1n; } catch (e) { return fsErrno(e); } }
      if (pageKind(path) === 2) return -21n;
      files[path] = d;
      return 1n;
    },
    // the rest of the file system (lib/std/files.jo): op 1 makes a directory, 2 removes one, 3
    // removes a file, 4 tells what is there (1 a file, 2 a directory, 3 something else); 0 done,
    // or -errno. A page's own files have directories only as the paths of their files, and
    // those made here.
    __wasm_fs: (op, pp, pn) => {
      const path = str(pp, pn).replace(/(.)\/+$/, "$1");
      const o = Number(op);
      if (nodeFs) {
        try {
          if (o === 1) nodeFs.mkdirSync(path);
          else if (o === 2) nodeFs.rmdirSync(path);
          else if (o === 3) nodeFs.unlinkSync(path);
          else if (o === 4) { const st = nodeFs.statSync(path); return st.isFile() ? 1n : st.isDirectory() ? 2n : 3n; }
          return 0n;
        } catch (e) { return fsErrno(e); }
      }
      const kind = pageKind(path);
      if (o === 4) return kind === 0 ? -2n : BigInt(kind);
      if (o === 1) { if (kind !== 0) return -17n; pageDirs.add(path); return 0n; }
      if (o === 2) {
        if (kind === 0) return -2n;
        if (kind !== 2) return -20n;
        if (Object.keys(files).some((f) => f.startsWith(path + "/")) || [...pageDirs].some((d) => d.startsWith(path + "/"))) return -39n;
        pageDirs.delete(path);
        return 0n;
      }
      if (o === 3) { if (kind === 0) return -2n; if (kind === 2) return -21n; delete files[path]; return 0n; }
      return -38n;
    },
    // (lib/crypto.jo's random_bytes)
    __wasm_random: (p, n) => {
      const b = u8().subarray(Number(p), Number(p) + Number(n));
      for (let i = 0; i < b.length; i += 65536) crypto.getRandomValues(b.subarray(i, Math.min(i + 65536, b.length)));
    },
    __wasm_page_url: (op, cap) => (typeof location === "undefined" ? 0n : give(new TextEncoder().encode(location.origin + location.pathname), op, cap)),
    __wasm_download: (pp, pn, np, nn) => {
      const path = str(pp, pn), d = readFile(path);
      if (d === null) return 0n;
      if (nodeFs || typeof document === "undefined") return 1n;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([d]));
      a.download = Number(nn) > 0 ? str(np, nn) : path.split("/").pop();
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 30000);
      return 1n;
    },
    __wasm_list_dir: (pp, pn, op, cap) => {
      const path = str(pp, pn).replace(/\/+$/, "");
      let names = null;
      if (nodeFs) { try { names = nodeFs.readdirSync(path); } catch (e) { return fsErrno(e); } }
      else {
        if (path in files) return -20n;
        const seen = new Set();
        for (const f of [...Object.keys(files), ...pageDirs]) if (f.startsWith(path + "/")) seen.add(f.slice(path.length + 1).split("/")[0]);
        names = seen.size > 0 || pageDirs.has(path) ? [...seen] : null;
      }
      return names === null ? -2n : give(new TextEncoder().encode(names.join("\n")), op, cap);
    },
    // data kept between runs (lib/std/save.jo): the browser's storage for the page, or under
    // node files in $DEWY_SAVE_DIR (else the system's temporary directory)
    __wasm_save_set: (kp, kn, dp, dn) => {
      const key = str(kp, kn);
      // (a length below 0: delete what is kept under key)
      if (Number(dn) < 0) {
        try {
          if (nodeFs) { if (nodeFs.existsSync(saveFile(key))) nodeFs.unlinkSync(saveFile(key)); else return 0n; }
          else { if (localStorage.getItem("sloppy:" + key) === null) return 0n; localStorage.removeItem("sloppy:" + key); }
          return 1n;
        } catch (e) { return 0n; }
      }
      const d = u8().slice(Number(dp), Number(dp) + Number(dn));
      try {
        if (nodeFs) {
          const p = saveFile(key);
          nodeFs.mkdirSync(p.slice(0, p.lastIndexOf("/")), { recursive: true });
          nodeFs.writeFileSync(p, d);
        } else {
          let s = "";
          for (let i = 0; i < d.length; i += 8192) s += String.fromCharCode.apply(null, d.subarray(i, i + 8192));
          localStorage.setItem("sloppy:" + key, btoa(s));
        }
        return 1n;
      } catch (e) { return 0n; }
    },
    // WebSockets (lib/net.jo): poll gives -1 (nothing now), -2 (opened), -3 (closed), or a
    // message's length (written at out when it fits in cap)
    __wasm_ws_open: (p, n) => {
      try {
        const url = str(p, n);
        // (an https page may not open ws:// to another machine: -4, to say why)
        if (typeof location !== "undefined" && location.protocol === "https:" && url.startsWith("ws://")) {
          const h = url.slice(5).split(/[:/]/)[0];
          if (h !== "localhost" && h !== "127.0.0.1" && h !== "[::1]") return -4n;
        }
        const ws = new WebSocket(url);
        ws.binaryType = "arraybuffer";
        const s = { ws, q: [] };
        ws.onopen = () => s.q.push("open");
        ws.onmessage = (e) => s.q.push(typeof e.data === "string" ? new TextEncoder().encode(e.data) : new Uint8Array(e.data));
        ws.onclose = ws.onerror = () => s.q.push("close");
        sockets.push(s);
        return BigInt(sockets.length - 1);
      } catch (e) { return -1n; }
    },
    __wasm_ws_send: (id, p, n) => {
      const s = sockets[Number(id)];
      if (s && s.ws.readyState === 1) s.ws.send(u8().slice(Number(p), Number(p) + Number(n)));
    },
    __wasm_ws_send_text: (id, p, n) => {
      const s = sockets[Number(id)];
      if (s && s.ws.readyState === 1) s.ws.send(new TextDecoder().decode(u8().subarray(Number(p), Number(p) + Number(n))));
    },
    __wasm_ws_poll: (id, op, cap) => {
      const s = sockets[Number(id)];
      if (!s || s.q.length === 0) return -1n;
      const x = s.q[0];
      if (x === "open") { s.q.shift(); return -2n; }
      if (x === "close") return -3n;
      if (x.length > Number(cap)) return BigInt(x.length);
      s.q.shift();
      u8().set(x, Number(op));
      return BigInt(x.length);
    },
    __wasm_ws_close: (id) => { const s = sockets[Number(id)]; if (s) s.ws.close(); },
    // WebRTC data channels between pages (lib/netplay.jo): unordered and never resent, like UDP.
    // The offer, answer and candidates travel through the game's relay: signal_out gives the
    // next one to send (-1: none), signal_in takes one from the other side. poll is as for WebSockets.
    __wasm_rtc_new: (init, sp, sn) => {
      try {
        const stun = str(sp, sn).split(" ").filter((u) => u);
        const pc = new RTCPeerConnection({ iceServers: stun.map((u) => ({ urls: u })) });
        const r = { pc, dc: null, q: [], sig: [], early: [], ready: false };
        const enc = new TextEncoder();
        const setup = (dc) => {
          r.dc = dc;
          dc.binaryType = "arraybuffer";
          dc.onopen = () => r.q.push("open");
          dc.onmessage = (e) => r.q.push(typeof e.data === "string" ? enc.encode(e.data) : new Uint8Array(e.data));
          dc.onclose = () => r.q.push("close");
        };
        pc.onicecandidate = (e) => { if (e.candidate) r.sig.push(JSON.stringify({ c: e.candidate })); };
        if (Number(init)) {
          setup(pc.createDataChannel("sloppy", { ordered: false, maxRetransmits: 0 }));
          pc.createOffer().then((o) => pc.setLocalDescription(o)).then(() => r.sig.push(JSON.stringify({ d: pc.localDescription })));
        } else pc.ondatachannel = (e) => setup(e.channel);
        rtcs.push(r);
        return BigInt(rtcs.length - 1);
      } catch (e) { return -1n; }
    },
    __wasm_rtc_signal_in: (id, p, n) => {
      const r = rtcs[Number(id)];
      if (!r) return;
      let m;
      try { m = JSON.parse(str(p, n)); } catch (e) { return; }
      const pc = r.pc;
      if (m.d) {
        pc.setRemoteDescription(m.d).then(() => {
          r.ready = true;
          for (const c of r.early) pc.addIceCandidate(c).catch(() => {});
          r.early = [];
          if (m.d.type === "offer")
            return pc.createAnswer().then((a) => pc.setLocalDescription(a)).then(() => r.sig.push(JSON.stringify({ d: pc.localDescription })));
        }).catch(() => r.q.push("close"));
      } else if (m.c) {
        if (r.ready) pc.addIceCandidate(m.c).catch(() => {});
        else r.early.push(m.c);
      }
    },
    __wasm_rtc_signal_out: (id, op, cap) => {
      const r = rtcs[Number(id)];
      if (!r || r.sig.length === 0) return -1n;
      const b = new TextEncoder().encode(r.sig[0]);
      if (b.length <= Number(cap)) r.sig.shift();
      return give(b, op, cap);
    },
    __wasm_rtc_send: (id, p, n) => {
      const r = rtcs[Number(id)];
      if (r && r.dc && r.dc.readyState === "open") { try { r.dc.send(u8().slice(Number(p), Number(p) + Number(n))); } catch (e) {} }
    },
    __wasm_rtc_poll: (id, op, cap) => {
      const r = rtcs[Number(id)];
      if (!r || r.q.length === 0) return -1n;
      const x = r.q[0];
      if (x === "open") { r.q.shift(); return -2n; }
      if (x === "close") return -3n;
      if (x.length > Number(cap)) return BigInt(x.length);
      r.q.shift();
      u8().set(x, Number(op));
      return BigInt(x.length);
    },
    __wasm_rtc_close: (id) => { const r = rtcs[Number(id)]; if (r) { try { r.pc.close(); } catch (e) {} rtcs[Number(id)] = null; } },
    // invite codes (lib/net.jo's invite and join_invite): a whole description once ICE has
    // gathered (no trickling: the code carries every candidate), and the data channel as above
    __wasm_rtc_invite: (reliable, sp, sn) => rtcNew(str(sp, sn), Number(reliable) ? {} : { ordered: false, maxRetransmits: 0 }, null),
    __wasm_rtc_join: (sp, sn, op, on) => rtcNew(str(sp, sn), null, str(op, on)),
    __wasm_rtc_local: (id, op, cap) => {
      const r = rtcs[Number(id)];
      if (!r || !r.local) return -1n;
      return give(new TextEncoder().encode(r.local), op, cap);
    },
    __wasm_rtc_answer: (id, p, n) => {
      const r = rtcs[Number(id)];
      if (r) r.pc.setRemoteDescription({ type: "answer", sdp: str(p, n) }).catch(() => r.q.push("close"));
    },
    __wasm_rtcp_send: (id, p, n) => env.__wasm_rtc_send(id, p, n),
    __wasm_rtcp_poll: (id, op, cap) => env.__wasm_rtc_poll(id, op, cap),
    __wasm_rtcp_close: (id) => env.__wasm_rtc_close(id),
    __wasm_save_get: (kp, kn, op, cap) => {
      const key = str(kp, kn);
      let d = null;
      try {
        if (nodeFs) d = new Uint8Array(nodeFs.readFileSync(saveFile(key)));
        else {
          const s = localStorage.getItem("sloppy:" + key);
          if (s !== null) d = Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
        }
      } catch (e) { d = null; }
      return d === null ? -1n : give(d, op, cap);
    },
    __wasm_args: (op, cap) => give(new TextEncoder().encode(args.join("\0")), op, cap),
  };
  // a peer connection for an invite code: offering (channel options given) or answering an offer;
  // r.local is its whole description once its candidates are gathered (or after 3 seconds)
  // (?DEWY_RTC_RELAY_ONLY=1, for trying the TURN path: only relayed candidates)
  const rtcRelayOnly = typeof location !== "undefined" && new URLSearchParams(location.search).get("DEWY_RTC_RELAY_ONLY") === "1";
  function rtcNew(stun, channel, offer) {
    try {
      // (one server a line; a TURN server's user and password after it, between tabs)
      const servers = stun.split("\n").filter((u) => u).map((u) => { const f = u.split("\t"); return f.length === 3 ? { urls: f[0], username: f[1], credential: f[2] } : { urls: f[0] }; });
      const pc = new RTCPeerConnection({ iceServers: servers, iceTransportPolicy: rtcRelayOnly ? "relay" : "all" });
      const r = { pc, dc: null, q: [], sig: [], early: [], ready: true, local: "" };
      const enc = new TextEncoder();
      const setup = (dc) => {
        r.dc = dc;
        dc.binaryType = "arraybuffer";
        dc.onopen = () => r.q.push("open");
        dc.onmessage = (e) => r.q.push(typeof e.data === "string" ? enc.encode(e.data) : new Uint8Array(e.data));
        dc.onclose = () => r.q.push("close");
      };
      pc.onconnectionstatechange = () => { if (pc.connectionState === "failed") r.q.push("close"); };
      const gathered = () => new Promise((done) => {
        if (pc.iceGatheringState === "complete") return done();
        pc.addEventListener("icegatheringstatechange", () => { if (pc.iceGatheringState === "complete") done(); });
        setTimeout(done, 3000);
      });
      let p;
      if (channel) {
        setup(pc.createDataChannel("sloppy", channel));
        p = pc.createOffer().then((o) => pc.setLocalDescription(o));
      } else {
        pc.ondatachannel = (e) => setup(e.channel);
        p = pc.setRemoteDescription({ type: "offer", sdp: offer }).then(() => pc.createAnswer()).then((a) => pc.setLocalDescription(a));
      }
      p.then(gathered).then(() => { r.local = pc.localDescription.sdp; }).catch(() => r.q.push("close"));
      rtcs.push(r);
      return BigInt(rtcs.length - 1);
    } catch (e) { return -1n; }
  }
  // (copy bytes to a buffer in wasm memory; the size there is the length needed)
  function give(b, op, cap) {
    u8().set(b.subarray(0, Math.min(b.length, Number(cap))), Number(op));
    return BigInt(b.length);
  }
  const files = {};
  let stdin = new Uint8Array(0);
  let lastBreak = typeof performance !== "undefined" ? performance.now() : 0;
  if (!isNode) setInterval(() => { lastBreak = performance.now(); }, 200);
  const nodeFs = isNode && typeof sloppyFs !== "undefined" ? sloppyFs : null;
  let args = isNode && typeof sloppyArgs !== "undefined" ? sloppyArgs : ["page"];
  function saveFile(key) {
    const dir = (typeof process !== "undefined" && process.env.DEWY_SAVE_DIR) || "/tmp/sloppy-save";
    return dir + "/" + key;
  }
  // (a node file system error as Linux's -errno)
  const ERRNO = { EPERM: 1, ENOENT: 2, EIO: 5, EACCES: 13, EBUSY: 16, EEXIST: 17, ENOTDIR: 20, EISDIR: 21,
                  EINVAL: 22, ENOSPC: 28, EROFS: 30, ENAMETOOLONG: 36, ENOTEMPTY: 39, ELOOP: 40 };
  const fsErrno = (e) => BigInt(-(ERRNO[e && e.code] ?? 5));
  // (a page's directories: made by the program, besides those its files are in)
  const pageDirs = new Set();
  // (what is at a page's path: 0 nothing, 1 a file, 2 a directory)
  function pageKind(path) {
    if (path in files) return 1;
    if (path === "" || path === "." || path === "/" || pageDirs.has(path)) return 2;
    for (const f of Object.keys(files)) if (f.startsWith(path + "/")) return 2;
    return 0;
  }
  function readFile(path) {
    if (nodeFs) { try { return new Uint8Array(nodeFs.readFileSync(path)); } catch (e) { return null; } }
    return files[path] ?? null;
  }
  const extra = [];   // modules (graphics, audio, input) register their imports here
  function run(bytes) {
    for (const f of extra) Object.assign(env, f.imports(() => mem, () => exports));
    const imports = { env: new Proxy(env, {
      get: (t, k) => k in t ? t[k] : (() => { throw new Error("missing import: " + String(k)); }) }) };
    // (a page compiles a big module off the main thread: Chrome refuses to do it on it above 8 MB,
    // as a big program with its files embedded is)
    if (!isNode && bytes.length > 4000000) {
      return WebAssembly.instantiate(bytes, imports).then((r) => { wmod = r.module; start(r.instance); });
    }
    wmod = new WebAssembly.Module(bytes);
    start(new WebAssembly.Instance(wmod, imports));
  }
  function start(inst) {
    // (the page's "loading…", shown while it came)
    if (!isNode) { const l = document.getElementById("sloppy-loading"); if (l) l.remove(); }
    exports = inst.exports;
    mem = exports.memory;
    try {
      exports.__start();
      for (const f of extra) if (f.start) f.start(exports);
    } catch (e) {
      if (e instanceof Exit) { flush(); if (isNode) process.exitCode = e.code; return; }
      flush();
      if (isNode) { console.error(e.stack || e); process.exitCode = 101; } else throw e;
    }
    flush();
  }
  function flush() { for (let fd = 1; fd <= 2; fd++) if (pending[fd - 1]) { out(fd, "\n"); } }
  // (for the program's own JavaScript, `js = "glue.js"` in its build block: sloppy.env.f = (p, n) =>
  // ... gives its `extern f = (p: *u8, n: int)`; sloppy.text(p, n) is the text there, ints come
  // as BigInt)
  return { run, extra, env, Exit, errorText, files, setArgs: (a) => { args = a; },
           text: (p, n) => str(p, n), bytes: (p, n) => u8().subarray(Number(p), Number(p) + Number(n)), memory: () => mem };
})();
