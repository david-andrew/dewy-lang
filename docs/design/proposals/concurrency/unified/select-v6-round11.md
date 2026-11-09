# Select, round 11

A qualified arm is legal only on a match written directly on the call that prepared the waits. The member names the type. The match says which argument produced it. `$named[Png Jpeg Gif]` installs those members. It is the spelling readers recognized, and it is backed by an ordinary comptime function.

`&` intersects every type. `heart.types & (Tick | Closed)` is `heart.Tick | heart.Closed`.

## Provenance

A source pattern is eligible only when the scrutinee is written there as `select(...)`, `race(...)`, `first_ok(...)`, `inbox.next` for an `inbox = merged(...)` in this function, or a direct `receive`, `next`, or `reserve`. The only wrapper that preserves this is `or_throw<...>`.

Every wait in that call is written there: `@path.op…`, `@name` for a named wait declared in this function, or `if cond @… else none` of those.

1. A slot has three identities: the receiver binding, the prepared operation, and the registration. The pattern keeps the slot with that receiver or operation and that resolved outcome type.
2. `heart.Tick` is the type. The match supplies the source. Copied elsewhere, the value is only the type.
3. From preparation through the match, including later arguments of that call and the loop back to the next preparation, the receiver path and the named wait stay immutable. Assignment, replacing an ancestor, a mutable borrow, a shared alias, and a closure that captured the place are errors. `let` does not prove this. `replace(@child)` between `@child.stdout.receive` and `child.stdout.string` is an error. The fix-it is a fresh local, or a plain arm.
4. A wait prepared on a backedge gets that iteration's slot. Replacing the receiver in the tail invalidates the next match.
5. The path is a local or a field chain. An index is not stable. Bind `let ch = channels[i]` and prepare `@ch.receive`.
6. `inbox = merged(...)` is one binding and its wait table. A copy or a later assignment does not carry the table. `select(@inbox.next)` and `merged(@inbox.next …)` see one opaque source. One inner close does not retire that outer source while an inner payload remains.
7. A direct receive, next, or reserve has one slot.
8. A helper, a stored result, a dynamic path, or an alias this walk cannot reject is rejected. The fix-it is a plain arm, or the wait written in the call.

Given up, and still expressible: matching a saved result, a helper that returns the result or the wait, `let room = if cond @w else none` then `select(room)`, a loop that builds the waits, and nested qualification through `@inbox.next`. Plain types cover all of them. A source the caller must tell apart inside a helper is a field on the payload, or a match inside the helper.

The same prepared wait listed twice is "this operation is listed twice". One commit token. A channel does not rendezvous with itself. No alias-equality proof. A losing receive takes nothing. A losing send delivers nothing.

## Facts, progress, escape

The `if` is an obligation fact for that registration only. Existing obligation rules drop it when a later argument, or anything else, mutates the place. The arm does not receive the fact again at entry. `local.length >? 0` does not prove `pop(0)` if a later argument clears `local`.

Progress is consuming a value, taking a tick, leaving the loop, turning that same registration off, or a step that blocks or moves forward. `merged` retiring a source counts as turning it off. A terminal outcome that stays ready (a close that stays closed, a poll that stays empty) must turn that registration off or leave the loop. An unchanged closed wait, a flag only another wait reads, and a timeout poll that puts `.value` back are still errors. Repeated ticks are not.

`path.<T>` and `(@name).<T>` select the resolved type on any eligible match. They do not look up a member. They are the escape for a clash, an omitted shorthand, and a generic parameter. Renaming the parameter does not retarget them. They are not legal on a stored result.

## Names

`$named[Png Jpeg Gif]` is the record `[Png = Png Jpeg = Jpeg Gif = Gif]`. Spread it with `...`. A callback is `each=@handler`. The backing function is ordinary comptime, and a user can call it:

```dewy
named = <Each>(types:array<Each>) =>
    [loop t in types $field(t.name) = t]
```

The call is specialized on the value sequence. An `array<Each>` parameter does not erase it. A runtime sequence is rejected. With `each`, the loop specializes the callback per element. The field's type is that call's result. The results are not joined into one type. `plugins.Draw` is `(p:Draw):>void`.

`T.name` is the canonical short name, when one exists. It is not `fields(S).name`, which names a field.

| Type | Name |
|---|---|
| `Job:type = [id:int64]`, the declaration that introduces it | `Job` |
| `Closed<Job>` | `Closed` |
| a parameter `T` instantiated as `Job` | `Job` |
| a parameter instantiated as a type with no name | absent |
| `ui.Job` and `net.Job` | both `Job`. The module is part of the type and not of the short name. |
| `AlsoQuit:type = Quit` | no name of its own. The type's name stays `Quit`. |
| `Alias:type = [x:int64]`, and the right-hand side had no name | `Alias` |
| an anonymous record, an anonymous union, an unnamed intersection | absent |
| a literal union member | its text, when that text is a field name (`loud`). A number has none. |

`members` of a type union yields the alternative types. `members` of a literal union yields the singletons, as it does today. A union alias is not itself an alternative.

Strict `$named` errors when a name is absent or repeated: `field Quit is listed twice`. That is the registry rule.

`Waitable<R>` does not use the strict rule on the raw union. It installs a shorthand only when exactly one alternative has that canonical name and the record does not already have the member. The others are omitted. `w.<ui.Job>` and `w.<Closed<string>>` stay available. Asking for a missing shorthand says which explicit arm to write. `types = R` is installed by Waitable, not by `$named`.

```dewy
Waitable = <R> [
    $named[the unique alternatives...]...
    types = R
]
```

`Channel<string>` has `.string` and `.Closed`. `Channel<Job>` has `.Job` and `.Closed`. `Waitable<ui.Job | net.Job>` has no `.Job`. An outcome whose name is `types` does not get a shorthand. `heart.types` stays the union.

## `types`

In an eligible match, `x:heart.types` is anything from heart. `heart.types & (Tick | Closed)` is `heart.Tick | heart.Closed`. The grouped arm writes the same match. The other name that readers accepted is `outcomes`.

## Clash

An ordinary read keeps the existing member, whether that member is an `int64` or a type. At the declaration or the instantiation, warn that the outcome shorthand was not added, and name both. A source pattern that has two meanings is an error and offers `heart.<Tick>`. The check uses the outcome-name set and the record's members. A later field winning a spread is not this check. That spread rule is only for a record the user wrote, as in program 20.

The other rule: the existing member wins for the pattern too, and the only signal is the warning. An upgrade can turn a source arm into a plain arm without a coverage error. A clean build uses the same rule either way.

## Control and race

`channel<T>` is rejected when `T` overlaps `Closed` or `Canceled`. That ban is not applied to ordinary function results. Payload `Timeout` is the overlap that remains. Inside the direct match the payload has the wait's source and the call-level `Timeout` has none. `<box.Timeout>` matches the payload. `<Timeout>` matches both. `or_throw<Timeout>` forwards both. A stored result has no source, so the distinction is gone.

`race` returns the first completed result, including a `Canceled` that the winning function returned as a value. Losers are canceled. Their `Canceled` is discarded. The race call's own `Canceled` has no source. A tie has no promised order. A losing receive takes nothing.

`first_ok` treats an exception result as a failure. A `Canceled` returned as a value is a failure too. The first result that is neither is the success. When every result is a failure, the one that finished first is returned, with no promised tie order. The call's own `Canceled` is not one of those results.

Select's `priority` is a different rule. `'fair'` and `'listed'`, a past `MonoPoint`, and a `0s` poll are unchanged. A relative timeout restarts each call. Nothing is remembered across calls.

`merged([])`, and a `merged` of an array that is empty at run time, finishes immediately with `open` false. A `select` with no wait is the obligation "select needs a wait". Known empty is a compile error. A length that is not known is that obligation under the existing settings: a compile error by default, a runtime check under `$runtime_checks`.

`send(timeout=)` is `void | Unsent<T> | Canceled`. `Unsent.reason` is `Timeout` or `Closed`. `.value` is the job. Hover says the job comes back.

## Cost

One index per function, built once: the bindings, the places that overlap them, and the assignments. Each wait consults the index. The walk is linear in the function. A nested `merged` table is one entry per source, charged to that size, looked up once. Obligation facts are the checker's existing work, not a second pass, and not free. No helper summary and no fixpoint. The winner index does not leave the match. No runtime map.

The middle-rule comparison is once per instantiation. The commit token is one per registration.

Flagship instruction counts are a landing gate. This round has no measured number. `$no_deadlocks` is unchanged.

## Retracted

Flowing provenance through copies, helpers, and loops. "The earlier argument wins" for a race or `first_ok` tie. The claim that `&` does not intersect unions. The claim that a type member is a reading cost. The claim that a ready source's arm must always turn that source off. The claim that `a.<T>` is legal only on a generic parameter. The claim that `Waitable` fails to compile when two outcomes want one short name. Round 10's recommendation of `named([...])` as the spelling readers should see.
