"""Opaque, UV-preserving 3D corner folds. No opacity or image dissolves."""
from pathlib import Path
import bpy,sys,math,json,subprocess
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'corner_renders';OUT.mkdir(exist_ok=True)
PREVIEW='--preview' in sys.argv;REUSE='--reuse' in sys.argv
if not (ROOT/'material_textures/paper_medium_creases.png').exists():
    subprocess.run(['python',str(ROOT/'prepare_materials.py')],check=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=32
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
s.render.film_transparent=True;s.render.dither_intensity=0
s.view_settings.view_transform='Standard';s.view_settings.look='None';s.render.fps=30
s.world=bpy.data.worlds.new('Transparent world')
camera_data=bpy.data.cameras.new('Fixed camera');camera=bpy.data.objects.new('Camera',camera_data)
s.collection.objects.link(camera);camera.location=(0,0,40)
camera_data.type='ORTHO';camera_data.ortho_scale=19.2;camera_data.clip_end=100;s.camera=camera

image=bpy.data.images.load(str(ROOT/'assets/final_word_frame.png'));image.pack()
mat=bpy.data.materials.new('Opaque printed paper and fibrous reverse');mat.use_nodes=True
n=mat.node_tree.nodes;n.clear();l=mat.node_tree.links
tex=n.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Linear';tex.extension='EXTEND'
relief=n.new('ShaderNodeTexImage');relief.interpolation='Linear';relief.extension='EXTEND'
front=n.new('ShaderNodeMixRGB')
l.new(relief.outputs['Alpha'],front.inputs[0]);l.new(tex.outputs['Color'],front.inputs[1]);l.new(relief.outputs['Color'],front.inputs[2])
geom=n.new('ShaderNodeNewGeometry')
back=n.new('ShaderNodeMixRGB');back.blend_type='MIX';back.inputs[1].default_value=(.88,.86,.81,1);back.inputs[2].default_value=(.94,.925,.89,1)
back.inputs[0].default_value=.5
paint=n.new('ShaderNodeMixRGB');l.new(geom.outputs['Backfacing'],paint.inputs[0]);l.new(front.outputs[0],paint.inputs[1]);l.new(back.outputs[0],paint.inputs[2])
direction=Vector((-.28,.36,.89)).normalized()
dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=direction
l.new(geom.outputs['Normal'],dot.inputs[0])
absolute=n.new('ShaderNodeMath');absolute.operation='ABSOLUTE';l.new(dot.outputs['Value'],absolute.inputs[0])
light=n.new('ShaderNodeMapRange');light.clamp=True
light.inputs['From Min'].default_value=0;light.inputs['From Max'].default_value=direction.z
light.inputs['To Min'].default_value=.48;light.inputs['To Max'].default_value=1
l.new(absolute.outputs[0],light.inputs['Value'])
color=n.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1
l.new(paint.outputs[0],color.inputs[1]);l.new(light.outputs['Result'],color.inputs[2])
em=n.new('ShaderNodeEmission');l.new(color.outputs[0],em.inputs['Color'])
out=n.new('ShaderNodeOutputMaterial');l.new(em.outputs[0],out.inputs['Surface'])

def folded_tip(point,p1,p2,angle):
    axis=(p2-p1).normalized();rel=point-p1
    sign=1 if axis.cross(rel).z>0 else -1
    a=math.radians(angle)*sign
    return p1+rel*math.cos(a)+axis.cross(rel)*math.sin(a)+axis*axis.dot(rel)*(1-math.cos(a))

def mesh_for_pose(p):
    # Five-pixel overscan keeps the straight top/bottom portions opaque.
    X,Y=9.65,5.45
    lengths=p['corner_legs_pixels'];angles=p['angles_degrees']
    legs=[(v[0]/100,v[1]/100) for v in lengths]
    a0,b0=legs[0];a1,b1=legs[1];a2,b2=legs[2];a3,b3=legs[3]
    boundary=[(-X+a0,Y,0),(X-a1,Y,0),(X,Y-b1,0),(X,-Y+b2,0),
              (X-a2,-Y,0),(-X+a3,-Y,0),(-X,-Y+b3,0),(-X,Y-b0,0)]
    verts=[Vector(v) for v in boundary]+[Vector((0,0,p['center_lift']))]
    original_xy=[(v.x,v.y) for v in verts]
    faces=[(8,(i+1)%8,i) for i in range(8)]
    tips=[Vector((-X,Y,0)),Vector((X,Y,0)),Vector((X,-Y,0)),Vector((-X,-Y,0))]
    hinges=[(7,0),(1,2),(3,4),(5,6)]
    for corner,(tip,(a,b),angle) in enumerate(zip(tips,hinges,angles)):
        original_xy.append((tip.x,tip.y))
        verts.append(folded_tip(tip,verts[a],verts[b],angle))
        faces.append((9+corner,a,b))
    mesh=bpy.data.meshes.new('Connected corner-hinged sheet')
    mesh.from_pydata([tuple(v) for v in verts],[],faces);mesh.update()
    uv=mesh.uv_layers.new(name='Unchanged printed frame')
    for polygon in mesh.polygons:
        for li in polygon.loop_indices:
            x,y=original_xy[mesh.loops[li].vertex_index]
            uv.data[li].uv=((x+9.6)/19.2,(y+5.4)/10.8)
    return mesh

sizes=[(55,45),(85,65),(120,95),(155,120),(195,150),(225,175),
       (250,195),(275,215),(295,235),(315,250),(340,270),(360,285)]
angles=[12,27,44,63,85,106,126,143,155,164,171,176]
poses=[]
for i,((a,b),angle) in enumerate(zip(sizes,angles)):
    legs=[(a,b),(round(a*.88),round(b*.94)),(round(a*.94),round(b*.87)),(round(a*1.02),round(b*.96))]
    corner_angles=[angle,max(0,angle-12),max(0,angle-22),max(0,angle-7)]
    poses.append({'index':i,'corner_legs_pixels':legs,'angles_degrees':corner_angles,
                  'center_lift':0 if i<6 else [.04,.08,.14,.21,.30,.39][i-6],
                  'sheet_scale':1,
                  'surface_crease_stage':'flat' if i<5 else ('near_flat' if i==5 else ('light' if i<9 else 'medium')),
                  'top_bottom_straight_edges_locked':True})

surface_images={'flat':image}
for key,file in [('near_flat','paper_near_flat.png'),('light','paper_light_creases.png'),('medium','paper_medium_creases.png')]:
    surface_images[key]=bpy.data.images.load(str(ROOT/'material_textures'/file));surface_images[key].pack()

for p in poses:
    i=p['index']
    if PREVIEW and i not in (0,4,8,11):continue
    if REUSE and (OUT/f'corner_{i:02d}.png').exists():continue
    # Printed photographs supply successively stronger physical crease
    # relief on an opaque mesh. Their alpha only selects surface colour;
    # it never changes the opacity of the paper or reveals a background.
    relief.image=surface_images[p['surface_crease_stage']]
    mesh=mesh_for_pose(p);ob=bpy.data.objects.new('Rigid corner folds',mesh)
    s.collection.objects.link(ob);mesh.materials.append(mat);ob.scale=(p['sheet_scale'],)*3
    thick=ob.modifiers.new('Thin paper edge','SOLIDIFY');thick.thickness=.006;thick.offset=0
    s.render.filepath=str(OUT/f'corner_{i:02d}.png')
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
    print('CORNER POSE',i,'ANGLES',p['angles_degrees'],flush=True)
(ROOT/'corner_poses.json').write_text(json.dumps({'poses':poses,'material_alpha':1,'image_dissolves':False,
                                               'motion':'rigid triangles rotate about diagonal corner hinges; central sheet stays attached'},indent=2))
print('CORNERS COMPLETE',flush=True)
