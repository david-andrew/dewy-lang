"""Build a Dewy leaf and its frozen twin with only the modules its services need."""
import subprocess

from tests.support import ROOT


def compare_narrow(compiler, tmp_path, release, stems, driver, doubles=None, run_in=None, observe=None,
                   invocations=(((), 0),)):
    """The stdout of each invocation, compared across both builds. stems: real twinned modules;
    doubles: {file: text}, Jo modules both builds use, or a `.dewy`/`.jo` pair; invocations:
    (arguments, status) runs, each in run_in()'s working directory; observe(directory): what else
    those runs must agree on. A single invocation's stdout comes back alone."""
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for name, text in (doubles or {}).items():
            (directory / name).write_text(text.replace(".dewy'", ".jo'") if extension == 'jo' else text)
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            (directory / f'{stem}.{extension}').write_text(text.replace(".dewy'", ".jo'") if extension == 'jo' else text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        body = driver.replace(".dewy'", ".jo'") if extension == 'jo' else driver
        source.write_text(''.join(f"use '{stem}.{extension}'\n" for stem in stems) + body)
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
    assert outputs[0] == outputs[1]
    stdout = [run[0] for run in outputs[0]]
    return stdout[0] if len(stdout) == 1 else stdout
