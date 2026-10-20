"""Machine-readable acceptance results retain failing programs and target identity."""
import json
from tools import ladder
from tests.support import compiler  # noqa: F401


def test_ladder_json_keeps_failures_and_target_identity(compiler, tmp_path, monkeypatch):
    doc = {'programs':{'01_example':{'milestone':1}}, 'milestones':{'1':'Example'}, 'design_passing':['01_example']}
    monkeypatch.setattr(ladder, 'load', lambda:doc)
    monkeypatch.setattr(ladder, 'validate', lambda doc:[])
    monkeypatch.setattr(ladder, 'has_core', lambda name:True)
    monkeypatch.setattr(ladder, 'evaluate', lambda compiler,directory,version,scratch,env,entry:
                        ladder.Result(directory.name,version,version=='core',version=='core',
                                      '' if version=='core' else 'example diagnostic'))
    output = tmp_path/'ladder.json'
    assert ladder.run(compiler,workers=1,json_output=output) == 1
    data = json.loads(output.read_text())
    assert data['target'] == 'native-release'
    assert len(data['revision']) == 40
    assert len(data['compiler_sha256']) == 64
    assert [(r['version'],r['ok']) for r in data['results']] == [('design',False),('core',True)]
    assert data['results'][0]['error'] == 'example diagnostic'
