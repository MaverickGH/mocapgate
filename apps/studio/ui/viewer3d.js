// MoCapGate Studio — 3D-просмотр BVH (three.js): скелет, суставы, пол; кадр задаёт плеер видео.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { BVHLoader } from "three/addons/loaders/BVHLoader.js";

const LEFT = /^Left/, RIGHT = /^Right/;
const FINGER = /^(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)\d+$/;
const baseName = name => (name || "").split(":").pop();
const isFinger = (bone) => FINGER.test(baseName(bone.name)) || /^(Jaw|LeftEye|RightEye)$/.test(baseName(bone.name)) || (bone.name === "ENDSITE" && (FINGER.test(baseName(bone.parent?.name)) || /^(Jaw|LeftEye|RightEye)$/.test(baseName(bone.parent?.name))));

export function createViewer(box) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(devicePixelRatio || 1);
  box.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x101113);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 200);
  camera.position.set(2.6, 1.6, 3.4);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.9, 0);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(3, 6, 4); scene.add(sun);
  const grid = new THREE.GridHelper(20, 20, 0x3a4a4e, 0x24282b); scene.add(grid);
  const axes = new THREE.AxesHelper(0.3); axes.position.y = 0.001; scene.add(axes);

  let rigs = [];
  let mode = "surface";
  let viewZoom = 1, lastDistance = null, lastFrame = 0;
  const jointGeo = new THREE.SphereGeometry(0.022, 12, 8);
  const boneGeo = new THREE.CylinderGeometry(0.014, 0.014, 1, 8); boneGeo.translate(0, 0.5, 0);
  const fingerJointGeo = new THREE.SphereGeometry(0.0045, 10, 6);
  const fingerBoneGeo = new THREE.CylinderGeometry(0.0033, 0.0033, 1, 8); fingerBoneGeo.translate(0, 0.5, 0);
  const mat = { c: new THREE.MeshStandardMaterial({ color: 0xd8dadd, roughness: .6 }),
    l: new THREE.MeshStandardMaterial({ color: 0xe27870, roughness: .6 }),
    r: new THREE.MeshStandardMaterial({ color: 0x5c9be2, roughness: .6 }),
    j: new THREE.MeshStandardMaterial({ color: 0xf0a35e, roughness: .4 }) };
  function clear() {
    for (const r of rigs) {
      r.mixer.stopAllAction(); r.mixer.uncacheRoot(r.bones[0]);
      scene.remove(r.group); r.trail.geometry.dispose(); r.trail.material.dispose(); r.material.dispose();
      if (r.surfaceMesh) { r.surfaceMesh.geometry.dispose(); r.surfaceMesh.material.dispose(); }
    }
    rigs = [];
    viewZoom = 1; lastDistance = null;
  }

  function load(text) {
    loadScene([{ text }]);
  }
  function loadScene(participants) {
    clear();
    for (const participant of participants) {
    const { text } = participant;
    const res = new BVHLoader().parse(text), clip = res.clip, bones = res.skeleton.bones;
    const group = new THREE.Group(); scene.add(group);
    const root = new THREE.Group(); root.scale.setScalar(0.01);  // BVH MoCapGate в сантиметрах
    root.add(bones[0]); group.add(root);
    const mixer = new THREE.AnimationMixer(bones[0]);
    const action = mixer.clipAction(clip); action.play();
    const m = /Frame Time:\s*([\d.]+)/.exec(text), frameTime = m ? Number(m[1]) : 1 / 30;
    const fm = /Frames:\s*(\d+)/.exec(text), frames = fm ? Number(fm[1]) : 0;
    const material = new THREE.MeshStandardMaterial({ color: participant.color || 0xf0a35e, roughness: .4 });
    const joints = [], links = [];
    for (const b of bones) {
      const finger = isFinger(b);
      const j = new THREE.Mesh(finger ? fingerJointGeo : jointGeo, material); group.add(j); joints.push(j);
      if (b.parent && b.parent.isBone) {
        const side = participants.length > 1 ? material : LEFT.test(baseName(b.name)) ? mat.l : RIGHT.test(baseName(b.name)) ? mat.r : mat.c;
        const l = new THREE.Mesh(finger ? fingerBoneGeo : boneGeo, side); l.userData = { a: b.parent, b }; group.add(l); links.push(l);
      }
    }
    // след таза — видно траекторию и проскальзывание
    const pts = [];
    const trail = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: participant.color || 0x5cc3cf, transparent: true, opacity: .5 }));
    group.add(trail);
    const rig = { root, group, bones, clip, mixer, action, frameTime, joints, links, trail, material,
      start: participant.start_frame ?? 0, end: participant.end_frame ?? frames-1 };
    if (participant.surface) {
      const data = participant.surface;
      const bytes = data.dtype === "int16" ? 2 : 4;
      if (data.format !== "mocapgate.mesh/1" || !Number.isInteger(data.vertex_count) || data.vertex_count < 1 ||
          data.vertex_count > 100000 || data.binary.byteLength !== data.frames * data.vertex_count * 3 * bytes) throw Error("Invalid SMPL-X surface");
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(data.vertex_count * 3), 3));
      geometry.setIndex(data.faces.flat());
      const surfaceMaterial = new THREE.MeshStandardMaterial({ color: participant.color || 0x83a4b2, roughness: .78, side: THREE.DoubleSide });
      const mesh = new THREE.Mesh(geometry, surfaceMaterial); group.add(mesh);
      rig.surface = data; rig.surfaceMesh = mesh;
      rig.surfacePositions = data.dtype === "int16" ? new Int16Array(data.binary) : new Float32Array(data.binary);
      rig.jointMap = new Map(data.joint_names.map((name, i) => [baseName(name), i]));
    }
    rig.observed = participant.overlayData?.detected;
    rigs.push(rig);
    for (let f = rig.start; f <= rig.end; f += 2) {
      if (rig.observed && !rig.observed[f]) continue;
      pose(rig, f);
      pts.push(bones[0].getWorldPosition(new THREE.Vector3()).setY(0.002));
    }
    trail.geometry.setFromPoints(pts);
    pose(rig, rig.start);
    }
    setFrame(0);
  }

  function pose(r, f) {
    r.action.time = Math.min(r.clip.duration, Math.max(0, f * r.frameTime));
    r.mixer.update(0);
    r.root.updateMatrixWorld(true);
  }

  const A = new THREE.Vector3(), B = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);
  function setFrame(f) {
    lastFrame = f;
    const bounds = new THREE.Box3();
    for (const rig of rigs) {
    const { bones, joints, links } = rig;
    rig.group.visible = f >= rig.start && f <= rig.end && (!rig.observed || !!rig.observed[f]);
    if (!rig.group.visible) continue;
    pose(rig, f);
    const frame = rig.surface ? Math.max(0, Math.min(rig.surface.frames-1, Math.floor(f))) : null;
    const positionFor = (bone, target) => {
      const index = rig.jointMap?.get(baseName(bone.name));
      if (index !== undefined) target.fromArray(rig.surface.joints[frame][index]);
      else bone.getWorldPosition(target);
      return target;
    };
    bones.forEach((b, i) => positionFor(b, joints[i].position));
    for (const l of links) {
      positionFor(l.userData.a, A); positionFor(l.userData.b, B);
      const d = B.clone().sub(A), len = d.length();
      l.position.copy(A); l.scale.set(1, Math.max(len, 1e-4), 1);
      l.quaternion.setFromUnitVectors(UP, d.normalize());
    }
    for (const bone of bones) bounds.expandByPoint(positionFor(bone, new THREE.Vector3()));
    const showBones = !rig.surface || mode !== "surface";
    joints.forEach(j => j.visible = showBones); links.forEach(l => l.visible = showBones);
    if (rig.surfaceMesh) {
      const mesh = rig.surfaceMesh, data = rig.surface;
      mesh.visible = mode !== "bones";
      const transparent = mode === "both";
      if (mesh.material.transparent !== transparent) { mesh.material.transparent = transparent; mesh.material.needsUpdate = true; }
      mesh.material.opacity = transparent ? .3 : 1;
      mesh.material.depthWrite = !transparent;
      const positions = mesh.geometry.attributes.position.array;
      const offset = frame * positions.length;
      for (let i=0; i<positions.length; i++) positions[i] = rig.surfacePositions[offset+i] * data.scale;
      mesh.position.fromArray(data.origins[frame]);
      mesh.geometry.attributes.position.needsUpdate = true;
      mesh.geometry.computeVertexNormals(); mesh.geometry.computeBoundingBox(); mesh.geometry.computeBoundingSphere();
      bounds.union(mesh.geometry.boundingBox.clone().translate(mesh.position));
    }
    }
    if (bounds.isEmpty()) return;
    // Fit visible people at this frame; a long trajectory must not shrink them to dots.
    // Preserve orbit direction and the zoom factor changed by the user's wheel.
    const offset = camera.position.clone().sub(controls.target);
    if (lastDistance) viewZoom *= offset.length() / lastDistance;
    viewZoom = THREE.MathUtils.clamp(viewZoom, .15, 8);
    const sphere = bounds.getBoundingSphere(new THREE.Sphere());
    const halfFov = THREE.MathUtils.degToRad(camera.fov / 2);
    const limitingFov = Math.min(halfFov, Math.atan(Math.tan(halfFov) * camera.aspect));
    const distance = Math.max(.8, sphere.radius) * 1.12 / Math.sin(limitingFov) * viewZoom;
    controls.target.copy(sphere.center);
    camera.position.copy(sphere.center).add(offset.normalize().multiplyScalar(distance));
    camera.far = Math.max(200, distance + sphere.radius * 3);
    camera.updateProjectionMatrix();
    lastDistance = distance;
  }

  function resize() {
    const w = box.clientWidth, h = box.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    if (rigs.length) setFrame(lastFrame);
  }
  new ResizeObserver(resize).observe(box);
  resize();
  (function tick() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(tick); })();
  function setMode(value) { mode = ["surface", "bones", "both"].includes(value) ? value : "surface"; setFrame(lastFrame); }
  function getStructure() {
    const describe = b => ({ name: b.name, children: b.children.filter(c => c.isBone && c.name !== "ENDSITE").map(describe) });
    return rigs.map(r => describe(r.bones[0]));
  }
  return { load, loadScene, setFrame, setMode, getStructure, clear, resize };
}
