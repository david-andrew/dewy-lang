import os,json
from pathlib import Path
builds=[]
def pytest_collection_modifyitems(items):
 seen=set()
 for item in items:
  if item.path.name!='test_sloppy_core.py' or id(item.module) in seen:continue
  seen.add(id(item.module));module=item.module
  module.VALUE_BATCH_SIZE=int(os.environ['MEASURE_BATCH_SIZE'])
  original=module.build_case_batch
  def counted(*a, _original=original, **kw):
   builds.append({'size':len(a[2]),'target':a[5],'release':a[4]})
   return _original(*a,**kw)
  module.build_case_batch=counted

def pytest_sessionfinish(session,exitstatus):
 worker=getattr(session.config,'workerinput',{}).get('workerid','controller')
 Path(os.environ['MEASURE_OUT']+'-'+worker+'.json').write_text(json.dumps(builds))
