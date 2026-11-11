"""`$dewy.version` says which Dewy a module means; named settings read at the call site."""
import os
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source, toolchain=None, name='main.dewy'):
    path = tmp_path / name
    path.write_text(source)
    environment = dict(os.environ)
    environment.pop('DEWY_TOOLCHAIN_VERSION', None)
    if toolchain:
        environment['DEWY_TOOLCHAIN_VERSION'] = toolchain
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False,
                          cwd=tmp_path, env=environment)


def test_version_reads_back(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$dewy.version = '0.1.0'\n\nprintl($dewy.version)\n")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '0.1.0\n'
    assert 'warning' not in ran.stderr


def test_development_toolchain_asks_nothing(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"hi"\n')
    assert ran.returncode == 0 and 'warning' not in ran.stderr, ran.stderr


def test_tagged_toolchain_warns_with_the_fix(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"hi"\n', toolchain='0.2.0')
    assert ran.returncode == 0, ran.stderr
    assert "add `$dewy.version = '0.2.0'` at the top" in ran.stderr


def test_tagged_toolchain_refuses_a_newer_version(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$dewy.version = '0.3.0'\n\nprintl\"hi\"\n", toolchain='0.2.0')
    assert ran.returncode != 0
    assert "newer than this toolchain (0.2.0)" in ran.stderr


def test_tagged_toolchain_takes_its_own_and_older(compiler, tmp_path):
    for version in ('0.2.0', '0.1.9'):
        ran = run(compiler, tmp_path, f'$dewy.version = \'{version}\'\n\nprintl"hi"\n', toolchain='0.2.0')
        assert ran.returncode == 0 and 'warning' not in ran.stderr, ran.stderr


def test_malformed_version(compiler, tmp_path):
    for version in ('0.1', '0.1.x', '1.2.3.4', ''):
        ran = run(compiler, tmp_path, f"$dewy.version = '{version}'\n\n")
        assert ran.returncode != 0
        assert 'three numbers in quotes' in ran.stderr


def test_version_is_a_module_setting(compiler, tmp_path):
    ran = run(compiler, tmp_path, '$dewy.version = \'0.1.0\'\nmain = () => {\n    printl"hi"\n}\n')
    assert ran.returncode != 0
    assert 'top of the module' in ran.stderr
    ran = run(compiler, tmp_path, "$dewy.version = '0.1.0'\n$dewy.version = '0.1.0'\n")
    assert ran.returncode != 0
    assert 'set twice' in ran.stderr


def test_edition_is_gone(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$edition = 2026\n")
    assert ran.returncode != 0
    assert 'edition' in ran.stderr


def test_not_inherited_by_modules(compiler, tmp_path):
    (tmp_path / 'other.dewy').write_text('printl"other"\n')
    ran = run(compiler, tmp_path, "$dewy.version = '0.2.0'\n\nimport p\"other.dewy\"\n", toolchain='0.2.0')
    assert ran.returncode == 0, ran.stderr
    assert 'other.dewy:1:1: warning' in ran.stderr
    assert 'main.dewy:1:1: warning' not in ran.stderr


READ = """f = (zone:string|none=$time.zone) => {
    match zone {
        name:string => printl"zone {name}"
        <none> => printl"no zone"
    }
}
"""


def test_default_reads_the_callers_setting(compiler, tmp_path):
    source = READ.replace("$time.zone", "$time.gap") + '$time.gap = \'next\'\ng = () => {\n    f\n}\nf\ng\nf("mine")\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'no zone\nzone next\nzone mine\n'


def test_module_setting_reaches_a_library_default(compiler, tmp_path):
    (tmp_path / 'lib.dewy').write_text(READ)
    source = "$time.zone = 'Asia/Tokyo'\n\nimport p\"lib.dewy\" as lib\nlib.f\n"
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'zone Asia/Tokyo\n'


def test_policy_settings_are_checked(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$time.gap = 'maybe'\n")
    assert ran.returncode != 0
    assert "'preserve_displacement'" in ran.stderr
    ran = run(compiler, tmp_path, "$time.fold = 'earlier'\n$time.gap = 'next'\nprintl\"ok\"\n")
    assert ran.returncode == 0, ran.stderr
