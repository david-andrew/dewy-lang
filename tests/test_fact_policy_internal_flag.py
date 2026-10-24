"""The harness's fact policy is an internal flag the test tools pass, not an environment
setting: a variable left in a user's shell cannot change what a build means."""
import os
import subprocess

from tests.support import ROOT, compiler

CASE = ROOT / 'tests/cases/facts/policy_unknown.dewy'


def check(compiler, *options, env=None):
    return subprocess.run([compiler, *options, 'check', CASE], text=True, capture_output=True,
                          timeout=60, env={**os.environ, **(env or {})})


def test_environment_does_not_set_the_policy(compiler):
    result = check(compiler, env={'DEWY_INTERNAL_FACT_POLICY': 'require-static'})
    assert result.returncode == 0, result.stderr


def test_flag_sets_the_policy(compiler):
    result = check(compiler, '--internal-fact-policy=require-static')
    assert result.returncode != 0 and 'cannot prove divisor is nonzero' in result.stderr, result.stderr
