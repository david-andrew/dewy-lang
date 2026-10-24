"""An unannotated integer's covering set proves literal-union conversions (require-static)."""
import os
import subprocess

from tests.support import compiler  # noqa: F401

PROVED = '''set_level=(l:1|2|3)=>printl(l)
run=()=>{
    let level=1
    let bump=($capture @level)=>{level=3}
    loop i in [0..3) {set_level(level) bump()}
}
main=()=>run()
'''

OPEN = '''set_level=(l:1|2|3)=>printl(l)
run=()=>{
    let level=1
    let bump=($capture @level)=>{level+=1}
    loop i in [0..3) {set_level(level) bump()}
}
main=()=>run()
'''


def check(compiler, tmp_path, source):
    path = tmp_path / 'domain.dewy'
    path.write_text(source)
    return subprocess.run([compiler, '--internal-fact-policy=require-static', 'check', path], text=True, capture_output=True, timeout=30)


def test_int_domain_proves_conversion(compiler, tmp_path):
    result = check(compiler, tmp_path, PROVED)
    assert result.returncode == 0, result.stdout + result.stderr


def test_open_int_domain_still_needs_proof(compiler, tmp_path):
    result = check(compiler, tmp_path, OPEN)
    assert result.returncode != 0
    assert 'level <=? 3' in result.stdout + result.stderr
