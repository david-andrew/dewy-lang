"""Independent stdlib-only oracles for the tier-4 flagships 100-101 (RTOS kernel, ML training loop).
Never reads Dewy sources or output. Oracles are registered by program directory name.
--write regenerates expected.out (and stdin.txt where a program reads one)."""
from pathlib import Path
import math,struct,sys
ROOT=Path(__file__).parent
ORACLES={}
INPUTS={}
def oracle(name):
    def register(f):ORACLES[name]=f;return f
    return register

# ---------------------------------------------------------------- 100: RTOS kernel
# A model of the specified kernel: one program word per tick for the best ready
# task (highest effective priority, then FIFO by readiness), timers, latched
# maskable interrupt lines serviced lowest first before scheduling, mutexes
# handed to the best waiter with priority inheritance recomputed to a fixpoint,
# bounded mailboxes with blocked senders and receivers, a LIFO block pool, a
# bump arena and a trace of every kernel decision.
RTOS_SCRIPT=r"""# Eight tasks in three phases: a priority-inheritance chain over two mutexes,
# an interrupt-driven sensor pipeline through three mailboxes, and storage
# pressure on the block pool, the bump arena and a bounded mailbox.
#
# Operations: work N, sleep N, lock M, unlock M, send BOX VALUE,
# send BOX reg [ADD], recv BOX, alloc, free, bump WORDS, reset, yield,
# mask LINE, unmask LINE, wait, repeat TO TIMES, exit.

task logger 1
    lock 0
    work 8
    unlock 0
    recv 2
    bump 8
    repeat 3 2
    reset
    exit
task bulk 2
    sleep 14
    lock 1
    work 1
    lock 0
    work 1
    unlock 0
    unlock 1
    sleep 40
    bump 30
    bump 30
    bump 30
    yield
    work 2
    exit
task control 6
    sleep 5
    lock 1
    work 1
    unlock 1
    sleep 12
    lock 1
    work 1
    unlock 1
    mask 1
    work 3
    unmask 1
    wait
    alloc
    alloc
    free
    free
    free
    unlock 3
    exit
task sensor 4
    recv 1
    send 0 reg 1
    repeat 0 4
    wait
    exit
task filter 3
    recv 0
    work 2
    lock 0
    send 2 reg 100
    unlock 0
    repeat 0 4
    exit
task spinner 2
    sleep 60
    work 3
    yield
    repeat 1 3
    exit
task burst 1
    sleep 70
    send 3 1
    send 3 2
    send 3 3
    send 3 4
    send 3 5
    send 3 6
    alloc
    alloc
    alloc
    alloc
    alloc
    exit
task drain 1
    sleep 5
    recv 3
    work 1
    repeat 1 5
    exit

vector 0 signal control
vector 1 post 1 50
vector 2 post 1 70
vector 3 signal sensor

irq 30 1
irq 31 2
irq 32 1
irq 32 2
irq 33 2
irq 34 2
irq 35 2
irq 36 2
irq 37 3
irq 45 0
irq 50 1
irq 62 0
run 170
"""
INPUTS['100_rtos_kernel']=lambda:RTOS_SCRIPT

NTASK,NCODE,NMUTEX,NBOX,BOXCAP,WHEEL,NBLOCK,HOLD,ARENA,NIRQ,QUANTUM=8,160,4,4,4,8,8,4,64,4,3
ARITY={'work':1,'sleep':1,'lock':1,'unlock':1,'recv':1,'bump':1,'mask':1,'unmask':1,'send':2,'repeat':2}

class Task:
    def __init__(s,name,prio,ops):
        s.name,s.base,s.eff,s.ops=name,prio,prio,ops
        s.state='ready';s.pc=s.left=s.loops=s.slice=0;s.ready_seq=s.wait_seq=0;s.wait_on=-1
        s.reg=s.outgoing=0;s.signaled=False;s.deadline=0;s.held=[];s.ran=0

class Rtos:
    def __init__(s,tasks,vectors):
        s.now=0;s.seq=0;s.current=-1;s.tasks=[];s.trace=[]
        s.owner=[-1]*NMUTEX;s.boxes=[[] for _ in range(NBOX)];s.peak=[0]*NBOX
        s.wheel=[[] for _ in range(WHEEL)];s.free=list(range(NBLOCK))  # top of the stack is free[0]
        s.top=s.arena_peak=0;s.pending=[False]*NIRQ;s.masked=[False]*NIRQ;s.vectors=vectors
        s.switches=s.idle=s.irqs=s.overruns=s.boosts=s.faults=0
        for name,prio,ops in tasks:
            s.tasks.append(Task(name,prio,ops));s.ready(len(s.tasks)-1)
    def who(s,t):return '-' if t<0 else s.tasks[t].name
    def log(s,text):s.trace.append(f'{str(s.now).ljust(4)} {text}')
    def ready(s,t):
        task=s.tasks[t];task.state='ready';task.ready_seq=s.seq;task.slice=0;s.seq+=1
    def block(s,t,state,on):
        task=s.tasks[t];task.state=state;task.wait_on=on;task.wait_seq=s.seq;s.seq+=1
    def resume(s,t):
        s.tasks[t].pc+=1;s.tasks[t].wait_on=-1;s.ready(t)
    def waiter(s,state,on):
        found=[(-x.eff,x.wait_seq,i) for i,x in enumerate(s.tasks) if x.state==state and x.wait_on==on]
        return min(found)[2] if found else -1
    def inherit(s):
        old=[x.eff for x in s.tasks]
        eff=[x.base for x in s.tasks]
        changed=True
        while changed:
            changed=False
            for w,x in enumerate(s.tasks):
                if x.state=='lock' and s.owner[x.wait_on]>=0 and eff[w]>eff[s.owner[x.wait_on]]:
                    eff[s.owner[x.wait_on]]=eff[w];changed=True
        for t,x in enumerate(s.tasks):
            x.eff=eff[t]
            if eff[t]!=old[t]:
                if eff[t]>old[t]:s.boosts+=1
                s.log(f'{x.name} priority {old[t]} -> {eff[t]}')
    def release(s,t,m):
        nxt=s.waiter('lock',m)
        if nxt<0:
            s.owner[m]=-1;s.log(f'{s.who(t)} unlocks m{m}')
        else:
            s.owner[m]=nxt;s.resume(nxt);s.log(f'{s.who(t)} hands m{m} to {s.who(nxt)}')
        s.inherit()
    def enqueue(s,b,v):
        if len(s.boxes[b])>=BOXCAP:return False
        s.boxes[b].append(v);s.peak[b]=max(s.peak[b],len(s.boxes[b]));return True
    def deliver(s,b,v):
        r=s.waiter('recv',b)
        if r>=0:
            s.tasks[r].reg=v;s.resume(r);return True,r
        return s.enqueue(b,v),-1
    def finish(s,t):
        x=s.tasks[t];x.state='done';s.log(f'{x.name} exits after {x.ran} ticks')
        while x.held:
            blk=x.held.pop();s.free.insert(0,blk);s.log(f'{x.name} reclaims block {blk}')
        for m in range(NMUTEX):
            if s.owner[m]==t:s.release(t,m)
    def step(s,t):
        x=s.tasks[t];x.ran+=1;n=x.name
        if not 0<=x.pc<len(x.ops):
            s.finish(t);return
        op,a,b,use_reg=x.ops[x.pc];nxt=True
        if op=='work':
            if x.left<=0:x.left=a
            x.left-=1;nxt=x.left<=0
        elif op=='sleep':
            x.state='sleeping';x.deadline=s.now+a;s.wheel[x.deadline%WHEEL].append(t);s.log(f'{n} sleeps until {s.now+a}')
        elif op=='lock':
            if s.owner[a]<0:s.owner[a]=t;s.log(f'{n} locks m{a}')
            elif s.owner[a]==t:s.faults+=1;s.log(f'{n} fault 1 on object {a}')
            else:
                o=s.owner[a];s.block(t,'lock',a);s.log(f'{n} blocks on m{a} held by {s.who(o)}');s.inherit();nxt=False
        elif op=='unlock':
            if not 0<=a<NMUTEX or s.owner[a]!=t:s.faults+=1;s.log(f'{n} fault: unlocks m{a} it does not hold')
            else:s.release(t,a)
        elif op=='send':
            v=x.reg+b if use_reg else b
            ok,to=s.deliver(a,v)
            if ok:s.log(f'{n} sends {v} to box {a}' if to<0 else f'{n} hands {v} to {s.who(to)}')
            else:x.outgoing=v;s.block(t,'send',a);s.log(f'{n} blocks sending {v} to full box {a}');nxt=False
        elif op=='recv':
            if not s.boxes[a]:s.block(t,'recv',a);s.log(f'{n} waits on empty box {a}');nxt=False
            else:
                x.reg=s.boxes[a].pop(0);s.log(f'{n} receives {x.reg} from box {a}')
                w=s.waiter('send',a)
                if w>=0 and s.enqueue(a,s.tasks[w].outgoing):
                    s.resume(w);s.log(f'{s.who(w)} unblocked: {s.tasks[w].outgoing} queued in box {a}')
        elif op=='alloc':
            if not s.free or len(x.held)>=HOLD:s.log(f'{n} allocation fails ({len(s.free)} free)')
            else:blk=s.free.pop(0);x.held.append(blk);s.log(f'{n} allocates block {blk}')
        elif op=='free':
            if not x.held:s.log(f'{n} frees nothing')
            else:blk=x.held.pop();s.free.insert(0,blk);s.log(f'{n} frees block {blk}')
        elif op=='bump':
            if a<=0 or a>ARENA-s.top:s.log(f'{n} arena full: {a} words at {s.top}')
            else:s.log(f'{n} bumps {a} words at {s.top}');s.top+=a;s.arena_peak=max(s.arena_peak,s.top)
        elif op=='reset':s.top=0;s.log(f'{n} resets the arena')
        elif op=='yield':s.ready(t);s.log(f'{n} yields')
        elif op in('mask','unmask'):s.masked[a]=op=='mask';s.log(f'{n} {op}s irq {a}')
        elif op=='wait':
            if x.signaled:x.signaled=False;s.log(f'{n} takes a latched signal')
            else:x.state='wait';s.log(f'{n} waits for a signal');nxt=False
        elif op=='repeat':
            if x.loops<b:x.loops+=1;x.pc=a;nxt=False
            else:x.loops=0
        elif op=='exit':
            s.finish(t);return
        if nxt:x.pc+=1
        if x.state=='ready':
            x.slice+=1
            if x.slice>=QUANTUM:s.ready(t)
    def raise_line(s,line):
        s.pending[line]=True;s.log(f'irq {line} raised'+(' while masked' if s.masked[line] else ''))
    def tick(s):
        slot=s.wheel[s.now%WHEEL];due=[t for t in slot if s.tasks[t].deadline==s.now and s.tasks[t].state=='sleeping']
        s.wheel[s.now%WHEEL]=[t for t in slot if t not in due]
        for t in due:s.ready(t);s.log(f'{s.who(t)} wakes (timer)')
        for line in range(NIRQ):
            if s.pending[line] and not s.masked[line]:
                s.pending[line]=False;s.irqs+=1;action,target,value=s.vectors.get(line,('none',0,0))
                if action=='post':
                    ok,to=s.deliver(target,value)
                    if not ok:s.overruns+=1;s.log(f'isr {line}: box {target} full, {value} lost')
                    elif to<0:s.log(f'isr {line}: posts {value} to box {target}')
                    else:s.log(f'isr {line}: hands {value} to {s.who(to)}')
                elif action=='signal':
                    if s.tasks[target].state=='wait':s.tasks[target].pc+=1;s.ready(target);s.log(f'isr {line}: wakes {s.who(target)}')
                    else:s.tasks[target].signaled=True;s.log(f'isr {line}: signal latched for {s.who(target)}')
        ready=[(-x.eff,x.ready_seq,i) for i,x in enumerate(s.tasks) if x.state=='ready']
        nxt=min(ready)[2] if ready else -1
        if nxt!=s.current:
            if nxt<0:s.log(f'idle after {s.who(s.current)}')
            else:s.log(f'switch {s.who(s.current)} -> {s.who(nxt)}');s.switches+=1
            s.current=nxt
        if nxt<0:s.idle+=1
        else:s.step(nxt)
        s.now+=1

@oracle('100_rtos_kernel')
def rtos_kernel():
    tasks,vectors,irqs,run=[],{},[],0
    for raw in RTOS_SCRIPT.splitlines():
        words=raw.split('#')[0].split()
        if not words:continue
        if raw.startswith(' '):
            op=words[0]
            if op=='send' and words[2]=='reg':tasks[-1][2].append((op,int(words[1]),int(words[3]) if len(words)>3 else 0,True))
            else:
                args=[int(w) for w in words[1:]]+[0,0]
                assert len(words)-1==ARITY.get(op,0),raw
                tasks[-1][2].append((op,args[0],args[1],False))
        elif words[0]=='task':tasks.append((words[1],int(words[2]),[]))
        elif words[0]=='vector':
            names=[t[0] for t in tasks]
            vectors[int(words[1])]=('signal',names.index(words[3]),0) if words[2]=='signal' else ('post',int(words[3]),int(words[4]))
        elif words[0]=='irq':irqs.append((int(words[1]),int(words[2])))
        elif words[0]=='run':run=int(words[1])
    k=Rtos(tasks,vectors)
    out=[f'boot: {len(tasks)} tasks, {sum(len(t[2]) for t in tasks)} program words, run {run} ticks']
    for now in range(run):
        for at,line in irqs:
            if at==now:k.raise_line(line)
        k.tick()
        out+=k.trace;k.trace=[]
    out.append(f'summary at tick {k.now}')
    out.append(f'  {"task".ljust(8)} {"state".ljust(9)} prio eff  ran')
    for x in k.tasks:
        out.append(f'  {x.name.ljust(8)} {x.state.ljust(9)} {str(x.base).ljust(4)} {str(x.eff).ljust(4)} {x.ran}')
    out.append(f'switches {k.switches}, idle {k.idle}, interrupts {k.irqs}, overruns {k.overruns}, boosts {k.boosts}, faults {k.faults}')
    out.append(f'pool {len(k.free)}/{NBLOCK} free, arena peak {k.arena_peak}/{ARENA}, mailbox peaks {" ".join(map(str,k.peak))}, trace dropped 0')
    return '\n'.join(out)

# ---------------------------------------------------------------- 101: ML training loop
# A 2-12-12-3 ReLU perceptron trained with Adam on a jittered three-class XOR
# cloud, in plain Python floats (IEEE binary64, the same operation order:
# dense sums start from the bias, gradients are summed in batch order).
M64=2**64
class Lcg:
    def __init__(s,seed):s.state=seed
    def next(s):
        s.state=(s.state*6364136223846793005+1442695040888963407)%M64
        return s.state>>33
    def uniform(s):return s.next()/2147483648.0
    def below(s,n):
        d=s.next()
        return d%n if n>0 else 0

def dataset(seed,count,noise):
    r=Lcg(seed);out=[]
    for i in range(count):
        label=i%3;side=(i//3)%2;flip=-1.0 if side==0 else 1.0
        cx,cy=(0.0,0.0) if label==2 else (flip,flip) if label==0 else (0.0-flip,flip)
        x0=cx+(2.0*r.uniform()-1.0)*noise
        x1=cy+(2.0*r.uniform()-1.0)*noise
        out.append((x0,x1,label))
    return out

IN,HID,OUT=2,12,3
def glorot(r,fi,fo):
    limit=math.sqrt(6.0/float(fi+fo))
    return [(2.0*r.uniform()-1.0)*limit for _ in range(fi*fo)]
def dense(x,w,b,cols):
    out=[]
    for j in range(cols):
        acc=b[j]
        for i,xi in enumerate(x):acc+=xi*w[i*cols+j]
        out.append(acc)
    return out
def relu(z):return [v if v>0.0 else 0.0 for v in z]
def forward(m,x0,x1):
    x=[x0,x1];h1=relu(dense(x,m[0],m[1],HID));h2=relu(dense(h1,m[2],m[3],HID));y=dense(h2,m[4],m[5],OUT)
    return x,h1,h2,y
def argmax(y):
    best,top=0,y[0]
    for k,v in enumerate(y):
        if v>top:best,top=k,v
    return best
def back(dz,w,rows,cols):
    out=[]
    for i in range(rows):
        acc=0.0
        for j,d in enumerate(dz):acc+=w[i*cols+j]*d
        out.append(acc)
    return out
def outer(a,b):return [ai*bj for ai in a for bj in b]
def backprop(m,sample):
    x0,x1,label=sample
    x,h1,h2,y=forward(m,x0,x1)
    dy=[yk-(1.0 if k==label else 0.0) for k,yk in enumerate(y)]
    dz2=[d if h>0.0 else 0.0 for d,h in zip(back(dy,m[4],HID,OUT),h2)]
    dz1=[d if h>0.0 else 0.0 for d,h in zip(back(dz2,m[2],HID,HID),h1)]
    acc=0.0
    for k,yk in enumerate(y):
        d=yk-(1.0 if k==label else 0.0);acc+=d*d
    return [outer(x,dz1),dz1,outer(h1,dz2),dz2,outer(h2,dy),dy],0.5*acc,argmax(y)==label

@oracle('101_ml_training')
def ml_training():
    train=dataset(2026,120,ML_NOISE);test=dataset(99,60,ML_NOISE)
    r=Lcg(7)
    m=[glorot(r,IN,HID),[0.0]*HID,glorot(r,HID,HID),[0.0]*HID,glorot(r,HID,OUT),[0.0]*OUT]
    rate,beta1,beta2,eps=0.01,0.9,0.999,0.00000001
    mm=[[0.0]*len(a) for a in m];vv=[[0.0]*len(a) for a in m];decay1=decay2=1.0
    rng=Lcg(77);epochs,batch=30,20
    out=[f'train {len(train)} samples, test {len(test)}, batch {batch}, {epochs} epochs']
    for epoch in range(1,epochs+1):
        order=list(range(len(train)))
        for j in range(1,len(order)):
            p=rng.below(j+1);order[j],order[p]=order[p],order[j]
        total=0.0;correct=0;start=0
        while start+batch<=len(order):
            steps=[backprop(m,train[order[i]]) for i in range(start,start+batch)]
            for g,l,c in steps:
                total+=l;correct+=c
            grad=[[0.0]*len(a) for a in m]
            for g,_,_ in steps:
                for a,ga in zip(grad,g):
                    for i,v in enumerate(ga):a[i]+=v
            mean=1.0/float(batch)
            grad=[[v*mean for v in a] for a in grad]
            decay1*=beta1;decay2*=beta2
            for p,mp,vp,g in zip(m,mm,vv,grad):
                for i,gi in enumerate(g):
                    mp[i]=beta1*mp[i]+(1.0-beta1)*gi
                    vp[i]=beta2*vp[i]+(1.0-beta2)*(gi*gi)
                    mhat=mp[i]/(1.0-decay1);vhat=vp[i]/(1.0-decay2)
                    p[i]-=rate*mhat/(math.sqrt(vhat)+eps)
            start+=batch
        out.append(f'epoch {epoch:02d} loss {total/float(len(train)):.6f} train {correct}/{len(train)}')
    counts=[[0]*3 for _ in range(3)]
    for x0,x1,label in test:counts[label][argmax(forward(m,x0,x1)[3])]+=1
    out.append(f'test {sum(counts[c][c] for c in range(3))}/{len(test)}')
    for c in range(3):out.append(f'  class {c}: '+' '.join(map(str,counts[c])))
    for x0,x1,label in [(-1.0,-1.0,0),(1.0,-1.0,1),(0.0,0.0,2),(0.5,0.5,0)]:
        y=forward(m,x0,x1)[3]
        out.append(f'probe ({x0:.1f}, {x1:.1f}) -> '+' '.join(f'{v:.3f}' for v in y)+f' class {argmax(y)}')
    return '\n'.join(out)
ML_NOISE=0.8


if __name__=='__main__':
    programs=sorted(q.name for q in ROOT.iterdir() if q.is_dir() and q.name[:3].isdigit() and 100<=int(q.name[:3])<=101)
    assert sorted(ORACLES)==programs,'every program 100-101 needs an oracle'
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
