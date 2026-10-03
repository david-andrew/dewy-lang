"""Bounded proof probes; native-driver protocol matches bootstrap_program.dewy."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError

CASES = {
    "refined_index": "get=(xs:array<int64> i:addr<k => k <? xs.length>):>int64 => xs[i]",
    "guarded_word_nonzero": "divide=(d:int64):>int64 => {if d <=? 0 return 0 return 42 // d}",
    "guarded_bigint_nonzero": "divide=(d:bigint):>bigint => {if d <=? 0 return 0 return 42 // d}",
    "explicit_bigint_nonzero": "divide=(d:bigint):>bigint => {if d =? 0 return 0 return 42 // d}",
    "masked_hex_index": "digit=(h:uint64):>string => {let digits='0123456789abcdef' let i:uint64=h and 15 return digits[i]}",
    "modulo_hex_index": "digit=(h:uint64):>string => {let digits='0123456789abcdef' let i:uint64=h % 16 return digits[i]}",
    "mutable_parallel_lengths": "State:type=[xs:array<int64> ys:array<int64 length =? xs.length>]\nget=(s:State i:addr<k => k <? s.xs.length>):>int64 => s.ys[i]",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--native-driver", type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("use a scratch directory outside this recorded bundle")
    output.mkdir(parents=True, exist_ok=True)

    def normalize(text: str) -> str:
        plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
        return plain.replace(str(output), "<probe-output>").replace(str(ROOT), "<repo>")

    record = {
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python_version": sys.version,
        "scope": "acceptance through code generation; generated programs are not executed",
        "cases": {},
    }
    if args.native_driver:
        binary = args.native_driver.resolve()
        record["native_driver"] = {
            "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "fixture": "tests/fixtures/bootstrap_program.dewy",
        }
        manifest = binary.parent / "identity.json"
        if manifest.is_file():
            identity = json.loads(manifest.read_text())
            record["native_driver"]["cached_build_inputs_digest"] = identity["inputs"]
            record["native_driver"]["build_options"] = identity["options"]

    for name, body in CASES.items():
        text = body + "\nmain=():>int64 => 42\n"
        source = output / f"{name}.dewy"
        source.write_text(text)
        result = {"source": text}
        try:
            codegen(SrcFile.from_path(source), debug_locations=False)
        except (TypeCheckError, UserError) as error:
            result["hosted"] = {"accepted": False, "diagnostic": normalize(str(error))}
        else:
            result["hosted"] = {"accepted": True}
        if args.native_driver:
            native = subprocess.run(
                [binary, source, ROOT / "library", output / "prelude-cache"],
                capture_output=True, text=True, timeout=120,
            )
            if native.returncode not in (0, 1):
                raise RuntimeError(f"native probe {name} failed: {native.returncode}: {native.stderr}")
            result["native"] = {"accepted": native.returncode == 0, "returncode": native.returncode}
            if native.stderr:
                result["native"]["diagnostic"] = normalize(native.stderr)
        record["cases"][name] = result
        print(name, {backend: result[backend]["accepted"] for backend in ("hosted", "native") if backend in result}, flush=True)
    (output / "runtime_asserts.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
