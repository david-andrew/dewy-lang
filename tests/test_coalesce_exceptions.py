"""`??` gives its fallback for none and for every exception value (`to_int(text) ?? 0`),
and the editor says which failures each `??` covers."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def test_editor_names_the_failures_covered(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>{\n    printl(to_int("12") ?? 0)\n    printl("a=b".find("=") ?? -1)\n}\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 0 and ran.stdout == '12\n1\n', ran.stdout + ran.stderr
    ide = subprocess.run([compiler, 'lsp', '--dump', source], capture_output=True, text=True, timeout=60, check=False)
    infos = [line for line in ide.stdout.splitlines() if line.startswith('I\t')]
    assert any('?? gives the fallback for NotAnInteger, TooManyDigits' in line for line in infos), ide.stdout + ide.stderr
    assert any('?? gives the fallback for Missing' in line for line in infos), ide.stdout + ide.stderr
