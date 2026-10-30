# print-compliance

A file-level screening engine for 3D-print files. It reads STL and 3MF files, measures a small set of interpretable geometric features (mainly internal cylindrical bores), and returns **PASS**, **REVIEW** or **BLOCK** for each file, with a reason a person can read and check:

```
REVIEW  corpus/control/control_abstract_bore_block.stl
        - PRIORITY (all geometry signals present, BLOCK disabled): bore 8.99mm (caliber band 9.0) with L/D 16.7 and length 150.0mm and stepped profile (8.99, 10.99 mm)
```

## Why it exists

A print service that accepts uploaded files needs a first-pass screen for parts that look like regulated weapon components, without turning every pen barrel and plumbing reducer into a rejection. This project is the measurable first layer of that screen. It is built around one question: how far can plain, explainable geometry go before it starts hurting legitimate customers? The answer is in [`reports/fp-floor.md`](reports/fp-floor.md), and it shaped the default configuration: shape alone can send a file to human review, but it cannot reject one.

It is a screening tool, not a weapon specification. It flags combinations of generic geometric signals. PASS is the common case.

## Design constraints

- **No weapon files anywhere.** Every test mesh and corpus part is generated in code from trimesh/shapely primitives and represents an ordinary part. The single should-flag control (`control_abstract_bore_block`) is a plain rectangular block with a stepped through-hole: no grip, no rails, no realistic external shape.
- **No thresholds tuned to a specific weapon.** The only domain fact used is the public one that common caliber bore diameters fall into bands (`caliber_bands`: 5.56 / 7.62 / 9.0 / 11.43 mm, ±0.3). Everything else is generic geometry: length/diameter ratio and stepped diameter profiles.
- **File-level only, no network calls.** The engine never talks to a printer or a remote service. A second decision layer (provenance, near-duplicate matching, a model, or a person) is out of scope for this repo.

## How it works

| module | job |
|---|---|
| `pce.loader` | STL/3MF to one trimesh mesh per body. 3MF objects are split; open meshes load and are reported, not rejected. |
| `pce.features` | Per-body report: bores (diameter, length, L/D, stepped, plateaus, caliber-band match, interruptions), bounding box, volume, watertightness, component count. `detect_rails` is a stub. |
| `pce.scoring` | Transparent rules that produce a verdict, reasons and notes. |
| `pce.geohash` | Normalized geometry hash plus an exact-match `blocklist.txt` (ships empty). |
| `pce.audit` | Append-only JSONL log, one line per scanned file: path, sha256 of the bytes, geohash, feature summary, verdict, reasons, timestamp. |
| `pce.cli` | `pce scan` and `pce features`. |
| `pce.shapes` | Primitive builders used by the tests and the corpus. |

**Bore detection** uses cross-section slicing. Each body is cut with up to 240 parallel planes along six candidate axes (world X/Y/Z and the three principal axes). In each cut the engine finds loops that enclose a void, resamples each loop by arc length, fits a circle, and rejects non-circles by maximum radial deviation and area ratio. Coaxial circles in neighbouring slices are chained into bores, collinear pieces split by a cross-hole are merged back together, and each bore's diameter profile is split into constant-diameter plateaus. Two plateaus of clearly different diameter make a bore **stepped**.

**Scoring** (default `combination` ruleset), per bore:

- Full signal: in a caliber band AND L/D >= `ld_block` (12) AND stepped. With the shipped default `geometry_can_block: false` this is a **PRIORITY REVIEW**. Set it to `true` and it becomes a **BLOCK**.
- **REVIEW**: in a caliber band AND (L/D >= `ld_review` (8) OR (stepped AND L/D >= `ld_stepped_review` (3))).
- **PASS** otherwise. A lone in-band bore is recorded as a note, not a flag.
- An exact blocklist hit is always **BLOCK**. A non-watertight body is **REVIEW** (set `non_watertight: note` to relax this). A file that fails to load is **REVIEW**.

All thresholds live in [`src/pce/default_config.yaml`](src/pce/default_config.yaml). Pass a partial YAML or TOML file with `--config` to override any of them; unknown keys are rejected.

## Install and run

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned in `.python-version`.

```bash
uv sync
uv run pce scan <folder-or-file> [--config my.yaml] [--json] [--blocklist FILE] [--audit-log FILE | --no-audit]
uv run pce features <file>                  # full per-body feature report as JSON
```

Reproduce the false-positive report:

```bash
uv run python corpus/generate_legit.py      # 186 legit parts -> corpus/legit/{tune,holdout}/, plus the control
uv run pce scan corpus/legit --no-audit
uv run python reports/make_fp_report.py     # rewrites reports/fp-floor.md (about 3 minutes)
```

`corpus/legit/`, `corpus/control/` and `audit/` are gitignored. The corpus regenerates deterministically from seed 20260922.

## Tests

```bash
uv run pytest        # 51 tests: loader, features, scoring, geohash, config, CLI/audit, corpus determinism
uvx ruff check .
```

CI runs both on every push (`.github/workflows/ci.yml`), plus a CLI smoke scan of the generated control file.

## Results: the false-positive floor

The corpus is 186 innocent parts, built to be hard: about half of the tube-like parts have an inner diameter inside a caliber band, and one category (pen barrels, recorder bodies, pipettes, telescoping sleeves) carries all three signals. Thresholds were adjusted on the tune half only. On the held-out half (93 parts):

| posture | PASS | REVIEW | BLOCK | control |
|---|---|---|---|---|
| naive rule: any bore in a caliber band | 47 | 0 | 46 (49.5%) | BLOCK |
| combination rules, geometry may BLOCK | 72 | 12 (12.9%) | 9 (9.7%) | BLOCK |
| combination rules, shipped default (`geometry_can_block: false`) | 72 | 21 (22.6%) | 0 | REVIEW (priority) |

The main finding: geometry alone cannot make BLOCK precise. A legitimate long, stepped, in-band tube is geometrically the same as the abstract control, and no threshold separates them without trading false positives for misses. Geometry works as a REVIEW screen; any automatic rejection needs a second layer behind it. Because the corpus is deliberately band-heavy, these rates describe a stress test, not real upload traffic. Full detail, per-category numbers and every flagged part: [`reports/fp-floor.md`](reports/fp-floor.md), with the written assessment in [`reports/assessment.md`](reports/assessment.md).

## Limits

Read these before trusting a PASS.

- A bore tilted more than about 15° from every world and principal axis is measured as an inflated ellipse (out of band), and it is missed entirely past about 20°.
- Bores that break out of the surface (open channels, U-slots) are not void loops and are not reported.
- Coarse polygonal bores (7 or fewer facets) fail the circle test. That is intended for hex and square holes, but it is an evasion route.
- Length resolution is one slice spacing (at most span/240, at least 0.25 mm). Units are assumed to be millimetres.
- Non-watertight meshes may section partially, which is why they default to REVIEW.
- External shape is ignored, and rail/interface detection is not implemented.
- The geohash is scale-invariant and quantized to 3 decimals. It survives rename, translation, rotation, uniform scaling and re-export, but not remeshing, and it does not distinguish mirror images. Shapes whose proportions agree to about 1% collide (two such pairs exist in the corpus), so a plain primitive should never be blocklisted.
- The detector recall figure (68/68 known main bores) covers the corpus's own tubes, which are mostly axis-aligned.
- Speed is about 0.8 to 0.9 s per part on one CPU core.

## Layout

```
src/pce/            engine package (+ default_config.yaml)
tests/              pytest suite
corpus/             generate_legit.py (legit corpus + control); outputs gitignored
reports/            make_fp_report.py, assessment.md (hand-written), fp-floor.md (generated)
blocklist.txt       exact-match geohash blocklist (empty)
```

## License

MIT. See [LICENSE](LICENSE).
