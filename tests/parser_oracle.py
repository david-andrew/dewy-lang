"""Exercise the live reader against the recorded build and runtime outcomes."""
from tests import leaf_oracle, whole_oracle
from tools.compiler import parser_diff


def build_pair(seed, work, release):
    return (parser_diff.build_reader(seed, work, release),)


def compare(pair, sources, work, release, workers):
    def observe(source, directory, run):
        assert run.returncode in (0, 1) and b'panic:' not in run.stderr, (source, run.stderr)
        arguments = ['build', source, '-o', directory / 'program', *(['--release'] if release else [])]
        files = sorted(p for p in directory.rglob('*') if p.is_file())
        outcome = whole_oracle.build(arguments, run.returncode, run.stdout, run.stderr, files, work)
        leaf_oracle.check_entry(lambda: outcome)

    return parser_diff.compare(pair, sources, work, release, workers, observe)
