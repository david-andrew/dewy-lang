# udewy Bootstrap Compiler

A self-hosting multi-backend compiler for the udewy language, written in udewy itself.

## Overview

The bootstrap compiler is a modular rewrite of the original single-file `udewy.udewy` compiler. It supports multiple target architectures through a pluggable backend system.

## Architecture

```
bootstrap/
├── main.udewy           # Entry point and CLI handling
├── prelude.udewy        # Common constants and character helpers
├── syscalls.udewy       # x86_64 Linux syscall wrappers
├── memory.udewy         # Arena allocator and memory utilities
├── strings.udewy        # String manipulation functions
├── output.udewy         # Output buffer management
├── tokens.udewy         # Tokenizer and token definitions
├── symbols.udewy        # Symbol tables (functions, globals, locals)
├── parser.udewy         # Parser and semantic analysis
├── backend.udewy        # Backend dispatcher
├── backend_x86_64.udewy # x86_64 code generation
├── backend_riscv.udewy  # RISC-V 64-bit code generation
└── backend_arm.udewy    # ARM64/AArch64 code generation
```

## Supported Targets

| Target | Description | Status |
|--------|-------------|--------|
| x86_64 | AMD64 / Intel 64-bit Linux | Primary |
| riscv  | RISC-V 64-bit Linux | Supported |
| arm    | ARM64 / AArch64 Linux | Supported |

## Building the Bootstrap Compiler

First, compile the bootstrap compiler using the Python-based compiler:

```bash
# From the udewy directory
python3 -m udewy.p0 bootstrap/main.udewy --target x86_64

# This creates an executable in __dewycache__
```

## Usage

```bash
./udewyc input.udewy [-o output.s] [--target x86_64|riscv|arm]
```

### Options

- `-o output.s` - Specify output assembly file (default: stdout)
- `--target <arch>` - Select target architecture (default: x86_64)

### Examples

```bash
# Compile to x86_64 assembly
./udewyc hello.udewy -o hello.s

# Compile for RISC-V
./udewyc hello.udewy -o hello.s --target riscv

# Compile for ARM64
./udewyc hello.udewy -o hello.s --target arm
```

## Module Descriptions

### Core Modules

- **prelude.udewy**: Boolean constants, ASCII codes, character classification functions
- **syscalls.udewy**: Linux system call numbers and wrapper functions for x86_64
- **memory.udewy**: Arena allocator for dynamic memory management

### I/O Modules

- **strings.udewy**: String comparison, manipulation, and conversion utilities
- **output.udewy**: Buffered output for text and data sections

### Compiler Modules

- **tokens.udewy**: Token type constants, token storage, and lexical analysis
- **symbols.udewy**: Symbol tables for functions, globals, constants, and local scopes
- **parser.udewy**: Recursive descent parser with Pratt-style expression parsing

### Backend Modules

- **backend.udewy**: Backend dispatcher that routes code generation to the selected target
- **backend_x86_64.udewy**: x86_64 assembly generation (System V ABI)
- **backend_riscv.udewy**: RISC-V assembly generation (LP64 ABI)
- **backend_arm.udewy**: ARM64 assembly generation (AAPCS64)

## Design Decisions

### Single-Pass Compilation

Like the Python compiler, the bootstrap compiler is single-pass. Functions are compiled as they are encountered, with forward references resolved via placeholder labels.

### Backend Abstraction

Code generation is abstracted through a dispatcher pattern. The parser calls backend functions like `backend_emit_push()`, `backend_emit_binop()`, etc., which route to the appropriate target-specific implementation.

### Memory Management

A simple arena allocator provides all dynamic memory. This avoids the complexity of a general-purpose allocator while being sufficient for compilation.

### Stack-Based Temporaries

Expression evaluation uses the hardware stack for temporaries. Each backend implements push/pop operations appropriate to its calling convention.

## Self-Hosting

The bootstrap compiler can compile itself (once the Python compiler builds it first):

```bash
# Build bootstrap compiler with Python
python3 -m udewy.p0 bootstrap/main.udewy

# Use bootstrap compiler to build itself
./udewyc bootstrap/main.udewy -o udewyc2.s
```
