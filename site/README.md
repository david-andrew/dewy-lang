# Dewy website

The site uses the current compiler only. Python 3.11+, Node 20+, mdBook 0.4.52,
a C compiler and make are needed for a clean checkout build. A pinned standalone
compiler avoids the C bootstrap. No old Python language packages or WABT are used.

```sh
npm ci --prefix site
python3 site/scripts/build.py
python3 -m http.server --directory site/dist 9000
```

Put `mdbook` on PATH. To pin an already-built matching toolchain:

```sh
python3 site/scripts/build.py --compiler /path/to/toolchain/bin/dewy-core
```

`python3 site/scripts/watch.py [port]` serves on port 9000 by default and reruns
the same complete build after source changes. Only successful builds notify
browser clients. Build output lives in ignored `site/dist/`; do not commit it.

## Sources and claims

- `static/`: public pages, shared assets and the retired µDewy installer message.
- `learn/`: current compiler walkthroughs. `reference/`: normative language design.
- `coverage-map.json`: reference section associations with ladder programs,
  golden cases and pytest node IDs. An association does not certify a chapter.
- `playground/examples.json`: bounded, precompiled wasm programs and check/run intent.
- `routes.json`: preserved anchors and retired routes, inventoried from both
  original books/static pages, tracked reference output and the archived µDewy
  specification/showcase catalog. It is routing metadata, not coverage evidence.
- `scripts/`: build, snippet validation, coverage rendering, highlighting, links
  and the watcher. The grammar comes from `editors/vscode/syntaxes/`.

Every published Dewy fence must have explicit metadata, including static HTML:

````markdown
<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
printl(42)
```
````

Modes: `check`, `run` (exact `stdout`, optional `exit`/`args`), `reject`
(required `diagnostic` substring), `design-only`. Static code uses a JSON
`data-example` attribute on `code.language-dewy`. `fixtures` supplies named
companion-file contents; `prefix`/`suffix` supply a declared context for a snippet.
The checker writes complete temporary files and reports page/line plus compiler
diagnostics. Reference snippets explicitly illustrate design, not implementation.

`coverage/index.json` and `coverage/ladder.json` are generated fresh with revision,
compiler identity, host and target. Ladder and selected golden checks run native
release builds. Related pytest IDs are labelled **not measured** by this build.
Precompiled wasm run entries separately execute under Node and compare stdout; the game entry is check/build only; this does
not certify browser input/graphics or other hosts. The playground runs generated
pages in opaque-origin sandboxes with network denied, output limits, Stop buttons
and a 15-second lifetime. It does not compile user edits.

## Installers and deployment

The build copies root `install.sh`/`install.ps1` when present. A missing installer
prints a warning. If `tools/compiler/channel.py` exists and `DEWY_CHANNEL_TAG` is
set, the build invokes it with `--tag TAG --output site/dist/toolchain-channel.txt`.
Otherwise it warns and publishes no channel file. Release publication must supply
a complete, validated toolchain tag before enabling installation via the channel.

The workflow validates pull requests and uploads a preview artifact. Only master
can deploy Pages, including manual dispatches. `channel_tag` or the repository
`DEWY_CHANNEL_TAG` variable supplies the channel tag. No generated output is a
source of truth for future builds; every build checks snippets and ladder anew.

Retired HTML routes have canonical/meta-refresh/visible links and preserve
fragments with JavaScript. `/udewy/install.sh` exits with a retirement message
before touching the filesystem. `check_links.py` verifies local fragments,
redirect destinations and cycles; external archives remain external links.
