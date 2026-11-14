"""Build a leaf's differential drivers once; execute every input in fresh processes."""
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from tests.compiler_modules import module_text
from tests.driver_cache import build_driver
from tests.module_redirects import module_rewriter
from tests.selfhost_effect_double import effect_services
from tests.support import ROOT


@dataclass(frozen=True)
class DriverPair:
    binaries: tuple

    def compare(self, arguments=(), status=0, *, with_stderr=False):
        outputs = []
        for binary in self.binaries:
            ran = subprocess.run([binary, *arguments], capture_output=True, timeout=60, check=False)
            assert ran.returncode == status, ran.stdout[-6000:] + ran.stderr
            outputs.append(ran.stdout + ran.stderr if with_stderr else ran.stdout)
        assert outputs[0] == outputs[1]
        return outputs[0]


def build_pair(compiler, release, driver, extra_stems=(), doubles=None, jo_doubles=None, *, services):
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
    binaries = []
    doubles = doubles or {}
    stems = ('node_store', 'source_types', 'checker_types', 'checker_state', 'checker_tokens',
             'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries',
             'type_intern', 'type_inference', 'type_constructors', 'type_labels',
             'type_unions', 'checker_alias', 'checker_resolve', 'checker_coerce') + tuple(doubles) + extra_stems
    sources = tuple((f'{stem}.{extension}', module_text(ROOT / f'compiler/{stem}.{extension}'))
                    for stem in stems if stem not in doubles for extension in ('dewy', 'jo'))
    variants = tuple((stem, (texts['dewy'], texts['jo'])) for stem, texts in doubles.items())
    for modules in _graphs(stems, extra_stems, variants, tuple(jo_doubles.items()), driver, sources):
        binaries.append(build_driver(compiler, modules, release))
    return DriverPair(tuple(binaries))


@lru_cache(maxsize=64)
def _graphs(stems, extra_stems, doubles, jo_doubles, driver, sources):
    sources = dict(sources)
    doubles = dict(doubles)
    jo_doubles = dict(jo_doubles)
    graphs = []
    rewrite = module_rewriter(effect_services, jo_doubles)
    for extension in ('dewy', 'jo'):
        modules = {}
        for stem in stems:
            if stem in doubles:
                text = doubles[stem][0 if extension == 'dewy' else 1]
            else:
                text = sources[f'{stem}.{extension}']
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            modules[f'{stem}.{extension}'] = rewrite(text)
        for name, text in (jo_doubles or {}).items():
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
                # Real Dewy services may also import the leaf under comparison.
                # Switch those edges too, so the graph has one implementation.
                for stem in extra_stems:
                    text = text.replace(f'p"{stem}.dewy"', f'p"{stem}.jo"')
            modules[name] = rewrite(text)
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
        modules['driver.jo'] = ''.join(f"use '{s}.{extension}'\n" for s in stems) + driver
        graphs.append(modules)
    return tuple(graphs)
