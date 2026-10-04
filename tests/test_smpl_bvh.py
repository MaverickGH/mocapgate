"""Тесты SMPL(-X) → BVH и адаптера GVHMR. Запуск: python3 -m unittest discover tests"""
from __future__ import annotations
import json, math, random, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import gvhmr, smpl, smpl_bvh                       # noqa: E402
from core.bvh import write                                    # noqa: E402
from core.rotations import (axis_angle_to_matrix, continuous_euler, euler_zxy_to_matrix,  # noqa: E402
                            mat_vec, matmul, matrix_to_euler_zxy)

FLIP = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))


def rand_rotvec(rng, max_angle=math.pi):
    v = [rng.gauss(0, 1) for _ in range(3)]
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    a = rng.uniform(0, max_angle)
    return [c / n * a for c in v]


def close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


def mclose(a, b, tol=1e-6):
    return all(close(r, s, tol) for r, s in zip(a, b))


def smpl_fk(params, rest, f, flip=False):
    """FK прямо по формулам SMPL — эталон, независимый от BVH."""
    pose = params["body_pose"][f]
    rv = [params["global_orient"][f]] + [pose[3 * i:3 * i + 3] for i in range(smpl.N_JOINTS - 1)]
    G, P = [None] * smpl.N_JOINTS, [None] * smpl.N_JOINTS
    for i, p in enumerate(smpl.PARENTS):
        R = axis_angle_to_matrix(rv[i])
        if p < 0:
            G[i] = R
            P[i] = tuple(rest[0][k] + params["transl"][f][k] for k in range(3))
        else:
            G[i] = matmul(G[p], R)
            off = mat_vec(G[p], [rest[i][k] - rest[p][k] for k in range(3)])
            P[i] = tuple(P[p][k] + off[k] for k in range(3))
    if flip:
        P = [mat_vec(FLIP, q) for q in P]
    return P


def parse_bvh(text):
    """Минимальный парсер BVH: имена, родители, оффсеты, каналы, кадры."""
    toks = text.split()
    names, parents, offsets, chans, stack, i = [], [], [], [], [], 0
    while toks[i] != "MOTION":
        t = toks[i]
        if t in ("ROOT", "JOINT"):
            names.append(toks[i + 1]); parents.append(stack[-1] if stack else -1)
            stack.append(len(names) - 1); i += 2
        elif t == "End":
            stack.append(None); i += 2
        elif t == "OFFSET":
            if stack[-1] is not None:
                offsets.append(tuple(float(x) for x in toks[i + 1:i + 4]))
            i += 4
        elif t == "CHANNELS":
            n = int(toks[i + 1]); chans.append(toks[i + 2:i + 2 + n]); i += 2 + n
        elif t == "}":
            stack.pop(); i += 1
        else:
            i += 1
    nframes = int(toks[i + 2]); i += 6  # MOTION Frames: N Frame Time: t
    width = sum(len(c) for c in chans)
    vals = [float(x) for x in toks[i:]]
    frames = [vals[k * width:(k + 1) * width] for k in range(nframes)]
    return names, parents, offsets, chans, frames


def bvh_fk(names, parents, offsets, chans, row):
    G, P, c = [None] * len(names), [None] * len(names), 0
    for j in range(len(names)):
        vals = dict(zip(chans[j], row[c:c + len(chans[j])])); c += len(chans[j])
        R = euler_zxy_to_matrix(vals["Zrotation"], vals["Xrotation"], vals["Yrotation"])
        if parents[j] < 0:
            G[j] = R
            P[j] = (vals["Xposition"], vals["Yposition"], vals["Zposition"])
        else:
            p = parents[j]
            G[j] = matmul(G[p], R)
            off = mat_vec(G[p], offsets[j])
            P[j] = tuple(P[p][k] + off[k] for k in range(3))
    return P


def synthetic(rng, n=12):
    return {
        "global_orient": [rand_rotvec(rng) for _ in range(n)],
        "body_pose": [sum((rand_rotvec(rng, 1.5) for _ in range(21)), []) for _ in range(n)],
        "transl": [[rng.uniform(-1, 1), rng.uniform(0, 1), rng.uniform(-1, 1)] for _ in range(n)],
        "betas": [[0.0] * 10 for _ in range(n)],
    }


class Rotations(unittest.TestCase):
    def test_euler_roundtrip(self):
        rng = random.Random(1)
        for _ in range(500):
            m = axis_angle_to_matrix(rand_rotvec(rng))
            self.assertTrue(mclose(euler_zxy_to_matrix(*matrix_to_euler_zxy(m)), m))

    def test_gimbal_lock(self):
        m = euler_zxy_to_matrix(30, 90, 0)
        self.assertTrue(mclose(euler_zxy_to_matrix(*matrix_to_euler_zxy(m)), m))

    def test_continuous_keeps_rotation_and_avoids_jumps(self):
        rng = random.Random(2)
        for _ in range(300):
            e = matrix_to_euler_zxy(axis_angle_to_matrix(rand_rotvec(rng)))
            prev = tuple(rng.uniform(-720, 720) for _ in range(3))
            c = continuous_euler(e, prev)
            self.assertTrue(mclose(euler_zxy_to_matrix(*c), euler_zxy_to_matrix(*e)))
            self.assertTrue(all(abs(c[k] - prev[k]) <= 180 + 1e-9 for k in (0, 2)))

    def test_no_wrap_jump_on_spin(self):
        # корень крутится вокруг Y на 720° — каналы не должны прыгать на 360°
        prev, last = None, None
        for f in range(200):
            e = continuous_euler(matrix_to_euler_zxy(axis_angle_to_matrix([0, math.radians(f * 3.6), 0])), prev)
            if prev:
                self.assertLess(max(abs(e[k] - prev[k]) for k in range(3)), 10)
            prev = last = e
        self.assertAlmostEqual(last[2], 199 * 3.6, places=6)


class SmplToBvh(unittest.TestCase):
    def check_fk(self, params, flip=False):
        skel, frames = smpl_bvh.convert(params)
        text = write(skel, frames, 1 / 30)
        names, parents, offsets, chans, rows = parse_bvh(text)
        # BVH идёт обходом в глубину — сверяем по именам, а не по индексам SMPL
        self.assertEqual(sorted(names), sorted(smpl.NAMES))
        for j, p in enumerate(parents):
            sp = smpl.PARENTS[smpl.NAMES.index(names[j])]
            self.assertEqual(names[p] if p >= 0 else None, smpl.NAMES[sp] if sp >= 0 else None)
        self.assertEqual(len(rows), len(params["transl"]))
        for f, row in enumerate(rows):
            want = [tuple(c * 100 for c in q) for q in smpl_fk(params, smpl.DEFAULT_REST, f, flip)]
            got = dict(zip(names, bvh_fk(names, parents, offsets, chans, row)))
            for j, name in enumerate(smpl.NAMES):
                # BVH пишет 4 знака; накопление по цепочке ~1e-3 см
                self.assertTrue(close(want[j], got[name], 5e-3), f"кадр {f} {name}: {want[j]} vs {got[name]}")

    def test_fk_matches_smpl(self):
        self.check_fk(synthetic(random.Random(3)))

    def test_incam_flip(self):
        params = synthetic(random.Random(4))
        params["cam_to_yup"] = True
        self.check_fk(params, flip=True)

    def test_rest_pose(self):
        p = {"global_orient": [[0, 0, 0]], "body_pose": [[0] * 63], "transl": [[0, 0, 0]]}
        skel, frames = smpl_bvh.convert(p)
        self.assertTrue(all(close(frames[0][n]["rot"], (0, 0, 0)) for n in smpl.NAMES))
        self.assertTrue(close(frames[0]["Hips"]["pos"], [c * 100 for c in smpl.DEFAULT_REST[0]]))

    def test_smpl_69_pose_accepted(self):
        p = {"global_orient": [[0, 0, 0]], "body_pose": [[0.1] * 69], "transl": [[0, 0, 0]]}
        self.assertEqual(len(smpl_bvh.convert(p)[1]), 1)

    def test_length_mismatch(self):
        p = {"global_orient": [[0, 0, 0]] * 2, "body_pose": [[0] * 63], "transl": [[0, 0, 0]]}
        with self.assertRaises(ValueError):
            smpl_bvh.convert(p)


class GvhmrAdapter(unittest.TestCase):
    def write_json(self, data):
        d = tempfile.mkdtemp()
        p = Path(d) / "res.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_nested_layout_and_batch_axis(self):
        params = synthetic(random.Random(5), n=4)
        batched = {k: [v] for k, v in params.items() if k != "betas"}  # (1, L, C)
        batched["betas"] = params["betas"]
        p = self.write_json({"smpl_params_global": batched, "smpl_params_incam": params})
        g = gvhmr.load(str(p), "global")
        self.assertEqual(len(g["transl"]), 4)
        self.assertFalse(g["cam_to_yup"])
        self.assertTrue(gvhmr.load(str(p), "incam")["cam_to_yup"])

    def test_missing_keys(self):
        p = self.write_json({"smpl_params_global": {"body_pose": [[0] * 63]}})
        with self.assertRaises(KeyError):
            gvhmr.load(str(p))

    def test_cli_end_to_end(self):
        params = synthetic(random.Random(6), n=8)
        p = self.write_json({"smpl_params_global": params})
        out = p.with_suffix(".bvh")
        r = subprocess.run([sys.executable, str(ROOT / "mocapgate.py"), str(p), "-o", str(out), "--fps", "25"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = out.read_text(encoding="utf-8")
        self.assertIn("Frames: 8", text)
        self.assertIn("Frame Time: 0.0400000", text)
        self.assertIn("JOINT LeftToeBase", text)


if __name__ == "__main__":
    unittest.main()
