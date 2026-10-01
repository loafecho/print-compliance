"""Transparent rule-based scoring: per-file verdict BLOCK / REVIEW / PASS with reasons.

Signals per bore (all generic geometry, none weapon-specific):
  caliber  - a constant-diameter section of the bore sits inside a configured caliber band
  long     - length/diameter ratio >= ld_review
  vlong    - length/diameter ratio >= ld_block
  stepped  - the bore has two plateaus of clearly different diameter

ruleset "combination" (default, conservative):
  BLOCK  = caliber AND vlong AND stepped        (all signals agree)
  REVIEW = caliber AND (long OR stepped)        (any corroborating signal)
  PASS   = everything else; a lone caliber-band bore is recorded as a note only.
ruleset "single_signal" (naive baseline for the FP report): BLOCK = caliber alone.

Also: exact geohash blocklist hit -> BLOCK; non-watertight body -> REVIEW (configurable),
because the bore detector cannot be trusted on an open mesh.
"""
from __future__ import annotations

ORDER = {"PASS": 0, "REVIEW": 1, "BLOCK": 2}


def _describe(b: dict, sig: dict) -> str:
    m = b.get("caliber_match")
    d = m["diameter_mm"] if m and "diameter_mm" in m else b["diameter_mm"]
    parts = [f"bore {d:.2f}mm"]
    if m:
        parts[0] += f" (caliber band {float(m['nominal_mm'])})"
    extras = [f"L/D {b['ld_ratio']:.1f}", f"length {b['length_mm']:.1f}mm"]
    if b.get("stepped"):
        segs = ", ".join(f"{s['diameter_mm']:.2f}" for s in b.get("segments", []))
        extras.append(f"stepped profile ({segs} mm)" if segs else "stepped profile")
    return parts[0] + " with " + " and ".join(extras)


def _bore_verdict(b: dict, cfg: dict) -> tuple[str, dict]:
    sc = cfg["scoring"]
    sig = {
        "caliber": b.get("caliber_match") is not None,
        "long": b["ld_ratio"] >= sc["ld_review"],
        "vlong": b["ld_ratio"] >= sc["ld_block"],
        "stepped": bool(b.get("stepped")),
    }
    rs = sc["ruleset"]
    if rs == "combination":
        if sig["caliber"] and sig["vlong"] and sig["stepped"]:
            return "BLOCK", sig
        if sig["caliber"] and (sig["long"] or sig["stepped"]):
            return "REVIEW", sig
        return "PASS", sig
    if rs == "single_signal":
        return ("BLOCK" if sig["caliber"] else "PASS"), sig
    raise ValueError(f"unknown scoring.ruleset {rs!r}")


def score_file(bodies: list[dict], cfg: dict, blocklist_hit: bool = False) -> dict:
    verdict = "PASS"
    reasons: list[str] = []
    notes: list[str] = []
    signals: list[dict] = []

    def bump(v):
        nonlocal verdict
        if ORDER[v] > ORDER[verdict]:
            verdict = v

    if cfg["scoring"]["ruleset"] not in ("combination", "single_signal"):
        raise ValueError(f"unknown scoring.ruleset {cfg['scoring']['ruleset']!r}")
    if blocklist_hit:
        bump("BLOCK")
        reasons.append("geometry hash matches the exact-match blocklist")
    for bi, body in enumerate(bodies):
        prefix = f"body {bi}: " if len(bodies) > 1 else ""
        if not body.get("watertight", True):
            if cfg["scoring"]["non_watertight"] == "review":
                bump("REVIEW")
                reasons.append(prefix + "mesh is not watertight; bore detection is unreliable")
            else:
                notes.append(prefix + "mesh is not watertight")
        if body.get("bore_error"):
            bump("REVIEW")
            reasons.append(prefix + f"bore detection failed ({body['bore_error']})")
        for b in body.get("bores", []):
            v, sig = _bore_verdict(b, cfg)
            signals.append({"body": bi, **sig, "verdict": v})
            if v != "PASS":
                bump(v)
                reasons.append(prefix + _describe(b, sig))
            elif sig["caliber"]:
                notes.append(prefix + "single signal only: " + _describe(b, sig))
    # most severe first
    return {"verdict": verdict, "reasons": reasons, "notes": notes, "signals": signals}
