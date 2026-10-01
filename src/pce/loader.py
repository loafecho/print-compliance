"""Load STL / 3MF files into one trimesh mesh per body."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import trimesh

SUPPORTED = {".stl", ".3mf"}


class LoadError(Exception):
    pass


@dataclass
class Body:
    name: str
    mesh: trimesh.Trimesh
    source: str


def load_bodies(path: str | Path) -> list[Body]:
    p = Path(path)
    if not p.is_file():
        raise LoadError(f"not a file: {p}")
    if p.suffix.lower() not in SUPPORTED:
        raise LoadError(f"unsupported file type {p.suffix!r} (want .stl or .3mf)")
    try:
        loaded = trimesh.load(str(p), file_type=p.suffix.lower().lstrip("."))
    except Exception as e:  # trimesh raises many types on corrupt input
        raise LoadError(f"could not parse {p.name}: {type(e).__name__}: {e}") from e

    bodies: list[Body] = []
    if isinstance(loaded, trimesh.Scene):
        for node in loaded.graph.nodes_geometry:
            transform, gname = loaded.graph[node]
            geom = loaded.geometry.get(gname)
            if not isinstance(geom, trimesh.Trimesh):
                continue
            m = geom.copy()
            m.apply_transform(transform)
            bodies.append(Body(name=str(node), mesh=m, source=str(p)))
    elif isinstance(loaded, trimesh.Trimesh):
        bodies.append(Body(name=p.stem, mesh=loaded, source=str(p)))
    bodies = [b for b in bodies if len(b.mesh.faces) > 0]
    if not bodies:
        raise LoadError(f"no mesh geometry found in {p.name}")
    return bodies
