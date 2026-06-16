from typing import TypeAlias, Literal

# supported target triples
# (TODO: port this back down to udewy)
# not specifying a target targets the current machine
# (TODO: uncomment ones in here as we support them)
target:TypeAlias = Literal[
    # currently just use the verbatim list udewy supports
    # TODO: expand support to this fuller list
    'x86_64',
    'riscv',
    'arm',
    'c',
    'wasm32',


    
    # target the current machine (current machine must be compatible)
    # 'x86_64',
    # 'riscv64',
    # 'aarch64',
    # 'c',

    # # freestanding / baremetal
    # 'x86_64-freestanding',
    # 'riscv64-freestanding',
    # 'aarch64-freestanding',
    # 'c-freestanding',

    # # linux
    # 'x86_64-linux',
    # 'riscv64-linux',
    # 'aarch64-linux',
    # 'c-linux',

    # # mac
    # 'x86_64-mac',
    # 'aarch64-mac',

    # # windows
    # 'x86_64-windows',
    # 'riscv64-windows',
    # 'aarch64-windows',
    # 'c-windows',
    
    # # portable-ish
    # 'c-posix',
    # 'c89',
    # 'wasm32',

    # Others TBD
]

TARGETS: list[target] = [*target.__args__]





"""
different libc implementations like glibc or musl or msvc or etc. shouldn't be relevant
dewy (udewy) does not make use of the c stdlib


Open questions
- what about different mac chips like m1, m2, m3, m4?
- what about GPUs?
- different riscv ISAs
- (universal) shell language targets? 
- what about interpreter mode? perhaps not needed
"""


"""
random ideas about what may or may not be included

c
c-posix
c-linux
c-windows

# Native targets
x86_64-linux-glibc
x86_64-linux-musl
x86_64-windows
aarch64-macos
aarch64-ios
aarch64-ios-simulator
riscv64-linux-lp64d
x86_64-baremetal

# WebAssembly
wasm32
wasm32-wasi
wasm32-wasi-p2
wasm32-emscripten


# Linux
x86_64-linux-musl
aarch64-linux-musl
armv7-linux-gnueabihf

aarch64-ios-device
aarch64-ios-simulator

# Android
armeabi-v7a-android
arm64-v8a-android
x86_64-android

# WebAssembly
wasm32-none
wasm32-wasi-p1
wasm32-wasi-p1-threads
wasm32-wasi-p2

# Freestanding
x86_64-none
aarch64-none
armv7-none-eabi
riscv32-none
riscv64-none

"""