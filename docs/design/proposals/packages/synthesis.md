# Packages: synthesis

**BLUF:** your vendoring lean holds up. Use one flat `libs/` beside the program, ordinary path imports, and a small optional tool. The compiler never fetches, and there's no lockfile, registry or version solver.

Inputs: [literature.md](literature.md), [ergonomics.md](ergonomics.md), [hard-problems.md](hard-problems.md).

## The design

```dewy
# main.dewy
$dewy.version = '0.1.0'
from p"libs/shapes/lib.dewy" import Circle
main = () => printl(Circle[radius=2])
```

```dewy
# libs/shapes/lib.dewy: the author writes all of this; the tool never edits it
$dewy.version = '0.1.0'
$lib.name = 'shapes'
$lib.version = '1.2.0'
$lib.license = 'MIT'
$needs(name='geom' url='https://github.com/someone/geom' min='2.0.0')
from p"@root/libs/geom/lib.dewy" import Point

Circle:type = [center:Point radius:float]
```

```dewy
# libs.dewy, at the program root: the tool writes this, one entry per library
$dewy.version = '0.1.0'
$vendor(name='shapes' url='https://github.com/someone/shapes' commit='9f2c…' digest='sha256:…')
$vendor(name='geom' url='https://github.com/someone/geom' commit='41ab…' digest='sha256:…')
```

## Common path

| Task | What you do |
|---|---|
| Add a library | `dewy add https://github.com/someone/shapes`; it copies source and its `$needs` into `libs/`, then you import by path |
| Update one | `dewy update shapes`, then review `git diff -- libs/shapes` |
| Security fix in a deep dependency | `dewy update geom`; there's one copy, so one edit fixes every user |
| Build offline, 100 years on | Nothing: the bytes are in your tree, and `$dewy.version` selects the semantics |
| Publish | Tag and push a repo; no account or registry |

## When that doesn't fit

| Need | What you do |
|---|---|
| No tool | Copy a folder by hand; the compiler only needs the files |
| Patch a library | Edit the file and commit; `dewy update` does a 3-way merge and stops on conflict |
| Two versions at once | Two folders (`libs/geom1`, `libs/geom2`), with an adapter where values cross |
| Huge library | Only imported files get compiled, because loading is lazy; the repo size is the real cost |
| Check integrity | `dewy audit`, in CI or before release, not on every build |

## What the reviews settled

- **Flat, not nested.** One design round preferred nested copies, because moving a library keeps its imports working. Flat wins on evidence:
  - Go banned nested vendor folders so each import path has one meaning.
  - With nested copies, a security fix must be found and applied in every copy. In Log4Shell, over 80% of affected Maven packages were more than one level deep.
  - Nested copies also make `a`'s `Point` a different type from `b`'s `Point`, even for the same library.
- **One path means one module.** A type's identity is its declaring module and declaration, as Dewy already does it.
  - Rejected, content identity: identical entry files can import different code.
  - Rejected, structural equality: two same-shaped handles can have different destructors.
  - Rejected, declared compatibility: a claim can't prove a layout safe.
  - The error must name both paths; today it can say `expected Point, found Point`.
- **Pins live in `libs.dewy`, not in the library's file.** You imagined metadata in `lib.dewy`, and the author's metadata stays there. The consumer's pin moves out because:
  - vendored files stay byte-identical to upstream, so diffs and audits stay clean;
  - a file can't contain its own hash without special cases;
  - updates don't conflict on a header the author never wrote;
  - one file answers "what do I depend on?".

  It's still a `.dewy` file, so your no-other-formats rule holds.
- **Digests aren't checked on every build.** Hashing a 2-million-line unused dependency would break the compile-speed target for a ten-line program, and hashing only loaded files can't verify the tree. The cost per build is zero; `dewy audit` does the checking.
- **Version choice: the highest requested minimum.** No solver. Across a major version, `dewy add` stops and asks instead of guessing. The typechecker and the diff are the compatibility test.
- **The tool is an ordinary Dewy program.** The compiler only gains the path root. Its current package-cache fallback goes away, so a missing file is always a local error.

## Known weak spots

- **Noticing updates is vendoring's real weakness.** In one large study, only 10% of vendored copies recorded their origin, and CVE-carrying copies had a confirmed fix less often than upstream-synced ones (44% vs 71%, with wide bounds). That study mostly covers unmanaged copies, so it doesn't measure a design like this one. `libs.dewy` closes the origin gap, and `dewy audit` can check advisories. Nothing shows metadata alone closes the gap.
- **Repo size grows,** and git keeps every old version.
- **Compile-time code in a vendored library runs when you compile.** Compile-time evaluation must not get network or file-write access, and the tool should flag build-time code.
- **Foreign C libraries and system SDKs** stay outside the 100-year promise.
- **Finding libraries** needs an index eventually, with no authority over names. Not needed yet.
- **Evidence is thin overall.** Most pain reports are anecdotal, no long-term study compares vendoring with package managers, and no large ecosystem uses first-class vendoring. Odin is closest, and it's small.

## The two things that remain David's

1. **How a library names its dependency.** The one hard problem no surveyed ecosystem solves with plain paths. The path must work in the library's own repo and under a program's `libs/`.
   - `p"@root/libs/geom/lib.dewy"`, where `@root` is the main file's folder. It follows the existing `p"@lib/…"`. **Rec.**
   - `p"@libs/geom/lib.dewy"`: shorter, but one letter from `@lib`, which is Dewy's own library.
   - `p"../geom/lib.dewy"`: no new spelling, but it forces every library to be flat, and in its own repo the dependency sits outside the repo.
2. **The metatag names:** `$lib.name`, `$lib.version`, `$lib.license`, `$needs(…)`, `$vendor(…)`.
