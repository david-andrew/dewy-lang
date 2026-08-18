# Learning Dewy

This directory contains the narrative, example-oriented Dewy guide published
under `/learn/` on the language website.

## Build the complete site

From the repository root:

```sh
python site/scripts/build.py
```

The generated website is written to `site/dist/`.

### Local Development

When working only on the guide, mdBook can still provide live reload:

```sh
cd site/learn
mdbook serve
```

Some older chapters describe the intended language rather than the current
compiler. New material should explicitly distinguish implemented behavior from
design direction.
