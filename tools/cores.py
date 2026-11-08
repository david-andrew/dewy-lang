"""Run a command on a limited number of cores, for tests and benchmarks.

A program's own cap is the `$program.max_cores` setting in its entry file.
Harnesses that run one build at several core counts limit the cores the
operating system gives the process instead: the runtime sizes its worker pool
from the cores the process may use.
"""
import os
import shutil


def on_cores(command, count):
    """`command` prefixed so it runs on at most `count` of the cores this process may use.

    Linux only (`taskset`); elsewhere the command is returned unchanged, so a
    result that depends on the count is checked on Linux alone."""
    command = [str(part) for part in command]
    if not hasattr(os, 'sched_getaffinity') or not shutil.which('taskset'):
        return command
    allowed = sorted(os.sched_getaffinity(0))[:max(1, int(count))]
    return ['taskset', '-c', ','.join(map(str, allowed)), *command]
