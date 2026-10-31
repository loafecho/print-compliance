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

Known limits (documented in README): bores tilted more than ~15 degrees from every
world/principal axis read as inflated ellipses and are missed past ~20 degrees; bores that break out of the surface (open
channels, U-slots) are not interior rings and are not reported; length resolution is
one slice spacing; non-watertight meshes may produce partial or no sections.

Fail-closed rules: any slicing/polygonizing error, a cross-section whose loops touch,
cross or duplicate each other (overlapping shells make loop-nesting parity unreliable),
a body too large to slice at bore resolution, or work over the configured caps or the
wall-clock budget raises BoreAnalysisError. body_features records that as bore_error,
which scores REVIEW. None of these conditions can silently read as "no bore".
"""
from __future__ import annotations

import time

import numpy as np
import trimesh
import shapely
from shapely.geometry import Polygon


class BoreAnalysisError(Exception):
    """Bore detection could not be completed reliably; the body must go to REVIEW."""


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise BoreAnalysisError("timeout: bore analysis exceeded its time budget")


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


def _void_rings(segs: np.ndarray, max_loops: int = 0) -> list:
    """Closed loops in one cross-section that bound a VOID (cavity/hole).

    Loops are recovered with shapely.polygonize; a loop enclosed by an odd number of
    other loops is a void (material -> hole -> pin-in-hole -> ...). Parity is only
    sound when the loops are pairwise disjoint or strictly nested, which is what a
    clean watertight section gives. Coincident or overlapping shells break that, so
    duplicate segments or loops that touch/cross raise BoreAnalysisError instead."""
    if len(segs) < 3:
        return []
    r = np.round(np.asarray(segs, dtype=np.float64), 5)
    p0, p1 = r[:, 0, :], r[:, 1, :]
    swap = (p0[:, 0] > p1[:, 0]) | ((p0[:, 0] == p1[:, 0]) & (p0[:, 1] > p1[:, 1]))
    key = np.c_[np.where(swap[:, None], p1, p0), np.where(swap[:, None], p0, p1)]
    key = key[(p0 != p1).any(1)]  # a plane through a vertex yields harmless zero-length bits
    if len(np.unique(key, axis=0)) != len(key):
        raise BoreAnalysisError("ambiguous cross-section: coincident surfaces (duplicate edges)")
    faces = shapely.get_parts(shapely.polygonize(shapely.linestrings(r)))
    loops = [Polygon(f.exterior) for f in faces if f.area > 0]
    if max_loops and len(loops) > max_loops:
        raise BoreAnalysisError(f"cross-section has {len(loops)} loops (cap {max_loops})")
    if not loops:
        return []
    rings = [lp.exterior for lp in loops]
    tree = shapely.STRtree(rings)
    ii, jj = tree.query(rings, predicate="intersects")
    if np.any(ii != jj):
        raise BoreAnalysisError("ambiguous cross-section: loops touch or overlap")
    # nesting depth via spatial index (loops are now known to be disjoint or nested)
    # (only larger loops count: a filled loop's representative point may fall inside
    # a smaller hole loop nested within it)
    pts = [lp.representative_point() for lp in loops]
    area = np.array([lp.area for lp in loops])
    pi, li = shapely.STRtree(loops).query(pts, predicate="within")
    depth = np.zeros(len(loops), dtype=int)
    for k, j in zip(pi, li):
        if k != j and area[j] > area[k]:
            depth[k] += 1
    return [rings[k] for k in range(len(loops)) if depth[k] % 2 == 1]


def _circles_along(mesh, axis, cfg, deadline=None):
    bd = cfg["bore_detection"]
    proj = mesh.vertices @ axis
    lo, hi = float(proj.min()), float(proj.max())
    span = hi - lo
    if span <= 0:
        return [], 0.0
    step = max(float(bd["min_step_mm"]), span / int(bd["max_slices_per_axis"]))
    # the body's extent must not set the resolution so coarse that a bore spans too
    # few slices (a far-away decoy shell would otherwise dilute the step): cap the
    # step at a bore-scale value and refuse bodies too large to slice at that scale
    step = min(step, float(bd["max_step_mm"]))
    n = int(np.floor(span / step))
    if n > int(bd["max_total_slices"]):
        raise BoreAnalysisError(f"body spans {span:.0f} mm along an analysis axis; too large "
                                f"to slice at {step:g} mm bore resolution")
    # offset off the half-step so planes never coincide with modelled step faces
    heights = lo + (np.arange(n) + 0.5) * step + 0.0137 * step
    heights = heights[heights < hi]
    if len(heights) == 0:
        return [], step
    # no try/except: a slicing failure must reach bore_error (REVIEW), not read as "no bore"
    lines, to3d, _ = trimesh.intersections.mesh_multiplane(
        mesh, plane_origin=np.zeros(3), plane_normal=axis, heights=heights
    )
    max_loops = int(bd["max_loops_per_section"])
    max_circles = int(bd["max_circles_per_axis"])
    circles = []
    for i, segs in enumerate(lines):
        _check_deadline(deadline)
        for ring in _void_rings(segs, max_loops):
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
            if len(circles) > max_circles:
                raise BoreAnalysisError(f"more than {max_circles} circular sections on one axis")
    return circles, step


def _chain(circles, axis, gap=1, deadline=None):
    chains: list[list] = []
    for i, c3, d in sorted(circles, key=lambda t: t[0]):
        _check_deadline(deadline)
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


def _merge_chains(chains, axis, step, cfg, deadline=None):
    """Join collinear, same-diameter chains separated by a short gap. A cross-hole or
    side port breaks the void ring on a few slices; it is still one bore. Without this,
    cross-drilling a bore would split it and hide its true length."""
    bd = cfg["bore_detection"]
    chains = sorted(chains, key=lambda ch: ch[0][0])
    merged = True
    while merged:
        merged = False
        for a in range(len(chains)):
            _check_deadline(deadline)
            for b in range(len(chains)):
                A, B = chains[a], chains[b]
                if a == b or B[0][0] <= A[-1][0]:
                    continue
                (ai, ac, ad), (bi, bc, bdia) = A[-1], B[0]
                gap_mm = (bi - ai - 1) * step
                if gap_mm > bd["merge_gap_diameters"] * min(ad, bdia):
                    continue
                v = bc - ac
                perp = float(np.linalg.norm(v - (v @ axis) * axis))
                thr = max(bd["step_change_mm"], bd["step_change_rel"] * min(ad, bdia))
                if perp <= max(0.5, 0.25 * min(ad, bdia)) and abs(ad - bdia) <= thr:
                    chains[a] = A + B
                    chains.pop(b)
                    merged = True
                    break
            if merged:
                break
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


def find_bores(mesh: trimesh.Trimesh, cfg: dict, deadline: float | None = None) -> list[dict]:
    bd = cfg["bore_detection"]
    raw = []
    for axis in _candidate_axes(mesh):
        _check_deadline(deadline)
        circles, step = _circles_along(mesh, axis, cfg, deadline)
        for ch in _merge_chains(_chain(circles, axis, deadline=deadline), axis, step, cfg, deadline):
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
                "interruptions": int(np.sum(np.diff(idx) > 2)),
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


def body_features(mesh: trimesh.Trimesh, cfg: dict, deadline: float | None = None) -> dict:
    watertight = bool(mesh.is_watertight)
    try:
        bores = find_bores(mesh, cfg, deadline)
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
