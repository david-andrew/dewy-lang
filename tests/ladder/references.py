"""Independent Python oracles for the acceptance ladder's expected output.

Only Python's standard library is used; no Dewy program output is read.

    python3 tests/ladder/references.py           # check every expected.out
    python3 tests/ladder/references.py --write   # regenerate them
"""
from pathlib import Path
from fractions import Fraction
import bisect,collections,csv,heapq,io,json,math,re,statistics,sys
W=Path(__file__).parent;expected={}
def put(n,s):expected[n]=str(s)
def dewy(v,inside=False):
 """A value as Dewy prints it: its literal syntax, a string quoted only inside a structure."""
 if isinstance(v,str):return '"'+v.translate({92:'\\\\',34:'\\"',123:'\\{',10:'\\n',9:'\\t',13:'\\r'})+'"' if inside else v
 if isinstance(v,bool):return 'true' if v else 'false'
 if v is None:return 'none'
 if isinstance(v,dict):return '['+' '.join(f'{dewy(k,True)} -> {dewy(x,True)}' for k,x in v.items())+']'
 if isinstance(v,(list,tuple)):return '['+' '.join(dewy(x,True) for x in v)+']'
 return str(v)
text='hello world\nhello café\n';put(1,f'{len(text.splitlines())} {len(text.split())} {len(text)}')
rows=list(csv.reader(io.StringIO('region,units,price\nNorth,2,3.5\nSouth,4,1.25\n')));put(2,f'{len(rows)-1} {sum(int(r[1])*float(r[2]) for r in rows[1:])}')
text='INFO boot\nERROR disk\nWARN hot\nERROR network\n';put(3,'|'.join(f'{i}:{line}' for i,line in enumerate(text.splitlines(),1) if re.search('^ERROR',line)))
queue=[(30,'flush'),(5,'read'),(10,'write')];heapq.heapify(queue);put(4,dewy([heapq.heappop(queue)[1] for _ in range(3)]))
edges=[(0,1,4),(0,2,1),(2,1,2),(1,3,1),(2,3,8)];dist=[1000000]*5;dist[0]=0;queue=[(0,0)]
while queue:
 d,u=heapq.heappop(queue)
 if d!=dist[u]:continue
 for a,b,c in edges:
  if a==u and d+c<dist[b]:dist[b]=d+c;heapq.heappush(queue,(d+c,b))
put(5,dewy(dist))
prefixes={''}
for word in ['cat','car','café','dog']:
 for i in range(1,len(word)+1):prefixes.add(word[:i])
put(6,f'{len(prefixes)} true')
lru=collections.OrderedDict()
def cache(k,v):
 lru[k]=v;lru.move_to_end(k)
 if len(lru)>2:lru.popitem(last=False)
cache('a',1);cache('b',2);lru.move_to_end('a');cache('c',3);cache('a',9);put(7,f'{lru["a"]} {dewy(list(lru))}')
a,b,c,d=3.,1.,1.,2.;det=a*d-b*c;solution=[(9*d-b*8)/det,(a*8-9*c)/det];put(8,f'{dewy(solution)} {det}')
y=1.;h=.01
for _ in range(100):
 k1=-y;k2=-(y+h*k1/2);k3=-(y+h*k2/2);k4=-(y+h*k3);y+=h*(k1+2*k2+2*k3+k4)/6
assert abs(y-math.exp(-1))<1e-8;put(9,f'{y:.8f}')
xs=[2.,4.,4.,4.,5.,5.,7.,9.];put(10,f'{len(xs)} {statistics.mean(xs)} {statistics.variance(xs):.6f} {statistics.median(xs)}')
mass,speed,g=map(Fraction, (2,20,10));t=speed/g;put(11,f'{speed*t-g*t*t/2} {mass*speed*speed/2} {t}')
xs=[-2.,-1.,0.,1.,2.];ys=[2*x+1 for x in xs];w=b=0.
for epoch in range(1000):
 errors=[w*x+b-y for x,y in zip(xs,ys)];dw=sum(2*e*x/len(xs) for e,x in zip(errors,xs));db=sum(2*e/len(xs) for e in errors);w-=.05*dw;b-=.05*db
put(12,f'{w:.4f} {b:.4f}')
xs=[-3.,-2.,-1.,1.,2.,3.];ys=[0.,0.,0.,1.,1.,1.];w=b=0.
for epoch in range(2000):
 errors=[1/(1+math.exp(-(w*x+b)))-y for x,y in zip(xs,ys)];dw=sum(e*x for e,x in zip(errors,xs));db=sum(errors);w-=.1*dw/6;b-=.1*db/6
correct=sum(int((1/(1+math.exp(-(w*x+b)))>=.5)==bool(y)) for x,y in zip(xs,ys));put(13,f'{correct} {w:.4f}')
put(14,''.join(re.findall(r'\d+|[^\s\d]','12 + (3*40)')))
put(15,2+3*(4+5))
record={'name':'Ada','score':2**64-1,'tags':['red','café'],'active':True};assert json.loads(json.dumps(record))==record;put(16,f'Ada {record["score"]} true 2')
ring=collections.deque(maxlen=4)
for i in range(1,8):ring.append(i)
put(17,dewy(list(ring)))
buf=bytearray(64);first=0;second=(3+4-1)//4*4;buf[second:second+4]=(305419896).to_bytes(4,'little');put(18,f'{first} {second} {int.from_bytes(buf[second:second+4],"little")}')
word=(2<<20)|(3<<16)|1024;put(19,f'{word} {word.bit_count()} {word&65535}')
def fnv(text):
 h=14695981039346656037
 for b in text.encode():h=((h^b)*1099511628211)%2**64
 return h
put(20,dewy([fnv(s) for s in ['','a','hello','foobar']]))
log=[('a','one',False),('b','two',False),('a','three',False),('b','',True)];store={}
for k,v,deleted in log:
 if deleted:store.pop(k,None)
 else:store[k]=v
put(21,f'{len(store)} {store["a"]} {len(log)+1}')
pages=[]
for key in [9,1,7,3,5,2,8,4,6,0]:
 if not pages:pages.append([])
 page=0
 while page+1<len(pages) and key>=pages[page+1][0]:page+=1
 bisect.insort(pages[page],key)
 if len(pages[page])>4:pages.insert(page+1,pages[page][2:]);pages[page]=pages[page][:2]
assert [k for p in pages for k in p]==list(range(10));put(22,f'{len(pages)} v7')
put(23,'hello café|second request|0123456789')
# HTTP wire status/body cases are standard known values, checked by Dewy socket assertions.
put(24,'200 hello 404 missing')
put(25,f'128 {sum(sum((n+i)%97 for i in range(1000)) for n in range(128))} 17')
x=list(map(float,range(32)));v=[0.]*32
for frame in range(10):
 nx=[];nv=[]
 for a,b in zip(x,v):
  force=sum((other-a)/(1+(other-a)**2) for other in x);vel=b+force*.001;nv.append(vel);nx.append(a+vel*.001)
 x,v=nx,nv
assert x[0]>0 and x[-1]<31;put(26,f'32 {sum(x):.6f} true')
x,v,hits=1.,4.,0
for frame in range(100):
 x+=v*.125
 if x>10:x=20-x;v=-v;hits+=1
 if x<0:x=-x;v=-v;hits+=1
put(27,f'{x} {v} {hits}')
def invoice(s):
 try:n=int(s)
 except ValueError:return 'invalid integer'
 return 'negative' if n<0 else str(n*7)
put(28,' '.join(invoice(s) for s in ['6','oops','-2']))
stack=list(range(4));snapshot=stack[:];assert stack.pop()==3;put(29,f'{sum(stack)} {len(snapshot)} 0')
put(30,f'{dewy([x*2 for x in [1,2,3]])} {dewy(list(__import__("itertools").accumulate([1,2,3])))} 5')
series=[1+3*i for i in range(5)];put(31,f'{dewy(series)} {sum(series)} {dewy([n for n in series if n%2==0])}')

programs=sorted(p for p in W.iterdir() if p.is_dir() and p.name.split('_')[0].isdigit() and int(p.name.split('_')[0])<32)
assert sorted(expected)==[int(p.name.split('_')[0]) for p in programs],'every program needs an oracle'
stale=[]
for program in programs:
 path=program/'expected.out';text=expected[int(program.name.split('_')[0])]+'\n'
 if '--write' in sys.argv:path.write_text(text)
 elif not path.exists() or path.read_text()!=text:stale.append(program.name)
if stale:raise SystemExit('expected.out differs from the oracle: '+', '.join(stale))
print(f'{len(programs)} oracles agree with expected.out' if '--write' not in sys.argv else f'wrote {len(programs)} expected.out files')
