"""Small, dependency-free calibrated-camera primitives for multi-view capture.

Coordinates use the OpenCV camera convention (x right, y down, z forward).
Each calibration maps world points into camera space as ``Xc = R @ Xw + t``.
Camera/world lengths use the explicitly declared calibration unit. This module
does not detect people or infer camera calibration; callers must supply both.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

Vector2 = tuple[float, float]
Vector3 = tuple[float, float, float]
Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


class CalibrationError(ValueError):
    """Camera calibration is incomplete, inconsistent, or unsupported."""


class TriangulationError(ValueError):
    """Observations do not support a reliable 3-D point."""


def _finite(values: Sequence[float]) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _matrix3(value: Sequence[Sequence[float]], label: str) -> Matrix3:
    if len(value) != 3 or any(len(row) != 3 for row in value):
        raise CalibrationError(f"{label} must be a 3x3 matrix")
    rows = tuple(tuple(float(x) for x in row) for row in value)
    if not _finite(tuple(x for row in rows for x in row)):
        raise CalibrationError(f"{label} contains a non-finite value")
    return rows  # type: ignore[return-value]


def _det3(m: Matrix3) -> float:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _transpose(m: Matrix3) -> Matrix3:
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _mv(m: Matrix3, v: Vector3) -> Vector3:
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _add(a: Vector3, b: Vector3) -> Vector3:
    return tuple(x + y for x, y in zip(a, b))  # type: ignore[return-value]


def _sub(a: Vector3, b: Vector3) -> Vector3:
    return tuple(x - y for x, y in zip(a, b))  # type: ignore[return-value]


def _scale(a: Vector3, s: float) -> Vector3:
    return tuple(x * s for x in a)  # type: ignore[return-value]


def _norm(a: Vector3) -> float:
    return math.sqrt(sum(x * x for x in a))


def _unit(a: Vector3) -> Vector3:
    n = _norm(a)
    if n <= 1e-15:
        raise TriangulationError("zero-length viewing ray")
    return _scale(a, 1.0 / n)


@dataclass(frozen=True)
class CameraCalibration:
    """A static, calibrated pinhole camera in an explicitly named world frame."""

    camera_id: str
    width: int
    height: int
    intrinsics: Matrix3
    rotation_world_to_camera: Matrix3
    translation_world_to_camera: Vector3
    distortion: tuple[float, ...] = ()  # Brown-Conrady: k1,k2,p1,p2[,k3,k4,k5,k6]
    unit: str = "m"
    world_frame: str = "world"
    stationary: bool = True
    reprojection_rms_px: float | None = None

    def __post_init__(self) -> None:
        if not self.camera_id.strip():
            raise CalibrationError("camera_id must be stable and non-empty")
        if self.width <= 0 or self.height <= 0:
            raise CalibrationError("image dimensions must be positive")
        if not self.stationary:
            raise CalibrationError("moving cameras require a known per-frame trajectory")
        if self.unit not in ("m", "cm", "mm"):
            raise CalibrationError("unit must be explicitly m, cm, or mm")
        k = _matrix3(self.intrinsics, "intrinsics")
        r = _matrix3(self.rotation_world_to_camera, "rotation_world_to_camera")
        object.__setattr__(self, "intrinsics", k)
        object.__setattr__(self, "rotation_world_to_camera", r)
        t = tuple(float(x) for x in self.translation_world_to_camera)
        if len(t) != 3 or not _finite(t):
            raise CalibrationError("translation_world_to_camera must contain 3 finite values")
        object.__setattr__(self, "translation_world_to_camera", t)
        if k[0][0] <= 0 or k[1][1] <= 0 or abs(k[2][2] - 1.0) > 1e-9:
            raise CalibrationError("intrinsics require positive focal lengths and K[2,2] = 1")
        if any(abs(k[2][i]) > 1e-9 for i in (0, 1)):
            raise CalibrationError("skewed/noncanonical intrinsics are unsupported")
        if abs(k[0][1]) > 1e-9 or abs(k[1][0]) > 1e-9:
            raise CalibrationError("non-zero camera skew is unsupported")
        if not self.world_frame.strip():
            raise CalibrationError("world_frame must be explicit and non-empty")
        rt = _transpose(r)
        err = max(abs(sum(r[i][j] * r[i][k2] for i in range(3)) - (1.0 if j == k2 else 0.0))
                    for j in range(3) for k2 in range(3))
        if err > 1e-4 or abs(_det3(r) - 1.0) > 1e-4:
            raise CalibrationError("camera rotation must be proper and orthonormal")
        del rt
        if len(self.distortion) not in (0, 4, 5, 8) or not _finite(self.distortion):
            raise CalibrationError("distortion must have 0, 4, 5, or 8 finite Brown-Conrady coefficients")
        if self.reprojection_rms_px is not None and (
            not math.isfinite(self.reprojection_rms_px) or self.reprojection_rms_px < 0
        ):
            raise CalibrationError("reprojection_rms_px must be finite and non-negative")

    def crop_resize(self, x: float, y: float, width: float, height: float,
                    output_width: int | None = None, output_height: int | None = None) -> "CameraCalibration":
        """Return calibration for a crop then resize, preserving pixel-center geometry."""
        if (not _finite((x, y, width, height)) or x < 0 or y < 0 or width <= 0 or height <= 0
                or x + width > self.width + 1e-6 or y + height > self.height + 1e-6):
            raise CalibrationError("crop must be positive and inside the calibrated image")
        ow = self.width if output_width is None else int(output_width)
        oh = self.height if output_height is None else int(output_height)
        if ow <= 0 or oh <= 0:
            raise CalibrationError("output dimensions must be positive")
        sx, sy = ow / width, oh / height
        k = self.intrinsics
        shifted = ((k[0][0], k[0][1], k[0][2] - x),
                   (k[1][0], k[1][1], k[1][2] - y),
                   k[2])
        scaled = ((sx * shifted[0][0], sx * shifted[0][1], (shifted[0][2] + 0.5) * sx - 0.5),
                  (sy * shifted[1][0], sy * shifted[1][1], (shifted[1][2] + 0.5) * sy - 0.5),
                  shifted[2])
        return CameraCalibration(self.camera_id, ow, oh, scaled, self.rotation_world_to_camera,
                                 self.translation_world_to_camera, self.distortion, self.unit,
                                 self.world_frame, self.stationary, self.reprojection_rms_px)

    def _distort(self, x: float, y: float) -> tuple[float, float]:
        d = self.distortion + (0.0,) * (8 - len(self.distortion))
        k1, k2, p1, p2, k3, k4, k5, k6 = d
        r2 = x * x + y * y
        r4, r6 = r2 * r2, r2 * r2 * r2
        denominator = 1 + k4 * r2 + k5 * r4 + k6 * r6
        if denominator <= 1e-12:
            raise CalibrationError("rational distortion is singular at this image point")
        radial = (1 + k1 * r2 + k2 * r4 + k3 * r6) / denominator
        return (x * radial + 2 * p1 * x * y + p2 * (r2 + 2 * x * x),
                y * radial + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y)

    def undistort_pixel(self, pixel: Vector2, iterations: int = 20) -> Vector2:
        """Map a distorted pixel to normalized camera coordinates by fixed-point inversion."""
        u, v = map(float, pixel)
        if not _finite((u, v)) or iterations < 1:
            raise CalibrationError("pixel must be finite and iterations positive")
        k = self.intrinsics
        xd, yd = (u - k[0][2]) / k[0][0], (v - k[1][2]) / k[1][1]
        x, y = xd, yd
        for _ in range(iterations):
            fx, fy = self._distort(x, y)
            dx, dy = xd - fx, yd - fy
            x, y = x + dx, y + dy
            if max(abs(dx), abs(dy)) < 1e-12:
                return x, y
        fx, fy = self._distort(x, y)
        if max(abs(fx - xd), abs(fy - yd)) > 1e-7:
            raise CalibrationError("distortion inversion did not converge")
        return x, y

    def project(self, point_world: Vector3) -> tuple[Vector2, float]:
        """Project a world point; return pixel coordinates and camera-space depth."""
        p = tuple(float(x) for x in point_world)
        if len(p) != 3 or not _finite(p):
            raise CalibrationError("world point must contain 3 finite values")
        xc = _add(_mv(self.rotation_world_to_camera, p), self.translation_world_to_camera)
        if xc[2] <= 1e-12:
            raise CalibrationError("point is behind the camera or on its focal plane")
        x, y = self._distort(xc[0] / xc[2], xc[1] / xc[2])
        k = self.intrinsics
        return (k[0][0] * x + k[0][1] * y + k[0][2],
                k[1][1] * y + k[1][2]), xc[2]

    def ray(self, pixel: Vector2) -> tuple[Vector3, Vector3]:
        """Return world-space ray origin and unit direction for a distorted pixel."""
        x, y = self.undistort_pixel(pixel)
        rt = _transpose(self.rotation_world_to_camera)
        center = _scale(_mv(rt, self.translation_world_to_camera), -1.0)
        direction = _unit(_mv(rt, (x, y, 1.0)))
        return center, direction


@dataclass(frozen=True)
class PointObservation:
    camera: CameraCalibration
    pixel: Vector2
    confidence: float = 1.0
    measurement_sigma_px: float = 1.0
    local_track_id: str = ""
    actor_id: str = ""
    timestamp_s: float | None = None
    joint_name: str = ""
    provenance: str = "observation"

    def __post_init__(self) -> None:
        if not _finite(self.pixel) or not 0 <= self.confidence <= 1 or not math.isfinite(self.confidence):
            raise ValueError("observation pixel/confidence must be finite and confidence in [0,1]")
        if self.measurement_sigma_px <= 0 or not math.isfinite(self.measurement_sigma_px):
            raise ValueError("measurement_sigma_px must be positive and finite")
        if self.timestamp_s is not None and not math.isfinite(self.timestamp_s):
            raise ValueError("timestamp_s must be finite")
        if self.provenance not in ("observation", "triangulation", "prediction", "interpolation"):
            raise ValueError("unknown observation provenance")


@dataclass(frozen=True)
class TriangulationPolicy:
    """Caller-supplied acceptance criteria; defaults are intentionally omitted."""

    huber_delta_px: float
    minimum_ray_angle_deg: float
    maximum_reprojection_error_px: float
    minimum_condition_ratio: float
    maximum_timestamp_spread_s: float

    def __post_init__(self) -> None:
        if (not _finite((self.huber_delta_px, self.minimum_ray_angle_deg,
                         self.maximum_reprojection_error_px, self.minimum_condition_ratio,
                         self.maximum_timestamp_spread_s))
                or self.huber_delta_px <= 0 or self.maximum_reprojection_error_px <= 0
                or not 0 < self.minimum_ray_angle_deg <= 180
                or not 0 < self.minimum_condition_ratio < 1 or self.maximum_timestamp_spread_s < 0):
            raise ValueError("invalid triangulation acceptance criteria")


@dataclass(frozen=True)
class TriangulationResult:
    point_world: Vector3
    reprojection_error_px: dict[str, float]
    maximum_ray_angle_deg: float
    condition_ratio: float
    used_camera_ids: tuple[str, ...]
    rejected_camera_ids: tuple[str, ...]
    provenance: str = "triangulation"
    pairwise_only: bool = False  # two cameras cannot independently validate their mutual agreement
    unit: str = "m"
    world_frame: str = "world"


def _solve3(a: list[list[float]], b: list[float]) -> Vector3:
    aug = [a[i][:] + [b[i]] for i in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(aug[row][col]))
        if abs(aug[pivot][col]) < 1e-14:
            raise TriangulationError("viewing rays are geometrically degenerate")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        divisor = aug[col][col]
        aug[col] = [x / divisor for x in aug[col]]
        for row in range(3):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [x - factor * y for x, y in zip(aug[row], aug[col])]
    return tuple(aug[i][3] for i in range(3))  # type: ignore[return-value]


def _eigenvalues_symmetric3(a: list[list[float]]) -> tuple[float, float, float]:
    """Jacobi eigenvalues for the small symmetric normal matrix."""
    m = [row[:] for row in a]
    for _ in range(32):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda ij: abs(m[ij[0]][ij[1]]))
        if abs(m[p][q]) < 1e-14:
            break
        tau = (m[q][q] - m[p][p]) / (2 * m[p][q])
        t = math.copysign(1.0, tau) / (abs(tau) + math.sqrt(1 + tau * tau)) if tau else 1.0
        c, s = 1 / math.sqrt(1 + t * t), t / math.sqrt(1 + t * t)
        app, aqq, apq = m[p][p], m[q][q], m[p][q]
        m[p][p], m[q][q], m[p][q] = app - t * apq, aqq + t * apq, 0.0
        m[q][p] = 0.0
        for r in range(3):
            if r in (p, q):
                continue
            arp, arq = m[r][p], m[r][q]
            m[r][p] = m[p][r] = c * arp - s * arq
            m[r][q] = m[q][r] = s * arp + c * arq
    return tuple(sorted((m[0][0], m[1][1], m[2][2])))


def _maximum_ray_angle(directions: Sequence[Vector3]) -> float:
    angles = []
    for i in range(len(directions)):
        for j in range(i + 1, len(directions)):
            cosine = max(-1.0, min(1.0, sum(a * b for a, b in zip(directions[i], directions[j]))))
            angles.append(math.degrees(math.acos(cosine)))
    return max(angles, default=0.0)


def _fit(observations: Sequence[PointObservation], huber_delta_px: float) -> tuple[Vector3, list[list[float]]]:
    rays = [(o, *o.camera.ray(o.pixel)) for o in observations]
    robust = [1.0] * len(rays)
    point: Vector3 = (0.0, 0.0, 0.0)
    normal = [[0.0] * 3 for _ in range(3)]
    for _ in range(8):
        normal = [[0.0] * 3 for _ in range(3)]
        rhs = [0.0] * 3
        for i, (obs, origin, direction) in enumerate(rays):
            # Closest point on a ray: (I - d dᵀ) (X - C) = 0.
            confidence = max(obs.confidence, 1e-6)
            calib_sigma = obs.camera.reprojection_rms_px or 0.0
            focal = math.sqrt(obs.camera.intrinsics[0][0] * obs.camera.intrinsics[1][1])
            angular_sigma = math.sqrt(obs.measurement_sigma_px ** 2 + calib_sigma ** 2) / focal
            weight = robust[i] * confidence / (angular_sigma ** 2)
            projector = [[(1.0 if r == c else 0.0) - direction[r] * direction[c]
                          for c in range(3)] for r in range(3)]
            pc = [sum(projector[r][c] * origin[c] for c in range(3)) for r in range(3)]
            for r in range(3):
                rhs[r] += weight * pc[r]
                for c in range(3):
                    normal[r][c] += weight * projector[r][c]
        point = _solve3(normal, rhs)
        errors = []
        for obs, _, _ in rays:
            projected, _depth = obs.camera.project(point)
            errors.append(math.dist(projected, obs.pixel))
        updated = [min(1.0, huber_delta_px / max(error, 1e-12)) for error in errors]
        if max(abs(a - b) for a, b in zip(updated, robust)) < 1e-5:
            break
        robust = updated
    return point, normal


def triangulate_point(observations: Sequence[PointObservation], policy: TriangulationPolicy) -> TriangulationResult:
    """Robust weighted ray triangulation with explicit geometric acceptance checks."""
    obs = list(observations)
    if len(obs) < 2:
        raise TriangulationError("at least two independent cameras are required")
    ids = [o.camera.camera_id for o in obs]
    if len(set(ids)) != len(ids):
        raise TriangulationError("observations must come from distinct cameras")
    actors = {o.actor_id.strip() for o in obs}
    local_ids = [o.local_track_id.strip() for o in obs]
    joints = {o.joint_name.strip() for o in obs}
    if len(actors) != 1 or not next(iter(actors)):
        raise TriangulationError("cross-camera actor identity must be explicitly assigned and consistent")
    if any(not track_id for track_id in local_ids):
        raise TriangulationError("each observation needs its camera-local track ID")
    if len(joints) != 1 or not next(iter(joints)):
        raise TriangulationError("observations must name the same semantic joint")
    units = {o.camera.unit for o in obs}
    frames = {o.camera.world_frame for o in obs}
    if len(units) != 1 or len(frames) != 1:
        raise TriangulationError("camera calibrations must share units and world frame")
    if any(o.confidence <= 0 for o in obs):
        raise TriangulationError("zero-confidence observations cannot constrain a point")
    if any(o.provenance != "observation" for o in obs):
        raise TriangulationError("only independent image observations may be triangulated")
    times = [o.timestamp_s for o in obs]
    if any(t is None for t in times):
        raise TriangulationError("every observation needs a session-clock timestamp")
    spread = max(times) - min(times)  # type: ignore[arg-type]
    if spread > policy.maximum_timestamp_spread_s:
        raise TriangulationError(f"observations are not synchronized (timestamp spread {spread:.6g} s)")

    # RANSAC over camera pairs prevents one bad view from dragging an otherwise
    # consistent solution. Pair agreement is deliberately reported as such when
    # only two views remain; it is not independent validation of either camera.
    candidates = []
    baseline_failures = 0
    for i in range(len(obs)):
        for j in range(i + 1, len(obs)):
            pair = [obs[i], obs[j]]
            try:
                point, normal = _fit(pair, policy.huber_delta_px)
                depths = [o.camera.project(point)[1] for o in pair]
                if any(z <= 0 for z in depths):
                    continue
                eig = _eigenvalues_symmetric3(normal)
                condition = max(0.0, eig[0]) / max(1e-30, eig[-1])
                if condition < policy.minimum_condition_ratio:
                    continue
                directions = [o.camera.ray(o.pixel)[1] for o in pair]
                angle = _maximum_ray_angle(directions)
                if angle < policy.minimum_ray_angle_deg:
                    baseline_failures += 1
                    continue
                errors = {o.camera.camera_id: math.dist(o.camera.project(point)[0], o.pixel) for o in obs}
                inliers = [o for o in obs if errors[o.camera.camera_id] <= policy.maximum_reprojection_error_px]
                if len(inliers) < 2:
                    continue
                score = (-len(inliers), sum(errors[o.camera.camera_id] ** 2 for o in inliers),
                         sum(min(errors[o.camera.camera_id], policy.maximum_reprojection_error_px) ** 2 for o in obs))
                candidates.append((score, inliers))
            except (CalibrationError, TriangulationError):
                continue
    if not candidates:
        if baseline_failures == len(obs) * (len(obs) - 1) // 2:
            raise TriangulationError("insufficient camera baseline for the requested minimum ray angle")
        raise TriangulationError("no camera pair provides synchronized, positive-depth, well-conditioned support")
    _, inliers = min(candidates, key=lambda candidate: candidate[0])
    rejected = [o.camera.camera_id for o in obs if o not in inliers]
    point, normal = _fit(inliers, policy.huber_delta_px)
    depths = [o.camera.project(point)[1] for o in inliers]
    if any(z <= 0 for z in depths):
        raise TriangulationError("triangulated point is behind at least one contributing camera")
    eig = _eigenvalues_symmetric3(normal)
    condition = max(0.0, eig[0]) / max(1e-30, eig[-1])
    if condition < policy.minimum_condition_ratio:
        raise TriangulationError(f"poorly conditioned ray geometry (normal-matrix eigenvalue ratio {condition:.3g})")
    directions = [o.camera.ray(o.pixel)[1] for o in inliers]
    max_angle = _maximum_ray_angle(directions)
    if max_angle < policy.minimum_ray_angle_deg:
        raise TriangulationError(f"insufficient camera baseline (ray angle {max_angle:.3g} deg)")
    errors = {o.camera.camera_id: math.dist(o.camera.project(point)[0], o.pixel) for o in inliers}
    if any(error > policy.maximum_reprojection_error_px for error in errors.values()):
        raise TriangulationError("robust reprojection residual exceeds the requested limit")
    return TriangulationResult(point, errors, max_angle, condition,
                               tuple(o.camera.camera_id for o in inliers), tuple(rejected),
                               pairwise_only=len(inliers) == 2,
                               unit=inliers[0].camera.unit,
                               world_frame=inliers[0].camera.world_frame)


@dataclass(frozen=True)
class ClockAlignment:
    """Affine mapping from a camera's local seconds into the session clock."""

    scale: float
    offset_s: float
    residual_rms_s: float
    event_count: int

    def __post_init__(self) -> None:
        if (not _finite((self.scale, self.offset_s, self.residual_rms_s)) or self.scale <= 0
                or self.residual_rms_s < 0 or self.event_count < 2):
            raise ValueError("clock alignment must be finite, forward-moving, and supported by at least two events")

    def to_session(self, local_time_s: float) -> float:
        return self.scale * local_time_s + self.offset_s


def fit_clock_alignment(reference_events_s: Sequence[float], local_events_s: Sequence[float]) -> ClockAlignment:
    """Fit local→reference time from explicitly corresponding events; no frame-number shortcut."""
    if len(reference_events_s) != len(local_events_s) or len(reference_events_s) < 2:
        raise ValueError("at least two paired synchronization events are required")
    if not _finite(reference_events_s) or not _finite(local_events_s):
        raise ValueError("synchronization event times must be finite")
    xbar = sum(local_events_s) / len(local_events_s)
    ybar = sum(reference_events_s) / len(reference_events_s)
    denominator = sum((x - xbar) ** 2 for x in local_events_s)
    if denominator <= 1e-15:
        raise ValueError("local synchronization events must span non-zero time")
    scale = sum((x - xbar) * (y - ybar) for x, y in zip(local_events_s, reference_events_s)) / denominator
    if scale <= 0:
        raise ValueError("camera clock alignment must preserve chronological order")
    offset = ybar - scale * xbar
    residuals = [scale * x + offset - y for x, y in zip(local_events_s, reference_events_s)]
    rms = math.sqrt(sum(e * e for e in residuals) / len(residuals))
    return ClockAlignment(scale, offset, rms, len(residuals))


def timestamp_bracket(timestamps_s: Sequence[float], target_s: float, max_gap_s: float) -> tuple[int, int, float] | None:
    """Find real-time interpolation neighbors; return None rather than bridging a large gap."""
    if max_gap_s <= 0 or not math.isfinite(max_gap_s) or not math.isfinite(target_s):
        raise ValueError("target time and positive max_gap_s are required")
    if not timestamps_s or not _finite(timestamps_s):
        raise ValueError("timestamps must be a non-empty finite sequence")
    if any(b <= a for a, b in zip(timestamps_s, timestamps_s[1:])):
        raise ValueError("timestamps must be strictly increasing")
    if target_s < timestamps_s[0] or target_s > timestamps_s[-1]:
        return None
    lo, hi = 0, len(timestamps_s) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if timestamps_s[mid] < target_s:
            lo = mid + 1
        else:
            hi = mid
    if timestamps_s[lo] == target_s:
        return lo, lo, 0.0
    left, right = lo - 1, lo
    gap = timestamps_s[right] - timestamps_s[left]
    if gap > max_gap_s:
        return None
    return left, right, (target_s - timestamps_s[left]) / gap
