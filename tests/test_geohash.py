import numpy as np
import trimesh

from pce import shapes
from pce.geohash import Blocklist, geohash
from pce.loader import load_bodies


def _part():
    # deliberately asymmetric legit part: L-bracket with holes
    return shapes.l_bracket(40, 30, 20, 4, hole_d=4.0)


def test_hash_is_stable_hex():
    h = geohash(_part())
    assert isinstance(h, str) and len(h) == 64
    assert geohash(_part()) == h


def test_translate_rotate_rescale_invariant():
    base = geohash(_part())
    rng = np.random.default_rng(7)
    for _ in range(5):
        m = _part()
        R = trimesh.transformations.random_rotation_matrix(rng.random(3))
        m.apply_transform(R)
        m.apply_translation(rng.uniform(-500, 500, 3))
        m.apply_scale(float(rng.uniform(0.2, 5.0)))
        assert geohash(m) == base


def test_rename_and_reexport_invariant(tmp_path):
    base = geohash(_part())
    a = tmp_path / "original.stl"
    _part().export(a)
    b = tmp_path / "totally_different_name.stl"
    b.write_bytes(a.read_bytes())
    c = tmp_path / "reexport.3mf"
    _part().export(c)
    for p in (a, b, c):
        assert geohash(load_bodies(p)[0].mesh) == base


def test_different_mesh_different_hash():
    hashes = {
        geohash(_part()),
        geohash(shapes.l_bracket(40, 30, 25, 4, hole_d=4.0)),
        geohash(shapes.stepped_tube([(100, 4.5, 6.0)])),
        geohash(shapes.stepped_tube([(100, 4.0, 6.0)])),
        geohash(trimesh.creation.box((10, 20, 30))),
    }
    assert len(hashes) == 5


def test_blocklist_starts_empty_and_matches(tmp_path):
    p = tmp_path / "blocklist.txt"
    bl = Blocklist.load(p)  # missing file -> empty
    assert len(bl) == 0
    h = geohash(_part())
    assert not bl.contains(h)
    p.write_text(f"# comment\n{h}  some note\n")
    bl = Blocklist.load(p)
    assert len(bl) == 1 and bl.contains(h)
