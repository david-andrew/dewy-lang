"""Program-wide settings belong to the entry; reachable test mains must agree."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def invoke(compiler, entry, command='run', flags=()):
    return subprocess.run([compiler, command, entry, *flags], capture_output=True,
                          text=True, timeout=90)


def files(tmp_path, app, library):
    entry = tmp_path / 'app.dewy'
    entry.write_text(app)
    lib = tmp_path / 'lib.dewy'
    lib.write_text(library)
    return entry, lib


@pytest.mark.parametrize('flags', [(), ('--release',), ('--eager-bodies',)])
@pytest.mark.parametrize('indirect', [False, True])
def test_reachable_mains_reject_conflicting_settings(compiler, tmp_path, flags, indirect):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\n$time.zone = \'UTC\'\nmain=()=>{\n' +
        ('lib.helper()' if indirect else 'lib.main()') + '\n}\n',
        'helper=()=>main()\n$time.zone = \'Asia/Tokyo\'\nmain=()=>{\nprintl"library"\n}\n')
    result = invoke(compiler, entry, 'check', flags)
    assert result.returncode != 0
    for text in ['app.dewy:2', 'lib.dewy:2', "$time.zone = 'UTC'",
                 "$time.zone = 'Asia/Tokyo'", 'conflicts with']:
        assert text in result.stderr, result.stderr
    assert 'override' not in result.stderr


@pytest.mark.parametrize('inner', ["$time.zone = 'UTC'\n", ''])
@pytest.mark.parametrize('indirect', [False, True])
def test_reachable_mains_accept_matching_or_absent_settings(compiler, tmp_path, inner, indirect):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\n$time.zone = \'UTC\'\nmain=()=>{\n' +
        ('lib.helper()' if indirect else 'lib.main()') + '\n}\n',
        'helper=()=>main()\n' + inner + 'main=()=>{\nprintl($time.zone)\n}\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'UTC\n'


@pytest.mark.parametrize('header', [False, True])
def test_only_entry_configuration_is_active(compiler, tmp_path, header):
    tag = "$time.zone = 'UTC'\n"
    entry, library = files(tmp_path,
        (tag + '\n' if header else '') + 'import p"lib.dewy" as lib\n' +
        ('' if header else tag) + 'main=()=>{\nprintl(lib.shown)\n}\n',
        "shown=()=> $time.zone\n$time.zone = 'Asia/Tokyo'\nmain=()=>{\nprintl(shown)\n}\n")
    for path, expected in [(entry, 'UTC\n'), (library, 'Asia/Tokyo\n')]:
        result = invoke(compiler, path)
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected


@pytest.mark.parametrize('name,value', [('time.zone', 'Asia/Tokyo'),
                                       ('time.rules', 'missing.bin'),
                                       ('time.zone_source', 'host')])
def test_foreign_main_never_supplies_the_program_setting(compiler, tmp_path, name, value):
    entry, _ = files(tmp_path, 'import p"lib.dewy" as lib\nmain=()=>lib.main()\n',
        f"${name} = '{value}'\nmain=()=>{{\nprintl(${name} is? none)\n}}\n")
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'true\n'


@pytest.mark.parametrize('name,value', [('time.zone', 'UTC'), ('time.rules', 'missing.bin'),
                                       ('time.zone_source', 'host')])
@pytest.mark.parametrize('body', [
    'TAG\nf=()=>{\nprintl(1)\n}\nmain=()=>f()\n',
    'main=()=>{\nif true TAG\n{\nprintl(1)\n}\n}\n',
    'main=()=>{\nprintl(1)\nTAG\n}\n',
])
def test_program_settings_reject_other_scopes(compiler, tmp_path, name, value, body):
    entry = tmp_path / 'app.dewy'
    entry.write_text(body.replace('TAG', f"${name} = '{value}'"))
    result = invoke(compiler, entry, 'check')
    assert result.returncode != 0
    if 'printl(1)\nTAG' in body:
        assert 'needs a following construct; move it before' in result.stderr, result.stderr
    else:
        assert 'top of the entry file' in result.stderr, result.stderr
        assert "directly before any file's main" in result.stderr


def test_entry_header_and_main_must_agree(compiler, tmp_path):
    entry = tmp_path / 'app.dewy'
    entry.write_text("$time.zone = 'UTC'\n\n$time.zone = 'Asia/Tokyo'\nmain=()=>{\n}\n")
    result = invoke(compiler, entry, 'check')
    assert result.returncode != 0
    assert 'app.dewy:1' in result.stderr and 'app.dewy:3' in result.stderr
    assert 'conflicts with' in result.stderr


def test_main_rule_pack_is_program_wide(compiler, tmp_path):
    from tests.test_time_rules import make_pack
    make_pack(tmp_path)
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\n$time.rules = \'test.bin\'\nmain=()=>{\nprintl(lib.shown)\n}\n',
        'shown=()=>zone"Test/Zone"\n$time.rules = \'missing.bin\'\nmain=()=>{\nprintl"test"\n}\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'Test/Zone\n'


def test_main_host_rules_are_program_wide(compiler, tmp_path):
    entry, library = files(tmp_path,
        'import p"lib.dewy" as lib\n$time.zone_source = \'host\'\nmain=()=>{\nprintl(lib.shown)\n}\n',
        "shown=()=> $time.zone_source\n$time.zone_source = 'host'\nmain=()=>{\nprintl(shown)\n}\n")
    for path in [entry, library]:
        result = invoke(compiler, path)
        assert result.returncode == 0, result.stderr
        assert result.stdout == 'host\n'


def test_unreached_helper_does_not_activate_a_foreign_main(compiler, tmp_path):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nunused=()=>lib.main()\n$time.zone = \'UTC\'\nmain=()=>{\nprintl"app"\n}\n',
        '$time.zone = \'Asia/Tokyo\'\nmain=()=>{\nprintl"library"\n}\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'app\n'


def test_recursive_call_summary_reaches_a_conflicting_main(compiler, tmp_path):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nbridge=(n:int64):>void=>{\nif n >? 0 {bridge(n-1)} else {lib.main()}\n}\n$time.zone = \'UTC\'\nmain=()=>{\nbridge(1)\n}\n',
        '$time.zone = \'Asia/Tokyo\'\nmain=()=>{\nprintl"library"\n}\n')
    result = invoke(compiler, entry, 'check')
    assert result.returncode != 0
    assert 'conflicts with' in result.stderr, result.stderr
