# Markdown Book Source for Documentation
This contains the source markdown files used to compile the language documentation hosted at https://david-andrew.github.io/dewy-lang/

## To Build
The docs are automatically built using github actions any time modifications to the `docs/` folder are detected. A new deployment of the docs site is performed if the resulting build folder is different from the previous build.

### Local Development

When adding to the docs, it can be useful to build and view them locally. Once you have the mdbook CLI installed (https://github.com/rust-lang/mdBook):
```
cd docs
mdbook serve
```
- This will build the docs and serve them at http://localhost:3000
- Changes are hot-reloaded in the browser
- Especially useful is how mdbook will create new pages if you make a link to them in `SUMMARY.md`