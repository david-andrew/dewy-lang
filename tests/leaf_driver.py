"""Build a live leaf driver once and run each input in a fresh process."""
import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from tests import leaf_oracle, whole_oracle
from tests.compiler_modules import module_text
from tests.driver_cache import build_driver
from tests.module_redirects import module_rewriter
from tests.selfhost_effect_double import effect_services
from tests.support import ROOT


@dataclass(frozen=True)
class LeafDriver:
    binary: Path
    # (a whole-compiler graph prints program images; its oracle is the program's own behaviour)
    probe: bool = True

    def compare(self, arguments=(), status=0, *, with_stderr=False):
        ran = subprocess.run([self.binary, *arguments], capture_output=True, timeout=60, check=False)
        assert ran.returncode == status, ran.stdout[-6000:] + ran.stderr
        output = ran.stdout + ran.stderr if with_stderr else ran.stdout
        if self.probe:
            leaf_oracle.check(arguments, status, output)
        else:
            leaf_oracle.check_entry(lambda: self.whole_outcome(arguments, ran))
        return output

    @staticmethod
    def whole_outcome(arguments, ran):
        """A whole compiler run as `build SOURCE -o TARGET ...` prints its output, then the program image."""
        if len(arguments) < 4 or arguments[0] != 'build' or arguments[2] != '-o':
            # (another command: the directory of the first file it names outside the checkout is the test's)
            named = [Path(a) for a in arguments if os.path.isabs(a) and not Path(a).is_relative_to(ROOT)]
            return whole_oracle.build(arguments, ran.returncode, ran.stdout, ran.stderr, (),
                                      named[0].parent if named else None)
        target = Path(arguments[3])
        files = whole_oracle.outputs(target)
        image = target.read_bytes() if target in files else b''
        stdout = ran.stdout.removesuffix(image + b'\n') if image else ran.stdout
        return whole_oracle.build(arguments, ran.returncode, stdout, ran.stderr, files, target.parent)


def build_leaf_driver(compiler, release, driver, extra_stems=(), doubles=None, jo_doubles=None, *, services):
    # doubles: {stem: {extension: text}}, modules standing in for compiler ones; jo_doubles:
    # {file: text}, Jo modules a Dewy module imports by file name, in both builds.
    # Supply the resolver's direct services to every derived leaf driver.
    arguments = getattr(jo_doubles, 'arguments', ())
    if arguments:
        driver = jo_doubles.runtime_driver(driver)
    jo_doubles = dict(jo_doubles or {})
    # (a whole compiler supplies every service itself)
    for module, functions in () if 'main.jo' in jo_doubles else services.items():
        text = jo_doubles.get(module, "use 'driver.jo'\nuse 'checker_resolve.dewy'\n")
        if module == 'effects.jo' and 'struct EffectSummary:' in text:
            continue
        for name, definition in functions.items():
            if not re.search(r'(?m)^' + re.escape(name) + r'\s*=', text):
                text += definition + '\n'
        if "use 'checker_resolve.dewy'" not in text:
            text = "use 'checker_resolve.dewy'\n" + text
        if "use 'driver.jo'" not in text:
            text = "use 'driver.jo'\n" + text
        jo_doubles[module] = text
    doubles = doubles or {}
    stems = ('node_store', 'source_types', 'checker_types', 'checker_state', 'checker_tokens',
             'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries',
             'type_intern', 'type_inference', 'type_constructors', 'type_labels',
             'type_unions', 'checker_alias', 'checker_resolve', 'checker_coerce') + tuple(doubles) + extra_stems
    # Snapshot behavior is exercised by the full compiler differential. Other
    # leaf drivers have no marked literal blocks and need only its interface.
    if 'literal_snapshots' not in stems and 'main.jo' not in jo_doubles:
        jo_doubles.setdefault('literal_snapshots.dewy',
            'literal_snapshot_context=(_block:int64 _expected:int64):>void=>{return}\n'
            'literal_snapshot_argument=(_block:int64):>int64=>0\n'
            'literal_sequence_context=(_block:int64 _expected:int64):>void=>{return}\n')
        jo_doubles.setdefault('literal_snapshots.jo',
            'literal_snapshot_context = (block: int, expected: int): return\n'
            'literal_snapshot_argument = (block: int) -> int: 0\n'
            'literal_sequence_context = (block: int, expected: int): return\n')
    # General value-parameter behavior is covered by whole-compiler twins.
    # Isolated resolver drivers have no integer-bound type symbols.
    if 'type_value_arguments' not in stems and 'main.jo' not in jo_doubles:
        jo_doubles.setdefault('type_value_arguments.dewy',
            'parameterized_array_type=(_node:int64 _element:int64):>int64=>0\n'
            'integer_parameter_literal=(_node:int64):>int64=>0\n'
            'integer_parameter_type=(_node:int64):>int64=>0\n')
        jo_doubles.setdefault('type_value_arguments.jo',
            'parameterized_array_type = (node: int, element: int) -> int: 0\n'
            'integer_parameter_literal = (node: int) -> int: 0\n'
            'integer_parameter_type = (node: int) -> int: 0\n')
    sources = tuple((f'{stem}.dewy', doubles[stem]['dewy'] if stem in doubles else
                     module_text(ROOT / f'compiler/{stem}.dewy')) for stem in stems)
    modules = _graph(stems, sources, tuple(jo_doubles.items()), driver)
    return LeafDriver(build_driver(compiler, modules, release), 'main.jo' not in jo_doubles)


@lru_cache(maxsize=64)
def _graph(stems, sources, jo_doubles, driver):
    jo_doubles = dict(jo_doubles)
    rewrite = module_rewriter(effect_services, jo_doubles)
    modules = {name: rewrite(text) for name, text in sources}
    modules.update((name, rewrite(text)) for name, text in jo_doubles.items())
    # Control-storage joins are host context in isolated checker drivers;
    # full compiler differentials cover their lexical and DA integration.
    if 'scope_joins' not in stems:
        modules['scope_joins.dewy'] = ('scope_join_begin=(n:int64):>int64=>0\n'
                                       'scope_join_end=(n:int64 state:int64 t:int64):>void=>{}\n'
                                       'scope_join_decl=(s:int64 l:int64 t:int64):>void=>{}\n'
                                       'scope_join_pattern=(s:int64):>void=>{}\n'
                                       'scope_call_alias=(n:int64 name:int64 symbol:int64 local:int64):>int64=>name\n'
                                       'scope_call_owns=(t:int64):>bool=>false\n'
                                       'scope_call_prepare=(n:int64):>int64=>n\n')
        modules['scope_joins.jo'] = ('scope_join_begin = (n: int) -> int: 0\n'
                                     'scope_join_end = (n: int, state: int, t: int): pass\n'
                                     'scope_join_decl = (s: int, l: int, t: int): pass\n'
                                     'scope_join_pattern = (s: int): pass\n'
                                     'scope_call_alias = (n: int, name: int, symbol: int, local: int) -> int: name\n'
                                     'scope_call_owns = (t: int) -> bool: false\n'
                                     'scope_call_prepare = (n: int) -> int: n\n')
    modules['driver.jo'] = ''.join(f"use '{s}.dewy'\n" for s in stems) + driver
    return modules
