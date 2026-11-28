# Handles: validity a library declares and the compiler carries (round 1)

**BLUF.**
- **Proposal:** handle validity is an ordinary membership fact, `h in? c`. Its meaning is the container's `contains(c h)` function, which is the existing `in?` protocol. A library states validity with refinements that already parse:
  - `b:Body<(in? w)>` on a parameter requires it;
  - `:>Body<(in? w)>` on a result establishes it;
  - `:>array<Body<(in? w)>>` gives it to every element of an array;
  - `rope:Joint<(in? world)>` on a record field keeps it.
- **Carrying it across calls:** the compiler forgets the fact only at a call that can falsify it. Whether a call can is the call's *membership summary*, derived from the callee's body on demand, as length summaries are today. Nothing is trusted that the facts cannot show.
- **Pool:** Pool becomes an ordinary user of the mechanism. Its file-path recognition goes in two stages.
- **The examples:** `examples/physics.dewy` and `examples/physics_scene.dewy` drop `$runtime_checks` with two added `in?` tests and one type annotation.
- **Surface:** no new syntax, metatags or members. One spelling consolidation goes to David as D54: `in?` replaces `pool.has`. It was dogfooded and the names were tested.

## 1. Where proofs fail today

Each case was measured on master `5e332ec35` with `dewy check`, `$runtime_checks` removed (scratch `~/dev/tmp/handles1/`):

| Case | Result |
|---|---|
| `let a = w.add_box(..)  let b = w.add_box(..)  w.pin(a b at)` | `pin` may panic: nothing says `add_box`'s result is a live body |
| `w.pin(physics.ground a at)` | same: `ground = Body(0)` is valid only by a World invariant the facts cannot see |
| `if w.alive(a) { w.pos(a) }` | same: a library's own bool test does not establish its accessor's precondition |
| `f = (@w:physics.World a:physics.Body) => w.pos(a)` | same: no way to require a live handle |
| `loop body in scene.world.bodies() { scene.world.pos(body) }` | same: a returned array's elements carry nothing |
| Pool: `h = pool.add(x)` … `pool.remove(g)` … `pool[h]` | proven (hard-wired, see §2) |
| Pool: `touch(@pool)` (reads only) then `pool[h]` | "cannot prove the handle is in the pool": any `@` call forgets membership |
| Pool: `loop h in pool.handles { pool[h] }` | unproven: `handles` elements are not known members |
| Pool on a record field, then `paint(@scene k)` writing only `scene.fills`, then `scene.pool[h]` | proven: field-precise call effects already keep sibling facts |

`physics_scene.dewy` fails at every `pin`, `rod` and `add_*` use of a body. `physics.dewy` fails at `kind(body)` (from `bodies_at`) and at `outline`, `radius` and `pos` (from `bodies()`). The joint calls (`ends`, `drag_to`) are silently total today: they do nothing for a dead joint, the bug string-shapes round 1 §3 flagged.

## 2. How Pool's proof works, and why it doesn't generalize

`compiler/facts_pools.dewy` recognizes six Pool functions by name (`has`, `[]`, `__pool_index`, `[]=`, `add`, `remove`). It also requires their declaration to come from `{lib_dir}/std/pool.jo`. Then it applies a hand-written model:
- membership is an element projection of the pool's value at the handle;
- `has` gives `member > 0`;
- `add` keeps every member and gives the result a fresh rank;
- `remove(g)` keeps the members whose rank provably differs from `g`'s;
- `[]=` keeps.

A user's wrapper, the physics World or a from-scratch slot map can't reach the model. Neither can a function between the caller and the Pool: any `@` call forgets. The model is also a trusted claim about `pool.jo` that appears nowhere in `assumptions.md`.

Dictionary keys have a second hard-wired membership system (`k in? d`, LANGUAGE.md "`d[k]` … need the key present"). The design below is the general form of both. Dictionaries keep their builtin rules and also gain call summaries.

## 3. What the design already has

| Construct | Status | Role here |
|---|---|---|
| `in?` with a `contains(container needle):>bool` overload | implemented for user types (tested: `H[1 1] in? t` works) | the validity relation |
| Partial-operator refinement `<(op x)>`, dependent on another parameter (`i:int64<(<? xs.length)>`) | decided 2026-10-23; `<(in? t)>` already **parses** and is rejected only as "unsupported refinement predicate" | requires |
| Returned refinement naming a `@` parameter's final state (`append = (@xs …):>addr<(<? xs.length)>`) | implemented | establishes |
| Element contracts on results (`:>generator<addr<(<? names.length)>>`) and sibling field contracts (`next:array<int64<(<? nodes.length)>>`) | implemented | arrays of handles; handles stored in records |
| Inferred call summaries: a result's length, record-field lengths, "kept upper" bounds (`facts_summaries.dewy`) | implemented | precedent for inferring results and preservation |
| Field-precise call effects | implemented (row 9 of §1) | the cheap "keeps" test |
| "Pure calls in guards contribute verified contracts" (refinement.md §2) | design rule | the callee unfolds `contains` into ordinary facts |
| Comptime hooks, `&` intersection, metatags | exist | **not needed.** Validity is run-time state of a container, so there is nothing to generate at compile time. Intersection adds fields, not relations. A tag would be a claim, which §7 rejects. |

`resources/discussion_points.md` has nothing on handles. The closest earlier thinking is in two places. String-shapes round 1 §3 proposed "move body storage onto a Pool; a wrapper whose body is `__bodies.has(h)` publishes that fact, no new spelling". Bulletproof round 3 §10 proposed "`w.pos(ball)` proven after `add` or within `if w.has(ball)`". This round keeps their intent and their no-new-syntax constraint. It also removes the wrapper-only and Pool-only limits.

## 4. The mechanism

### 4.1 The relation

A container type defines `contains(c:C h:H):>bool`, a pure function with no effects (`& no_effects`) that cannot panic. That body is the validity relation, written once in ordinary code. `h in? c` is then a **membership atom**: an opaque fact over the *values* of `h` and `c`, keyed by the resolved `contains` declaration (binding identity, never a path).

A `contains` that is impure, may panic or reads globals is a declaration error wherever it appears in a refinement.

### 4.2 Requires

`pos = (w:World b:Body<(in? w)>):>vec2` puts `b in? w` on the caller, checked like any refined argument after all actuals are evaluated (refinement.md §4).

The callee receives the atom **unfolded**: its entry state gets the conjuncts of `contains(w b)` as facts. For example, `b.h.slot <? w.bodies.__where.length` and `__gen[b.h.slot] =? b.h.gen`, or the Pool atom when `contains` is `b.h in? w.bodies`. So the library's own indexing proves from them, with no trust. A union arm can carry the contract: `a:Body<(in? w)> | Ground`.

### 4.3 Establishes

- **Written result:** `add = (@p:Pool<T> x:T):>Handle<(in? p)>`. The result is in `p`'s value after the call. Each return is checked by unfolding `contains` at that point.
- **Inferred result:** a function without a result contract gets the same summary the compiler already infers for a returned length. In `physics_scene.dewy`, the user's helper `add_box(@scene …)` returns a body known to be in `scene.world` with no annotation. Library APIs write it, because it is their promise.
- **Guards:** `if h in? c` (or a direct `contains(c h)` call) gives the atom on the true edge and its negation on the false edge. `w.get(b)` stays the value form: `T | none`, no proof.
- **Elements:** `:>array<Body<(in? w)>>`. The library proves each push, typically `[loop h in w.bodies.keys if <filter> Body[h]]`. Reading an element gives the atom. Pool gets `keys` this way, which fixes row 8 of §1.
- **Fields:** `Level:type = [world:World player:Body<(in? world)>]` is a sibling contract. It is checked at construction and after every change of `world`, so a store or call that may remove the player is an error at that write (program 12). Values in a dictionary work the same way.

### 4.4 What keeps it, what ends it

The atom names the container's current value. Any write gives `c` a new value, so the atom survives only by a rule:

| Event | Rule |
|---|---|
| A write in the program's own code (`c.gravity = g`, `c.bodies[h].pos += v`) | kept if the write cannot reach the fields `contains` reads (its **read set**, computed once from its body). Otherwise forgotten, unless the write is itself a call (next rows). |
| A call taking `@c` (or `@` of a record holding it) whose settled may-write regions miss the read set | kept. This is today's field-precise effect test (row 9 of §1). |
| A call whose regions touch the read set | its **membership summary** for that parameter decides (§4.5): `keeps`, `keeps unless key k` (a removal), or `forgets`. A refined result adds `fresh`: its key differs from every member at entry. |
| An unknown callee, callback, extern, a recursive cycle, or an exhausted budget | forgets |
| Copy or move of `c` (`let w2 = w`) | the atom follows the value: `b in? w2`; later writes to `w` don't touch `w2`'s atoms |
| Replacement (`scene = fresh()`) | forgotten, as every fact about the old value |
| Join | an atom survives where every predecessor has it. On a union value it is conditional on the arm (`previous` is `Ground`, or a `Body` in the world), as optional-payload facts are today. |

`keeps unless key k` keeps a member `h` when the caller knows `h`'s key differs from `k`'s. That knowledge comes from:
- `fresh`: whichever of the two was added second;
- or `h not=? k` with both members. Two members that differ as values differ in key, a lemma checked once per `contains` (below).

This is Pool's current rule ("both came from `add`, one while the other was in"), now derived.

### 4.5 Computing a summary

A summary is computed on demand, only when a caller holds an atom on an argument across the call and later needs it. It is cached per (callee instance, parameter, `contains`):

1. **Region prefilter, O(|read set| × |regions|):** no overlap means `keeps`. Physics `step`, `set_velocity` and `push` stop here, because they write bodies' motion fields, arbiters and events, not the slot tables.
2. **Symbolic member pass:** analyze the callee once more with a fresh handle value `h`, entering with the unfolded `contains(c h)`. At every normal exit, query the unfolded `contains(c' h)`.
   - All proven: `keeps`.
   - Proven only under `h.key not=? k.key` for a handle parameter `k` the callee writes at: `keeps unless key k`.
   - Otherwise: `forgets`, with the first write that broke it kept as the witness.
   - For a refined result, also query `result.key not=? h.key`: `fresh`.

   The pass uses the ordinary fact engine and budgets. Its cost is bounded by one more fact pass over the callee.

Two general fact-engine rules make slot tables provable (they help any code, not only handles):
- **Disequality from element facts:** if `a[i]` and `a[j]` of the same array value have disjoint known intervals or tags, then `i not=? j`. Pool's `add` tests `__where[slot] >=? 0` before reusing a slot, an O(1) check that never fails while the free list is right. That makes `slot` differ from every member's slot (program 03 does the same).
- **Weak update:** a write `a[i] = v` that may alias a tracked `a[j]` keeps the hull of the old and new bounds rather than forgetting both. Pool's `remove` moves the last item and updates `__where[moved.slot] = i` with `i >=? 0`.

The injectivity lemma (members that differ in value differ in key) is a two-handle query on the unfolded `contains`: equal keys, both members, so every handle field is equal. It is cached per `contains` and costs O(handle fields).

### 4.6 Cost

- **Dormant:** zero. A demand flag set by the first `in?` refinement or summary request guards every new branch, as for self-length refinements.
- **Active, per call:** one region test and, if a summary is needed, O(tracked atoms on that container), within the existing `FACT_CAP`.
- **Summaries:** each costs at most one extra fact pass over the callee, once per program, and only when demanded. Recursion forgets rather than iterating.
- **Read sets:** O(body of `contains`), once.
- **Measurement:** the flagship panel's instruction counts must not move, since no flagship uses `in?` refinements. The physics examples get measured before and after.

### 4.7 Diagnostics

Each failure names the handle, the container and the event. Three shapes, from the programs:

```
error: `bob` is no longer in `names`                          # refuted
    note: `names.remove(bob)` (line 39) removed it
    help: `names.get(bob)` gives none for a missing key

error: cannot prove `boom` is in `mixer`                      # forgotten by a call
    note: `mixer.play(explosion volume=0.3)` (line 30) may replace any voice: it writes
          `m.channels[slot]` for a `slot` it picks (10_voices.dewy:14)
    help: test it with `if boom in? mixer`, or use it before starting another sound

error: cannot prove `b` is in `w`                             # a parameter
    help: require it, `b:Body<(in? w)>`; test it with `if b in? w`; or use `w.get(b)`
```

A field contract adds: "removing `e` may remove `level.player`, which must stay in `level.world`: nothing shows `e` differs from it". `$runtime_checks` still turns an unproven site into a check, which is `contains` itself, O(1). A refuted one stays an error even then, as bulletproof round 3 §10 required.

### 4.8 Concurrency and moves

- **Facts never cross tasks.** A handle is a plain value that tasks may send freely, and its atom stays behind. The receiver has a different container value, or none, so it tests. This is no new rule: facts are per task, and value semantics means another task can't change the caller's container.
- **Shared containers** (`Mutex<World>`): atoms hold while the guard is held, exactly as dictionary keys do (`@(m.lock())`), and are forgotten at release.
- **Parallel work** over a container's items (`parallel` over `@w.bodies.items` partitions) writes items, not the slot tables, so it keeps every member (region prefilter). Removal needs `@w` whole and is never parallel.
- **Moves and copies** carry atoms with the value (§4.4). A copied world is a snapshot whose handles stay valid in it, which value semantics makes correct. Consuming handles stay rejected (string-shapes round 1).

### 4.9 Trust and the strict lane

Nothing new is assumed:
- `contains` is ordinary code;
- a requirement is checked at the call, an establishment at the return, and a summary in the callee.

Stage 1 (§9) keeps today's Pool model for Pool's own `add` and `remove` until the two fact rules land. It does so by binding identity, not by path, and it is listed in `assumptions.md` as "the bundled Pool's add and remove keep other members (reviewed, not derived)", opt-out pending. That row describes a trust that exists today unlisted. Stage 2 derives the same summaries from `pool.jo`'s body and deletes the row.

### 4.10 Pool and physics as ordinary users

- **Pool** (`00_library_side.dewy`) defines `contains`, writes `Handle<(in? p)>` on `add`, `__index__` and `__setindex__`, and adds `keys`. `facts_pools.dewy`'s name and path recognition (`fact_pool_call`, `fact_pool_type`, `pool_library_fn`) goes. Out of scope here: the direct-update fast path (`__pool_index`, `pool_direct_update`) is a code-generation choice with the same path check.
- **Physics** stores bodies and joints on two Pools:
  - `Body` and `Joint` wrap a `Handle`, and `body.id` stays for dictionary keys;
  - `ground` becomes its own type, so joint constructors take `Body<(in? w)> | Ground`;
  - accessors require `<(in? w)>`, and `bodies()`/`bodies_at()` return arrays of members;
  - joint reads and writes require membership instead of doing nothing;
  - `w.get(b)` gives `BodyState | none`;
  - `alive` and `joint_alive` go;
  - removing a body forgets its joints (a `retain` with a callback).

  `lib/physics3d.jo` follows the same pattern later.

## 5. Alternatives

| Option | For | Against | Verdict |
|---|---|---|---|
| **A. Membership atoms, written contracts, derived summaries (this round)** | No new syntax; checked, not trusted; any container shape (pools, epochs, fixed tables, user slot maps); Pool stops being special | Largest compiler slice (§9); summaries make a library's internals part of what callers rely on, so a library change that starts removing breaks callers' proofs (correctly) | **Recommended** |
| B. Wrapper transparency (string-shapes round 1, stage 2): store on Pool, and a wrapper whose body is `__bodies.has(h)` publishes Pool's fact | No annotations at all | Requirements become inferred public contracts; only Pool-backed containers; `step` and other `@` calls still forget without summaries; arenas and fixed tables (programs 07, 10) are out | Subsumed: A with inferred results is B where B works |
| C. Declared roles: `$adds`, `$removes`, `$keeps` on functions | Small to build; explicit | A wrong claim erases a check the library body relies on: an out-of-bounds read on library honesty. New surface; needs a strict-lane opt-out | Rejected: an incantation, not a fact |
| D. Quantified postconditions (`void & <every h in? before: h in? after>`) | Fully explicit | New syntax; refinement.md rejects quantifiers; authors would repeat what the body already shows | Rejected |
| E. Consuming handles (`remove` takes the handle) | Catches `remove; use` in one scope | Handles are aliased in globals and arrays (`contacts()`, `bodies()`); owners in globals are unsupported | Rejected (as in string-shapes round 1) |
| F. Branded handles per container (Rust "generativity") | Proves *which* container | Says nothing about removal; heavy types | Complementary at most; not needed |
| G. Value only: `get` gives `T \| none` (Rust slotmap's default) | Exists | Every access is a branch; "the player always exists" pays forever | Kept as the escape, never the only path |
| H. Owning values with drop hooks instead of handles | Nothing can name a dead resource | Fits one owner per resource, not many names for one thing | Right for single-owner GPU buffers and files (program 05's note), complementary |

## 6. Dogfood

Thirteen programs are in [programs-r1/](programs-r1/). Each one is graded 1–5 on obvious (O), discoverable (D), concise (C), safe by default (S) and complete (K) against the best of Rust (slotmap/thunderdome generational indices, wgpu owned buffers, bumpalo lifetimes), C++ (indices or pointers), Go (maps of ids), Swift (dictionaries with optionals) and Python (dicts, weakrefs). "Concise" is judged against the shortest *safe* equivalent. Python's unchecked version is shorter and crashes.

| # | Program | O | D | C | S | K | Notes |
|---|---|---|---|---|---|---|---|
| 00 | Library side: Pool and physics | 5 | 5 | 4 | 5 | 5 | Each accessor states `<(in? w)>` once (49 in physics); the "may panic" fix-it offers it |
| 01 | `physics_scene.dewy` rewritten | 5 | 5 | 5 | 5 | 5 | Tag gone; one annotation (`previous:physics.Anchor`), as Rust's enum would need |
| 02 | `physics.dewy` rewritten | 5 | 5 | 5 | 5 | 5 | Two `in?` tests for joints held in globals across frames, as `if let Some` in Rust |
| 03 | Slot map from scratch | 4 | 5 | 5 | 5 | 5 | Callers 5; the author must add the "never reuse a full slot" test for `fresh` to be a fact |
| 04 | ECS (entities, component dictionaries, a two-component query) | 5 | 5 | 5 | 5 | 5 | Query helper returns entities proven in both dictionaries |
| 05 | GPU buffer handles | 5 | 5 | 4 | 5 | 5 | Stored handles are tested once a frame; wgpu's owned buffers need no test |
| 06 | File-descriptor table | 5 | 5 | 5 | 5 | 5 | Double close is a compile error; script numbers are tested |
| 07 | Per-frame arena (epoch validity) | 5 | 5 | 4 | 5 | 5 | Provable with today's facts; a reference stored inside the arena's own items is tested on read |
| 08 | Shooter: homing bullets, retained pools | 5 | 5 | 5 | 5 | 5 | `keys` elements are members; `retain` forgets |
| 09 | Node editor graph | 5 | 5 | 5 | 5 | 4 | "A live edge's ends are live" is an invariant facts can't see: `ends` gives an optional, as petgraph's does |
| 10 | Mixer with voice stealing | 5 | 5 | 5 | 5 | 5 | `play` forgets every voice, derived from its body with no tag; the note names the line |
| 11 | Chat server connections | 5 | 5 | 5 | 5 | 5 | Events' ids are tested; just-accepted ones are proven |
| 12 | Platformer: player in a field contract | 4 | 5 | 5 | 5 | 5 | Removing an enemy needs `e not=? level.player`; the error says so |

**59 of 65 marks are 5.** Iterations: the first drafts had 12 marks below 5, and five changes fixed six of them:
- inferred membership results for unannotated helpers (01 C3 to 5, 05 C3 to 5);
- requiring membership on joint calls instead of keeping them silently total (02 S3 to 5);
- `keys` with an element contract (08 C4 to 5);
- the conjunction query (04 C4 to 5);
- the fix-it on "may panic" (00 D4 to 5).

**Why the remaining six can't reach 5 in this design:**
- **03 O4:** freshness needs a local fact that the reused slot is free. The alternative is reasoning over a container invariant (the free list holds only free slots), which the fact engine deliberately doesn't do. The author learns it from the caller's note, which points at the unproven write.
- **05 C4 and 07 C4:** a handle stored across frames, or inside the container's own elements, is tested on use. Rust avoids this with owners or lifetimes. Dewy's answers are owning values with drop hooks (05) and the deferred general dependent element contracts (refinement.md, "Deferred").
- **09 K4:** a relation between two containers' memberships ("a live edge's ends are live") is a cross-container invariant. Rust's petgraph has the same `Option`.
- **12 O4:** a field contract is a promise the program made. Removing *any* body must show it isn't the promised one, which is the price of zero tests per frame. Without the field contract the program is 5/5/4/5/5 with a test per frame.
- **00 C4:** requirements are written by rule (public contracts are written). Inferring them would make 5 and break that rule.

## 7. Cold read

Three context-free readers (Sonnet, Haiku, Fable) read nine shuffled lines (kit `~/dev/tmp/naming-1107/r36/`):
- **Requires, establishes, element and guard forms:** 3/3 read correctly, with confidence 3–5. This covers `pos = (w:World b:Body<(in? w)>)`, `add … :>Handle<(in? p)>`, `bodies … :>array<Body<(in? w)>>`, `close … f:File<(in? files)>`, `if h in? pool`, and `if ball in? world`.
- **Field contract** (`rope:Joint<(in? world)>`): the meaning was read correctly 3/3, with confidence 2–3. One reader thought the record could later hold a removed handle, so the docs must say the contract holds after every change of `world`.
- **`contains`:** one reader of three saw it as the definition behind `in?`. It is library-author surface and already documented.
- **`pool.has(h)` versus `h in? pool`:** 3/3 rated `has` less clearly a proof. That is D54's evidence.

## 8. What needs David

Only D54: `in?` is the one spelling of handle membership, so `pool.has(h)` goes and D11's proposed `w.has(ball)` becomes `ball in? w`. It is reversible.

The semantics pass both of the two-question tests:
- After `add` or `in?`, callers write nothing.
- A stored handle takes one `in?` test or `get`.

The refinement forms are the decided partial-operator spelling with a dependent operand, a natural extension, so they are reported here rather than asked.

## 9. Implementation

**Stage 1 (about 1,400 compiler lines, about 2 weeks):**
- the atom and `contains` resolution (`refine`, about 200 lines);
- guards, unfolding at entry and checking at return (about 350);
- transfer of the atom through writes, copies, joins and union arms (about 200);
- summaries: region prefilter, symbolic member pass, cache and witnesses (about 450);
- element, field and result routes (about 150);
- diagnostics (about 150).

Pool's `add` and `remove` keep their model by binding identity (the `assumptions.md` row). The library side:
- `pool.jo` gets contracts and `keys`, and `has` goes after D54;
- physics moves onto Pools (about 300 lines changed);
- both examples drop `$runtime_checks`.

Tests go in new files under `tests/`: refuted, unknown, through-call, field contract, union-arm join, copy snapshot and `Mutex` guard.

**Stage 2 (about 400 lines added and about 250 removed, about 1 week, time-boxed):**
- the two fact rules (§4.5);
- Pool's summaries derived from its body;
- delete `facts_pools.dewy`'s model and the `assumptions.md` row.

One failed pilot keeps the stage 1 bridge.

**Gates:** each commit runs focused tests and the quick suite. The batch runs the full suite, bootstrap and fixed point, and the flagship instruction counts must stay unchanged.

## 10. Found outside scope

- Today's Pool model is trusted but missing from `assumptions.md`.
- `pool_direct_update` and `__pool_index` recognize Pool by file path, as `facts_pools.dewy` does.
- Physics joint calls silently do nothing for a dead joint (`__jid` returns -1).
- `lib/physics3d.jo` has the same handle pattern with 47 lookups.
- A read-only callee taking `@` (row 7 of §1) forgets every fact on that argument, not only memberships. A "reads only" summary would help lengths too.
