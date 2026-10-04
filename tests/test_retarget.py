"""Ретаргет точек MediaPipe → SMPL: точки, построенные из известной позы, дают ту же позу."""
from __future__ import annotations
import math, random, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import retarget as rt, smpl                                           # noqa: E402
from core.rotations import axis_angle_to_matrix, mat_vec, matmul                # noqa: E402
from core.filters import OneEuro, median_filter                                 # noqa: E402

LIMB_JOINTS = (1, 2, 4, 5, 7, 8, 10, 11, 16, 17, 18, 19, 20, 21)


def rv(rng, a):
    v = [rng.gauss(0, 1) for _ in range(3)]
    n = math.sqrt(sum(c * c for c in v))
    return [c / n * rng.uniform(0, a) for c in v]


def landmarks_from_pose(go, body, tr, rest=smpl.DEFAULT_REST):
    """33 точки MediaPipe (в Y-up) из позы SMPL: суставы конечностей + уши и кисти по ориентации."""
    P = smpl.fk(go, body, tr, rest)
    rots = [go] + [body[3 * i:3 * i + 3] for i in range(21)]
    G = [None] * 22
    for i, p in enumerate(smpl.PARENTS):
        R = axis_angle_to_matrix(rots[i])
        G[i] = R if p < 0 else matmul(G[p], R)
    pts = [[0.0, 0.0, 0.0] for _ in range(33)]
    m = {rt.L_HIP: 1, rt.R_HIP: 2, rt.L_KNEE: 4, rt.R_KNEE: 5, rt.L_ANK: 7, rt.R_ANK: 8, rt.L_TOE: 10, rt.R_TOE: 11,
         rt.L_SH: 16, rt.R_SH: 17, rt.L_EL: 18, rt.R_EL: 19, rt.L_WR: 20, rt.R_WR: 21}
    for k, j in m.items():
        pts[k] = list(P[j])
    for ear, sx in ((rt.L_EAR, 0.07), (rt.R_EAR, -0.07)):
        o = mat_vec(G[15], (sx, 0.0, 0.0))
        pts[ear] = [P[15][i] + o[i] for i in range(3)]
    o = mat_vec(G[15], rt.NOSE_REST)
    pts[rt.NOSE] = [P[15][i] + o[i] for i in range(3)]
    for wr, j, a, b, sx in ((rt.L_WR, 20, rt.L_INDEX, rt.L_PINKY, 1), (rt.R_WR, 21, rt.R_INDEX, rt.R_PINKY, -1)):
        o = mat_vec(G[j], (0.09 * sx, 0.0, 0.0))
        side = mat_vec(G[j], (0.0, 0.0, 0.02))
        pts[a] = [P[j][i] + o[i] + side[i] for i in range(3)]
        pts[b] = [P[j][i] + o[i] - side[i] for i in range(3)]
    return pts, P, G


def globals_of(go, body):
    rots = [go] + [body[3 * i:3 * i + 3] for i in range(21)]
    G = [None] * 22
    for i, p in enumerate(smpl.PARENTS):
        R = axis_angle_to_matrix(rots[i])
        G[i] = R if p < 0 else matmul(G[p], R)
    return G


class Retarget(unittest.TestCase):
    def test_round_trip_positions(self):
        rng = random.Random(7)
        for _ in range(40):
            go = rv(rng, math.pi)
            body = [0.0] * 63
            for j in (1, 2, 4, 5, 7, 8, 16, 17, 18, 19, 20, 21, 15):
                body[3 * (j - 1):3 * j] = rv(rng, 1.4)
            # таз и грудь у SMPL с прямой спиной совпадают; голова: шея делит поворот пополам — даём только наклон головы
            pts, P, G = landmarks_from_pose(go, body, [0, 0, 0])
            g2, b2 = rt.pose_frame(pts)
            Q = smpl.fk(g2, b2, [0, 0, 0])
            for j in LIMB_JOINTS:
                err = max(abs(P[j][k] - Q[j][k]) for k in range(3))
                self.assertLess(err, 1e-6, f"сустав {smpl.NAMES[j]}: {err}")
            # ориентация головы восстанавливается точно (позицию сдвигает шея, берущая половину поворота)
            G2 = globals_of(g2, b2)
            self.assertLess(max(abs(G[15][r][c] - G2[15][r][c]) for r in range(3) for c in range(3)), 1e-6)

    def test_mediapipe_axes(self):
        # человек лицом к камере: нос ближе к камере (z<0 у MediaPipe) → у нас лицо к +Z
        self.assertGreater(rt.to_yup([0, 0, -0.1])[2], 0)
        self.assertGreater(rt.to_yup([0, -0.5, 0])[1], 0)   # MediaPipe Y вниз

    def test_full_pipeline_on_synthetic_clip(self):
        rng = random.Random(3)
        frames = []
        for f in range(20):
            body = [0.0] * 63
            body[3 * 15:3 * 16] = [0, 0, -1.2 + 0.3 * math.sin(f / 3)]  # LeftArm (16): машет
            pts, _, _ = landmarks_from_pose([0, 0.2, 0], body, [0, 0, 0])
            mp = [[p[0], -p[1], -p[2], 0.99] for p in pts]   # обратно в систему MediaPipe
            img = [[0.5 + p[0] * 0.3, 0.5 - p[1] * 0.3, 0.99] for p in pts]
            frames.append({"world": mp, "image": img} if f != 5 else None)  # кадр 5 — человек потерян
        res = rt.retarget({"fps": 30, "width": 1000, "height": 1000, "frames": frames}, smoothing=0.0)
        self.assertEqual(len(res["global_orient"]), 20)
        self.assertFalse(res["found"][5])
        low = min(min(smpl.fk(g, b, t)[j][1] for j in rt.FOOT_JOINTS)
                  for g, b, t in zip(res["global_orient"], res["body_pose"], res["transl"]))
        self.assertAlmostEqual(low, 0.0, places=4)  # стоит на полу (пол — по 10-му перцентилю)


class UpperBody(unittest.TestCase):
    def test_hidden_legs_are_kept_straight(self):
        frames = []
        for f in range(10):
            body = [0.0] * 63
            body[0:3] = [-0.8, 0, 0]  # «выдуманное» бедро
            pts, _, _ = landmarks_from_pose([0, 0, 0], body, [0, 0, 0])
            mp = [[p[0], -p[1], -p[2], 0.05 if i in rt.LEG_POINTS else 0.99] for i, p in enumerate(pts)]
            img = [[0.5 + p[0] * 0.3, 0.5 - p[1] * 0.3, 0.99] for p in pts]
            frames.append({"world": mp, "image": img})
        res = rt.retarget({"fps": 30, "width": 1000, "height": 1000, "frames": frames}, smoothing=0.0)
        self.assertTrue(res["upper_body"])
        for b in res["body_pose"]:
            for j in rt.LEG_JOINTS:
                self.assertEqual(b[3 * (j - 1):3 * j], [0.0, 0.0, 0.0])


class CameraFit(unittest.TestCase):
    def _clip(self, f_mm, n=12):
        rng = random.Random(11)
        W, H = 1920, 1080
        f = rt.focal_px(W, H, f_mm)
        inputs, truth = [], []
        for _ in range(n):
            body = [0.0] * 63
            for j in (1, 2, 4, 5, 16, 17, 18, 19):
                body[3 * (j - 1):3 * j] = rv(rng, 1.0)
            go = rv(rng, 0.8)
            rel = [smpl.fk(go, body, [-c for c in smpl.DEFAULT_REST[0]])[j] for j in rt.FIT_JOINTS]
            T = [rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.3), rng.uniform(-6, -2.5)]
            img = []
            for x, y, z in rel:
                d = -(z + T[2])
                img.append((W / 2 + f * (x + T[0]) / d, H / 2 - f * (y + T[1]) / d, 1.0))
            inputs.append((rel, img))
            truth.append(T)
        return inputs, truth, W, H

    def test_fit_root_recovers_position(self):
        inputs, truth, W, H = self._clip(50.0)
        f = rt.focal_px(W, H, 50.0)
        for (rel, img), T in zip(inputs, truth):
            got, err = rt.fit_root(rel, img, f, W / 2, H / 2)
            self.assertLess(max(abs(a - b) for a, b in zip(got, T)), 1e-6)
            self.assertLess(err, 1e-6)

    def test_estimate_focal(self):
        for f_mm in (24.0, 50.0, 135.0):
            inputs, _, W, H = self._clip(f_mm)
            self.assertEqual(rt.estimate_focal(inputs, W, H), f_mm)


class Filters(unittest.TestCase):
    def test_one_euro_reduces_jitter(self):
        rng = random.Random(1)
        noisy = [math.sin(i / 60) + rng.gauss(0, 0.05) for i in range(300)]
        f = OneEuro(30, min_cutoff=1.0, beta=0.3)
        out = [f([v])[0] for v in noisy]

        def jitter(x):  # энергия второй разности — дрожание кадр к кадру
            return sum((x[i + 1] - 2 * x[i] + x[i - 1]) ** 2 for i in range(1, len(x) - 1))
        self.assertLess(jitter(out), jitter(noisy) * 0.1)

    def test_one_euro_follows_fast_motion(self):
        # резкий шаг на 1 м: за 0,3 с фильтр должен пройти бо́льшую часть пути (не «плывёт»)
        f = OneEuro(30, min_cutoff=1.0, beta=0.3)
        out = [f([0.0 if i < 30 else 1.0])[0] for i in range(60)]
        self.assertGreater(out[39], 0.8)

    def test_median(self):
        self.assertEqual(median_filter([1, 1, 9, 1, 1], 1), [1, 1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()


class FootLock(unittest.TestCase):
    def test_sliding_foot_is_pinned(self):
        from core import cleanup
        # стоим на месте, а корень «уезжает» на 30 см/с — монокулярный дрейф; стопы должны остаться на месте
        n, fps = 60, 30.0
        params = {"global_orient": [[0, 0, 0]] * n, "body_pose": [[0.0] * 63] * n,
                  "transl": [[0.3 * t / fps, -smpl.DEFAULT_REST[0][1] - 0.0 + 1.29, 0.0] for t in range(n)]}
        # transl.y подобран так, чтобы носки были на полу (≈0)
        low = min(smpl.fk([0, 0, 0], [0.0] * 63, params["transl"][0])[j][1] for j in (10, 11))
        params["transl"] = [[t[0], t[1] - low, t[2]] for t in params["transl"]]
        out = cleanup.foot_lock(params, fps)
        first = smpl.fk([0, 0, 0], [0.0] * 63, out["transl"][0])[10]
        last = smpl.fk([0, 0, 0], [0.0] * 63, out["transl"][-1])[10]
        self.assertTrue(all(all(c) for c in out["contacts"]))
        self.assertLess(math.hypot(last[0] - first[0], last[2] - first[2]), 0.01)

    def test_lifted_out_of_floor(self):
        from core import cleanup
        n = 10
        params = {"global_orient": [[0, 0, 0]] * n, "body_pose": [[0.0] * 63] * n, "transl": [[0.0, 0.0, 0.0]] * n}
        out = cleanup.foot_lock(params, 30.0)  # без transl стопы глубоко под полом
        low = min(smpl.fk([0, 0, 0], [0.0] * 63, out["transl"][-1])[j][1] for j in (7, 8, 10, 11))
        self.assertGreater(low, -0.05)
