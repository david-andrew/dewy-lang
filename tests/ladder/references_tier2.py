"""Independent stdlib-only oracles for ladder tier 2 (programs 32-63; oracle n is program n+31).
Never reads Dewy output. --write regenerates expected.out."""
from pathlib import Path
from collections import OrderedDict,deque,Counter
from fractions import Fraction
import base64,binascii,csv,hashlib,heapq,html,io,json,math,re,sqlite3,struct,sys,unicodedata
ROOT=Path(__file__).parent
ORACLES={}
def dewy(v,inside=False):
 """A value as Dewy prints it: its literal syntax, a string quoted only inside a structure."""
 if isinstance(v,str):return '"'+v.translate({92:'\\\\',34:'\\"',123:'\\{',10:'\\n',9:'\\t',13:'\\r'})+'"' if inside else v
 if isinstance(v,bool):return 'true' if v else 'false'
 if v is None:return 'none'
 if isinstance(v,dict):return '['+' '.join(f'{dewy(k,True)} -> {dewy(x,True)}' for k,x in v.items())+']'
 if isinstance(v,(list,tuple)):return '['+' '.join(dewy(x,True) for x in v)+']'
 return str(v)
def oracle(n):
    def register(f):ORACLES[n]=f;return f
    return register
@oracle(1)
def vm():
    # High-level recurrence, deliberately not an opcode interpreter.
    return f'{math.factorial(6)} 0 {math.prod(range(1,7))}'
@oracle(2)
def types():
    nodes=[('int',),('var','x'),('+',0,1),('==',2,0),('bool',),('and',3,4),('+',0,4),('var','missing'),('?',0,1)]
    def check(i,env):
        n=nodes[i]
        if n[0] in ('int','bool'):return n[0]
        if n[0]=='var':return env[n[1]]
        a,b=check(n[1],env),check(n[2],env)
        assert a==b
        if n[0]=='+':assert a=='int';return a
        if n[0]=='and':assert a=='bool';return a
        assert n[0]=='==';return 'bool'
    good=bad=0
    for i in range(len(nodes)):
        try:check(i,{'x':'int'});good+=1
        except (AssertionError,KeyError):bad+=1
    return f'{good} {bad}'
@oracle(3)
def regex():
    hits=[i+1 for i,(p,t) in enumerate((p,t) for p in ['a*b','.*','ab*','c*a*b','a.*c','a*a*a*b'] for t in ['','b','ab','aaab','ac','axxc','miss']) if re.fullmatch(p,t)]
    return f'{len(hits)} {sum(hits)}'
@oracle(4)
def btree():
    values=set(range(64));saved=values.copy()
    for i in range(48):values.remove(i*19%64)
    return f'{len(values)} {sum(values)} {len(saved)}'
@oracle(5)
def wal():
    records=[(1,10),(2,20),(1,30),(2,255),(3,40)]
    raw=b''.join(struct.pack('BBBB',4,k,v,(k+v+4)%256) for k,v in records)
    total=0
    for cut in range(len(raw)+1):
        state={}
        for offset in range(0,cut-3,4):
            _,k,v,c=struct.unpack('BBBB',raw[offset:offset+4])
            assert c==(k+v+4)%256
            if v==255:state.pop(k,None)
            else:state[k]=v
        total+=sum(k*100+v for k,v in state.items())
    return f'{len(raw)+1} {total} 2'
@oracle(6)
def query():
    db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE c(id,active); CREATE TABLE o(customer,region,units,price);')
    db.executemany('INSERT INTO c VALUES (?,?)',[(1,1),(2,0),(3,1)])
    db.executemany('INSERT INTO o VALUES (?,?,?,?)',[(1,'N',3,10),(3,'S',2,20),(2,'N',9,99),(1,'N',1,7),(3,'E',5,8),(9,'W',9,99),(1,'S',4,5)])
    rows=db.execute('SELECT region,sum(units*price),count(*) FROM o JOIN c ON c.id=o.customer WHERE active AND units>=2 GROUP BY region HAVING sum(units*price)>=20 ORDER BY 2 DESC,1').fetchall();db.close()
    return f'{len(rows)} {sum(r[1] for r in rows)} {sum(r[2] for r in rows)}'
@oracle(7)
def lru():
    c=OrderedDict();hits=total=0
    for i in range(2000):
        k=i*17%23;c[k]=i;c.move_to_end(k)
        if len(c)>8:c.popitem(last=False)
        k=i*7%23
        if k in c:hits+=1;total+=c[k];c.move_to_end(k)
    return f'{hits} {total} {next(iter(c))} {next(reversed(c))}'
@oracle(8)
def broadcast():
    a=[[1.,2.,3.],[4.,5.,6.]]
    b=[[x+[10,20,30][j]+[100,200][i] for j,x in enumerate(row)] for i,row in enumerate(a)]
    for row in b:row[1]*=2
    gram=[[sum((a[i][j]-sum(r[j] for r in a)/2)*(a[i][k]-sum(r[k] for r in a)/2) for i in range(2)) for k in range(3)] for j in range(3)]
    return f'{sum(map(sum,b)):.1f} {sum(map(sum,gram)):.1f} {sum(range(1,9))+2*sum(range(1,5)):.1f}'
@oracle(9)
def dual():
    # Closed-form derivative instead of dual propagation.
    def derivative(x):return ((math.cos(x)+3*x*x)*(1+x*x)-2*x*(math.sin(x)+x**3))/(1+x*x)**2
    return f'{sum(derivative(i/4) for i in range(-8,9)):.6f} {12.:.6f} {4+math.exp(3):.6f}'
@oracle(10)
def kmeans():
    points=[(c*20+i%5-2,c*10+i%4-1) for c in range(3) for i in range(40)]
    groups=[points[i*40:(i+1)*40] for i in range(3)]
    centers=[tuple(sum(p[j] for p in g)/len(g) for j in range(2)) for g in groups]
    loss=sum(sum((p[j]-centers[c][j])**2 for j in range(2)) for c,g in enumerate(groups) for p in g)
    return f'{centers[0][0]:.1f} {centers[1][1]:.1f} {centers[2][0]:.1f} {loss:.1f}'
@oracle(11)
def neural():
    # Reverse-mode graph evaluator; independent of the manually derived Dewy gradients.
    class V:
        def __init__(self,x,parents=()):self.x=x;self.parents=parents;self.g=0.
        def __add__(a,b):
            if not isinstance(b,V):b=V(b)
            return V(a.x+b.x,((a,1.),(b,1.)))
        def __mul__(a,b):
            if not isinstance(b,V):b=V(b)
            return V(a.x*b.x,((a,b.x),(b,a.x)))
        def tanh(a):
            t=math.tanh(a.x);return V(t,((a,1-t*t),))
    weights=[.3,-.2,.5,.4,-.7,.6,.1,-.3,.2,.2,-.4,.7,.05]
    def graph():
        p=[V(w) for w in weights];loss=V(0.)
        for x in [-1.,1.]:
            for y in [-1.,1.]:
                h=[(p[2*j]*x+p[2*j+1]*y+p[6+j]).tanh() for j in range(3)]
                out=p[12]
                for j in range(3):out=out+p[9+j]*h[j]
                e=out+(-x*y);loss=loss+e*e*.25
        return p,loss
    _,start=graph();initial=start.x
    for _ in range(800):
        params,loss=graph();seen=set();order=[]
        def visit(v):
            if id(v) in seen:return
            seen.add(id(v))
            for p,_ in v.parents:visit(p)
            order.append(v)
        visit(loss);loss.g=1.
        for v in reversed(order):
            for p,d in v.parents:p.g+=v.g*d
        weights=[w-.1*p.g for w,p in zip(weights,params)]
    _,end=graph();assert end.x<.01
    return f'{initial:.6f} {end.x:.6f} 4'
@oracle(12)
def fft():
    xs=[float(i*7%13) for i in range(64)]
    # Direct O(N^2) DFT, rather than butterflies/bit reversal.
    bins=[sum(x*complex(math.cos(-2*math.pi*k*j/64),math.sin(-2*math.pi*k*j/64)) for j,x in enumerate(xs)) for k in range(64)]
    return f'{bins[0].real:.3f} {sum(x*x for x in xs):.3f} {bins[1].real:.3f}'
@oracle(13)
def units():
    speed=Fraction(72*1000,3600);mass=Fraction(2);g=Fraction(10)
    peak=speed**2/(2*g);energy=mass*speed**2/2;impulse=mass*2*speed;distance=Fraction(90*1000,3600)*120
    return f'{float(peak):.3f} {float(energy):.3f} {float(impulse):.3f} {distance}'
@oracle(14)
def allocator():return f'{sum(range(16))*10-30} 777 1'
@oracle(15)
def ring():
    queue=deque(range(800));return f'{len(queue)} {sum(queue)} {len(queue)+2}'
@oracle(16)
def protocol():
    payload=bytes([0,1,127,128,255]);wire=b'DW'+struct.pack('>BHH',3,65530,len(payload))+payload
    wire+=bytes([sum(wire)%256])
    return f'{len(wire)} {2*len(wire)} {sum(wire)}'
@oracle(17)
def crc():
    data=bytes((i*37+11)%256 for i in range(1024));return f'{binascii.crc32(data)} {len(data)+1} {binascii.crc32(bytes([255]))}'
@oracle(18)
def sha():return '\n'.join(dewy(list(struct.unpack('>8I',hashlib.sha256(m).digest()))) for m in [b'abc',b'a'*1000,b'x'*56])
@oracle(19)
def b64():
    encoded=[base64.b64encode(bytes((i*53+n)%256 for i in range(n))) for n in range(130)]
    assert all(base64.b64decode(s,validate=True)==bytes((i*53+n)%256 for i in range(n)) for n,s in enumerate(encoded))
    return f'{len(encoded)} {sum(map(len,encoded))} {base64.b64encode(b"hello").decode()}'
@oracle(20)
def markdown():
    # Known block structure; standard HTML escaping with independent inline regexes.
    def inline(s):
        s=html.escape(s,quote=False)
        s=re.sub(r'`([^`]*)`',r'<code>\1</code>',s)
        return re.sub(r'\*\*([^*]*)\*\*',r'<strong>\1</strong>',s)
    return '<h1>'+inline('Dewy & tools')+'</h1><p>'+inline('A **bold** line with `<tag>`.')+'</p><ul><li>one</li><li>'+inline('**two**')+'</li></ul><p>'+html.escape('<script>')+'</p>'
@oracle(21)
def quoted_csv():
    text='name,note,amount\r\nAda,"a,b",12\r\n"B""ob","two\nlines",7\r\n,empty,0\r\n'
    rows=list(csv.reader(io.StringIO(text,newline=''),strict=True))
    return f'{len(rows)} {sum(map(len,rows))} {sum(int(r[2]) for r in rows[1:])}'
@oracle(22)
def unicode_wrap():
    # The fixed corpus has combining accents, ZWJ emoji, and paired regional indicators.
    def clusters(s):
        out=[];regional=0
        for c in s:
            ri=0x1f1e6<=ord(c)<=0x1f1ff
            if out and (unicodedata.combining(c) or c=='\u200d' or out[-1].endswith('\u200d') or (ri and regional%2)):
                out[-1]+=c
            else:out.append(c)
            regional=regional+1 if ri else 0
        return out
    words='café 👩‍💻 tools αβγδε 世界 hello'.split();lines=[];current=[]
    for word in words:
        cs=clusters(word)
        if current and len(current)+1+len(cs)<=5:current+=[' ']+cs;continue
        if current:lines.append(''.join(current));current=[]
        while len(cs)>5:lines.append(''.join(cs[:5]));cs=cs[5:]
        current=cs
    if current:lines.append(''.join(current))
    return '|'.join(lines)+f'\n{len(lines)} {sum(len(clusters(s)) for s in lines)} 3'
@oracle(23)
def reduce():
    xs=[i*37%101 for i in range(4097)]
    # Polynomial evaluation in modular arithmetic, independent of the merge tree.
    digest=sum(x*pow(257,len(xs)-1-i,2**64) for i,x in enumerate(xs))%2**64
    return f'{len(xs)} {sum(xs)} {digest}'
@oracle(24)
def pipeline():
    jobs=[(i,3*i) for i in range(200) if i%11]
    total=sum(sum((v+j)%97 for j in range(300)) for _,v in jobs)
    return f'{len(jobs)} {200-len(jobs)} {total} {sum(i for i,_ in jobs)}'
@oracle(25)
def ecs():
    # ID-keyed objects, not dense arrays/swap deletion.
    def entity(i):return [i%101,i%79,i%7-3,i%5-2]
    w={i:entity(i) for i in range(4096)}
    def checksum(w):return sum(i*13+x*7+y*3+vx+vy for i,(x,y,vx,vy) in w.items())
    initial=checksum(w)
    for frame in range(60):
        for i,p in w.items():
            p[0]+=p[2];p[1]+=p[3]
            if not 0<=p[0]<=100:p[2]=-p[2];p[0]+=2*p[2]
            if not 0<=p[1]<=78:p[3]=-p[3];p[1]+=2*p[3]
        if frame==20:w={i:p for i,p in w.items() if i%3}
        if frame==30:w.update({i:entity(i) for i in range(4096,4608)})
    return f'{len(w)} {checksum(w)} {initial}'
@oracle(26)
def astar():
    blocked={y*32+15 for y in range(31) if y!=17}|{10*32+x for x in range(1,30) if x!=8}
    q=deque([(0,0)]);seen={0}
    while q:
        u,d=q.popleft()
        if u==1023:return f'{d} 0 1023 0'
        x,y=u%32,u//32
        for nx,ny in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
            v=ny*32+nx
            if 0<=nx<32 and 0<=ny<32 and v not in blocked and v not in seen:seen.add(v);q.append((v,d+1))
    raise AssertionError('unreachable')
@oracle(27)
def rollback():
    ps=[[20,0,0],[80,0,0]];rng=12345
    for frame in range(180):
        rng=(rng*1664525+1013904223)%2**32
        for p,command in zip(ps,[frame%3-1,frame*7%3-1]):
            p[1]=max(-5,min(5,p[1]+command));p[0]+=p[1]
            if p[0]<0:p[0]=p[1]=0
            if p[0]>100:p[0]=100;p[1]=0
            if p[0]%13==rng%13:p[2]+=1
    h=rng
    for x,v,s in ps:h=(h*257+(x+v*100+s*1000)%2**64)%2**64
    h=(h*257+180)%2**64
    return f'180 {h} {sum(p[2] for p in ps)} {sum(180-r for r in [0,1,7,31,90,179])}'
@oracle(28)
def generic_deque():
    total=count=0
    for r in range(100):
        q=deque(r*10+i for i in range(8))
        for i in range(4):q.appendleft(-i)
        total+=sum(q);count+=len(q)
        for i in range(6):q.popleft();q.pop()
        assert not q
    return f'{count} {total} 2'
@oracle(29)
def combinators():return f'{sum(i*i for i in range(20) if (i*i)%2==0)} {sum(range(1,5))} {19+7} 3'
@oracle(30)
def module_errors():
    values=[2,3,0,10];valid=[v for v in ['0','1','100','-1','101','x'] if v.isdigit() and 0<=int(v)<=100]
    return f'{sum(values)*7} {len(values)} {len(valid)} {6-len(valid)}'
@oracle(31)
def reflection():
    def describe(d):return ''.join(f'{k}={v};' for k,v in d.items())
    rows=[dict(workers=i,limit=2*i,mode=i%3) for i in range(100)]
    return describe(dict(workers=4,limit=16,mode=3))+f'\n{sum(sum(v!=0 for v in d.values()) for d in rows)} {sum(len(describe(d)) for d in rows)} 1'
@oracle(32)
def comptime():
    primes=[n for n in range(2,128) if all(n%d for d in range(2,math.isqrt(n)+1))]
    reverse=[int(f'{i:08b}'[::-1],2) for i in range(256)]
    word=int.from_bytes(bytes(reverse[i] for i in [1,2,3,4]),'big')
    return f'{len(primes)} {sum(primes)} {sum(reverse)} {word}'
if __name__=='__main__':
    assert set(ORACLES)==set(range(1,33))
    failed=[]
    for p in sorted(q for q in ROOT.iterdir() if q.is_dir() and q.name[:2].isdigit() and 32<=int(q.name[:2])<=63):
        n=int(p.name[:2])-31;expected=ORACLES[n]()+'\n';target=p/'expected.out'
        if '--write' in sys.argv:target.write_text(expected)
        elif not target.exists() or target.read_text()!=expected:failed.append(p.name)
    if failed:raise SystemExit('Oracle mismatch: '+', '.join(failed))
    print(f'{len(ORACLES)} tier-2 oracles verified')
