"""Render a UV-textured sheet crumpling into a small paper ball, in held poses."""
import bpy, math, json, sys
from pathlib import Path
import numpy as np
from mathutils import Vector, Euler

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'paper_renders';OUT.mkdir(exist_ok=True)
PREVIEW='--preview' in sys.argv
REUSE='--reuse' in sys.argv
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=32
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
s.render.film_transparent=True;s.render.dither_intensity=0
s.view_settings.view_transform='Standard';s.view_settings.look='None'
s.render.fps=30
s.world=bpy.data.worlds.new('Transparent world')
s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
camdata=bpy.data.cameras.new('Fixed front camera');cam=bpy.data.objects.new('Camera',camdata)
s.collection.objects.link(cam);cam.location=(0,0,40);camdata.type='ORTHO';camdata.ortho_scale=19.2;camdata.clip_end=100;s.camera=cam

image=bpy.data.images.load(str(ROOT/'assets/final_word_frame.png'));image.pack()
mat=bpy.data.materials.new('Printed blue paper / ivory unprinted reverse');mat.use_nodes=True
n=mat.node_tree.nodes;n.clear();links=mat.node_tree.links
tex=n.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Linear';tex.extension='EXTEND'
geom=n.new('ShaderNodeNewGeometry')
back=n.new('ShaderNodeMixRGB');back.blend_type='MIX'
links.new(geom.outputs['Backfacing'],back.inputs[0]);links.new(tex.outputs['Color'],back.inputs[1]);back.inputs[2].default_value=(.94,.915,.86,1)
dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=Vector((-.32,.42,.85)).normalized()
links.new(geom.outputs['Normal'],dot.inputs[0])
light=n.new('ShaderNodeMapRange');light.clamp=True
light.inputs['From Min'].default_value=-.65;light.inputs['From Max'].default_value=.85
light.inputs['To Min'].default_value=.17;light.inputs['To Max'].default_value=1.08
links.new(dot.outputs['Value'],light.inputs['Value'])
mult=n.new('ShaderNodeMixRGB');mult.blend_type='MULTIPLY';mult.inputs[0].default_value=1
links.new(back.outputs[0],mult.inputs[1]);links.new(light.outputs['Result'],mult.inputs[2])
em=n.new('ShaderNodeEmission');links.new(mult.outputs[0],em.inputs['Color']);em.inputs['Strength'].default_value=1
out=n.new('ShaderNodeOutputMaterial');links.new(em.outputs[0],out.inputs['Surface'])

NX,NY=64,36
rng=np.random.default_rng(252610)
uvs=[];flat=[];ball=[];creases=[]
for j in range(NY+1):
    for i in range(NX+1):
        u=i/NX;v=j/NY
        if i not in (0,NX):u+=float(rng.uniform(-.22,.22))/NX
        if j not in (0,NY):v+=float(rng.uniform(-.22,.22))/NY
        a,b=(u-.5)*2,(v-.5)*2
        crease=(abs(math.sin(a*15+b*4))-.5)*.75+(abs(math.sin(b*17-a*3))-.5)*.65
        crease+=(abs(math.sin(a*6-b*9+1.2))-.5)*.65
        az=a*math.pi*1.65+.27*math.sin(b*6)
        ph=b*math.pi*.83+math.pi/2
        radius=1.35*(1+.09*math.sin(az*5)+.07*math.sin(ph*8)+.18*crease)
        uvs.append((u,v));flat.append((a*9.6,b*5.4,0))
        ball.append((radius*math.sin(ph)*math.cos(az),radius*math.cos(ph),radius*math.sin(ph)*math.sin(az)))
        creases.append(crease)
faces=[]
for j in range(NY):
    for i in range(NX):
        a=j*(NX+1)+i;b=a+1;c=a+NX+1;d=c+1
        faces.extend([(a,b,d),(a,d,c)] if (i+j)%2==0 else [(a,b,c),(b,d,c)])
mesh=bpy.data.meshes.new('Connected printed paper mesh');mesh.from_pydata(flat,[],faces);mesh.update()
uv=mesh.uv_layers.new(name='Original entire frame')
for polygon in mesh.polygons:
    polygon.use_smooth=False
    for loop in polygon.loop_indices:uv.data[loop].uv=uvs[mesh.loops[loop].vertex_index]
paper=bpy.data.objects.new('Whole frame becomes one sheet',mesh);s.collection.objects.link(paper);mesh.materials.append(mat)
thick=paper.modifiers.new('Thin paper edges','SOLIDIFY');thick.thickness=.009;thick.offset=0
flat=np.asarray(flat);ball=np.asarray(ball);creases=np.asarray(creases)

def geometry(t):
    blend=t**.92
    p=(1-blend)*flat+blend*ball
    envelope=math.sin(math.pi*t)
    a=flat[:,0]/9.6;b=flat[:,1]/5.4
    # Edges gather in unequal folds, while the image remains attached by UV.
    p[:,0]+=envelope*.70*np.sin(b*5+a*3)*(a*a+.15)
    p[:,1]+=envelope*.55*np.sin(a*6-b*4)*(b*b+.15)
    p[:,2]+=envelope*(1.65*creases+.38*(a*a+b*b))
    return p

steps=[.025,.065,.12,.19,.28,.38,.49,.60,.72,.83,.93,1.0]
poses=[]
for i,t in enumerate(steps):
    poses.append({'index':i,'kind':'crumple','progress':t,'center_y':0.,'rotation_z':float(((-1)**i)*.035*t)})
for i,y in enumerate([-.45,-1.5,-3.15,-5.65,-9.0]):
    poses.append({'index':len(steps)+i,'kind':'exit','progress':1.,'center_y':y,'rotation_z':[-.12,.20,.40,.67,.95][i]})

for pose in poses:
    index=pose['index'];s.frame_set(index*3+93)
    coords=geometry(pose['progress'])
    for v,co in zip(mesh.vertices,coords):v.co=co
    paper.location=(0,pose['center_y'],0)
    paper.rotation_euler=(0,0,pose['rotation_z'])
    mesh.update()
    if PREVIEW and index not in [0,4,8,11]:continue
    if REUSE and (OUT/f'paper_{index:02d}.png').exists():
        print('REUSE PAPER POSE',index,flush=True)
        continue
    s.render.filepath=str(OUT/f'paper_{index:02d}.png')
    bpy.ops.render.render(write_still=True)
    print('PAPER POSE',index,pose['kind'],pose['progress'],flush=True)

(ROOT/'paper_poses.json').write_text(json.dumps({'width':1920,'height':1080,'vertices':len(flat),'triangles':len(faces),'connected_sheet':True,'uv_source':'assets/final_word_frame.png','poses':poses},indent=2))
print('PAPER RENDERS COMPLETE',flush=True)
