"""pce command line: `pce scan <folder-or-file>` and `pce features <file>`."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import trimesh

from pce.audit import append_record
from pce.config import ConfigError, load_config
from pce.features import body_features
from pce.geohash import Blocklist, geohash
from pce.loader import LoadError, load_bodies
from pce.scoring import score_file


def iter_files(target: Path) -> list[Path]:
    """Every regular file under target. Unsupported types are not skipped here: they
    reach load_bodies and come back as REVIEW, so nothing in the folder goes unscreened
    or unaudited."""
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.is_file())


def _term_safe(text: str) -> str:
    """Escape control characters (newline, CR, ESC, undecodable bytes) so a file name
    or parser message cannot forge or overwrite verdict lines on a terminal."""
    return "".join(c if c.isprintable() else ascii(c)[1:-1] for c in str(text))


def _review_record(path: Path, sha: str | None, reason: str) -> dict:
    return {"file": str(path), "sha256": sha, "geohash": None, "body_count": 0,
            "features": [], "verdict": "REVIEW", "reasons": [reason], "notes": []}


def _same_bore(b: dict, others: list[dict]) -> bool:
    for o in others:
        d = o["diameter_mm"]
        if (abs(b["diameter_mm"] - d) <= max(0.3, 0.05 * d)
                and abs(b["length_mm"] - o["length_mm"]) <= max(2.0, 0.05 * o["length_mm"])
                and sum((x - y) ** 2 for x, y in zip(b["center"], o["center"])) ** 0.5
                <= max(1.0, 0.25 * d)):
            return True
    return False


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
    limits = cfg["limits"]
    cap = int(limits["max_file_mb"]) * 1024 * 1024
    if path.stat().st_size > cap:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return _review_record(path, h.hexdigest(), f"could not load file: over the "
                              f"{limits['max_file_mb']} MB size limit; not analysed")
    # read once: the bytes that are hashed are the bytes that are parsed and scored
    data = path.read_bytes()
    rec = {"file": str(path), "sha256": hashlib.sha256(data).hexdigest()}
    try:
        bodies = load_bodies(path, data=data, limits=limits)
    except LoadError as e:
        rec.update(geohash=None, body_count=0, features=[], verdict="REVIEW",
                   reasons=[f"could not load file: {e}"], notes=[])
        return rec
    try:
        return _analyse(rec, bodies, cfg, blocklist)
    except Exception as e:  # never let one file's analysis crash fail open or abort a batch
        rec.update(_review_record(path, rec["sha256"],
                                  f"analysis failed: {type(e).__name__}: {e}"))
        return rec


def _analyse(rec: dict, bodies: list, cfg: dict, blocklist: Blocklist) -> dict:
    deadline = time.monotonic() + float(cfg["limits"]["scan_seconds"])
    feats = [body_features(b.mesh, cfg, deadline) for b in bodies]
    combined = trimesh.util.concatenate([b.mesh for b in bodies]) if len(bodies) > 1 else bodies[0].mesh
    scored = list(feats)
    combined_feats = None
    if len(bodies) > 1:
        # a bore split across bodies is only visible on the combined geometry; score
        # any bore found there that no single body already reports
        cf = body_features(combined, cfg, deadline)
        seen = [b for f in feats for b in f["bores"]]
        combined_feats = {**cf, "watertight": True,  # watertightness is scored per body
                          "bores": [b for b in cf["bores"] if not _same_bore(b, seen)],
                          "label": "combined bodies"}
        scored.append(combined_feats)
    gh = geohash(combined)
    body_hashes = [geohash(b.mesh) for b in bodies]
    hit = blocklist.contains(gh) or any(blocklist.contains(h) for h in body_hashes)
    res = score_file(scored, cfg, blocklist_hit=hit)
    if combined_feats is not None:
        rec["combined_features"] = _compact(combined_feats)
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
        try:
            rec = scan_file(f, cfg, blocklist)
        except Exception as e:  # e.g. unreadable file: still a verdict and an audit line
            rec = _review_record(f, None, f"could not scan file: {type(e).__name__}: {e}")
        results.append(rec)
        summary[rec["verdict"]] += 1
        if audit_path:
            append_record(audit_path, rec)
        if not args.json:
            print(f"{rec['verdict']:<6}  {_term_safe(f)}")
            for r in rec["reasons"]:
                print(f"        - {_term_safe(r)}")
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
        bodies = load_bodies(args.file, limits=cfg["limits"])
    except LoadError as e:
        print(f"pce: {_term_safe(e)}", file=sys.stderr)
        return 2
    deadline = time.monotonic() + float(cfg["limits"]["scan_seconds"])
    out = {
        "file": str(args.file),
        "body_count": len(bodies),
        "bodies": [{"name": b.name, **body_features(b.mesh, cfg, deadline)} for b in bodies],
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
