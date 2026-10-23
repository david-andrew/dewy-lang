"""Run the interactive prompt (plain `dewy` at a terminal) with scripted input.

The prompt starts only when standard input is a terminal, so the input goes through a
pseudo-terminal; standard output and error stay pipes. The prompt's line redrawing is
removed from the output, leaving the program's own output and the values shown.
"""
import os
import re
import subprocess
import threading

import pytest

ANSI = re.compile(rb'\x1b\[[0-9;?]*[A-Za-z]')
REDRAW = re.compile(rb'(?:\r+(?:>>> |\.\.\. )[^\r\n]*)+(?:\r*\n)?')
BANNER = b'Dewy (:help for help; braces may span lines; ctrl-d quits)\n'


def run_repl(compiler, text, cwd, env=None, timeout=20):
    """Feed text to the prompt; return a CompletedProcess whose stdout has no prompt drawing."""
    if os.name == 'nt':
        pytest.skip('the prompt is driven through a POSIX pseudo-terminal')
    import pty
    master, slave = pty.openpty()
    env = {**os.environ, **(env or {}), 'DEWY_REPL_HISTORY': str(cwd / 'repl-history')}
    process = subprocess.Popen([compiler], cwd=cwd, env=env, stdin=slave,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    os.close(slave)

    def drain():  # (the terminal's echo of what is typed ahead must not fill its buffer)
        try:
            while os.read(master, 4096):
                pass
        except OSError:
            pass

    threading.Thread(target=drain, daemon=True).start()
    try:
        os.write(master, text.encode())
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        out, err = process.communicate()
        raise
    finally:
        os.close(master)
    out = REDRAW.sub(b'', ANSI.sub(b'', out)).replace(BANNER, b'', 1).replace(b'\r', b'')
    return subprocess.CompletedProcess(process.args, process.returncode, out.decode(), err.decode())
