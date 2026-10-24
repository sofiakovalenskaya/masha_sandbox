"""Check the deliverables and the edit seam against the approved source."""
import json, hashlib, subprocess, math
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image
import animate as A

ROOT=A.ROOT;DELIVERY=ROOT.parent;WORK=Path('/workspace/tipo_typography_v2_work')
original=Path('/workspace/tipo_fullhd_work/render_frames/frame_0031.png')
last=WORK/'frames/frame_0239.png'
assert np.array_equal(np.asarray(Image.open(original)),np.asarray(Image.open(last)))
assert np.array_equal(np.asarray(Image.open(WORK/'frames/frame_0219.png')),np.asarray(Image.open(last)))
assert len(A.DATA['letters'])==30
assert [g['letter'] for g in A.DATA['letters'] if g['row']==2]==list('НАВНИМАТЕЛЬНОСТЬ')
sequence=[A.variant_at(f/30)+1 for f in range(69,101,4)]
assert sequence==[1,2,3,4,1,2,3,4]
assert A.variant_at(68/30)==3 and A.variant_at(69/30)==0
assert not any(A.visible(p) for _,p in A.all_poses(A.SEAM_START))
phrase=[g for g in A.DATA['letters'] if g['row']==2]
assert all(A.pose(g,1.2-1/30) is None for g in phrase)
assert all(A.pose(g,1.2) is not None for g in phrase)
assert len({g['group'] for g in phrase})==1
exits=Counter()
for g in A.DATA['letters']+[A.DATA['exclamation']]:
    for f in range(math.ceil(A.BURST[g['id']]['start']*30),240):
        p=A.pose(g,f/30)
        if not A.visible(p):
            x,y=p['center'];r=math.hypot(*p['size'])/2
            edge='left' if x+r<0 else 'right' if x-r>=1920 else 'top' if y+r<0 else 'bottom'
            exits[edge]+=1
            break
assert sum(exits.values())==31
assert exits['left']>0 and exits['right']>0 and exits['top']>0
for g in A.DATA['letters']:
    assert A.pose(g,A.START[g['group']]-.01) is None
    p=A.pose(g,A.START[g['group']]+.3)
    assert np.allclose(p['center'],g['center'])
for f in range(101,149,3):
    g=A.DATA['exclamation'];poses=[A.pose(g,ff/30) for ff in range(f,f+3)]
    # Check exact three-frame held blocks at the actual starting phase.
    start=101+3*((f-101)//3)
    poses=[A.pose(g,ff/30) for ff in range(start,start+3)]
    assert poses[0]==poses[1]==poses[2]

report={'native_resolution':[1920,1080],'fps':30,'background_rgb':A.DATA['background'],
        'individual_letters':30,'individual_exclamation':1,'o_cycle_sequence':sequence,
        'o_frames_per_variant':4,'exclamation_pose_hold_frames':3,
        'phrase_appears_together':True,'word_start_seconds':A.START,
        'side_launches':sum(b['direction']=='side' for b in A.BURST.values()),
        'up_launches':sum(b['direction']=='up' for b in A.BURST.values()),
        'actual_exit_edges':dict(exits),
        'source_png_final_seam_pixel_identical':True,'pre_seam_hold_pixel_identical':True,
        'approved_source_frame':31,'continue_from_source_frame':32,
        'original_assets':A.DATA['original_assets'],'videos':{}}
for filename,count in [('tipo_typography_intro_v2_1080p.mp4',240),('tipo_intro_and_paper_story_v2_1080p.mp4',959)]:
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
report['blender_project']={'filename':'tipo_typography_intro_v2.blend','sha256':hashlib.sha256((DELIVERY/'tipo_typography_intro_v2.blend').read_bytes()).hexdigest()}
(ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
