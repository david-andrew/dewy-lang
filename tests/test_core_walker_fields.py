"""Walks over every field of a node read a checked node's c and d only where they hold nodes.

A checked `for` keeps locals in c and d (its index and the iterable's snapshot) and a partial a
function instance in d; ast.jo's kid_c and kid_d skip them. `--internal-collide-locals` gives
each array or map loop's index local the loop's own node number, so a walk that reads the loop's
c as a node meets the loop again and overflows the stack, deterministically. The dogfood
programs built that way must still build and print what they print.
"""
import dataclasses
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)
from tools import cases


class CollidingRunner(cases.Runner):
    def build(self, source, output, mode):
        self.builds += 1
        return subprocess.run([str(self.compiler), '--internal-collide-locals', 'build', str(source), '-o', str(output),
                               *self.flags(mode)], cwd=output.parent, env=self.env, capture_output=True, text=True,
                              errors='replace', timeout=cases.BUILD_TIMEOUT, check=False)


def test_core_walker_fields(compiler, tmp_path):
    chosen = [dataclasses.replace(case, modes=('native',))
              for case in map(cases.parse, sorted((cases.CASES / 'dogfood').glob('*.dewy')))
              if 'native' in case.modes]
    runner = CollidingRunner(compiler, tmp_path, cases.clean_environment())
    outcomes = []
    for unit, mode, batch in cases.plan(chosen, node=False):
        if unit == 'value':
            outcomes += runner.value_batch(batch, mode)
        elif unit == 'panic':
            outcomes += runner.panic_batch(batch, mode)
        else:
            outcomes += runner.single(batch[0], mode)
    failed = [f'{outcome.case.name}: {outcome.message}' for outcome in outcomes if not outcome.ok]
    assert len(outcomes) == len(chosen) and not failed, '\n\n'.join(failed)
