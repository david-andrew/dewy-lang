"""Function policies override callers locally and restore on every return."""
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
def test_reachable_mains_override_and_restore_settings(compiler, tmp_path, flags, indirect):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nmain=()=>{\n$time.zone = \'UTC\'\n' +
        'printl($time.zone)\n' + ('lib.helper()' if indirect else 'lib.main()') +
        '\nprintl($time.zone)\n}\n',
        'helper=()=>main()\nmain=()=>{\n$time.zone = \'Asia/Tokyo\'\nprintl($time.zone)\n}\n')
    result = invoke(compiler, entry, flags=flags)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'UTC\nAsia/Tokyo\nUTC\n'


@pytest.mark.parametrize('inner', ["$time.zone = 'UTC'\n", ''])
@pytest.mark.parametrize('indirect', [False, True])
def test_reachable_mains_accept_matching_or_absent_settings(compiler, tmp_path, inner, indirect):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nmain=()=>{\n    $time.zone = \'UTC\'\n' +
        ('lib.helper()' if indirect else 'lib.main()') + '\n}\n',
        'helper=()=>main()\nmain=()=>{\n' + inner + 'printl($time.zone)\n}\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'UTC\n'


@pytest.mark.parametrize('header', [False, True])
def test_only_entry_configuration_is_active(compiler, tmp_path, header):
    tag = "$time.zone = 'UTC'\n"
    entry, library = files(tmp_path,
        (tag + '\n' if header else '') + 'import p"lib.dewy" as lib\n' +
        'main=()=>{\n' + ('' if header else tag) + 'printl(lib.shown)\n}\n',
        "shown=()=> $time.zone\nmain=()=>{\n    $time.zone = 'Asia/Tokyo'\nprintl(shown)\n}\n")
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
    'f=()=>printl(1)\nTAG\nmain=()=>f()\n',
    'main=()=>{\nif true TAG\n{printl(1)}\n}\n',
    'main=()=>{\nprintl(1)\nTAG\n}\n',
])
def test_program_settings_reject_misplacement(compiler, tmp_path, name, value, body):
    entry = tmp_path / 'app.dewy'
    entry.write_text(body.replace('TAG', f"${name} = '{value}'"))
    result = invoke(compiler, entry, 'check')
    assert result.returncode != 0
    assert 'top of' in result.stderr and ('file' in result.stderr or 'scope' in result.stderr), result.stderr


def test_entry_header_is_a_default_for_main(compiler, tmp_path):
    entry = tmp_path / 'app.dewy'
    entry.write_text("$time.zone = 'UTC'\nmain=()=>{\n$time.zone = 'Asia/Tokyo'\nprintl($time.zone)\n}\n")
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'Asia/Tokyo\n'


def test_main_rule_pack_reaches_runtime_zone_resolution(compiler, tmp_path):
    from tests.test_time_rules import make_pack
    make_pack(tmp_path)
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nmain=()=>{\n    $time.rules = \'test.bin\'\nprintl(lib.shown("Test/Zone"))\n}\n',
        '$time.rules = \'missing.bin\'\nshown=(text:string)=>zone(text)\nmain=()=>printl"test"\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'Test/Zone\n'


def test_main_host_rules_are_program_wide(compiler, tmp_path):
    entry, library = files(tmp_path,
        'import p"lib.dewy" as lib\nmain=()=>{\n    $time.zone_source = \'host\'\nprintl(lib.shown)\n}\n',
        "$time.zone_source = 'host'\nshown=()=> $time.zone_source\nmain=()=>printl(shown)\n")
    for path in [entry, library]:
        result = invoke(compiler, path)
        assert result.returncode == 0, result.stderr
        assert result.stdout == 'host\n'


def test_unreached_helper_does_not_activate_a_foreign_main(compiler, tmp_path):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nunused=()=>lib.main()\nmain=()=>{\n    $time.zone = \'UTC\'\nprintl"app"\n}\n',
        'main=()=>{\n    $time.zone = \'Asia/Tokyo\'\nprintl"library"\n}\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'app\n'


def test_recursive_call_restores_inner_main_policy(compiler, tmp_path):
    entry, _ = files(tmp_path,
        'import p"lib.dewy" as lib\nbridge=(n:int64):>void=>{\nif n >? 0 {bridge(n-1)} else {lib.main()}\n}\nmain=()=>{\n$time.zone = \'UTC\'\nbridge(1)\nprintl($time.zone)\n}\n',
        'main=()=>{\n$time.zone = \'Asia/Tokyo\'\nprintl($time.zone)\n}\n')
    result = invoke(compiler, entry)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'Asia/Tokyo\nUTC\n'
