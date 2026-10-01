"""Layer 1 fallback: normalized geometry hash + exact-match blocklist.

Normalization: recenter on the area-weighted surface centroid, scale by RMS surface
radius, then describe the shape with quantities that do not depend on orientation:
  - PCA eigenvalue ratios of the area-weighted surface covariance
  - radial distribution of surface area (distance from centroid, 32 bins)
  - distribution of |coordinate| along the dominant principal axis (16 bins)
All values are quantized (rounded) and SHA-256 hashed. Because every term is
rotation-invariant, degenerate PCA axes (cylinders, cubes) cannot make the hash flip.

Invariant to: rename, translation, rotation, uniform scale, re-export (STL/3MF).
NOT invariant to: remeshing/re-tessellation, mirroring is NOT distinguished,
non-uniform scale, edits. Quantization boundaries can (rarely) flip a hash on
float32 round-trips. This is an exact-match layer, not a similarity search.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


def descriptor(mesh: trimesh.Trimesh) -> dict:
    w = mesh.area_faces.astype(np.float64)
    A = w.sum()
    c = mesh.triangles_center.astype(np.float64)
    mu = (c * w[:, None]).sum(0) / A
    X = c - mu
    r = np.linalg.norm(X, axis=1)
    scale = np.sqrt((w * r * r).sum() / A)
    Xn, rn, wn = X / scale, r / scale, w / A
    cov = (Xn * wn[:, None]).T @ Xn
    evals, evecs = np.linalg.eigh(cov)
    evals, evecs = evals[::-1], evecs[:, ::-1]
    ratios = evals / evals.sum()
    radial, _ = np.histogram(np.clip(rn, 0, 3.999), bins=32, range=(0, 4), weights=wn)
    axial = np.zeros(16)
    if ratios[0] - ratios[1] > 0.02:  # dominant axis well defined
        t = np.abs(Xn @ evecs[:, 0])
        axial, _ = np.histogram(np.clip(t, 0, 3.999), bins=16, range=(0, 4), weights=wn)
    q = lambda a: [round(float(v), 3) + 0.0 for v in a]  # noqa: E731  (+0.0 kills -0.0)
    return {"eig": q(ratios), "radial": q(radial), "axial": q(axial)}


def geohash(mesh: trimesh.Trimesh) -> str:
    blob = json.dumps(descriptor(mesh), sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


class Blocklist:
    """Text file, one hex geohash per line (first token); '#' starts a comment."""

    def __init__(self, hashes: set[str]):
        self._h = hashes

    @classmethod
    def load(cls, path: str | Path | None) -> "Blocklist":
        hashes: set[str] = set()
        if path and Path(path).is_file():
            for line in Path(path).read_text().splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    hashes.add(line.split()[0].lower())
        return cls(hashes)

    def __len__(self):
        return len(self._h)

    def contains(self, h: str) -> bool:
        return h.lower() in self._h
