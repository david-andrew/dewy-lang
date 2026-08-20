# Time

Time is a unit, like mass or length. A duration keeps the number you
chose. Unit constants such as `ms` carry an exact scale.

```dewy
const Duration:type = <T of real>(T * Time)

pause = 300ms
nap = 10s
sleep(pause)
```

`ns`, `ms`, and `s` (and the written-out `nanosecond` / `millisecond` /
`second` forms) come from the prelude. Writing a number next to one of
them builds a `Duration`. `sleep` waits for that duration.

Calendar arithmetic, clocks, and conversion among units of time that are
not exact SI scales are covered under [Units](../ch03/units.md).

## Timezones and Calendars

Timezones and calendar systems (Gregorian, Julian, Human Era, and so on)
are not yet determined.
