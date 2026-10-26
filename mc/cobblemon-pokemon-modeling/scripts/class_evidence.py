"""Minimal JVM class disassembly for local research, never executes source classes."""
import argparse,json,struct
from pathlib import Path
class Reader:
    def __init__(self,d):self.d=d;self.p=0
    def take(self,n):v=self.d[self.p:self.p+n];self.p+=n;return v
    def u1(self):return self.take(1)[0]
    def u2(self):return int.from_bytes(self.take(2),'big')
    def u4(self):return int.from_bytes(self.take(4),'big')
def parse(p):
    r=Reader(p.read_bytes());assert r.u4()==0xcafebabe;r.take(4);n=r.u2();cp=[None]*n;i=1
    while i<n:
        tag=r.u1()
        if tag==1:v=r.take(r.u2()).decode('utf-8','replace')
        elif tag in (3,4):v=struct.unpack('>i' if tag==3 else '>f',r.take(4))[0]
        elif tag in (5,6):v=struct.unpack('>q' if tag==5 else '>d',r.take(8))[0]
        elif tag in (7,8,16,19,20):v=(tag,r.u2())
        elif tag in (9,10,11,12,17,18):v=(tag,r.u2(),r.u2())
        elif tag==15:v=(tag,r.u1(),r.u2())
        else:raise ValueError(tag)
        cp[i]=v;i+=2 if tag in (5,6) else 1
    def val(i):
        if not i or i>=len(cp):return str(i)
        v=cp[i]
        if not isinstance(v,tuple):return str(v)
        if v[0] in (7,8,16,19,20):return val(v[1])
        if v[0]==12:return val(v[1])+':'+val(v[2])
        if v[0] in (9,10,11):return val(v[1])+'.'+val(v[2])
        return str(v)
    r.take(6);r.take(2*r.u2())
    def attrs():
        a={}
        for _ in range(r.u2()):name=val(r.u2());a[name]=r.take(r.u4())
        return a
    for _ in range(r.u2()):r.take(6);attrs()
    methods=[]
    for _ in range(r.u2()):
        flags=r.u2();name=val(r.u2());desc=val(r.u2());a=attrs();code=None
        if 'Code'in a:
            z=Reader(a['Code']);z.take(4);code=z.take(z.u4())
        methods.append((name,desc,code))
    return cp,val,methods
names=['nop','aconst_null','iconst_m1','iconst_0','iconst_1','iconst_2','iconst_3','iconst_4','iconst_5','lconst_0','lconst_1','fconst_0','fconst_1','fconst_2','dconst_0','dconst_1','bipush','sipush','ldc','ldc_w','ldc2_w','iload','lload','fload','dload','aload','iload_0','iload_1','iload_2','iload_3','lload_0','lload_1','lload_2','lload_3','fload_0','fload_1','fload_2','fload_3','dload_0','dload_1','dload_2','dload_3','aload_0','aload_1','aload_2','aload_3','iaload','laload','faload','daload','aaload','baload','caload','saload','istore','lstore','fstore','dstore','astore','istore_0','istore_1','istore_2','istore_3','lstore_0','lstore_1','lstore_2','lstore_3','fstore_0','fstore_1','fstore_2','fstore_3','dstore_0','dstore_1','dstore_2','dstore_3','astore_0','astore_1','astore_2','astore_3','iastore','lastore','fastore','dastore','aastore','bastore','castore','sastore','pop','pop2','dup','dup_x1','dup_x2','dup2','dup2_x1','dup2_x2','swap','iadd','ladd','fadd','dadd','isub','lsub','fsub','dsub','imul','lmul','fmul','dmul','idiv','ldiv','fdiv','ddiv','irem','lrem','frem','drem','ineg','lneg','fneg','dneg','ishl','lshl','ishr','lshr','iushr','lushr','iand','land','ior','lor','ixor','lxor','iinc','i2l','i2f','i2d','l2i','l2f','l2d','f2i','f2l','f2d','d2i','d2l','d2f','i2b','i2c','i2s','lcmp','fcmpl','fcmpg','dcmpl','dcmpg','ifeq','ifne','iflt','ifge','ifgt','ifle','if_icmpeq','if_icmpne','if_icmplt','if_icmpge','if_icmpgt','if_icmpge','if_acmpeq','if_acmpne','goto','jsr','ret','tableswitch','lookupswitch','ireturn','lreturn','freturn','dreturn','areturn','return','getstatic','putstatic','getfield','putfield','invokevirtual','invokespecial','invokestatic','invokeinterface','invokedynamic','new','newarray','anewarray','arraylength','athrow','checkcast','instanceof','monitorenter','monitorexit','wide','multianewarray','ifnull','ifnonnull','goto_w','jsr_w']
names[164]='if_icmple'
def dis(code,val):
    r=Reader(code);out=[]
    single={16,18,21,22,23,24,25,54,55,56,57,58,169,188}
    double={17,19,20,132,*range(153,169),*range(178,185),187,189,192,193,198,199}
    while r.p<len(code):
        at=r.p;op=r.u1();operand=''
        if op in single:
            x=r.u1();operand=val(x) if op==18 else str(x)
        elif op in double:
            x=r.u2();operand=val(x) if op in {19,20,*range(178,185),187,189,192,193} else str(x)
        elif op in (185,186):operand=val(r.u2());r.take(2)
        elif op==197:operand=val(r.u2())+' dimensions='+str(r.u1())
        elif op in (200,201):operand=str(r.u4())
        elif op in (170,171):
            while r.p%4:r.u1()
            r.u4()
            if op==170:low=r.u4();high=r.u4();r.take((high-low+1)*4)
            else:r.take(r.u4()*8)
            operand='switch table'
        elif op==196:
            inner=r.u1();operand=(names[inner]if inner<len(names)else str(inner))+' '+str(r.u2())
            if inner==132:operand+=' '+str(r.u2())
        out.append(f'{at:04d} {names[op] if op<len(names)else hex(op)} {operand}'.rstrip())
    return out
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('file',type=Path);ap.add_argument('--method');ap.add_argument('--out',type=Path);a=ap.parse_args();cp,val,methods=parse(a.file)
    result={'source':str(a.file),'methods':[{'name':n,'descriptor':d,'instructions':dis(c,val) if c and a.method and a.method in n else None}for n,d,c in methods]}
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    else:print(json.dumps(result,ensure_ascii=False,indent=2))
