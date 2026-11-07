# Parallel names: cold-read test

**Method:** the same as `../../bulletproof/names-round1.md`. Three readers with no context guessed each name's meaning from the name alone. These candidates came from proposal v3 and earlier rounds.

| Meaning | Picked | Rejected, and how it was read |
|---|---|---|
| Most items in flight at once | `$parallel.max_concurrent` (3/3, confidence 4) | `$parallel.at_once`: one reader took it as a batch size. `$parallel.in_flight`: vaguer. `$parallel.window`: unsure (round 1) |
| Items per chunk | `$parallel.chunk_size` | `$parallel.chunk`: vague. `$parallel.grain`: read as minimum work |
| Threads for parallel work in a scope | `$parallel.threads` | `$parallel.workers`: also fine |
| Run parallel code in order | `$parallel.off` | `$parallel = false`: read the same, but makes a namespace a value |
| CPU or GPU, and core pinning | `$placement.device`, `$placement.cores` | `$parallel.device`: also fine, but a device also places data |
| Struct-of-arrays layout | `$memory.layout` | `$storage.layout`: read as field order and alignment |
| Program-wide cores, memory and tasks | `$program.max_cores`, `$program.max_memory`, `$program.max_tasks` | `$limits.cores` and the rest: all three readers took them as per-scope. `$resources.cores`: vague |
| Point where a task stops if canceled (used with `or_throw`) | `check_cancel` | `stop_if_canceled`, `cancel_point`: also clear, but `stop_if_canceled or_throw` says "stop" twice |
| Float sum grouping | `sum(xs grouping='tree')` | `order=`: also clear; "grouping" is what actually changes |
| Fair choice among ready channels | `ties='fair'` | `prefer=`: read the same |
| Anything a loop visits | `Iterable<T>` (confidence 5) | `Loopable<T>` (confidence 3) |
