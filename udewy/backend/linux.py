from typing import Literal


LINUX_SYSCALL_INTRINSIC_ARITIES: dict[str, int] = {
    f"__syscall{i}__": i + 1 for i in range(7)
}

LINUX_COMMON_CONSTANTS: dict[str, int] = {
    "STDIN": 0,
    "STDOUT": 1,
    "STDERR": 2,
    "O_RDONLY": 0,
    "O_WRONLY": 1,
    "O_RDWR": 2,
    "O_CREAT": 64,
    "O_TRUNC": 512,
    "O_APPEND": 1024,
    "PROT_NONE": 0,
    "PROT_READ": 1,
    "PROT_WRITE": 2,
    "PROT_EXEC": 4,
    "MAP_SHARED": 1,
    "MAP_PRIVATE": 2,
    "MAP_ANONYMOUS": 32,
    "MAP_FIXED": 16,
}

X86_64_LINUX_SYSCALLS: dict[str, int] = {
    "SYS_READ": 0,
    "SYS_WRITE": 1,
    "SYS_OPEN": 2,
    "SYS_CLOSE": 3,
    "SYS_STAT": 4,
    "SYS_FSTAT": 5,
    "SYS_LSEEK": 8,
    "SYS_MMAP": 9,
    "SYS_MUNMAP": 11,
    "SYS_BRK": 12,
    "SYS_IOCTL": 16,
    "SYS_PIPE": 22,
    "SYS_DUP": 32,
    "SYS_DUP2": 33,
    "SYS_GETPID": 39,
    "SYS_FORK": 57,
    "SYS_EXECVE": 59,
    "SYS_EXIT": 60,
    "SYS_WAIT4": 61,
    "SYS_KILL": 62,
    "SYS_GETCWD": 79,
    "SYS_CHDIR": 80,
    "SYS_MKDIR": 83,
    "SYS_RMDIR": 84,
    "SYS_CREAT": 85,
    "SYS_UNLINK": 87,
    "SYS_GETUID": 102,
    "SYS_GETGID": 104,
    "SYS_GETEUID": 107,
    "SYS_GETEGID": 108,
    "SYS_CLOCK_GETTIME": 228,
    "SYS_EXIT_GROUP": 231,
}

NEWSTYLE_LINUX_SYSCALLS: dict[str, int] = {
    "SYS_GETCWD": 17,
    "SYS_DUP": 23,
    "SYS_DUP3": 24,
    "SYS_IOCTL": 29,
    "SYS_MKDIRAT": 34,
    "SYS_UNLINKAT": 35,
    "SYS_FTRUNCATE": 46,
    "SYS_FACCESSAT": 48,
    "SYS_CHDIR": 49,
    "SYS_OPENAT": 56,
    "SYS_CLOSE": 57,
    "SYS_PIPE2": 59,
    "SYS_LSEEK": 62,
    "SYS_READ": 63,
    "SYS_WRITE": 64,
    "SYS_READV": 65,
    "SYS_WRITEV": 66,
    "SYS_FSTAT": 80,
    "SYS_EXIT": 93,
    "SYS_EXIT_GROUP": 94,
    "SYS_KILL": 129,
    "SYS_GETPID": 172,
    "SYS_GETUID": 174,
    "SYS_GETEUID": 175,
    "SYS_GETGID": 176,
    "SYS_GETEGID": 177,
    "SYS_BRK": 214,
    "SYS_MUNMAP": 215,
    "SYS_CLONE": 220,
    "SYS_EXECVE": 221,
    "SYS_MMAP": 222,
    "SYS_WAIT4": 260,
    "AT_FDCWD": -100,
}


def linux_builtin_constants(kind: Literal["x86_64", "newstyle"]) -> dict[str, int]:
    if kind == "x86_64":
        return LINUX_COMMON_CONSTANTS | X86_64_LINUX_SYSCALLS
    return LINUX_COMMON_CONSTANTS | NEWSTYLE_LINUX_SYSCALLS
