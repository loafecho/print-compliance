"""Load STL / 3MF files into one trimesh mesh per body.

Anything the loader cannot account for fails closed: it raises LoadError, which the
scanner turns into a REVIEW verdict. That covers 3MF packages whose declared content
does not fully become scored bodies (unresolved components, dropped instances, a
second candidate root model, embedded sliced G-code), non-millimetre units that cannot
be converted, and inputs over the configured size / body / face limits.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import trimesh

SUPPORTED = {".stl", ".3mf"}

# 3MF core spec unit names -> millimetres
UNIT_MM = {
    "micron": 0.001,
    "millimeter": 1.0,
    "centimeter": 10.0,
    "inch": 25.4,
    "foot": 304.8,
    "meter": 1000.0,
}
_MODEL_REL = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"

# used when load_bodies is called without a config (library use)
DEFAULT_LIMITS = {
    "max_file_mb": 100,
    "max_uncompressed_mb": 512,
    "max_bodies": 256,
    "max_faces": 2_000_000,
}


class LoadError(Exception):
    pass


@dataclass
class Body:
    name: str
    mesh: trimesh.Trimesh
    source: str


@dataclass
class _Plan:
    """What a 3MF package declares, read before trimesh parses it."""
    scale: float
    expected_instances: int


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _inspect_3mf(data: bytes, name: str, limits: dict) -> _Plan:
    """Validate a 3MF package and count the instances a complete load must produce."""
    from lxml import etree
    from trimesh.exchange.common import XML_PARSER_OPTIONS

    if name.lower().endswith(".gcode.3mf"):
        raise LoadError(f"{name} is a sliced plate file (.gcode.3mf); embedded G-code is not screened")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        raise LoadError(f"could not open 3MF package {name}: {type(e).__name__}: {e}") from e

    names = [i.filename for i in infos]
    if len({n.lower() for n in names}) != len(names):
        raise LoadError(f"{name} has duplicate archive entries")
    total = sum(i.file_size for i in infos)
    if total > limits["max_uncompressed_mb"] * 1024 * 1024:
        raise LoadError(f"{name} expands to {total} bytes, over the "
                        f"{limits['max_uncompressed_mb']} MB limit")
    gcode = [n for n in names if n.lower().endswith((".gcode", ".bgcode", ".gco"))]
    if gcode:
        raise LoadError(f"{name} contains embedded G-code ({gcode[0]}); sliced toolpaths are not screened")

    # trimesh picks the first member whose name contains this; make that unambiguous
    roots = [n for n in names if "3d/3dmodel.model" in n.lower()]
    if len(roots) != 1:
        raise LoadError(f"{name} has {len(roots)} candidate root model parts (want exactly 1)")
    root = roots[0]
    rels = [n for n in names if n.lower() == "_rels/.rels"]
    if len(rels) != 1:
        raise LoadError(f"{name} has no package relationships (_rels/.rels)")
    try:
        rel_root = etree.fromstring(zf.read(rels[0]), etree.XMLParser(**XML_PARSER_OPTIONS))
        targets = [r.get("Target", "") for r in rel_root.iter()
                   if _local(r.tag) == "Relationship" and r.get("Type") == _MODEL_REL]
    except Exception as e:
        raise LoadError(f"could not read {name} relationships: {type(e).__name__}: {e}") from e
    if len(targets) != 1 or targets[0].lstrip("/").lower() != root.lower():
        raise LoadError(f"{name} start part {targets!r} does not match the root model {root!r}")

    # walk the root model: object ids, inline meshes, components, build items, units
    objects: dict[str, tuple[bool, list[tuple[str | None, str | None]]]] = {}
    build: list[str | None] = []
    unit = "millimeter"
    try:
        with zf.open(root) as fh:
            for event, el in etree.iterparse(fh, events=("start", "end"), **XML_PARSER_OPTIONS):
                tag = _local(el.tag)
                if event == "start":
                    if tag == "model":
                        unit = el.get("unit", "millimeter")
                elif tag == "object":
                    oid = el.get("id")
                    if oid is None or oid in objects:
                        raise LoadError(f"{name} has a missing or duplicate object id {oid!r}")
                    has_mesh = any(True for _ in el.iter("{*}mesh"))
                    comps = [(c.get("objectid"),
                              next((v for k, v in c.attrib.items() if k.endswith("path")), None))
                             for c in el.iter("{*}component")]
                    objects[oid] = (has_mesh, comps)
                    el.clear()
                elif tag == "item":
                    build.append(el.get("objectid"))
    except LoadError:
        raise
    except Exception as e:
        raise LoadError(f"could not read {name} root model: {type(e).__name__}: {e}") from e

    if unit not in UNIT_MM:
        raise LoadError(f"{name} declares unsupported unit {unit!r}")
    if not build:
        raise LoadError(f"{name} has no build items")

    cap = int(limits["max_bodies"])
    memo: dict[str, int] = {}

    def count(oid, stack: tuple) -> int:
        if oid in stack:
            raise LoadError(f"{name} has a component cycle at object {oid!r}")
        if oid in memo:
            return memo[oid]
        if oid not in objects:
            raise LoadError(f"{name} references undefined object {oid!r}")
        has_mesh, comps = objects[oid]
        if has_mesh and comps:
            raise LoadError(f"{name} object {oid!r} has both a mesh and components")
        if not has_mesh and not comps:
            raise LoadError(f"{name} object {oid!r} has no geometry")
        n = 0 if comps else 1
        for cid, path in comps:
            if path is not None:
                # trimesh resolves sub-model parts by exact member name only
                if path.strip("/") not in names:
                    raise LoadError(f"{name} component path {path!r} is not in the package")
                n += 1
            else:
                n += count(cid, stack + (oid,))
            if n > cap:
                raise LoadError(f"{name} declares more than {cap} bodies")
        memo[oid] = n
        return n

    total_instances = 0
    for oid in build:
        total_instances += count(oid, ())
        if total_instances > cap:
            raise LoadError(f"{name} declares more than {cap} bodies")
    return _Plan(scale=UNIT_MM[unit], expected_instances=total_instances)


def load_bodies(path: str | Path, data: bytes | None = None, limits: dict | None = None) -> list[Body]:
    """Parse `data` (the exact bytes that were hashed) or, if None, the file at `path`."""
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED:
        raise LoadError(f"unsupported file type {p.suffix!r} (want .stl or .3mf)")
    if data is None:
        if not p.is_file():
            raise LoadError(f"not a file: {p}")
        data = p.read_bytes()
    if len(data) > limits["max_file_mb"] * 1024 * 1024:
        raise LoadError(f"{p.name} is {len(data)} bytes, over the {limits['max_file_mb']} MB limit")
    ftype = p.suffix.lower().lstrip(".")
    plan = _inspect_3mf(data, p.name, limits) if ftype == "3mf" else None

    try:
        loaded = trimesh.load(io.BytesIO(data), file_type=ftype)
        bodies: list[Body] = []
        if isinstance(loaded, trimesh.Scene):
            referenced = set()
            for node in loaded.graph.nodes_geometry:
                transform, gname = loaded.graph[node]
                referenced.add(gname)
                geom = loaded.geometry.get(gname)
                if not isinstance(geom, trimesh.Trimesh):
                    raise LoadError(f"{p.name} instance {node!r} has no mesh geometry")
                m = geom.copy()
                m.apply_transform(transform)
                bodies.append(Body(name=str(node), mesh=m, source=str(p)))
            # geometry that was parsed but never instanced would be printed by a
            # slicer that resolves the file differently; never score a subset
            unused = [g for g, m in loaded.geometry.items()
                      if isinstance(m, trimesh.Trimesh) and len(m.faces) and g not in referenced]
            if unused:
                raise LoadError(f"{p.name} has parsed geometry that is never placed: {unused[0]!r}")
        elif isinstance(loaded, trimesh.Trimesh):
            bodies.append(Body(name=p.stem, mesh=loaded, source=str(p)))
    except LoadError:
        raise
    except Exception as e:  # trimesh raises many types on corrupt input
        raise LoadError(f"could not parse {p.name}: {type(e).__name__}: {e}") from e

    if plan is not None and len(bodies) != plan.expected_instances:
        raise LoadError(f"{p.name} declares {plan.expected_instances} bodies but "
                        f"{len(bodies)} were loaded")
    nonempty = [b for b in bodies if len(b.mesh.faces) > 0]
    if not nonempty:
        raise LoadError(f"no mesh geometry found in {p.name}")
    if plan is not None and len(nonempty) != len(bodies):
        raise LoadError(f"{p.name} has an empty body")
    bodies = nonempty
    if len(bodies) > limits["max_bodies"]:
        raise LoadError(f"{p.name} has {len(bodies)} bodies, over the limit of {limits['max_bodies']}")
    faces = sum(len(b.mesh.faces) for b in bodies)
    if faces > limits["max_faces"]:
        raise LoadError(f"{p.name} has {faces} faces, over the limit of {limits['max_faces']}")
    if plan is not None and plan.scale != 1.0:
        # thresholds are millimetres; measure what the slicer will print
        for b in bodies:
            b.mesh.apply_scale(plan.scale)
    return bodies
