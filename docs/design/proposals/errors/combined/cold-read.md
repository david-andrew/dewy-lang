# Cold read: combining-failures names

Three context-free readers (A, B, C), names shuffled.

```
$origin_at_caller open = (path:Path mode:string) => …
let problems = ErrorList[name_missing email_invalid]
printl("failed at {failure.$location}")
let got = net.tcp_receive(conn) ??<SocketReceiveFailed> none
if result is? ErrorStack<FileCloseFailed> printl"{result.length} files did not close"
file.write_text(row) ??<FileWriteFailed> return
<RollbackFailed> => printl"the transaction could not be undone"
printl("failed at {failure.$where}")
let conn = net.tcp_connect(host port) ??<SocketConnectFailed> return none
tx.commit() ??<CommitFailed> return
printl("failed at {failure.$origin}")
<ProcessStopFailed> => printl"the child process could not be stopped"
let site:SourceLocation = failure.$origin
loop part in failure.$failures printl(part)
let server = net.tcp_listen(8080) ??<SocketListenFailed> return
let status = child.wait ??<ProcessWaitFailed> -1
problems &= age_invalid
let problems = ErrorStack[name_missing email_invalid]
let text = file.read_text ??<FileReadFailed> ""
loop frame in failure.$backtrace printl(frame)
let problems = Errors[name_missing email_invalid]
tx.put(row) ??<QueryFailed> return
<SocketCloseFailed> => printl"the connection did not close cleanly"
$blame_caller open = (path:Path mode:string) => …
$track_caller open = (path:Path mode:string) => …
loop frame in failure.$trace printl(frame)
net.tcp_send(conn data) ??<SocketSendFailed> return
both:FileWriteFailed & FileCloseFailed => printl"the write failed and so did the close"
loop part in failure.$parts printl(part)
```

## Reader A

$origin_at_caller open = (path:Path mode:string) => … | Metatag on `open` that records the call site (the caller’s location) as where any resulting failure originated. | 4
let problems = ErrorList[name_missing email_invalid] | A failure collection type listing named validation errors in declaration order: missing name, then invalid email. | 4
printl("failed at {failure.$location}") | Prints a human-readable failure message using the failure value’s `$location` metafield as the place the error occurred. | 4
let got = net.tcp_receive(conn) ??<SocketReceiveFailed> none | On TCP receive, use `none` if the operation fails with type `SocketReceiveFailed` (receiving bytes on the socket failed). | 5
if result is? ErrorStack<FileCloseFailed> printl"{result.length} files did not close" | `ErrorStack<FileCloseFailed>` is a stack of failures where each entry is a file-close operation that failed; length is how many closes failed. | 4
file.write_text(row) ??<FileWriteFailed> return | If writing text to `file` fails with `FileWriteFailed` (the write operation failed), return from the function. | 5
<RollbackFailed> => printl"the transaction could not be undone" | Match arm for failure type `RollbackFailed`: undoing the transaction (rollback) failed. | 5
printl("failed at {failure.$where}") | Same kind of diagnostic print, but the failure exposes `$where` as the site or context of the failure. | 3
let conn = net.tcp_connect(host port) ??<SocketConnectFailed> return none | Connecting via TCP failed with `SocketConnectFailed` (the connect call failed); then return `none`. | 5
tx.commit() ??<CommitFailed> return | Committing the transaction failed with `CommitFailed` (the commit operation failed); then return. | 5
printl("failed at {failure.$origin}") | Print using `failure.$origin` as the starting point or source location of the failure chain. | 4
<ProcessStopFailed> => printl"the child process could not be stopped" | Handler for `ProcessStopFailed`: stopping the child process failed. | 5
let site:SourceLocation = failure.$origin | Read `$origin` off the failure as a `SourceLocation` (source code position where the failure started). | 4
loop part in failure.$failures printl(part) | Iterate `failure.$failures`, a sequence of sub-failure values or error parts bundled in this failure. | 4
let server = net.tcp_listen(8080) ??<SocketListenFailed> return | Binding/listening on TCP port failed with `SocketListenFailed` (listen failed); then return. | 5
let status = child.wait ??<ProcessWaitFailed> -1 | Waiting on the child process failed with `ProcessWaitFailed`; use `-1` as fallback status. | 5
problems &= age_invalid | Merge the `age_invalid` failure tag into `problems` using `&=` (combine failure sets). | 4
let problems = ErrorStack[name_missing email_invalid] | Stack-ordered collection of the same named errors, most recent or inner failures on top depending on stack semantics. | 3
let text = file.read_text ??<FileReadFailed> "" | Reading file text failed with `FileReadFailed` (read operation failed); use empty string. | 5
loop frame in failure.$backtrace printl(frame) | `$backtrace` is an ordered list of stack frames (calls) leading to the failure, printed oldest-to-newest or similar. | 5
let problems = Errors[name_missing email_invalid] | Another failure-collection spelling for the same named errors—likely an unordered or generic error bag. | 3
tx.put(row) ??<QueryFailed> return | Insert/update via the transaction failed with `QueryFailed` (the database put/query operation failed). | 4
<SocketCloseFailed> => printl"the connection did not close cleanly" | Handler for `SocketCloseFailed`: closing the TCP connection failed or was unclean. | 5
$blame_caller open = (path:Path mode:string) => … | Metatag on `open` attributing responsibility or error reporting to the caller rather than inside `open`. | 3
$track_caller open = (path:Path mode:string) => … | Metatag on `open` that records or tracks caller context (e.g. for diagnostics) when the function runs. | 3
loop frame in failure.$trace printl(frame) | `$trace` is a sequence of trace frames for the failure, similar to a lightweight backtrace. | 4
net.tcp_send(conn data) ??<SocketSendFailed> return | Sending on the socket failed with `SocketSendFailed` (the send operation failed); then return. | 5
both:FileWriteFailed & FileCloseFailed => printl"the write failed and so did the close" | Match when failures combine both types: a write failed and a close failed (paired compound failure). | 4
loop part in failure.$parts printl(part) | `$parts` is an ordered list of pieces making up a composite failure (each `part` is one component). | 4

## Reader B

$origin_at_caller open = (path:Path mode:string) => … | A metatag on `open` saying that the recorded origin of a failure from this function is the call site, not the function body. | confidence 4
let problems = ErrorList[name_missing email_invalid] | A list of failures holding `name_missing` then `email_invalid`, in that listed order. | confidence 4
printl("failed at {failure.$location}") | Prints the source location attached to `failure` (file/line where it was created or attributed). | confidence 4
let got = net.tcp_receive(conn) ??<SocketReceiveFailed> none | If receiving on the TCP connection fails, substitute `none`; `SocketReceiveFailed` is that receive operation failing. | confidence 5
if result is? ErrorStack<FileCloseFailed> printl"{result.length} files did not close" | Checks whether `result` is a stack of close failures; `FileCloseFailed` is closing a file failing, and the stack holds those failures (likely newest last or innermost first) with `.length` counting them. | confidence 4
file.write_text(row) ??<FileWriteFailed> return | If writing text to the file fails, return; `FileWriteFailed` is that write failing. | confidence 5
<RollbackFailed> => printl"the transaction could not be undone" | Match arm for a rollback that failed: undoing/rolling back the transaction did not succeed. | confidence 5
printl("failed at {failure.$where}") | Prints where the failure is attributed (a place or source site stored on the failure). | confidence 4
let conn = net.tcp_connect(host port) ??<SocketConnectFailed> return none | If connecting the TCP socket fails, return `none`; `SocketConnectFailed` is that connect failing. | confidence 5
tx.commit() ??<CommitFailed> return | If committing the transaction fails, return; `CommitFailed` is that commit failing. | confidence 5
printl("failed at {failure.$origin}") | Prints the origin attached to the failure (where it started or whom it is attributed to). | confidence 4
<ProcessStopFailed> => printl"the child process could not be stopped" | Match arm for stopping a process failing: the stop/kill of `child` did not succeed. | confidence 5
let site:SourceLocation = failure.$origin | Reads `$origin` as a `SourceLocation`: the source site recorded as the failure’s origin. | confidence 5
loop part in failure.$failures printl(part) | Iterates the failures collected inside this failure (component or nested failures), printing each. | confidence 4
let server = net.tcp_listen(8080) ??<SocketListenFailed> return | If listening on the TCP port fails, return; `SocketListenFailed` is that listen failing. | confidence 5
let status = child.wait ??<ProcessWaitFailed> -1 | If waiting for the child process fails, use `-1`; `ProcessWaitFailed` is that wait failing. | confidence 5
problems &= age_invalid | Combines `problems` with the `age_invalid` failure (appends or merges it into the collection). | confidence 4
let problems = ErrorStack[name_missing email_invalid] | A stack of failures holding `name_missing` then `email_invalid` (push order: first listed at the bottom or first). | confidence 3
let text = file.read_text ??<FileReadFailed> "" | If reading the file as text fails, use `""`; `FileReadFailed` is that read failing. | confidence 5
loop frame in failure.$backtrace printl(frame) | Iterates a call-stack backtrace stored on the failure, printing each frame. | confidence 5
let problems = Errors[name_missing email_invalid] | A collection of failures holding `name_missing` then `email_invalid`, in that listed order. | confidence 4
tx.put(row) ??<QueryFailed> return | If putting the row through the transaction/query fails, return; `QueryFailed` is that query/put failing. | confidence 5
<SocketCloseFailed> => printl"the connection did not close cleanly" | Match arm for closing a socket/connection failing. | confidence 5
$blame_caller open = (path:Path mode:string) => … | A metatag on `open` saying failures from this function are blamed on the caller (the call site is at fault). | confidence 4
$track_caller open = (path:Path mode:string) => … | A metatag on `open` saying the caller is recorded/tracked on failures from this function (caller appears in the failure’s location or trace). | confidence 4
loop frame in failure.$trace printl(frame) | Iterates a stack trace stored on the failure, printing each frame. | confidence 5
net.tcp_send(conn data) ??<SocketSendFailed> return | If sending on the TCP connection fails, return; `SocketSendFailed` is that send failing. | confidence 5
both:FileWriteFailed & FileCloseFailed => printl"the write failed and so did the close" | Match arm for the combined failure of a file write and a file close, bound as `both`. | confidence 5
loop part in failure.$parts printl(part) | Iterates the parts of a combined failure (the individual failures that were `&`-joined), printing each. | confidence 4

## Reader C

$origin_at_caller open = (path:Path mode:string) => … | a metatag on open: a failure from open is reported at the location of the call that invoked open, not inside open | 3
let problems = ErrorList[name_missing email_invalid] | a list of two failures, name_missing then email_invalid, kept in the order written | 3
printl("failed at {failure.$location}") | prints the place in the code where the failure happened, interpolated into the text | 4
let got = net.tcp_receive(conn) ??<SocketReceiveFailed> none | got is the received data, or none if the receive operation failed with SocketReceiveFailed | 5
if result is? ErrorStack<FileCloseFailed> printl"{result.length} files did not close" | true when result is a stack of FileCloseFailed failures; then prints how many files failed to close | 3
file.write_text(row) ??<FileWriteFailed> return | if writing row fails with FileWriteFailed, the enclosing function returns early | 5
<RollbackFailed> => printl"the transaction could not be undone" | match arm: taken when the failure is RollbackFailed, the operation that undoes a transaction | 5
printl("failed at {failure.$where}") | prints the place where the failure happened, probably the same as $location | 3
let conn = net.tcp_connect(host port) ??<SocketConnectFailed> return none | if connecting fails with SocketConnectFailed, the function returns none and conn is not set | 4
tx.commit() ??<CommitFailed> return | if committing the transaction fails with CommitFailed, the enclosing function returns early | 5
printl("failed at {failure.$origin}") | prints where the failure originally started, interpolated into the text | 4
<ProcessStopFailed> => printl"the child process could not be stopped" | match arm: taken when the failure is ProcessStopFailed, the operation that stops a child process | 5
let site:SourceLocation = failure.$origin | binds the failure's origin to site, typed as a SourceLocation | 4
loop part in failure.$failures printl(part) | goes through the individual failures that were combined into this failure, in the order they were combined | 3
let server = net.tcp_listen(8080) ??<SocketListenFailed> return | if listening on port 8080 fails with SocketListenFailed, the enclosing function returns early | 5
let status = child.wait ??<ProcessWaitFailed> -1 | status is the child's result, or -1 if waiting on the child failed with ProcessWaitFailed | 5
problems &= age_invalid | adds the age_invalid failure to the combined problems | 3
let problems = ErrorStack[name_missing email_invalid] | a stack of two failures; the order written is probably bottom to top, so email_invalid is the most recent | 3
let text = file.read_text ??<FileReadFailed> "" | text is the file's contents, or an empty string if reading failed with FileReadFailed | 5
loop frame in failure.$backtrace printl(frame) | goes through the call frames that led to the failure, printing each one | 4
let problems = Errors[name_missing email_invalid] | a collection of two failures, name_missing and email_invalid, in the order written | 3
tx.put(row) ??<QueryFailed> return | if putting row into the transaction fails with QueryFailed, the enclosing function returns early | 5
<SocketCloseFailed> => printl"the connection did not close cleanly" | match arm: taken when the failure is SocketCloseFailed, the operation that closes a socket | 5
$blame_caller open = (path:Path mode:string) => … | a metatag on open: failures from open are attributed to the caller rather than to open itself | 2
$track_caller open = (path:Path mode:string) => … | a metatag on open: the failure records the chain of callers that led to it | 3
loop frame in failure.$trace printl(frame) | goes through the trace of frames the failure passed through, printing each one | 4
net.tcp_send(conn data) ??<SocketSendFailed> return | if sending data fails with SocketSendFailed, the enclosing function returns early | 5
both:FileWriteFailed & FileCloseFailed => printl"the write failed and so did the close" | match arm: taken when a failure is both a FileWriteFailed and a FileCloseFailed, bound to the name both | 4
loop part in failure.$parts printl(part) | goes through the parts of the failure, the individual failures it combines, in order | 3
