import math
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
def blend(a,b,u):return a*(1-u)+b*u

class Path:
    def __init__(self,knots):
        self.t=np.array([k[0] for k in knots],float)
        self.p=np.array([k[1] for k in knots],float)
        self.m=np.zeros_like(self.p)
        for i in range(1,len(self.t)-1):self.m[i]=(self.p[i+1]-self.p[i-1])/(self.t[i+1]-self.t[i-1])
    def at(self,t):
        if t<=self.t[0]:return Vector(self.p[0])
        if t>=self.t[-1]:return Vector(self.p[-1])
        i=int(np.searchsorted(self.t,t)-1)
        dt=self.t[i+1]-self.t[i];u=(t-self.t[i])/dt
        v=(2*u**3-3*u*u+1)*self.p[i]+(u**3-2*u*u+u)*dt*self.m[i]+(-2*u**3+3*u*u)*self.p[i+1]+(u**3-u*u)*dt*self.m[i+1]
        return Vector(v)

CAM_KNOTS=[
 (0,(0,-.22,1.08),(0,0,1.08)),(2.2,(0,-.22,1.08),(0,0,1.08)),
 (4.2,(0,-.22,1.08),(0,0,1.08)),(5.55,(0,-.255,1.07),(0,0,1.06)),
 (6.4,(.025,-.35,1.00),(0,.02,.96)),(7.1,(-.07,-.46,.88),(.02,.02,.86)),
 (7.8,(.06,-.43,.74),(0,.02,.70)),(8.5,(.11,-.36,.55),(.005,.025,.50)),
 (9.2,(-.17,-.28,.43),(-.198499,-.017741,.349869)),(9.8,(-.25,-.20,.211),(-.250876,.011843,.080768)),
 (10.35,(-3*PITCH,-.11,.19),(-3*PITCH,0,.001)),(11.5,(-3*PITCH,-.11,.19),(-3*PITCH,0,.001)),
]
for i in range(1,8):
    x=(i-3.5)*PITCH
    CAM_KNOTS.append((11.5+i*.5,(x,-.11,.19),(x,0,.001)))
CAM_KNOTS.append((15.7,(.21,.10,.24),(.15,.21,.001)))
for j in range(7):
    y=(4-j)*PITCH
    CAM_KNOTS.append((16.3+j*(3.5/6),(1.5*PITCH,y-.14,.25),(1.5*PITCH,y,.001)))
CAM_KNOTS += [(20.8,(.07,-.12,.52),(.05,-.03,0)),(22,(.02,.03,1.05),(.02,.05,0)),(24,(0,PITCH,1.35),(0,PITCH,0))]
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
HERO_MAP={h[0]:h for h in HEROES}

def box_pose(t):
    hover=.002*math.sin(t*math.tau*.65)*(1-smooth((t-3.9)/1.1))
    p=BOX_CENTER+Vector((0,0,hover))
    q=Quaternion((0,1,0),math.pi*smooth((t-2.2)/1.9))
    return p,q

def lid_angles(t):
    theta=math.radians(115)*smooth((t-4.15)/1.45)
    phase=smooth((math.degrees(theta)-40)/60)
    flap=blend(theta,-math.pi/2,phase)
    return -theta,flap

def camera_pose(t):
    p=CAM_POS.at(t);a=CAM_AIM.at(t)
    forward=(a-p).normalized()
    amount=smooth((t-19.8)/3.2)
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
        self.release=5.55+(60-index)*.035
        self.clear=self.release+.31
        self.hero=HERO_MAP.get(index)
        rng=np.random.default_rng(20261024+index*47)
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
        if t<=self.release:
            bp,bq=box_pose(t)
            return bp+bq@self.initial_center,bq@self.initial_rotation,(0.,0.,0.)
        if t<=self.clear:
            bp,bq=box_pose(self.release)
            p=bp+bq@self.initial_center-Vector((0,0,.085*smooth((t-self.release)/(.31))))
            return p,self.q0,(0.,0.,0.)
        u=clamp((t-self.clear)/(self.land-self.clear))
        p=bezier(self.p0,self.p1,self.p2,self.p3,u)
        env=math.sin(math.pi*u)**.7
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
        if .1<p.z<1.1 and t<self.land:
            cp,cq,aim=camera_pose(t)
            delta=p-cp
            if delta.length<.078:
                direction=delta.normalized() if delta.length>.0001 else cq@Vector((1,0,0))
                p=cp+direction*.078
        return p,q,(b1,b2,tw)
