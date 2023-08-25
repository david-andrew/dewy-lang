# Markdown Book Source for Documentation
This contains the source markdown files used to compile the language documentation hosted at https://david-andrew.github.io/DewySpeak/

## To Build
The docs are automatically built and deployed using github actions any time modifications to the `docs/` folder are detected.

If you wish to manually build the docs:
1. Ensure you have the mdbook CLI installed (https://github.com/rust-lang/mdBook)
2. Run `mdbook build` from the `docs/` directory