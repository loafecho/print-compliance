import pytest
import trimesh

from pce.loader import LoadError, load_bodies


def test_load_stl_single_body(tmp_path, tube_9mm):
    p = tmp_path / "straw.stl"
    tube_9mm.export(p)
    bodies = load_bodies(p)
    assert len(bodies) == 1
    assert bodies[0].mesh.is_watertight
    assert bodies[0].name


def test_load_3mf_splits_bodies(tmp_path, tube_9mm, solid_rod):
    scene = trimesh.Scene()
    scene.add_geometry(tube_9mm, geom_name="tube")
    rod = solid_rod.copy()
    rod.apply_translation([50, 0, 0])
    scene.add_geometry(rod, geom_name="rod")
    p = tmp_path / "pair.3mf"
    scene.export(p)
    bodies = load_bodies(p)
    assert len(bodies) == 2
    assert all(b.mesh.is_watertight for b in bodies)


def test_non_watertight_loads_without_crash(tmp_path, open_mesh):
    p = tmp_path / "open.stl"
    open_mesh.export(p)
    bodies = load_bodies(p)
    assert len(bodies) == 1
    assert bodies[0].mesh.is_watertight is False


def test_missing_and_unsupported(tmp_path):
    with pytest.raises(LoadError):
        load_bodies(tmp_path / "nope.stl")
    bad = tmp_path / "x.obj"
    bad.write_text("v 0 0 0\n")
    with pytest.raises(LoadError):
        load_bodies(bad)


def test_garbage_stl_raises_loaderror(tmp_path):
    p = tmp_path / "junk.stl"
    p.write_bytes(b"\x00\x01not a mesh")
    with pytest.raises(LoadError):
        load_bodies(p)
