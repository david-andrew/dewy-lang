# Dewy language website

The complete language website lives under `site/` and builds into the ignored
`site/dist/` directory.

## Local prerequisites

- Python 3.12 or newer
- [mdBook](https://rust-lang.github.io/mdBook/)
- [WABT](https://github.com/WebAssembly/wabt), providing `wat2wasm`

Build and serve the site from the repository root:

```sh
python site/scripts/build.py
python -m http.server --directory site/dist 8000
```

Then open <http://localhost:8000/>.

## Source layout

- `static/` contains the landing page and top-level information pages.
- `learn/` is the narrative guide built with mdBook.
- `reference/` is the concise language reference built with mdBook.
- `playground/` documents the generated µDewy browser playground.
- `scripts/` contains the single build entry point and output checks.

The GitHub Pages workflow runs the same build command. Do not edit `dist/`
directly.
