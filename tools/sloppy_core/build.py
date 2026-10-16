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


def build(sloppy_root: Path, dewy: Path, output: Path, sloppy_seed: Path | None = None,
          *, bootstrap: bool = False) -> Path:
    sloppy_root, dewy, output = sloppy_root.resolve(), dewy.resolve(), output.resolve()
    seed = (sloppy_seed or sloppy_root / 'bin/sloppy').resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(['git', '-C', str(sloppy_root), 'archive', PIN,
                                       'compiler', 'lib', 'stage0', 'LICENSE', 'NOTICE'])
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
    env = env | {'SLOPPY_LIB': str(output / 'lib'), 'SLOPPY_EMIT_WORKERS': '1'}
    bootstrap_hashes = []
    if bootstrap:
        # The C implementation supports the bootstrap subset, so first build
        # pristine Sloppy, then use it for the Dewy adapter and core.
        stage0 = output / 'stage0/sloppy0'
        first = binary_dir / 'sloppy-bootstrap'
        commands = [
            ['make', '-s', '-C', str(output / 'stage0')],
            [str(stage0), str(output / 'compiler/main.jo'), '-o', str(first)],
        ]
        for index, command in enumerate(commands):
            result = subprocess.run(command, cwd=output, env=env, capture_output=True,
                                    text=True, timeout=180, check=False)
            (output / f'bootstrap-{index}.log').write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
        bootstrap_hashes = [hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in (stage0, first)]
        seed = first
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
    arithmetic_anchor = '    if is_lit(a) and is_lit(b) and not is_cmp:\n'
    assert text.count(arithmetic_anchor) == 1
    text = text.replace(arithmetic_anchor, '''    if op == .slash and is_int(ta) and is_int(tb) and ends_with(files[pos_file(nodes[n].pos)].path, ".dewy"):
        fatal(nodes[n].pos, "Dewy core experiment does not yet support integer /; use // or convert to float64")
''' + arithmetic_anchor)
    empty_anchor = '    else if k == .array:\n        et = 0\n'
    assert text.count(empty_anchor) == 1
    text = text.replace(empty_anchor, '''    else if k == .array:
        if nkids(n) == 0 and ex != 0 and is_map_type(ex) and ends_with(files[pos_file(nodes[n].pos)].path, ".dewy"):
            nodes[n].kind = .map_lit
            return check_expr(n, expected)
        et = 0
''')
    checker.write_text(text)
    lsp = output / 'compiler/lsp.jo'
    text = lsp.read_text()
    format_anchor = 'on_formatting = (id: int, params: int) -> int:\n    d = text_params_doc(params)\n    if d < 0: return lsp_reply(id, "null")\n'
    assert text.count(format_anchor) == 1
    text = text.replace(format_anchor, format_anchor + '    if ends_with(docs[d].path, ".dewy"): return lsp_reply(id, "[]")\n')
    discovery_anchor = '        if ends_with(n, ".jo"): ws_files.push(full)\n'
    assert text.count(discovery_anchor) == 1
    text = text.replace(discovery_anchor, '        if ends_with(n, ".jo") or ends_with(n, ".dewy"): ws_files.push(full)\n')
    lsp.write_text(text)
    formatter = output / 'compiler/fmt.jo'
    text = formatter.read_text()
    format_anchor = 'fmt_main = (a: str[]):\n'
    assert text.count(format_anchor) == 1
    text = text.replace(format_anchor, format_anchor + '''    loop path in a[2..):
        if ends_with(path, ".dewy"):
            eprint("Dewy formatting is not implemented in this core experiment")
            exit(2)
''')
    formatter.write_text(text)
    binary = binary_dir / 'dewy-core'
    result = subprocess.run([seed, 'build', output / 'compiler/main.jo', '-o', binary],
                            cwd=output, env=env, capture_output=True, text=True, timeout=180, check=False)
    (output / 'core-build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    if bootstrap:
        first_core = binary_dir / 'dewy-core-bootstrap'
        binary.rename(first_core)
        bootstrap_hashes.append(hashlib.sha256(first_core.read_bytes()).hexdigest())
        result = subprocess.run([first_core, 'build', output / 'compiler/main.jo', '-o', binary],
                                cwd=output, env=env, capture_output=True, text=True, timeout=180, check=False)
        (output / 'self-build.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    identity = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'build.json').write_text(json.dumps({
        'sloppy_revision': PIN, 'sloppy_seed_sha256': identity(seed),
        'dewy_seed_sha256': identity(dewy), 'parser_sha256': identity(parser),
        'adapter_sha256': identity(adapter), 'core_sha256': identity(binary),
        'parser_source_sha256': identity(source), 'patched_parser_sha256': identity(original),
        'patched_checker_sha256': identity(checker),
        'patched_lsp_sha256': identity(lsp), 'patched_formatter_sha256': identity(formatter),
        'bootstrap_generations_sha256': bootstrap_hashes,
    }, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sloppy-root', type=Path, required=True)
    parser.add_argument('--dewy', type=Path, required=True)
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument('--sloppy-seed', type=Path)
    seeds.add_argument('--bootstrap', action='store_true', help='build the core from the pinned independent C bootstrap')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.sloppy_root, args.dewy, args.output, args.sloppy_seed, bootstrap=args.bootstrap))
