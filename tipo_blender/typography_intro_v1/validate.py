"""Check the deliverables and the edit seam against the approved source."""
import json, hashlib, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import animate as A

ROOT=A.ROOT;DELIVERY=ROOT.parent;WORK=Path('/workspace/tipo_typography_work')
original=Path('/workspace/tipo_fullhd_work/render_frames/frame_0031.png')
last=WORK/'frames/frame_0269.png'
assert np.array_equal(np.asarray(Image.open(original)),np.asarray(Image.open(last)))
assert np.array_equal(np.asarray(Image.open(WORK/'frames/frame_0249.png')),np.asarray(Image.open(last)))
assert len(A.DATA['letters'])==30
assert [g['letter'] for g in A.DATA['letters'] if g['row']==2]==list('НАВНИМАТЕЛЬНОСТЬ')
sequence=[A.variant_at(f/30)+1 for f in range(102,134,4)]
assert sequence==[1,2,3,4,1,2,3,4]
assert not any(A.visible(p) for _,p in A.all_poses(8.4))
for g in A.DATA['letters']:
    assert A.pose(g,A.START[g['group']]-.01) is None
    p=A.pose(g,A.START[g['group']]+.3)
    assert np.allclose(p['center'],g['center'])
for f in range(135,177,3):
    g=A.DATA['exclamation'];poses=[A.pose(g,ff/30) for ff in range(f,f+3)]
    # Check exact three-frame held blocks at the actual starting phase.
    start=134+3*((f-134)//3)
    poses=[A.pose(g,ff/30) for ff in range(start,start+3)]
    assert poses[0]==poses[1]==poses[2]

report={'native_resolution':[1920,1080],'fps':30,'background_rgb':A.DATA['background'],
        'individual_letters':30,'individual_exclamation':1,'o_cycle_sequence':sequence,
        'o_frames_per_variant':4,'exclamation_pose_hold_frames':3,
        'source_png_final_seam_pixel_identical':True,'pre_seam_hold_pixel_identical':True,
        'approved_source_frame':31,'continue_from_source_frame':32,
        'original_assets':A.DATA['original_assets'],'videos':{}}
for filename,count in [('tipo_typography_intro_v1_1080p.mp4',270),('tipo_intro_and_paper_story_v1_1080p.mp4',989)]:
    path=DELIVERY/filename
    p=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
    video=next(s for s in p['streams'] if s['codec_type']=='video')
    assert video['codec_name']=='h264' and video['width']==1920 and video['height']==1080
    assert video['avg_frame_rate']=='30/1' and int(video['nb_read_frames'])==count
    assert not any(s['codec_type']=='audio' for s in p['streams'])
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-f','null','-'],check=True)
    report['videos'][filename]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'frames':count,'duration_seconds':float(p['format']['duration']),'codec':'H.264 High',
        'pixel_format':video['pix_fmt'],'full_decode_passed':True}
report['blender_project']={'filename':'tipo_typography_intro_v1.blend','sha256':hashlib.sha256((DELIVERY/'tipo_typography_intro_v1.blend').read_bytes()).hexdigest()}
(ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
