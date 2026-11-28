# Refinements on time values, round 1: `Duration<(>? 0s)>` and division by a nonzero time

Ladder 154 (a token-bucket rate limiter) refills tokens by `(now - b.last) / p.per`. The period was
checked positive when the policy was parsed, but `/` still gives `rational | OutOfRange` because the
compiler cannot see that, so 154 writes `(now - b.last) / p.per ?? 0` and a comment saying why the
`0` can never happen. This round proposes the form that lets the proof reach the division, dogfoods it
on thirteen programs and grades it. The result is open decision D52.

## What the rules say today

- LANGUAGE.md, time: "`d/1s` is an exact `rational`, `d/3` an exact quantity, `d//7` a `Duration`;
  a divisor known only at run time may be zero, so that result also has `OutOfRange`, and a constant
  zero is a compile error."
- LANGUAGE.md, refinements: "Scalar integer annotations can carry checked refinements ... Predicates
  cannot contain calls or other arithmetic." A string's length is the one other refined quantity.
- refinement.md, accepted contract atoms: "integer bounds, nonzero/disequality, comparisons between
  named scalar/length terms, conjunctions, ordered chains ...".
- Probed at this HEAD: `d:Duration<(>? 0s)>` is rejected with "unsupported refinement term; expected a
  scalar binding or integer bound". `if b >? 0s { a / b }` is still `OutOfRange | rational`, so a guard
  does not help either. Integer division is different: a divisor proven nonzero by its type or by a guard
  gives no failure, and an unproven one is a compile error with a fix-it.

## The proposal

```dewy
Policy:type = [count:int64<(>=? 1)> per:Duration<(>? 0s)> burst:int64<(>=? 1)>]

refill = (elapsed:Duration p:Policy):>rational => (elapsed / p.per) * p.count   # no `?? 0`
```

1. A stored time type (`Duration`, `Instant`) takes the refinement spelling integers have, with time
   constants (`0s`, `1ms`, a module `const`, `instant"..."`) as bounds: `Duration<(>? 0s)>`,
   `Duration<(>=? 1ms)>`, `Instant<(>=? launch)>`, a conjunction or chain as for integers. With the other
   arguments it reads `Duration<(>? 0ms) width=64>`. Bounds are constants only in this round.
2. Time values are proven by the same facts as integers: a refined type, a constant, or a guard
   (`if per <=? 0s return ...`, `if b >? 0s { ... }`), and a constructor proves a field as it does for
   an integer field.
3. `/`, `//` and `%` with a time divisor proven nonzero by 2 have no `OutOfRange`: `elapsed / per` is a
   `rational`, `elapsed // per` an `int`, `elapsed % per` a `Duration`. Unproven stays as today.
4. Facts flow through the arithmetic that keeps them exact: `d / 1s` of a `d >? 0s` is `>? 0`, and
   `t - c` and `t + d` carry bounds as integer addition of a constant does.

The limit the brief raised: a local proven only by a guard needs no fallback, because 2 and 3 let the
guard prove it. Not proposed: making a run-time-divisor `/` a nonzero obligation (a compile error
unless proven). Today the union is a legitimate value, `x / d ?? 0` or `match`, and a period typed
by a user is the common case; an obligation would turn working code into errors for nothing the union
does not already say. The `?? 0` stays available wherever the divisor is not proven.

## Two-question test

1. The common path: a positive period, timeout or interval used as a divisor. Today every such division
   carries `?? 0` or a `match` that cannot happen.
2. When it does not fit, adjusting is a guard or the `?? 0` fallback, both unchanged. So the semantics are
   taken; the new surface is the spelling of a refinement on a time, type (b). No new names.

## Peers

| Language | `elapsed / period` with a period that was checked |
|---|---|
| Python | `timedelta / timedelta` is a float and raises `ZeroDivisionError` at the division |
| Go | `int64(elapsed / period)` panics on zero; `float64` form gives `+Inf` |
| Rust | `elapsed.div_duration_f64(period)` gives `inf` or `NaN`, no signal |
| TypeScript | millisecond numbers; `0` period gives `Infinity` or `NaN` |
| Swift | `Duration / Duration` is `Double`: `inf`, no signal |

All five either trap or return a poisoned float at the division, and none lets the earlier check
remove it. Dewy keeps the exact `rational`, and the check that already exists removes the failure.

## Dogfooding

Thirteen realistic programs. Grades 1–5 on obvious, discoverable, concise, safe by default and
complete (O D C S Co), against Python, Go, Rust, TypeScript and Swift. Where a program scored under 5
in the first pass, the proposal changed (marked "pass 1") and the program was graded again.

### 1. Token bucket refill (ladder 154)

```dewy
take = (@b:Bucket p:Policy now:Instant cost:int64):>Duration | none => {
    let refill = ((now - b.last) / p.per) * p.count
    b.tokens = min(rational(p.burst) b.tokens + refill)
    b.last = now
    ...
}
```

5 5 5 5 5. The comment about a period of `0s` and the `?? 0` go; `parse_policy`'s existing
`if per <=? 0s return UsageError[...]` is what proves the constructor's field.

### 2. Download progress against a timeout

```dewy
progress = (elapsed:Duration timeout:Duration<(>? 0s)>):>int64 => {
    let done = min(rational(1) elapsed / timeout)
    (done * 100).floor()
}
```

5 5 5 5 5. A caller with a constant `30s` passes without a word; one with `Duration(text)` meets the
refinement as an argument obligation and is told to guard, as for an integer.

### 3. Metronome beat and phase

```dewy
beat_at = (now:Instant start:Instant beat:Duration<(>? 0s)>):>string => {
    let since = now - start
    "beat {since // beat}, {since % beat} in"
}
```

5 5 5 5 5. All three division forms lose `OutOfRange` together; Go and Python need two operations and
a zero check each.

### 4. Hits per second over a window, guard only

```dewy
rate = (hits:int64 window:Duration):>rational | ConfigError => {
    if window <=? 0s return ConfigError["window must be positive"]
    rational(hits) / (window / 1s)
}
```

Pass 1: 3 5 4 5 3. The `Duration` division is fine after the guard, but the divisor of `hits / ...` is
the rational `window / 1s`, and nothing proved it nonzero, so the line needed another fallback. Change
(rule 4): `window / 1s` of a window `>? 0s` is `>? 0`. After it: 5 5 5 5 5. The guard is all there is.

### 5. Easing for an animation

```dewy
ease = (t:Duration length:Duration<(>? 0s)>):>float64 => {
    let x = clamp(t / length 0 1)
    float64(x * x * (3 - 2 * x))
}
```

5 5 5 5 5. Smoothstep over elapsed time: the division is the only place the length matters, and
the parameter says so once for every caller.

### 6. Scheduler: runs missed while asleep

```dewy
missed = (last:Instant now:Instant every:Duration<(>? 0s)>):>int =>
    max(1 (now - last) // every) - 1
```

5 5 5 5 5. A job table `[name:string every:Duration<(>? 0s)>]` proves each entry at construction.

### 7. Cache freshness from a time-to-live field

```dewy
Entry:type = [value:string stored:Instant ttl:Duration<(>? 0s)>]
freshness = (e:Entry now:Instant):>rational => 1 - (now - e.stored) / e.ttl
```

5 5 5 5 5. The field's refinement is used at every read of `e.ttl`; a `ttl` of `0s` cannot be
stored, so no entry ever divides by it.

### 8. Sampling rate on a 64-bit tick

```dewy
expected = (span:Duration<(>? 0ms) width=64> every:Duration<(>? 0ms) width=64>):>int =>
    span // every
```

5 5 5 5 5. The refinement and `width=64` combine as another type argument would. The `0ms` bound is
a constant of the type's own tick.

### 9. Uptime and stale-reading checks

```dewy
const launch = instant"2026-01-01T00:00:00Z"
uptime = (at:Instant<(>=? launch)>):>Duration => at - launch
stale = (at:Instant<(>=? launch)>):>bool => at - launch >=? 1day
```

5 5 5 5 5. An `Instant` bound is a refinement like any other; `at - launch` is known `>=? 0s`
(rule 4), so a later `// 1hour` is a nonnegative count.

### 10. Retry wait as a share of a budget

```dewy
share = (waited:Duration budget:Duration):>int64 | ConfigError => {
    if budget =? 0s return ConfigError["no budget"]
    (waited / budget * 100).floor()
}
```

5 5 5 5 5. An early return on `=? 0s` proves `not=? 0s` for the rest of the function, as `>? 0s` would; a negative budget is allowed, as the guard says.

### 11. A period typed by the user, not guarded

```dewy
main = (argv:array<string>) => {
    let period = Duration(argv[1]) ?? return
    printl(Duration("2s") / period)   # still `rational | OutOfRange`
}
```

5 5 5 5 5. Safe by default: nothing proves `period`, so the result keeps its failure and the
program must handle it, as today. The message names both fixes: a guard, or a refined parameter.

### 12. A constant that breaks the contract

```dewy
share(5s 0s)       # error: the refinement `>? 0s` is false for `0s`
```

5 5 5 5 5. A refuted constant is a compile error, as `positive(0)` is for an integer.

### 13. Frame pacing with a fallback kept

```dewy
let fps = (1s / frame_time) ?? 0    # frame_time known only at run time
```

5 5 5 5 5. Unchanged and still allowed: the proposal removes a `?? 0` only where a proof exists,
and a program with no proof keeps the fallback it has.

### Summary

All 65 marks at 5 after the pass-1 change; before it, program 4 scored 3, 5, 4, 5, 3 and led to
rule 4 (the proof carried through exact division by a positive constant). The peers either trap or
return a poisoned float and none can use an earlier check. One caveat: programs 2, 5 and 9 assume the
checked-fact engine proves a constant bound on a time; that is implementation work, not a design
question. The programs are not run (the form is not implemented); programs 1, 4 and 11's current
behavior, and the rejection of the refinement, were probed on this HEAD.

## Not proposed

- Refinements on `rational` or `float64` (`rational<(>? 0)>`): a separate question with its own
  arithmetic; time is the case that came up.
- Bounds that name another time (`Instant<(>=? start)>`): the integer form allows other scalars, but no
  program here needed it. It can follow.
- An obligation on every run-time-divisor division (see above).
