# Claude (Opus) critical pass on Grok's critique of v4

## Points to adopt from Grok
- **`Instant` storage:** plain `Instant` = int128 count of 1 ns ticks since J0. int64 ns only spans 1685–2269, which fails the 10,000-year priority. `width=64` stays an explicit packed form.
- **Elapsed time is monotonic:** `now - start` uses the monotonic sample, and wall time is `.nominal`. The type change at `.nominal` is the fix for Go's hidden-monotonic bug.
- **No `L_G` or leap-table work in `now`:** it uses one cached offset.
- **Compile-time-checked literals are infallible when unique.**
  - A literal fold or gap without a policy is a compile error, not a runtime `or_throw`.
  - Runtime strings stay fallible.
- **Negative leap seconds** are just a skipped label in the segment table. No dedicated feature, and no `:60` clamp.
- **Host zone name plus pinned rules,** with `ZonePackStale` as a status and `zone_source='host'` as an opt-in.
- **Module cut:**
  - `time` covers clocks, `Instant`, `Duration`, `sleep` and `within`;
  - `time/civil` covers dates, zones and periods;
  - `time/science` covers the rest.

  Programs link only what they name. This doubles as the compile-speed rule.
- **A discrete successor on `Instant`;** density only on `Coordinate`.
- **Prior-art table:** keep the Go, jiff, Temporal and C++ chrono lessons.

## Where I disagree with Grok or would change its proposal

1. **Edition in a "project file"** conflicts with David's "everything in `.dewy` source".
   - Use a main-file metatag, `$edition = 2026`, set like `$build`/`$target`: a statement sets it, an expression checks it.
   - If it's absent, the compiler assumes the current edition and warns, with a fix-it that inserts the line. Code that states its edition never changes meaning when the compiler is upgraded.
   - Library modules declare their own edition the same way, so editions mix per module, as in Rust.
2. **`1day` / `1week` as type errors on `Instant` and `sleep` is surprising.**
   - On the TT axis, a day has exactly one meaning: 86400 s. There are no leaps and no zone.
   - Proposal, directed by the receiver type:
     - `Instant + 1day` and `sleep(1day)` give 86400 s;
     - `ZonedDateTime + 1day` and `Date + 1day` give a calendar day, the same local time tomorrow under the scope's gap/fold policy;
     - `month` and `year` stay calendar-only, as already decided.
   - The trap Grok worries about, `meeting + 1day` drifting across DST, is exactly the zoned case, and it gets the civil meaning.
   - This needs David's decision.
3. **Lazy clock acquisition makes the first `now` fallible,** which reintroduces an error branch.
   - Keep v4's entry acquisition, but only for providers the program statically reaches.
   - The compiler already knows whether `now`, `sleep` or civil reads are reachable. That gives both "pay only for what you use" and "fail once, at entry".
   - Pure programs acquire nothing.
4. **`now + 5s` as a monotonic deadline:** fine, but say what printing it shows.
   - It should print its wall projection with a `~` marker, like the reading itself.
   - A deadline must never be serialized as an `Instant` without `.nominal`.
5. **`age` defaulting to `leap_day='march_1'`:** jurisdictions differ (e.g. Feb 28 in some), so a silent convention here contradicts least surprise.
   - Keep the default only for `age`, which counts completed anniversaries, and note it under `$time.require_profile`.
   - `legal_age` always requires a jurisdiction. Grok already says this; just make sure the docs don't blur the two.
6. **`Coordinate<Scale>` as a rational** keeps a rational in the language. It's acceptable because it is opt-in and science-only, but name the cost: it allocates and has a variable denominator.
   - Alternative: `Instant<tick=…>` with caller-named ticks covers most uses.
   - Keep `Coordinate` only for exact affine scale maps (TT↔TCG, TCB↔TDB) and uncertainty work.
7. **Example syntax fixes:**
   - `$calendar = gregorian` should use the string-literal union style, `$calendar = 'gregorian'`, unless calendars are types: `Date<Gregorian>` suggests a type, so maybe `$calendar = Gregorian`. Decide one way.
   - Example 2's `loop true { … }` is fine.
   - Example 14's `ship.elapsed(...)` shadows `ship`.
   - Example 12 uses the commas-free style correctly.
8. **Missing from everyone so far:** how `Duration` is stored. It should be an int128 ns count too, or int64 with an explicit width; check how `125ms` prints.
   - Also `Duration` ↔ float conversions for physics and games: `dt.seconds` returns float64 explicitly.
   - Game loops want `dt` as a float. Make that one named member, never implicit.

## Decisions that will need David
- `1day`/`1week` semantics (point 2).
- `$edition` as a main-file metatag (point 1), and edition semantics in general. This is language-wide, not just for time.
- int128 default width: performance vs range. Recommend int128.
- The literal-call infallibility rule (`instant"…"`, `date"…"`, `zoned"…"`, `zone"…"`, `utc"…"`).
- The `$calendar` spelling and its value form.
