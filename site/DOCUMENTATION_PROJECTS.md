# Future documentation projects

This is the durable queue of examples and case studies intended to stress-test Dewy and eventually become substantive parts of the documentation. Removing a stub from an mdBook summary must not remove its project from this list.

These projects deliberately cover many domains because Dewy is a general-purpose language. STEM examples are represented alongside application, web, systems, media, and infrastructure work.

## “Hello, Many Worlds” quick starts

Each project should eventually become a short, practical “get something working in this domain” guide written from a real Dewy implementation:

- **GUI:** create a window with a click counter.
- **Graphics:** draw a triangle from scratch.
- **Audio:** play a sine wave through the speakers.
- **Networking:** build a simple client/server chat program.
- **2D game development:** make a Flappy Bird-style game.
- **3D game development:** make a small 3D racing game.
- **Web development:** build a simple website.
- **Databases:** create a simple data store.
- **Cryptography:** encrypt and decrypt a string.
- **Operating systems:** run Hello World on bare metal, with Raspberry Pi as one candidate target.
- **Compilers:** build a toy compiler, perhaps a stack-based language in the spirit of a simplified Porth, or a small Dewy/C-like language.
- **Scientific computing:** render an infinitely zooming Mandelbrot set.
- **Robotics:** implement forward and inverse kinematics for a six-degree-of-freedom robot arm using homogeneous transformation matrices.
- **Machine learning:** train a small multilayer perceptron on MNIST.

## Longer case studies

### Dewy compiler

Build a compiler for Dewy in Dewy, covering tokenization, parsing, type checking, code generation, and eventually bootstrapping.

### Asteroid detection and orbit mapping

Create a self-contained pipeline that collects raw Vera C. Rubin Observatory data, identifies near-Earth objects and asteroids, calculates orbital parameters, and presents an animated 3D visualization of their orbits.

### PDF viewer and editor

Build a cross-platform PDF tool from the ground up: rendering, form filling including XFA, handwritten-image and cryptographic signatures, adding and removing content, and saving modified documents. Explore whether a better document format should receive first-class support as a related project.

### dwitter for Dewy

Build a browser experience in which people write small Dewy programs that generate graphics or sound. Consider a roughly one-kilobyte limit and whether size should be based on the AST so whitespace and identifier length are free.

### Dewy Web

Explore an alternative web stack and protocol, inspired by “I Made My Own Web,” potentially paired with Dewy OS.

### DMail

Implement an email protocol and a pleasant inbox experience, including useful notification and assistant-driven organization policies.

### Dewy OS

Build an operating system from the ground up with security primitives designed in, ideally using a fully Dewy-derived toolchain through the trusted-computing-base layers. Candidate hardware includes Raspberry Pi, Framework computers, RISC-V systems, and phones.

## Standard-library explorations

- **Data structures:** queues, graphs, and structures that do not warrant literal syntax.
- **Time:** clocks, calendars, time zones, and exact versus calendar-relative durations.
- **Plotting:** common plots, including ridgeline and Sankey diagrams, plus animation and interactive behavior.
- **Parsing:** grammar-oriented parsing inspired by the turtles library, with possible tree-sitter-compatible parser generation and language-server integration. Preserve the existing CSV grammar sketch in `learn/src/ch04/xx-parsing.md` until this project supersedes it.
- **Parallelism:** work stealing, parallel collection operations, task graphs and futures, later GPU/distributed tiers, and carefully designed low-level synchronization and channel primitives.
- **Sandboxes and harnesses:** convenient restricted execution and test/program harnesses.

## Language-and-library drafts awaiting settled foundations

- **Everyday mathematics:** turn `learn/src/ch03/basic-math.md` into a practical guide once fractional numerics, ordinary juxtaposition multiplication, the core math library, and vectorized operations have settled contracts. The current draft remains source material but is not in the published navigation.
- **Arrays and linear algebra:** turn `learn/src/ch03/linear-algebra.md` into a real walkthrough once multidimensional literal syntax, contiguous shapes, axis selection, broadcasting, and matrix overloads are sufficiently settled. Nested arrays remain covered by the ordinary container chapter in the meantime.

## Promotion criteria

A project should enter the published navigation when it:

1. is backed by a real Dewy program or a sufficiently settled design;
2. teaches a coherent workflow rather than only naming an ambition;
3. states its prerequisites and expected result;
4. distinguishes portable language behavior from platform or library requirements; and
5. has examples classified as compiler-checked, parser-checked, or design-only.
