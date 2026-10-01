# print-compliance-engine (Phase 1)

loafecho's file-level screening engine for 3D-print files. It reads STL / 3MF files, measures **interpretable functional geometry** (mainly internal cylindrical bores), and returns **BLOCK / REVIEW / PASS** per file, with human-readable reasons such as:

```
BLOCK   corpus/control/control_abstract_bore_block.stl
        - bore 8.99mm (caliber band 9.0) with L/D 16.7 and length 150.0mm and stepped profile (8.99, 10.99 mm)
```

It is a **screening tool, not a weapon specification.** It flags *combinations* of generic geometric signals for human review. PASS is the common case.

## Hard rules (non-negotiable, apply to all future work here)

1. **Zero gun files.** Never download, generate, or model any firearm or firearm part, conversion device, suppressor, receiver, frame, barrel, or slide. Don't search for them, fetch them, or describe how to make one. Test meshes are generated programmatically from trimesh/shapely primitives and represent legitimate parts only. The one "should-flag" control (`control_abstract_bore_block`) is a plain rectangular block with a stepped through-hole: no grip, no trigger area, no rails, no realistic external shape.
2. **Never print anything.** File-level work only. This repo does not touch printer tooling.
3. **No thresholds tuned to a weapon's exact dimensions.** The only weapon-adjacent fact used is the public, generic one that common caliber bore diameters fall into bands (`caliber_bands` in the config: 5.56 / 7.62 / 9.0 / 11.43 mm ± 0.3). Everything else is generic geometry (length/diameter ratio, stepped profile).
4. **No network calls in the engine.** No external decision layer is integrated yet. That comes later as an optional add-on.

## Install / run

Requires `uv` (Python 3.12 is pinned in `.python-version`).

```bash
uv sync
uv run pytest                               # unit tests
uv run pce scan <folder-or-file> [--config my.yaml] [--json] [--blocklist FILE] [--audit-log FILE | --no-audit]
uv run pce features <file>                  # full per-body feature report (JSON)

# false-positive floor
uv run python corpus/generate_legit.py      # 186 legit parts -> corpus/legit/{tune,holdout}/ (+ control)
uv run pce scan corpus/legit
uv run python reports/make_fp_report.py     # -> reports/fp-floor.md
```

`corpus/legit/`, `corpus/control/` and `audit/` are gitignored. They regenerate deterministically (seed 20260922).

## How it works

| module | job |
|---|---|
| `pce.loader` | STL/3MF → one trimesh mesh per body (3MF objects are split; open meshes load and are reported, not rejected) |
| `pce.features` | per-body report: bores (diameter, length, L/D, stepped, plateaus, caliber-band match, interruptions), bbox, volume, watertightness, components. `detect_rails` is a **stub (TODO, Phase 2)** |
| `pce.scoring` | transparent rules → verdict + reasons + notes |
| `pce.geohash` | Layer 1 fallback: normalized geometry hash + exact-match `blocklist.txt` (starts empty) |
| `pce.audit` | one JSONL line per scanned file: file, sha256 of bytes, geohash, features summary, verdict, reasons, timestamp |
| `pce.cli` | `pce scan`, `pce features` |
| `pce.shapes` | primitive builders for tests and the corpus (innocent parts + the abstract control) |

**Bore detection** works by cross-section slicing. It cuts each body with up to 240 parallel planes along each candidate axis (world X/Y/Z plus the three principal axes). In each cut it finds the loops that enclose a *void*, fits a circle to each loop after resampling it by arc length, and rejects non-circles by max radial deviation and area ratio. It then chains coaxial circles across slices into bores (merging pieces split by cross-holes), and splits each bore's diameter profile into constant-diameter plateaus. Two plateaus of clearly different diameter = **stepped**.

**Scoring (default `combination` ruleset)**, per bore:

- **BLOCK** = in a caliber band AND L/D ≥ `ld_block` (12) AND stepped
- **REVIEW** = in a caliber band AND (L/D ≥ `ld_review` (8) OR (stepped AND L/D ≥ `ld_stepped_review` (3)))
- **PASS** otherwise. A lone in-band bore is recorded as a *note*, not a flag.
- Exact blocklist hit → BLOCK. Non-watertight body → REVIEW (`non_watertight: note` to relax). An unloadable file → REVIEW.
- `geometry_can_block: false` caps geometry-only verdicts at REVIEW (marked PRIORITY), so only the blocklist can BLOCK. **Recommended until a second decision layer exists**: see the FP report.

All thresholds live in `src/pce/default_config.yaml`. Pass a partial YAML/TOML with `--config` to override them. Unknown keys are rejected.

## False-positive floor (summary; full detail in `reports/fp-floor.md`)

186 innocent parts, deliberately hard: about half of the tubes have in-band IDs, plus long thin tubes, stepped bores, and a category of legit parts that carry all three signals (pen barrels, recorder bodies, pipettes, telescoping sleeves). Held-out half (93 parts), shipped rules:

- **BLOCK (hard FP): 9.7%. REVIEW (soft FP): 12.9%.** The naive "any bore in a caliber band" rule flags 49.5%.
- With `geometry_can_block: false`: **0% BLOCK, 22.6% REVIEW**. The control still goes red.
- Verdict: geometry alone cannot make BLOCK precise. Legit long, stepped, in-band tubes are geometrically the same as the abstract control. Use geometry as a REVIEW screen plus a second layer.

## Limits (read these before trusting a PASS)

- A bore tilted more than ~15° from every world/principal axis is measured as an inflated ellipse (out of band) and **missed** past ~20°.
- Bores that break out of the surface (open channels, U-slots) are not void loops and are not reported.
- Coarse polygonal bores (≤7 facets) fail the circle test. That is intended for hex/square holes, but it is an evasion route.
- Length resolution is one slice spacing (≤ span/240, ≥ 0.25 mm). Units are assumed to be mm.
- Non-watertight meshes may section partially. That is why they default to REVIEW.
- External shape is ignored entirely, and rail/interface detection is not implemented (stub).
- The geohash is scale-invariant and quantized to 3 decimals. It survives rename/translate/rotate/uniform-scale/re-export but **not** remeshing, and shapes whose proportions agree to about 1% collide (two such pairs in the corpus). Never blocklist plain primitives. Mirroring is not distinguished.
- About 0.85 s per part (pure CPU, single thread).

## Layout

```
src/pce/            engine package (+ default_config.yaml)
tests/              pytest suite (TDD)
corpus/             generate_legit.py (legit corpus + control); outputs gitignored
reports/            make_fp_report.py, assessment.md (hand-written), fp-floor.md (generated)
blocklist.txt       exact-match geohash blocklist (empty)
```
