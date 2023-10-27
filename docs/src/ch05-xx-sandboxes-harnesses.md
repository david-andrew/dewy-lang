# Sandboxes and Harnesses
say you want to simulate running your program to test it, but without it actually having any side effects outside of the program. Sandboxes/Harnesses make this trivial.
(TODO)
- when developing apps that have side effects outside of the program (e.g. file system, web traffic, etc.), sandboxes and harnesses provide a convenient way to test the program without it actually affecting anything outside of the program.
- should probably be some sort of command line argument when running a program. Can also provide code that determines the sandbox/harness response for various actions (e.g. handle what happens when the user tries to open a file, or when the program tries to send a web request, etc.). There should also be good default implementations for all aspects of the sandbox/harness.
- can also harness portions of an application while other aspects have not yet been developed. For example, if you are developing a new page on a large web app, and it itself interacts with parts that aren't implemented, you can create a harness that simulates those aspects as if they were implemented.
- harnesses can simulate different operating systems, etc.

Sandboxes/Harnesses make it so testing code is identical to running in production