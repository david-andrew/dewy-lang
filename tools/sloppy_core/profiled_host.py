"""Sequential GCC profile-guided optimization for the optional compiler host."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from tools.sloppy_core.build import identity


def compiler_training(bundle: Path, work: Path) -> tuple[list[list[str]], dict[str, str]]:
    """Snapshot training examples, including relative imports, before profiling."""
    root = Path(__file__).resolve().parents[2]
    examples = work / 'training-examples'
    shutil.copytree(root / 'examples/sloppy_core', examples)
    cases = [(bundle / 'compiler/main.jo', False, 'linux'),
             (examples / 'reaction_field.dewy', False, 'linux'),
             (examples / 'reaction_field.dewy', True, 'linux'),
             (examples / 'paddle.dewy', False, 'wasm'),
             (examples / 'exact_rationals.dewy', False, 'linux'),
             (examples / 'pool_inventory.dewy', True, 'linux')]
    commands = []
    for index, (source, release, target) in enumerate(cases):
        command = [str(bundle / 'bin/dewy-core'), 'build', str(source),
                   '--target', target, '-o', str(work / f'training-{index}')]
        if release:
            command.append('--release')
        commands.append(command)
    hashes = {str(p.relative_to(work)): identity(p)
              for p in sorted(examples.rglob('*')) if p.is_file()}
    return commands, hashes


def compile_profiled_c(directory: Path, output: Path, cc: list[str],
                       commands: list[list[str]], env: dict[str, str], *,
                       expected_status: int = 0, lto: bool = False, optimization: int = 3) -> dict:
    """Collect fresh freestanding profiles, then build without instrumentation.

    Custom startup needs explicit counter registration and dumping. Streaming
    counters alone loses run summaries and can crash GCC's LTO profile reader.
    Counter correction handles inconsistent string-operation frequencies;
    source mismatches and missing profiles remain fatal. Training and final
    compilation use the same optimization level to preserve counter layouts.
    """
    from tools.sloppy_core.build_optimized_host import compile_c, run_command

    if optimization not in (2, 3):
        raise ValueError('Compiler-host optimization must be 2 or 3')
    if not commands:
        raise ValueError('Profile-guided builds need at least one training command')
    started = time.monotonic()
    work = directory.parent
    profiles = work / 'profiles'
    profiles.mkdir(exist_ok=False)
    header = directory / 'host.h'
    source = header.read_text()
    signature = 'static inline U sc('
    entry = '  register U r10'
    if source.count(signature) != 1 or source.count(entry) != 1:
        raise ValueError('Unrecognized compiler-host syscall wrapper')
    source = source.replace(signature, 'extern void dewy_host_profile_dump(void);\n' + signature)
    source = source.replace(entry, '  if (n == 60 || n == 231) dewy_host_profile_dump();\n' + entry)
    header.write_text(source)
    shutil.copy2(Path(__file__).with_name('c_host_profile.c'), directory / 'profile.c')
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if 'profile.c' in manifest['units']:
        raise ValueError('Compiler host was already instrumented')
    manifest['units'].append('profile.c')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    generate_flags = [f'-fprofile-generate={profiles}', '-fprofile-info-section=gcov_info',
                      '-DDEWY_PROFILE_GENERATE']
    instrumented = compile_c(directory, output, [*cc, *generate_flags], lto=lto, optimization=optimization)
    generation_logs = work / 'profile-generate-logs'
    generation_logs.mkdir()
    for log in directory.glob('*.log'):
        shutil.copy2(log, generation_logs / log.name)
    saved = output.with_name(output.name + '-instrumented')
    shutil.copy2(output, saved)
    gcov_dump = subprocess.check_output([*cc, '-print-prog-name=gcov-dump'],
                                        text=True, timeout=10).strip()
    gcov_version = subprocess.check_output([gcov_dump, '--version'], text=True, timeout=10).splitlines()[0]
    training = []
    training_env = {k: v for k, v in env.items() if not k.startswith('GCOV_')}
    for index, command in enumerate(commands):
        step = run_command(command, work / f'training-{index}.log', 120,
                           env=training_env, expected_status=expected_status)
        files = sorted(profiles.rglob('*.gcda'))
        if not files:
            raise ValueError(f'Training command did not write a profile: {command}')
        summary_log = work / f'training-{index}-profiles.log'
        run_command([gcov_dump, *map(str, files)], summary_log, 30, env=training_env)
        summaries = [(int(runs), int(maximum)) for runs, maximum in
                     re.findall(r'OBJECT_SUMMARY runs=(\d+), sum_max=(\d+)', summary_log.read_text())]
        if len(summaries) != len(files) or any(runs != index + 1 or maximum <= 0
                                              for runs, maximum in summaries):
            raise ValueError(f'Missing or inconsistent training run summaries: {summary_log}')
        training.append({**step, 'expected_status': expected_status,
                         'profile_count': len(files), 'accumulated_runs': index + 1,
                         'summaries_sha256': identity(summary_log)})
        print(f'Trained {index + 1}/{len(commands)}', flush=True)
    profile_hashes = {str(p.relative_to(profiles)): identity(p)
                      for p in sorted(profiles.rglob('*.gcda'))}
    if not profile_hashes:
        raise ValueError('Training produced no GCC profile data')
    use_flags = [f'-fprofile-use={profiles}', '-fprofile-correction', '-fprofile-partial-training',
                 '-Werror=coverage-mismatch', '-Werror=missing-profile']
    result = compile_c(directory, output, [*cc, *use_flags], lto=lto, optimization=optimization)
    return dict(result, pgo=True, seconds=time.monotonic() - started, profile_use_build=result,
                  profile_generate_flags=generate_flags, profile_use_flags=use_flags,
                  instrumented_build=instrumented, instrumented_binary_sha256=identity(saved),
                  gcov_dump=gcov_dump, gcov_version=gcov_version, training=training,
                  profile_data_sha256=profile_hashes)
