// WebAudio output for the Sloppy mixer: audio is pulled from wasm a little ahead of time and played
// by an AudioWorklet (on the audio thread, so a busy page does not interrupt it), or where that
// is unavailable, by a buffer source node per chunk.
dewy.extra.push({
  imports(getMem, getExports) {
    let ctx = null, node = null, loading = false, next = 0, rate = 48000;
    const worklet = `registerProcessor("dewy-out", class extends AudioWorkletProcessor {
      constructor() { super(); this.q = []; this.at = 0; this.port.onmessage = (e) => this.q.push(e.data); }
      process(_, outs) {
        const l = outs[0][0], r = outs[0][1] || outs[0][0];
        for (let i = 0; i < l.length; i++) {
          const b = this.q[0];
          if (!b) { l[i] = r[i] = 0; continue; }
          l[i] = b[this.at]; r[i] = b[this.at + 1];
          this.at += 2;
          if (this.at >= b.length) { this.q.shift(); this.at = 0; }
        }
        return true;
      }
    });`;
    function pump() {
      if (!ctx || ctx.state !== "running" || loading) return;
      const ex = getExports();
      const ahead = 0.09;
      if (next < ctx.currentTime) next = ctx.currentTime + 0.02;
      while (next < ctx.currentTime + ahead) {
        const n = 1024;
        const p = Number(ex.__audio_fill(n));
        const f = new Float32Array(getMem().buffer, p, n * 2);
        if (node) {
          const c = f.slice();
          node.port.postMessage(c, [c.buffer]);
        } else {
          const buf = ctx.createBuffer(2, n, rate);
          const l = buf.getChannelData(0), r = buf.getChannelData(1);
          for (let i = 0; i < n; i++) { l[i] = f[2 * i]; r[i] = f[2 * i + 1]; }
          const src = ctx.createBufferSource();
          src.buffer = buf;
          src.connect(ctx.destination);
          src.start(next);
        }
        next += n / rate;
      }
    }
    let hidden = false;
    dewy.resumeAudio = () => { if (ctx && !hidden && ctx.state !== "running") ctx.resume(); };
    // (the page hidden: the game gets no frames, so its sound stops; back as it is shown, if it
    // was running)
    let wasRunning = false;
    dewy.pauseAudio = (on) => {
      hidden = on;
      if (!ctx) return;
      if (on) { wasRunning = ctx.state === "running"; if (wasRunning) ctx.suspend(); }
      else if (wasRunning) ctx.resume();
    };
    dewy.pumpAudio = pump;
    return {
      __web_audio_start(r) {
        rate = r;
        try { ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: r }); } catch (e) { ctx = null; }
        if (ctx && ctx.audioWorklet) {
          loading = true;
          // (a data: URL: pages opened from disk may not load blob: or file: modules)
          const url = "data:text/javascript;charset=utf-8," + encodeURIComponent(worklet);
          ctx.audioWorklet.addModule(url).then(() => {
            node = new AudioWorkletNode(ctx, "dewy-out", { outputChannelCount: [2] });
            node.connect(ctx.destination);
          }).catch(() => {}).finally(() => { loading = false; });
        }
        if (ctx) setInterval(pump, 20);       // (no audio here: nothing to feed)
      },
    };
  },
});
