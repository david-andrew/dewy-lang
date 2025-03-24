# original command I had working
# qbe metal.qbe > metal.s && as -o metal.o metal.s && as -o syscalls.o syscalls.x86_64 && ld -o app syscalls.o metal.o && ./app


"""
Given
- <program>.qbe
- all-core.qbe
- <OS>-core.qbe
- <OS>-syscalls-<arch>.s

emit the following commands:
# compile QBE files to assembly
- qbe {program}.qbe > {program}.s
- qbe all-core.qbe > all-core.s
- qbe {OS}-core.qbe > {OS}-core.s

# assemble object files
- as -o {program}.o {program}.s
- as -o all-core.o all-core.s
- as -o {OS}-core.o {OS}-core.s
- as -o {OS}-syscalls-{arch}.o {OS}-syscalls-{arch}.s

# link all object files together into program
ld -o {program} {program}.o all-core.o {OS}-core.o {OS}-syscalls-{arch}.o

# run the program
./{program}
"""

import subprocess
from argparse import ArgumentParser
import platform
from pathlib import Path

def main():
    # args: program name, [-os <os_name>] [-arch <arch_name>]
    parser = ArgumentParser(description='Demo to assemble and link QBE programs.')
    parser.add_argument('program', type=str, help='Name of the program to assemble and link.')
    parser.add_argument('-os', type=str, help='Operating system name for cross compilation. If not provided, defaults to current host OS', choices=['linux', 'apple', 'windows'])
    parser.add_argument('-arch', type=str, help='Architecture name for cross compilation. If not provided, defaults to current host arch', choices=['x86_64', 'arm64', 'riscv64'])

    args = parser.parse_args()
    program_path = Path(args.program)
    program = program_path.stem
    extension = program_path.suffix
    os_name: str = args.os if args.os else platform.system().lower()
    arch_name: str = args.arch if args.arch else platform.machine().lower()

    # verify that host arch is 64-bit since qbe doesn't support 32-bit
    if platform.architecture()[0] != '64bit':
        raise ValueError("This script only supports 64-bit architectures.")

    # compile QBE files to assembly
    qbe_target = get_qbe_target(arch_name, os_name)

    commands = [
        ['qbe', f'{program}{extension}', '>', f'{program}.s'],
        ['qbe', 'all-core.qbe', '>', 'all-core.s'],
        ['qbe', f'{os_name}-core.qbe', '>', f'{os_name}-core.s'],
        ['as', '-o', f'{program}.o', f'{program}.s'],
        ['as', '-o', 'all-core.o', 'all-core.s'],
        ['as', '-o', f'{os_name}-core.o', f'{os_name}-core.s'],
        ['as', '-o', f'{os_name}-syscalls-{arch_name}.o', f'{os_name}-syscalls-{arch_name}.s'],
        ['ld', '-o', program, f'{program}.o', 'all-core.o', f'{os_name}-core.o', f'{os_name}-syscalls-{arch_name}.o'],
        ['./', program]
    ]

    for command in commands:
        subprocess.run(' '.join(command), shell=True, check=True)


def get_qbe_target(arch_name: str, os_name: str) -> str:
    arch_map = {
        'x86_64': 'amd64',
        'arm64': 'arm64',
        'riscv64': 'rv64',
    }
    os_map = {
        'linux': 'sysv',
        'apple': 'apple',
        'windows': 'windows',
    }

    if arch_name not in arch_map:
        raise ValueError(f"Unsupported architecture: {arch_name}, supported: {list(arch_map.keys())}")
    if os_name not in os_map:
        raise ValueError(f"Unsupported OS: {os_name}, supported: {list(os_map.keys())}")
    
    arch_name = arch_map[arch_name]
    os_name = os_map[os_name]

    qbe_target = arch_name
    if arch_name in ['amd64', 'arm64'] and os_name == 'apple':
        qbe_target += '_apple'
    elif arch_name == 'amd64' and os_name == 'sysv':
        qbe_target += '_sysv'
    
    return qbe_target

if __name__ == '__main__':
    main()