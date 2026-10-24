import math
import numpy as np
from mathutils import Vector,Quaternion,Euler,Matrix

FPS=30
PITCH=.065*848/768
SIZE=.065
THICKNESS=.00025
FINAL_Z=.00010
BOX_CENTER=Vector((0,0,1.08))
_TRACKERS=None
RELEASE_START=5.8
RELEASE_GAP=.55
CLEAR_TIME=.35
CLEAR_DROP=.10
FALL_SPEED=.22
BRAKE_HEIGHT=.06
BRAKE_START=CLEAR_TIME+(BOX_CENTER.z-CLEAR_DROP-BRAKE_HEIGHT)/FALL_SPEED
BRAKE_TIME=2*(BRAKE_HEIGHT-FINAL_Z)/FALL_SPEED
FLIGHT_TIME=BRAKE_START+BRAKE_TIME

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
        i=int(np.searchsorted(self.t,t)-1);dt=self.t[i+1]-self.t[i];u=(t-self.t[i])/dt
        return Vector((2*u**3-3*u*u+1)*self.p[i]+(u**3-2*u*u+u)*dt*self.m[i]+(-2*u**3+3*u*u)*self.p[i+1]+(u**3-u*u)*dt*self.m[i+1])

CAM_KNOTS=[
 (4.65,(0,-.235,1.08),(0,0,1.08)),
 (5.65,(0,-.34,1.04),(0,0,1.02)),
 (6.6,(.025,-.36,.99),(0,0,.94)),
 (7.5,(-.05,-.42,.80),(0,.015,.74)),
 (8.5,(.06,-.43,.60),(0,.02,.52)),
 (9.3,(-.10,-.36,.46),(-.13,0,.35)),
 (10.2,(-.20,-.28,.30),(-.22,0,.14)),
 (11.0,(-.25,-.20,.20),(-.25,0,.035)),
 (11.6,(-3.5*PITCH,-.11,.19),(-3.5*PITCH,0,.001)),
 (12.2,(-3.5*PITCH,-.11,.19),(-3.5*PITCH,0,.001)),
]
for i in range(1,8):
    x=(i-3.5)*PITCH
    CAM_KNOTS.append((12.2+i*.65,(x,-.11,.19),(x,0,.001)))
CAM_KNOTS += [
 (17.4,(3.5*PITCH,-.11,.19),(3.5*PITCH,0,.001)),
 (18.5,(.16,-.12,.40),(.08,.035,0)),
 (20.0,(.07,-.08,.75),(.03,.055,0)),
 (22.4,(.02,.015,1.20),(.015,.065,0)),
 (24.0,(0,PITCH,1.35),(0,PITCH,0)),
]
CAM_POS=Path([(t,p) for t,p,a in CAM_KNOTS])
CAM_AIM=Path([(t,a) for t,p,a in CAM_KNOTS])

SLOTS=[
 ('H1','face_51',(-3.5*PITCH,0)),
 ('H2','face_78',(-2.5*PITCH,0)),
 ('H3','ref_H3',(-1.5*PITCH,0)),
 ('H4','ref_H4',(-.5*PITCH,0)),
 ('H5','face_95',(.5*PITCH,0)),
 ('H6','face_70',(1.5*PITCH,0)),
 ('H7','ref_H7',(2.5*PITCH,0)),
 ('H8','face_52',(3.5*PITCH,0)),
 ('V1','face_66',(1.5*PITCH,4*PITCH)),
 ('V2','face_69',(1.5*PITCH,3*PITCH)),
 ('V3','face_67',(1.5*PITCH,2*PITCH)),
 ('V4','face_76',(1.5*PITCH,1*PITCH)),
 ('V6','face_75',(1.5*PITCH,-1*PITCH)),
 ('V7','face_87',(1.5*PITCH,-2*PITCH)),
]
HEROES=[(60-r,slot,face,xy,RELEASE_START+r*RELEASE_GAP+FLIGHT_TIME) for r,(slot,face,xy) in enumerate(SLOTS)]
HERO_MAP={h[0]:h for h in HEROES}

def box_pose(t):
    p=BOX_CENTER.copy();p.z=blend(.90,BOX_CENTER.z,smoother(t/1.0))
    q=Quaternion((0,1,0),math.pi*smooth((t-3.0)/1.6))
    return p,q

def lid_angles(t):
    theta=math.radians(115)*smooth((t-4.65)/1.0)
    phase=smooth((math.degrees(theta)-40)/60)
    return -theta,blend(theta,-math.pi/2,phase)

def camera_pose(t):
    if t<=4.65:
        p=Vector((0,-.235,1.08));a=Vector((0,0,1.08))
        if 3.0<t<4.6:p.y-=.020*math.sin(math.pi*(t-3.0)/1.6)**2
    else:p=CAM_POS.at(t);a=CAM_AIM.at(t)
    global _TRACKERS
    follow=smooth((t-5.95)/.55)*(1-smooth((t-11.0)/.6))
    if follow>0:
        if _TRACKERS is None:
            rotation=Quaternion((1,0,0),math.pi/2)
            _TRACKERS=[CardMotion(60,Vector((0,-.008,0)),rotation),CardMotion(59,Vector((0,-.0077,0)),rotation)]
        p.y*=1+.25*follow
        directions=[(tracker.pose(t)[0]-p).normalized() for tracker in _TRACKERS]
        direction=(directions[0]+directions[1]).normalized()
        a=a.lerp(p+direction*.5,follow)
    f=(a-p).normalized()
    amount=smooth((t-17.4)/4.5)
    up_hint=Vector((0,amount,1-amount)).normalized()
    right=f.cross(up_hint).normalized();up=right.cross(f).normalized()
    q=Matrix(((right.x,up.x,-f.x),(right.y,up.y,-f.y),(right.z,up.z,-f.z))).to_quaternion()
    return p,q,a

def height(age):
    if age<=CLEAR_TIME:
        u=clamp(age/CLEAR_TIME)
        drop=(-2*u**3+3*u*u)*CLEAR_DROP+(u**3-u*u)*CLEAR_TIME*FALL_SPEED
        return BOX_CENTER.z-drop
    if age<=BRAKE_START:return BOX_CENTER.z-CLEAR_DROP-FALL_SPEED*(age-CLEAR_TIME)
    u=clamp((age-BRAKE_START)/BRAKE_TIME)
    return (2*u**3-3*u*u+1)*BRAKE_HEIGHT+(u**3-2*u*u+u)*BRAKE_TIME*(-FALL_SPEED)+(-2*u**3+3*u*u)*FINAL_Z

class CardMotion:
    def __init__(self,index,initial_center,initial_rotation):
        self.index=index;self.initial_center=initial_center;self.initial_rotation=initial_rotation
        self.hero=HERO_MAP.get(index)
        self.rank=60-index
        self.release=RELEASE_START+self.rank*RELEASE_GAP if self.hero else 1e6
        self.clear=self.release+CLEAR_TIME
        self.land=self.release+FLIGHT_TIME if self.hero else 9.6
        rng=np.random.default_rng(20261024+index*47)
        self.phase=float(rng.uniform(0,math.tau));self.omega=float(rng.uniform(.9,1.5))
        self.lane_x=float(rng.uniform(-.11,.11))
        ys=[-.13,.14,-.21,.07,-.10,.16,-.17,.05,-.20,.18,-.12,.10,-.20,.12]
        self.lane_y=ys[self.rank] if self.hero else 0
        bp,bq=box_pose(self.release if self.hero else 6)
        self.q0=bq@self.initial_rotation
        self.p0=bp+bq@self.initial_center
        self.target=Vector((*self.hero[3],FINAL_Z)) if self.hero else None
        self.flip=self.hero and self.rank in [1,4,9]
        self.spin=self.hero and self.rank in [3,8,12]
    def pose(self,t):
        if not self.hero or t<=self.release:
            bp,bq=box_pose(t)
            return bp+bq@self.initial_center,bq@self.initial_rotation,(0.,0.,0.)
        age=t-self.release
        if age<=CLEAR_TIME:
            p=self.p0.copy();p.z+=height(age)-BOX_CENTER.z
            return p,self.q0,(0.,0.,0.)
        if age>=FLIGHT_TIME:
            return self.target.copy(),Quaternion((0,1,0),math.pi),(0.,0.,0.)
        s=age-CLEAR_TIME
        fan=smooth(s/.60);settle=smooth((s-1.8)/1.7)
        flutter=fan*(1-settle)
        x=blend(blend(self.p0.x,self.lane_x,fan),self.target.x,settle)
        y=blend(blend(self.p0.y,self.lane_y,fan),self.target.y,settle)
        x+=.010*math.sin(s*3+self.phase)*flutter
        y+=.006*math.sin(s*2.7+self.phase)*flutter
        p=Vector((x,y,height(age)+self.initial_center.z))
        final=Quaternion((0,1,0),math.pi)
        align=smooth((s-2.1)/1.4)
        base=self.q0.slerp(final,align)
        flip=math.tau*smooth((s-.5)/2.3) if self.flip else 0
        spin=math.tau*smooth((s-.4)/2.4) if self.spin else 0
        tilt=Euler((.32*math.sin(s*3.5+self.phase)*flutter+flip,
                    .40*math.sin(s*2.9+self.phase*.7)*flutter,
                    spin+.22*math.sin(s*2.2+self.phase)*flutter),'XYZ').to_quaternion()
        q=base@tilt
        bends=(.60*math.sin(s*math.tau*self.omega+self.phase)*flutter,
               .45*math.sin(s*math.tau*self.omega*.8+self.phase*.6)*flutter,
               .30*math.sin(s*math.tau*self.omega*.7+self.phase)*flutter)
        return p,q,bends
