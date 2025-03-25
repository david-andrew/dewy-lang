# original command I had working
# qbe metal.qbe > metal.s && as -o metal.o metal.s && as -o syscalls.o syscalls.x86_64 && ld -o app syscalls.o metal.o && ./app


"""
Tasks
- grab the system regardless of if target provided
- if target provided, check against system to determine if can run at the end or not

- allow running against .qbe programs anywhere (but the supporting files stay here)
"""

"""
Given
- <program>.qbe
- all-core.qbe
- <OS>-core.qbe
- <OS>-syscalls-<arch>.s

emit the following commands:
# compile QBE files to assembly
- qbe {program}.qbe all-core.qbe {OS}-core.qbe > {program}.s

# assemble object files
- as -o {program}.o {program}.s
- as -o {OS}-syscalls-{arch}.o {OS}-syscalls-{arch}.s

# link all object files together into program
ld -o {program} {program}.o {OS}-syscalls-{arch}.o

# run the program (if not cross-compiling)
./{program}
"""

# e.g.
# qbe myprog.qbe all-core.qbe linux-core.qbe > myprog.s && as -o myprog.o myprog.s && as -o linux-syscalls-x86_64.o linux-syscalls-x86_64.s && ld -o myprog myprog.o linux-syscalls-x86_64.o && ./myprog

import subprocess
from argparse import ArgumentParser
import platform
from pathlib import Path
import os

import pdb

here = Path(__file__).parent

def main():
    # get the host system info
    host_os = platform.system().lower()
    host_arch = platform.machine().lower()
    host_system = get_qbe_target(host_arch, host_os)

    # verify that host arch is 64-bit since qbe doesn't support 32-bit
    if platform.architecture()[0] != '64bit':
        raise ValueError("This script only supports 64-bit architectures.")

    # args: [-os <os_name>] [-arch <arch_name>] program_name [optional command line args for the program]
    parser = ArgumentParser(description='Demo to assemble and link QBE programs.')
    parser.add_argument('program', type=str, help='Name of the program to assemble and link.')
    parser.add_argument('-os', type=str, help='Operating system name for cross compilation. If not provided, defaults to current host OS', choices=['linux', 'apple', 'windows'])
    parser.add_argument('-arch', type=str, help='Architecture name for cross compilation. If not provided, defaults to current host arch', choices=['x86_64', 'arm64', 'riscv64'])
    parser.add_argument('-b', '--build-only', action='store_true', help='Only compile/build the program, do not run it')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print out the commands being run')
    parser.add_argument('remaining_args', nargs='*', help='Any command line arguments for the program.')

    args = parser.parse_args()
    verbose: bool = args.verbose
    program_path = Path(args.program)
    program, extension = program_path.stem, program_path.suffix
    target_os: str = args.os if args.os else host_os
    target_arch: str = args.arch if args.arch else host_arch
    remaining_args: list[str] = args.remaining_args

    # compile QBE files to assembly
    target_system = get_qbe_target(target_arch, target_os)
    cross_compiling = target_system != host_system
    run_program = not args.build_only and not cross_compiling

    commands = [
        ['qbe', '-t', target_system, f'{program}{extension}', 'all-core.qbe', f'{target_os}-core.qbe', '>', f'{program}.s'],
        ['as', '-o', f'{program}.o', f'{program}.s'],
        ['as', '-o', f'{target_os}-syscalls-{target_arch}.o', f'{target_os}-syscalls-{target_arch}.s'],
        ['ld', '-o', program, f'{program}.o', f'{target_os}-syscalls-{target_arch}.o'],
        # clean up temporary files
        ['rm', f'{program}.s', f'{program}.o', f'{target_os}-syscalls-{target_arch}.o'],
    ]


    for command in commands:
        # TODO: this isn't secure. want shell=False, but need to properly handle piping
        cmd = ' '.join(command)
        if verbose: print(cmd)
        subprocess.run(cmd, shell=True, check=True)


    # run the program after if not cross-compiling (or in build-only mode)
    # hand off execution from this script to the compiled program
    if run_program:
        if verbose: print(f'./{program} {" ".join(remaining_args)}')
        os.execv(program, [program] + remaining_args)


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