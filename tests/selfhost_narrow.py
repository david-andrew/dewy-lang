"""Build a Dewy leaf and its frozen twin with only the modules its services need."""
import subprocess

from tests.support import ROOT


def compare_narrow(compiler, tmp_path, release, stems, driver, doubles=None, run_in=None, status=0, observe=None):
    """Both builds' stdout, compared and returned. stems: real twinned modules; doubles: {file: text},
    Jo modules both builds use, or a `.dewy`/`.jo` pair; run_in(): a fresh working directory for each
    run; observe(directory): what else the two runs must agree on."""
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
        where = run_in() if run_in else None
        ran = subprocess.run([binary], capture_output=True, timeout=60, cwd=where)
        assert ran.returncode == status, ran.stdout[-3000:] + ran.stderr
        outputs.append((ran.stdout, ran.stderr, observe(where) if observe else None))
    assert outputs[0] == outputs[1]
    return outputs[0][0]
