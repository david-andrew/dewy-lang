"""Stand in front of a leaf compiler and record what each invocation does (tests/leaf_oracle.py).

Usage: leaf_record.py LOG COMPILER TMP CLI NAME ARGUMENTS...
Runs COMPILER (as NAME, the path the test knows) with ARGUMENTS, passes its output through, and
appends to LOG the build record of tests/whole_oracle.py: arguments, status, output, diagnostics and
what the files it made do.
Interactive commands (the language server, watch, and with CLI=1 the bare prompt) pass straight through: their sessions
are recorded where the test reads them.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import whole_oracle

INTERACTIVE = ('lsp', 'watch', 'repl')


def recorded(output, name):
    """Output as recorded: this stand-in's paths and the times a run reports (`12.5 ms`) named."""
    output = output.replace(os.fsencode(name), b'<compiler>')
    # (where the stand-in would find its library: above the test's own directory)
    output = output.replace(os.fsencode(Path(os.path.abspath(name)).parent.parent / 'lib'), b'<above>/lib')
    output = re.sub(rb'\d+(?:\.\d+)? ms\b', b'N ms', output)
    return re.sub(rb'"ms":\d+(?:\.\d+)?', b'"ms":N', output)


def main():
    log, compiler, tmp, cli, name, *arguments = sys.argv[1:]
    # (a timed report measures this run: it is not an outcome)
    interactive = arguments[0] in INTERACTIVE if arguments else cli == '1'
    if interactive or os.environ.get('DEWY_PAR_TIME'):
        os.execv(compiler, [name, *arguments])
    # (the compiler sees this wrapper's name as its own, as the test expects)
    ran = subprocess.run([name, *arguments], executable=compiler, capture_output=True, check=False)
    # (a compiler that names where it runs from names this stand-in, the path the test knows)
    real, shown = Path(compiler), Path(os.path.abspath(name))
    places = [(real, shown), (real.parent, shown.parent), (real.parent.parent, shown.parent.parent)]
    for real, shown in places:
        ran.stdout = ran.stdout.replace(os.fsencode(real), os.fsencode(shown))
        ran.stderr = ran.stderr.replace(os.fsencode(real), os.fsencode(shown))
    sys.stdout.buffer.write(ran.stdout)
    sys.stderr.buffer.write(ran.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    if '--time' in arguments:
        sys.exit(ran.returncode)  # (a timed report measures this run: it is not an outcome)
    files = []
    if 'build' in arguments and '-o' in arguments[:-1]:
        files = whole_oracle.outputs(Path(os.path.abspath(arguments[arguments.index('-o') + 1])))
    shown = [os.path.abspath(a) if os.path.exists(a) else a for a in arguments]
    entry = whole_oracle.build(shown, ran.returncode, recorded(ran.stdout, name), recorded(ran.stderr, name),
                               files, Path(tmp))
    with open(log, 'a') as stream:
        stream.write(json.dumps(entry) + '\n')
    sys.exit(ran.returncode)


main()
