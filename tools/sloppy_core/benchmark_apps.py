"""Measure native or WebAssembly Dewy application workloads against C and an optional core baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from tools.sloppy_core.benchmark_compile import positive, sample_order

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / 'dewy/benchmarks/apps'
COUNTS = {'helpers': 2000000, 'arrays': 10000000, 'records': 1000000,
          'text': 10000000, 'graph': 1000000, 'string_equal': 10000000, 'match_dispatch': 10000000, 'branch_dispatch': 10000000,
          'managed_params': 10000000, 'method_params': 10000000, 'shifted_arrays': 100000, 'case_conversion': 20000, 'array_swap': 10000000, 'integer_parse': 2000000}
CHECKSUMS_1000 = {'helpers': 985290002, 'arrays': 876830114, 'records': 649125068,
                  'text': 681360428, 'graph': 740553269, 'string_equal': 171284, 'match_dispatch': 29443, 'branch_dispatch': 517766884,
                  'managed_params': 250508, 'method_params': 250508, 'shifted_arrays': 2100736000, 'case_conversion': 17080000, 'array_swap': 888753138, 'integer_parse': 33285884}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_identity(path: Path, compiler: Path, input_directory: Path | None = None) -> dict:
    """Keep the raw hash and isolate embedded toolchain paths without moving bytes.

    Native benchmark inputs are identical between variants. Their panic locations
    embed the compiler bundle's absolute path; masking only that exact prefix
    permits byte-for-byte comparison of all code, layout and other data.
    """
    data = path.read_bytes()
    prefix = str(compiler.resolve().parent.parent).encode()
    masked = data.replace(prefix, b'\0' * len(prefix))
    result = {'binary_sha256': hashlib.sha256(data).hexdigest(),
              'bundle_path': prefix.decode(), 'bundle_path_bytes': len(prefix),
              'occurrences': data.count(prefix),
              'masked_sha256': hashlib.sha256(masked).hexdigest()}
    if input_directory is not None:
        source_prefix = str(input_directory.resolve()).encode()
        result.update(input_directory=source_prefix.decode(), input_directory_bytes=len(source_prefix),
                      input_directory_occurrences=data.count(source_prefix),
                      canonical_sha256=hashlib.sha256(
                          masked.replace(source_prefix, b'\0' * len(source_prefix))).hexdigest())
    return result


def equivalent_artifact(left: dict, right: dict) -> bool:
    if left.get('binary_sha256') and left['binary_sha256'] == right.get('binary_sha256'):
        return True
    return bool(left.get('masked_sha256') and left['masked_sha256'] == right.get('masked_sha256')
                and left.get('bundle_path_bytes') == right.get('bundle_path_bytes')
                and left.get('occurrences', 0) > 0 and left['occurrences'] == right.get('occurrences'))


def equivalent_canonical_artifact(left: dict, right: dict) -> bool:
    """Compare separate runs, masking only equal-width bundle/input path prefixes."""
    return bool(left.get('canonical_sha256') and left['canonical_sha256'] == right.get('canonical_sha256')
                and isinstance(left.get('bundle_path_bytes'), int) and left['bundle_path_bytes'] > 0
                and left.get('bundle_path_bytes') == right.get('bundle_path_bytes')
                and left.get('occurrences', 0) > 0 and left['occurrences'] == right.get('occurrences')
                and isinstance(left.get('input_directory_bytes'), int) and left['input_directory_bytes'] > 0
                and left['input_directory_bytes'] == right.get('input_directory_bytes')
                and left.get('input_directory_occurrences') is not None
                and left['input_directory_occurrences'] == right.get('input_directory_occurrences'))


def artifact_representatives(identities: dict[str, dict]) -> dict[str, str]:
    representatives = []
    reused = {}
    for label, identity in identities.items():
        representative = next((other for other in representatives
                               if equivalent_artifact(identity, identities[other])), None)
        if representative is None:
            representatives.append(label)
        else:
            reused[label] = representative
    return reused


def prepare_source(name: str, directory: Path) -> Path:
    """Adapt only the platform harness and the old pointer-sized index spelling."""
    source = directory / f'{name}.dewy'
    source.write_text((APPS / f'{name}.dewy').read_text()
                      .replace('p"harness.dewy"', 'p"benchmark_harness.jo"')
                      .replace(':addr', ':int64'))
    shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', directory)
    return source


def prepare_clock(directory: Path, clock: str) -> dict[str, str]:
    """Use the same kernel clock in Dewy and C, retaining the original sources."""
    harness = directory / 'benchmark_harness.jo'
    c_header = (APPS / 'harness.h').read_text()
    if clock == 'thread-cpu':
        if platform.system() != 'Linux':
            raise RuntimeError('Thread CPU timing currently requires Linux')
        timer = '''clock = () -> int:
    ts: (int, int)
    if syscall(228, 3, &ts) != 0: panic("thread CPU clock unavailable")
    ts.0 * 1000000000 + ts.1'''
        original = harness.read_text()
        if original.count('clock = () -> int: time_ns()') != 1 or c_header.count('CLOCK_MONOTONIC') != 1:
            raise RuntimeError('Benchmark clocks changed; update the thread CPU adaptation')
        harness.write_text(original.replace('clock = () -> int: time_ns()', timer))
        c_header = c_header.replace('CLOCK_MONOTONIC', 'CLOCK_THREAD_CPUTIME_ID')
    elif clock != 'wall':
        raise ValueError(f'Unknown kernel clock: {clock}')
    (directory / 'harness.h').write_text(c_header)
    return {'dewy': digest(harness), 'c': digest(directory / 'harness.h')}


def run(command: list, env: dict) -> tuple[str, float]:
    started = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, timeout=120, check=False)
    elapsed = time.perf_counter() - started
    if result.returncode:
        raise RuntimeError(f'{command}:\n{result.stdout}{result.stderr}')
    return result.stdout, elapsed


def execute(binary: Path | list[str | Path], count: int, env: dict) -> tuple[int, dict]:
    command = binary if isinstance(binary, list) else [binary]
    output, elapsed = run([*command, str(count)], env)
    checksum, ns = map(int, output.split())
    if ns < 0:
        raise RuntimeError(f'{binary}: negative kernel time')
    return checksum, {'kernel_ns': ns, 'wall_seconds': elapsed}


def measure(compilers: dict[str, Path], workloads: list[str], samples: int,
            cc: str, count: int | None = None, clock: str = 'wall', mode: str = 'release',
            target: str = 'native', node: str = 'node', reuse_identical_artifacts: bool = False,
            on_progress: Callable[[dict], None] | None = None,
            unchanged_proof: Callable[[str, dict, dict], dict | None] | None = None) -> dict:
    if target == 'wasm' and clock != 'wall':
        raise ValueError('WebAssembly benchmarks require --clock wall; the thread CPU clock uses native syscalls')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    modes = ['default', 'release'] if mode == 'both' else [mode]
    target_flags = ['--target', 'wasm'] if target == 'wasm' else []
    runtime = None
    if target == 'wasm':
        node = shutil.which(node)
        if node is None:
            raise RuntimeError('Node is needed to benchmark WebAssembly; use --node /path/to/node')
        runtime = {'path': node, 'version': run([node, '--version'], env)[0].strip(),
                   'node_options': env.get('NODE_OPTIONS', ''),
                   'sampling': 'Every sample starts a fresh Node process. The discarded warmup warms '
                               'filesystem/host caches; JIT state does not persist between samples.'}
    variants = {label if mode != 'both' else f'{label}-{build_mode}':
                (label, [*target_flags, *([] if build_mode == 'default' else ['--release'])])
                for label in compilers for build_mode in modes}
    result = {
        'platform': platform.platform(),
        'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'load_average_start': os.getloadavg(),
        'samples': samples,
        'kernel_clock': clock,
        'warmups_per_binary': 1,
        'reuse_identical_artifacts': reuse_identical_artifacts,
        'sample_order': 'Rotating positions and direction; identical artifacts share explicitly labeled samples when enabled.',
        'mode': mode,
        'core_flags': [*target_flags, *([] if mode == 'default' else ['--release'])] if mode != 'both' else None,
        'target': target,
        'web_runtime': runtime,
        'variants': {label: {'compiler': compiler, 'flags': flags}
                     for label, (compiler, flags) in variants.items()},
        'emission_workers': 1,
        'cc': run([cc, '--version'], env)[0],
        'c_flags': ['-O2'],
        'compilers': {},
        'adaptations': ['Replace the platform harness import', 'Replace :addr with :int64'],
        'harness_sha256': digest(ROOT / 'tools/sloppy_core/benchmark_harness.jo'),
        'c_harness_sha256': digest(APPS / 'harness.h'),
        'workloads': {},
        'limits': [('WebAssembly under Node, compared with native C.' if target == 'wasm'
                    else 'Native 64-bit host.') + ' Warm filesystem caches; one build per binary.',
                   'C graph uses flat edges and a handwritten map; Dewy uses per-node arrays and an insertion-ordered map.',
                   'String equality uses separately allocated payloads; C uses pointer/length pairs and libc memcmp, Dewy uses runtime strings.',
                   'Kernel times exclude input generation; wall times include the complete process.',
                   ('Web kernel times include JIT work during the measured kernel; these are not browser rendering timings.'
                    if target == 'wasm' else
                    'Thread CPU timing excludes descheduling, but CPU frequency and cache contention still matter.')],
    }
    for label, compiler in compilers.items():
        identity = {'path': str(compiler), 'sha256': digest(compiler)}
        manifest = compiler.parent.parent / 'build.json'
        if manifest.exists():
            identity['build_manifest'] = json.loads(manifest.read_text())
        result['compilers'][label] = identity
    with tempfile.TemporaryDirectory(prefix='dewy-app-benchmark-') as directory:
        work = Path(directory)
        for name in workloads:
            source = prepare_source(name, work)
            result['measured_harness_sha256'] = prepare_clock(work, clock)
            c_source = work / f'{name}.c'
            shutil.copy2(APPS / c_source.name, c_source)
            binaries = {label: work / f'{name}-{label}' for label in [*variants, 'c']}
            builds = {}
            commands = {label: [binary] for label, binary in binaries.items()}
            runners = {}
            for label, (compiler, flags) in variants.items():
                _, elapsed = run([compilers[compiler], 'build', source, *flags, '-o', binaries[label]], env)
                builds[label] = elapsed
                if target == 'wasm':
                    artifact = binaries[label].with_suffix('.html')
                    scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script\s*>',
                                         artifact.read_text(), flags=re.DOTALL | re.IGNORECASE)
                    if not scripts or not any('const SLOPPY_WASM =' in script for script in scripts):
                        raise RuntimeError(f'{artifact}: generated WebAssembly script missing')
                    runner = binaries[label].with_suffix('.cjs')
                    runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts))
                    runners[label] = runner
                    commands[label] = [node, runner]
                    binaries[label] = artifact
            _, builds['c'] = run([cc, '-O2', c_source, '-o', binaries['c']], env)
            identities = {label: artifact_identity(binaries[label], compilers[compiler], work)
                          for label, (compiler, _) in variants.items()} if target == 'native' else {}
            reused = artifact_representatives(identities) if reuse_identical_artifacts else {}
            checksums = {}
            # Fast boundary/small-input comparison before the expensive measurements.
            for size in [0, 1, 17, 1000]:
                checks = {label: execute(command, size, env)[0] for label, command in commands.items()}
                if len(set(checks.values())) != 1:
                    raise RuntimeError(f'{name} count={size}: checksum mismatch {checks}')
                checksums[str(size)] = checks['c']
            size = count if count is not None else COUNTS[name]
            workload = {'count': size, 'source_sha256': digest(APPS / f'{name}.dewy'),
                        'adapted_source_sha256': digest(source), 'c_source_sha256': digest(c_source),
                        'artifact_identity': identities}
            proof = unchanged_proof(name, result, workload) if unchanged_proof is not None else None
            measured = {label: [] for label in binaries}
            labels = list(binaries)
            checksum = None
            for sample in range(1 if proof else samples + 1):
                # Every binary runs at full size once, even when its later timings
                # can be shared with a byte-equivalent representative.
                timed = [label for label in labels if sample == 0 or label not in reused]
                order = sample_order(timed, sample)
                for label in order:
                    actual, timing = execute(commands[label], size, env)
                    if checksum is None:
                        checksum = actual
                    if actual != checksum:
                        raise RuntimeError(f'{name} {label} count={size}: expected {checksum}, got {actual}')
                    if sample:
                        measured[label].append(timing)
                if sample:
                    for label, representative in reused.items():
                        measured[label].append(measured[representative][-1].copy())
            medians = {label: statistics.median(row['kernel_ns'] for row in rows) / 1e6 if rows else None
                       for label, rows in measured.items()}
            result['workloads'][name] = {
                **workload, 'checksum': checksum, 'preflight_checksums': checksums,
                'build_seconds': builds,
                'binary_sha256': {label: digest(binary) for label, binary in binaries.items()},
                'binary_bytes': {label: binary.stat().st_size for label, binary in binaries.items()},
                'timing_reused_from': {} if proof else reused,
                'unchanged_runtime_proof': proof,
                'runner_sha256': {label: digest(runner) for label, runner in runners.items()},
                'artifact_kind': {label: 'html' if label in runners else 'native' for label in binaries},
                'samples': measured, 'median_kernel_ms': medians,
                'median_wall_seconds': {label: statistics.median(row['wall_seconds'] for row in rows) if rows else None
                                        for label, rows in measured.items()},
            }
            if proof:
                print(name + ': verified unchanged runtime artifacts; all binaries passed full-size checks', flush=True)
            else:
                print(name + f' ({clock} kernel): ' + ', '.join(
                    f'{label} {ms:.2f} ms' + (f' (same artifact as {reused[label]})' if label in reused else '')
                    for label, ms in medians.items()), flush=True)
            if on_progress is not None:
                on_progress(result)
    result['load_average_end'] = os.getloadavg()
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--workload', choices=COUNTS, action='append', dest='workloads')
    cli.add_argument('--samples', type=positive, default=5)
    cli.add_argument('--count', type=positive, help='Override the input size for every selected workload')
    cli.add_argument('--cc', default='cc')
    cli.add_argument('--target', choices=['native', 'wasm'], default='native',
                     help='Core target; the C baseline always runs natively')
    cli.add_argument('--node', default='node', help='Node executable for --target wasm')
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='wall')
    cli.add_argument('--mode', choices=['default', 'release', 'both'], default='release',
                     help='Core build mode; both compares default and release with the same inputs')
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    if options.target == 'wasm' and options.clock != 'wall':
        cli.error('--target wasm requires --clock wall; thread-cpu uses native syscalls')
    compilers = {}
    if options.baseline:
        compilers['baseline'] = options.baseline.resolve(strict=True)
    compilers['candidate'] = options.compiler.resolve(strict=True)
    report = measure(compilers, options.workloads or list(COUNTS), options.samples, options.cc,
                     options.count, options.clock, options.mode, options.target, options.node)
    options.output.write_text(json.dumps(report, indent=2) + '\n')
