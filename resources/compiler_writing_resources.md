# Compiler Resources/Ideas

- I made a language for the Nintendo DS
  - https://www.youtube.com/watch?v=jMIj893JJBg
  - talking about how to do typechecking, dealing with out of order dependencies in declarations (make a declarations DAG and go in that order)
- Muukid channel
  - https://www.youtube.com/@Muukid
  - 2 videos about making windows (and later graphic stuff) from scratch on WINDOWS. will be very useful when I want to get dewy running on windows

- Compilers, How They Work, And Writing Them From Scratch
  - https://www.youtube.com/watch?v=QdnxjYj1pS0
  - high level overview


- creating a compiler in C++
  - https://www.youtube.com/watch?v=vcSijrRsrY0&list=PLUDlas_Zy_qC7c5tCgTMYq2idyyT241qs
  - shows good stuff e.g. the most basic x86_64 program (exit 42)
  - decent in that it doesn't gloss over much (but the compiler made is pretty simple)
  - pretty off the cuff. C++ is not great


- Porth
  - https://www.youtube.com/watch?v=8QP2fDBIxjM&list=PLpM-Dvs8t0VbMZA7wW9aR3EtBqe2kinu4
  - a classic. shows a lot of low level details about running linux programs
  - less relevant to Dewy because Porth is reverse polish notation (i.e. minimal lexing/parsing difficulty) and the runtime is stack based, so completely foreign to how Dewy runs

- Mixing C++ and Rust for Fun and Profit: Part 1
  - https://www.kdab.com/mixing-c-and-rust-for-fun-and-profit-part-1/
  - mostly just for the idea of having good support for talking to other languages
  - the consensus I've reached is Dewy should let you use flags to specify a name-mangling scheme so that dewy binaries can talk natively to other language binaries, etc. 




# Standard Library Resources/Ideas:
- Printf and Non-Blocking C & C++ Logging for Debugging Concurrency Issues
  - https://www.youtube.com/watch?v=QeXrPVD5LJA
  - basically how to do logging at ~1 nanosecond scale by fancy mapping to data segments in compiled file
  - in video they have to do an extra processing step, but perhaps we can automatically have `dewy` command call the processing step after the file is executed

- When Nanoseconds Matter: Ultrafast Trading Systems in C++ - David Gross - CppCon 2024
  - https://www.youtube.com/watch?v=sX2nF1fW7kI




# Various features from zig/rust:
Zig is better than Rust (sometimes): https://www.youtube.com/watch?v=l9eFGToyjf8
- optionals (stick with my `type|undefined` and `type|void` types)
- `unreachable` keyword
- consider `!!` operator as opposite of `??` for panicing on something being null. Though honestly could just do `thing ?? panic"shouldn't be possible"`
- thing abour regexes possibly being invalid, probably should be done at compile-time. Also dewy should have much stronger support for actual parser-generators over regex
- module imports: basically planning to do the zig version anyways with filepath-based imports
- no changes from Dewy's existing let/const declaration system
- TBD how to handle pointers in Dewy! I think in general the idea is to not have pointers from a developer point of view and things are reference and dereferenced automatically. But there certainly could be instances where being able to deal in pointers would be valuable
- compiletime: basically taking from zig/jai
- C interop: should add nice support for working with C. perhaps we could build in a C compiler and let it be as easy as calling C in zig? Or let the user point to a C compiler, and automatically generate shim C code for calling the C code from dewy
