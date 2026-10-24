import math,json
from pathlib import Path as FilePath
import numpy as np
from mathutils import Vector,Quaternion,Euler,Matrix

FPS=30
PITCH=.065*848/768
SIZE=.065
THICKNESS=.00025
FINAL_Z=.00010
BOX_CENTER=Vector((0,0,1.08))

def clamp(x,a=0.,b=1.):return max(a,min(b,x))
def smooth(x):
    x=clamp(x);return x*x*(3-2*x)
def smoother(x):
    x=clamp(x);return x*x*x*(x*(x*6-15)+10)
def blend(a,b,u):return a*(1-u)+b*u

class Path:
    def __init__(self,knots):
        self.t=np.array([k[0] for k in knots],float)
        self.p=np.array([k[1] for k in knots],float)
        self.m=np.zeros_like(self.p)
        for i in range(1,len(self.t)-1):
            if np.allclose(self.p[i-1],self.p[i]) or np.allclose(self.p[i+1],self.p[i]):continue
            self.m[i]=(self.p[i+1]-self.p[i-1])/(self.t[i+1]-self.t[i-1])
    def at(self,t):
        if t<=self.t[0]:return Vector(self.p[0])
        if t>=self.t[-1]:return Vector(self.p[-1])
        i=int(np.searchsorted(self.t,t)-1)
        dt=self.t[i+1]-self.t[i];u=(t-self.t[i])/dt
        v=(2*u**3-3*u*u+1)*self.p[i]+(u**3-2*u*u+u)*dt*self.m[i]+(-2*u**3+3*u*u)*self.p[i+1]+(u**3-u*u)*dt*self.m[i+1]
        return Vector(v)

CAM_KNOTS=[
 (0,(0,-.235,1.08),(0,0,1.08)),(3,(0,-.235,1.08),(0,0,1.08)),
 (4.65,(0,-.235,1.08),(0,0,1.08)),(5.55,(0,-.255,1.07),(0,0,1.06)),
 (6.4,(.025,-.35,1.00),(0,.02,.96)),(7.1,(-.07,-.46,.88),(.02,.02,.86)),
 (7.8,(.06,-.43,.74),(0,.02,.70)),(8.5,(.11,-.36,.55),(.005,.025,.50)),
 (9.2,(-.17,-.28,.43),(-.198499,-.017741,.349869)),
 (9.8,(-.25,-.20,.211),(-.250876,.011843,.080768)),
 (10.35,(-3*PITCH,-.11,.19),(-3*PITCH,0,.001)),
 (12.2,(-3*PITCH,-.11,.19),(-3*PITCH,0,.001)),
]
for i in range(1,8):
    x=(i-3.5)*PITCH
    CAM_KNOTS.append((12.2+i*.65,(x,-.11,.19),(x,0,.001)))
CAM_KNOTS += [(17.4,(3.5*PITCH,-.11,.19),(3.5*PITCH,0,.001)),
 (18.1,(.10,-.08,.65),(.03,.04,0)),(19.5,(0,PITCH,1.35),(0,PITCH,0))]
CAM_POS=Path([(t,p) for t,p,a in CAM_KNOTS])
CAM_AIM=Path([(t,a) for t,p,a in CAM_KNOTS])

HEROES=[
 (3,'H1','face_51',(-3.5*PITCH,0),10.10),
 (30,'H2','face_78',(-2.5*PITCH,0),10.43),
 (49,'H3','ref_H3',(-1.5*PITCH,0),10.76),
 (50,'H4','ref_H4',(-.5*PITCH,0),11.09),
 (47,'H5','face_95',(.5*PITCH,0),11.42),
 (22,'H6','face_70',(1.5*PITCH,0),11.75),
 (51,'H7','ref_H7',(2.5*PITCH,0),12.08),
 (4,'H8','face_52',(3.5*PITCH,0),12.41),
 (18,'V1','face_66',(1.5*PITCH,4*PITCH),11.4),
 (21,'V2','face_69',(1.5*PITCH,3*PITCH),11.7),
 (19,'V3','face_67',(1.5*PITCH,2*PITCH),12.0),
 (28,'V4','face_76',(1.5*PITCH,1*PITCH),12.3),
 (27,'V6','face_75',(1.5*PITCH,-1*PITCH),12.6),
 (39,'V7','face_87',(1.5*PITCH,-2*PITCH),12.8),
]
ORIGINAL_HEROES=HEROES
HEROES=[(47-i,h[1],h[2],h[3],h[4]+.4) for i,h in enumerate(ORIGINAL_HEROES)]
SEEDS={47-i:h[0] for i,h in enumerate(ORIGINAL_HEROES)}
HERO_MAP={h[0]:h for h in HEROES}
OFFSET_FILE=FilePath(__file__).with_name('motion_offsets.json')
OFFSETS=json.loads(OFFSET_FILE.read_text()) if OFFSET_FILE.exists() else {}
def offset_at(index,t):
    data=OFFSETS.get(str(index))
    if not data:return Vector((0,0,0))
    ts=data['t'];c=data['c']
    if t<=ts[0] or t>=ts[-1]:return Vector((0,0,0))
    k=int(np.searchsorted(ts,t)-1);u=t-ts[k]
    return Vector([((c[0][k][j]*u+c[1][k][j])*u+c[2][k][j])*u+c[3][k][j] for j in range(3)])


def box_pose(t):
    p=BOX_CENTER.copy()
    if t<.85:p.z=blend(.90,BOX_CENTER.z+.006,smoother(t/.85))
    elif t<1.20:p.z=blend(BOX_CENTER.z+.006,BOX_CENTER.z,smoother((t-.85)/.35))
    return p,Quaternion((0,1,0),math.pi*smooth((t-3.0)/1.6))

def lid_angles(t):
    theta=math.radians(115)*smooth((t-4.65)/1.0)
    phase=smooth((math.degrees(theta)-40)/60)
    flap=blend(theta,-math.pi/2,phase)
    return -theta,flap

def camera_pose(t):
    p=CAM_POS.at(t);a=CAM_AIM.at(t)
    forward=(a-p).normalized()
    amount=smooth((t-17.4)/2.1)
    up_hint=Vector((0,amount,1-amount)).normalized()
    right=forward.cross(up_hint).normalized()
    up=right.cross(forward).normalized()
    q=Matrix(((right.x,up.x,-forward.x),(right.y,up.y,-forward.y),(right.z,up.z,-forward.z))).to_quaternion()
    return p,q,a

def bezier(p0,p1,p2,p3,u):
    return p0*(1-u)**3+p1*(3*(1-u)**2*u)+p2*(3*(1-u)*u*u)+p3*u**3

class CardMotion:
    def __init__(self,index,initial_center,initial_rotation):
        self.index=index;self.initial_center=initial_center;self.initial_rotation=initial_rotation
        self.active=index>=31
        self.release=5.8+(60-index)*.08 if self.active else 1e6
        self.clear=self.release+.31
        self.hero=HERO_MAP.get(index)
        rng=np.random.default_rng(20261024+SEEDS.get(index,index)*47)
        self.phase=float(rng.uniform(0,math.tau))
        self.omega=float(rng.uniform(1.1,2.0))
        self.spin=(math.tau*(1 if index%7==0 or index in [58,59] else 0))
        self.flip=math.tau if index%8==0 or index==59 else 0
        if self.hero:
            self.land=self.hero[4];x,y=self.hero[3]
        else:
            angle=float(rng.uniform(0,math.tau));radius=float(rng.uniform(.85,1.5))
            x,y=math.cos(angle)*radius,math.sin(angle)*radius
            self.land=float(rng.uniform(10.2,13.8))
        bp,bq=box_pose(self.release)
        self.p0=bp+bq@self.initial_center-Vector((0,0,.085))
        self.q0=bq@self.initial_rotation
        self.p3=Vector((x,y,FINAL_Z))
        self.p1=Vector((float(rng.uniform(-.18,.18)),float(rng.uniform(-.11,.15)),.78))
        self.p2=Vector((x+float(rng.uniform(-.07,.07)),y+float(rng.uniform(-.05,.05)),.14))
        # Несколько близких пролётов по краям кадра создают выраженный параллакс.
        if index in [60,59,58]:
            hit={60:6.9,59:7.7,58:8.5}[index]
            u=clamp((hit-self.clear)/(self.land-self.clear),.1,.65)
            cp,cq,aim=camera_pose(hit)
            f=(aim-cp).normalized();right=cq@Vector((1,0,0))
            desired=cp+f*.19+right*(.065 if index%2 else -.065)
            self.p1=(desired-self.p0*(1-u)**3-self.p2*(3*(1-u)*u*u)-self.p3*u**3)/(3*(1-u)**2*u)
    def pose(self,t):
        if not self.active or t<=self.release:
            bp,bq=box_pose(t)
            return bp+bq@self.initial_center,bq@self.initial_rotation,(0.,0.,0.)
        if t<=self.clear:
            bp,bq=box_pose(self.release)
            p=bp+bq@self.initial_center-Vector((0,0,.085*smooth((t-self.release)/(.31))))
            return p,self.q0,(0.,0.,0.)
        u=clamp((t-self.clear)/(self.land-self.clear))
        raw=u
        if u>.85:
            v=(u-.85)/.15;u=.85+.15*(v+4*v**3-7*v**4+3*v**5)
        p=bezier(self.p0,self.p1,self.p2,self.p3,u)
        p.y=blend(self.p0.y-.05*(t-self.clear),p.y,smoother((t-self.clear-.35)/.5))
        p+=offset_at(self.index,t)
        env=math.sin(math.pi*u)**2
        if u<1:
            p+=Vector((.012*math.sin((t-self.clear)*4+self.phase)*env,
                       .008*math.sin((t-self.clear)*3.3+self.phase)*env,0))
        final=Quaternion((0,1,0),math.pi)
        align=smooth((u-.58)/.42)
        base=self.q0.slerp(final,align)
        elapsed=t-self.clear
        tilt=Euler((.35*math.sin(elapsed*3.5+self.phase)*env+self.flip*smooth((u-.10)/.80),
                    .55*math.sin(elapsed*2.9+self.phase*.7)*env,
                    self.spin*smooth(u)+.25*math.sin(elapsed*2.2+self.phase)*env),'XYZ').to_quaternion()
        q=base@tilt
        b1=.75*math.sin(elapsed*math.tau*self.omega+self.phase)*env
        b2=.55*math.sin(elapsed*math.tau*(self.omega*.8)+self.phase*.6)*env
        tw=.35*math.sin(elapsed*math.tau*(self.omega*.7)+self.phase)*env
        if u>=1:
            q=final;b1=b2=tw=0
        return p,q,(b1,b2,tw)

_h=CardMotion(47,Vector((0,-.008,0)),Quaternion((1,0,0),math.pi/2))
for _t,_rel in [(9.2,(.028499,-.262259,.080131)),(9.8,(.000876,-.211843,.130232))]:
    _p=_h.pose(_t)[0]
    for _i,_k in enumerate(CAM_KNOTS):
        if _k[0]==_t:CAM_KNOTS[_i]=(_t,tuple(_p+Vector(_rel)),tuple(_p))
CAM_POS=Path([(t,p) for t,p,a in CAM_KNOTS])
CAM_AIM=Path([(t,a) for t,p,a in CAM_KNOTS])
