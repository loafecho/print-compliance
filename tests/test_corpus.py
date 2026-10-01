import importlib.util
import json
from pathlib import Path

from pce.cli import scan_file
from pce.config import load_config
from pce.geohash import Blocklist

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate_legit", ROOT / "corpus" / "generate_legit.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_generator_is_deterministic_and_watertight(tmp_path):
    a = gen.generate(tmp_path / "a", seed=11, limit=2)
    b = gen.generate(tmp_path / "b", seed=11, limit=2)
    assert a == b
    assert len(a) == 2 * len(gen.PLAN)
    assert all(r["watertight"] for r in a)
    assert {r["split"] for r in a} == {"tune", "holdout"}
    assert json.loads((tmp_path / "a" / "manifest.json").read_text()) == a


def test_control_goes_red(tmp_path):
    p = gen.generate_control(tmp_path)
    assert p.name == "control_abstract_bore_block.stl"
    rec = scan_file(p, load_config(None), Blocklist(set()))
    assert rec["verdict"] == "BLOCK"
