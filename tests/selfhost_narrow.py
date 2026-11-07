"""Build a Dewy leaf and its frozen twin with only the modules its services need."""
import re
import subprocess

from tests.selfhost_effect_double import CHECKS_HOMES
from tests.support import ROOT


def compare_narrow(compiler, tmp_path, release, stems, driver, doubles=None, run_in=None, observe=None,
                   invocations=(((), 0),), services=()):
    """The stdout of each invocation, compared across both builds. stems: real twinned modules;
    doubles: {file: text}, Jo modules both builds use, or a `.dewy`/`.jo` pair; invocations:
    (arguments, status) runs, each in run_in()'s working directory; observe(directory): what else
    those runs must agree on; services: compiler modules (by stem) whose imports all lead to the Jo
    double `services.jo`. A single invocation's stdout comes back alone."""
    # (a moved checking leaf stands with the module it left, when that module is a service or a double)
    services = (*services, *(stem for stem, home in CHECKS_HOMES.items() if home[:-3] in services))
    doubled = {stem: home for stem, home in CHECKS_HOMES.items() if home in (doubles or {})}

    def redirect(text):
        for stem, home in doubled.items():
            for extension in ('dewy', 'jo'):
                text = text.replace(f'{stem}.{extension}', home)
        for stem in services:
            for quote in ('"', "'"):
                for extension in ('dewy', 'jo'):
                    text = text.replace(f'{quote}{stem}.{extension}{quote}', f'{quote}services.jo{quote}')
        return text

    # (what a real module imports comes too, down to the services and doubles)
    stems = list(stems)
    for stem in stems:
        for name in (re.findall(r'(?m)^\s*from p"(\w+)\.dewy"', (ROOT / f'compiler/{stem}.dewy').read_text())
                     + re.findall(r"(?m)^use '(\w+)\.dewy'", (ROOT / f'compiler/{stem}.jo').read_text())):
            if name not in stems and name not in services and name not in doubled and f'{name}.dewy' not in (doubles or {}):
                stems.append(name)
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for name, text in (doubles or {}).items():
            (directory / name).write_text(text.replace(".dewy'", ".jo'") if extension == 'jo' else text)
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            text = redirect(text)
            (directory / f'{stem}.{extension}').write_text(text.replace(".dewy'", ".jo'") if extension == 'jo' else text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        body = redirect(driver)
        body = body.replace(".dewy'", ".jo'") if extension == 'jo' else body
        uses = ("use 'services.jo'\n" if services else '') + ''.join(f"use '{stem}.{extension}'\n" for stem in stems)
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
        outputs.append(runs)
    for index, (dewy, jo) in enumerate(zip(*outputs)):
        for field, (a, b) in zip(('stdout', 'stderr', 'observed'), zip(dewy, jo)):
            if a != b:
                at = next((i for i, pair in enumerate(zip(a, b)) if pair[0] != pair[1]), min(len(a), len(b)))
                raise AssertionError(f'run {index} {field} differs at {at}: dewy {a[max(0, at - 80):at + 160]!r} jo {b[max(0, at - 80):at + 160]!r}')
    stdout = [run[0] for run in outputs[0]]
    return stdout[0] if len(stdout) == 1 else stdout
