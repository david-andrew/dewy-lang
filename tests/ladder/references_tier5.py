"""Independent stdlib-only oracles for tier 5 (programs 102-112): decided surface in combination.
Never reads Dewy sources or output. Oracles are registered by program directory name.
--write regenerates expected.out (and stdin.txt where a program reads one)."""
from fractions import Fraction as F
from pathlib import Path
import sys
ROOT=Path(__file__).parent
ORACLES={}
INPUTS={}
def oracle(name):
    def register(f):ORACLES[name]=f;return f
    return register
def dstr(xs):return '['+' '.join(f'"{x}"' for x in xs)+']'

# ---------------------------------------------------------------- 102: trip splitter
@oracle('102_trip_splitter')
def trip_splitter():
    expenses=[('Maya',18450,'cabin'),('Jonah',6320,'groceries'),('Ines',4275,'fuel'),('Maya',2999,'firewood'),
              ('Theo',11800,'kayak rental'),('Jonah',1550,'coffee'),('Ines',905,'ice')]
    people=['Ines','Jonah','Maya','Theo']
    def money(c):
        if c<0:return '-'+money(-c)
        return f'${c//100}.{c%100:02d}'
    out=['expenses:']
    for who,c,what in expenses:out.append(f'  {who} paid {money(c)} for {what}')
    total=sum(c for _,c,_ in expenses)
    out.append(f'total {money(total)} ({total//100} dollars, {total%100} cents)')
    cs=[c for _,c,_ in expenses]
    out.append(f'cheapest {money(min(cs))}, dearest {money(max(cs))}')
    base,extra=divmod(total,len(people))
    bal={p:-(base+(1 if i<extra else 0)) for i,p in enumerate(people)}
    for who,c,_ in expenses:bal[who]=bal.get(who,0)+c
    out.append('balances:')
    for p,a in bal.items():
        v='is owed' if a>0 else 'owes' if a<0 else 'is even'
        out.append(f'  {p} {v} {money(abs(a))}')
    owed=dict(bal);transfers=[]
    while True:
        debtor=creditor='';low=high=0
        for p,a in owed.items():
            if a<low:debtor,low=p,a
            if a>high:creditor,high=p,a
        if not debtor or not creditor:break
        paid=min(-low,high);transfers.append((debtor,creditor,paid))
        owed[debtor]+=paid;owed[creditor]-=paid
    out.append(f'settle up in {len(transfers)} transfers:')
    for s,r,c in transfers:out.append(f'  {s} pays {r} {money(c)}')
    order=sorted(people,key=lambda p:-bal[p])
    out.append(f'most owed {order[0]}, most owing {order[-1]}, between: {dstr(order[1:-1])}')
    out.append(f'first transfer {transfers[0][0]} -> {transfers[0][1]}')
    out.append('after the swap Theo drives and Ines navigates')
    return '\n'.join(out)

# ---------------------------------------------------------------- 103: garden physics
LENGTH=[('nm',F(1,10**9)),('µm',F(1,10**6)),('mm',F(1,1000)),('m',F(1)),('km',F(1000))]
MASS=[('mg',F(1,10**6)),('g',F(1,1000)),('kg',F(1))]
def si(name):return [('n'+name,F(1,10**9)),('µ'+name,F(1,10**6)),('m'+name,F(1,1000)),(name,F(1)),('k'+name,F(1000)),('M'+name,F(10**6)),('G'+name,F(10**9))]
def frac(q):
    q=F(q);return str(q.numerator) if q.denominator==1 else f'{q.numerator}/{q.denominator}'
def qty(v,cands):
    """An exact quantity in the largest candidate unit keeping a whole count (else the simplest fraction)."""
    v=F(v)
    if v==0:return f'0{[n for n,s in cands if s==1][0]}'
    whole=[(n,s) for n,s in cands if (v/s).denominator==1 and abs(v)>=s]
    if whole:n,s=max(whole,key=lambda c:c[1]);return f'{frac(v/s)}{n}'
    n,s=min(cands,key=lambda c:((v/c[1]).denominator,-c[1]));return f'{frac(v/s)}{n}'
def to_f(c):return c*F(9,5)+32
def to_c(f):return (f-32)*F(5,9)
@oracle('103_garden_physics')
def garden_physics():
    out=['-- bricks --']
    for rows in [3,5,8]:
        n=rows*(rows+1)//2
        out.append(f'{rows} rows: {n} bricks, {qty(n*3,MASS)}, weighs {qty(n*3*10,si("N"))}')
    out.append('-- gravel border --')
    l,b=F(3),F(3,2)
    for w in [F(10,100),F(25,100),F(40,100)]:
        area=(l+2*w)*(b+2*w)-l*b
        out.append(f'border {qty(w,LENGTH)}: {float(area):.2f} m^2, {frac(area*F(5,100)*1000)} litres of gravel')
    out.append('-- paving around a square pond --')
    for n in [2,3,5]:
        ring=(n+2)**2-n**2;out.append(f'{n}x{n} pond: {ring} tiles, {frac(ring*F(1,4))} m^2 of paving')
    out.append('-- wheelbarrow ramp --')
    for run in [2,4]:
        h=F(3,4)*run;out.append(f'run {qty(run,LENGTH)}: rise {qty(h,LENGTH)}, lifting 40kg takes {qty(40*10*h,si("J"))}')
    out.append('-- spring trellis --')
    for x in [F(2,100),F(5,100),F(8,100)]:
        out.append(f'stretch {qty(x,LENGTH)}: {qty(400*x*x/2,si("J"))}')
    out.append('-- path sag --')
    sag=lambda x:3*x*x-2*x+1
    for x in [F(0),F(1,3),F(1),F(2)]:out.append(f'x={frac(x)}: {frac(sag(x))} cm')
    v=F(2,6);out.append(f'lowest point at x={frac(v)}, sag {frac(sag(v))} cm')
    out.append('-- kettle --')
    tap=F(13+15+16+16,4);rise=100-tap
    out.append(f'tap water {frac(tap)}°C ({frac(to_f(tap))}°F), rise {frac(rise)}°C ({frac(rise*F(9,5))}°F)')
    out.append(f'heat {frac(2*1000*F(42,10)*rise/1000)} kJ')
    out.append(f'served at {frac(100-5)}°C, {frac(to_f(F(95)))}°F')
    out.append('-- greenhouse thermostat --')
    sp,band=F(21),F(2)
    out.append(f'heater on below {frac(sp-band)}°C, vent above {frac(sp+band)}°C ({frac(band)}°C or {frac(band*F(9,5))}°F either side)')
    for f in [64,68,71,73,75]:
        c=to_c(F(f))
        action='heat' if c<sp-band else 'vent' if c>sp+band else 'hold'
        side='below' if c<sp else 'at or above'
        out.append(f'{f}°F = {frac(c)}°C: {action} ({side} the setpoint)')
    return '\n'.join(out)

# ---------------------------------------------------------------- 104: exact kitchen
def dec(q):
    """An exact value written with decimals: terminating digits, or the repeating block in parentheses."""
    q=F(q)
    if q.denominator==1:return str(q.numerator)
    sign='-' if q<0 else '';q=abs(q)
    whole,rem=divmod(q.numerator,q.denominator);digits=[];seen={}
    while rem and rem not in seen:
        seen[rem]=len(digits);rem*=10;digits.append(str(rem//q.denominator));rem%=q.denominator
    if not rem:return f'{sign}{whole}.'+''.join(digits)
    i=seen[rem];return f'{sign}{whole}.'+''.join(digits[:i])+'('+''.join(digits[i:])+')'
def shown(q,decimal):
    """Both kinds took part: a decimal when the digits end, otherwise a fraction."""
    q=F(q);d=q.denominator
    while d%2==0:d//=2
    while d%5==0:d//=5
    return dec(q) if decimal and d==1 else frac(q)
@oracle('104_exact_kitchen')
def exact_kitchen():
    recipe=[('flour',F(3,4),'cup',False),('milk',F(5,4),'cup',True),('sugar',F(1,3),'cup',False),('butter',F(1,2),'stick',True),('eggs',F(2),'whole',False)]
    out=['-- pancakes for 4 --']
    for n,a,u,d in recipe:out.append(f'  {shown(a,d)} {u} {n}')
    out.append('-- for 6 (x3/2) --')
    for n,a,u,d in recipe:out.append(f'  {shown(a*F(3,2),d)} {u} {n}')
    out.append('-- for 1 (x0.25) --')
    for n,a,u,d in recipe:out.append(f'  {shown(a*F(1,4),True)} {u} {n}')
    out.append('-- splitting a bill --')
    for k in [2,3,4,6,7]:out.append(f'  {k} ways: {dec(F(100)/k)} each')
    out.append(f'  with tip {dec(F(100)*F(115,100))}, tax on 19.99 is {shown(F(1999,100)*F(8,100),True)}')
    out.append(f'  a third and a half: {shown(F(1,3)+F(1,2),True)}')
    out.append('-- shopping --')
    sub=F(249,100)*3+F(99,100)*12+F(375,100)*2
    half_away=lambda q:int(q+F(1,2)) if q>=0 else -int(-q+F(1,2))
    out.append(f'  subtotal {dec(sub)}, rounded {half_away(sub)}')
    out.append(f'  halves round away from zero: {half_away(F(5,2))} {half_away(F(-5,2))} {half_away(F(125,1000)*100)}')
    egg=F(375,100)/12
    out.append(f'  each egg {dec(egg)}, a dozen {dec(egg*12)}, a third of a dozen {dec(egg*12/3)}')
    out.append('-- savings --')
    saved=F(1000)*F(105,100)**10
    out.append(f'  1000.00 at 5% for 10 years: {dec(saved)}')
    cents=saved*100;r=int(cents)+(1 if cents-int(cents)>=F(1,2) else 0)
    out.append(f'  to the cent: {dec(F(r,100))}')
    out.append(f'  250 at 1/100 for 3 months: {frac(250*F(101,100)**3)}')
    out.append('-- harmonic and dice --')
    out.append(f'  H(10) = {frac(sum(F(1,k) for k in range(1,11)))}')
    p={}
    for a in range(1,7):
        for b in range(1,7):p[a+b]=p.get(a+b,0)+F(1,36)
    out.append(f'  P(7) = {frac(p[7])}, P(2) = {frac(p[2])}, P(10) = {frac(p[10])}')
    out.append(f'  all totals: {frac(sum(p.values()))}')
    out.append('-- floats where they belong --')
    x=2.0
    for _ in range(6):x=(x+2.0/x)/2
    out.append(f'  sqrt(2) ~ {x!r}')
    out.append(f'  a third as a float {1/3!r}, as a fraction 1/3')
    out.append('-- a sack of flour --')
    out.append(f'  {frac(F(2500,125))} portions, weighing {dec(F(25,10)*F(981,100))} N')
    return '\n'.join(out)

# ---------------------------------------------------------------- 105: hash toolkit
M32,M64=2**32,2**64
def fnv1a(t):
    h=2166136261
    for b in t.encode():h=((h^b)*16777619)%M32
    return h
def adler32(t):
    a,b=1,0
    for c in t.encode():a=(a+c)%65521;b=(b+a)%65521
    return b*65536+a
@oracle('105_hash_toolkit')
def hash_toolkit():
    out=['-- hashes --']
    for w in ['','a','hello','Dewy','The quick brown fox jumps over the lazy dog']:
        out.append(f'{len(w)} chars: fnv1a {fnv1a(w)} adler32 {adler32(w)}')
    out.append('-- generator --')
    state=2026;draws=[]
    for _ in range(5):
        x=state;x^=x>>12;x=(x^(x<<25))%M64;x^=x>>27;state=x;draws.append(x*2685821657736338717%M64)
    out.append('['+' '.join(map(str,draws))+']')
    out.append('dice ['+' '.join(str(d%6+1) for d in draws)+']')
    out.append('-- exact intermediates --')
    big=18446744073709551000
    out.append(f'midpoint {(big+big+500)//2}')
    out.append(f'mul_mod {big*18446744073709550000%1000000007}')
    out.append(f'blend {(250+240)//2} {(3+4)//2}')
    out.append(f'per mille {3037000500*3037000500//1000000007}')
    keys=[3,9,27,81,243,18446744073709551000,18446744073709551600]
    out.append(f'find {"true" if 81 in keys else "false"} {"true" if 18446744073709551600 in keys else "false"} {"true" if 4 in keys else "false"}')
    out.append('-- counting bloom filter --')
    counts=[0]*64
    slots=lambda w:[(fnv1a(w)+i*adler32(w))%64 for i in range(3)]
    def add(w):
        for s in slots(w):counts[s]=min(255,counts[s]+1)
    for w in ['apple','banana','cherry','date']:add(w)
    for _ in range(300):add('spam')
    out.append(f'saturated counters {sum(c==255 for c in counts)}')
    for w in ['apple','cherry','grape','spam','kiwi']:
        out.append(f'{w}: {"true" if all(counts[s] for s in slots(w)) else "false"}')
    return '\n'.join(out)

# ---------------------------------------------------------------- 106: login vault
VAULT_SCRIPT="""register ann hunter2 1234
register bob correct-horse-battery 9876
login ann hunter2
login bob wrong
login bob correct-horse-battery
whoami
login carl anything
pin ann 1234
pin ann 4321
pin dave 0000
login bob x1
login bob x2
login bob x3
login bob correct-horse-battery
passwd ann hunter2 short
passwd ann wrong newpassword1
passwd zed hunter2 newpassword1
passwd ann hunter2 newpassword1
login ann hunter2
login ann newpassword1
dump
frobnicate now
"""
INPUTS['106_login_vault']=lambda:VAULT_SCRIPT
def to_int(t):
    body=t[1:] if t[:1] in '+-' else t
    return int(t) if body.isdigit() and body.isascii() else None
@oracle('106_login_vault')
def login_vault():
    R='<redacted>';out=[];accounts={};sessions=[];audit=[];last=None
    acct=lambda a:f'[user="{a["user"]}" password={R} pin={R} failures={a["failures"]}]'
    hexd=lambda t:f'{fnv1a(t):08x}'
    for line in VAULT_SCRIPT.splitlines():
        parts=line.split()
        if not parts:continue
        cmd,rest=parts[0],parts[1:]
        if cmd=='register' and len(rest)==3:
            u,pw,pin=rest;v=to_int(pin)
            accounts[u]=dict(user=u,password=pw,pin=0 if v is None else v,failures=0)
            out.append(f'registered {acct(accounts[u])}');audit.append(f'register {u} {hexd(pw)}')
        elif cmd=='login' and len(rest)==2:
            u,att=rest;a=accounts.get(u)
            if a is None:out.append(f'refused: BadLogin[message="unknown user" user="{u}" tried={R}]');continue
            if a['failures']>=3:out.append(f'refused: too many failures for {u}');continue
            if a['password']!=att:
                a['failures']+=1;out.append(f'refused: BadLogin[message="wrong password" user="{u}" tried={R}]');continue
            old=a['failures'];a['failures']=0
            token=f'tok-{(len(accounts)+old+len(u))*7919%100003}-{u}'
            sessions=[(t,w) for t,w in sessions if t!=token]+[(token,u)];last=token
            out.append(f'welcome {u}, your session is {R}');audit.append(f'login {u} session {hexd(token)}')
        elif cmd=='pin' and len(rest)==2:
            u,g=rest;a=accounts.get(u)
            if a is None:out.append(f'no such user {u}');continue
            v=to_int(g);ok=a['pin']+1111==(-1 if v is None else v)+1111
            out.append(f'pin for {u}: {"accepted" if ok else "rejected"} (shifted pin is {R})')
        elif cmd=='passwd' and len(rest)==3:
            u,old,new=rest;a=accounts.get(u)
            if a is None:out.append(f'passwd refused: no user {u}');continue
            if a['password']!=old:out.append(f'passwd refused for {u}: wrong password');continue
            if len(new)<8:out.append(f'passwd refused for {u}: new password too short');continue
            a['password']=new;out.append(f'password changed: {acct(a)}');audit.append(f'passwd {u} {hexd(new)}')
        elif cmd=='whoami':
            out.append(f'the last session belongs to {dict(sessions).get(last,"nobody")}')
        elif cmd=='dump':
            for u,a in accounts.items():out.append(f'  {u}: {acct(a)}')
            out.append('  sessions: ['+' '.join(f'{R} -> "{w}"' for _,w in sessions)+']')
            out.append('  passwords: ['+' '.join(R for _ in accounts)+']')
        else:out.append(f'unknown command: {line}')
    out.append('audit log:')
    for e in audit:out.append(f'  {e}')
    return '\n'.join(out)

# ---------------------------------------------------------------- 107: static files
STATIC_SCRIPT="""GET /
GET /index.html
GET /about.html?lang=en
GET /css/site.css
GET /css
GET /empty
GET /missing.html
GET /../private.txt
GET /css/../../private.txt
GET /css/../about.html
GET /./about.html
DOWNLOAD notes.txt
DOWNLOAD data.json
DOWNLOAD ../../private.txt
DOWNLOAD ../index.html
LIST /
LIST /files
LIST /css/..
LIST /about.html
POST /index.html
"""
INPUTS['107_static_files']=lambda:STATIC_SCRIPT
@oracle('107_static_files')
def static_files():
    files={'index.html':'<h1>Home</h1>\n<p>welcome</p>','about.html':'<h1>About</h1>','css/site.css':'body { margin: 0 }',
           'files/notes.txt':'shopping: eggs, flour','files/data.json':'{"visits": 3}'}
    dirs={'','css','files','empty'}
    kinds={'.html':'text/html','.css':'text/css','.txt':'text/plain','.json':'application/json'}
    def parts(t):return [x for x in t.split('/') if x not in ('','.')]
    def contained(rel):return '..' not in parts(rel)   # relative to the site root
    def serve(rel):
        key='/'.join(parts(rel))
        if key in dirs:
            if (key+'/index.html').lstrip('/') in files:return (200,'OK','text/html',files[(key+'/index.html').lstrip('/')])
            return (403,'Forbidden','text/plain','no index')
        if key not in files:return (404,'Not Found','text/plain','missing')
        suf=key[key.rfind('.'):] if '.' in key.rsplit('/',1)[-1] else ''
        return (200,'OK',kinds.get(suf,'application/octet-stream'),files[key])
    out=[]
    for line in STATIC_SCRIPT.splitlines():
        method,target=line.split()
        if method=='GET':
            name=target.split('?')[0].removeprefix('/')
            r=serve('') if name=='' else serve(name) if contained(name) else None
        elif method=='DOWNLOAD':
            rel='files/'+target
            if not contained(rel):r=(403,'Forbidden','text/plain','outside the site')
            else:r=serve(rel);r=(r[0],r[1],'application/octet-stream',r[3])
        elif method=='LIST':
            name=target.split('?')[0].removeprefix('/')
            if not contained(name):r=None
            else:
                key='/'.join(parts(name))
                if key not in dirs:r=(404,'Not Found','text/plain','not a directory')
                else:
                    pre=key+'/' if key else ''
                    names={k[len(pre):].split('/')[0] for k in list(files)+[d for d in dirs if d] if k.startswith(pre) and k!=key}
                    r=(200,'OK','text/plain',' '.join(sorted(names)))
            out.append(f'{method} {target} -> 403 Forbidden (escapes the site)' if r is None else f'{method} {target} -> {r[0]} {r[1]}: {r[3]}')
            continue
        else:r=(405,'Method Not Allowed','text/plain','')
        if r is None:out.append(f'{method} {target} -> 403 Forbidden (escapes the site)');continue
        out.append(f'{method} {target} -> {r[0]} {r[1]} {r[2]} {len(r[3])}: {r[3].split(chr(10))[0]}')
    return '\n'.join(out)

# ---------------------------------------------------------------- 108: bank ledger
@oracle('108_bank_ledger')
def bank_ledger():
    names=['alice','bob','carol','dave','erin','frank'];bal=[10000]*6
    day=[((i*7+3)%6,(i*11+1)%6,(i%9+1)*10) for i in range(120)]+[(0,1,1000000),(4,2,999999)]
    done=rej=dup=0
    for s_,t,a in day:   # every affordable transfer stays affordable in any order
        if s_==t:dup+=1
        elif bal[s_]<a:rej+=1
        else:bal[s_]-=a;bal[t]+=a;done+=1
    out=[f'opening total {60000}',f'transfers done {done}, rejected {rej}, same account {dup}','after transfers:']
    out+=[f'  {n}: {b}' for n,b in zip(names,bal)]+[f'total {sum(bal)}','after interest:']
    bal=[b+b//100 for b in bal]
    out+=[f'  {n}: {b}' for n,b in zip(names,bal)]+[f'total {sum(bal)}']
    bal[2]-=100;bal[0]+=50;bal[1]+=50
    out+=['dave cannot pay dave','after the treat:']+[f'  {n}: {b}' for n,b in zip(names,bal)]+[f'total {sum(bal)}']
    out+=[f'  bob has {bal[1]}','  carol is busy',f'  dave has {bal[3]}']
    return '\n'.join(out)

# ---------------------------------------------------------------- 109: log pipeline
ACCESS_LOG="""GET /index.html 200 5120
GET /style.css 200 1024
POST /login 302 0
GET /index.html 200 5120
GET /missing 404 312
this line is garbage
GET /api/items 200 2048
PUT /api/items/7 204 0
GET /api/items 500 128
DELETE /api/items/7 403 96
GET /index.html 304 0
PATCH /api/items/7 200 64
GET /api/items 200 2048
GET /logo.png 200 eighty
POST /api/items 201 256
GET /style.css 200 1024
GET /index.html 200 5120 extra
GET /api/items 200 2048
GET /missing 404 312
POST /login 200 640
"""
INPUTS['109_log_pipeline']=lambda:ACCESS_LOG
@oracle('109_log_pipeline')
def log_pipeline():
    lines=ACCESS_LOG.splitlines();hits=[];bad=0
    for line in lines:
        f=line.split()
        if len(f)!=4 or f[0] not in ('GET','POST','PUT','DELETE') or to_int(f[2]) is None or to_int(f[3]) is None:bad+=1;continue
        hits.append((f[1],int(f[2]),int(f[3])))
    status={};size={}
    for p_,c,b in hits:status[c]=status.get(c,0)+1;size[p_]=size.get(p_,0)+b
    out=[f'{len(lines)} lines, {len(hits)} requests, {bad} malformed','by status:']
    out+=[f'  {c}: {status[c]}' for c in sorted(status)]
    cls={}
    for _,c,_ in hits:
        k='ok' if c<300 else 'redirect' if c<400 else 'client error' if c<500 else 'server error';cls[k]=cls.get(k,0)+1
    out.append('by class: ['+' '.join(f'"{k}" -> {v}' for k,v in cls.items())+']')
    out.append('bytes by path, largest first:')
    out+=[f'  {p_}: {size[p_]}' for p_ in sorted(size,key=lambda q:-size[q])]
    out.append(f'error rate {sum(n for c,n in status.items() if c>=400)}/{len(hits)}')
    return '\n'.join(out)

# ---------------------------------------------------------------- 110: config loader
import re
CONFIG_TEXT="""# demo server
name = notes
port = 1234567890
workers = eight
max_body = 2x

user_pattern = ^[a-z][a-z0-9_]{1,15}$
this is not a setting
"""
INPUTS['110_config_loader']=lambda:CONFIG_TEXT
def to_int_kind(t,max_digits=10**6):
    body=t[1:] if t[:1] in '+-' else t
    if not (body.isdigit() and body.isascii()):return 'not a number'
    if len(body)>max_digits:return 'too many digits'
    return int(t)
@oracle('110_config_loader')
def config_loader():
    out=[];raw={}
    for line in CONFIG_TEXT.splitlines():
        if re.fullmatch(r'\s*(#.*)?',line):continue
        m=re.match(r'^\s*([a-z_]+)\s*=\s*(.*?)\s*$',line)
        if m:raw[m[1]]=m[2]
        else:out.append(f'ignored: {line}')
    def load(raw):
        probs=[]
        w=to_int_kind(raw.get('workers','4'));workers=w if isinstance(w,int) else 4
        pt=raw.get('port','8080');v=to_int_kind(pt,5);port=8080
        if isinstance(v,int):port=v
        elif v=='too many digits':probs.append(f'port {pt}: too many digits, using 8080')
        if port<1 or port>65535:probs.append(f'port {port}: out of range, using 8080');port=8080
        bt=raw.get('max_body','1048576');v=to_int_kind(bt,9);mb=1048576
        if isinstance(v,int):mb=v
        else:probs.append(f'max_body {bt}: {v}, using 1048576')
        name=raw.get('name','server') or 'server'
        pat=None
        if 'user_pattern' in raw:
            try:pat=re.compile(raw['user_pattern'])
            except re.error:probs.append(f'user_pattern {raw["user_pattern"]}: not a valid pattern')
        return dict(port=port,workers=workers,max_body=mb,name=name,pat=pat,probs=probs)
    out.append(f'read {len(raw)} settings')
    c=load(raw)
    out.append(f'name {c["name"]}, port {c["port"]}, workers {c["workers"]}, max_body {c["max_body"]}')
    out+=[f'problem: {p_}' for p_ in c['probs']]
    rule=c['pat'] or re.compile('^[a-z]+$')
    for u in ['ada','bob_2','3cats','Eve','x','dave-o']:
        out.append(f'user {u}: {"ok" if rule.fullmatch(u) else "rejected"}')
    for t in ['42','4x2','123456789012','']:
        v=to_int_kind(t,10);out.append(f"'{t}' -> {-1 if v=='not a number' else v}")
    b=load({'user_pattern':'([a-z]+','port':'http','workers':'many'})
    out.append(f'second config: port {b["port"]}, workers {b["workers"]}')
    out+=[f'problem: {p_}' for p_ in b['probs']]
    return '\n'.join(out)

# ---------------------------------------------------------------- 111: build aware
@oracle('111_build_aware')
def build_aware():
    # The ladder builds --release on x86_64-linux.
    out=['notes 0.3 (release build, linux, 64-bit words)','config in /home/demo/.config/notes','line endings LF, 64 buckets','installs notes and libnotes.so']
    notes=['Eggs flour milk and more eggs','a tiny language with exact numbers and no traps','Write the parser then the checker then more tests']
    def key(w):
        h=0
        for b in w.encode():h=(h*31+b)%1000003
        return h
    buckets=[[] for _ in range(64)];words=0
    for body in notes:
        for w in body.split(' '):
            if not w:continue
            w=w.lower();b=buckets[key(w)%64]
            if w not in b:b.append(w);words+=1
    out+=[f'{words} distinct words','self-check skipped in release builds',f'{sum(1 for b in buckets if b)} of 64 buckets used']
    for w in ['eggs','Parser','traps','coffee']:out.append(f'{w}: {"true" if w.lower() in buckets[key(w.lower())%64] else "false"}')
    out.append('ready')
    return '\n'.join(out)

# ---------------------------------------------------------------- 112: bulletproof sensor
def sensor_lines():
    import random
    r=random.Random(112)
    out=[str(v) for v in [215,198,-34,0,1003,987,456,-1205,333,250,99999,100001,-100000]]
    out+=['abc','','  42  ','12.5','+17','--3','12345678','7e2']
    out+=[str(r.randint(-300,600)) for _ in range(55)]
    return out
INPUTS['112_bulletproof_sensor']=lambda:'\n'.join(sensor_lines())+'\n'
@oracle('112_bulletproof_sensor')
def bulletproof_sensor():
    out=[];vals=[];rejected=0;lines=0
    for line in sensor_lines():
        lines+=1;t=line.strip();body=t[1:] if t[:1] in '+-' else t
        if not (body.isdigit() and body.isascii()):msg='not a number'
        elif len(body)>7:msg='too long'
        elif not -100000<=int(t)<=100000:msg='out of range'
        else:
            if len(vals)<64:vals.append(int(t))
            else:out.append(f'line {lines}: log full');rejected+=1
            continue
        out.append(f"line {lines}: {msg}: '{line}'");rejected+=1
    out.append(f'{lines} lines, {len(vals)} readings kept, {rejected} rejected')
    def deg(t):
        m=abs(t);return f'{"-" if t<0 else ""}{m//10}.{m%10}'
    n=len(vals);lo,hi,total=min(vals),max(vals),sum(vals);med=sorted(vals)[n//2]
    out.append(f'low {deg(lo)} high {deg(hi)} mean {deg(total//n)} median {deg(med)}')
    out.append(f'exact mean {float(total)/float(n)/10.0!r}')
    width=hi-lo+1;bars=[0]*10
    for v in vals:
        b=(v-lo)*10//width
        if 0<=b<10:bars[b]+=1
    out+=[f'  bucket {i}: {c}' for i,c in enumerate(bars)]
    return '\n'.join(out)


if __name__=='__main__':
    programs=sorted(q.name for q in ROOT.iterdir() if q.is_dir() and q.name[:3].isdigit() and 102<=int(q.name[:3])<=112)
    assert sorted(ORACLES)==programs,'every program 102-112 needs an oracle'
    selected=[a for a in sys.argv[1:] if not a.startswith('--')]
    files={}
    for name in programs:
        if selected and not any(s in name for s in selected):continue
        files[ROOT/name/'expected.out']=ORACLES[name]()+'\n'
        if name in INPUTS:files[ROOT/name/'stdin.txt']=INPUTS[name]()
    failed=[]
    for target,text in files.items():
        if '--write' in sys.argv:target.write_text(text)
        elif not target.exists() or target.read_text()!=text:failed.append(f'{target.parent.name}/{target.name}')
    if failed:raise SystemExit('Oracle mismatch: '+', '.join(failed))
    print(f'{len(files)} tier-5 oracle files verified')
