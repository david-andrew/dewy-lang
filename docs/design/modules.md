# Import cycles

Decision #140: modules may import each other in cycles. The rule is "as if
everything were one big file": a program that works as one file keeps working
when it is split into modules, for declarations and module-level code alike.
The only errors are the ones one file would also have.

## Names

Every module of the program is loaded and its declarations registered before
any import binds a name, so a cycle needs nothing special: `import`, `from …
import` and splat imports bind against the full declaration tables of the
modules they name, wherever those sit in the cycle. A splat import never passes
on the other module's own imports, so two modules splatting each other see only
each other's declarations. Sloppy (`.jo`) and Dewy modules mix freely.

## Checking

Checking is demand-driven, as in one file: a function body is checked when
something reaches it, and a module-level value when something reads it, in the
context of the module that declares it. Order of modules does not matter.

## Initialization

Each module's top-level code runs in its own source order, as one file does.
Modules that do not import each other in a cycle run as before: what a module
imports first. Within a cycle (a strongly connected component of the import
graph that contains a Dewy module), the members' top-level statements are
merged into one initialization sequence:

- a statement that reads or writes a value declared by another member of the cycle runs
  after that value's declaration; an access through a statically known function it
  calls counts too. A write waits for the declaration so its initializer cannot
  overwrite the write. Merely making or storing a function does not call it;
- otherwise statements keep the import order: the module that would have run
  first without the cycle runs as far as it can before the next one starts.

The merged sequence is one function, so a narrowed name or a top-level loop
variable behaves as within one file. Programs without a cycle through a Dewy
module produce exactly the code they did before; cycles of Sloppy modules alone
keep their import order.

## Errors

- A genuine value cycle, where values need each other's first values
  (`let a = B.b + 1` beside `let b = A.a + 1`), is reported where checking meets
  it, naming each value and where it is declared, in the order they need each
  other.
- A use before initialization, where no merged order exists because a module's
  own source order puts a statement before the value it needs (`let z = A.y`
  above `let x = 1` in B, while A has `let y = B.x`), names the chain of
  statements: which value each needs and which earlier statement of the same
  module it must wait for.

Within one file both errors keep their existing wording. The chain is found by
following, from the first blocked statement, the statement each one waits for
until one repeats; it costs nothing unless a cycle exists.

## Representation

The order is computed once checking is done (Tarjan's components over the
import edges that already order initialization). A cyclic Dewy component's
init functions become one: the first member's function takes the merged body
and the others' locals; every member's `init_fn` names it.
