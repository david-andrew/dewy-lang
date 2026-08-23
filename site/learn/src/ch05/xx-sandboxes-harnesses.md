# Sandboxes and Harnesses

A sandbox lets you run a program that would touch the outside world, the file system, the network, the clock, without those effects escaping. A harness is the same idea aimed at development. You simulate a dependency that is not written yet, or an operating system you are not running on.

The goal is that the code you test is the code you ship. You do not rewrite calls into mocks by hand. The harness intercepts host actions and answers them.

Typical uses:

- Open a file, send a request, or sleep, and have the harness supply the response
- Develop one page of a larger application against simulated neighbors
- Pretend you are on a different operating system

How you attach a sandbox, a command-line flag, a source declaration, or both, and the default catalog of host actions are not yet determined. The intent is that defaults exist for common actions, and you can override any of them with ordinary Dewy code.

<!-- TODO: likely sandboxes will make use of the effects system for mocking effects to build up the harness -->
