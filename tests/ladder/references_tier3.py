"""Independent stdlib-only oracles for ladder tier 3 (programs 64-94; oracle n is program n+63).
Never reads Dewy sources or output. --write regenerates expected.out, 90's stdin.txt and 89's
expected-tests.json. Programs that must be rejected (NEGATIVE) have no expected.out."""
from pathlib import Path
from fractions import Fraction as F
import json,math,sqlite3,sys
ROOT=Path(__file__).parent
ORACLES={}
NEGATIVE={2,3,4,7,12,15,17}
def oracle(n):
    def register(f):ORACLES[n]=f;return f
    return register
@oracle(1)
def strict_audio():return f'{sum(144+i for i in range(64))}'
@oracle(5)
def positive_divisors():return f'{sum(1000//d for d in range(1,17))+31}'
@oracle(6)
def dependent_append():return f'{sum(i*i for i in range(32))} 999'
@oracle(8)
def checked_proofs():return '128'
@oracle(9)
def prototype_boundary():return f'{sum([2,3,5,7,11,13])}'
@oracle(10)
def place_effects():return '64 -2 74'
@oracle(11)
def callback_rows():return f'{sum(x*x-x for x in range(32))} 7'
@oracle(13)
def arena_escape():return f'{sum(sum(i*i for i in range(n)) for n in range(1,17))} 30 16'
@oracle(14)
def owner_cleanup():return '72 61'
@oracle(16)
def scoped_byte_loan():return f'{sum(37+i for i in range(32))} 39'
@oracle(18)
def partition_join():return f'{sum((i-32)**2+i for i in range(65))} 9'
@oracle(19)
def overlap_race():return f'{sum(a<b and a<4 and b>0 for a in range(8) for b in range(a,9))}'
@oracle(20)
def transfer_properties():return f'{sum(sender*100+i for sender in range(1,9) for i in range(16))}'
@oracle(21)
def tensor_broadcast():return f'{sum(r*10+c+(c+1)+(r+1)*100 for r in range(3) for c in range(4))} 327'
@oracle(22)
def ieee_policy():return '1 100 1'
@oracle(23)
def exact_energy():
    # Quantities start from integers and decimal strings, never binary floats.
    energy=sum(F(w*(b-a),3600000) for a,b,w in [(0,1200,1500),(1200,3600,500)])
    return f'{energy} {energy*F("0.24")} {sum([F("0.01")]*1000)} {sum([F(1,d) for d in range(1,18)])}'
@oracle(24)
def big_arithmetic():
    modulus=32416190071*32416187567
    return f'{modulus}\n{pow(12345678901234567890,65537,modulus)}\n{math.factorial(100)}\n{math.comb(100,50)}'
@oracle(25)
def temperature_points():return f'100 {sum(F(c)+F("273.15") for c in range(-20,41))}'
@oracle(26)
def test_contracts():return '120'

REPL_INPUT=['2 3 +','dup *','let x','x 5 /','0 /','unknown','clear -7 3 /','dup 2 *','quit']
@oracle(27)
def stack_repl():
    # Independent token/stack model; a failed line rolls back stack and variables.
    env={};stack=[];errors=0;lines=[]
    for source in REPL_INPUT:
        old=stack[:];oldenv=env.copy();tokens=iter(source.split());ok=True
        try:
            for t in tokens:
                try:stack.append(int(t));continue
                except ValueError:pass
                if t=='quit':break
                if t=='clear':stack=[]
                elif t=='dup':stack.append(stack[-1])
                elif t=='let':env[next(tokens)]=stack.pop()
                elif t in env:stack.append(env[t])
                elif t in ['+','-','*','/','=']:
                    b=stack.pop();a=stack.pop()
                    stack.append({'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a//b,'=':lambda:int(a==b)}[t]())
                elif t=='drop':stack.pop()
                elif t=='swap':stack[-2:]=[stack[-1],stack[-2]]
                else:raise ValueError(t)
        except (ValueError,IndexError,ZeroDivisionError,StopIteration):
            stack=old;env=oldenv;errors+=1;ok=False
        lines.append(('ok ' if ok else f'error {errors} ')+'stack'+''.join(' '+str(v) for v in stack))
    lines.append(f'done {len(REPL_INPUT)} {errors} {len(env)}')
    return '\n'.join(lines)
@oracle(28)
def adventure_state():
    exits={'hall':{'north':'study','east':'garden'},'study':{'south':'hall','east':'vault'},'garden':{'west':'hall','north':'gate'},'vault':{'west':'study'},'gate':{'south':'garden'}}
    items={'hall':['lamp'],'study':['key'],'garden':['coin'],'vault':['gem'],'gate':[]}
    titles={'hall':'Quiet hall','study':'Dusty study','garden':'Moon garden','vault':'Stone vault','gate':'Iron gate'}
    script=['look','take lamp','go north','go east','take key','use key','go east','take gem','go west','go south','go east','go north','use gem','go south','take coin','go north','use gem','look']
    room='hall';held=set();visited=set();unlocked=False;won=False;score=0;turns=0;lines=[]
    for cmd in script:
        if won:lines.append('game over');continue
        if cmd=='look':lines.append(titles[room]+''.join(' '+i for i in items[room] if i not in held));continue
        turns+=1;verb,arg=cmd.split()
        if verb=='go':
            target=exits[room].get(arg)
            if target is None:result='blocked'
            elif target=='vault' and not unlocked:result='locked'
            elif target=='gate' and 'lamp' not in held:result='dark'
            else:
                room=target;result='entered '+room
                if room not in visited:score+=1;visited.add(room)
        elif verb=='take':
            if arg in held:result='already held'
            elif arg not in items[room]:result='not here'
            else:held.add(arg);score+=5;result='took '+arg
        elif verb=='use' and arg=='key':unlocked=True;score+=10;result='vault unlocked'
        elif verb=='use' and arg=='gem':
            if 'coin' not in held:result='toll required'
            else:won=True;score+=100;result='escaped'
        else:raise AssertionError(cmd)
        lines.append(result)
    lines.append(f'{score} {turns} {len(held)}')
    return '\n'.join(lines)
@oracle(29)
def http_json_routes():
    # Stdlib JSON decoding and a separate CRUD model; no socket is involved.
    data={};writes=0;result=[]
    cases=[('GET','/health',''),('GET','/items/apple',''),('PUT','/items/apple','{"value":7}'),('GET','/items/apple',''),('PUT','/items/apple','{"value":9}'),('PUT','/items/pear','{"value":-4}'),('PUT','/items/pear','{"value":oops}'),('POST','/items/apple',''),('DELETE','/items/apple',''),('GET','/items/apple',''),('GET','/items/pear','')]
    compact=lambda x:json.dumps(x,separators=(',',':'))
    for method,path,body in cases:
        key=path.rsplit('/',1)[-1];status=200
        if path=='/health':payload={'ok':True}
        elif method=='GET':
            if key in data:payload={'value':data[key]}
            else:status=404;payload={'error':'missing'}
        elif method=='PUT':
            try:value=json.loads(body)['value']
            except (ValueError,KeyError):status=400;payload={'error':'json'}
            else:status=200 if key in data else 201;data[key]=value;writes+=1;payload={'value':value}
        elif method=='DELETE':status=204;del data[key];writes+=1;payload=None
        else:status=405;payload={'error':'method'}
        result.append(f'{status} '+('' if payload is None else compact(payload)))
    result.append('400 '+compact({'error':'request'}));result.append(f'{len(data)} {writes}')
    return '\n'.join(result)
@oracle(30)
def table_queries():
    # SQLite supplies primary-key, query and transaction answers.
    db=sqlite3.connect(':memory:',isolation_level=None)
    db.execute('create table t(id integer primary key, name text, score integer)')
    result=[]
    script=['INSERT 3 cy 70','INSERT 1 al 40','INSERT 2 be 60','SELECT score >= 50 ORDER id','BEGIN','UPDATE 1 90','DELETE 2','SELECT score >= 50 ORDER id','ROLLBACK','SELECT score >= 50 ORDER id','BEGIN','UPDATE 3 10','COMMIT','SELECT score >= 0 ORDER id','INSERT 1 dup 5','SELECT score >= nope ORDER id']
    for line in script:
        t=line.split();verb=t[0]
        try:
            if verb=='INSERT':db.execute('insert into t values(?,?,?)',(int(t[1]),t[2],int(t[3])));reply='insert 1'
            elif verb=='UPDATE':c=db.execute('update t set score=? where id=?',(int(t[2]),int(t[1])));reply=f'changed {c.rowcount}'
            elif verb=='DELETE':c=db.execute('delete from t where id=?',(int(t[1]),));reply=f'changed {c.rowcount}'
            elif verb=='SELECT':
                rows=db.execute('select id,name,score from t where score>=? order by id',(int(t[3]),)).fetchall()
                reply='rows'+''.join(f' {i}:{n}:{s}' for i,n,s in rows)
            else:db.execute(verb);reply=verb.lower()
        except sqlite3.IntegrityError:reply='error duplicate'
        except ValueError:reply='error syntax'
        result.append(reply)
    result.append(f'{db.execute("select count(*) from t").fetchone()[0]} 0')
    return '\n'.join(result)
@oracle(31)
def physics_hash():
    # Brute-force pairs, independent of Dewy's spatial hash and candidate ordering.
    b=[[i,10+i%6*18,10+i//6*18,i%3-1,(i+1)%3-1,5] for i in range(24)]
    initial=sum(x[3]**2+x[4]**2 for x in b);contacts=0
    for _ in range(80):
        for body in b:
            body[1]+=body[3];body[2]+=body[4]
            for axis,velocity in [(1,3),(2,4)]:
                r=body[5]
                if body[axis]<r:body[axis]=2*r-body[axis];body[velocity]*=-1
                if body[axis]>128-r:body[axis]=2*(128-r)-body[axis];body[velocity]*=-1
        pairs=[(i,j) for i in range(len(b)) for j in range(i+1,len(b)) if (b[i][1]-b[j][1])**2+(b[i][2]-b[j][2])**2<=(b[i][5]+b[j][5])**2]
        for i,j in pairs:
            axis=3 if abs(b[i][1]-b[j][1])>=abs(b[i][2]-b[j][2]) else 4
            b[i][axis],b[j][axis]=b[j][axis],b[i][axis];contacts+=1
        assert sum(x[3]**2+x[4]**2 for x in b)==initial
    checksum=sum((i+1)*(x*31+y*17+vx*7+vy) for i,x,y,vx,vy,r in b)
    return f'{checksum} {contacts} {initial}'
def test_contract():
    # The native test runner's contract for 89: ten case-expanded tests, one failed helper expectation.
    cases={**{f'identity_cases[{i}]':'pass' for i in range(4)},'narrowing':'pass','snapshots':'pass','expect_stops_helper':'fail',**{f'commutes[{i}]':'pass' for i in range(3)}}
    return json.dumps({'cases':cases,'passed':9,'failed':1,'exit':1,'failure_stdout':'continued\n','message_contains':'nonempty input','ordinary_stdout':test_contracts()+'\n'},indent=2)+'\n'
if __name__=='__main__':
    assert set(ORACLES)|NEGATIVE==set(range(1,32)) and not set(ORACLES)&NEGATIVE
    programs=sorted(q for q in ROOT.iterdir() if q.is_dir() and q.name.split('_')[0].isdigit() and 64<=int(q.name.split('_')[0])<=94)
    assert [int(p.name.split('_')[0])-63 for p in programs]==list(range(1,32)),'every tier-3 program needs an oracle'
    files={}
    for p in programs:
        n=int(p.name.split('_')[0])-63
        if n in NEGATIVE:files[p/'expected.out']=None
        else:files[p/'expected.out']=ORACLES[n]()+'\n'
    files[ROOT/'90_stack_repl'/'stdin.txt']='\n'.join(REPL_INPUT)+'\n'
    files[ROOT/'89_test_contracts'/'expected-tests.json']=test_contract()
    failed=[]
    for target,text in files.items():
        if '--write' in sys.argv:
            if text is None:target.unlink(missing_ok=True)
            else:target.write_text(text)
        elif (text is None and target.exists()) or (text is not None and (not target.exists() or target.read_text()!=text)):
            failed.append(f'{target.parent.name}/{target.name}')
    if failed:raise SystemExit('Oracle mismatch: '+', '.join(failed))
    print(f'{len(ORACLES)} tier-3 oracles verified; {len(NEGATIVE)} programs must be rejected')
