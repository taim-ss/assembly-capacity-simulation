"""Encode the actual Visual05 window frames; never synthesize simulation frames."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    run = ROOT / 'results/native-3d/P3V2Visual05'
    frames = sorted((run / 'frames').glob('frame-*.png'))
    if len(frames) < 2:
        raise ValueError('Native recording needs multiple real frames')
    records = [dict(file=p.name, sha256=sha(p), saved_ns=p.stat().st_mtime_ns) for p in frames]
    times = [r['saved_ns'] for r in records]
    intervals = [(b-a)/1e9 for a,b in zip(times,times[1:])]
    if min(intervals) <= 0:
        raise ValueError('Non-increasing native frame save timestamps')
    average = (times[-1]-times[0])/1e9/(len(frames)-1)
    out = ROOT / 'results/visual-final'
    out.mkdir(parents=True, exist_ok=True)
    images = []
    scene_changes = []
    previous = None
    for frame in frames:
        with Image.open(frame) as opened:
            rgb = opened.convert('RGB')
            # Factory region only: exclude changing dashboard/clock from movement evidence.
            scene = np.asarray(rgb.crop((220, 500, 1550, 820)), dtype=np.int16)
            if previous is not None:
                scene_changes.append(int(np.count_nonzero(np.max(np.abs(scene-previous),axis=2)>20)))
            previous = scene
            rgb.thumbnail((1280, 1280))
            images.append(rgb.copy())
    durations = [max(10, round(x*1000/10)*10) for x in intervals]+[round(average*1000/10)*10]
    images[0].save(out/'sensor-line.gif',save_all=True,append_images=images[1:],
                   duration=durations,loop=0,optimize=False)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-framerate',str(1/average),
        '-i',str(run/'frames/frame-%04d.png'),'-frames:v',str(len(frames)),
        '-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-crf','20',
        '-pix_fmt','yuv420p','-movflags','+faststart',str(out/'sensor-line.mp4')],check=True,
        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    shutil.copy2(run/'inspection/frame-0001.png',out/'sensor-line.png')
    launch=json.loads((run/'runtime/launch.json').read_text())
    plan=json.loads((run/'visual-plan.json').read_text())
    if launch['alp_sha256'] != plan['copy_sha256']:
        raise ValueError('Native launched model identity differs from visual plan')
    log=run/'runtime/native-seed-1-scenario-0-finite.log'
    terminal=log.read_text().strip().splitlines()[-1]
    if launch['status']!='complete' or not terminal.startswith('P3_DONE,1,0,80,80,'):
        raise ValueError('Native full cohort did not complete')
    acceptance=dict(label='SYNTHETIC actual native AnyLogic window recording',
        source_sha256=plan['source_sha256'],copy_sha256=plan['copy_sha256'],
        native_terminal=terminal,native_log_sha256=sha(log),frames=len(frames),
        unique_frames=len({r['sha256'] for r in records}),
        recording_seconds=(times[-1]-times[0])/1e9+average,
        timing='Reconstructed from original NTFS frame-save modification timestamps; GIF uses individual intervals; MP4 uses their mean. Not exact capture-start timing.',
        scope='Final approximately32 seconds of the actual run, ending at Finished80/80; not a recording of the whole campaign.',
        capture_limit='160 frames requested; native window closed after152 saved frames, so the capture-loop final timing manifest was not written. Original saved frame timestamps/hashes retained here.',
        maximum_changed_factory_pixels_between_frames=max(scene_changes),
        visually_reviewed='Dashboard separated from factory; labelled equipment, product positions and shipping change across authentic frames; terminal frame shows80 completed and zero WIP. Flowchart is outside runtime scene.',
        scenario='Baseline, seed1,80orders, caps[2,5,5,3,1], empirical inputs, rework0.10, ample components; playback3model hours/second.',
        frame_manifest=records,
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.iterdir() if p.suffix in {'.png','.gif','.mp4'}})
    (out/'acceptance.json').write_text(json.dumps(acceptance,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in acceptance.items() if k not in {'frame_manifest','artifacts'}},indent=2))


if __name__=='__main__':
    main()
