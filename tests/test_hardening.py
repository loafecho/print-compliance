"""Fail-closed regressions: inputs the scanner cannot fully account for must REVIEW, never PASS.

All meshes are innocent primitives built in-test; 3MF packages are written by hand."""
import hashlib
import io
import json
import time
import zipfile

import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon, box

import pce.cli
import pce.loader
from pce import shapes
from pce.cli import main, scan_file
from pce.features import body_features
from pce.geohash import Blocklist
from pce.loader import LoadError, load_bodies

parametrize = pytest.mark.parametrize  # alias keeps decorator lines free of '@word.word' patterns

NO_BLOCKLIST = Blocklist(set())

CT = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
      'package/2006/content-types"><Default Extension="rels" ContentType="application/'
      'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType='
      '"application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats'
        '.org/package/2006/relationships"><Relationship Target="{}" Id="rel0" Type="http://schemas'
        '.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
NS = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
      'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"')


def mesh_xml(m: trimesh.Trimesh) -> str:
    v = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in m.vertices)
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
    return f"<mesh><vertices>{v}</vertices><triangles>{t}</triangles></mesh>"


def model_xml(objects: str, items: str, unit: str = "millimeter") -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?><model unit="{unit}" {NS}>'
            f"<resources>{objects}</resources><build>{items}</build></model>")


def package(model: str, extra: dict | None = None, root: str = "3D/3dmodel.model",
            target: str = "/3D/3dmodel.model", first: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in (first or {}).items():
            z.writestr(n, d)
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS.format(target))
        z.writestr(root, model)
        for n, d in (extra or {}).items():
            z.writestr(n, d)
    return buf.getvalue()


def tube(length=100.0, z0=0.0):
    m = shapes.stepped_tube([(length, 4.5, 6.0)])
    m.apply_translation([0, 0, z0])
    return m


def cube(size=5.0):
    return trimesh.creation.box((size, size, size))


def scan_bytes(tmp_path, name, data, cfg):
    p = tmp_path / name
    p.write_bytes(data)
    return scan_file(p, cfg, NO_BLOCKLIST)


def obj(oid, m, name=None):
    return f'<object id="{oid}" type="model"{f" name={name!r}" if name else ""}>{mesh_xml(m)}</object>'


# ------------------------------------------------------------------ control
def test_handwritten_3mf_control_loads(tmp_path, cfg):
    data = package(model_xml(obj(1, cube()) + obj(2, tube()),
                             '<item objectid="1"/><item objectid="2"/>'))
    assert len(load_bodies("ok.3mf", data=data)) == 2
    # the long 9 mm tube in a well-formed package is still found
    assert scan_bytes(tmp_path, "ok.3mf", data, cfg)["verdict"] == "REVIEW"


def test_plain_cube_3mf_still_passes(tmp_path, cfg):
    data = package(model_xml(obj(1, cube()), '<item objectid="1"/>'))
    assert scan_bytes(tmp_path, "cube.3mf", data, cfg)["verdict"] == "PASS"


# ------------------------------------------------------- run-1: 3MF package
def test_gcode_3mf_is_review(tmp_path, cfg):
    data = package(model_xml(obj(1, cube()), '<item objectid="1"/>'),
                   extra={"Metadata/plate_1.gcode": "; placeholder\n"})
    rec = scan_bytes(tmp_path, "plate.3mf", data, cfg)
    assert rec["verdict"] == "REVIEW" and "G-code" in rec["reasons"][0]
    clean = package(model_xml(obj(1, cube()), '<item objectid="1"/>'))
    assert scan_bytes(tmp_path, "plate.gcode.3mf", clean, cfg)["verdict"] == "REVIEW"


def test_decoy_root_model_is_review(tmp_path, cfg):
    decoy = model_xml(obj(1, cube()), '<item objectid="1"/>')
    data = package(model_xml(obj(1, tube()), '<item objectid="1"/>'),
                   first={"decoy/3D/3dmodel.model": decoy})
    rec = scan_bytes(tmp_path, "decoy.3mf", data, cfg)
    assert rec["verdict"] == "REVIEW" and "candidate root model" in rec["reasons"][0]


def test_start_part_mismatch_is_review(tmp_path, cfg):
    data = package(model_xml(obj(1, cube()), '<item objectid="1"/>'), target="/3D/other.model")
    assert scan_bytes(tmp_path, "rels.3mf", data, cfg)["verdict"] == "REVIEW"


def test_inch_units_are_converted_to_mm(cfg):
    data = package(model_xml(obj(1, cube(1.0)), '<item objectid="1"/>', unit="inch"))
    (b,) = load_bodies("inch.3mf", data=data)
    assert b.mesh.extents == pytest.approx([25.4, 25.4, 25.4])
    bad = package(model_xml(obj(1, cube(1.0)), '<item objectid="1"/>', unit="cubit"))
    with pytest.raises(LoadError):
        load_bodies("bad.3mf", data=bad)


# --------------------------------------------- run-2: 3MF scene completeness
def test_unresolved_component_path_is_review(tmp_path, cfg):
    sub = f'<?xml version="1.0"?><model unit="millimeter" {NS}><resources>{obj(1, tube())}</resources><build/></model>'
    root = model_xml(obj(1, cube()) + '<object id="2" type="model"><components>'
                     '<component p:path="/3D/Objects/Barrel.model" objectid="1"/></components></object>',
                     '<item objectid="1"/><item objectid="2"/>')
    bad = package(root, extra={"3D/Objects/barrel.model": sub})  # case differs
    rec = scan_bytes(tmp_path, "case.3mf", bad, cfg)
    assert rec["verdict"] == "REVIEW" and "not in the package" in rec["reasons"][0]
    good = package(root, extra={"3D/Objects/Barrel.model": sub})
    assert len(load_bodies("ok.3mf", data=good)) == 2


def test_object_with_mesh_and_components_is_review(tmp_path, cfg):
    root = model_xml(f'<object id="2" type="model">{mesh_xml(cube())}</object>'
                     f'<object id="1" type="model">{mesh_xml(tube())}'
                     '<components><component objectid="2"/></components></object>',
                     '<item objectid="1"/>')
    rec = scan_bytes(tmp_path, "mixed.3mf", package(root), cfg)
    assert rec["verdict"] == "REVIEW"


def test_instancing_cutoff_cannot_drop_a_build_item(tmp_path, cfg):
    comps = lambda child: "".join(  # noqa: E731
        f'<component objectid="{child}" transform="1 0 0 0 1 0 0 0 1 {6 * k} 0 0"/>' for k in range(12))
    root = model_xml(obj("C", cube()) + f'<object id="B" type="model"><components>{comps("C")}</components></object>'
                     f'<object id="A" type="model"><components>{comps("B")}</components></object>'
                     + obj("X", tube()),
                     '<item objectid="A"/><item objectid="X" transform="1 0 0 0 1 0 0 0 1 0 200 0"/>')
    rec = scan_bytes(tmp_path, "deep.3mf", package(root), cfg)
    assert rec["verdict"] == "REVIEW"


def test_body_cap_is_review_without_parsing(tmp_path, cfg):
    items = '<item objectid="1"/>' * 300
    rec = scan_bytes(tmp_path, "many.3mf", package(model_xml(obj(1, cube()), items)), cfg)
    assert rec["verdict"] == "REVIEW" and "more than" in rec["reasons"][0]


def test_zip_expansion_cap_is_review(tmp_path, cfg):
    cfg["limits"]["max_uncompressed_mb"] = 1
    data = package(model_xml(obj(1, cube()), '<item objectid="1"/>'),
                   extra={"Metadata/pad.bin": b"\0" * (2 * 1024 * 1024)})
    rec = scan_bytes(tmp_path, "bomb.3mf", data, cfg)
    assert rec["verdict"] == "REVIEW" and "MB limit" in rec["reasons"][0]


def test_stl_solid_count_cap_is_review(tmp_path, cfg):
    cfg["limits"]["max_bodies"] = 3
    solids = "".join(trimesh.exchange.stl.export_stl_ascii(cube()).replace("solid ", f"solid s{i}", 1)
                     for i in range(5))
    rec = scan_bytes(tmp_path, "solids.stl", solids.encode(), cfg)
    assert rec["verdict"] == "REVIEW"


# ------------------------------------------------- run-1/2: bore detection
def test_slicing_failure_is_review_not_pass(tmp_path, cfg, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("slicer blew up")
    monkeypatch.setattr(trimesh.intersections, "mesh_multiplane", boom)
    p = tmp_path / "t.stl"
    tube().export(p)
    rec = scan_file(p, cfg, NO_BLOCKLIST)
    assert rec["verdict"] == "REVIEW" and "bore detection failed" in rec["reasons"][0]


def _bore_block():
    return shapes.extrude(box(-10, -10, 10, 10).difference(shapes.regular_polygon(0, 0, 9.0, 64)), 150.0)


def _sleeve(offset=0.0, shift=0.0):
    t = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    ri = 4.5 + offset
    inner = np.c_[ri * np.cos(t) + shift, ri * np.sin(t)]
    return shapes.extrude(Polygon(shapes.regular_polygon(0, 0, 15.0, 64).exterior.coords, [inner]), 150.0)


@parametrize("offset,shift", [(0.0, 0.0), (5e-6, 0.0), (0.0, 0.03125)])
def test_overlapping_shell_with_coincident_bore_is_review(cfg, offset, shift):
    m = trimesh.util.concatenate([_bore_block(), _sleeve(offset, shift)])
    f = body_features(m, cfg)
    assert "ambiguous" in f.get("bore_error", "")


def test_bore_budget_timeout_is_review(tmp_path, cfg):
    f = body_features(tube(), cfg, deadline=time.monotonic() - 1)
    assert "timeout" in f["bore_error"]
    cfg["limits"]["scan_seconds"] = 0
    p = tmp_path / "t.stl"
    tube().export(p)
    assert scan_file(p, cfg, NO_BLOCKLIST)["verdict"] == "REVIEW"


def test_loop_cap_is_review(cfg, hole_plate):
    cfg["bore_detection"]["max_loops_per_section"] = 2
    assert "loops" in body_features(hole_plate, cfg)["bore_error"]


def test_far_decoy_shell_cannot_dilute_slicing(tmp_path, cfg):
    tet = trimesh.creation.box((1, 1, 1))
    for z, name in ((3000.0, "near.stl"), (24000.0, "far.stl")):
        d = tet.copy()
        d.apply_translation([0, 0, z])
        p = tmp_path / name
        trimesh.util.concatenate([tube(), d]).export(p)
        rec = scan_file(p, cfg, NO_BLOCKLIST)
        assert rec["verdict"] == "REVIEW", (name, rec["reasons"])
    near = scan_file(tmp_path / "near.stl", cfg, NO_BLOCKLIST)
    assert near["features"][0]["n_bores"] >= 1


def test_bore_split_across_bodies_is_scored_whole(tmp_path, cfg):
    single = tmp_path / "single.stl"
    tube().export(single)
    assert scan_file(single, cfg, NO_BLOCKLIST)["verdict"] == "REVIEW"
    a, b = tube(50.0), tube(50.0, z0=50.0)
    scene = trimesh.Scene()
    scene.add_geometry(a, geom_name="a")
    scene.add_geometry(b, geom_name="b")
    p3 = tmp_path / "split.3mf"
    scene.export(p3)
    pstl = tmp_path / "split.stl"
    pstl.write_text(trimesh.exchange.stl.export_stl_ascii(a).replace("solid ", "solid a", 1)
                    + trimesh.exchange.stl.export_stl_ascii(b).replace("solid ", "solid b", 1))
    for p in (p3, pstl):
        rec = scan_file(p, cfg, NO_BLOCKLIST)
        assert rec["body_count"] == 2
        assert rec["verdict"] == "REVIEW", (p.name, rec["reasons"], rec["notes"])
        assert any("combined bodies" in r for r in rec["reasons"])


# ------------------------------------------------------------ run-1/2: CLI
def test_hash_and_parse_use_the_same_bytes(tmp_path, cfg, monkeypatch):
    p = tmp_path / "part.stl"
    cube().export(p)
    benign = p.read_bytes()
    real = pce.loader.trimesh.load

    def swap_then_load(*a, **k):
        shapes.control_abstract_bore_block().export(p)  # swapped after hashing
        return real(*a, **k)
    monkeypatch.setattr(pce.loader.trimesh, "load", swap_then_load)
    rec = scan_file(p, cfg, NO_BLOCKLIST)
    assert rec["sha256"] == hashlib.sha256(benign).hexdigest()
    assert rec["verdict"] == "PASS" and rec["features"][0]["n_bores"] == 0


def test_one_crashing_file_does_not_abort_the_batch(tmp_path, capsys, monkeypatch):
    for n in ("a.stl", "b.stl", "c.stl"):
        cube().export(tmp_path / n)
    real = pce.cli.scan_file

    def flaky(path, *a):
        if path.name == "b.stl":
            raise OSError("unreadable")
        return real(path, *a)
    monkeypatch.setattr(pce.cli, "scan_file", flaky)
    log = tmp_path / "audit.jsonl"
    assert main(["scan", str(tmp_path), "--json", "--audit-log", str(log)]) == 0
    out = json.loads(capsys.readouterr().out)
    by = {r["file"].split("/")[-1]: r["verdict"] for r in out["results"]}
    assert by == {"a.stl": "PASS", "b.stl": "REVIEW", "c.stl": "PASS"}
    assert len(log.read_text().splitlines()) == 3


def test_analysis_exception_is_review_with_hash(tmp_path, cfg, monkeypatch):
    def boom(_m):
        raise ZeroDivisionError("degenerate")
    monkeypatch.setattr(pce.cli, "geohash", boom)
    p = tmp_path / "a.stl"
    cube().export(p)
    rec = scan_file(p, cfg, NO_BLOCKLIST)
    assert rec["verdict"] == "REVIEW" and rec["sha256"]


def test_text_output_escapes_control_characters(tmp_path, capsys):
    stl = cube().export(file_type="stl")
    (tmp_path / "x\rPASS  ok.stl").write_bytes(stl)
    (tmp_path / "y\nPASS    fake.stl").write_bytes(stl)
    assert main(["scan", str(tmp_path), "--no-audit"]) == 0
    out = capsys.readouterr().out
    assert "\r" not in out
    verdict_lines = [ln for ln in out.splitlines() if ln.startswith(("PASS", "REVIEW", "BLOCK"))]
    assert len(verdict_lines) == 2  # no forged extra verdict line
    assert all(str(tmp_path) in ln for ln in verdict_lines)
    assert "\\r" in out and "\\n" in out


def test_unsupported_and_odd_names_are_review_not_skipped(tmp_path, capsys):
    cube().export(tmp_path / "plate.stl")
    (tmp_path / "cube.obj").write_text("v 0 0 0\n")
    (tmp_path / ".stl").write_bytes(cube().export(file_type="stl"))
    (tmp_path / "part.stl ").write_bytes(cube().export(file_type="stl"))
    assert main(["scan", str(tmp_path), "--json", "--no-audit"]) == 0
    out = json.loads(capsys.readouterr().out)
    by = {r["file"].split("/")[-1]: r["verdict"] for r in out["results"]}
    assert by == {"plate.stl": "PASS", "cube.obj": "REVIEW", ".stl": "REVIEW", "part.stl ": "REVIEW"}
    assert out["summary"] == {"PASS": 1, "REVIEW": 3, "BLOCK": 0}
