# Packages literature review: vendoring versus package managers

**BLUF**

- Vendoring solves availability, 100-year builds and "the bytes I reviewed are the bytes I built". The evidence for this is strong.
- Vendoring fails on update visibility. Only [10% of vendored copies record their origin, and 44% of CVE-carrying copies have a confirmed fix versus 71% for upstream-sync copies](https://arxiv.org/pdf/2607.02059). Provenance recorded by a tool is the main fix.
- Nested copies are the design error to avoid. Go banned them, and flat layouts avoid the diamond problem.
- A vendored tree can be its own lockfile, so no `.lock` file is needed.

## Ecosystems

**Go: the closest working model of a vendor directory that stays in sync with its metadata.**

- **Does:** import paths name modules, and MVS picks the highest requested minimum. [`vendor/modules.txt` is checked against `go.mod`, and only the top-level `vendor/` counts](https://go.dev/ref/mod), so that [each import path has one meaning](https://go.googlesource.com/proposal/+/master/design/24301-versioned-go.md).
- **Praise:** [no surprise upgrades](https://sourcegraph.com/blog/the-pain-that-minimal-version-selection-solves) and a [transparent checksum log](https://golang.org/design/25530-sumdb).
- **Complaints:**
  - [`/v2` path failures](https://gitlab.com/gitlab-org/api/client-go/-/issues/2239).
  - Vendor [diff noise](https://gitlab.com/gitlab-org/gitlab/-/work_items/17123), though another user says [vendor diffs make audits easier](https://github.com/golang/go/issues/33848).
  - A [typosquatted backdoor stayed in the mirror for about three years while its GitHub tag looked clean](https://www.infoworld.com/article/3817921/malicious-package-found-in-the-go-ecosystem.html).
- **Counterpoint:** Cox calls vendor directories ["almost entirely redundant" and says they "bloat the repositories"](https://research.swtch.com/vgo-module).
- **Verdict: helps.** Copy the flat layout and the consistency check.

**Zig: shows that digests in source work without a lockfile.**

- **Does:** the [hash is the "source of truth" and the URL is "one of many possible mirrors"; the hash covers only the files in `paths`](https://raw.githubusercontent.com/ziglang/zig/master/doc/build.zig.zon.md). Packages now land in a [local `zig-pkg/`, recommended to be gitignored but usable for self-contained archival tarballs](https://ziglang.org/devlog/2026/).
- **Praise:** a language-design author calls it ["extremely neat, even if rough at the edges"](https://matklad.github.io/2024/12/24/minimal-version-selection-revisited.html).
- **Complaints:** the [`zig fetch --save` overwrite problems](https://ziggit.dev/t/question-about-updating-dependencies-via-zig-fetch-save/15607) are one forum thread. Evidence is thin.
- **Verdict: helps.** Hashing file contents avoided the kind of [GitHub archive checksum change that broke builds in 2023](https://blog.bazel.build/2023/02/15/github-archive-checksum.html).

**Odin: the purest vendoring stance, with thin outcome data.**

- **Does:** ["will never officially support a package manager"; "copying and vendoring each package manually"](https://odin-lang.org/docs/faq/). Bill's objection is to ["the automation of dependency hell"](https://www.gingerbill.org/article/2025/09/08/package-managers-are-evil/), not to packages. A curated `vendor:` collection ships with the compiler.
- **Praise:** manual work forces you to think about each dependency.
- **Complaints:** users predict [fragmentation and CVE-tracking costs](https://forum.odin-lang.org/t/how-does-odin-plan-to-avoid-repeating-c-pythons-dependency-management-fiasco/591). A community [vendoring tool with a lockfile](https://forum.odin-lang.org/t/odyn-reproducible-vendoring-tool-for-odin-v0-1-0/1702) appeared anyway, which suggests people want the mechanical steps automated.
- **Verdict: helps on philosophy, unproven at scale.** I found no Odin project reporting on transitive or diamond handling.

**Jai: no usable evidence.**

- The compiler is in [closed beta](https://en.wikipedia.org/wiki/Jai_(programming_language)). Community setups use [local module folders and `-import_dir`](https://github.com/patrickgh3/jai-getting-started).
- **I found no primary Blow statement against package managers.** A [talk title on dependency hell](https://www.youtube.com/watch?v=ccV9aae8DIc) had no readable content. Treat "Jai's position" as hearsay.
- One useful warning: a community author notes that [a git-fetching metaprogram means "you can get owned simply by compiling the code"](https://github.com/onelivesleft/Metaprogram). This applies to comptime in vendored Dewy libraries too.

**C/C++: vendoring is already the majority practice, and it is painful.**

- **Does:** in the [2024 ISO survey, 68.5% have library source as part of their build; 19% use Conan and 19% vcpkg; 45.4% call managing libraries a major pain](https://isocpp.org/files/papers/CppDevSurvey-2024-summary.pdf), slightly above build times.
- **Praise:** stb's ["very easy to just drop them into a project"](https://raw.githubusercontent.com/nothings/stb/master/README.md), with a license in every source file.
- **Complaints:**
  - Stale copies: [a zlib CVE sat unpatched in PointCloudLibrary for nearly nine years](https://arxiv.org/pdf/2607.02059), and a [FOSDEM talk on Nix](https://thenewstack.io/vendoring-why-you-still-have-overlooked-security-holes/) reportedly counted 237 libpng copies in nixpkgs (from a search excerpt; I couldn't open the article body).
  - [stb_image CVE-2023-45661 is still listed unfixed by Debian](https://security-tracker.debian.org/tracker/CVE-2023-45661).
  - For the managers, [long source builds and CI drift](https://pkglog-com.pages.dev/en/blog/cpp-series-17-2-package-managers-en/) (weak source).
- **Best practice:** Chromium's [`README.chromium`](https://chromium.googlesource.com/chromium/src/+/main/third_party/README.chromium.template) requires license and security fields, [enforced at presubmit](https://chromium.googlesource.com/chromium/src/+/ae613976fedd97ce180da4b58725aada7a19be92/third_party/PRESUBMIT.py).
- **Verdict: mixed.** It shows both the failure mode and the fix.

**Deno: decentralized URLs failed for reasons vendoring only partly shares.**

- **Does:** moved from URL imports to import maps and JSR.
- **Complaints:** [Deno's own list](https://deno.com/blog/http-imports): exact URLs produce "several variants of the same library"; availability depends on "the least reliable host"; "import maps don't solve the semantic versioning problem". Import maps are also [not composable](https://questions.deno.com/m/1239219812031533076). A critic says the move [makes Deno more like npm](https://blog.jim-nielsen.com/2024/deno-de-emphasizes-http-imports/).
- **Verdict: both.** Local copies remove the host problem. Variant sprawl remains unless versions are unified.

**Rust: the best tooling, and honest about type identity.**

- **Does:** Cargo unifies compatible versions and allows incompatible ones to coexist. [Their types differ, and this can appear as a compile error or a runtime downcast failure. `links` forces one copy of a native library](https://doc.rust-lang.org/cargo/reference/resolver.html).
- **Praise:** Firefox vendors [about 400 crates and CI rejects unaudited ones via cargo-vet](https://groups.google.com/a/mozilla.org/g/dev-platform/c/j6cKDRP7jWY).
- **Complaints:**
  - [About 1 in 31 releases of top crates violated semver](https://predr.ag/blog/semver-violations-are-common-better-tooling-is-the-answer/).
  - [Different git revisions become different crates, with type errors](https://upd.dev/longbridge/gpui-component/issues/2532).
  - [`cargo vendor` can fail on duplicate sources](https://github.com/rust-lang/cargo/issues/10310).
  - [Dependency-count creep](https://users.rust-lang.org/t/request-derank-crates-io-results-by-number-of-dependencies-including-transitives/139153).
- **Verdict: helps.** Vendoring plus retained metadata keeps audits working. Semver is a claim that needs checking.

**npm: the case against automatic, deep trust.**

- **Incidents:**
  - [left-pad: 273 packages unpublished, 2.5 hours of disruption](https://blog.npmjs.org/post/141577284765/kik-left-pad-and-npm).
  - [event-stream: a new maintainer, with an encrypted payload in a "test fixture"](https://blog.npmjs.org/post/180565383195/details-about-the-event-stream-incident).
  - [Shai-Hulud: a self-republishing worm, around 200 packages in a day](https://javapro.io/2025/10/02/the-shai-hulud-npm-worm-when-supply-chains-bite-back/).
  - [A few maintainer accounts reach most packages](https://arxiv.org/abs/1902.09217).
- **Counterpoint:** one essay argues [lockfiles and registry governance, not vendoring, were the lasting fixes](https://nesbitt.io/2026/02/10/lockfiles-killed-vendoring) (informed, but no measurements).
- **Thin:** node_modules size complaints are mostly folklore. I found no good measurement.
- **Verdict: helps.** Vendoring blocks left-pad and auto-pull worms. It would not have flagged event-stream unless someone reviewed the update.

**Nix/flakes: per-dependency pins diverge unless something unifies them.**

- **Does:** content-addressed sources with `flake.lock`.
- **Praise:** [everything relevant is expressed in the pinned files](https://discourse.nixos.org/t/what-are-nix-flakes-and-why-should-i-care/12910).
- **Complaints:**
  - [10,754 indexed flakes pin 3,261 distinct nixpkgs revisions](https://fzakaria.com/2026/08/31/how-safe-is-follows), and the `follows` fix risks untested combinations.
  - [100 separate imports raised peak memory about tenfold](https://discourse.nixos.org/t/mre-for-1000-instances-of-nixpkgs-problem/43982).
- **Sister project data:** Guix measured [source still available upstream at 96.4% after one year and 91.5% after five](https://arxiv.org/pdf/2405.15516). Extrapolating that to 100 years is my inference.
- **Verdict: both.** Pins alone do not survive; copies do.

**Unison: a clean answer that requires a different substrate.**

- **Does:** identity is the hash; dependencies are [tracked per definition, and versions coexist](https://unison-lang.org/blog/reducing-churn), [under `lib`](https://softwaremill.com/trying-out-unison-part-2-organising-code/).
- **Complaints:** ["content" is underspecified, and fixed functions lose their names](https://redlib.hbubli.cc/r/programming/comments/o9679a/unison_a_new_programming_language_with_immutable/h3b907d/?context=3) (a single comment). Adoption data is weak, and most claims come from the vendor. I found nothing on what happens when old and new types meet.
- **Verdict: an idea, not a model.** Borrow "identical content means identical identity" at library level.

**Git submodules and subtree: subtree is vendoring; a submodule is a pin.**

- **Submodule:** [tracks a specific commit](https://www.techielass.com/subtrees-and-submodules). The code is not in your tree, so the upstream must survive. Complaints: [branch switching and cross-repo changes](https://lemmy.amethyst.name/post/595901/262263) (anecdotal).
- **Subtree:** [consumers need learn nothing and no metadata is added, but your commits must not mix with the library's](https://gitprotect.io/blog/managing-git-projects-git-subtree-vs-submodule/). A [2014 retrospective reports each push getting slower](https://spin.atomicobject.com/?p=112929).
- **Verdict: subtree helps, submodules hurt 100-year builds.** Neither records license or version in a form tools understand.

**Python: years of churn, plus the best written vendoring policy.**

- **History:** [source installs via `setup.py`, then wheels, then pyproject](https://pydevtools.com/handbook/explanation/how-python-package-formats-evolved/); only recently a [standard lockfile requiring hashes](https://peps.python.org/pep-751/). PEP 723 puts [dependency metadata in the script itself](https://peps.python.org/pep-0723/), which is precedent for the owner's in-source metadata, with an explicit warning about auto-installing code.
- **Vendoring:** [pip's policy](https://raw.githubusercontent.com/pypa/pip/main/src/pip/_vendor/README.rst): released copies only, license files required, no changes except documented patches, versions listed.
- **Identity failure:** when distros unbundled requests, [`requests.packages.urllib3` was not the same object as `urllib3`](https://git.cbaines.net/python-requests/tree/requests/packages/__init__.py).
- **Verdict: helps.** Adopt the policy and expect path-based identity to bite.

**xz: the attack that neither model catches without review.**

- **What happened:** the [trigger was only in release tarballs; the payload was in binary test files committed to git](https://www.openwall.com/lists/oss-security/2024/03/29/4).
- **Lessons (my inference):** vendor from commits rather than tarballs; flag binary files.
- **Cooldown:** [8 of 10 attack windows were under a week; xz was about 5 weeks](https://www.blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns) (the author's own "very small sample"). [tj-actions repointed mutable tags](https://lil-business-blog.pages.dev/github-actions-supply-chain-attack-cicd-security) (weak source), so tags cannot be the pin. [Polyfill.io](https://sonatype.com/blog/polyfill.io-supply-chain-attack-hits-100000-websites-all-you-need-to-know) shows the same for hosts.
- **Verdict: mildly helps.** Vendoring delays updates by default, but no one reads every diff.

## Hard problems

| Problem | Best today | How vendoring fares |
|---|---|---|
| **Transitive deps** | Go/Cargo: automatic closure | **Weak by hand.** Odin users declare them by hand. A tool that flattens and copies fixes it. |
| **Diamonds and type identity** | Google's [one-version rule](https://opensource.google/docs/thirdparty/oneversion/?hl=bn) for simplicity; Go for [major-version coexistence](https://research.swtch.com/vgo-principles) | **Bad if nested** (see Go and requests). **Good if flat**: the conflict is visible in one folder. |
| **Deep security update** | Go/Cargo plus scanners; one-version gives a [single upgrade point](https://gist.github.com/hashbrowncipher/94f781dedd804c1b8198153c61fc6aea) | **Worst by default.** [Log4Shell: 80%+ of affected Maven packages were over one level deep, with many blocked on others](https://www.securityweek.com/google-finds-35863-java-packages-using-defective-log4j/). Flat vendoring removes the blocking, since you patch your copy. Finding the need still takes provenance. |
| **Discoverability** | [pkg.go.dev](https://pkg.go.dev/about): an index with no publish step and quality signals | **Neutral to weak.** It needs an index that holds no authority. Odin has only its curated collection. |
| **Publishing** | Go, Zig: a tagged repo | **Excellent.** No registry account, so one worm vector disappears. Git host renames and takedowns matter only when updating. |
| **Repo size** | Lockfiles (nothing stored); Zig's `paths` filter | **Real cost.** [Git keeps every old version in every clone](https://nesbitt.io/2026/02/10/lockfiles-killed-vendoring). Copy only imported files, as [Go copies only needed packages](https://go.dev/ref/mod). No hard numbers found. |
| **Offline, 100-year** | Vendored source; Guix with [Software Heritage](https://arxiv.org/pdf/2405.15516) | **Best.** Needs nothing but the repo and a compiler for `$dewy.version`. Foreign C libraries and system SDKs remain outside. |
| **License tracking** | Chromium presubmit; pkg.go.dev license check | **Bad by default**: [license risk is concentrated in direct source reuse, with little origin recorded](https://arxiv.org/pdf/2607.02059). Good if the copy tool requires a license file or field. |
| **Reviewing diffs** | [cargo-vet](https://www.github.com/mozilla/cargo-vet): recorded audits, CI gate | **Good raw material.** The diff is in your repo and is what gets built, which defeats the boltdb trick. Volume leads people to [hide it](https://gitlab.com/gitlab-org/gitlab/-/work_items/17123). Needs a dedicated view. |

## Evidence quality

- **Strongest:** the file-copying study (large, recent, but one preprint). Its [fix-rate bounds are wide, 44–83% for vendored and 71–86% for upstream sync](https://arxiv.org/pdf/2607.02059). It mostly studies unmanaged copies, so it does **not** measure tool-managed vendoring with metadata. Its [2-day versus 175-day lag for PR-linked copies](https://arxiv.org/pdf/2607.02059) is correlation.
- **Solid primary data:** the C++ survey (self-selected), the Guix link-rot figures, and Cargo's docs.
- **Anecdotal:** nearly all the Go, Zig, Odin and submodule pain reports. Incident reports show that attacks happen, not how often.
- **Missing:** any comparison of vendoring and package-manager projects over time; any language with first-class vendoring at scale. Odin is the nearest, and it is small.
- **Applications versus libraries:** ["libraries should never vendor dependencies"](https://jmoiron.net/blog/dependencies) is a 2016 opinion, but Go's and Python's experience supports it.

## Recommendation

**Adopt vendoring as the only install model, flat, and managed by a tool that writes provenance into `lib.dewy`.**

Illustrative only; the spellings are the owner's call:

```dewy
$library(shapes version='1.2.0' source='https://github.com/someone/shapes' commit='9f2c…' tree='sha256:…' license='Apache-2.0')
$requires(geometry min='0.4.0' source='https://github.com/someone/geometry')
```

- **Flat `libs/`:** one project-level folder, with no nested copies. Libraries ship their requirements, not their dependencies.
- **Lock:** the tree on disk plus its `tree` digest. No lock file. The compiler checks digests against the files, as Go checks `modules.txt`.
- **Version selection:** the highest requested minimum, so no solver. Conflicts appear as an edit in one place.
- **Two versions of one library:** allowed only as two explicit folders, with distinct types. The compiler explains the mismatch when they meet.
- **Tool commands:** add, update, audit, show-diff. Copy from commits, not tags or tarballs; take only imported files; flag non-`.dewy` and binary files, build-time code, and a missing license; optionally apply a short cooldown.
- **Scanner support:** the metatag gives scanners the source and version, closing the 10% provenance gap.

**What I'm least sure about:**

1. **How a library names its dependency.** A vendored library needs a path that works both in its own repo and under `libs/`. Sibling paths (`p"../geometry/lib.dewy"`) force a layout on library authors; a logical name adds the non-path resolution the owner wants to avoid. No surveyed ecosystem solves this with plain paths alone, and this is what could break the design.
2. **Update freshness.** No study shows that metadata alone closes the repair gap. It may take automated update proposals, which depend on infrastructure beyond the compiler.
