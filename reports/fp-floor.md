# False-positive floor report: Phase 1 functional-geometry rules

Generated 2026-10-01 by `reports/make_fp_report.py`. Corpus: 186 programmatically generated legitimate parts (`corpus/generate_legit.py`, seed 20260922), split per category into 93 tune / 93 held-out. Feature extraction took 153s (0.82s/part).

Every part in the corpus is innocent, so **any BLOCK is a hard false positive and any REVIEW is a soft false positive.**

## Headline (held-out half, shipped default rules)

- Parts: **93**
- PASS 72 / REVIEW 12 / BLOCK 9
- **Hard FP rate (BLOCK): 9.7%**
- **Soft FP rate (REVIEW): 12.9%**
- Should-flag control `control_abstract_bore_block`: **BLOCK** (bore 8.99mm (caliber band 9.0) with L/D 16.7 and length 150.0mm and stepped profile (8.99, 10.99 mm))

## Rule posture comparison

| ruleset | split | n | PASS | REVIEW | BLOCK | hard FP | soft FP | any flag | control |
|---|---|---|---|---|---|---|---|---|---|
| single_signal | tune | 93 | 47 | 0 | 46 | 49.5% | 0.0% | 49.5% | BLOCK |
| single_signal | holdout | 93 | 47 | 0 | 46 | 49.5% | 0.0% | 49.5% | BLOCK |
| single_signal | all | 186 | 94 | 0 | 92 | 49.5% | 0.0% | 49.5% | BLOCK |
| v0_combination | tune | 93 | 73 | 12 | 8 | 8.6% | 12.9% | 21.5% | BLOCK |
| v0_combination | holdout | 93 | 71 | 13 | 9 | 9.7% | 14.0% | 23.7% | BLOCK |
| v0_combination | all | 186 | 144 | 25 | 17 | 9.1% | 13.4% | 22.6% | BLOCK |
| v1_combination | tune | 93 | 76 | 9 | 8 | 8.6% | 9.7% | 18.3% | BLOCK |
| v1_combination | holdout | 93 | 72 | 12 | 9 | 9.7% | 12.9% | 22.6% | BLOCK |
| v1_combination | all | 186 | 148 | 21 | 17 | 9.1% | 11.3% | 20.4% | BLOCK |
| v1_review_only | tune | 93 | 76 | 17 | 0 | 0.0% | 18.3% | 18.3% | REVIEW |
| v1_review_only | holdout | 93 | 72 | 21 | 0 | 0.0% | 22.6% | 22.6% | REVIEW |
| v1_review_only | all | 186 | 148 | 38 | 0 | 0.0% | 20.4% | 20.4% | REVIEW |

`single_signal` = any bore in a caliber band is flagged (BLOCK). `v0_combination` = combination rules as first written. `v1_combination` = shipped default: identical except `ld_stepped_review: 3.0`, the one adjustment, chosen by looking at the **tune** half only. `v1_review_only` = v1 with `geometry_can_block: false`: the same flags, but a full-signal match is a PRIORITY REVIEW instead of a BLOCK.

## Per category (held-out half)

| category | n | single-signal flags | v0 REVIEW | v0 BLOCK | v1 REVIEW | v1 BLOCK |
|---|---|---|---|---|---|---|
| bracket | 10 | 3 | 0 | 0 | 0 | 0 |
| combo | 6 | 3 | 2 | 0 | 2 | 0 |
| gear | 5 | 3 | 0 | 0 | 0 | 0 |
| knob | 5 | 2 | 0 | 0 | 0 | 0 |
| long_thin_tube | 10 | 7 | 5 | 1 | 5 | 1 |
| pin_rod | 6 | 0 | 0 | 0 | 0 | 0 |
| plate | 7 | 4 | 0 | 0 | 0 | 0 |
| spool | 4 | 1 | 0 | 0 | 0 | 0 |
| stepped_bore | 10 | 4 | 4 | 0 | 3 | 0 |
| triple_signal_legit | 8 | 8 | 0 | 8 | 0 | 8 |
| tube_in_band | 10 | 10 | 1 | 0 | 1 | 0 |
| tube_other | 6 | 0 | 0 | 0 | 0 | 0 |
| vessel | 6 | 1 | 1 | 0 | 1 | 0 |

## Every non-PASS legit part (shipped default rules, both halves)

| split | file | category | verdict | reasons |
|---|---|---|---|---|
| holdout | `long_thin_tube__flute_body_13.stl` | long_thin_tube | **BLOCK** | bore 7.79mm (caliber band 7.62) with L/D 28.4 and length 220.8mm and stepped profile (7.79, 10.69 mm) |
| holdout | `triple_signal_legit__dropper_pipette_10.stl` | triple_signal_legit | **BLOCK** | bore 9.07mm (caliber band 9.0) with L/D 15.5 and length 140.3mm and stepped profile (9.07, 2.00 mm) |
| holdout | `triple_signal_legit__pen_barrel_tip_00.stl` | triple_signal_legit | **BLOCK** | bore 5.48mm (caliber band 5.56) with L/D 16.9 and length 92.7mm and stepped profile (3.69, 5.48 mm) |
| holdout | `triple_signal_legit__pen_barrel_tip_04.3mf` | triple_signal_legit | **BLOCK** | bore 8.89mm (caliber band 9.0) with L/D 25.8 and length 229.7mm and stepped profile (3.73, 8.89 mm) |
| holdout | `triple_signal_legit__pen_barrel_tip_08.stl` | triple_signal_legit | **BLOCK** | bore 7.51mm (caliber band 7.62) with L/D 16.0 and length 120.1mm and stepped profile (2.81, 7.51 mm) |
| holdout | `triple_signal_legit__pen_barrel_tip_12.stl` | triple_signal_legit | **BLOCK** | bore 11.29mm (caliber band 11.43) with L/D 20.6 and length 232.4mm and stepped profile (2.81, 11.29 mm) |
| holdout | `triple_signal_legit__recorder_body_01.stl` | triple_signal_legit | **BLOCK** | bore 11.41mm (caliber band 11.43) with L/D 24.1 and length 274.5mm and stepped profile (11.41, 14.41 mm) |
| holdout | `triple_signal_legit__recorder_body_05.stl` | triple_signal_legit | **BLOCK** | bore 9.10mm (caliber band 9.0) with L/D 16.9 and length 153.6mm and stepped profile (9.10, 12.10 mm) |
| holdout | `triple_signal_legit__telescoping_sleeve_03.stl` | triple_signal_legit | **BLOCK** | bore 5.59mm (caliber band 5.56) with L/D 18.1 and length 101.5mm and stepped profile (5.59, 9.60 mm) |
| holdout | `combo__multi_body_kit_02.3mf` | combo | **REVIEW** | body 0: bore 11.45mm (caliber band 11.43) with L/D 8.2 and length 94.1mm |
| holdout | `combo__multi_body_kit_11.3mf` | combo | **REVIEW** | body 0: bore 7.50mm (caliber band 7.62) with L/D 24.2 and length 181.8mm |
| holdout | `long_thin_tube__antenna_tube_01.stl` | long_thin_tube | **REVIEW** | bore 7.78mm (caliber band 7.62) with L/D 31.5 and length 245.1mm |
| holdout | `long_thin_tube__antenna_tube_11.stl` | long_thin_tube | **REVIEW** | bore 11.60mm (caliber band 11.43) with L/D 24.9 and length 288.4mm |
| holdout | `long_thin_tube__curtain_rod_sleeve_17.stl` | long_thin_tube | **REVIEW** | bore 8.88mm (caliber band 9.0) with L/D 24.2 and length 214.7mm |
| holdout | `long_thin_tube__straw_long_09.3mf` | long_thin_tube | **REVIEW** | bore 9.09mm (caliber band 9.0) with L/D 10.3 and length 94.0mm |
| holdout | `long_thin_tube__straw_long_19.3mf` | long_thin_tube | **REVIEW** | bore 7.74mm (caliber band 7.62) with L/D 31.9 and length 247.1mm |
| holdout | `stepped_bore__counterbored_spacer_13.stl` | stepped_bore | **REVIEW** | bore 5.65mm (caliber band 5.56) with L/D 4.8 and length 27.0mm and stepped profile (10.20, 5.65 mm) |
| holdout | `stepped_bore__nozzle_adapter_07.stl` | stepped_bore | **REVIEW** | bore 5.40mm (caliber band 5.56) with L/D 11.9 and length 64.1mm and stepped profile (18.52, 5.40, 3.29 mm) |
| holdout | `stepped_bore__plumbing_reducer_16.stl` | stepped_bore | **REVIEW** | bore 7.50mm (caliber band 7.62) with L/D 3.7 and length 27.5mm and stepped profile (16.59, 7.50 mm) |
| holdout | `tube_in_band__bushing_band_03.stl` | tube_in_band | **REVIEW** | bore 5.57mm (caliber band 5.56) with L/D 11.1 and length 61.6mm |
| holdout | `vessel__test_tube_rack_cell_03.stl` | vessel | **REVIEW** | bore 9.19mm (caliber band 9.0) with L/D 8.0 and length 73.8mm |
| tune | `triple_signal_legit__dropper_pipette_02.stl` | triple_signal_legit | **BLOCK** | bore 11.37mm (caliber band 11.43) with L/D 23.1 and length 262.6mm and stepped profile (11.37, 2.00 mm) |
| tune | `triple_signal_legit__dropper_pipette_06.stl` | triple_signal_legit | **BLOCK** | bore 5.55mm (caliber band 5.56) with L/D 23.0 and length 127.8mm and stepped profile (5.55, 2.00 mm) |
| tune | `triple_signal_legit__dropper_pipette_14.3mf` | triple_signal_legit | **BLOCK** | bore 11.30mm (caliber band 11.43) with L/D 20.9 and length 235.9mm and stepped profile (11.30, 2.00 mm) |
| tune | `triple_signal_legit__recorder_body_09.3mf` | triple_signal_legit | **BLOCK** | bore 11.50mm (caliber band 11.43) with L/D 22.5 and length 258.3mm and stepped profile (11.50, 14.50 mm) |
| tune | `triple_signal_legit__recorder_body_13.stl` | triple_signal_legit | **BLOCK** | bore 5.64mm (caliber band 5.56) with L/D 32.4 and length 182.6mm and stepped profile (5.64, 8.64 mm) |
| tune | `triple_signal_legit__telescoping_sleeve_07.stl` | triple_signal_legit | **BLOCK** | bore 11.48mm (caliber band 11.43) with L/D 26.3 and length 302.1mm and stepped profile (11.48, 16.34 mm) |
| tune | `triple_signal_legit__telescoping_sleeve_11.stl` | triple_signal_legit | **BLOCK** | bore 8.98mm (caliber band 9.0) with L/D 24.2 and length 216.9mm and stepped profile (8.98, 13.00 mm) |
| tune | `triple_signal_legit__telescoping_sleeve_15.stl` | triple_signal_legit | **BLOCK** | bore 5.52mm (caliber band 5.56) with L/D 27.1 and length 149.7mm and stepped profile (5.52, 10.84 mm) |
| tune | `combo__multi_body_kit_05.3mf` | combo | **REVIEW** | body 0: bore 7.62mm (caliber band 7.62) with L/D 18.1 and length 138.1mm |
| tune | `combo__multi_body_kit_08.3mf` | combo | **REVIEW** | body 0: bore 5.64mm (caliber band 5.56) with L/D 12.3 and length 69.2mm |
| tune | `long_thin_tube__antenna_tube_16.stl` | long_thin_tube | **REVIEW** | bore 5.51mm (caliber band 5.56) with L/D 20.6 and length 113.5mm |
| tune | `long_thin_tube__pen_barrel_05.stl` | long_thin_tube | **REVIEW** | bore 7.63mm (caliber band 7.62) with L/D 34.5 and length 263.2mm |
| tune | `stepped_bore__counterbored_spacer_09.3mf` | stepped_bore | **REVIEW** | bore 9.06mm (caliber band 9.0) with L/D 4.5 and length 40.5mm and stepped profile (13.75, 9.06 mm) |
| tune | `stepped_bore__nozzle_adapter_11.stl` | stepped_bore | **REVIEW** | bore 5.38mm (caliber band 5.56) with L/D 11.5 and length 62.1mm and stepped profile (17.93, 5.38, 3.53 mm) |
| tune | `stepped_bore__plumbing_reducer_00.stl` | stepped_bore | **REVIEW** | bore 7.72mm (caliber band 7.62) with L/D 7.4 and length 57.0mm and stepped profile (7.72, 11.72 mm) |
| tune | `stepped_bore__plumbing_reducer_04.3mf` | stepped_bore | **REVIEW** | bore 11.44mm (caliber band 11.43) with L/D 4.5 and length 51.0mm and stepped profile (11.44, 5.53 mm) |
| tune | `vessel__test_tube_rack_cell_11.stl` | vessel | **REVIEW** | bore 5.47mm (caliber band 5.56) with L/D 13.5 and length 73.8mm |

### Changed by the v0 -> v1 adjustment

| split | file | v0 | v1 | v0 reason |
|---|---|---|---|---|
| holdout | `stepped_bore__plumbing_reducer_08.stl` | REVIEW | PASS | bore 7.48mm (caliber band 7.62) with L/D 2.5 and length 44.2mm and stepped profile (7.48, 18.07 mm) |
| tune | `stepped_bore__bearing_housing_10.stl` | REVIEW | PASS | bore 7.61mm (caliber band 7.62) with L/D 1.6 and length 24.8mm and stepped profile (15.99, 7.61, 15.99 mm) |
| tune | `stepped_bore__bearing_housing_14.3mf` | REVIEW | PASS | bore 11.52mm (caliber band 11.43) with L/D 0.7 and length 19.0mm and stepped profile (27.98, 11.52, 27.98 mm) |
| tune | `stepped_bore__counterbored_spacer_01.stl` | REVIEW | PASS | bore 9.16mm (caliber band 9.0) with L/D 1.3 and length 11.5mm and stepped profile (15.01, 9.16 mm) |

## Detector sanity check (is the low FP rate real or just missed bores?)

For the 68 tube parts whose main bore diameter the generator knows, the detector found a bore within 0.3 mm of the true diameter in **68/68** (100.0%).

This includes 4 band tubes exported at a random tilt (found via the principal axis).

## Assessment

*Hand-written (`reports/assessment.md`); the generator appends it verbatim. The numbers quoted here come from the run above.*

**Bottom line: geometry signals alone can't push the BLOCK false-positive rate to near zero.** They work as a screen that sorts files into PASS and REVIEW. A geometry-only BLOCK needs a second layer behind it (provenance, a near-duplicate match against known-bad files, a model, or a human).

### What trips the rules (held-out half, shipped rules)

1. **`triple_signal_legit`: 8/8 BLOCK.** Pen barrels with a writing-tip step, recorder bodies with a joint socket, dropper/pipette tubes, and telescoping sleeves. A long, stepped, in-band bore is exactly what these objects are. At the level of "a cylindrical hole with a diameter profile" they are indistinguishable from the abstract control, and the control BLOCKs for the same three reasons. No threshold separates them. Moving `ld_block` or the band tolerance trades these FPs for misses one-for-one.
2. **`long_thin_tube`: 6/10 flagged** (5 REVIEW, 1 BLOCK). Antenna tubes, curtain-rod sleeves and long straws with an in-band ID clear `ld_review`. The BLOCK is `flute_body_13`, whose bore is long, in band and socketed.
3. **`stepped_bore`: 3/10 REVIEW.** Plumbing reducers, nozzle adapters and counterbored spacers whose narrow section falls in a band and which are 3+ diameters long.

Combos follow the same pattern (2/6 REVIEW: a long in-band tube inside a multi-body kit). Brackets, plates, gears, knobs, spools, pins and other tubes never get past PASS, even though many have in-band holes. That is where combination logic pays off.

### What the combination logic buys

The naive single-signal rule ("any bore in a caliber band") flags **49.5%** of the held-out legit parts. Combination logic cuts the total flag rate to **22.6%**, with a **9.7% BLOCK** rate. Every BLOCK comes from a part that really has all three signals. The corpus is deliberately band-heavy (about half of every tube-like category has an in-band ID on purpose), so these rates describe a stress test, not real-world upload traffic. On a realistic upload mix I would expect the flag rate to be much lower. That's unmeasured, so treat it as a guess.

### Changes made during this pass (disclosed)

- **One threshold adjustment, chosen by looking at the tune half only:** `ld_stepped_review: 3.0`. A stepped bore now corroborates a caliber match only when the bore is at least 3 diameters long. The aim was to stop flagging short counterbores and bearing seats. Effect: tune-half REVIEW went from 12 to 9, and the held-out half from 13 to 12 (one plumbing reducer, L/D 2.5). BLOCK is unaffected. The before/after table above lists every part that changed.
- **One detector fix, made for correctness rather than for FP rate:** collinear bore pieces of the same diameter, split by a cross-hole, are now merged (`merge_gap_diameters: 2.0`). Before the fix, `flute_body_13` measured 69 mm of a 221 mm bore, because its tone holes broke the chain. That fix *increased* FPs (the flute went from REVIEW to BLOCK). It also closes an obvious evasion: cross-drilling a bore to hide its length.
- **The corpus got harder after the first run.** The first report (170 parts, before the fix) showed **0 BLOCK / 15.3% REVIEW** on held-out. That zero was an artifact: almost no legit part carried all three signals, and only by chance. I appended a 16-part `triple_signal_legit` category (the original 170 parts are byte-identical under the same seed) specifically to stress the BLOCK rule. I did not tune any threshold toward zero BLOCK, which would only have overfit the rules to my own corpus.

### Recommendation

Run with `geometry_can_block: false` until a second layer exists. In that posture a full-signal match becomes a **PRIORITY REVIEW**, and only the exact-match geohash blocklist BLOCKs. Held-out results in that posture: **0.0% BLOCK, 22.6% REVIEW** (the same files are flagged, just none are auto-rejected). The control still goes red (REVIEW, marked PRIORITY). With the default (`true`), roughly 1 in 10 innocent long stepped tubes in this stress corpus gets hard-rejected.

### Detector limits that bias these numbers

- The 100% bore recall (68/68 known main bores) covers axis-aligned tubes and a few tilted ones found through the principal axis. A bore tilted away from every world and principal axis is measured as an ellipse. Measured: a 9.0 mm hole reads 9.15 mm at 15° and 9.28 mm at 20° (so it falls out of the ±0.3 band past roughly 15–18°), and it is **missed entirely** past ~20°. A bore that breaks out of the surface (an open channel) is also missed. Misses lower the FP rate and the true-positive rate together, so a low FP rate on oddly oriented parts is not evidence of precision.
- Holes with 7 or fewer facets fail the circularity test (measured: 6- and 7-gon rejected, 8-gon accepted). That rejects hex/square holes on purpose, but a deliberately coarse polygonal bore would slip past. That evasion should be closed in Phase 2 (for example, inscribed-circle fitting on polygonal rings).
- The external shape is not used at all. That keeps the engine generic, and it is also why it can't tell a pen from anything else with the same bore.

### Geohash (Layer 1) note

Across the 186 corpus parts there are 184 distinct geohashes. The two collisions are real near-duplicates, not random clashes: two solid rods whose length/diameter ratios differ by 0.2% (11.13 vs 11.15), and two thin tubes (L/D 19.8 vs 20.0, ID/OD ratio within 1%). The hash is scale-invariant and quantized to 3 decimals, so shapes whose proportions agree to about 1% hash identically. For an exact-match blocklist that is mostly harmless. It does mean **never blocklist a plain primitive** (a bare tube, rod or box), because every proportionally similar innocent part would BLOCK.
