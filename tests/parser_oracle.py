"""Whole-reader differentials (tools/compiler/parser_diff.py) held to recorded build outcomes.

Each source is built with the compiler that links the Dewy reader leaves; with the twin compiler too
(--leaf-oracle both|twin|capture) the two must agree on status, output and every emitted byte. Each
build's outcome is recorded as tests/whole_oracle.py does, in tests/fixtures/leaf_outputs/.
"""
from tests import leaf_oracle, whole_oracle
from tools.compiler import parser_diff


def build_pair(seed, work, release, **keywords):
    return parser_diff.build_pair(seed, work, release, twin=leaf_oracle.builds_twin(), **keywords)


def compare(pair, sources, work, release, workers):
    def observe(source, directory, run):
        arguments = ['build', source, '-o', directory / 'program', *(['--release'] if release else [])]
        files = sorted(p for p in directory.rglob('*') if p.is_file())
        outcome = whole_oracle.build(arguments, run.returncode, run.stdout, run.stderr, files, work)
        leaf_oracle.check_entry(lambda: outcome)

    return parser_diff.compare(pair, sources, work, release, workers, observe)
