# Markdown Book Source for Documentation
This contains the source markdown files used to compile the language documentation hosted at https://david-andrew.github.io/dewy-lang/

## To Build
The docs are automatically built using github actions any time modifications to the `docs/` folder are detected. A new deployment of the docs site is performed if the resulting build folder is different from the previous build.

If you wish to manually build the docs:
1. Ensure you have the mdbook CLI installed (https://github.com/rust-lang/mdBook)
2. Run `mdbook build` from the `docs/` directory
    - This will generate the static site in the `docs/book/` directory