# Cold read: errors

Three readers saw the shuffled usage lines without the proposal. Confidence is on a 1–5 scale. The full lines and original guesses follow; reader labels are A, B and C.

## Lines shown

```dewy
let site:errors.SourceLocation = known_site
loop frame in trace.frames { printl(frame.file) }
printl(site.column)
let trace:errors.ErrorTrace = failure.$trace
$errors.trace = true
printl(site.line)
if trace.status is? 'disabled' printl("trace disabled")
let site = failure.$origin
let site = frame.location
return errors.caused_by(ConfigError["cannot load configuration"] failure)
errors.join(parts.rest...) or_throw
return errors.with_context(failure "loading configuration")
loop handled in parts.matched { errors.report(handled) }
let failure = errors.join(first second)
loop frame in failure.$context { printl(frame.message) }
if trace.status is? 'truncated' printl("trace truncated")
errors.report(failure file=stderr locations=true trace=true)
printl(site.function)
printl(site.file)
loop child in group.errors { errors.report(child) }
if failure is? errors.ErrorGroup errors.report(failure)
loop leaf in errors.leaves(failure) { errors.report(leaf) }
let parts = errors.split<FileError>(failure)
let cause = failure.$cause
if trace.status is? 'unavailable' printl("trace unavailable")
if failure is? errors.ExceptionGroup errors.report(failure)
if trace.status is? 'captured' printl("trace captured")
```

## Reader A

1 | Assigns a known source location value to a variable typed as errors.SourceLocation. | 5
2 | Iterates over stack frames in an error trace and prints each frame's source file path. | 5
3 | Prints the column number of a source location. | 5
4 | Extracts the error trace metatag from a failure value into a typed ErrorTrace variable. | 4
5 | Turns on stack-trace capture for the errors module via a metatag assignment. | 4
6 | Prints the line number of a source location. | 5
7 | If the trace's status is the disabled variant, prints that tracing is disabled. | 5
8 | Binds the failure's origin source location (where it was raised) to site. | 5
9 | Binds a stack frame's source location to site. | 5
10 | Returns a new failure chain linking a configuration load error as the cause of the given failure. | 4
11 | Merges the remaining failure parts into one value and propagates it to the caller if it is a failure. | 4
12 | Returns the failure augmented with a human-readable context string about loading configuration. | 5
13 | Iterates matched failure fragments from a split result and reports each one. | 4
14 | Combines two failures into a single grouped or joined failure value. | 4
15 | Walks contextual messages attached to the failure and prints each context entry's message. | 4
16 | If the trace status indicates it was cut short, prints a truncated notice. | 5
17 | Formats and emits the failure to standard error, including file/line locations and a stack trace. | 5
18 | Prints the function or symbol name from a source location. | 5
19 | Prints the file path from a source location. | 5
20 | Iterates child failures inside an error group and reports each child. | 5
21 | If the value is an ErrorGroup, reports that grouped failure (likely including its children). | 4
22 | Visits every leaf failure in a nested group tree and reports each leaf individually. | 4
23 | Splits a composite failure into parts and types or filters them as FileError-related segments. | 3
24 | Reads the underlying cause failure from a wrapped failure chain via the cause metatag. | 5
25 | If trace capture was not possible, prints that the trace is unavailable. | 5
26 | If the failure is an ExceptionGroup (multiple concurrent errors), reports the whole group. | 4
27 | If the trace was successfully recorded, prints that the trace was captured. | 5

## Reader B

let site:errors.SourceLocation = known_site | Binds `site` as an errors-library source location (file/line/column-like) copied from `known_site`. | confidence 5
loop frame in trace.frames { printl(frame.file) } | Walks the stack frames on a trace and prints each frame's source file path. | confidence 5
printl(site.column) | Prints the column number of that source location. | confidence 5
let trace:errors.ErrorTrace = failure.$trace | Reads the `$trace` metatag on a failure, yielding its captured error/stack trace. | confidence 5
$errors.trace = true | Turns on tracing for the errors library (a process- or compile-wide metatag). | confidence 4
printl(site.line) | Prints the line number of that source location. | confidence 5
if trace.status is? 'disabled' printl("trace disabled") | If the trace's status variant is `disabled`, prints that tracing was off. | confidence 5
let site = failure.$origin | Reads the `$origin` metatag: the source location where the failure was created. | confidence 4
let site = frame.location | Takes the source location recorded on a single stack frame. | confidence 5
return errors.caused_by(ConfigError["cannot load configuration"] failure) | Returns a ConfigError whose message is "cannot load configuration", with `failure` as its cause. | confidence 4
errors.join(parts.rest...) or_throw | Joins the remaining failures from a split into one value; if that join itself fails, passes the failure to the caller. | confidence 3
return errors.with_context(failure "loading configuration") | Returns `failure` with extra context text "loading configuration" attached. | confidence 5
loop handled in parts.matched { errors.report(handled) } | Reports each failure that matched the split filter (the handled subset). | confidence 4
let failure = errors.join(first second) | Combines two failures into one, containing `first` then `second`. | confidence 4
loop frame in failure.$context { printl(frame.message) } | Walks the `$context` metatag (context frames on the failure) and prints each frame's message. | confidence 4
if trace.status is? 'truncated' printl("trace truncated") | If the trace status is `truncated`, prints that the trace was cut short. | confidence 5
errors.report(failure file=stderr locations=true trace=true) | Writes a human report of the failure to stderr, including source locations and the stack trace. | confidence 5
printl(site.function) | Prints the function name of that source location. | confidence 5
printl(site.file) | Prints the file path of that source location. | confidence 5
loop child in group.errors { errors.report(child) } | Reports each child failure stored on an error group, in the group's listed order. | confidence 5
if failure is? errors.ErrorGroup errors.report(failure) | If the failure is an ErrorGroup, reports that grouped failure. | confidence 5
loop leaf in errors.leaves(failure) { errors.report(leaf) } | Walks to the leaf (non-group) failures under `failure` and reports each, in traversal order. | confidence 4
let parts = errors.split<FileError>(failure) | Splits a (possibly grouped) failure into FileError-matching pieces versus the rest. | confidence 4
let cause = failure.$cause | Reads the `$cause` metatag: the prior failure this one was caused by. | confidence 5
if trace.status is? 'unavailable' printl("trace unavailable") | If the trace status is `unavailable`, prints that no trace could be obtained. | confidence 5
if failure is? errors.ExceptionGroup errors.report(failure) | If the failure is an ExceptionGroup, reports that grouped exception. | confidence 4
if trace.status is? 'captured' printl("trace captured") | If the trace status is `captured`, prints that a trace was successfully recorded. | confidence 5

## Reader C

let site:errors.SourceLocation = known_site | binds site to a source location value (file, line, column, function) taken from known_site | 4
loop frame in trace.frames { printl(frame.file) } | walks each frame of the trace and prints its file name | 4
printl(site.column) | prints the column number of the site location | 5
let trace:errors.ErrorTrace = failure.$trace | binds trace to the error trace metatag of failure, the recorded call frames for that failure | 4
$errors.trace = true | turns on error tracing for the errors library via a settings metatag | 3
printl(site.line) | prints the line number of the site location | 5
if trace.status is? 'disabled' printl("trace disabled") | if the trace's status is the value 'disabled', prints that tracing is off | 4
let site = failure.$origin | binds site to the origin metatag of failure, where the failure was first raised, as a location | 4
let site = frame.location | binds site to the location of a single frame, its source position | 4
return errors.caused_by(ConfigError["cannot load configuration"] failure) | returns a new ConfigError with message "cannot load configuration" whose cause is failure | 4
errors.join(parts.rest...) or_throw | joins the spread rest of parts into one group failure; if that fails, passes it up to the caller | 3
return errors.with_context(failure "loading configuration") | returns failure with the note "loading configuration" added as context, without changing its type | 4
loop handled in parts.matched { errors.report(handled) } | for each failure in parts.matched, reports it | 4
let failure = errors.join(first second) | binds failure to a group containing first then second, in that order | 4
loop frame in failure.$context { printl(frame.message) } | walks the context entries attached to failure and prints each message | 4
if trace.status is? 'truncated' printl("trace truncated") | if the trace status is 'truncated', prints that the trace was cut short | 4
errors.report(failure file=stderr locations=true trace=true) | reports failure to stderr with source locations and trace included | 4
printl(site.function) | prints the function name of the site location | 5
printl(site.file) | prints the file name of the site location | 5
loop child in group.errors { errors.report(child) } | reports each member of group's errors list in order | 4
if failure is? errors.ErrorGroup errors.report(failure) | if failure is an ErrorGroup, reports it | 5
loop leaf in errors.leaves(failure) { errors.report(leaf) } | reports each leaf failure, the innermost non-group failures, of failure in order | 4
let parts = errors.split<FileError>(failure) | splits failure into parts that are FileError and the rest, bound as parts | 3
let cause = failure.$cause | binds cause to the cause metatag of failure, the underlying failure that led to it | 4
if trace.status is? 'unavailable' printl("trace unavailable") | if the trace status is 'unavailable', prints that no trace could be recorded | 4
if failure is? errors.ExceptionGroup errors.report(failure) | if failure is an ExceptionGroup, reports it | 4
if trace.status is? 'captured' printl("trace captured") | if the trace status is 'captured', prints that the trace was recorded | 4

## Result and current scope

All 27 lines conveyed their broad role; none of the three readers distinguished ErrorGroup from ExceptionGroup. Round 4 removes ExceptionGroup and keeps one ErrorGroup. This read does not establish precise runtime semantics. The new value-level & / &= combination and recover<E> helper were not included; their cold reads remain outstanding. Trace, cause and advanced split lines are retained here as historical test inputs, not v1 approvals.
