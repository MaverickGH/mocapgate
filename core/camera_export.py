"""MoCapGate — camera export (matchmove): the static video camera in the same world as the exported BVH.

Stdlib only (Studio's bundled Python has no numpy); the Blender script reads the JSON it produces.

Camera dict (host side, produced by core/gemx_runner.build_scene or camera_from_gvhmr):
    rotation  3×3 camera → world, OpenCV camera axes (x right, y down, z forward)
    position  [x, y, z] camera centre in metres, in the world of the people's root positions (Y up)
    K         3×3 intrinsics in pixels; width / height_px — image size in pixels

Portable file (camera_json → "mocapgate.camera/1"):
    position         [x, y, z] metres, Y up. BVH root positions are centimetres: BVH = position × 100.
    rotation_quat    [w, x, y, z] camera → world, camera looking along its −Z with +Y up
                     (Blender / Maya / three.js / glTF convention). From OpenCV: R_gl = R_cv · diag(1, −1, −1).
    fov_vertical_deg, fov_horizontal_deg
    focal_mm         35 mm equivalent: f_mm = f_px / width_px × sensor_width_mm, sensor_width_mm = 36
                     (horizontal sensor fit)
    principal_point  [cx, cy] pixels (Blender shift is derived from it)
    width, height (pixels), fps, frames, static: true

The camera is assumed static (one pose averaged over the take), like core/scene_align.py.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

from core.rotations import axis_angle_to_matrix, mat_vec, matmul, matrix_to_quat, transpose

FORMAT = "mocapgate.camera/1"
SENSOR_WIDTH_MM = 36.0
CV_TO_GL = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))  # OpenCV camera axes → GL camera axes


def _median(values: list) -> float:
    values = sorted(values)
    return values[len(values) // 2] if values else 0.0


def camera_from_gvhmr(params: dict, rest=None) -> dict | None:
    """Static camera for GVHMR results in the world of the BVH written by core/smpl_bvh.convert.

    params — one person's params from core.gvhmr.from_data/load_people: world (`global_orient`, `transl`) with
    `incam` (camera space, OpenCV) and `K`. As core/scene_align: R = mean(G_t·C_tᵀ) (camera → GVHMR world, Y up),
    offset = median(R·pelvis_cam − pelvis_world); the camera centre (0 in camera space) lands at −offset.
    For params already in camera space (`cam_to_yup`) the BVH world is the flipped camera frame: camera at 0.
    Returns None when the camera cannot be recovered (no K or no camera-space parameters).
    """
    from core import scene_align, smpl
    K = params.get("K")
    if not K:
        return None
    rest = rest or params.get("rest_joints") or smpl.DEFAULT_REST
    pelvis = [float(c) for c in rest[0]]
    if params.get("cam_to_yup"):
        R, position = CV_TO_GL, [0.0, 0.0, 0.0]
    else:
        inc = params.get("incam")
        if not inc or not inc.get("global_orient") or not params.get("global_orient"):
            return None
        n = min(len(inc["global_orient"]), len(params["global_orient"]), len(inc["transl"]), len(params["transl"]))
        if not n:
            return None
        G = [axis_angle_to_matrix(params["global_orient"][i]) for i in range(n)]
        C = [axis_angle_to_matrix(inc["global_orient"][i]) for i in range(n)]
        R = scene_align.camera_to_world(G, C)
        cam = [[pelvis[k] + float(inc["transl"][i][k]) for k in range(3)] for i in range(n)]
        world = [[pelvis[k] + float(params["transl"][i][k]) for k in range(3)] for i in range(n)]
        offset = scene_align.anchor_offset(R, cam, world)
        position = [-c for c in offset]
    video = params.get("video") or {}
    width = int(video.get("width") or round(K[0][2] * 2))
    height = int(video.get("height") or round(K[1][2] * 2))
    return {"rotation": [list(r) for r in R], "position": position, "K": [list(r) for r in K],
            "width": width, "height_px": height, "height": position[1]}


def gl_rotation(rotation) -> tuple:
    """Camera → world rotation with GL camera axes (looking along −Z, Y up) from OpenCV axes."""
    return matmul(rotation, CV_TO_GL)


def camera_json(camera: dict, fps: float, frames: int) -> dict:
    """Portable camera description (see module docstring); camera — dict with rotation, position, K, width, height_px."""
    K, width = camera["K"], int(camera["width"])
    height = int(camera.get("height_px") or round(K[1][2] * 2))
    fx, fy = float(K[0][0]), float(K[1][1])
    w, x, y, z = matrix_to_quat(gl_rotation(camera["rotation"]))
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    position = [float(c) for c in camera["position"]]
    return {"format": FORMAT, "position": [round(c, 6) for c in position],
            "position_bvh_cm": [round(c * 100.0, 4) for c in position],
            "rotation_quat": [round(c, 8) for c in (w, x, y, z)],
            "up": "Y", "units": "m",
            "fov_vertical_deg": round(math.degrees(2.0 * math.atan(height / (2.0 * fy))), 6),
            "fov_horizontal_deg": round(math.degrees(2.0 * math.atan(width / (2.0 * fx))), 6),
            "focal_mm": round(fx / width * SENSOR_WIDTH_MM, 6), "sensor_width_mm": SENSOR_WIDTH_MM,
            "principal_point": [float(K[0][2]), float(K[1][2])],
            "width": width, "height": height, "fps": float(fps), "frames": int(frames), "static": True}


def save(path, camera: dict, fps: float, frames: int) -> dict:
    data = camera_json(camera, fps, frames)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def project_gl(data: dict, point) -> list:
    """Project a world point (metres, Y up) through a camera_json description → pixels (x right, y down)."""
    from core.rotations import quat_to_matrix
    R = quat_to_matrix(data["rotation_quat"])
    local = mat_vec(transpose(R), [p - c for p, c in zip(point, data["position"])])
    if local[2] >= 0:
        raise ValueError("point is behind the camera")
    f_px = data["focal_mm"] / data["sensor_width_mm"] * data["width"]
    cx, cy = data.get("principal_point") or (data["width"] / 2.0, data["height"] / 2.0)
    return [cx + f_px * local[0] / -local[2], cy - f_px * local[1] / -local[2]]


FOOT_JOINTS = (7, 8, 10, 11)  # smpl.NAMES: LeftFoot, RightFoot, LeftToeBase, RightToeBase


def _present_frames(person: dict, n: int) -> list:
    """Frames where the person is tracked: inside [start_frame, end_frame] (person or params) and params['found']."""
    params = person.get("params") or {}
    start = person.get("start_frame", params.get("start_frame", 0))
    end = person.get("end_frame", params.get("end_frame", n - 1))
    start, end = max(0, int(start if start is not None else 0)), min(n - 1, int(end if end is not None else n - 1))
    found = params.get("found")
    return [i for i in range(start, end + 1) if found is None or i >= len(found) or found[i]]


def _yaw_part(M) -> tuple:
    """Closest rotation about +Y to M (both GVHMR worlds are gravity-aligned, so the true map is a yaw)."""
    yaw = math.atan2(M[0][2] - M[2][0], M[0][0] + M[2][2])
    return axis_angle_to_matrix([0.0, yaw, 0.0]), yaw


def _camera_solve(params: dict, rest, frames: list):
    """R (camera → person world) and offset o with pelvis_world + o ≈ R·pelvis_cam, over the given frames."""
    from core import scene_align
    if params.get("cam_to_yup") or not params.get("K"):
        return None
    inc = params.get("incam")
    if not inc or not inc.get("global_orient") or not inc.get("transl") or not params.get("global_orient"):
        return None
    n = min(len(inc["global_orient"]), len(params["global_orient"]), len(inc["transl"]), len(params["transl"]))
    frames = [i for i in frames if i < n]
    if not frames:
        return None
    pelvis = [float(c) for c in rest[0]]
    G = [axis_angle_to_matrix(params["global_orient"][i]) for i in frames]
    C = [axis_angle_to_matrix(inc["global_orient"][i]) for i in frames]
    R = scene_align.camera_to_world(G, C)
    cam = [[pelvis[k] + float(inc["transl"][i][k]) for k in range(3)] for i in frames]
    world = [[pelvis[k] + float(params["transl"][i][k]) for k in range(3)] for i in frames]
    return R, scene_align.anchor_offset(R, cam, world), cam, world


def align_people(people: list, rest_by_person: dict | None = None) -> tuple[list, dict]:
    """Put every GVHMR participant into ONE shared world: the world of the reference person, floor at Y = 0.

    people — as core.gvhmr.load_people / pipeline.run_gvhmr_file: [{"id", "params", "start_frame"?, "end_frame"?}];
    params: world `global_orient`/`transl` (Y up, each GVHMR track starts at its own origin and heading), `incam`
    (OpenCV camera space) and `K`. rest_by_person — {id: 22 rest joints}; default params['rest_joints'] or
    smpl.DEFAULT_REST. Only frames where the person is present (start/end_frame, params['found']) are used to solve.

    Conventions (smpl.fk): pelvis_world = rest[0] + transl (root rotation does not move the pelvis), so
    transl = pelvis − rest[0]. Per person R_p = mean(G·Cᵀ) (camera → person world). Reference = first person with
    camera data. Map person world → reference world: M_p = yaw part of R_ref·R_pᵀ, d_p = median(R_ref·pelvis_cam −
    M_p·pelvis_world) − o_ref; then global_orient' = M_p·G, pelvis' = M_p·pelvis + d_p (exact data: d_p = M_p·o_p − o_ref).
    Floor: 10th percentile of min foot height over present frames of all aligned people → everyone Y −= floor.

    Returns (new_people, info); inputs are not mutated. info: reference (id | None), aligned (ids moved into the
    reference world, reference excluded), skipped (ids without camera data — returned unchanged, not floor-shifted),
    yaw {id: radians of M_p}, floor_shift (metres added to Y), camera (camera_from_gvhmr of the shifted reference,
    for camera_json/save) or None.
    """
    import copy
    from core import scene_align, smpl
    from core.rotations import matrix_to_axis_angle
    out = copy.deepcopy(people)
    rest_by_person = rest_by_person or {}
    info = {"reference": None, "aligned": [], "skipped": [], "yaw": {}, "floor_shift": 0.0, "camera": None}

    def rest_of(person):
        return rest_by_person.get(person.get("id")) or person["params"].get("rest_joints") or smpl.DEFAULT_REST

    solves = {}
    for index, person in enumerate(out):
        params = person["params"]
        solve = _camera_solve(params, rest_of(person), _present_frames(person, len(params.get("transl") or [])))
        if solve is None:
            info["skipped"].append(person.get("id"))
        else:
            solves[index] = solve
    if not solves:
        return out, info
    ref = min(solves)
    R_ref, o_ref = solves[ref][0], solves[ref][1]
    info["reference"] = out[ref].get("id")
    info["yaw"][out[ref].get("id")] = 0.0
    for index, (R_p, _o, cam, world) in solves.items():
        if index == ref:
            continue
        person = out[index]
        params = person["params"]
        M, yaw = _yaw_part(matmul(R_ref, transpose(R_p)))
        diffs = [[a - b for a, b in zip(mat_vec(R_ref, c), mat_vec(M, w))] for c, w in zip(cam, world)]
        d = [_median([v[k] for v in diffs]) - o_ref[k] for k in range(3)]
        pelvis = [float(c) for c in rest_of(person)[0]]
        params["global_orient"] = [matrix_to_axis_angle(matmul(M, axis_angle_to_matrix(g)))
                                   for g in params["global_orient"]]
        new_transl = []
        for t in params["transl"]:
            p = mat_vec(M, [pelvis[k] + float(t[k]) for k in range(3)])
            new_transl.append([p[k] + d[k] - pelvis[k] for k in range(3)])
        params["transl"] = new_transl
        info["aligned"].append(person.get("id"))
        info["yaw"][person.get("id")] = yaw

    joints = []
    for index in solves:
        person, params = out[index], out[index]["params"]
        rest = rest_of(person)
        frames = _present_frames(person, len(params["transl"]))
        joints.append([smpl.fk(params["global_orient"][i], params["body_pose"][i], params["transl"][i], rest)
                       for i in frames if i < len(params["global_orient"]) and i < len(params["body_pose"])])
    shift = -scene_align.floor_height(joints, list(FOOT_JOINTS))
    for index in solves:
        params = out[index]["params"]
        params["transl"] = [[float(t[0]), float(t[1]) + shift, float(t[2])] for t in params["transl"]]
    info["floor_shift"] = shift
    ref_person = out[ref]
    ref_params = {**ref_person["params"], "start_frame": ref_person.get("start_frame"),
                  "end_frame": ref_person.get("end_frame")}
    solve = _camera_solve(ref_params, rest_of(ref_person), _present_frames({"params": ref_params},
                                                                           len(ref_params["transl"])))
    camera = camera_from_gvhmr(ref_person["params"], rest_of(ref_person))
    if camera and solve:  # same solve as above, restricted to the frames where the reference is present
        R, o = solve[0], solve[1]
        camera["rotation"], camera["position"] = [list(r) for r in R], [-c for c in o]
        camera["height"] = camera["position"][1]
    info["camera"] = camera
    return out, info
