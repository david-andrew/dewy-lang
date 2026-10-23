"""load_value gives the default when nothing is kept, and a TextError when what is kept does
not read back (copied to name.bad first), never a silent default."""
import os
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)

PROGRAM = '''Settings:type=[volume:float64=0.5 name:string="x"]
main=()=>{
    printl(load_value("settings" Settings[]))
    save_data("settings" "Settings(volume=");
    let broken=load_value("settings" Settings[])
    if broken is? TextError printl"error: {broken.message}" else printl(broken)
    printl(load_data("settings.bad") ?? "none")
    save_value("settings" Settings[volume=0.9]);
    printl(load_value("settings" Settings[]))
}
'''


def test_load_value_reports_unreadable_data(compiler, tmp_path):
    source = tmp_path / 'settings.dewy'
    source.write_text(PROGRAM)
    binary = tmp_path / 'settings'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    env = dict(os.environ, SLOPPY_SAVE_DIR=str(tmp_path / 'saves'))
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, env=env, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == [
        '[volume=0.5 name="x"]',
        "error: volume: expected a number",
        'Settings(volume=',
        '[volume=0.9 name="x"]',
    ]
    assert ran.stderr == ''
