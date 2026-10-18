import json,os,resource,subprocess,time,statistics
from pathlib import Path
root=Path.cwd();base=root/'__dewycache__/task-tmp/batch-size'
env={k:v for k,v in os.environ.items() if not k.startswith(('DEWY_','SLOPPY_'))}
env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',DEWY_CORE_COMPILER=str(root/'__dewycache__/compact-core/build-1792311942096452923/bin/dewy-core'),SLOPPY_EMIT_WORKERS='1',PYTHONPATH=str(base)+os.pathsep+str(root))
rows=[]
for round,size in enumerate((16,64,64,16)):
 env['MEASURE_BATCH_SIZE']=str(size)
 env['MEASURE_OUT']=str(base/f'builds-{round}-{size}')
 log=base/f'pytest-{round}-{size}.log';start=time.perf_counter();cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
 with log.open('w') as out:
  r=subprocess.run([root/'.venv/bin/python','-m','pytest','-q','-o','addopts=','--maxfail=1','-p','size_override','-p','xdist.plugin','-p','tools.sloppy_core.pytest_parallel','-n','2','--dist=loadgroup','tests/python_misc/test_sloppy_core.py','-k','test_core_values or test_core_value_web'],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=120,check=False)
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 row={'batch_size':size,'wall_seconds':time.perf_counter()-start,'cpu_seconds':after.ru_utime+after.ru_stime-cpu.ru_utime-cpu.ru_stime,'status':r.returncode,'summary':log.read_text().splitlines()[-1]}
 details=[]
 for file in base.glob(f'builds-{round}-{size}-gw*.json'):details.extend(json.loads(file.read_text()))
 assert details and max(d['size'] for d in details)==size,details
 row['build_count']=len(details);row['largest_batch']=max(d['size'] for d in details)
 rows.append(row); print(row,flush=True)
 if r.returncode:break
(base/'pytest-comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
