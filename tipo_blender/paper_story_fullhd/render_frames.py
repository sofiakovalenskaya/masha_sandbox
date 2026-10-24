import bpy,os,hashlib,json,time,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
WORK=Path(os.environ.get('TIPO_FHD_WORK',str(Path(__file__).resolve().parent)));folder=WORK/'render_frames';folder.mkdir(exist_ok=True,parents=True)
assert hashlib.sha256((ROOT/'tipo_paper_story_v1_fixed.blend').read_bytes()).hexdigest()=='44d494117090ffd704107ff00682643d82b462190e473e14d0b461d5e686de68'
s=bpy.data.scenes['TIPO_Paper_Story_v1_fixed'];bpy.context.window.scene=s
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8';s.render.image_settings.compression=15
for f in range(1,751):
 p=folder/f'frame_{f:04}.png'
 if p.exists():
  with p.open('rb') as h:
   header=h.read(24);h.seek(-12,2);tail=h.read()
  assert header[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24])==(1920,1080)
  if tail!=b'\x00\x00\x00\x00IEND\xaeB\x60\x82':p.unlink()
 cached=1 if 2<=f<=13 else 31 if 32<=f<=67 else 523 if 524<=f<=750 else None
 if not p.exists():
  if cached is not None:os.link(folder/f'frame_{cached:04}.png',p)
  else:
   s.frame_set(f);s.eevee.taa_render_samples=16 if f in [31,523] else 4
   s.render.filepath=str(p);start=time.monotonic();bpy.ops.render.render(write_still=True)
   print('NATIVE_FHD_FRAME',f,'SECONDS',round(time.monotonic()-start,2),flush=True)
 temp=folder/'progress.tmp';temp.write_text(json.dumps({'frame':f,'total':750,'resolution':[1920,1080],'native_render':True}));temp.replace(folder/'progress.json')
print('FHD FRAMES COMPLETE',flush=True)
