import numpy as np
import pytest
import trimesh

from pce.features import body_features, caliber_match, detect_rails, find_bores


def test_plain_tube_one_bore(tube_9mm, cfg):
    bores = find_bores(tube_9mm, cfg)
    assert len(bores) == 1
    b = bores[0]
    assert b["diameter_mm"] == pytest.approx(9.0, abs=0.15)
    assert b["length_mm"] == pytest.approx(100.0, abs=3.0)
    assert b["ld_ratio"] == pytest.approx(100 / 9.0, rel=0.05)
    assert b["stepped"] is False


def test_stepped_spacer_detected(stepped_spacer, cfg):
    bores = find_bores(stepped_spacer, cfg)
    assert len(bores) == 1
    b = bores[0]
    assert b["stepped"] is True
    diams = sorted(s["diameter_mm"] for s in b["segments"])
    assert diams[0] == pytest.approx(6.0, abs=0.15)
    assert diams[-1] == pytest.approx(12.0, abs=0.15)
    assert b["length_mm"] == pytest.approx(50.0, abs=3.0)


def test_solid_rod_has_no_bores(solid_rod, cfg):
    assert find_bores(solid_rod, cfg) == []


def test_plate_holes_are_short_bores(hole_plate, cfg):
    bores = find_bores(hole_plate, cfg)
    assert len(bores) == 4
    for b in bores:
        assert b["diameter_mm"] == pytest.approx(5.0, abs=0.2)
        assert b["ld_ratio"] < 1.5


def test_tilted_tube_found_via_pca_axis(tube_9mm, cfg):
    m = tube_9mm.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(0.7, [1, 1, 0]))
    m.apply_translation([13, -7, 42])
    bores = find_bores(m, cfg)
    assert len(bores) == 1
    assert bores[0]["diameter_mm"] == pytest.approx(9.0, abs=0.15)


def test_hex_hole_is_not_a_circular_bore(cfg):
    from pce import shapes

    m = shapes.plate_with_holes(30, 30, 10, [(0, 0)], 9.0, hole_sections=6)
    assert find_bores(m, cfg) == []


def test_caliber_match(cfg):
    assert caliber_match(9.02, cfg)["nominal_mm"] == 9.0
    assert caliber_match(7.70, cfg)["nominal_mm"] == 7.62
    assert caliber_match(10.0, cfg) is None
    assert caliber_match(3.0, cfg) is None


def test_body_features_report(tube_9mm, cfg):
    f = body_features(tube_9mm, cfg)
    assert f["watertight"] is True
    assert f["volume_mm3"] > 0
    assert sorted(f["bbox_mm"]) == pytest.approx([12, 12, 100], abs=0.1)
    assert f["bores"][0]["caliber_match"]["nominal_mm"] == 9.0
    assert f["rails"] is None  # stub: out of scope in Phase 1


def test_non_watertight_body_features_do_not_crash(open_mesh, cfg):
    f = body_features(open_mesh, cfg)
    assert f["watertight"] is False
    assert f["volume_mm3"] is None
    assert isinstance(f["bores"], list)


def test_rails_stub():
    assert detect_rails(None) is None
