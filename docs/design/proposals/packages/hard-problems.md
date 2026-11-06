# Vendoring: six bounded decisions

**Recommendation: ordinary file imports, declaration-based nominal identity, and one inert provenance metatag; fetching, flattening and auditing belong to tools.**

- Scope: six requested decisions; no implementation, resolver, registry, or binary ABI design. Owned output: this file only. Acceptance: source examples, rejection cases, diagnostics, and a lazy-build cost boundary. Budget: stop after the targeted module/type inspection.
- All `$vendor` syntax and diagnostics below are proposals requiring David's approval, not implemented behavior. `$dewy.version` is the brief's assumed contract; no occurrence was found in the inspected compiler or current design documents.
- Evidence: `compiler/module_paths.jo:54` normalizes absolute path keys; `compiler/check.jo:873` interns modules by those keys; `check.jo:1053` resolves file imports beside the importer, currently with package-cache fallback. `type_factory.jo:84` interns declaration/type-argument instances; `type_inference.jo:97` rejects different declarations. `expr.jo:2572` interns anonymous record shapes; `refine.jo:937` distinguishes structural conversion from nominal identity. `docs/design/modules.md` requires cycle-safe declaration registration and demand-driven checking.

## 1. Transitive dependencies

**Rule: a relative `p"…"` import is relative to the file containing it, never the program, working directory, or library entrypoint. Default to nested copies.**

```dewy
# Nested: libs/a/lib.dewy; identically in libs/b/lib.dewy
from p"libs/c/lib.dewy" import Point
# Resolves respectively to libs/a/libs/c/lib.dewy and libs/b/libs/c/lib.dewy.
```

```dewy
# Flat: libs/a/lib.dewy; identically in libs/b/lib.dewy
from p"../c/lib.dewy" import Point
# Both resolve to libs/c/lib.dewy.
```

- In `libs/a/src/work.dewy`, those imports become `p"../libs/c/lib.dewy"` and `p"../../c/lib.dewy"`. Moving `a` with its nested dependencies preserves its imports. Flattening rewrites affected imports and records a local patch.
- Explicit paths must fail locally, without searching caches or fetching. Normalize `.`/`..` before both opening and keying the file; using different paths for those operations can confuse identity around symlinks. Keep lexical identity: symlink/hardlink spellings do not promise one module; audited vendor trees reject symlinks.
- **Reject:** program-root-relative imports. Two independently vendored libraries using `p"libs/c/lib.dewy"` would silently select the application's copy instead of their own.
- **Failure:** `libs/a/lib.dewy` imports an absent nested `c`:

```text
error: cannot find 'libs/c/lib.dewy' (looked for libs/a/libs/c/lib.dewy)
note: relative imports start at libs/a/lib.dewy's directory; no dependency search was performed
```

## 2. Diamonds and type identity

**Rule: one normalized module path means one module instance; different paths mean different instances. Nominal types retain their declaring module, declaration, and type arguments.**

- A flat diamond loads one `c`; both imports refer to the same declarations and initialization. A nested diamond loads two, even with identical bytes, origin, version, or digest. Two copies may coexist without error until an incompatible value crosses between them.
- If both declare `Point = type of [x:int64 y:int64]`, their nominal `Point`s differ. Re-exporting one shared declaration preserves identity; copying its declaration does not. This matches current declaration-based interning.
- Anonymous structural records remain structural: `Point:type = [x:int64 y:int64]` can alias the same shape across modules. Compare resolved member types, refinements, effects and ownership obligations, including nested nominal identities. Different layouts never become identical because their aliases are both named `Point`. Checked value construction/conversion may produce a different layout; reference reinterpretation may not.
- **Reject content identity:** identical `c/lib.dewy` bytes importing `p"types.dewy"` can resolve to different `Point` layouts in their two directories. Hashing only the entry merges incompatible types. Hashing dependency closure, dialect and context instead adds cycle handling, whole-closure work, and surprising merging of independent global state.
- **Reject universal structural typing:** two same-shaped handles can have different destructors and ownership authorities. Keep structural records where explicitly chosen; do not erase nominal identities to fix diamonds.
- **Reject declared compatibility as equality:** `compatible='c@1'` cannot prove an altered field layout or destructor safe. Compatibility claims can guide tooling, never override checking. Share a declaration or write an adapter that constructs the destination type and satisfies its contracts.
- **Failure:** `a.make` returns its nominal `Point`; `b.consume(a.make)` requires the other copy, whose `y` is now `string`:

```text
error: type mismatch: expected Point from libs/b/libs/c/lib.dewy, found Point from libs/a/libs/c/lib.dewy
note: these are distinct nominal declarations; matching names or versions do not establish identity
help: import one shared declaration, or explicitly construct the destination value
```

- This qualification improves today's `expr.jo:995` message, which can merely say `expected Point, found Point`. The same rejection applies when both layouts happen to match.

## 3. Integrity and provenance

**Rule: record provenance and an expected payload digest in the entry's `$vendor`; audit explicitly, never traverse or hash the vendor tree during ordinary compilation.**

- Four required fields: `origin` (immutable upstream snapshot locator), `version` (human release label), `digest` (expected installed payload), `license` (license expression). Preserve full notices/text in `.dewy` comments or string data; the identifier alone is not the text.
- Define `sha256-tree-v1`: hash `Dewy-vendor-tree-v1\0`, followed by files sorted by UTF-8 relative `/` path bytes; each contributes unsigned 64-bit big-endian path length, path, content length, content. Include every regular payload file, including notices/assets; exclude the root's `libs/` subtree, whose libraries are audited separately. No Git administrative files are installed. Reject symlinks, traversal names and portable-path collisions.
- For the entry only, remove its sole complete `$vendor(...)` logical line, including its terminating LF, before hashing. Preserve all other raw bytes. This removes digest self-reference; `$dewy.version` and executable code remain covered. Audit rejects duplicate tags. The entry's directory is the ownership boundary, a tool convention rather than a language namespace.
- A local patch retains `origin`/`version`, adds `upstream` holding the pristine payload digest and `patch` describing the reviewed change, then updates `digest`. Import rewrites count as patches. Updating a recorded digest must be deliberate; a failed audit never silently accepts new bytes.
- Audit reports clean, recorded-local-patch, or unexplained-change. It verifies the pristine snapshot too when available; otherwise it explicitly says upstream provenance is unverified. Metadata cannot prove intent: an attacker able to replace source and its digests can forge a patch declaration. Trust requires a separately trusted/reviewed record or authenticated upstream, not a self-hash.
- Compile overhead: parse/retain the small literal header already encountered, O(header bytes); **zero extra payload reads, hashes or network requests**. No promised numerical speed result without measurement. Explicit full audit costs O(payload bytes + file sorting), includes unused vendor files, and checks dependency roots separately. Bytes outside audited roots are reported as unverified. Auditing is not a guarantee that later, changed bytes were built; verification/release work uses an immutable snapshot.
- **Reject:** checking the complete digest every build. A 2-million-line unused dependency must not burden a ten-line application or defeat the 200–250k lines/s target. Hashing only loaded files cannot establish a whole-tree digest either.
- **Failure:** editing a function without recording a patch:

```text
error: vendor payload mismatch at libs/pkgA/lib.dewy
note: installed bytes do not match $vendor.digest; this is an unexplained change
help: restore the recorded source, or review and record a local patch
```

## 4. `$dewy.version`

**Rule: each file selects its own language semantics; package release versions do not select language versions.**

- Program `0.2.0` may import library `0.1.0`, and program `0.1.0` may import library `0.2.0`, provided this compiler supports both dialects and their boundary. Do not inherit the caller's dialect; internal library files declare their own version too.
- Compile both into a common checked representation. Check imported signatures, layout, contracts, effects and lifecycle behavior at the boundary. Generic bodies retain their defining dialect. A builtin can share identity only where its semantics agree; otherwise require a checked bridge or reject the boundary. Never infer ABI compatibility from equal names or sizes.
- **Reject:** upgrading every file to the program's version. Changed arithmetic or initialization semantics would change an archived library without changing its source. Source preservation alone cannot supply an implementation of a future dialect.
- **Failure:** a compiler supporting through `0.2.0` encounters:

```dewy
$dewy.version = '0.3.0'
```

```text
error: unsupported Dewy version '0.3.0' in libs/pkgA/lib.dewy
note: this compiler supports versions through '0.2.0'; the importing module's version does not override it
```

- If both dialects are understood but an exported type lacks a sound bridge:

```text
error: cannot import Buffer from libs/pkgA/lib.dewy: no supported representation bridge from Dewy '0.2.0' to '0.1.0'
```

## 5. Tool boundary

**Rule: the compiler needs ordinary imports, sound identity, version handling and inert literal metadata; dependency management is ordinary Dewy tooling.**

- Compiler: accept one file-scoped `$vendor` literal record without execution, fetching, version solving, compatibility overrides or digest verification. Keep missing-path and qualified-type diagnostics. Existing cycle and demand-driven checking rules remain applicable.
- `dewy add`: obtain an explicit snapshot, materialize its source/dependencies, preserve notices, and write imports/metadata. `dewy update`: choose new source, preserve/reapply recorded patches or report conflict, update digests, and typecheck before replacing the installed tree. Neither operation silently flattens dependencies.
- `dewy audit`: read metadata as data, check whole inventories/digests and provenance availability, and report duplicate copies or unaudited dependency roots. These commands require no lockfile or compiler network access. Dependency edges remain source imports.
- **Reject:** compiler resolution from global package names/cache. Another machine's cache could silently supply a different `c` when vendored source is missing.
- **Failure:** updating locally patched source when its changed function was removed upstream; tool leaves installed files untouched:

```text
error: cannot update libs/pkgA: local patch conflicts in lib.dewy
note: installed source and $vendor metadata were not changed
help: resolve the patch against the requested revision, then retry the update
```

## 6. Minimal entry and importing program

**Rule: one new metatag, `$vendor`; no package name, dependencies list, compatibility tag, or special import syntax.**

- Complete single-file payload below; fictional origin, actual payload digest under §3. Metadata is optional for compilation and required for a provenance-checked vendor root. Patched copies add only `upstream` and `patch`.

```dewy
# libs/pkgA/lib.dewy (this explanatory comment is not file content)
$dewy.version = '0.1.0'
$vendor(
    origin='https://example.invalid/pkgA/revisions/0123456789abcdef0123456789abcdef01234567'
    version='1.2.0'
    digest='sha256-tree-v1:1dcabd480471b73a5526d9a35bf6d644d9d2504700faee38ed2565c6e8fc2b93'
    license='CC0-1.0'
)
Point = type of [x:int64 y:int64]
xyz = (p:Point):>int64 => p.x + p.y
```

```dewy
# main.dewy
$dewy.version = '0.2.0'
from p"libs/pkgA/lib.dewy" import (Point xyz)
printl(xyz(Point[2 3]))
```

- **Reject:** separate name/version/dependency metatags controlling resolution. Renaming `libs/pkgA` and adjusting its import should not require updating a second namespace.
- **Failure:** replacing `digest` with `'latest'`; the audit tool, not compilation, diagnoses:

```text
error: invalid $vendor.digest in libs/pkgA/lib.dewy: expected 'sha256-tree-v1:' followed by 64 hexadecimal digits
```

**Single recommendation:** adopt nested file vendoring plus explicit sharing, existing nominal/structural distinctions, and one tool-owned provenance record. **Least certain:** whether callers need routine build-time integrity enforcement; that would require a separately designed per-file authenticated scheme, rather than pretending lazy reads verify a whole tree.
