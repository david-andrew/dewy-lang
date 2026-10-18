import hashlib,json,os,statistics,tempfile,time
from pathlib import Path
from tests.python_misc import test_sloppy_core as gate
root=Path.cwd(); compiler=root/'__dewycache__/compact-core/build-1792311942096452923/bin/dewy-core'
os.environ['SLOPPY_EMIT_WORKERS']='1'
portable=[name for name in gate.CASES if name.startswith(('numeric-', 'record-', 'dictionary-', 'unpack-', 'generic-', 'rational-', 'bigint-', 'sequence-', 'fixed-array-', 'named-', 'coalesce-', 'compound-', 'default-reference-', 'constant-'))]
names=[portable[i*len(portable)//128] for i in range(128)]
original=gate.build_case_batch; builds=0

def counted(*a,**kw):
 global builds
 builds+=1
 return original(*a,**kw)
gate.build_case_batch=counted
report={'compiler':str(compiler),'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'names':names,'cases_per_round':512,'samples':{},'builds':{},'load_start':os.getloadavg()}
for sample in range(3):
 order=[[16,32,64],[64,32,16],[32,16,64]][sample]
 for size in order:
  builds=0; started=time.perf_counter()
  with tempfile.TemporaryDirectory(prefix='batch-size-') as tmp:
   base=Path(tmp)
   for target in ('native','wasm'):
    for release in (False,True):
     for start in range(0,len(names),size):
      directory=base/f'{target}-{release}-{start}'; directory.mkdir()
      selected=names[start:start+size]
      results=gate.run_value_batch(compiler,directory,{n:gate.CASES[n] for n in selected},release,target)
      assert all(code=='42' for code,_ in results.values()),results
  elapsed=time.perf_counter()-started
  report['samples'].setdefault(str(size),[]).append(elapsed);report['builds'].setdefault(str(size),[]).append(builds)
  print(sample,size,elapsed,builds,flush=True)
report['median_seconds']={k:statistics.median(v) for k,v in report['samples'].items()};report['load_end']=os.getloadavg()
(root/'__dewycache__/task-tmp/batch-size/results.json').write_text(json.dumps(report,indent=2)+'\n')
