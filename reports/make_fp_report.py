"""Build reports/fp-floor.md from the legit corpus.

    uv run python corpus/generate_legit.py      # regenerate the corpus (fixed seed)
    uv run python reports/make_fp_report.py

Features are computed once per file; the file is then scored under three rule postures:
  single_signal     - naive baseline: any caliber-band bore -> BLOCK
  v0_combination    - combination rules as first written (ld_stepped_review = 0)
  v1_combination    - the shipped default config (after the one tune-half adjustment)
The hand-written assessment lives in reports/assessment.md and is appended verbatim.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

from pce.config import load_config
from pce.features import body_features
from pce.loader import load_bodies
from pce.scoring import score_file

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus" / "legit"
CONTROL = ROOT / "corpus" / "control" / "control_abstract_bore_block.stl"
OUT = ROOT / "reports" / "fp-floor.md"
ASSESS = ROOT / "reports" / "assessment.md"


def rulesets():
    base = load_config(None)
    single = copy.deepcopy(base)
    single["scoring"]["ruleset"] = "single_signal"
    v0 = copy.deepcopy(base)
    v0["scoring"]["ld_stepped_review"] = 0.0
    return {"single_signal": single, "v0_combination": v0, "v1_combination": base}


def pct(a, n):
    return f"{100.0 * a / n:.1f}%" if n else "n/a"


def main():
    rs = rulesets()
    cfg = rs["v1_combination"]
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    t0 = time.time()
    rows = []
    for r in manifest:
        bodies = load_bodies(CORPUS / r["file"])
        feats = [body_features(b.mesh, cfg) for b in bodies]
        scores = {name: score_file(feats, c) for name, c in rs.items()}
        found = None
        if "expect_d" in r:
            found = any(
                abs(b["diameter_mm"] - r["expect_d"]) <= 0.3
                or any(abs(s["diameter_mm"] - r["expect_d"]) <= 0.3 for s in b["segments"])
                for f in feats for b in f["bores"]
            )
        rows.append({**r, "scores": scores, "found": found,
                     "n_bores": sum(len(f["bores"]) for f in feats)})
    elapsed = time.time() - t0

    ctl_feats = [body_features(b.mesh, cfg) for b in load_bodies(CONTROL)]
    ctl = {name: score_file(ctl_feats, c) for name, c in rs.items()}

    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
    L = []
    w = L.append
    w("# False-positive floor report: Phase 1 functional-geometry rules\n")
    w(f"Generated {dt.date.today().isoformat()} by `reports/make_fp_report.py` at engine commit "
      f"`{commit}`. Corpus: {len(rows)} programmatically generated legitimate parts "
      f"(`corpus/generate_legit.py`, seed 20260922), split per category into "
      f"{sum(r['split'] == 'tune' for r in rows)} tune / {sum(r['split'] == 'holdout' for r in rows)} "
      f"held-out. Feature extraction took {elapsed:.0f}s ({elapsed / len(rows):.2f}s/part).\n")
    w("Every part in the corpus is innocent, so **any BLOCK is a hard false positive and any REVIEW "
      "is a soft false positive.**\n")

    hold = [r for r in rows if r["split"] == "holdout"]
    c = Counter(r["scores"]["v1_combination"]["verdict"] for r in hold)
    w("## Headline (held-out half, shipped default rules)\n")
    w(f"- Parts: **{len(hold)}**")
    w(f"- PASS {c['PASS']} / REVIEW {c['REVIEW']} / BLOCK {c['BLOCK']}")
    w(f"- **Hard FP rate (BLOCK): {pct(c['BLOCK'], len(hold))}**")
    w(f"- **Soft FP rate (REVIEW): {pct(c['REVIEW'], len(hold))}**")
    v = ctl["v1_combination"]
    w(f"- Should-flag control `control_abstract_bore_block`: **{v['verdict']}** "
      f"({'; '.join(v['reasons'])})\n")

    w("## Rule posture comparison\n")
    w("| ruleset | split | n | PASS | REVIEW | BLOCK | hard FP | soft FP | any flag | control |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for name in rs:
        for split in ("tune", "holdout", "all"):
            sub = rows if split == "all" else [r for r in rows if r["split"] == split]
            k = Counter(r["scores"][name]["verdict"] for r in sub)
            n = len(sub)
            w(f"| {name} | {split} | {n} | {k['PASS']} | {k['REVIEW']} | {k['BLOCK']} | "
              f"{pct(k['BLOCK'], n)} | {pct(k['REVIEW'], n)} | {pct(k['BLOCK'] + k['REVIEW'], n)} | "
              f"{ctl[name]['verdict']} |")
    w("")
    w("`single_signal` = any bore in a caliber band is flagged (BLOCK). `v0_combination` = "
      "combination rules as first written. `v1_combination` = shipped default: identical except "
      "`ld_stepped_review: 3.0`, the one adjustment, chosen by looking at the **tune** half only.\n")

    w("## Per category (held-out half)\n")
    w("| category | n | single-signal flags | v0 REVIEW | v0 BLOCK | v1 REVIEW | v1 BLOCK |")
    w("|---|---|---|---|---|---|---|")
    bycat = defaultdict(list)
    for r in hold:
        bycat[r["category"]].append(r)
    for cat in sorted(bycat):
        sub = bycat[cat]
        cnt = lambda rule, v: sum(r["scores"][rule]["verdict"] == v for r in sub)  # noqa: E731
        w(f"| {cat} | {len(sub)} | {cnt('single_signal', 'BLOCK')} | {cnt('v0_combination', 'REVIEW')} | "
          f"{cnt('v0_combination', 'BLOCK')} | {cnt('v1_combination', 'REVIEW')} | "
          f"{cnt('v1_combination', 'BLOCK')} |")
    w("")

    w("## Every non-PASS legit part (shipped default rules, both halves)\n")
    w("| split | file | category | verdict | reasons |")
    w("|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["split"] != "holdout",
                                         r["scores"]["v1_combination"]["verdict"] != "BLOCK", r["file"])):
        s = r["scores"]["v1_combination"]
        if s["verdict"] != "PASS":
            w(f"| {r['split']} | `{Path(r['file']).name}` | {r['category']} | **{s['verdict']}** | "
              f"{'<br>'.join(s['reasons'])} |")
    w("")
    w("### Changed by the v0 -> v1 adjustment\n")
    changed = [r for r in rows if r["scores"]["v0_combination"]["verdict"]
               != r["scores"]["v1_combination"]["verdict"]]
    if changed:
        w("| split | file | v0 | v1 | v0 reason |")
        w("|---|---|---|---|---|")
        for r in changed:
            w(f"| {r['split']} | `{Path(r['file']).name}` | {r['scores']['v0_combination']['verdict']} | "
              f"{r['scores']['v1_combination']['verdict']} | "
              f"{'<br>'.join(r['scores']['v0_combination']['reasons'])} |")
    else:
        w("(none)")
    w("")

    exp = [r for r in rows if r["found"] is not None]
    hit = sum(1 for r in exp if r["found"])
    w("## Detector sanity check (is the low FP rate real or just missed bores?)\n")
    w(f"For the {len(exp)} tube parts whose main bore diameter the generator knows, the detector "
      f"found a bore within 0.3 mm of the true diameter in **{hit}/{len(exp)}** ({pct(hit, len(exp))}).")
    miss = [r for r in exp if not r["found"]]
    if miss:
        w("Missed: " + ", ".join(f"`{Path(r['file']).name}` (expected {r['expect_d']} mm)" for r in miss))
    tilted = [r for r in exp if r["category"] == "tube_in_band" and r["name"].endswith(("_00", "_05", "_10", "_15"))]
    w(f"\nThis includes {len(tilted)} band tubes exported at a random tilt (found via the principal axis).\n")

    w("## Assessment\n")
    w(ASSESS.read_text().strip() if ASSESS.exists() else "_(assessment pending)_")
    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT}")
    print(json.dumps({"holdout_v1": dict(c), "n_holdout": len(hold), "control": v["verdict"],
                      "recall": f"{hit}/{len(exp)}"}))


if __name__ == "__main__":
    main()
