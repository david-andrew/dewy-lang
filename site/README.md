# Dewy language website

The complete language website lives under `site/` and builds into the ignored
`site/dist/` directory.

## Local prerequisites

- Python 3.14 or newer
- Node.js 20 or newer
- [mdBook](https://rust-lang.github.io/mdBook/)
- [WABT](https://github.com/WebAssembly/wabt), providing `wat2wasm`

Install the build-time syntax highlighter once after cloning or updating the
site dependencies:

```sh
npm ci --prefix site
```

Build and serve the site from the repository root:

```sh
python site/scripts/watch.py
```

That rebuilds into `site/dist/` when sources change and serves <http://localhost:8080/>.
Open pages from that server reload after a successful rebuild.

A one-shot build is still:

```sh
python site/scripts/build.py
python -m http.server --directory site/dist 8000
```

## Source layout

- `static/` contains the landing page, the µDewy home and showcase chrome, and top-level information pages.
- `learn/` is the narrative guide built with mdBook.
- `reference/` is the concise Dewy language reference built with mdBook.
- `DOCUMENTATION_GUIDE.md` defines the voice, scope, and design-versus-implementation policy shared by both books.
- `DOCUMENTATION_PROJECTS.md` preserves future domain quick starts, case studies, and library explorations until they are substantial enough to publish.
- `udewy/reference/` is the µDewy spec book. Its `src/` is generated from `udewy/README.md` at build time.
- The showcase compiles selected µDewy wasm demos into `dist/udewy/showcase/demos/`.
- `playground/` documents the generated µDewy browser playground.
- `scripts/` contains the build, a file watcher, local-link validation, and published Dewy-example checks.
- The repo-root `install.sh` is copied to the site root; `udewy/install.sh` is copied to `/udewy/install.sh`.
- Dewy code blocks are prerendered from the VS Code extension's TextMate grammar during the site build; the browser does not run a Dewy highlighter.
- µDewy code blocks are prerendered from the tokenizer highlighter during the site build.

The GitHub Pages workflow runs the same build command. Do not edit `dist/`
directly.

Published `dewy` code fences are parser-checked by default. Self-contained examples can opt into semantic checking with `<!-- dewy-example: compiler -->`, while syntax that is explicitly part of a provisional design uses `<!-- dewy-example: design-only -->`. See `DOCUMENTATION_GUIDE.md` for the complete policy.
