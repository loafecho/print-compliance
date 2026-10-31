import hashlib
import json

import trimesh

from pce import shapes
from pce.audit import append_record
from pce.cli import main


def test_append_record(tmp_path):
    log = tmp_path / "a" / "log.jsonl"
    rec = {"file": "x.stl", "verdict": "PASS"}
    append_record(log, rec)
    append_record(log, rec)
    lines = log.read_text().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["verdict"] == "PASS" and "timestamp" in row


def _folder(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    shapes.stepped_tube([(100.0, 4.5, 6.0)]).export(tmp_path / "straw.stl")
    trimesh.creation.box((20, 20, 5)).export(tmp_path / "plate.stl")
    shapes.control_abstract_bore_block().export(tmp_path / "control_abstract_bore_block.stl")
    (tmp_path / "notes.txt").write_text("not a mesh")
    return tmp_path


def test_scan_json_and_audit(tmp_path, capsys):
    folder = _folder(tmp_path / "in")
    log = tmp_path / "audit.jsonl"
    rc = main(["scan", str(folder), "--json", "--audit-log", str(log)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    by = {r["file"].split("/")[-1]: r for r in out["results"]}
    assert by["control_abstract_bore_block.stl"]["verdict"] == "REVIEW"
    assert "PRIORITY" in by["control_abstract_bore_block.stl"]["reasons"][0]
    assert by["plate.stl"]["verdict"] == "PASS"
    assert by["straw.stl"]["verdict"] in ("PASS", "REVIEW")
    # unsupported files are never skipped silently: REVIEW + audit row
    assert by["notes.txt"]["verdict"] == "REVIEW"
    assert sum(out["summary"].values()) == 4
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows) == 4
    plate = next(r for r in rows if r["file"].endswith("plate.stl"))
    assert plate["sha256"] == hashlib.sha256((folder / "plate.stl").read_bytes()).hexdigest()
    for key in ("geohash", "features", "verdict", "reasons", "timestamp"):
        assert key in plate


def test_scan_text_output(tmp_path, capsys):
    folder = _folder(tmp_path / "in")
    rc = main(["scan", str(folder), "--no-audit"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BLOCK" in out and "Summary" in out


def test_scan_unreadable_file_is_review_not_crash(tmp_path, capsys):
    (tmp_path / "junk.stl").write_bytes(b"\x00garbage")
    rc = main(["scan", str(tmp_path), "--json", "--no-audit"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["results"][0]["verdict"] == "REVIEW"


def test_features_command(tmp_path, capsys):
    p = tmp_path / "straw.stl"
    shapes.stepped_tube([(100.0, 4.5, 6.0)]).export(p)
    assert main(["features", str(p)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["bodies"][0]["bores"][0]["caliber_match"]["nominal_mm"] == 9.0


def test_custom_config(tmp_path, capsys):
    cfgp = tmp_path / "c.yaml"
    cfgp.write_text("scoring:\n  ruleset: single_signal\n  geometry_can_block: true\n")
    p = tmp_path / "straw.stl"
    shapes.stepped_tube([(30.0, 4.5, 6.0)]).export(p)
    main(["scan", str(p), "--config", str(cfgp), "--json", "--no-audit"])
    out = json.loads(capsys.readouterr().out)
    assert out["results"][0]["verdict"] == "BLOCK"
