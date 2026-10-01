"""pce command line: `pce scan <folder-or-file>` and `pce features <file>`."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import trimesh

from pce.audit import append_record
from pce.config import ConfigError, load_config
from pce.features import body_features
from pce.geohash import Blocklist, geohash
from pce.loader import SUPPORTED, LoadError, load_bodies
from pce.scoring import score_file


def iter_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)


def _compact(feats: dict) -> dict:
    return {
        "watertight": feats["watertight"],
        "volume_mm3": feats["volume_mm3"],
        "bbox_mm": feats["bbox_mm"],
        "n_bores": len(feats["bores"]),
        "bores": [
            {k: b[k] for k in ("diameter_mm", "length_mm", "ld_ratio", "stepped", "caliber_match")}
            for b in feats["bores"]
        ],
    }


def scan_file(path: Path, cfg: dict, blocklist: Blocklist) -> dict:
    data = path.read_bytes()
    rec = {"file": str(path), "sha256": hashlib.sha256(data).hexdigest()}
    try:
        bodies = load_bodies(path)
    except LoadError as e:
        rec.update(geohash=None, body_count=0, features=[], verdict="REVIEW",
                   reasons=[f"could not load file: {e}"], notes=[])
        return rec
    feats = [body_features(b.mesh, cfg) for b in bodies]
    combined = trimesh.util.concatenate([b.mesh for b in bodies]) if len(bodies) > 1 else bodies[0].mesh
    gh = geohash(combined)
    body_hashes = [geohash(b.mesh) for b in bodies]
    hit = blocklist.contains(gh) or any(blocklist.contains(h) for h in body_hashes)
    res = score_file(feats, cfg, blocklist_hit=hit)
    rec.update(
        geohash=gh,
        body_geohashes=body_hashes,
        body_count=len(bodies),
        features=[_compact(f) for f in feats],
        verdict=res["verdict"],
        reasons=res["reasons"],
        notes=res["notes"],
    )
    return rec


def cmd_scan(args) -> int:
    cfg = load_config(args.config)
    target = Path(args.target)
    if not target.exists():
        print(f"pce: no such file or folder: {target}", file=sys.stderr)
        return 2
    blocklist = Blocklist.load(args.blocklist or cfg["blocklist_path"])
    audit_path = None if args.no_audit else (args.audit_log or cfg["audit_log_path"])
    results, summary = [], {"PASS": 0, "REVIEW": 0, "BLOCK": 0}
    for f in iter_files(target):
        rec = scan_file(f, cfg, blocklist)
        results.append(rec)
        summary[rec["verdict"]] += 1
        if audit_path:
            append_record(audit_path, rec)
        if not args.json:
            print(f"{rec['verdict']:<6}  {f}")
            for r in rec["reasons"]:
                print(f"        - {r}")
    if args.json:
        print(json.dumps({"results": results, "summary": summary}, indent=2))
    else:
        n = sum(summary.values())
        print(f"\nSummary: {n} files | PASS {summary['PASS']} | REVIEW {summary['REVIEW']}"
              f" | BLOCK {summary['BLOCK']}")
    return 0


def cmd_features(args) -> int:
    cfg = load_config(args.config)
    try:
        bodies = load_bodies(args.file)
    except LoadError as e:
        print(f"pce: {e}", file=sys.stderr)
        return 2
    out = {
        "file": str(args.file),
        "body_count": len(bodies),
        "bodies": [{"name": b.name, **body_features(b.mesh, cfg)} for b in bodies],
    }
    print(json.dumps(out, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pce", description="3D-print file compliance screening (Phase 1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="scan a file or folder of STL/3MF files")
    s.add_argument("target")
    s.add_argument("--config")
    s.add_argument("--json", action="store_true")
    s.add_argument("--blocklist")
    s.add_argument("--audit-log")
    s.add_argument("--no-audit", action="store_true")
    s.set_defaults(func=cmd_scan)
    f = sub.add_parser("features", help="dump the feature report for one file")
    f.add_argument("file")
    f.add_argument("--config")
    f.set_defaults(func=cmd_features)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"pce: config error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
