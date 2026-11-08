# snake_case or Julia-style joined names for Dewy?

Research note, 2026-11-07. Nothing in the repo was changed.

## BLUF

- **Recommendation: snake_case**, with one rule for what counts as a word (below) and a compiler hint that ignores separators. In Julia style, each name needs its own judgment call. Julia couldn't make that rule crisp in 13 years, and in March 2025 its own style guide [switched to recommending snake_case for packages](https://github.com/JuliaLang/julia/pull/57577).
- **Dewy is already snake_case in practice.** About 300 multi-word names use underscores and about 12 are joined. The joined ones are the most visible names (`startswith`, `endswith`, `rfind`, `printl`). Snake_case means about 10 renames, most of them already proposed in open decision D10 Q3/Q7. Julia style would mean 120+ library renames plus metatags, keyword arguments and literal-union members.
- **The evidence is thin but points one way.** Controlled studies compare camelCase with underscores, never joined lowercase. Visible word boundaries matter more as names get longer: in an eye-tracking study, 3-word camelCase phrases took 1.8 s longer to find than underscored ones, with almost no gap at 2 words. Removing spaces from prose roughly halves reading speed. I found no study supporting run-together identifiers.
- **Julia style's real advantage is familiarity on about 10 famous names** (`startswith`, `isinstance`-style, `readline`). The compiler's habit hints already cover those: `startswith` → "write `starts_with`".
- **To test it:** the guessability kit is in this folder (section 5). My prediction, which is untested: the snake brief gets more exact matches, and the gap is widest on 3+ word names.

## 1. Inventory: what Dewy uses today

Method: `inventory/extract.py` pulls public top-level definitions from the 35 `lib/**/*.dewy` files and identifiers from LANGUAGE.md's code spans. A dictionary pass flags joined compounds, and I checked the flagged ones by hand. Raw output is in `inventory/raw.tsv`.

| Source | Underscored | Single word | Joined compound |
|---|---|---|---|
| `lib/**/*.dewy` public names | 121 | 141 | 1 (`divmod`) |
| LANGUAGE.md identifiers | 182 | ~826 | ~12 Dewy-owned (below) |
| Metatags (`$…`) | 23 (`$no_hidden_costs`, `$runtime_checks`, `$warn_if`…) | 31 | 1 (`$realtime`) |
| Literal-union members | `'nearest_even'`, `'toward_zero'`, `'nearest_away'`, `'preserve_displacement'` | — | 0 |
| Keyword arguments | `max_digits=`, `allow_nonfinite=`, `new_group=` | — | 0 |

- **Dewy-owned joined names:**
  - `startswith`, `endswith`, `rfind`, `printl`;
  - `mkdir`, `rmdir`, `chmod`, `unlink` (path methods);
  - `divmod`, `hypot`, `linspace`, `polyline`;
  - `totaldict` (a type);
  - `$realtime`.
- **Foreign names quoted in the docs, which are not Dewy's to rename:** `getenv`, `getpid`, `strlen`, `qsort` (C FFI); `setdefault`, `newaxis` (Python and NumPy references).
- **Inconsistencies:**
  - **The string-ends family mixes both styles:** `startswith`/`endswith` sit next to `remove_prefix`/`remove_suffix`, `trim_start`/`trim_end` and `pad_start`/`pad_end`/`pad_center`.
  - **The compiler disagrees with itself:**
    - `"abc".starts_with("a")` is an error, "write `x.startswith(...)`" (`compiler/expr.jo:4146`).
    - The compiler's own effect table spells it `starts_with` (`compiler/effect_classifiers.dewy:80`).
    - The Sloppy habit table maps `startswith` → `starts_with` (`compiler/habits.dewy:232`).
  - **Finding:** `rfind` sits next to `find_all` and `index_of`, and next to the proposed `find_last`.
  - **Line I/O:** `printl` sits next to `read_line`, `input_int` and `input_float`.
  - **Paths (LANGUAGE.md:3813–3848):**
    - The method forms are `mkdir`, `rmdir`, `chmod`, `unlink`, `is_dir`, `make_dirs` and `exists`.
    - The function forms are `make_directory`, `remove_directory`, `is_directory`, `list_directory`, `remove_file` and `file_exists`.
    - The two forms disagree on both separators and abbreviation.
  - **Time:** `weekday` (a closed English compound) sits next to `time_of_day`, `days_of_week`, `days_in_month`, `weekday_name`, `month_name` and `strict_today`. All of these are consistent under a "what English writes as one word" rule. Julia style gives `timeofday`, `daysofweek`, `stricttoday`.
  - **Types:** `totaldict` is a joined lowercase type; the other builtins are single words (`int64`, `string`, `array`) and user types are CamelCase (`AmbiguousToday`).
- **Already in flight:** open decision D10 Q3 proposes `starts_with`/`ends_with` and `set_permissions` in place of `startswith`/`endswith` and `chmod`, marked "read fine". D10 Q7 adds `find_last`, `make_dir` and `remove_dir`. Your instinct shows in the most visible names, but the rest of the library has gone snake_case.

## 2. Prior art

- **Julia**
  - *What the guide said until 2025* (v1.10 manual): functions are "lowercase … and, when readable, with multiple words squashed together (`isequal`, `haskey`). When necessary, use underscores as word separators. Underscores are also used to indicate a combination of concepts (`remotecall_fetch`) or as modifiers."
  - *What it says now* (master, since [PR #57577](https://github.com/JuliaLang/julia/pull/57577), merged 2025-03-25): "Function names should be written in snake case (`minimum`, `count_zeros`, `escape_string`). Base often breaks this convention by squashing words together (`splitpath`, `readeach`) but this style is not recommended for packages."
    - The PR author on Base's underscores: "I don't think we have a particularly principled way."
  - *History:*
    - **2012–13 ([#1539](https://github.com/JuliaLang/julia/issues/1539)):** Bezanson removed underscores from `begins_with`, `ends_with`, `parse_int` and `parse_float`: "Any underscore removal is usually good." Trailing `?` predicates were proposed and rejected because `?` was taken by the ternary operator.
    - **2017–18 ([#20402](https://github.com/JuliaLang/julia/issues/20402)):** renamed `method_exists`→`hasmethod`, `object_id`→`objectid`, `nb_available`→`bytesavailable` and `print_with_color`→`printstyled`.
      - Kept `unsafe_*`, because the underscore marks danger.
      - Left `count_ones`/`leading_zeros` unresolved.
      - Karpinski: "we should strive to eliminate all names where underscores are necessary."
  - *In practice, Base mixes both:*
    - `count_ones` next to `countlines`;
    - `leading_zeros` and `escape_string` next to `lastindex`;
    - `require_one_based_indexing` next to `searchsortedfirst`;
    - long joined names such as `lastdayofmonth`, `daysofweekinmonth`, `dayofweekofmonth` and `uppercasefirst`.
  - *Complaints:*
    - ["Recommended style guide for naming functions is not practical"](https://discourse.julialang.org/t/recommended-style-guide-for-naming-functions-is-not-practical/21206) (2019): "when readable" is subjective, so no checker can enforce it.
    - ["The current state of function naming style"](https://discourse.julialang.org/t/the-current-state-of-function-naming-style/136849) (2026):
      - One user calls squashing "probably the worst style decisions that ever made it into Julia".
      - The SciML style guide uses snake_case.
      - Others say Base keeps squashing on purpose, because long Base names are a smell.
- **Python**
  - *The rule:* PEP 8 says lowercase, "with words separated by underscores as necessary to improve readability". "As necessary" is the same kind of judgment call as Julia's "when readable".
  - *Legacy names:* `startswith`, `isinstance`, `getattr` and `isdigit` predate PEP 8. Newer modules use snake_case: pathlib's `is_file`, `read_text`, `with_suffix`; asyncio's `create_task`.
  - *Local consistency wins:* [PEP 616](https://peps.python.org/pep-0616/) (2020) rejected `remove_prefix` because "All of the other methods of the string API, e.g. `str.startswith()`, use `lowercase`". `math.isclose` and `math.isqrt` were joined to match `math`.
  - *Lesson for Dewy:* a joined family perpetuates itself. If `startswith` stays, `removeprefix` follows.
- **Go**
  - *The rule:* MixedCaps with no underscores ("Effective Go"). Word boundaries are visible through case.
  - *Judgment calls remain:* `HasPrefix`, `ReadFile`, `ToUpper`, but also `MkdirAll` (POSIX legacy inside camelCase) and initialisms (`ServeHTTP`).
- **Rust**
  - *The rule:* snake_case for functions ([RFC 430](https://rust-lang.github.io/rfcs/0430-finalizing-naming-conventions.html)), enforced by the `non_snake_case` lint.
  - *Words are still a judgment, but a smaller one:* `to_uppercase` treats "uppercase" as one word; `file_name`, `read_line`, `starts_with`, `contains_key`.
  - *No POSIX abbreviations:* `create_dir`, `remove_dir_all`.
  - *Relevance:* the closest model for Dewy.
- **Nim**
  - *The rule:* identifiers are style-insensitive. Apart from the first letter, case and underscores are ignored, so `startsWith` is the same identifier as `starts_with` ([manual](https://nim-lang.org/docs/manual.html#lexical-analysis-identifier-equality)).
  - *What it gains:* nobody has to guess the spelling when writing.
  - *What it costs:*
    - one codebase can spell a name three ways;
    - plain-text search breaks;
    - `--styleCheck` exists because of this.
  - *Verdict:* worth borrowing for diagnostics only (section 6).
- **Swift**
  - *The rule:* lowerCamelCase, with booleans that read as assertions: `isEmpty`, `hasPrefix`, `uppercased()` ([API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/)).
  - *Relevance:* clarity at the point of use, not brevity.
- **R**
  - *The rule:* base R has none: `read.csv`, `is.na`, `nchar`, `Sys.time`.
  - *Evidence:* [Bååth 2012](https://journal.r-project.org/articles/RJ-2012-018/index.html) documented the mix across CRAN.
  - *Outcome:* the tidyverse standardized on snake_case (`read_csv`, `str_detect`).
  - *Lesson for Dewy:* a mix is the worst outcome.
- **Ruby**
  - *The rule:* snake_case plus `?` predicates (`empty?`, `start_with?`, `key?`) and `!` for danger.
  - *Fit for Dewy:* `?` isn't available for names here, because Dewy already uses it for optional types (`string?`) and question operators (`is?`, `in?`, `=?`). Dewy's operators already make `?` its predicate marker. Names don't need one.

## 3. Evidence on readability

- **Binkley et al. 2009 ([ICPC](https://doi.org/10.1109/ICPC.2009.5090039)) and the journal family of five studies ([EMSE 2013](https://doi.org/10.1007/s10664-012-9201-4)).**
  - *Participants:* 150 in total: 135 Loyola students including non-programmers, a subset of 19, and 15 Kent programmers.
  - *Phrase-matching task* (pick the identifier for a phrase among distractors):
    - camelCase was more accurate: 89% vs 84% (odds ratio 1.5);
    - it was also slower: 3.5 s vs 3.1 s, or 13.5% longer.
  - *Eye tracking* (15 programmers, mostly trained in underscores):
    - camelCase took 0.93 s longer on average;
    - there was almost no difference for 2-word phrases;
    - **3-word phrases took 1.8 s longer.**
  - *Authors' conclusion:* experienced developers are less affected; beginners benefit from camelCase in accuracy and effort.
- **Sharif & Maletic 2010 ([ICPC](https://doi.org/10.1109/ICPC.2010.41)):** an eye-tracking replication with 15 subjects. Accuracy was the same; underscores were recognized faster and with lower visual effort.
- **Run-together lowercase (`readline`):** I found **no controlled study** of joined identifiers. The nearest proxies:
  - **Rayner, Fischer & Pollatsek 1998** ([Vision Research](https://doi.org/10.1016/S0042-6989(97)00274-5)): removing the spaces from English prose cut reading rate by about 50% and disturbed where the eyes landed.
    - This is a weak proxy: identifiers are short, and famous ones (`readline`) are read as single units.
    - The direction still holds: boundaries help, and they help more as words accumulate.
  - **Identifier-splitting research** (Enslen et al. 2009 "Samurai"; [Hill et al. 2014](https://www.eecis.udel.edu/~pollock/879tainsef13/idsplittjournal.pdf)):
    - tools split `_` and case boundaries mechanically ("hard words");
    - same-case joined names need dictionaries and frequency tables, and still mis-split.
    - Machines find joined names ambiguous too, and search, completion and spell-checking all depend on splitting.
- **Abbreviation is a separate axis:** [Hofmeister et al. 2017](https://www.se.cs.uni-saarland.de/publications/docs/HoSeHo17.pdf) found that full-word names led to faster defect-finding than abbreviations or single letters. That bears on `printl`, `chmod` and `dir`, not on separators.
- **How strong is all this?**
  - small samples, mostly students, from 2009–2013;
  - lab tasks such as finding a phrase in a word cloud;
  - effects under a second for short names.
  - Nothing here proves joined 2-word names are worse. The defensible claim is narrower: **visible boundaries matter more as names get longer**, and no evidence favors removing them.

## 4. The tradeoffs for Dewy

- **Predictability**
  - *Snake_case:* the writer needs one decision, what counts as a word. The answer is mostly settled by English (`weekday`, `uppercase`, `timestamp`); a few cases are fuzzy (`filename` vs `file_name`).
  - *Julia style:* the writer needs that decision plus a second, per name: "is it readable joined?" Julia's own Base answers it inconsistently, as the `count_ones`/`countlines` pair shows.
  - *Recall:* a newcomer can guess `last_day_of_month` mechanically. Remembering whether it was `lastdayofmonth` or `last_dayofmonth` is a lookup.
- **Brevity and typing**
  - *Measured:* across the 27 test names where both keys use the same words, snake_case adds 1.3 underscores per name, or 13% of characters.
  - *Typing cost:* `_` takes a Shift; completion mostly erases the difference.
  - *Brevity elsewhere:* Dewy gains far more brevity from juxtaposition and `?` operators than this would cost.
- **Names of three or more words**
  - *Joined is hard to read:* `nthweekdayofmonth`, `lastdayofmonth`, `searchsortedfirst`, `daysofweekinmonth`.
  - *Julia's own escape hatch is snake_case:* `require_one_based_indexing`.
  - *Dewy has several already, and they keep coming:* `nth_weekday_of_month`, `secure_random_bytes`, `sanitize_file_name`.
- **Ambiguous splits**
  - *Examples:*
    - `hasheader` (has header / hash eader);
    - `useregex` (use regex / user egex);
    - Julia's real `tolast` (to last / tol ast);
    - `isover`, `nowhere` (no where / now here).
  - *Who meets them:* rare in a curated standard library, but users name things too, and they would follow the library's style.
- **Discoverability**
  - *Fuzzy completion (VS Code-style)* gives a bonus at `_` and case humps, so `sw` and `ends` rank `starts_with`/`ends_with` high. In joined names they are plain subsequences, which rank lower.
  - *Docs and search tokenizers* can split snake_case mechanically; joined names need a dictionary.
  - *Mixed conventions are worse than either style:* a wrong guess gets zero search hits.
- **Fit with Dewy's other conventions**
  - *Already snake_case:* metatags (`$prove_no_counter_overflow`, `$no_hidden_costs`), keyword arguments (`max_digits=`), literal unions (`'nearest_even'`), record fields, and every example program's own functions (`make_counter`, `odd_squares`).
  - *What Julia style would force:* either a two-style language (joined functions, underscored everything else) or `$provenocounteroverflow`.
  - *Units are unaffected:* they are single English words (`10minute`, `kilogram`).
  - *Types are a separate axis:* CamelCase for user types; `totaldict` is the odd one out.
- **Hybrid rules**
  - *Julia's own hybrid failed to be crisp:* "when readable", plus underscores "for a combination of concepts", which its own PR removed as inaccurate.
  - *"Join established single concepts (readline, filename)" needs a list:* who decides `readline` is established but `readuntil` isn't?
  - *The only crisp hybrid* is "join exactly when English writes the compound as one word", and that is simply snake_case with a definition of "word". **There is no separate crisp hybrid.** The candidates either collapse into snake_case or come down to a lookup table.
- **The safety net works for both styles.** A separator-insensitive "did you mean" turns every separator-only wrong guess into one compile error that names the fix. It doesn't settle the choice, but it caps the cost of whichever style loses, and it handles Python and Julia habits (`startswith`, `isfile`) for free.

## 5. The guessability test (files in this folder)

- `descriptions.txt`: 30 items, each with an id, a description and a call shape. The mix:
  - famous Python and Julia names (items 1, 2, 15, 19);
  - 3+ word names (25–30);
  - three items where Julia's word choice differs (3 `chopprefix`, 22 `basename`, 24 `mkpath`);
  - one where Julia itself is snake_case (14 `leading_zeros`);
  - three with no Julia function, where the Julia key follows Julia's style guide (28–30).
- `key-snake.tsv` / `key-julia.tsv`: the two canonical keys.
  - The snake key uses Dewy's current or proposed name where one exists, Rust's or Python's otherwise.
  - The Julia key uses Julia's actual name where one exists (Base or Dates).
  - The `words_vs_other_key` column marks the three word-choice items, so separator errors can be scored apart from word errors.
- `brief-snake.md` / `brief-julia.md`: identical apart from the style paragraph.
  - Each paragraph gives three parallel examples that aren't in the test (`is_equal`/`isequal`, `get_index`/`getindex`, `print_styled`/`printstyled`).
  - The Julia brief also says to use Julia's name where Julia has one, which is the honest version of adopting Julia style.
  - Neither brief shows a key.
- `score.py`: `python3 -I score.py key-snake.tsv answers/*.txt`. It reports exact matches, "right words, wrong separator" matches, and the shared-word and word-choice items separately.
- **How to run:**
  - Give each brief to 3 or more fresh readers, with **different readers for each brief**: one reader seeing both contaminates the second.
  - Save the replies as `answers/snake-A.txt` and so on, then score each against its own key.
- **Prediction (not yet tested):**
  - the snake brief scores higher on exact matches;
  - the gap is largest on items 8, 12 and 17–18 and on the 3+ word items 25–30;
  - the Julia brief comes close on the famous names (1, 2, 5, 15, 16, 19, 20);
  - the Julia brief loses the word-choice items unless readers know Julia well.
- **What would change my recommendation:** the Julia brief matching or beating the snake brief on exact matches, including items 25–30.

## 6. Recommendation

**Use snake_case.** The rule a newcomer applies without a table:

1. **Name it in plain English words and put `_` between them:** `starts_with`, `is_file`, `has_key`, `read_line`, `nth_weekday_of_month`.
2. **A word is what English writes as one word:**
   - joined: `weekday`, `uppercase`, `keyword`, `timestamp`, `overflow`, `nonzero`;
   - split: anything English writes open or hyphenated, and anything you're unsure of: `file_name`, `time_zone`, `real_time`.
3. **Don't abbreviate, except for a short closed list** in the language guide:
   - `dir`, `min`, `max`, `len`;
   - math function names as mathematics spells them: `sin`, `atan2`, `hypot`, `divmod`, `linspace`;
   - `printl`.
4. **Predicates read as assertions:** `is_`/`has_`/`can_` followed by the rest, or a third-person verb (`starts_with`, `contains`). Modifier prefixes are words too: `strict_today`, `unsafe_…`, `secure_…`.
5. **Implementation:**
   - the "did you mean" check ignores `_` and case when matching an unknown name to a known one, so `startswith`, `startsWith` and `isFile` each get "write `starts_with`" (or `is_file`);
   - this replaces per-name entries in the habit table;
   - it is an internal mechanism, not new syntax.

Rule 2 leaves a few fuzzy cases (`filename`/`file_name`, `realtime`), which rule 5 catches. Julia style leaves every multi-word name to judgment.

**Renames this implies in today's library:** about 10, most already in D10.

| Today | Under the rule | Already proposed? |
|---|---|---|
| `startswith`, `endswith` | `starts_with`, `ends_with` (and drop the compiler's error at `expr.jo:4146`) | D10 Q3 |
| `rfind` | `find_last` | D10 Q7 |
| path `mkdir`, `rmdir` | `make_dir`, `remove_dir` | D10 Q7 |
| path `chmod` | `set_permissions` | D10 Q3 |
| path `unlink` | `remove_file` (matching the function form) | implied by D10's "one name per operation" |
| `is_directory`, `list_directory`, `make_directory`, `remove_directory` | `is_dir`, `list_dir`, `make_dir`, `remove_dir` (`dir` is on the abbreviation list) | D10 Q7 (partly) |
| `totaldict` | `total_dict`, or CamelCase if it's a library type (type style is a separate question) | no: flag |
| `$realtime` | `$real_time` under rule 2 (English is split between "real-time" and "realtime"); or list it | no: flag, low value |

- **Kept under the rule:**
  - `divmod`, `hypot`, `linspace` (math names);
  - `polyline` (one word in graphics);
  - `printl` (listed);
  - `weekday`, `nonempty`, `nonzero`;
  - every existing underscored name, including `pad_center`, `strict_today`, `days_of_week` and `time_of_day`.
- **Out of scope, but noticed:**
  - `exists` vs `file_exists` and `to_int` vs `int(text)` are word-choice questions, not separator questions; D10 already covers the second.
  - `make_dirs` (plural) next to `make_dir` should get one name.
- **What Julia style would cost instead:**
  - renaming the ~120 underscored library names and 182 underscored identifiers in LANGUAGE.md;
  - either living with two styles (squashed functions next to `$no_hidden_costs` and `max_digits=`), or squashing the metatags and literal unions too.
- **Before this reaches open_decisions.md:** run the kit in section 5. Per AGENTS.md this is a convention change to names you already decided, category (a), and it would need the cold read and a dogfood pass.
