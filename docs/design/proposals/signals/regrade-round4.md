# Independent regrade: signals round 4

Floor: **3/5 for working selected-design examples**, principally contextual lifetime discoverability, separate-output REPL plumbing, and platform completeness. No remaining must-fixes found. The deliberately unsupported/negative fixtures have completeness 2; they do not lower the working-design floor. These are paper-design grades, not compiled, native-platform, race-detector or performance validation.

Scope: round4.md, summary-final.md, every programs-r4 source and support module; prior regrade-round3 must-fixes and review-round3 M1. Repository read-only. Owned outputs: this report and programs-regrade-r4/. Budget: one bounded independent review session. Acceptance: independent grades, three edge programs, prior-finding disposition, minimal REPL, new must-fixes only. dogfood-round4.md was not read before these grades were written.

## Prior must-fixes

1. **Overlapping-handler liveness: resolved by the permitted qualification and escape, not by making (b) guarantee termination.** round4's opening limit, section 2, programs 26:6–8 and 27:5–14 explicitly show indefinite activity. The 2s/3s handlers and 1.1s arrival trace reproduce the prior counterexample. Program 19:7–15 gives explicit done priority; 28:14–16 races both handlers against sticky closed-channel readiness and joins cancellation. The claim now bounds backlog after closure, not invocations after named work finishes. Cooperative cancellation remains a stated limit.
2. **Escaped registration authority: resolved structurally.** round4 section 1 assigns subscriptions to the executing owner and section 4 revokes them at owner exit independently of aliases. Program 30:3–16 retains an inert descriptor without retaining policy. A background task that actually starts listening installs its own policy; that is a new active subscription, not an escaped old one. Program 31 deliberately exposes the resulting library-policy consequence and recommends passive observation. Forgetting signal cleanup is no longer possible because there is no required cleanup call.
3. **Unexpected facility closure in shutdown examples: resolved.** 02:25 and 03:36 fail on Closed; 11:33–35 exits nonzero without relying on console output. round4 section 1 distinguishes SignalUnavailable from normal Closed, including pending payload then sticky failure. 14:4 and :18–19 use merged retirement to drain normal closure and explicitly fail fast on facility error. Genuine cancellation still forwards.
4. **review-round3 M1, unjustified mandatory acquisition/stop: resolved.** First-use attachment, persistence through handler gaps, stable first-use failure types and automatic scope exit are now the default. Program 32:3–8 is precisely the proposed minimal alternative. Program 24:6–13 makes optional startup ordering with an existing timed operation explicit; 25 adds a real readiness barrier. No claim remains that future code is intercepted before it executes.

## Independent programs and the REPL

programs-regrade-r4/01_owner_repl.dewy preserves David's record, run loop, input/echo and EOF/quit shape. Construction precedes explicit execution: a synchronous constructor cannot publish the instance while its run method is still running. The unused alive field disappears. Lines 6 and 11 are the machinery beyond the sketch: race handles both interrupted reads and between-read source events; the outcome arm prints only after the read loser has joined/reset. Lines 13–15 are visible failure/cancellation handling. This implements round4's required adapter contract, not evidence the adapter exists.

This is the simplest robust event-aware REPL under round 4:

```dewy
import p"@lib/std/signals.dewy" as signals
UnexpectedSignalClose:type = type of error
repl:type = [
    run = () => loop true {
        match race(@input(">>> ") @signals.ctrl_c.next) {
            line:string => {
                if line =? "quit" break
                printl"you said {line}"
            }
            <Interrupted | CtrlC> => printl"KeyboardInterrupt"
            <EndOfInput> => break
            <Closed> => UnexpectedSignalClose or_throw
            <Canceled> => Canceled or_throw
            problem:error => problem or_throw
        }
    }
]
main = () => { let r = repl; r.run() or_throw }
```

A prompt-only version can instead attach once with a timed poll, then handle input's Interrupted directly, but needs startup-outcome handling and has no between-read source-event handler. An unattached input-only loop gets default cancellation, not magically Python-like caught interruption.

**Closest separate-loop version:** programs-r4/01 plus support/repl already supplies it: construct r; create notices and printed; parallel r.run(notices printed) beside `loop _ in notices or_throw { printl"KeyboardInterrupt"; printed.send(true) or_throw }`. EOF/quit closes notices; printer closes acknowledgements on exit. This is as close to the literal two-loop sketch as round4 allows while preserving one interruption message and ordering the next fresh prompt. Its handler receives selected notices rather than raw signals. Keeping a raw-source sibling cannot see the owner's consumed active-read interrupt; inventing a broadcast rule to repair that would change round4.

The race is useful for the full event-aware REPL; **two channels are not necessary for REPL behavior**. They are sufficient explicit coordination for the extra requirement that a separate loop own printing. Presenting that version as the minimal everyday REPL is over-built. Round4 already acknowledges the direct-print alternative, so this is a presentation/concision cost, not a new must-fix. No ordering guarantee applies to unrelated terminal writers or a simultaneous completed line that wins the ordinary race tie.

programs-regrade-r4/02_drain_server.dewy adds two concurrent accept lanes using the supplied protected-request helper. SIGTERM cancels/joins both lanes, closing accepted sockets after their existing request-relative budgets. It has no post-drain write and does not promise a fresh hard five seconds from SIGTERM. Concurrent/cancellation-safe accept remains an explicit library assumption. programs-regrade-r4/03_forgotten_lifetime.dewy omits both acquisition and cleanup and keeps the alias after scope exit: the default is restored. The nearest r3 negative fixture is now ordinary valid design code.

## Grading method and comparisons

O=obvious, D=discoverable, C=concise, S=safe by default, F=complete. Scores compare design friction against Python, Go, Rust, TypeScript and Swift, not executable implementations. Python offers the shortest familiar prompt-only interruption path; the other four generally need console/signal adapter coordination. Go signal channels, Rust streams/select, TypeScript event subscriptions and Swift async/dispatch sources expose listener lifetime more explicitly; Python async listeners also need installation/task cleanup. Dewy's automatic lifetime removes that ceremony but makes scope and current waits affect termination. Across all five, bounded cleanup remains cooperative and platform termination/job control still require platform facilities. A 5 means no material defect found in the stated scenario, not verification of a runtime. Every sub-5 score below has a location and dimension-specific reason. Locations are in programs-r4 unless otherwise stated; M marks machinery beyond the owner's sketch.

| Program | O | D | C | S | F | Every deduction |
|---|---:|---:|---:|---:|---:|---|
| 01 REPL | 4 | 3 | 3 | 5 | 5 | O: support/repl:9,14 unifies two delivery paths. D: :9 depends on inherited race ownership/reset. C: M 01:5–6 and support/repl:16–21,33–36 are message/ack protocol solely for separate ordered printing. |
| 02 search/save | 4 | 4 | 4 | 5 | 4 | O,D: :18 joins canceled search before saving. C: :7–12,20–23 preserve cleanup failures and exit provenance. F: support/search:26–28 relies on proposed durable-path operations. |
| 03 server | 4 | 4 | 4 | 5 | 5 | O,D: :18 must protect inside the canceled race participant; :41–44 distinguish request and shutdown budgets. C: :18–23 explicit bounded drain outcomes. Complete for the stated serial echo-server scenario. |
| 04 game | 4 | 4 | 4 | 5 | 5 | O,D: :4,25–31 real channel lifetime must unblock sender despite signal auto-closure. C: :23–33 bridge and closure protocol. |
| 05 shell | 4 | 4 | 4 | 5 | 4 | O,D: :6,16 race/reset plus :25–27 retained root interception and delayed notification. C: M :6,18 extra signal path/terminal handling. F: :1,11 shared foreground child only, no job control. |
| 06 resize | 4 | 4 | 3 | 5 | 3 | O,D: :5–9 must independently query/parse dimensions after signal. C: :5–12 subprocess/parser for layout. F: :1,5 Linux/TTY/stty dependency. Actual layout calculation now exists. |
| 07 listeners | 4 | 3 | 5 | 5 | 5 | O: :5–6 intercept/passive views differ. D: :8 attachment/readiness versus broadcast needs learning. Complete as explicitly non-barrier example. |
| 08 busy | 4 | 4 | 5 | 5 | 5 | O,D: :6–10 coalescing, final drain and ambient closure require the model. |
| 09 early finish | 4 | 3 | 5 | 5 | 5 | O,D: :8,18 helper return changes sibling source lifetime without explicit done. |
| 10 default CLI | 5 | 5 | 5 | 5 | 5 | No deductions. |
| 11 Windows close | 4 | 4 | 4 | 5 | 3 | O,D: :22,37 scope retains native callback hold beyond race. C: :25–35 explicit best-effort outcome policy. F: :1,25 host may terminate before save; :14–16 proposed durable path dependency. |
| 12 library observer | 4 | 3 | 5 | 5 | 5 | O,D: :7 helper inherits caller owner; a nested parallel changes lifetime. |
| 13 default save | 4 | 4 | 4 | 5 | 4 | O,D: :9 operates with cancellation already pending. C: :9–16 preserve original reason despite save outcomes. F: support/search:26–28 proposed durability dependency. |
| 14 multi-source | 4 | 4 | 4 | 5 | 5 | O,D: :4,18–19 merged tracks retirement while failures abort. C: :4–11 name dispatch for shared payload type. |
| 15 Ctrl-Break | 4 | 4 | 5 | 5 | 4 | O,D: :5 portable descriptor fails on first use where unavailable. F: :1 Windows-only. |
| 16 unsupported guard | 3 | 3 | 4 | 3 | 2 | O,D: :11 looks like ordinary read but would need reactive semantics. C: :12–16 additional terminal plumbing. S: :4,5,11 lacks proposed shared guard synchronization. F: :1,21 explicitly unselected; not working round4. |
| 17 manual next | 4 | 3 | 4 | 5 | 5 | O,D: :8 Closed comes from collective state. C: :8–10 visible terminal arms beyond raw next sketch. |
| 18 race baseline | 5 | 4 | 5 | 5 | 5 | D: :9–10 joins loser mid-handler but root subscription survives until entry exit. |
| 19 done baseline | 5 | 4 | 3 | 5 | 5 | D: :9 priority establishes ready-done precedence. C: M :4,7,9–15 explicit completion protocol. |
| 20 nested sessions | 4 | 3 | 5 | 5 | 5 | O,D: :4–6 copied source gets independent ownership per block, unlike same-owner competing receives. |
| 21 external task | 4 | 3 | 4 | 5 | 5 | O,D: :7–14 app-owned scope and expected child cancellation differ from lexical closure. C: :8,13–14 explicit task stop/join remains necessary. |
| 22 passive default | 4 | 4 | 5 | 5 | 4 | O,D: :5 observes best-effort without suppressing cancellation. F: :5 cannot guarantee final telemetry before root shutdown. |
| 23 dependent report | 3 | 3 | 5 | 5 | 5 | O,D: :10–11 future ordinary report cannot sustain its own signal prerequisite. |
| 24 early attach | 4 | 3 | 3 | 5 | 5 | O,D: :6 zero-time poll is policy attachment, not just checking data. C: M :5–13,15–22 explicit startup dependency/outcomes. |
| 25 ready barrier | 4 | 3 | 3 | 5 | 5 | O,D: :15–17 ownership plus :26–30 readiness versus release. C: M :4–8,20–30 two-party barrier protocol. |
| 26 timer negative | 4 | 3 | 5 | 5 | 2 | O,D: :6–8 timer permanently defeats signal-only closure. F: :1,6 intentionally fails post-work termination; negative fixture. |
| 27 overlapping negative | 3 | 3 | 5 | 5 | 2 | O,D: :7,13–14 overlapping ordinary bodies prevent collective quiescence. F: :1–2 no eventual end under stipulated stream; negative fixture. |
| 28 done/race escape | 4 | 4 | 4 | 5 | 5 | O,D: :15–16 done readiness cancels/joins bodies through owned races. C: M :4–9,12,14 explicit cutoff. |
| 29 boundaries | 3 | 3 | 5 | 5 | 5 | O,D: :6,10,12 tiny scope refactor changes finite listener to immediately closed or indefinite. |
| 30 escaped descriptor | 4 | 4 | 4 | 5 | 5 | O,D: :5,12 alias does not retain authority; executed wait would attach anew. C: :9,15–16 background task still needs stop/join. |
| 31 library policy | 4 | 3 | 5 | 4 | 5 | O,D: :5,9–12 library owner extends process interception. S: :5 suppresses app default via direct library listening; explicit passive mode is required to avoid that policy effect. This is disclosed ambient authority, not leaked ownership. |
| 32 idiom | 4 | 3 | 5 | 5 | 5 | O,D: :5,7–8 first execution attaches and collective frontier closes; neither boundary is plain lexical iteration. |

Support modules are included above: repl in 01; search in 02/13; telemetry in 12/22. Independent 01 scores 4/4/4/5/5: O,D at :6 depend on inherited race/reset rules; C at M :6,11,13–15 is event/error branching beyond input/echo. Independent 02 scores 4/4/4/5/4: O,D at :6–9,14 require canceled-lane joins with protected requests; C at :15–19 is explicit shutdown outcome policy; F at :22 assumes concurrent cancellation-safe accept. Independent 03 scores 4/3/5/5/5: O,D at :6–10 require knowing that scope completion revokes policy despite retained copy.

## New must-fixes

None found. The simplified public lifetime is coherent on paper; contextual closure, startup exposure, library authority, coalescing and platform limits remain visible costs. No request to redesign those policies, no new naming decisions and no implementation approval is implied. Keep the native adapter, console cancellation reset, DAG readiness ordering, routing retirement and flagship instruction-count checks as future implementation obligations.
