// start the program once all runtime modules are registered
if (typeof SLOPPY_WASM !== "undefined") {
  const bin = typeof atob === "function" ? Uint8Array.from(atob(SLOPPY_WASM), c => c.charCodeAt(0)) : Buffer.from(SLOPPY_WASM, "base64");
  if (typeof window !== "undefined") {
    const fail = (e) => { const l = document.getElementById("log"); l.style.display = "block"; l.textContent += "error: " + sloppy.errorText(e) + "\n"; };
    window.addEventListener("error", (ev) => fail(ev.error || ev.message));
    window.addEventListener("load", () => { try { const r = sloppy.run(bin); if (r && r.catch) r.catch(fail); } catch (e) { fail(e); } });
  } else sloppy.run(bin);
}
