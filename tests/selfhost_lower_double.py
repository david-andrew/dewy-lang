"""Link one lowering leaf or its twin against the real compiler services."""
import json

from tests.compiler_modules import compiler_modules
from tests.driver_cache import build_driver


class CompilerModules(dict):
    """Compiler sources plus the invocation supplied to each fresh driver process."""

    def __init__(self, modules, source, output, flags):
        super().__init__(modules)
        self.arguments = ('build', str(source), '-o', str(output), *flags)

    def runtime_driver(self, driver):
        # Paths are inputs to the compiler being tested, not inputs to its build.
        for index in (2, 4):
            driver = driver.replace(json.dumps(self.arguments[index - 1]), f'args()[{index}]')
        return driver


def cached_driver(compiler, tmp_path, release, modules):
    """The driver built from this module graph, reused from the persistent cache (tests/driver_cache.py).

    The key hashes the entire supplied graph, including service doubles and the driver, with the
    compiler and library. A changed leaf body therefore cannot reuse its previous executable.
    Runtime inputs and outputs stay in each test's own directory and are never cached.
    """
    return build_driver(compiler, modules, release)


def modules_for(source, output, leaf="lower_group", flags=()):
    return CompilerModules(compiler_modules(leaf), source, output, flags)
