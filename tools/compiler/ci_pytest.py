"""Run one CI pytest shard and leave a trail when something kills it.

A shard has twice died with exit 143 (SIGTERM) and "The runner has received a shutdown signal",
after which the runner skips every later step, so nothing can be collected afterwards. This
wrapper therefore writes what it learns to the job log as it goes:

* a heartbeat every 15 s: the test each pytest process started last (DEWY_TEST_TRACE files,
  tools/compiler/pytest_parallel.py) and the processes running;
* a bpftrace probe, when it can be installed, that logs the sender and target of every SIGTERM;
* on SIGTERM to this wrapper, or a failing exit, the senders, the process list and dmesg.

Usage (CI): DEWY_TEST_TRACE=DIR python -m tools.compiler.ci_pytest [PYTEST PATHS]
"""
import glob
import os
import signal
import subprocess
import sys
import threading
import time

from tools.core import TESTS

PROBE = ('tracepoint:signal:signal_generate /args->sig == 15/ '
         '{ printf("%d s: %s[%d] sends SIGTERM to %s[%d]\\n", elapsed / 1000000000, comm, pid, args->comm, args->pid); }')
INTERESTING = ('pytest', 'dewy-core', 'node', 'python', 'Runner')


def say(text: str) -> None:
    print(text, flush=True)


def snapshot() -> str:
    ps = subprocess.run(['ps', '-eo', 'pid,ppid,pgid,sid,etimes,args', '--sort=pid'],
                        capture_output=True, text=True, check=False).stdout.splitlines()
    rows = [row[:170] for row in ps[1:] if any(word in row for word in INTERESTING)]
    return '\n'.join(ps[:1] + rows[-40:])


def last_tests(directory: str) -> str:
    lines = []
    for path in sorted(glob.glob(os.path.join(directory, 'start-*.log'))):
        try:
            with open(path) as handle:
                last = handle.read().strip().splitlines()[-1:]
        except OSError:
            continue
        lines += [f'{os.path.basename(path)}: {row}' for row in last]
    return '\n'.join(lines[-8:])


def start_probe(directory: str):
    """bpftrace logging every SIGTERM's sender, if it can be had; else None."""
    senders = os.path.join(directory, 'sigterm.senders')
    try:
        if subprocess.run(['sudo', '-n', 'true'], capture_output=True, check=False).returncode:
            return None, senders
        if subprocess.run(['which', 'bpftrace'], capture_output=True, check=False).returncode:
            subprocess.run(['sudo', 'apt-get', 'install', '-y', '-q', 'bpftrace'], capture_output=True,
                           timeout=120, check=False)
        probe = subprocess.Popen(['sudo', 'bpftrace', '-e', PROBE], stdout=open(senders, 'w'),
                                 stderr=subprocess.STDOUT, start_new_session=True)
    except (OSError, subprocess.SubprocessError) as error:
        say(f'ci_pytest: no SIGTERM probe: {error}')
        return None, senders
    for _ in range(40):  # (it prints "Attaching" once the probe is live)
        time.sleep(0.5)
        if os.path.exists(senders) and 'Attaching' in open(senders).read():
            say('ci_pytest: SIGTERM probe attached')
            return probe, senders
    say('ci_pytest: the SIGTERM probe did not attach: ' + open(senders).read()[:300])
    return probe, senders


def report(why: str, directory: str, senders: str) -> None:
    say(f'::group::ci_pytest report: {why}')
    say('SIGTERM senders:')
    try:
        say(open(senders).read()[-4000:] or '(none recorded)')
    except OSError:
        say('(no probe)')
    say('last test of each pytest process:\n' + last_tests(directory))
    say(snapshot())
    subprocess.run('free -m; sudo -n dmesg | tail -30', shell=True, check=False)
    say('::endgroup::')


def main() -> int:
    directory = os.environ.get('DEWY_TEST_TRACE') or os.path.join(os.environ.get('RUNNER_TEMP', '.'), 'test-trace')
    os.environ['DEWY_TEST_TRACE'] = directory
    os.makedirs(directory, exist_ok=True)
    say(f'pid_max {open("/proc/sys/kernel/pid_max").read().strip()}; wrapper pid {os.getpid()} '
        f'group {os.getpgrp()} session {os.getsid(0)}')
    subprocess.run(['free', '-m'], check=False)
    probe, senders = start_probe(directory)
    command = [sys.executable, '-m', 'pytest', '-q', '-o', 'addopts=', '--junitxml=core-results.xml',
               '-p', 'xdist.plugin', '-p', 'tools.compiler.pytest_parallel', '-n', '4',
               '--dist=loadgroup', '-m', 'not nightly', *(sys.argv[1:] or TESTS)]
    child = subprocess.Popen(command)
    done = threading.Event()

    def beat():
        while not done.wait(15):
            say(f'--- heartbeat {time.strftime("%H:%M:%S")}\n{last_tests(directory)}\n{snapshot()}')

    threading.Thread(target=beat, daemon=True).start()

    def terminated(number, frame):
        report('SIGTERM reached the wrapper', directory, senders)
        child.send_signal(signal.SIGTERM)
        signal.signal(number, signal.SIG_DFL)
        os.kill(os.getpid(), number)

    signal.signal(signal.SIGTERM, terminated)
    status = child.wait()
    done.set()
    if status:
        report(f'pytest exited {status}', directory, senders)
    if probe is not None:
        probe.terminate()
    return 128 - status if status < 0 else status


if __name__ == '__main__':
    raise SystemExit(main())
