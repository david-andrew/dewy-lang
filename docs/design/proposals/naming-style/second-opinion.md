# Identifier style

**BLUF:** Snake_case for every multi-word name (`starts_with`, `is_file`, `has_key`, `remove_prefix`). Julia-style smushing wins on a handful of short predicates and loses as soon as a name has a real word boundary. No hybrid is both mechanical and readable. I would not follow the Julia lean.

## What Dewy does today

- The public surface is already snake_case: `is_file`, `is_empty`, `is_absolute`, `is_alpha`, `read_text`, `write_bytes`, `with_suffix`, `remove_prefix`, `trim_start`, `make_directory`, `index_of`, `to_int`, `time_of_day`, `min_by`, `byte_slice`.
- The smushed pair is `startswith` / `endswith`, in the same paragraph of the language guide as `remove_prefix` and `trim_start`.
- One-word names stay one word (`find`, `trim`, `split`, `has`, `walk`). A few Unix loans stay Unix (`mkdir`, `chmod`, `rfind`).
- The mix is already an orthogonality leak: method `is_dir` beside function `is_directory`, `mkdir` beside `make_directory`, and a habit entry that exists only because people type `ends_with`.

## Case for smushing

- A function name is one token. `text.startswith(prefix)` has no seam. Beside space-separated arguments, an underscore looks like a second kind of space.
- `isfile`, `isempty`, `haskey`, `startswith`, `isdigit` are already familiar from Python string methods, the shell, and Julia. There the underscore is pure tax.
- Formulas stay denser: `isapprox`, `findall`, `eachindex` sit more quietly than `is_approx`, `find_all`, `each_index`. The names people type most are the short ones, so the smoothness lands where the keystrokes are.

## What goes wrong with smushing

- "Join words when the result is readable" is a taste vote. `startswith` is obvious. These are not, and reasonable people split them differently:
  - `removeprefix` / `remove_prefix` / `strippprefix`
  - `withsuffix` (fine) vs `byteslice` (reads as "byte lice")
  - `timeofday` vs `time_of_day` (the `of` vanishes)
  - `runsilent`, `listdirectory`, `indexof`, `offsetat`, `setpermissions`, `inzone`
- Julia's own library shows the rule breaking: `startswith` and `isfile`, then `unsafe_load`, `pointer_from_objref`, `get_zero_subnormals`. The escape hatch is the entire problem. Dewy's time names (`zone_parse`, `zoned_text_error`, `day_add_error`, `local_days`) are readable because the underscores are there.
- Joins invent false words: `toint`, `tofloat`, `offsetat`, `inzone`, `byteslice`, `runsilent`. A reader who does not already know the phrase cannot segment a smash. An underscore is a pause.
- Snake_case is an algorithm: say the English, lowercase it, put `_` at the spaces. Smushing needs autocomplete or a correcting habit. Dewy already has that habit for this one pair.
- `is_` lists every predicate. `isfile` does not find `isdir` or `is_absolute`. And the readable smash is often a clip, not a join: people remember `listdir`, not `listdirectory`. Two hidden choices per name.

## Case for snake_case

- One rule, applied the same way by two people on two days. `starts with` → `starts_with`. `is file` → `is_file`. `time of day` → `time_of_day`. `max exact int` → `max_exact_int`. No meeting.
- The cost is one column on the short names and a real gain on the long ones. `is_file` vs `isfile` is nothing. `set_permissions` vs `setpermissions` is reading versus decoding.
- It finishes the library already shipped. The migration is `starts_with` and `ends_with`, not a rename of `read_text` and `with_suffix`.
- It is the Python of pathlib and the modern stdlib. Rust's `starts_with` and Go's `HasPrefix` mark the same boundary in different letters.
- Single words stay single; `find` never becomes `find_`. The separator is one character, used the same way everywhere, including names with `of`, `to`, or `at`.

## Can a hybrid be crisp enough to guess?

- **Closed list** (`isempty`, `isfile`, `haskey`, `startswith`, and nothing else). Crisp for the compiler. Opaque for people. Nobody memorizes the list; they invent a theory of it and miss. `remove_prefix` staying split while `startswith` joins is the theory, and it is unjustified.
- **Julia's published rule** ("underscore only when hard to read"). Not crisp. "Hard" has no test. The stdlib evidence is a split vocabulary.
- **Two words join, three or more split.** Crisp, and still wrong. Word count forces `byteslice`, `runsilent`, `indexof`, `listdirectory`, `offsetat`, `copyto`. Readability is not a function of word count. `alnum`, `json`, and `dir` also make "how many words is this?" its own judgment (`isalnum` vs `is_alnum`, `tojson` vs `to_json`).
- **`is`/`has` glue onto one real word.** `absolute` is one word, so the rule demands `isabsolute`, which readers write `is_absolute`. `alnum` is not a word, so it flips back to `is_alnum`. Crisp until the second prefix.

The only hybrid that stays both crisp and readable is snake_case plus a written list of one-word loans (`mkdir`, `chmod`), each with no snake twin. That is a loanword list, not a second style.

## Pick

Snake_case, including `starts_with` and `ends_with`. `startswith` is the best advertisement smushing will ever have, and a language cannot be designed around its best special case.

The spelling to optimize is the one typed on the first try, before any docs and before autocomplete: English words, `_` at the spaces. Keep genuine one-word names as one word. Decide `mkdir` / `chmod` / `rfind` as a short loan list or spell them out (`make_directory`, `set_permissions`, `find_last`); do not let them set the policy for every other name.
