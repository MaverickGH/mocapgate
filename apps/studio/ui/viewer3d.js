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
  // колесо прокручивает страницу; масштаб — Ctrl/⌘ + колесо, щипок или колесо после щелчка по виду
  let engaged = false;
  renderer.domElement.addEventListener("pointerdown", () => { engaged = true; });
  renderer.domElement.addEventListener("pointerleave", () => { engaged = false; });
  renderer.domElement.addEventListener("wheel", (e) => { controls.enableZoom = engaged || e.ctrlKey || e.metaKey; }, { capture: true });
  scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(3, 6, 4); scene.add(sun);
  const grid = new THREE.GridHelper(20, 20, 0x3a4a4e, 0x24282b); scene.add(grid);
  const axes = new THREE.AxesHelper(0.3); axes.position.y = 0.001; scene.add(axes);

  let rigs = [];
  let mode = "character", participantsCache = [];
  let follow = true, fitted = false, cameraView = "free";
  let viewZoom = 1, lastDistance = null, lastFrame = 0;
  // правка позы: слой поворотов (дельта к локальному повороту сустава), выбранный сустав, «луковая шелуха»
  let layer = null, picked = "", onPick = null, onion = 0;
  const ONION_STEP = 5, DQ = new THREE.Quaternion();  // слой отдаёт [w, x, y, z]
  const pickMat = new THREE.MeshStandardMaterial({ color: 0xffe36b, emissive: 0x6b5500, roughness: .4 });
  const jointGeo = new THREE.SphereGeometry(0.022, 12, 8);
  const boneGeo = new THREE.CylinderGeometry(0.014, 0.014, 1, 8); boneGeo.translate(0, 0.5, 0);
  const fingerJointGeo = new THREE.SphereGeometry(0.0045, 10, 6);
  const fingerBoneGeo = new THREE.CylinderGeometry(0.0033, 0.0033, 1, 8); fingerBoneGeo.translate(0, 0.5, 0);
  const mat = { c: new THREE.MeshStandardMaterial({ color: 0xd8dadd, roughness: .6 }),
    l: new THREE.MeshStandardMaterial({ color: 0xe27870, roughness: .6 }),
    r: new THREE.MeshStandardMaterial({ color: 0x5c9be2, roughness: .6 }),
    j: new THREE.MeshStandardMaterial({ color: 0xf0a35e, roughness: .4 }) };
  function clear(dropCache = true) {
    if (dropCache) participantsCache = [];
    for (const r of rigs) {
      r.mixer?.stopAllAction(); r.mixer?.uncacheRoot(r.bones[0]);
      scene.remove(r.group); r.trail.geometry.dispose(); r.trail.material.dispose(); r.material.dispose();
      if (r.surfaceMesh) { r.surfaceMesh.geometry.dispose(); r.surfaceMesh.material.dispose(); }
    }
    rigs = [];
    viewZoom = 1; lastDistance = null; fitted = false;
  }

  function load(text) {
    loadScene([{ text }]);
  }
  function loadScene(participants) {
    participantsCache = participants;
    clear(false);
    for (const participant of participants) {
    const { text } = participant;
    const character = mode !== "surface" ? participant.character : null;
    const res = character ? null : new BVHLoader().parse(text), clip = res?.clip;
    const bones = character ? character.geometry.bones.map(b => {
      const bone = new THREE.Bone(); bone.name = b.name; bone.position.fromArray(b.position);
      bone.quaternion.setFromRotationMatrix(new THREE.Matrix4().set(
        ...b.rotation[0],0,...b.rotation[1],0,...b.rotation[2],0,0,0,0,1));
      return bone;
    }) : res.skeleton.bones;
    if (character) character.geometry.bones.forEach((b,i) => { if (b.parent >= 0) bones[b.parent].add(bones[i]); });
    const group = new THREE.Group(); scene.add(group);
    const root = new THREE.Group(); root.scale.setScalar(0.01);  // BVH MoCapGate в сантиметрах
    root.add(bones[0]); group.add(root);
    const mixer = character ? null : new THREE.AnimationMixer(bones[0]);
    const action = mixer?.clipAction(clip); action?.play();
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
    const rig = { root, group, bones, clip, mixer, action, frameTime, joints, links, trail, material, character,
      start: participant.start_frame ?? 0, end: participant.end_frame ?? frames-1 };
    if (character) {
      const data = character.geometry, geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(data.vertices.length*3),3));
      geometry.setIndex(data.faces.flat());
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: participant.color || 0xb7c4cf, roughness: .65, side: THREE.DoubleSide }));
      group.add(mesh); rig.surfaceMesh = mesh;
      rig.skinMatrices = data.influences.map(() => new THREE.Matrix4());
      rig.inverseBind = data.inverse_bind.map(m => new THREE.Matrix4().fromArray(m));
    } else if (participant.surface) {
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
    if (r.character) {
      const data = r.character, offset = Math.max(0, Math.min(data.frames-1, Math.floor(f)))*data.stride;
      r.bones[0].position.fromArray(data.motion,offset);
      r.bones.forEach((bone,i) => bone.quaternion.fromArray(data.motion,offset+3+i*4).normalize());
    } else {
      r.action.time = Math.min(r.clip.duration, Math.max(0, f * r.frameTime));
      r.mixer.update(0);
      if (layer && rigs.length === 1) {  // несохранённые правки видны сразу (как R·D в core/pose_layer.py)
        for (const bone of r.bones) { const d = layer(bone.name, Math.round(f)); if (d) bone.quaternion.multiply(DQ.set(d[1], d[2], d[3], d[0])); }
      }
    }
    r.root.updateMatrixWorld(true);
  }
  // призрачные позы за ONION_STEP·k кадров до и после текущего
  function drawOnion(rig, f) {
    for (const g of rig.ghosts || []) rig.group.remove(g);
    rig.ghosts = [];
    if (!onion || rig.character || rig.surface) return;
    const pairs = rig.bones.filter((b) => b.parent && b.parent.isBone);
    for (let k = -onion; k <= onion; k++) {
      if (!k) continue;
      const g0 = f + k * ONION_STEP;
      if (g0 < rig.start || g0 > rig.end) continue;
      pose(rig, g0);
      const pts = [];
      for (const b of pairs) pts.push(b.parent.getWorldPosition(new THREE.Vector3()), b.getWorldPosition(new THREE.Vector3()));
      const line = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: k < 0 ? 0x5cc3cf : 0xf0a35e, transparent: true, opacity: 0.55 - 0.12 * Math.abs(k) }));
      rig.group.add(line); rig.ghosts.push(line);
    }
    pose(rig, f);
  }

  const A = new THREE.Vector3(), B = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);
  function setFrame(f) {
    lastFrame = f;
    const bounds = new THREE.Box3();
    for (const rig of rigs) {
    const { bones, joints, links } = rig;
    rig.group.visible = f >= rig.start && f <= rig.end && (!rig.observed || !!rig.observed[f]);
    if (!rig.group.visible) continue;
    drawOnion(rig, f);
    pose(rig, f);
    rig.joints.forEach((j, i) => { j.material = picked && rig.bones[i].name === picked && rigs.length === 1 ? pickMat : (j.userData.base || (j.userData.base = j.material)); });
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
    const showBones = !(rig.surface || rig.character) || mode === "bones" || mode === "both";
    joints.forEach(j => j.visible = showBones); links.forEach(l => l.visible = showBones);
    if (rig.surfaceMesh) {
      const mesh = rig.surfaceMesh, data = rig.surface;
      mesh.visible = mode !== "bones";
      const transparent = mode === "both";
      if (mesh.material.transparent !== transparent) { mesh.material.transparent = transparent; mesh.material.needsUpdate = true; }
      mesh.material.opacity = transparent ? .3 : 1;
      mesh.material.depthWrite = !transparent;
      const positions = mesh.geometry.attributes.position.array;
      if (rig.character) {
        const skin = rig.character.geometry;
        skin.influences.forEach((bone,i) => rig.skinMatrices[i].multiplyMatrices(bones[bone].matrixWorld,rig.inverseBind[i]));
        skin.vertices.forEach((v,i) => {
          let x=0,y=0,z=0;
          for (const [influence,weight] of skin.weights[i]) {
            const e=rig.skinMatrices[influence].elements;
            x += weight*(e[0]*v[0]+e[4]*v[1]+e[8]*v[2]+e[12]);
            y += weight*(e[1]*v[0]+e[5]*v[1]+e[9]*v[2]+e[13]);
            z += weight*(e[2]*v[0]+e[6]*v[1]+e[10]*v[2]+e[14]);
          }
          positions[i*3]=x; positions[i*3+1]=y; positions[i*3+2]=z;
        });
      } else {
        const offset = frame * positions.length;
        for (let i=0; i<positions.length; i++) positions[i] = rig.surfacePositions[offset+i] * data.scale;
        mesh.position.fromArray(data.origins[frame]);
      }
      mesh.geometry.attributes.position.needsUpdate = true;
      mesh.geometry.computeVertexNormals(); mesh.geometry.computeBoundingBox(); mesh.geometry.computeBoundingSphere();
      bounds.union(mesh.geometry.boundingBox.clone().translate(mesh.position));
    }
    }
    if (cameraView === "capture" || bounds.isEmpty() || (!follow && fitted)) return;  // камера съёмки неподвижна
    fitted = true;
    // Fit visible people at this frame; a long trajectory must not shrink them to dots.
    // Preserve orbit direction and the zoom factor changed by the user's wheel.
    const offset = camera.position.clone().sub(controls.target);
    const directions={front:[0,0,1],back:[0,0,-1],side:[1,0,0]};
    if (directions[cameraView]) offset.fromArray(directions[cameraView]).multiplyScalar(lastDistance || 4);
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
  function setMode(value) {
    const next = ["character", "surface", "bones", "both"].includes(value) ? value : "character";
    const rebuild = (mode === "surface") !== (next === "surface") && participantsCache.some(p => p.character);
    mode = next;
    const frame = lastFrame;
    if (rebuild) loadScene(participantsCache);
    setFrame(frame);
  }
  function getStructure() {
    const describe = b => ({ name: b.name, children: b.children.filter(c => c.isBone && c.name !== "ENDSITE").map(describe) });
    return rigs.map(r => describe(r.bones[0]));
  }
  let capture = null;  // mocapgate.camera/1 — камера съёмки (метры, Y вверх, взгляд по −Z)
  function setCaptureCamera(data) { capture = data || null; if (cameraView === "capture") setView(capture ? "capture" : "free"); }
  function setView(value) {
    cameraView=["free","front","back","side"].includes(value) || (value==="capture" && capture)?value:"free";
    controls.enabled=cameraView!=="capture";
    controls.enableRotate=cameraView==="free";fitted=false;
    if (cameraView==="capture") {
      camera.position.fromArray(capture.position);
      const [w,x,y,z]=capture.rotation_quat; camera.quaternion.set(x,y,z,w);
      camera.fov=capture.fov_vertical_deg; camera.near=0.05; camera.far=200; camera.updateProjectionMatrix();
    }
    setFrame(lastFrame);
  }
  function setFollow(value) { follow = !!value; if (follow) setFrame(lastFrame); }
  // щелчок по суставу (без перетаскивания) — выбор для правки позы
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(); let down = null;
  renderer.domElement.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!onPick || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4 || rigs.length !== 1) return;
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const rig = rigs[0], hit = ray.intersectObjects(rig.joints.filter((j) => j.visible), false)[0];
    const bone = hit && rig.bones[rig.joints.indexOf(hit.object)];
    if (bone && bone.name !== "ENDSITE") onPick(bone.name);
  });
  function setLayer(fn) { layer = fn; setFrame(lastFrame); }
  function setPicked(name) { picked = name || ""; setFrame(lastFrame); }
  function setPickHandler(fn) { onPick = fn; }
  function setOnion(n) { onion = Math.max(0, Math.min(4, n | 0)); setFrame(lastFrame); }
  function boneNames() { return rigs.length === 1 && !rigs[0].character ? rigs[0].bones.map((b) => b.name).filter((n) => n !== "ENDSITE") : []; }
  return { load, loadScene, setFrame, setMode, setFollow, setView, getStructure, clear, resize, setLayer, setPicked, setPickHandler, setOnion, boneNames, setCaptureCamera };
}
