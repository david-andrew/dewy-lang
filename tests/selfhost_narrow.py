"""Build a live Dewy leaf with its service doubles and check its recorded outputs."""
import re
import subprocess

from tests import leaf_oracle
from tests.selfhost_effect_double import CHECKS_HOMES, LEAF_HOMES
from tests.support import ROOT


def compare_narrow(compiler, tmp_path, release, stems, driver, doubles=None, run_in=None, observe=None,
                   invocations=(((), 0),), services=(), *, snapshot=True):
    """Run each (arguments, status) invocation in run_in()'s working directory.
    Doubles replace named modules. Imports of services are redirected to
    services.jo. The record includes stdout, stderr and observe(directory).
    Return one invocation's stdout or the list of outputs for multiple runs."""
    # (a moved checking leaf stands with the module it left, when that module is a service or a double)
    homes = {**CHECKS_HOMES, **LEAF_HOMES}
    services = (*services, *(stem for stem, home in homes.items() if home[:-3] in services and stem not in stems))
    doubled = {stem: home for stem, home in homes.items() if home in (doubles or {})}

    def redirect(text):
        for stem, home in doubled.items():
            for extension in ('dewy', 'jo'):
                text = text.replace(f'{stem}.{extension}', home)
        for stem in services:
            for quote in ('"', "'"):
                for extension in ('dewy', 'jo'):
                    text = text.replace(f'{quote}{stem}.{extension}{quote}', f'{quote}services.jo{quote}')
        return text

    stems = list(stems)
    for stem in stems:
        source = (ROOT / f'compiler/{stem}.dewy').read_text()
        for name in re.findall(r'(?m)^\s*from p"(\w+)\.dewy"', source):
            if name not in stems and name not in services and name not in doubled and f'{name}.dewy' not in (doubles or {}):
                stems.append(name)
    directory = tmp_path / 'dewy'
    directory.mkdir()
    for name, text in (doubles or {}).items():
        (directory / name).write_text(text)
    for stem in stems:
        text = (ROOT / f'compiler/{stem}.dewy').read_text()
        text = redirect(text)
        (directory / f'{stem}.dewy').write_text(text)
    source, binary = directory / 'driver.jo', directory / 'driver'
    body = redirect(driver)
    uses = ("use 'services.jo'\n" if services else '') + ''.join(f"use '{stem}.dewy'\n" for stem in stems)
    source.write_text(uses + body)
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=90)
    assert built.returncode == 0, built.stdout + built.stderr
    runs = []
    for arguments, status in invocations:
        where = run_in() if run_in else None
        ran = subprocess.run([binary, *arguments], capture_output=True, timeout=60, cwd=where)
        assert ran.returncode == status, (arguments, ran.stdout[-3000:], ran.stderr)
        runs.append((ran.stdout, ran.stderr, observe(where) if observe else None))
    if snapshot:
        for (arguments, status), (stdout, stderr, observed) in zip(invocations, runs):
            payload = stdout + (b'\n--stderr--\n' + stderr if stderr else b'')
            payload += b'\n--observed--\n' + repr(observed).encode() if observe else b''
            leaf_oracle.check(arguments, status, leaf_oracle.without(tmp_path, payload))
    stdout = [run[0] for run in runs]
    return stdout[0] if len(stdout) == 1 else stdout
