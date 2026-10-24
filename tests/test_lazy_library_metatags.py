"""A library module's lazily lexed bodies survive loading the directive bundles, which an
unknown or bundle metatag in it asks for: a bundle compiles, an unknown one is the
ordinary unknown-directive error."""
import os
import subprocess

from tests.support import ROOT, compiler

BODY = 'g = x => {\n    x * 2\n}\n'


def run(compiler, tmp_path, library):
    lib = tmp_path / 'lib'
    lib.mkdir()
    for entry in (ROOT / 'lib').iterdir():
        (lib / entry.name).symlink_to(entry)
    (lib / 'zz_lazy.dewy').write_text(library)
    main = tmp_path / 'main.dewy'
    main.write_text('import zz_lazy\nprintl(zz_lazy.g(3))\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env['DEWY_CORE_LIB'] = str(lib)
    built = subprocess.run([compiler, 'build', main, '-o', tmp_path / 'main'], env=env,
                           capture_output=True, text=True, timeout=120)
    if built.returncode:
        return built.returncode, built.stderr
    ran = subprocess.run([tmp_path / 'main'], capture_output=True, text=True, timeout=60)
    return ran.returncode, ran.stdout


def test_bundle_metatag(compiler, tmp_path):
    assert run(compiler, tmp_path, BODY + '$finite_floats\n') == (0, '6\n')


def test_unknown_metatag(compiler, tmp_path):
    code, err = run(compiler, tmp_path, BODY + '$bogus\n')
    assert code != 0 and 'unknown directive `$bogus`' in err and 'LazyBody' not in err
