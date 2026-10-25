"""Structured waiting-lane lifetimes and cancellation values."""
import os
import subprocess

import pytest

from tests.support import compiler


def run(compiler, tmp_path, source, *, expected_error=None):
    path = tmp_path / 'tasks.dewy'
    path.write_text(source + ('\n$runtime_checks\n' if '$runtime_checks' not in source and '$prototype' not in source else ''))
    binary = tmp_path / 'tasks'
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True, timeout=60)
    if expected_error:
        assert built.returncode != 0
        assert expected_error in built.stderr, built.stderr
        return
    assert built.returncode == 0, built.stderr
    result = subprocess.run([binary], env=dict(os.environ, DEWY_THREADS='2'), capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.core_quick
def test_group_joins_and_exports_results(compiler, tmp_path):
    run(compiler, tmp_path, '''
work=(n:int64)=>n*2
main=()=>{
 concurrent {let a=spawn work(21) let b=spawn work(20)}
 $runtime_assert(a is? int64 and a =? 42)
 $runtime_assert(b is? int64 and b =? 40)
}
''')


@pytest.mark.core_quick
def test_deadline_cancels_sleep(compiler, tmp_path):
    run(compiler, tmp_path, '''
slow=():>int64|Canceled=>{sleep(1s) or_throw return 42}
main=()=>{
 let result=within(10ms @slow)
 $runtime_assert(result is? Timeout)
}
''')


def test_race_joins_losing_task(compiler, tmp_path):
    run(compiler, tmp_path, '''
slow=():>int64|Canceled=>{sleep(1s) or_throw return 42}
fast=():>int64|Canceled=>{sleep(1ms) or_throw return 7}
main=()=>{
 let result=race(@slow @fast)
 $runtime_assert(result is? int64 and result =? 7)
}
''')


def test_canceled_spelling(compiler, tmp_path):
    run(compiler, tmp_path, 'main=()=>{let value=Cancelled}', expected_error='use `Canceled`')


def test_first_failure_is_a_value(compiler, tmp_path):
    run(compiler, tmp_path, '''
Bad:type=type of error & [message:string]
fail=():>int64|Bad=>Bad["first"]
slow=():>int64|Canceled=>{sleep(1s) or_throw return 42}
main=()=>{
 let joined=concurrent {spawn fail() spawn slow()}
 $runtime_assert(joined is? Bad and joined.message =? "first")
}
''')


def test_named_group_can_be_passed(compiler, tmp_path):
    run(compiler, tmp_path, """
launch=(g:TaskGroup hits:Atomic<int64>)=>{spawn(g) hits.add(1)}
main=()=>{
 let hits=atomic(0)
 concurrent g {launch(g hits); launch(g hits);}
 $runtime_assert(hits.load() =? 2)
}
""")


def test_cancellation_is_level_triggered(compiler, tmp_path):
    run(compiler, tmp_path, """
Bad:type=type of error
fail=()=>{sleep(2ms); return Bad}
observe=(hits:Atomic<int64>)=>{
 let first=sleep(1s)
 if first is? Canceled {hits.add(1);}
 let second=sleep(1s)
 if second is? Canceled {hits.add(1);}
}
main=()=>{
 let hits=atomic(0)
 concurrent {spawn observe(hits) spawn fail()}
 $runtime_assert(hits.load() =? 2)
}
""")


def test_deadline_interrupts_blocked_file_open(compiler, tmp_path):
    import json
    fifo = tmp_path / 'waiting-fifo'
    os.mkfifo(fifo)
    run(compiler, tmp_path, f"""
main=()=>{{
 let result=within(10ms @read_text({json.dumps(str(fifo))}))
 $runtime_assert(result is? Timeout)
}}
""")


@pytest.mark.parametrize("cleanup_ns,expected", [(2000000, 1), (1000000000, -1)])
def test_cleanup_is_shielded(compiler, tmp_path, cleanup_ns, expected):
    (tmp_path / 'cleanup.jo').write_text(f"""
cleanup = (flag: Atomic[int]) -> void:
    result = __task_sleep_ns({cleanup_ns})
    if result is Canceled: flag.store(-1)
    else: flag.store(1)
work = (flag: Atomic[int]) -> (int | Canceled):
    defer cleanup(flag)
    result = __task_sleep_ns(1000000000)
    if result is Canceled: return Canceled
    42
""")
    run(compiler, tmp_path, """
from p"cleanup.jo" import work
main=()=>{
 let flag=atomic(0)
 let result=within(10ms @work(flag))
 $runtime_assert(result is? Timeout)
 $runtime_assert(flag.load() =? EXPECTED)
}
""".replace("EXPECTED", str(expected)))


def test_group_does_not_leak_native_tasks(compiler, tmp_path):
    (tmp_path / 'threads.jo').write_text('live = () -> int: list_dir("/proc/self/task").len()\n')
    run(compiler, tmp_path, """
from p"threads.jo" import live
work=()=>{sleep(1ms); return 1}
main=()=>{
 let before=live()
 loop i in [0..20) {concurrent {spawn work() spawn work()}}
 loop i in [0..100) {if live() =? before break sleep(1ms);}
 $runtime_assert(live() =? before)
}
""")


@pytest.mark.parametrize('operation', ['read_stdin()', 'read_line()', 'input()', 'input_int()', 'input_float()'])
def test_deadline_interrupts_stdin(compiler, tmp_path, operation):
    path = tmp_path / 'stdin.dewy'
    path.write_text(f'''main=()=>{{
 let result=within(10ms @({{ {operation} }}))
 $runtime_assert(result is? Timeout)
}}''')
    # Use an explicit thunk: stdin stays open without producing input or EOF.
    path.write_text(path.read_text().replace(f'@({{ {operation} }})', f'@wait_input'))
    path.write_text(f'wait_input=()=>{operation}\n' + path.read_text() + '\n$runtime_checks\n')
    binary = tmp_path / 'stdin'
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    with subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        try:
            assert child.wait(timeout=5) == 0, child.stderr.read().decode()
        finally:
            if child.poll() is None:
                child.kill()


@pytest.mark.parametrize('operation', ['read_line', 'read_bytes', 'write_text'])
def test_deadline_interrupts_stream_io(compiler, tmp_path, operation):
    import json
    fifo = tmp_path / 'stream'
    os.mkfifo(fifo)
    # Hold both ends open, without supplying input or consuming output.
    fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    try:
        if operation == 'write_text':
            work = f'work=()=>write_text({json.dumps(str(fifo))} "x"*1000000)'
        else:
            read = 'file.read_line()' if operation == 'read_line' else 'file.read_bytes(1)'
            work = f'''work=():>int64|Canceled=>{{
 let opened=open_file({json.dumps(str(fifo))})
 if opened is? none return -1
 if opened is? Canceled return Canceled
 let file=opened
 let value={read}
 file.close()
 if value is? Canceled return Canceled
 return 1
}}'''
        run(compiler, tmp_path, work + '''
main=()=>{
 let result=within(10ms @work)
 $runtime_assert(result is? Timeout)
}
''')
    finally:
        os.close(fd)


@pytest.mark.parametrize('operation', ['run', 'run_silent', 'capture'])
def test_deadline_cancels_owned_process_wait(compiler, tmp_path, operation):
    run(compiler, tmp_path, f'''
main=()=>{{
 let result=within(20ms @{operation}("/bin/sleep" ["10"]))
 $runtime_assert(result is? Timeout)
}}
''')


def test_cancellation_reaches_nested_join(compiler, tmp_path):
    run(compiler, tmp_path, '''
slow=()=>sleep(1s)
wait=()=>concurrent {spawn slow() spawn slow()}
main=()=>{
 let result=within(10ms @wait)
 $runtime_assert(result is? Timeout)
}
''')


def test_return_cancels_and_joins_children(compiler, tmp_path):
    run(compiler, tmp_path, '''
work=()=>{sleep(1s); return 1}
early=()=>{concurrent {spawn work() return 7} return 8}
main=()=>{$runtime_assert(early() =? 7)}
''')


def test_task_rejects_unsynchronized_global(compiler, tmp_path):
    run(compiler, tmp_path, '''
let shared=[1 2 3]
read=()=>shared.length
main=()=>{concurrent {spawn read()} shared.push(4)}
''', expected_error='unsynchronized global')


def test_output_is_not_a_cancellation_point(compiler, tmp_path):
    path = tmp_path / 'output.dewy'
    path.write_text('''main=()=>{
 concurrent g {
  cancel(g)
  printl("still printed")
  printl("to stderr" file=stderr)
  $runtime_assert(sleep(1ms) is? Canceled)
 }
}
''')
    binary = tmp_path / 'output'
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'still printed\n' and result.stderr == 'to stderr\n'


def test_void_tasks_and_race(compiler, tmp_path):
    run(compiler, tmp_path, """
work=(hits:Atomic<int64>):>void=>{hits.add(1);}
main=()=>{
 let hits=atomic(0)
 concurrent {let a=spawn work(hits)}
 $runtime_assert(a is? void)
 let result=race(@work(hits) @work(hits))
 $runtime_assert(result is? void)
 $runtime_assert(hits.load() >=? 2)
}
""")


def test_first_failure_survives_later_sibling_failure(compiler, tmp_path):
    run(compiler, tmp_path, """
First:type=type of error & [message:string]
Later:type=type of error & [message:string]
fail=()=>{sleep(2ms); return First["original"]}
late=()=>{sleep(1s); return Later["after cancellation"]}
main=()=>{
 let joined=concurrent {spawn late() spawn fail()}
 $runtime_assert(joined is? First and joined.message =? "original")
}
""")
