"""Programmatic builders for innocent primitive parts (and the abstract control block).

Everything here is built from trimesh/shapely primitives. Nothing models a firearm part.
"""
from __future__ import annotations

import numpy as np
import trimesh
from shapely.geometry import Polygon, box


def regular_polygon(cx: float, cy: float, d: float, sections: int = 64) -> Polygon:
    t = np.linspace(0, 2 * np.pi, sections, endpoint=False)
    r = d / 2.0
    return Polygon(np.c_[cx + r * np.cos(t), cy + r * np.sin(t)])


def revolve_profile(points, sections: int = 64) -> trimesh.Trimesh:
    """Revolve a closed (r, z) profile around Z. Returns a watertight solid."""
    pts = [tuple(map(float, p)) for p in points]
    clean = [pts[0]]
    for p in pts[1:]:
        if np.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    if np.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) > 1e-9:
        clean.append(clean[0])
    m = trimesh.creation.revolve(np.array(clean), sections=sections)
    if m.volume < 0:
        m.invert()
    return m


def stepped_tube(segments, sections: int = 64) -> trimesh.Trimesh:
    """Stack of coaxial segments along +Z: each (length, r_inner, r_outer).

    r_inner == 0 makes that segment solid (a blind bottom / closed end).
    The bore is only open if the first/last segments have r_inner > 0.
    """
    z = 0.0
    outer, inner = [], []
    for length, r_in, r_out in segments:
        outer += [(r_out, z), (r_out, z + length)]
        inner += [(r_in, z), (r_in, z + length)]
        z += length
    prof = outer + list(reversed(inner))
    # profile: up the outside, across the top, down the inside, across the bottom
    if inner[0][0] == 0 and inner[-1][0] == 0 and all(p[0] == 0 for p in inner):
        prof = [(0.0, 0.0)] + outer + [(0.0, z)]
    return revolve_profile(prof, sections=sections)


def extrude(poly: Polygon, height: float) -> trimesh.Trimesh:
    return trimesh.creation.extrude_polygon(poly, height)


def plate_with_holes(w, h, t, centers, hole_d, hole_sections: int = 64) -> trimesh.Trimesh:
    poly = box(-w / 2, -h / 2, w / 2, h / 2)
    for cx, cy in centers:
        poly = poly.difference(regular_polygon(cx, cy, hole_d, hole_sections))
    return extrude(poly, t)


def cylinder_z(d, length, center=(0, 0, 0), sections: int = 64) -> trimesh.Trimesh:
    c = trimesh.creation.cylinder(radius=d / 2.0, height=length, sections=sections)
    c.apply_translation(center)
    return c


def drill(mesh, d, length, center, axis="z", sections: int = 64) -> trimesh.Trimesh:
    c = cylinder_z(d, length, sections=sections)
    if axis == "x":
        c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    elif axis == "y":
        c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    c.apply_translation(center)
    return mesh.difference(c)


def l_bracket(a, b, width, t, hole_d=None) -> trimesh.Trimesh:
    """L-profile (leg a along X, leg b along Z) extruded along Y, optional one hole per leg."""
    prof = Polygon([(0, 0), (a, 0), (a, t), (t, t), (t, b), (0, b)])
    m = extrude(prof, width)  # extruded along +Z of the profile plane
    # rotate so the profile lies in XZ and the extrusion runs along Y
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    if hole_d:
        cy = -width / 2.0
        m = drill(m, hole_d, 3 * t, (a * 0.65, cy, t / 2), axis="z")
        m = drill(m, hole_d, 3 * t, (t / 2, cy, b * 0.6), axis="x")
    return m


def control_abstract_bore_block() -> trimesh.Trimesh:
    """Synthetic SHOULD-FLAG control. Not a firearm part: a plain rectangular block
    with one long stepped through-hole (9.0 mm for most of its length, a wider
    counterbore at one end). It exists only to prove the scoring path can go red."""
    block = trimesh.creation.box((30.0, 30.0, 150.0))
    hole = stepped_tube([(130.0, 0.0, 4.5), (24.0, 0.0, 5.5)])  # solid revolved cutter
    hole.apply_translation([0, 0, -77.0])
    return block.difference(hole)
