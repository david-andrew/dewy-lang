# Security

Software security should be one of the core features Dewy is aiming to solve. It should be difficult if not impossible to write insecure programs granted they make use of the security primitives provided by Dewy.

Other languages like Rust have made great progress in eliminating whole classes of security vulnerabilities (namely memory safety), but there still remains a whole class of logical errors that can make systems insecure.

E.g. [Low Level | Massive apple hack](https://www.youtube.com/watch?v=PNWABi6Dcl8)

One idea towards dealing with this: [Logan Smith | How to write the perfect function](https://youtu.be/2OMRWPOSw9s?si=Msbvd6vbckxM7VD6&t=1753)

- make use of types to carry at compile time the proof that some thing is true rather than just imperatively programming the functionality

```dewy
# ensure that A is always called before B
let A = ():>ProofThatYouCalledA => ...
let B = <ProofThatYouCalledA> :> ActualThingWeWant => ...

# literelly can't call B without calling A first
proofA = A()
result = B(proofA)
```

This doesn't automatically ensure logic-bug free code, but with a suitable designed base system, it can ensure anything built on top is logic-bug free wherever it would be dangerous.

e.g. DewyOS should build access types that are required for the various effectful things on the OS (read/write files, network access, etc. etc.). Higher level programs making use of that functionality have to prove they have access to do the effect, and thus must pass in proof of access. the compiler guarantees that the access is valid, and so no code paths can do some effectful thing without showing it has access. Good design of the base system (e.g. DewyOS, or etc. context) guarantees that consumers remain safe even if the consumers are written by lay programmers--it would be impossible for them to compile a program that could both access the resources without the access being allowed

Just a highly simplified sketch (a real system would be more comprehensive)

```dewy
let StartScreenShare = <Permissions<CanScreenShare>> :> ScreenShare => ...
```

> note this sketch is assuming `StartScreenShare` _is_ the lowest OS function you hit, and therefore the `Permission<CanScreenShare>` is not used internally by the function. But a higher level library function implementing the capability _would_ need to name and thread the permission down to the OS maintaining the requirement

## Random Security design ideas

The language should be secure by default and users have to opt in (usually with long obnoxious flags) to unsecure execution

TODO in general memory safety is a given but other areas not handled by rust are important to consider:

- https://www.horizon3.ai/attack-research/attack-blogs/analysis-of-2023s-known-exploited-vulnerabilities/
- https://owasp.org/www-project-top-ten/
- https://www.ibm.com/reports/threat-intelligence
- jonathan blow on mitigating buffer overflow risks: https://www.youtube.com/watch?v=EJRdXxS_jqo
- on qmail's strong security record: https://blog.acolyer.org/2018/01/17/some-thoughts-on-security-after-ten-years-of-qmail-1-0/
  - high level idea is reduce amount of trusted code, trade speed for security within trusted code, etc.

TODO: any other logical errors that come up, note them here. Basically we need to treat this the same way airplane crash investigations are handled (Root Cause Analysis / Safety Management System). Collect basically all case studies of known security vulnerabilities, categorize them by their root cause/flavor, and then adjust OS design, and language security features to mitigate them.

Logical errors that we can help with:

- https://www.youtube.com/watch?v=CDtIS8XaJDY
  - basically I think the OS should know what things are trusted vs untrusted, and then perhaps there are libraries that when interacting with the OS (e.g. getting environment variables) that hooks into the security model for the language, and you would get a compile time security error if you tried to do something like use environment variables in a context marked as privileged. note that the security checker would probably be compile-time running code
  - I think in general, having a good model of trusted vs untrusted side effects (inputs), and a good security model in the language where you can mark sections as privileged. For example I think the type system will already have a good notion of what is internal vs external (e.g. for being able to determine what can be precomputed vs what touches non-deterministic/external input). So I think having hooks into that kind of internal vs external source information should be a solid part of the security structure

- e.g. Go's secret mode: https://www.youtube.com/watch?v=GhYpMFRiw34
