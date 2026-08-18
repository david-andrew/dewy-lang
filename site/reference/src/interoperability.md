# µDewy and host interoperability

Dewy currently lowers to µDewy as its primary backend. µDewy is a strict,
minimal subset designed for bootstrapping; its runtime values occupy 64 bits and
its type annotations are intentionally lightweight.

Dewy exposes typed forms of µDewy's memory, allocation, shift, unsigned
operation, and supported syscall intrinsics. Linux x86-64 syscall intrinsics are
available today. A stable foreign-function interface and portable host
capability selection remain in development.

The µDewy compiler supports x86-64 Linux, WebAssembly, RISC-V, AArch64, and C
backends. Dewy's standard prelude does not yet provide equivalent host behavior
on every target.
