"""Interpretable per-body geometry features.

Bore detection method (cross-section slicing):
  1. Candidate axes = the world X/Y/Z axes plus the body's three principal axes
     (area-weighted PCA of the surface), de-duplicated.
  2. For each axis, cut the mesh with up to `max_slices_per_axis` parallel planes.
  3. In each cross-section, every *interior ring* (a hole in a filled region) is a
     candidate. A ring counts as a circle when a least-squares circle fit has small
     max radial deviation and the ring's area is close to pi*R^2 (this rejects
     hexagonal/square holes whose vertices also sit on a circle).
  4. Circles on consecutive slices whose centres stay on the same line (small
     perpendicular drift) are chained into one bore. Length = slices * spacing.
  5. The diameter profile along a chain is split into constant-diameter plateaus.
     An abrupt jump between adjacent slices separating two plateaus = "stepped".
  6. Bores found on more than one candidate axis are de-duplicated.

Known limits (documented in README): bores whose axis is not within ~15 degrees of a
world or principal axis are missed; bores that break out of the surface (open
channels, U-slots) are not interior rings and are not reported; length resolution is
one slice spacing; non-watertight meshes may produce partial or no sections.
"""
from __future__ import annotations

import numpy as np
import trimesh
import shapely
from shapely.geometry import Polygon


# ---------------------------------------------------------------- helpers
def caliber_match(diameter_mm: float, cfg: dict) -> dict | None:
    bands = cfg["caliber_bands"]
    tol = float(bands["tolerance_mm"])
    best = None
    for nom in bands["nominal_mm"]:
        delta = abs(diameter_mm - float(nom))
        if delta <= tol and (best is None or delta < best["delta_mm"]):
            best = {"nominal_mm": float(nom), "delta_mm": round(delta, 3)}
    return best


def _fit_circle(xy: np.ndarray):
    x, y = xy[:, 0], xy[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    b = x * x + y * y
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    r2 = c + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = float(np.sqrt(r2))
    dev = float(np.max(np.abs(np.hypot(x - cx, y - cy) - r)) / r)
    return float(cx), float(cy), r, dev


def _candidate_axes(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    axes = [np.eye(3)[i] for i in range(3)]
    try:
        w = mesh.area_faces
        c = mesh.triangles_center
        mu = (c * w[:, None]).sum(0) / w.sum()
        X = (c - mu) * np.sqrt(w)[:, None]
        _, vecs = np.linalg.eigh(X.T @ X)
        axes += [vecs[:, i] for i in range(3)]
    except Exception:
        pass
    out: list[np.ndarray] = []
    for a in axes:
        a = a / np.linalg.norm(a)
        if all(abs(float(a @ b)) < 0.995 for b in out):
            out.append(a)
    return out


def _void_rings(segs: np.ndarray) -> list:
    """Closed loops in one cross-section that bound a VOID (cavity/hole).

    Loops are recovered with shapely.polygonize; a loop enclosed by an odd number of
    other loops is a void (material -> hole -> pin-in-hole -> ...)."""
    if len(segs) < 3:
        return []
    try:
        faces = shapely.get_parts(shapely.polygonize(shapely.linestrings(np.round(segs, 5))))
    except Exception:
        return []
    loops = [Polygon(f.exterior) for f in faces if f.area > 0]
    voids = []
    for k, lp in enumerate(loops):
        pt = lp.representative_point()
        depth = sum(1 for j, other in enumerate(loops) if j != k and other.area > lp.area
                    and other.contains(pt))
        if depth % 2 == 1:
            voids.append(lp.exterior)
    return voids


def _circles_along(mesh, axis, cfg):
    bd = cfg["bore_detection"]
    proj = mesh.vertices @ axis
    lo, hi = float(proj.min()), float(proj.max())
    span = hi - lo
    if span <= 0:
        return [], 0.0
    step = max(float(bd["min_step_mm"]), span / int(bd["max_slices_per_axis"]))
    n = int(np.floor(span / step))
    # offset off the half-step so planes never coincide with modelled step faces
    heights = lo + (np.arange(n) + 0.5) * step + 0.0137 * step
    heights = heights[heights < hi]
    if len(heights) == 0:
        return [], step
    try:
        lines, to3d, _ = trimesh.intersections.mesh_multiplane(
            mesh, plane_origin=np.zeros(3), plane_normal=axis, heights=heights
        )
    except Exception:
        return [], step
    circles = []
    for i, segs in enumerate(lines):
        for ring in _void_rings(segs):
            xy = np.asarray(ring.coords)[:-1]
            if len(xy) < 6:
                continue
            # resample uniformly by arc length so uneven vertex spacing (extra
            # collinear points from triangulation) cannot fake a circle fit
            dists = np.linspace(0, ring.length, 72, endpoint=False)
            even = shapely.get_coordinates(shapely.line_interpolate_point(ring, dists))
            fit = _fit_circle(even)
            if fit is None:
                continue
            cx, cy, r, dev = fit
            d = 2 * r
            if d < bd["min_diameter_mm"] or dev > bd["max_circle_deviation"]:
                continue
            if Polygon(xy).area / (np.pi * r * r) < bd["min_area_ratio"]:
                continue
            c3 = (to3d[i] @ np.array([cx, cy, 0.0, 1.0]))[:3]
            circles.append((i, c3, d))
    return circles, step


def _chain(circles, axis, gap=1):
    chains: list[list] = []
    for i, c3, d in sorted(circles, key=lambda t: t[0]):
        best, best_dist = None, None
        for ch in chains:
            li, lc, ld = ch[-1]
            if li >= i or i - li > gap + 1:
                continue
            v = c3 - lc
            perp = float(np.linalg.norm(v - (v @ axis) * axis))
            if perp <= max(0.5, 0.25 * min(ld, d)) and (best_dist is None or perp < best_dist):
                best, best_dist = ch, perp
        if best is None:
            chains.append([(i, c3, d)])
        else:
            best.append((i, c3, d))
    return chains


def _plateaus(diams: np.ndarray, step: float, cfg):
    bd = cfg["bore_detection"]
    thr = lambda a, b: max(bd["step_change_mm"], bd["step_change_rel"] * min(a, b))  # noqa: E731
    runs, start, jumps = [], 0, 0
    for k in range(1, len(diams)):
        if abs(diams[k] - diams[k - 1]) > thr(diams[k], diams[k - 1]):
            runs.append((start, k))
            start = k
            jumps += 1
    runs.append((start, len(diams)))
    min_len = max(bd["min_segment_mm"], 2 * step)
    plateaus = [
        {"diameter_mm": float(np.median(diams[a:b])), "length_mm": (b - a) * step}
        for a, b in runs
        if (b - a) * step >= min_len
    ]
    stepped = False
    for p in range(1, len(plateaus)):
        a, b = plateaus[p - 1]["diameter_mm"], plateaus[p]["diameter_mm"]
        if abs(a - b) > thr(a, b):
            stepped = True
    return plateaus, stepped, jumps


def find_bores(mesh: trimesh.Trimesh, cfg: dict) -> list[dict]:
    bd = cfg["bore_detection"]
    raw = []
    for axis in _candidate_axes(mesh):
        circles, step = _circles_along(mesh, axis, cfg)
        for ch in _chain(circles, axis):
            if len(ch) < bd["min_track_slices"]:
                continue
            idx = np.array([c[0] for c in ch])
            diams = np.array([c[2] for c in ch])
            centers = np.array([c[1] for c in ch])
            length = (idx[-1] - idx[0] + 1) * step
            plateaus, stepped, jumps = _plateaus(diams, step, cfg)
            primary = (
                max(plateaus, key=lambda p: p["length_mm"])["diameter_mm"]
                if plateaus
                else float(np.median(diams))
            )
            # caliber match: longest plateau (or the primary diameter) inside a band
            match = None
            for p in sorted(plateaus, key=lambda p: -p["length_mm"]) or [
                {"diameter_mm": primary, "length_mm": length}
            ]:
                m = caliber_match(p["diameter_mm"], cfg)
                if m:
                    match = {**m, "diameter_mm": round(p["diameter_mm"], 3),
                             "segment_length_mm": round(p["length_mm"], 2)}
                    break
            dmin, dmax = float(diams.min()), float(diams.max())
            raw.append({
                "axis": [round(float(v), 4) for v in axis],
                "center": [round(float(v), 3) for v in centers.mean(0)],
                "length_mm": round(float(length), 2),
                "diameter_mm": round(primary, 3),
                "min_diameter_mm": round(dmin, 3),
                "max_diameter_mm": round(dmax, 3),
                "ld_ratio": round(float(length / primary), 2),
                "stepped": bool(stepped),
                "tapered": bool(not stepped and dmax - dmin > max(bd["step_change_mm"],
                                                                 bd["step_change_rel"] * dmin)),
                "segments": [{"diameter_mm": round(p["diameter_mm"], 3),
                              "length_mm": round(p["length_mm"], 2)} for p in plateaus],
                "n_slices": int(len(ch)),
                "caliber_match": match,
                "_axis": axis,
                "_center": centers.mean(0),
            })
    # de-duplicate the same bore seen along nearly-parallel candidate axes
    kept: list[dict] = []
    for b in sorted(raw, key=lambda b: (-b["n_slices"], -b["length_mm"])):
        dup = False
        for k in kept:
            if abs(float(b["_axis"] @ k["_axis"])) < 0.98:
                continue
            v = b["_center"] - k["_center"]
            perp = float(np.linalg.norm(v - (v @ k["_axis"]) * k["_axis"]))
            if perp <= max(1.0, 0.25 * k["diameter_mm"]) and abs(
                b["diameter_mm"] - k["diameter_mm"]
            ) <= max(0.5, 0.1 * k["diameter_mm"]):
                dup = True
                break
        if not dup:
            kept.append(b)
    for b in kept:
        b.pop("_axis")
        b.pop("_center")
    return kept


def detect_rails(mesh) -> None:
    """TODO(phase-2): rail / mounting-interface detection is out of scope for Phase 1.
    Returns None so the feature report carries an explicit 'not evaluated' value."""
    return None


def body_features(mesh: trimesh.Trimesh, cfg: dict) -> dict:
    watertight = bool(mesh.is_watertight)
    try:
        bores = find_bores(mesh, cfg)
        bore_error = None
    except Exception as e:  # never crash a scan on a weird mesh
        bores, bore_error = [], f"{type(e).__name__}: {e}"
    ext = mesh.extents
    feats = {
        "watertight": watertight,
        "volume_mm3": round(float(abs(mesh.volume)), 2) if watertight else None,
        "bbox_mm": [round(float(v), 3) for v in ext],
        "face_count": int(len(mesh.faces)),
        "components": int(mesh.body_count),
        "bores": bores,
        "rails": detect_rails(mesh),
    }
    if bore_error:
        feats["bore_error"] = bore_error
    return feats
