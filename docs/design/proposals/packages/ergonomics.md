# Packages: ergonomics

## Verdict

- Flat vendoring wins. The program keeps one copy of each library under `libs/`, imports it by path, and builds with no network and no tool.
- A three-command tool (`dewy add`, `dewy update`, `dewy audit`) is the 80% way to edit that tree. The compiler never fetches.
- Pins live in `libs.dewy` at the program root. Library identity lives in `lib.dewy`.
- His lean is right that the bytes which compile sit in the tree beside the program. It is wrong where a library carries its own copy of a dependency, and wrong where the pin is written into the library file it hashes.

## Designs

- **(1) Pure vendoring.** Copy a folder. `from p"libs/shapes/lib.dewy" import Circle`. No tool, no pin.
- **(2) Vendoring plus a tool.** `dewy add URL` copies into `libs/` and writes a provenance metatag into the library's `.dewy`. `dewy update`, `dewy audit`.
- **(3) Digest in source, bytes in a cache.** `$package(shapes url='…' ref='v1.2.0' digest='sha256:…')` then `import shapes`. First compile downloads.
- **(4) Flat tree, pins in `libs.dewy`.** Commands as (2). Libraries do not vendor dependencies. `dewy add` copies each `$needs` once, as a sibling. Update is a 3-way merge that stops on conflict. A second copy is an explicit second folder.

`@libs` is the one new spelling: `p"@libs/shapes/lib.dewy"` is `libs/` beside the main file, or the directory `$libs` names, same idea as `p"@lib/…"`.

## Scores

| Scenario | (1) | (2) | (3) | (4) |
|---|---|---|---|---|
| First dependency | rough | pass | pass if online | pass |
| Update one library | rough | pass if it merges | fail the review | pass |
| Security fix, transitive | fail if nested | pass if flattened | fail | pass |
| Two versions, pass a value | fail | fail if nested | fail if duplicated | pass; two copies are a type error |
| Keep a local patch | pass with care | fail if it overwrites | rough | pass |
| Publish | pass | pass | pass while the URL lives | pass |
| Review an update | pass | pass | fail | pass |
| Find a library | fail | fail | fail | fail |
| Offline, 100 years | pass | pass | fail | pass |
| Huge dependency | rough | pass if source only | fail the promise | pass |

## Scenarios

### First dependency in a one-file script

- **(1)** The script grows a directory, and nothing records the origin.

```sh
mkdir -p libs
git clone --depth 1 --branch v1.2.0 https://github.com/someone/shapes.git libs/shapes
rm -rf libs/shapes/.git
```

```dewy
$dewy.version = '0.1.0'
from p"libs/shapes/lib.dewy" import Circle
main = () => { printl(Circle[radius=2]) }
```

- **(2) and (4)** One command, then the import. (2) also rewrites `libs/shapes/lib.dewy`, so the tree no longer matches upstream.

```sh
dewy add https://github.com/someone/shapes version=v1.2.0
```

```dewy
$dewy.version = '0.1.0'
from p"@libs/shapes/lib.dewy" import Circle
main = () => { printl(Circle[radius=2]) }
```

- **(3)** A person cannot type a digest. The tool still writes the line; compile then needs the network.

```dewy
$dewy.version = '0.1.0'
$package(shapes url='https://github.com/someone/shapes' ref='v1.2.0' digest='sha256:9f2c4e1a')
import shapes
main = () => { printl(shapes.Circle[radius=2]) }
```

```sh
dewy main.dewy
```

### Update one library

```sh
dewy update shapes version=v1.3.0
```

- **(1)** Re-cloning drops a local edit. A hand merge works and is too many steps for the common case.
- **(2) and (4)** fetch the tag, merge, rewrite the pin. (4) merges against the stored base and, on conflict, leaves markers with the old digest untouched.
- **(3)** rewrites `ref` and `digest`. That line's diff does not show the library.

### Security fix in a dependency of a dependency

`shapes` needs `json` v1.4.0. `json` v1.4.3 is the fix. The application never imports `json`.

- **(4)** `dewy add` already copied `libs/json` once, because `shapes` says:

```dewy
$needs(name='json' url='https://github.com/someone/json' version='v1.4.0')
from p"@libs/json/lib.dewy" import parse
```

```sh
dewy update json version=v1.4.3
dewy audit
git diff -- libs/json libs.dewy
```

- Audit prints `shapes wants json v1.4.0, pin is v1.4.3`. The typechecker is the compatibility test. One edit fixes every user of `json`.
- **(1)** when each library holds its own copy:

```sh
rm -rf libs/shapes/libs/json
git clone --depth 1 --branch v1.4.3 https://github.com/someone/json.git libs/shapes/libs/json
```

- `libs/physics/libs/json` still has the hole, and nothing lists the copies. Nested vendoring fails here.
- **(2)** passes when `dewy add` flattened. A tag inside `json` does not reveal a second copy.
- **(3)** the vulnerable pin is a line inside `shapes`. An override metatag is a second mechanism for a common case.

### Two libraries, two versions, pass a value

`ui` needs `geom` v1. `physics` needs `geom` v2. Named records are distinct types, so two copies of `Point` are two types however similar the fields are.

- **(4)** the common path is one copy. `dewy add` of the second library stops:

```text
ui needs geom v1.0.0, physics needs geom v2.0.0; libs/geom not written
```

- Pick one, compile, fix the call sites:

```sh
dewy add https://github.com/someone/geom version=v2.0.0
```

```dewy
from p"@libs/ui/lib.dewy" import corner
from p"@libs/physics/lib.dewy" import place
place(corner)
```

- That passes when both files import `p"@libs/geom/lib.dewy"`. The adjustment, when v1 and v2 must both exist:

```sh
dewy add https://github.com/someone/geom version=v1.0.0 name=geom1
dewy add https://github.com/someone/geom version=v2.0.0 name=geom2
```

- Point the vendored imports at those paths (local patches), then:

```dewy
from p"@libs/geom1/lib.dewy" import Point as Point1
from p"@libs/geom2/lib.dewy" import Point as Point2
let a:Point1 = corner
place(a)   # error: Point1 is not Point2
```

- The way across is an adapter in the program.
- **(1) (2) (3)** can store both copies quietly. The call fails later, and the security fix has two trees. A solver hides which `Point` you hold.

### Patch, and keep it

Edit `libs/shapes/curve.dewy`. Commit it.

```sh
dewy update shapes version=v1.3.0
```

- **(4)** fetches the base and v1.3.0, merges onto the edit, updates `libs.dewy`. On conflict the markers stay and the digest stays on the old pin. After resolving, `dewy audit accept=shapes` stores `digest` of the local tree and `base` of the upstream.
- **(1)** is that merge, typed by hand, with the origin URL from memory.
- **(2)** a tool that copies a fresh tree over `libs/shapes` deletes the patch. That tool is worse than none.
- **(3)** `path='../shapes'` leaves the pin. The next update has to merge anyway.

### Publish

- Tag the library repo and push it. No registry account.

```sh
git tag v1.2.0
git push origin v1.2.0
```

- Repo root is `lib.dewy` plus the other sources, no nested `libs/`. `$lib.version` equals the tag.
- **(3)** publishes the same way. The program builds while that URL still serves the digest.

### Review what changed

```sh
dewy update shapes version=v1.3.0
git diff -- libs/shapes libs.dewy
```

- **(1) and (4)** the review is that diff.
- **(2)** adds noise when the tool rewrote a header in every library file.
- **(3)** `git diff` shows one new hash.

### Find a library

- A page of URLs is the finding step; `dewy add` takes the one you copied. A global short name is a namespace to police. The folder name stays local to the program.

### No network, 100 years later

```sh
dewy main.dewy
```

- **(1) (2) (4)** compile from the tree. The tool is absent. `$dewy.version` on each module is already how mixed language versions interoperate.
- **(3)** the host is gone and the cache is not in the repository. The digest names bytes you do not have.
- A submodule fails too: a fresh clone lacks the bytes until a network fetch.

### A huge dependency

- **(4)** `dewy add` copies `.dewy` sources and `$include_bytes` files, and skips `.git`, tests, and examples. `lib.dewy` imports nothing, so one used module does not compile the rest.
- **(1)** `git clone` brings history and tests. Compile time holds if those files stay unimported.
- **(3)** keeps the clone small and drops the offline build. A large library means a large tree. That is the cost of the promise.

## Where his lean is best and worst

- **Best** is the offline build, the review (`git diff libs/shapes`), and a patch that is an ordinary edit once update merges.
- **Worst** is a library that vendors its own dependencies. The `json` hole and the `Point` mismatch are one mistake: two copies.
- **Worst** for the first dependency is no tool. Clone, delete `.git`, remember the URL. Keep the compiler free of the tool anyway.
- **The pin inside the library file is the wrong spot.** Audit cannot hash a file that contains its own hash, and update conflicts on a header the author did not write. `libs.dewy` is the one consumer file the tool rewrites.
- MIT and Apache require their text to travel with the copy. The tool writes that text into `license.dewy` as a string. A SPDX tag alone does not meet the license.

## Metatags

Smallest set on the library entry file:

- `$dewy.version` — already required on every module, including this one.
- `$lib.name` — folder name and audit name.
- `$lib.version` — the git tag.
- `$lib.license` — SPDX key, beside the pasted license text.
- `$needs(name url version)` — zero or more. Exact tag, no range. The URL is how `dewy add` fetches a library the program never named. A dead URL matters for a later update, not for a build.

No digest on `lib.dewy`. The consumer pin, in `libs.dewy`:

```dewy
$dewy.version = '0.1.0'
$vendor(
    name='shapes'
    url='https://github.com/someone/shapes'
    version='v1.2.0'
    digest='sha256:9f2c4e1a'
    path='libs/shapes'
)
```

After a local patch, the same call gains `base='sha256:9f2c4e1a'` and `digest` becomes the local tree. Digest covers the copied files, sorted by relative path, excluding `libs.dewy`.

```dewy
$dewy.version = '0.1.0'
$lib.name = 'shapes'
$lib.version = 'v1.2.0'
$lib.license = 'MIT'
$needs(name='geom' url='https://github.com/someone/geom' version='v2.0.0')

from p"@libs/geom/lib.dewy" import Point

Circle:type = [center:Point radius:float]
area = (c:Circle) => 3.141592653589793 * c.radius * c.radius
```

## Recommendation

- Ship (4). Default to one sibling copy, path imports through `@libs`, pins in `libs.dewy`, and a tool whose update merges and whose absence does not matter at compile time. Version ranges and a registry are the part to leave out: the diff plus the typechecker is the compatibility test, and a second copy is a second path with an adapter at the boundary.

Least sure: `@libs` versus banning subfolders so every dependency import is `p"../name/lib.dewy"`. The new root is worth it as soon as a library has two directories; if libraries stay flat, the spelling is unnecessary.
