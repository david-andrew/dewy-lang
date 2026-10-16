"""Build a source-level Dewy experiment against an untouched, pinned Sloppy core."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from udewy.cache import cache_artifact

PIN = '235e19a271bccad3fe72e36d03264807a632dc1b'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def build(sloppy_root: Path, dewy: Path, output: Path, sloppy_seed: Path | None = None) -> Path:
    sloppy_root, dewy, output = sloppy_root.resolve(), dewy.resolve(), output.resolve()
    seed = (sloppy_seed or sloppy_root / 'bin/sloppy').resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(['git', '-C', str(sloppy_root), 'archive', PIN,
                                       'compiler', 'lib', 'LICENSE'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(output, filter='data')
    binary_dir = output / 'bin'
    binary_dir.mkdir()
    work = output / 'parser-build'
    work.mkdir()
    source = HERE / 'parse.dewy'
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['DEWY_LIBRARY_ROOT'] = str(ROOT / 'library')
    result = subprocess.run([dewy, '-c', source], cwd=work, env=env,
                            capture_output=True, text=True, timeout=180, check=False)
    (output / 'parser-build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    parser = binary_dir / 'dewy-parse'
    shutil.copy2(work / cache_artifact(source, cwd=work), parser)
    adapter = output / 'compiler/dewy_parse.jo'
    shutil.copy2(HERE / 'dewy_parse.jo', adapter)
    original = output / 'compiler/parse.jo'
    text = original.read_text()
    anchor = 'parse_file = (file: int) -> int[]:\n'
    assert text.count(anchor) == 1
    text = "use 'dewy_parse.jo'\n" + text.replace(anchor, anchor + '''    if ends_with(files[file].path, ".dewy"):
        first = nodes.len()
        decls = dewy_parse_file(file)
        i = nodes.len() - 1
        loop i >= first:
            if nodes[i].kind == .loopx:
                lowered = desugar_loopx(i)
                nodes[i] = nodes[lowered]
            i -= 1
        return decls
''')
    original.write_text(text)
    checker = output / 'compiler/expr.jo'
    text = checker.read_text()
    anchor = 'finish_arg = (a: int, pt: int, is_mut: bool):\n'
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + '''    if is_mut and not has_flag(a, NF_MUT) and ends_with(files[pos_file(nodes[a].pos)].path, ".dewy"):
        fatal(nodes[a].pos, "a mutable argument needs `@` at the call site")
''')
    length_anchor = '        if is_soa(t): return check_soa_method(n, args[0], intern("len"), [], expected)\n'
    assert text.count(length_anchor) == 1
    text = text.replace(length_anchor, length_anchor + '''        if types[t].kind == .str_ and ends_with(files[pos_file(nodes[n].pos)].path, ".dewy"):
            fatal(nodes[n].pos, "Dewy core experiment does not yet support grapheme string length")
''')
    index_anchor = '        bk = types[bt].kind\n        b = int(nodes[n].b)\n'
    assert text.count(index_anchor) == 1
    text = text.replace(index_anchor, index_anchor + '''        if bk == .str_ and ends_with(files[pos_file(nodes[n].pos)].path, ".dewy"):
            fatal(nodes[n].pos, "Dewy core experiment does not yet support grapheme string indexing")
''')
    checker.write_text(text)
    binary = binary_dir / 'dewy-core'
    env = env | {'SLOPPY_LIB': str(output / 'lib'), 'SLOPPY_EMIT_WORKERS': '1'}
    result = subprocess.run([seed, 'build', output / 'compiler/main.jo', '-o', binary],
                            cwd=output, env=env, capture_output=True, text=True, timeout=180, check=False)
    (output / 'core-build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    identity = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'build.json').write_text(json.dumps({
        'sloppy_revision': PIN, 'sloppy_seed_sha256': identity(seed),
        'dewy_seed_sha256': identity(dewy), 'parser_sha256': identity(parser),
        'adapter_sha256': identity(adapter), 'core_sha256': identity(binary),
        'parser_source_sha256': identity(source), 'patched_parser_sha256': identity(original),
        'patched_checker_sha256': identity(checker),
    }, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sloppy-root', type=Path, required=True)
    parser.add_argument('--dewy', type=Path, required=True)
    parser.add_argument('--sloppy-seed', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.sloppy_root, args.dewy, args.output, args.sloppy_seed))
