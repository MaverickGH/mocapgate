"""Prepare and compare GVHMR / SAM-Body4D experiments without installing into Studio."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import bvh, cleanup, gvhmr, report, smpl, smpl_bvh
from core.rotations import axis_angle_to_matrix, euler_zxy_to_matrix
from core.sam_body4d_runner import UPSTREAM_COMMIT
from core.video_timing import probe


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def export_gvhmr(params, fps, destination):
    """Export both variants and measure root rotation error after BVH serialization."""
    if params.get('cam_to_yup'):
        raise ValueError('Dance export checks require world-space GVHMR parameters')
    if not math.isfinite(fps) or fps <= 0 or not params['transl']:
        raise ValueError('Need positive FPS and nonempty motion')
    rest = params.get('rest_joints', smpl.DEFAULT_REST)
    variants = {'raw': copy.deepcopy(params), 'foot-lock': cleanup.foot_lock(params, fps, rest)}
    results = {}
    for label, sequence in variants.items():
        skeleton, frames = smpl_bvh.convert(sequence)
        text = bvh.write(skeleton, frames, 1 / fps)
        bvh.save(destination / f'gvhmr-{label}.bvh', text)
        # ROOT channels are first; check the actual rounded file, not only in-memory angles.
        rows = text.split('Frame Time: ', 1)[1].splitlines()[1:]
        errors = []
        for orient, row in zip(params['global_orient'], rows):
            actual = euler_zxy_to_matrix(*map(float, row.split()[3:6]))
            expected = axis_angle_to_matrix(orient)
            errors.append(max(abs(actual[i][j] - expected[i][j]) for i in range(3) for j in range(3)))
        world = [smpl.fk(g, p, t, rest) for g, p, t in
                 zip(sequence['global_orient'], sequence['body_pose'], sequence['transl'])]
        min_height = min(P[j][1] for P in world for j in cleanup.TOES + cleanup.ANKLES)
        results[label] = {'frames': len(frames), 'root_rotation_matrix_max_error': max(errors),
                          'minimum_foot_height_m': min_height,
                          'root_vertical_range_m': max(t[1] for t in sequence['transl']) - min(t[1] for t in sequence['transl']),
                          'rotations_preserved': sequence['global_orient'] == params['global_orient'] and
                                                 sequence['body_pose'] == params['body_pose']}
    return results


def make_report(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    video = folder / 'input-30fps.mp4'
    if digest(video) != manifest['prepared_sha256']:
        raise ValueError('Prepared video differs from experiment manifest')
    gv_record = json.loads((folder / 'gvhmr-run.json').read_text())
    if gv_record['video_sha256'] != manifest['prepared_sha256']:
        raise ValueError('GVHMR was run on a different clip')
    people = gvhmr.load_people(str(folder / 'gvhmr/result.mocapgate.json'))
    if len(people) != 1:
        raise ValueError('First dance comparison requires one GVHMR participant')
    params = people[0]['params']
    fps = params.get('fps', 30)
    if abs(fps - 30) > .01 or len(params['transl']) != manifest['frames']:
        raise ValueError('GVHMR timeline differs from prepared clip')
    sam = json.loads((folder / 'sam-body4d/keypoints.json').read_text())
    if sam.get('format') != 'mocapgate.sam-body4d-experiment/1':
        raise ValueError('Unsupported SAM experiment format')
    if not sam.get('completed'):
        raise ValueError('SAM run is incomplete; inspect its worker error before comparing')
    if sam['video_sha256'] != manifest['prepared_sha256'] or sam['frames'] != manifest['frames'] or abs(sam['fps'] - fps) > .01:
        raise ValueError('SAM and GVHMR must use the exact same clip and FPS')
    if sam['width'] != manifest['width'] or sam['height'] != manifest['height']:
        raise ValueError('SAM image dimensions differ')
    if not sam['records']:
        raise ValueError('SAM did not export any tracked frames')
    ids = sorted({r['id'] for r in sam['records']})
    if len(ids) != 1:
        raise ValueError('First comparison requires one stable SAM participant ID')
    sam_frames = [None] * manifest['frames']
    for record in sam['records']:
        frame = record['frame']
        if not isinstance(frame, int) or not 0 <= frame < len(sam_frames) or sam_frames[frame] is not None:
            raise ValueError('Invalid or duplicate SAM frame index')
        points = record['pred_keypoints_2d']
        if len(points) < 21 or any(len(p) < 2 or not all(math.isfinite(v) for v in p[:2]) for p in points):
            raise ValueError('Invalid SAM image keypoints')
        sam_frames[frame] = points
    incam, K = params.get('incam'), params.get('K')
    if incam is None or K is None:
        raise ValueError('GVHMR comparison needs camera parameters and K_fullimg')
    if any(len(incam[k]) != manifest['frames'] for k in ('global_orient', 'body_pose', 'transl')):
        raise ValueError('GVHMR camera timeline differs from world timeline')
    overlay = [report.project_opencv(smpl.fk(g, p, t), K) for g, p, t in
               zip(incam['global_orient'], incam['body_pose'], incam['transl'])]
    metrics = export_gvhmr(params, fps, folder)
    metrics['sam'] = {'tracked_frames': sum(f is not None for f in sam_frames),
                      'missing_frames': [i for i, f in enumerate(sam_frames) if f is None],
                      'revision': sam['revision'], 'completion': sam['completion']}
    metrics['limitations'] = ['No motion ground truth: metrics do not establish a winner.',
                             'MHR and SMPL joints differ. Compare timing and visual fit, not raw cross-model joint error.',
                             'SAM camera trajectories are not GVHMR world trajectories.',
                             'GVHMR overlay uses neutral approximate bone lengths and first-frame intrinsics.',
                             'Upstream rendered SAM videos may have different playback FPS; this report uses the input timeline.']
    save_json(folder / 'metrics.json', metrics)
    data = json.dumps({'fps': fps, 'gv': overlay, 'sam': sam_frames}, allow_nan=False).replace('<', '\\u003c')
    html = HTML.replace('__DATA__', data)
    (folder / 'comparison.html').write_text(html, encoding='utf-8')
    print(folder / 'comparison.html')


HTML = '''<!doctype html><meta charset="utf-8"><title>MoCapGate — Dance comparison</title>
<style>body{background:#15171b;color:#eee;font:16px system-ui;max-width:1200px;margin:24px auto;padding:0 20px}canvas{width:100%;background:#000}button,label{margin-right:16px}small{color:#bbc}</style>
<h1>GVHMR / SAM-Body4D</h1><p>Общий клип и таймлайн. Голубой — GVHMR, оранжевый — SAM-Body4D.</p>
<p><button id="play">▶ / ❚❚</button><label><input type="checkbox" id="gv" checked>GVHMR</label><label><input type="checkbox" id="sam" checked>SAM-Body4D</label><span id="status"></span></p>
<video id="video" src="input-30fps.mp4" controls style="width:100%"></video><canvas id="canvas"></canvas>
<p><small>Проверяйте наклон таза, ритм, приседания, стопы и перекрытия. Суставы MHR и SMPL различаются; это визуальная проверка, а не измерение точности по эталону. Экспорт GVHMR: <a href="gvhmr-raw.bvh">исходный BVH</a> / <a href="gvhmr-foot-lock.bvh">с фиксацией стоп</a>. <a href="metrics.json">Диагностика</a>.</small></p>
<script>const data=__DATA__; const v=document.getElementById('video'), c=document.getElementById('canvas'), ctx=c.getContext('2d');
const gvEdges=[[-1,0],[0,1],[0,2],[0,3],[1,4],[2,5],[3,6],[4,7],[5,8],[6,9],[7,10],[8,11],[9,12],[9,13],[9,14],[12,15],[13,16],[14,17],[16,18],[17,19],[18,20],[19,21]].filter(e=>e[0]>=0);
const samEdges=[[5,6],[5,7],[7,62],[6,8],[8,41],[5,9],[6,10],[9,10],[9,11],[11,13],[13,15],[13,17],[10,12],[12,14],[14,18],[14,20]];
function draw(points,edges,color){if(!points)return;ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=3;for(const [a,b]of edges){const p=points[a],q=points[b];if(!p||!q||p[0]==null||q[0]==null)continue;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke()}for(const p of points){if(!p||p[0]==null)continue;ctx.beginPath();ctx.arc(p[0],p[1],3,0,Math.PI*2);ctx.fill()}}
function render(){if(v.readyState>=2){c.width=v.videoWidth;c.height=v.videoHeight;ctx.drawImage(v,0,0);const f=Math.min(data.gv.length-1,Math.max(0,Math.floor(v.currentTime*data.fps+1e-4)));if(document.getElementById('gv').checked)draw(data.gv[f],gvEdges,'#4bdcff');if(document.getElementById('sam').checked)draw(data.sam[f],samEdges,'#ffa94b');document.getElementById('status').textContent=`Кадр ${f} / ${data.gv.length-1}`+(data.sam[f]?'':' · SAM: нет данных')}requestAnimationFrame(render)}
document.getElementById('play').onclick=()=>v.paused?v.play():v.pause();render();</script>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('video', type=Path); p.add_argument('folder', type=Path)
    for name in ('gvhmr', 'sam'):
        p = sub.add_parser(name)
        p.add_argument('folder', type=Path); p.add_argument('--python', type=Path, required=True)
        p.add_argument('--repository', type=Path, required=True)
        if name == 'gvhmr':
            p.add_argument('--static', action='store_true', help='only for a stationary camera')
        else:
            p.add_argument('--completion', action='store_true'); p.add_argument('--batch-size', type=int, default=4)
    p = sub.add_parser('report'); p.add_argument('folder', type=Path)
    a = ap.parse_args()
    folder = a.folder.resolve()
    if a.command == 'prepare':
        from core.managed_tools import find_ffmpeg
        ffmpeg = find_ffmpeg() or shutil.which('ffmpeg')
        if not ffmpeg:
            raise RuntimeError('Install FFmpeg first')
        if folder.exists():
            raise FileExistsError('Choose a new experiment folder')
        source = a.video.resolve(strict=True)
        folder.mkdir(parents=True)
        video = folder / 'input-30fps.mp4'
        subprocess.run([str(ffmpeg), '-nostdin', '-n', '-i', str(source), '-an', '-vf', 'fps=30',
                        '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', str(video)], check=True)
        timing = probe(video)
        # Decode/count via ffprobe because container nb_frames may be unavailable.
        ffprobe = shutil.which('ffprobe') or str(Path(ffmpeg).with_name('ffprobe'))
        result = subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                                         '-show_entries', 'stream=nb_read_frames,width,height', '-of', 'json', str(video)], text=True)
        stream = json.loads(result)['streams'][0]
        count = int(stream['nb_read_frames'])
        if not 1 <= count <= 1800:
            raise ValueError('Use a clip of at most 60 seconds')
        save_json(folder / 'manifest.json', {'source_sha256': digest(source), 'prepared_sha256': digest(video),
                  'frames': count, 'fps': 30, 'width': stream['width'], 'height': stream['height'],
                  'timing': timing, 'sam_body4d_commit': UPSTREAM_COMMIT})
        print(folder / 'manifest.json')
    elif a.command == 'report':
        make_report(folder)
    else:
        manifest = json.loads((folder / 'manifest.json').read_text())
        video = folder / 'input-30fps.mp4'
        if digest(video) != manifest['prepared_sha256']:
            raise ValueError('Video checksum differs from manifest')
        py = a.python.resolve(strict=True)
        repo = a.repository.resolve(strict=True)
        if a.command == 'gvhmr':
            dest = folder / 'gvhmr'
            if dest.exists():
                raise FileExistsError('GVHMR output already exists; use a new experiment')
            dest.mkdir()
            subprocess.run([str(py), str(ROOT / 'core/gvhmr_runner.py'), str(repo), str(video), str(dest),
                            '--max-people', '1', '--fps', '30'] + (['--static'] if a.static else []), check=True)
            revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            save_json(folder / 'gvhmr-run.json', {'video_sha256': digest(video), 'revision': revision, 'static_camera': a.static})
        else:
            subprocess.run([str(py), str(ROOT / 'core/sam_body4d_runner.py'), str(repo), str(video), str(folder / 'sam-body4d'),
                            '--batch-size', str(a.batch_size)] + (['--completion'] if a.completion else []), check=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
