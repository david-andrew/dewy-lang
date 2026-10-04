# wasm32 harness

The page and host functions every wasm32 module runs in. µDewy's two
compilers fill these templates — `udewy/backend/wasm.py` reads them and
`udewy/bootstrap/backend/wasm.udewy` embeds them with `$include_bytes` — so a
module from either, or from the Dewy compiler's own wasm32 emitter (which
hands its module to `udewy`), gets the same page.

- `host.js`: the `env` imports and the local server's lifecycle hooks.
- `embedded.html`: one file with the module in base64.
- `split.html`: the page for a module served beside it (`--split-wasm`).

Placeholders, each replaced wherever it appears:

| placeholder | value |
|---|---|
| `@@MEMORY_PAGES@@` | the module's imported memory minimum, in 64 KiB pages |
| `@@HOST_JS@@` | `host.js`, then each linked `.js` artifact on a new line |
| `@@TITLE@@` | the module's name |
| `@@WASM_B64@@` | the module in base64 |
| `@@WASM_FILE@@` | the module's file name |
| `@@LINKED_WASM@@` | a `<script data-wasm-artifact>` block per linked `.wasm`, one per line |
