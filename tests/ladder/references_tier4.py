"""Independent stdlib-only oracles for ladder tier 4 (flagship programs, 95 onward).
Never reads Dewy sources or output. Oracles are registered by program directory name.
--write regenerates expected.out (and stdin.txt where a program reads one)."""
from pathlib import Path
import hashlib,hmac,re,sqlite3,sys
ROOT=Path(__file__).parent
ORACLES={}
INPUTS={}
def oracle(name):
    def register(f):ORACLES[name]=f;return f
    return register

# ---------------------------------------------------------------- 95: durable key-value store
# The scripted session runs against SQLite (the table, SQL semantics and transactions) plus a
# model of what the store promises across crashes: a committed transaction survives a crash; an
# open transaction and a torn append do not; damage to the newest log record loses exactly the
# newest transaction in the live log; compaction makes the live data one snapshot transaction.
KV_SCRIPT=r"""-- a small catalogue
INSERT INTO kv VALUES ('apple', 'red'), ('banana', 'yellow'), ('cherry', 'dark red')
INSERT INTO kv VALUES ('date', 'brown'), ('elderberry', 'purple'), ('fig', 'green'), ('grape', 'green')
SELECT * FROM kv
SELECT key FROM kv WHERE value = 'green' ORDER BY key DESC
SELECT COUNT(*) FROM kv WHERE key >= 'b' AND key < 'e'
EXPLAIN SELECT * FROM kv WHERE key >= 'b' AND key < 'e'
EXPLAIN SELECT * FROM kv WHERE key = 'fig' OR key = 'date'
EXPLAIN SELECT key FROM kv WHERE key LIKE 'gr%' AND value <> 'x'
EXPLAIN SELECT COUNT(*) FROM kv WHERE key BETWEEN 'c' AND 'f' AND key > 'cherry'
EXPLAIN SELECT * FROM kv WHERE (key = 'kiwi') AND NOT value = 'x'
INSERT INTO kv VALUES ('apple', 'green')
INSERT INTO kv VALUES ('honeydew', 'pale'), ('honeydew', 'paler')
REPLACE INTO kv VALUES ('apple', 'green'), ('quince', 'it''s gold')
UPDATE kv SET value = 'ripe' WHERE value LIKE '%red'
SELECT key, value FROM kv WHERE value != 'green' AND NOT key BETWEEN 'c' AND 'e'
SELECT * FROM kv WHERE key LIKE '_i%' OR (value LIKE 'p%' AND key > 'd')
select value, key from kv where key <= 'cherry' order by key desc limit 2;
.crash
SELECT * FROM kv LIMIT 3
BEGIN
DELETE FROM kv WHERE key < 'c'
INSERT INTO kv VALUES ('kiwi', 'brown'), ('lemon', 'yellow')
SELECT key FROM kv WHERE key < 'l'
SELECT COUNT(*) FROM kv
ROLLBACK
SELECT COUNT(*) FROM kv
BEGIN
INSERT INTO kv VALUES ('kiwi', 'brown'), ('lemon', 'yellow'), ('mango', 'orange')
DELETE FROM kv WHERE key = 'banana'
.tear 400
COMMIT
SELECT COUNT(*) FROM kv
SELECT * FROM kv WHERE key > 'h'
BEGIN
INSERT INTO kv VALUES ('kiwi', 'brown'), ('lemon', 'yellow'), ('mango', 'orange')
DELETE FROM kv WHERE key = 'banana'
INSERT INTO kv VALUES ('banana', 'green')
COMMIT
.check
REPLACE INTO kv VALUES ('nectarine', 'peach'), ('orange', 'orange')
.damage
SELECT * FROM kv WHERE key >= 'm'
DELETE FROM kv WHERE key = 'nothing'
.damage
SELECT COUNT(*) FROM kv
.compact
DELETE FROM kv WHERE value = 'green'
SELECT COUNT(*) FROM kv
.crash-compact before_manifest
SELECT COUNT(*) FROM kv
.crash-compact before_cleanup
.check
UPDATE kv SET value = 'sour' WHERE key = 'date'
BEGIN
UPDATE kv SET value = 'tart' WHERE key = 'date'
SELECT value FROM kv WHERE key = 'date'
.crash
SELECT * FROM kv WHERE key = 'date'
.damage
SELECT * FROM kv WHERE key = 'date'
.tear 999
DELETE FROM kv WHERE key LIKE 'e%'
SELECT key FROM kv WHERE key LIKE 'e%'
COMMIT
BEGIN
BEGIN
SELEKT * FROM kv
SELECT * FROM fruit
SELECT * FROM kv WHERE key = 'unterminated
ROLLBACK
.tear 0
INSERT INTO kv VALUES ('papaya', 'orange')
INSERT INTO kv VALUES ('papaya', 'orange')
SELECT * FROM kv ORDER BY key DESC LIMIT 2
.damage
.damage
.damage
SELECT COUNT(*) FROM kv
.check
"""
INPUTS['95_kv_store']=lambda:KV_SCRIPT

def kv_plan(where):
    """The key range the store scans: top-level AND conjuncts on key narrow it."""
    tokens=re.findall(r"'(?:[^']|'')*'|<=|>=|<>|!=|[A-Za-z_][A-Za-z_0-9]*|[()=<>]",where)
    pos=0
    def peek():return tokens[pos].upper() if pos<len(tokens) else ''
    def take():
        nonlocal pos;pos+=1;return tokens[pos-1]
    def lit(t):return t[1:-1].replace("''","'")
    def disj():
        e=conj()
        while peek()=='OR':take();e=('or',e,conj())
        return e
    def conj():
        e=neg()
        while peek()=='AND':take();e=('and',e,neg())
        return e
    def neg():
        if peek()=='NOT':take();return ('not',neg())
        if peek()=='(':take();e=disj();take();return e
        col=take().lower();op=take().upper()
        if op=='BETWEEN':
            a=lit(take());take();b=lit(take())
            return ('and',('cmp',col,'>=',a),('cmp',col,'<=',b))
        return ('cmp',col,op,lit(take()))
    tree=disj();low=high=None
    def tighter(old,new,lower):
        if old is None:return new
        if (new[0]>old[0] if lower else new[0]<old[0]) or (new[0]==old[0] and not new[1]):return new
        return old
    def narrow(e):
        nonlocal low,high
        if e[0]=='and':narrow(e[1]);narrow(e[2]);return
        if e[0]!='cmp' or e[1]!='key':return
        _,_,op,text=e
        if op=='LIKE':
            prefix=re.match(r'[^%_]*',text).group(0)
            if prefix and 32<=ord(prefix[-1])<126:
                low=tighter(low,(prefix,True),True);high=tighter(high,(prefix[:-1]+chr(ord(prefix[-1])+1),False),False)
        elif op=='=':low=tighter(low,(text,True),True);high=tighter(high,(text,True),False)
        elif op in('>','>='):low=tighter(low,(text,op=='>='),True)
        elif op in('<','<='):high=tighter(high,(text,op=='<='),False)
    narrow(tree)
    if low is None and high is None:return 'full scan'
    if low and high and low[0]==high[0] and low[1] and high[1]:return f'point lookup {low[0]}'
    a='-' if low is None else ('[' if low[1] else '(')+low[0]
    b='-' if high is None else high[0]+(']' if high[1] else ')')
    return f'range {a} .. {b}'

def kv_session():
    db=sqlite3.connect(':memory:',isolation_level=None)
    db.execute('PRAGMA case_sensitive_like=ON')
    db.execute('CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT)')
    out=[];state=lambda:dict(db.execute('SELECT key,value FROM kv'))
    history=[];generation=1;open_txn=False;txn_keys=set();begin_state=None;tear=None
    def restore(d):
        db.execute('DELETE FROM kv');db.executemany('INSERT INTO kv VALUES (?,?)',sorted(d.items()))
    def restart(tail='clean',removed=0):
        nonlocal open_txn,tear
        if open_txn:db.execute('ROLLBACK');open_txn=False
        tear=None
        out.append(f'recovered keys={len(state())} tail={tail} removed={removed}')
    def written_keys(sql):
        # Keys a write statement touches, judged by SQLite itself on a savepoint.
        before=state();db.execute('SAVEPOINT probe');db.execute(sql)
        after=state();db.execute('ROLLBACK TO probe');db.execute('RELEASE probe')
        return {k for k in set(before)|set(after) if before.get(k)!=after.get(k)},before
    for line in KV_SCRIPT.splitlines():
        if not line or line.startswith('--'):continue
        out.append(f'> {line}')
        words=line.split(' ');upper=line.upper().rstrip(';')
        if words[0]=='.crash':restart()
        elif words[0]=='.tear':tear=int(words[1])
        elif words[0]=='.damage':
            if history:restore(history.pop());restart('dropped')
            else:restart()
        elif words[0]=='.compact':
            generation+=1;history=[{}];out.append(f'compacted keys={len(state())} generation={generation}')
        elif words[0]=='.crash-compact':
            out.append(f'crashed {words[1]}')
            if words[1]=='before_cleanup':generation+=1;history=[{}]
            restart(removed=1)
        elif words[0]=='.check':out.append(f'check ok keys={len(state())}')
        elif upper.startswith('EXPLAIN'):
            m=re.search(r'\bWHERE\b(.*)$',line,re.I)
            out.append(kv_plan(m.group(1)) if m else 'full scan')
        elif upper=='BEGIN':
            if open_txn:out.append('error: transaction already open')
            else:db.execute('BEGIN');open_txn=True;txn_keys=set();begin_state=state();out.append('ok')
        elif upper in('COMMIT','ROLLBACK'):
            if not open_txn:out.append('error: no transaction');continue
            if upper=='ROLLBACK' or not txn_keys:db.execute('ROLLBACK' if upper=='ROLLBACK' else 'COMMIT');open_txn=False;out.append('ok');continue
            if tear is not None:
                out.append('crashed during append');restart('dropped' if tear>0 else 'clean');continue
            db.execute('COMMIT');open_txn=False;history.append(begin_state);out.append('ok')
        else:
            sql=line.rstrip(';')
            try:
                if upper.startswith('SELECT'):
                    if 'ORDER BY' not in upper:
                        m=re.search(r'\bLIMIT\b',sql,re.I)
                        sql=sql[:m.start()]+'ORDER BY key '+sql[m.start():] if m else sql+' ORDER BY key'
                    rows=db.execute(sql).fetchall()
                    if 'COUNT(*)' in upper:out.append(str(rows[0][0]))
                    else:out+=['|'.join(r) for r in rows]+[f'({len(rows)} rows)']
                    continue
                if upper.startswith('INSERT'):
                    keys=re.findall(r"\('((?:[^']|'')*)'",sql);seen=set()
                    dup=next((k for k in keys if k in seen or seen.add(k) or db.execute('SELECT 1 FROM kv WHERE key=?',(k.replace("''","'"),)).fetchone()),None)
                    if dup is not None:out.append(f'error: duplicate key {dup}');continue
                keys,before=written_keys(sql)
                if open_txn:
                    count=db.execute(sql).rowcount;txn_keys|=keys;out.append(f'ok {count}');continue
                if keys and tear is not None:
                    out.append('crashed during append');restart('dropped' if tear>0 else 'clean');continue
                count=db.execute(sql).rowcount
                if count>0:history.append(before)
                out.append(f'ok {count}')
            except sqlite3.Error as e:
                text=str(e)
                out.append('error: '+('no such table' if 'no such table' in text else 'unterminated string' if 'unrecognized token' in text else 'unknown statement'))
    return out

class Lcg:
    def __init__(self,seed):self.state=seed
    def next(self):self.state=(self.state*6364136223846793005+1442695040888963407)%2**64;return self.state>>33
    def below(self,n):return self.next()%n
def kv_workload(seed,steps):
    rng=Lcg(seed);model={};undo=None
    t=dict(steps=0,commits=0,rollbacks=0,torn=0,crashes=0,damaged=0,compactions=0,interrupted=0,recoveries=0)
    def changes(count,step):
        out=[]
        for i in range(count):
            key=f'w{rng.below(400)}'
            out.append((key,None) if rng.below(4)==0 else (key,f's{step}.{i}'))
        return out
    for step in range(steps):
        t['steps']+=1;action=rng.below(100)
        if action<70:
            count=1 if action<55 else 2+rng.below(5)
            batch=changes(count,step)
            if action>=55 and rng.below(8)==0:t['rollbacks']+=1;continue
            undo=dict(model)
            for k,v in batch:
                if v is None:model.pop(k,None)
                else:model[k]=v
            t['commits']+=1
        elif action<80:
            changes(2+rng.below(4),step);rng.below(1000);t['torn']+=1;t['recoveries']+=1
        elif action<88:t['crashes']+=1;t['recoveries']+=1
        elif action<92:
            if undo is None:t['crashes']+=1
            else:model=undo;undo=None;t['damaged']+=1
            t['recoveries']+=1
        elif action<96:undo=None;t['compactions']+=1
        else:
            if rng.below(2)==1:undo=None
            t['interrupted']+=1;t['recoveries']+=1
    t['recoveries']+=1
    h=0xcbf29ce484222325
    for k in sorted(model):
        for b in f'{k}={model[k]}\n'.encode():h=((h^b)*0x100000001b3)%2**64
    return [f"workload steps={t['steps']} commits={t['commits']} rollbacks={t['rollbacks']} torn={t['torn']} crashes={t['crashes']} damaged={t['damaged']}",
            f"workload compactions={t['compactions']} interrupted={t['interrupted']} recoveries={t['recoveries']} mismatches=0",
            f'workload keys={len(model)} fingerprint={h:016x}']

@oracle('95_kv_store')
def kv_store():return '\n'.join(kv_session()+kv_workload(20261021,3000))

# ---------------------------------------------------------------- 96: constant-time crypto
# Straight transcriptions of the RFC algorithms over Python integers, checked against the
# published vectors before they are trusted for anything else.
def rotl(x,n):return ((x<<n)|(x>>(32-n)))&0xffffffff
def chacha_block(key,counter,nonce):
    s=[0x61707865,0x3320646e,0x79622d32,0x6b206574]+[int.from_bytes(key[i:i+4],'little') for i in range(0,32,4)]
    s+=[counter]+[int.from_bytes(nonce[i:i+4],'little') for i in range(0,12,4)]
    x=s[:]
    def qr(a,b,c,d):
        x[a]=(x[a]+x[b])&0xffffffff;x[d]=rotl(x[d]^x[a],16)
        x[c]=(x[c]+x[d])&0xffffffff;x[b]=rotl(x[b]^x[c],12)
        x[a]=(x[a]+x[b])&0xffffffff;x[d]=rotl(x[d]^x[a],8)
        x[c]=(x[c]+x[d])&0xffffffff;x[b]=rotl(x[b]^x[c],7)
    for _ in range(10):
        qr(0,4,8,12);qr(1,5,9,13);qr(2,6,10,14);qr(3,7,11,15)
        qr(0,5,10,15);qr(1,6,11,12);qr(2,7,8,13);qr(3,4,9,14)
    return b''.join(((x[i]+s[i])&0xffffffff).to_bytes(4,'little') for i in range(16))
def chacha_xor(key,counter,nonce,data):
    out=bytearray()
    for j in range(0,len(data),64):
        ks=chacha_block(key,counter+j//64,nonce)
        out+=bytes(a^b for a,b in zip(data[j:j+64],ks))
    return bytes(out)
def poly1305(key,msg):
    r=int.from_bytes(key[:16],'little')&0x0ffffffc0ffffffc0ffffffc0fffffff
    s=int.from_bytes(key[16:],'little');p=(1<<130)-5;acc=0
    for i in range(0,len(msg),16):
        acc=(acc+int.from_bytes(msg[i:i+16]+b'\x01','little'))*r%p
    return ((acc+s)&((1<<128)-1)).to_bytes(16,'little')
def pad16(n):return bytes(-n%16)
def aead_seal(key,nonce,aad,pt):
    ct=chacha_xor(key,1,nonce,pt)
    mac=aad+pad16(len(aad))+ct+pad16(len(ct))+len(aad).to_bytes(8,'little')+len(ct).to_bytes(8,'little')
    return ct,poly1305(chacha_block(key,0,nonce)[:32],mac)
P25519=2**255-19
def x25519(k,u):
    k=bytearray(k);k[0]&=248;k[31]&=127;k[31]|=64
    k=int.from_bytes(k,'little');x1=int.from_bytes(u,'little')&((1<<255)-1)
    x2,z2,x3,z3,swap=1,0,x1,1,0
    for t in range(254,-1,-1):
        bit=(k>>t)&1;swap^=bit
        if swap:x2,x3,z2,z3=x3,x2,z3,z2
        swap=bit
        a=x2+z2;aa=a*a;b=x2-z2;bb=b*b;e=aa-bb;c=x3+z3;d=x3-z3;da=d*a;cb=c*b
        x3=(da+cb)**2%P25519;z3=x1*(da-cb)**2%P25519;x2=aa*bb%P25519;z2=e*(aa+121665*e)%P25519
    if swap:x2,z2=x3,z3
    return (x2*pow(z2,P25519-2,P25519)%P25519).to_bytes(32,'little')
BASE=(9).to_bytes(32,'little')
def hkdf(salt,ikm,info,n):
    prk=hmac.new(salt or bytes(32),ikm,'sha256').digest();okm=t=b'';i=1
    while len(okm)<n:t=hmac.new(prk,t+info+bytes([i]),'sha256').digest();okm+=t;i+=1
    return okm[:n]
H=bytes.fromhex
SUNSCREEN=b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it."
# Published values (RFC 8439 2.3.2/2.4.2/2.5.2/2.6.2/2.8.2, RFC 7748 5.2/6.1) the oracle must reproduce.
PUBLISHED={
    'chacha20-block-0':'76b8e0ada0f13d90405d6ae55386bd28bdd219b8a08ded1aa836efcc8b770dc7da41597c5157488d7724e03fb8d84a376a43b8f41518a11cc387b669b2ee6586',
    'chacha20-block-8439':'10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4ed2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e',
    'chacha20-8439-2.4.2':'6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0bf91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d807ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab77937365af90bbf74a35be6b40b8eedf2785e42874d',
    'poly1305-8439-2.5.2':'a8061dc1305136c6c22b8baf0c0127a9',
    'poly1305-keygen-8439-2.6.2':'8ad5a08b905f81cc815040274ab29471a833b637e3fd0da508dbb8e2fdd1a646',
    'aead-8439-2.8.2-tag':'1ae10b594f09e26a7e902ecbd0600691',
    'x25519-7748-1':'c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552',
    'x25519-alice-public':'8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a',
    'x25519-bob-public':'de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f',
    'x25519-shared':'4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742',
    'x25519-iterate-1':'422c8e7a6227d7bca1350b3e2bb7279f7897b87bb6854b783c60e80311ae3079',
    'x25519-iterate-1000':'684cf59ba83309552800ef566f2f4d3c1c3887c49360e3875f2eb94d99532c51',
    'sha256-448':'248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
    'hmac-4231-2':'5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843',
    'hkdf-5869-1':'3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865',
}
class Stream:
    def __init__(self,seed):self.seed=seed;self.counter=0
    def next(self,n):
        out=b''
        while len(out)<n:out+=hashlib.sha256(self.seed+f'/{self.counter}'.encode()).digest();self.counter+=1
        return out[:n]
@oracle('96_ct_crypto')
def ct_crypto():
    lines=[];values={}
    def show(label,data):values[label]=data.hex();lines.append(f'{label} {data.hex()}')
    sha=lambda b:hashlib.sha256(b).digest()
    show('sha256-abc',sha(b'abc'));show('sha256-empty',sha(b''))
    show('sha256-448',sha(b'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'))
    show('sha256-896',sha(b'abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu'))
    show('sha256-million-a',sha(b'a'*1000000))
    show('hmac-4231-1',hmac.new(b'\x0b'*20,b'Hi There','sha256').digest())
    show('hmac-4231-2',hmac.new(b'Jefe',b'what do ya want for nothing?','sha256').digest())
    show('hmac-4231-6',hmac.new(b'\xaa'*131,b'Test Using Larger Than Block-Size Key - Hash Key First','sha256').digest())
    show('hkdf-5869-1',hkdf(H('000102030405060708090a0b0c'),b'\x0b'*22,H('f0f1f2f3f4f5f6f7f8f9'),42))
    show('hkdf-5869-3',hkdf(b'',b'\x0b'*22,b'',42))
    lines.append('hkdf-limit true')
    zk,zn=bytes(32),bytes(12)
    show('chacha20-block-0',chacha_block(zk,0,zn));show('chacha20-block-1',chacha_block(zk,1,zn))
    key=bytes(range(32))
    show('chacha20-block-8439',chacha_block(key,1,H('000000090000004a00000000')))
    show('chacha20-8439-2.4.2',chacha_xor(key,1,H('000000000000004a00000000'),SUNSCREEN))
    lines.append('chacha20-roundtrip true')
    show('poly1305-8439-2.5.2',poly1305(H('85d6be7857556d337f4452fe42d506a80103808afb0db2fd4abff6af4149f51b'),b'Cryptographic Forum Research Group'))
    r1=H('01'+'00'*31);r2=H('02'+'00'*31)
    show('poly1305-wrap',poly1305(r1,b'\xff'*16))
    show('poly1305-reduce',poly1305(r2,H('ff'*16+'fb'+'ff'*15)))
    show('poly1305-carry',poly1305(r1,H('ff'*16+'f0'+'ff'*15+'11'+'00'*15)))
    show('poly1305-pad',poly1305(H('02'+'00'*15+'ff'*16),H('02'+'00'*15)))
    akey=bytes(range(0x80,0xa0))
    show('poly1305-keygen-8439-2.6.2',chacha_block(akey,0,H('000000000001020304050607'))[:32])
    aad=H('50515253c0c1c2c3c4c5c6c7');ct,tag=aead_seal(akey,H('070000004041424344454647'),aad,SUNSCREEN)
    show('aead-8439-2.8.2-ciphertext',ct);show('aead-8439-2.8.2-tag',tag)
    lines.append('aead-open true')
    n=128+16+len(aad)+2;lines.append(f'aead-forgeries {n}/{n}')
    lines.append('ct-equal true false false')
    show('x25519-7748-1',x25519(H('a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4'),H('e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c')))
    show('x25519-7748-2',x25519(H('4b66e9d4d1b4673c5ad22691957d6af5c11b6421e0ea01d42ca4169e7918ba0d'),H('e5210f12786811d3f4b7959d0538ae2c31dbe7106fc03c3efc4cd549c715a493')))
    alice=H('77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a')
    bob=H('5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb')
    show('x25519-alice-public',x25519(alice,BASE));show('x25519-bob-public',x25519(bob,BASE))
    show('x25519-shared',x25519(alice,x25519(bob,BASE)))
    lines.append('x25519-agree true')
    k=u=BASE
    for i in range(1,1001):
        k,u=x25519(k,u),k
        if i==1:show('x25519-iterate-1',k)
    show('x25519-iterate-1000',k)
    rng=Stream(b'dewy tier 4 crypto workload');transcript=hashlib.sha256();sent=total=0
    for session in range(8):
        a=rng.next(32);b=rng.next(32);shared=x25519(a,x25519(b,BASE))
        keys=hkdf(f'session {session}'.encode(),shared,b'dewy aead',44);key,base=keys[:32],keys[32:]
        for m in range(24):
            length=(session*131+m*37)%700;msg=rng.next(length);ad=rng.next(m%5)
            nonce=base[:11]+bytes([base[11]^m]);ct,tag=aead_seal(key,nonce,ad,msg)
            transcript.update(ct+tag);sent+=1;total+=length
    lines.append(f'workload messages {sent} bytes {total}')
    show('workload-transcript',transcript.digest())
    big=bytes(((i*7+i//256)&255) for i in range(1048576))
    ct,tag=aead_seal(sha(b'bulk key'),H('000000000000000000000001'),b'',big)
    show('bulk-ciphertext-sha256',sha(ct));show('bulk-tag',tag)
    lines.append('bulk-open true')
    wrong=[k for k,v in PUBLISHED.items() if values[k]!=v]
    assert not wrong,f'oracle disagrees with published vectors: {wrong}'
    return '\n'.join(lines)

if __name__=='__main__':
    programs=sorted(q.name for q in ROOT.iterdir() if q.is_dir() and q.name[:2].isdigit() and int(q.name[:2])>=95)
    assert sorted(ORACLES)==programs,'every tier-4 program needs an oracle'
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
    print(f'{len(files)} tier-4 oracle files verified')
