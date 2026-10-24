import bpy,shutil,time,json,os
from pathlib import Path
s=bpy.data.scenes['TIPO_Paper_Story_v1_fixed'];bpy.context.window.scene=s
s.render.resolution_percentage=40;s.eevee.taa_render_samples=4;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.compression=15
w=Path(os.environ.get('TIPO_PREVIEW_DIR',str(Path(__file__).resolve().parent/'render_frames')));w.mkdir(exist_ok=True,parents=True)
for f in range(int(os.environ.get('TIPO_START_FRAME','1')),int(os.environ.get('TIPO_END_FRAME','750'))+1):
 p=w/f'frame_{f:04}.png'
 source=1 if 2<=f<=13 else 31 if 32<=f<=67 else 523 if 524<=f<=750 else None
 if not p.exists():
  if source is not None:shutil.copyfile(w/f'frame_{source:04}.png',p)
  else:
   s.frame_set(f);s.render.filepath=str(p);bpy.ops.render.render(write_still=True)
 (w/'progress.json').write_text(json.dumps({'frame':f,'total':750}))
print('PREVIEW COMPLETE',flush=True)
