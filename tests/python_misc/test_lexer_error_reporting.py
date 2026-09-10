"""A local lexer error should not lay out the entire preceding token stream."""
import subprocess
import sys


def test_unclosed_quote_in_large_source_reports_promptly(tmp_path):
    path = tmp_path / 'unfinished.dewy'
    path.write_text('let value=7\n' * 4096 + '"unfinished')
    result = subprocess.run(
        [sys.executable, '-c',
         'import sys; from dewy.parser.t0 import tokenize; from dewy.reporting import SrcFile; tokenize(SrcFile.from_path(sys.argv[1]))',
         str(path)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 1, result.stderr
    assert 'Missing string closing quote' in result.stdout
    assert 'String opened here' in result.stdout
    assert len(result.stdout) < 10_000
