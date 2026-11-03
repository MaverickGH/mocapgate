// Optional preview trackers. Recording keeps the original camera stream.
export class LiveDetails {
  constructor() { this.trackers = {}; this.loading = {}; this.errors = {}; }
  async load(kind, vision, files) {
    if (this.trackers[kind]) return;
    if (this.loading[kind]) return this.loading[kind];
    const Class = kind === 'face' ? vision.FaceLandmarker : vision.HandLandmarker;
    const make = delegate => Class.createFromOptions(files, {
      baseOptions: { delegate, modelAssetPath: `https://storage.googleapis.com/mediapipe-models/${kind}_landmarker/${kind}_landmarker/float16/1/${kind}_landmarker.task` },
      runningMode: 'VIDEO', ...(kind === 'face' ? { numFaces: 4, outputFaceBlendshapes: true } : { numHands: 8 })
    });
    this.loading[kind] = (async () => {
      try { this.trackers[kind] = await make('GPU').catch(() => make('CPU')); delete this.errors[kind]; }
      catch (e) { this.errors[kind] = e.message || String(e); throw e; }
      finally { delete this.loading[kind]; }
    })();
    return this.loading[kind];
  }
  detect(video, timestamp, enabled) {
    const result = {};
    for (const kind of ['hand', 'face']) {
      if (!enabled[kind] || !this.trackers[kind] || this.errors[kind]) continue;
      try { result[kind] = this.trackers[kind].detectForVideo(video, timestamp); }
      catch (e) { this.errors[kind] = e.message || String(e); }
    }
    return result;
  }
}
export function drawDetails(g, project, result) {
  g.strokeStyle = '#e8b67d'; g.fillStyle = '#e8b67d'; g.lineWidth = 1.5;
  for (const points of result.hand?.landmarks || []) {
    for (const start of [1, 5, 9, 13, 17]) {
      g.beginPath(); g.moveTo(...project(points[0]));
      for (let i = start; i < start + 4; i++) g.lineTo(...project(points[i]));
      g.stroke();
    }
    for (const p of points) { const [x,y] = project(p); g.fillRect(x-1.5,y-1.5,3,3); }
  }
  g.fillStyle = '#9de0cf';
  for (const points of result.face?.faceLandmarks || []) {
    for (const p of points) { const [x,y] = project(p); g.fillRect(x-.8,y-.8,1.6,1.6); }
  }
}
