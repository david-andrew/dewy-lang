# Time, dates and calendars (direction, 2026-10-21)

David's long-term direction for open question 9c. Not urgent; this records the
shape the library should grow toward.

- **One canonical timeline.** Every instant lives on a single monotonic timeline
  anchored at a fixed epoch (e.g. the Unix or Apollo epoch). Consider a
  TAI-like base, so leap seconds live in a layer rather than in the core.
- **Everything else is a layer** indexed off that timeline: timezones (the IANA
  tz database), calendars, country-specific quirks, leap seconds, daylight
  saving time and so on. Layers aren't guaranteed to interoperate in every
  combination, but Dewy strives for maximal coverage of the classic problems
  (see Computerphile, "The Problem with Time & Timezones").
- **Calendar units combine only with dates.** `month` and `year` combine only
  with real dates, never with fixed durations. Fixed durations (seconds, hours,
  …) are ordinary quantities.
