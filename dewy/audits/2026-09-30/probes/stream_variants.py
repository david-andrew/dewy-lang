import argparse
import collections
import json
from pathlib import Path

from udewy.stream import Stream

parser = argparse.ArgumentParser(
    description="Record duplicate native UBC2 function bodies"
)
parser.add_argument("--ubc-3", type=Path, required=True)
parser.add_argument("--ubc-7", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()


class Capture:
    bytecode_target = "x86_64"

    def __init__(self):
        self.next_id = 0
        self.functions = {}
        self.active = None
        self.slot = 0

    def __getattr__(self, name):
        def invoke(*args, **kwargs):
            if name == "declare_function":
                result = self.next_id
                self.next_id += 1
                self.functions[result] = {
                    "name": args[0],
                    "parameters": args[1],
                    "body": [],
                }
                return result
            if name == "begin_function":
                self.active = args[0]
                self.slot = 0
                return None
            if name == "end_function":
                self.active = None
                return None
            if self.active is not None and name not in ("mark_location", "note_local"):
                self.functions[self.active]["body"].append((name, args, kwargs))
            if name == "alloc_local":
                result = self.slot
                self.slot += 1
                return result
            if name in ("function_ref", "string_ref", "static_ref"):
                return f"{name}:{args[0]}"
            if name.startswith(("declare_", "intern_")) or name in (
                "cond_and_split",
                "cond_or_split",
            ):
                result = self.next_id
                self.next_id += 1
                return result
            return None

        return invoke


results = []
for n in (3, 7):
    artifact = args.ubc_3 if n == 3 else args.ubc_7
    capture = Capture()
    Stream(artifact.read_bytes()).play(capture)
    groups = collections.defaultdict(list)
    for identifier, function in capture.functions.items():
        if function["parameters"] == 2:
            key = json.dumps(function["body"], sort_keys=True, default=repr)
            groups[key].append(identifier)
    repeated = sorted(groups.items(), key=lambda p: len(p[1]), reverse=True)
    results.append(
        {
            "lengths": n,
            "all_functions": len(capture.functions),
            "largest_identical_two_parameter_group": len(repeated[0][1]),
            "body": json.loads(repeated[0][0]),
            "identifiers": repeated[0][1],
        }
    )
    print(n, "largest identical group", len(repeated[0][1]), flush=True)
args.output.write_text(json.dumps(results, indent=2))
