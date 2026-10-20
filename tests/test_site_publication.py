"""Publication must reject unmeasured claims and broken deep links."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]

def script(name):
    key = 'publication_' + name
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, ROOT / 'site/scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def test_site_requires_explicit_example_intent(tmp_path):
    checker = script('check_dewy_examples')
    page = tmp_path/'lesson.md'
    page.write_text('```dewy\nprintl(42)\n```\n')
    with pytest.raises(ValueError, match='missing explicit'):
        checker.examples_in(page)
    with pytest.raises(ValueError, match='exact stdout'):
        checker.metadata('{"mode":"run"}', 'lesson:1')
    with pytest.raises(ValueError, match='diagnostic'):
        checker.metadata('{"mode":"reject"}', 'lesson:1')
    page.write_text('<!-- dewy-example: {"mode":"design-only"} -->\n```dewy\nunimplemented\n```\n')
    example, = checker.examples_in(page)
    assert example.metadata['mode'] == 'design-only'
    parser = checker.StaticExamples(page)
    with pytest.raises(ValueError, match='missing explicit'):
        parser.feed('<pre><code class="language-dewy">printl(42)</code></pre>')


def test_site_checks_exact_stdout_and_rejection(compiler, tmp_path):
    checker = script('check_dewy_examples')
    page = ROOT/'site/learn/src/00-introduction.md'
    example = checker.Example(page, 1, 'printl(42)\n', {'mode':'run','stdout':'42\n'})
    assert checker.validate(example, compiler, tmp_path)['executed']
    example.metadata['stdout'] = '43\n'
    with pytest.raises(ValueError, match='expected'):
        checker.validate(example, compiler, tmp_path)
    example.metadata = {'mode':'reject','diagnostic':'error'}
    with pytest.raises(ValueError, match='expected rejection'):
        checker.validate(example, compiler, tmp_path)
    example.source = 'let x:int64 = "text"\n'
    assert checker.validate(example, compiler, tmp_path)['checked']


def test_site_checks_fragments_redirect_targets_and_cycles(tmp_path):
    links = script('check_links')
    (tmp_path/'index.html').write_text('<a href="#old">old</a><a href="/other.html#caf%C3%A9">next</a><span id="old"></span>')
    (tmp_path/'other.html').write_text('<h1 id="café">OK</h1>')
    assert links.check(tmp_path) == []
    (tmp_path/'moved.html').write_text('<meta http-equiv="refresh" content="0; url=/other.html"><span id="retained"></span>')
    assert any('forwarded #retained' in error for error in links.check(tmp_path))
    (tmp_path/'moved.html').unlink()
    (tmp_path/'other.html').write_text('<h1>Missing anchor</h1>')
    assert any('missing fragment' in error for error in links.check(tmp_path))
    (tmp_path/'other.html').write_text('<meta http-equiv="refresh" content="0; URL=/absent/">')
    assert any('missing local target' in error for error in links.check(tmp_path))
    (tmp_path/'other.html').write_text('<meta http-equiv="refresh" content="0; url=/index.html">')
    (tmp_path/'index.html').write_text('<meta http-equiv="refresh" content="0; url=/other.html">')
    assert any('redirect cycle' in error for error in links.check(tmp_path))



def test_retired_installer_exits_without_mutation(tmp_path):
    retired = ROOT/'site/static/udewy/install.sh'
    result = subprocess.run(['sh',str(retired)],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode == 1
    assert 'retired' in result.stderr
    assert list(tmp_path.iterdir()) == []
