"""Deterministic 2D animation using the user's original PNG letterforms.

Coordinates are Full HD pixels. No replacement font is used. The same poses
are used by the offline compositor and the editable Blender scene.
"""
import json, math, random
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'assets.json').read_text())
START={'visual':.2,'game':.7,'attention':1.2,'exclamation':101/30}
CYCLE_START_FRAME=69
CYCLE_END_FRAME=101
BOX_START=5.
SEAM_START=7.4
PIVOTS={}
for group in ['visual','game','attention']:
    glyphs=[g for g in DATA['letters'] if g['group']==group]
    left=min(g['center'][0]-g['size'][0]/2 for g in glyphs)
    right=max(g['center'][0]+g['size'][0]/2 for g in glyphs)
    top=min(g['center'][1]-g['size'][1]/2 for g in glyphs)
    bottom=max(g['center'][1]+g['size'][1]/2 for g in glyphs)
    PIVOTS[group]=((left+right)/2,(top+bottom)/2)

def ease_out(u):
    return 1-(1-max(0,min(1,u)))**3

def gentle(age):
    if age>=.27:return 1.
    if age<.15:
        u=ease_out(age/.15);return .98+.028*u
    u=max(0,min(1,(age-.15)/.12));return 1.008-.008*(u*u*(3-2*u))

def variant_at(t):
    # Start from the flower O, so the beginning of the first full cycle is
    # visible too: flower -> 1,2,3,4 -> 1,2,3,4. Four frames per drawing.
    if t<CYCLE_START_FRAME/30:return 3
    if t>=CYCLE_END_FRAME/30:return 3
    return min(7,int((t*30-CYCLE_START_FRAME)/4+1e-7))%4

RNG=random.Random(871904)
BURST={}
for glyph in DATA['letters']+[DATA['exclamation']]:
    x,y=glyph['center'];dx=x-960
    direction=1 if dx>0 else -1
    if abs(dx)<90:direction=RNG.choice([-1,1])
    # A smaller contact impulse, aerodynamic damping and gravity replace the
    # fast linear explosion. Angular velocity decays independently of travel.
    lateral=glyph['id']%5 in (0,1,3)
    if lateral:
        vx=direction*RNG.uniform(700,960)
        vy=RNG.uniform(-260,60)
        gravity=RNG.uniform(225,315)
    else:
        vx=direction*RNG.uniform(610,820)
        vy=-RNG.uniform(720,940)
        gravity=RNG.uniform(220,280)
    # Trigger the impulse as the rising box reaches the lower edge of a row;
    # letters farther from the impact react a fraction of a second later.
    bottom=y+glyph['size'][1]/2
    contact=BOX_START+1.12*(1-max(0,min(1,(bottom-148)/950))**(1/3))
    start=contact+abs(dx)*.00015+RNG.uniform(-.012,.018)
    BURST[glyph['id']]={'start':start,'vx':vx,'vy':vy,'gravity':gravity,
                        'direction':'side' if lateral else 'up',
                        'drag':RNG.uniform(.12,.19),
                        'spin_drag':RNG.uniform(.55,.85),
                        'spin':RNG.uniform(65,165)*RNG.choice([-1,1])}

# Deliberately irregular held poses, about 10 distinct drawings per second.
# The small position / rotation / scale changes preserve the original scribble.
STOP=[(0,0,0,1),(-1.8,.7,-2.4,.99),(1.2,-1.1,1.8,1.012),
      (-.6,-.3,-.8,1),(1.7,.9,2.8,1.008),(-1.1,-1,-1.7,.993),
      (.4,.4,.6,1.015),(1.3,-.6,1.6,1),(-1.6,.5,-2.1,.989),
      (.8,-1.2,.9,1.007),(-.2,.3,-.4,1)]

def pose(glyph,t):
    age=t-START[glyph['group']]
    if age<0:return None
    asset=glyph['asset'];size=glyph['size'][:];x,y=glyph['center']
    angle=0.;scale=1.
    if glyph['id']==DATA['o_glyph_id']:
        v=DATA['o_variants'][variant_at(t)];asset=v['asset'];size=v['size'][:]
    if glyph['group']=='exclamation':
        dx,dy,angle,scale=STOP[int((t-START['exclamation'])*10+1e-7)%len(STOP)]
        x+=dx;y+=dy
    else:
        scale=gentle(age);px,py=PIVOTS[glyph['group']]
        x=px+(x-px)*scale;y=py+(y-py)*scale
    b=BURST[glyph['id']];flight=t-b['start']
    if flight>=0:
        # Launch each glyph independently. The exclamation retains its last
        # stepped pose at impact instead of jittering during free flight.
        if glyph['group']=='exclamation':
            dx,dy,angle,scale=STOP[int((b['start']-START['exclamation'])*10)%len(STOP)]
            x,y=glyph['center'][0]+dx,glyph['center'][1]+dy
        travel=-math.expm1(-b['drag']*flight)/b['drag']
        x+=b['vx']*travel
        y+=b['vy']*travel+b['gravity']/b['drag']*(flight-travel)
        angle+=b['spin']*(-math.expm1(-b['spin_drag']*flight))/b['spin_drag']
    return {'asset':asset,'center':[x,y],'size':[v*scale for v in size],
            'angle':angle,'flight':max(0,flight)}

def box_pose(t):
    if t<BOX_START:return None
    # Fixed image size and perspective; arrive at the approved frame exactly.
    offset=950*(1-ease_out((t-BOX_START)/1.12))
    return {'center':[960,540.5+offset],'size':DATA['box']['size'][:],'angle':0,
            'asset':DATA['box']['asset']}

def all_poses(t):
    return [(g,pose(g,t)) for g in DATA['letters']+[DATA['exclamation']]]

def visible(p):
    if p is None:return False
    x,y=p['center'];w,h=p['size'];r=math.hypot(w,h)/2
    return x+r>=0 and x-r<1920 and y+r>=0 and y-r<1080
