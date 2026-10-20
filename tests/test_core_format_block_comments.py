"""The Dewy formatter keeps nestable #{ ... }# block comments exactly as written."""
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_CORE_COMPILER')
    if not path:
        pytest.skip('set DEWY_CORE_COMPILER for formatter checks')
    return Path(path).resolve(strict=True)


def fmt(compiler, text):
    result = subprocess.run([compiler, 'fmt', '-'], input=text, capture_output=True, text=True,
                            timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_block_comments_survive_layout(compiler):
    text = ('#{ header\n'
            '      indented   text  stays\n'
            '   #{ nested }#\n'
            '}#\n'
            'main=()=>{\n'
            'let a=1 #{ inline }# +2\n'
            '      #{ a comment\n'
            '  over lines, odd   indentation kept }#   let b=#{ before }#40\n'
            '#{ first }# printl(a+b)\n'
            'return 0 #{ trailing\n'
            '   continues }#\n'
            '}\n')
    expected = ('#{ header\n'
                '      indented   text  stays\n'
                '   #{ nested }#\n'
                '}#\n'
                'main = () => {\n'
                '    let a = 1 #{ inline }# +2\n'
                '    #{ a comment\n'
                '  over lines, odd   indentation kept }#   let b=#{ before }#40\n'
                '    #{ first }# printl(a+b)\n'
                '    return 0 #{ trailing\n'
                '   continues }#\n'
                '}\n')
    assert fmt(compiler, text) == expected
    assert fmt(compiler, expected) == expected


def test_block_comment_braces_do_not_count(compiler):
    text = 'main=()=>{\n#{ { ( [ }#\nreturn 0\n}\n'
    assert fmt(compiler, text) == 'main = () => {\n    #{ { ( [ }#\n    return 0\n}\n'
