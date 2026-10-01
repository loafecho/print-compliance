# False-positive floor report: Phase 1 functional-geometry rules

Generated 2026-10-01 by `reports/make_fp_report.py`. Corpus: 170 programmatically generated legitimate parts (`corpus/generate_legit.py`, seed 20260922), split per category into 85 tune / 85 held-out. Feature extraction took 145s (0.85s/part).

Every part in the corpus is innocent, so **any BLOCK is a hard false positive and any REVIEW is a soft false positive.**

## Headline (held-out half, shipped default rules)

- Parts: **85**
- PASS 72 / REVIEW 13 / BLOCK 0
- **Hard FP rate (BLOCK): 0.0%**
- **Soft FP rate (REVIEW): 15.3%**
- Should-flag control `control_abstract_bore_block`: **BLOCK** (bore 8.99mm (caliber band 9.0) with L/D 16.7 and length 150.0mm and stepped profile (8.99, 10.99 mm))

## Rule posture comparison

| ruleset | split | n | PASS | REVIEW | BLOCK | hard FP | soft FP | any flag | control |
|---|---|---|---|---|---|---|---|---|---|
| single_signal | tune | 85 | 47 | 0 | 38 | 44.7% | 0.0% | 44.7% | BLOCK |
| single_signal | holdout | 85 | 47 | 0 | 38 | 44.7% | 0.0% | 44.7% | BLOCK |
| single_signal | all | 170 | 94 | 0 | 76 | 44.7% | 0.0% | 44.7% | BLOCK |
| v0_combination | tune | 85 | 73 | 12 | 0 | 0.0% | 14.1% | 14.1% | BLOCK |
| v0_combination | holdout | 85 | 71 | 14 | 0 | 0.0% | 16.5% | 16.5% | BLOCK |
| v0_combination | all | 170 | 144 | 26 | 0 | 0.0% | 15.3% | 15.3% | BLOCK |
| v1_combination | tune | 85 | 76 | 9 | 0 | 0.0% | 10.6% | 10.6% | BLOCK |
| v1_combination | holdout | 85 | 72 | 13 | 0 | 0.0% | 15.3% | 15.3% | BLOCK |
| v1_combination | all | 170 | 148 | 22 | 0 | 0.0% | 12.9% | 12.9% | BLOCK |

`single_signal` = any bore in a caliber band is flagged (BLOCK). `v0_combination` = combination rules as first written. `v1_combination` = shipped default: identical except `ld_stepped_review: 3.0`, the one adjustment, chosen by looking at the **tune** half only.

## Per category (held-out half)

| category | n | single-signal flags | v0 REVIEW | v0 BLOCK | v1 REVIEW | v1 BLOCK |
|---|---|---|---|---|---|---|
| bracket | 10 | 3 | 0 | 0 | 0 | 0 |
| combo | 6 | 3 | 2 | 0 | 2 | 0 |
| gear | 5 | 3 | 0 | 0 | 0 | 0 |
| knob | 5 | 2 | 0 | 0 | 0 | 0 |
| long_thin_tube | 10 | 7 | 6 | 0 | 6 | 0 |
| pin_rod | 6 | 0 | 0 | 0 | 0 | 0 |
| plate | 7 | 4 | 0 | 0 | 0 | 0 |
| spool | 4 | 1 | 0 | 0 | 0 | 0 |
| stepped_bore | 10 | 4 | 4 | 0 | 3 | 0 |
| tube_in_band | 10 | 10 | 1 | 0 | 1 | 0 |
| tube_other | 6 | 0 | 0 | 0 | 0 | 0 |
| vessel | 6 | 1 | 1 | 0 | 1 | 0 |

## Every non-PASS legit part (shipped default rules, both halves)

| split | file | category | verdict | reasons |
|---|---|---|---|---|
| holdout | `combo__multi_body_kit_02.3mf` | combo | **REVIEW** | body 0: bore 11.45mm (caliber band 11.43) with L/D 8.2 and length 94.1mm |
| holdout | `combo__multi_body_kit_11.3mf` | combo | **REVIEW** | body 0: bore 7.50mm (caliber band 7.62) with L/D 24.2 and length 181.8mm |
| holdout | `long_thin_tube__antenna_tube_01.stl` | long_thin_tube | **REVIEW** | bore 7.78mm (caliber band 7.62) with L/D 31.5 and length 245.1mm |
| holdout | `long_thin_tube__antenna_tube_11.stl` | long_thin_tube | **REVIEW** | bore 11.60mm (caliber band 11.43) with L/D 24.9 and length 288.4mm |
| holdout | `long_thin_tube__curtain_rod_sleeve_17.stl` | long_thin_tube | **REVIEW** | bore 8.88mm (caliber band 9.0) with L/D 24.2 and length 214.7mm |
| holdout | `long_thin_tube__flute_body_13.stl` | long_thin_tube | **REVIEW** | bore 7.79mm (caliber band 7.62) with L/D 8.9 and length 69.0mm and stepped profile (7.79, 10.69 mm) |
| holdout | `long_thin_tube__straw_long_09.3mf` | long_thin_tube | **REVIEW** | bore 9.09mm (caliber band 9.0) with L/D 10.3 and length 94.0mm |
| holdout | `long_thin_tube__straw_long_19.3mf` | long_thin_tube | **REVIEW** | bore 7.74mm (caliber band 7.62) with L/D 31.9 and length 247.1mm |
| holdout | `stepped_bore__counterbored_spacer_13.stl` | stepped_bore | **REVIEW** | bore 5.65mm (caliber band 5.56) with L/D 4.8 and length 27.0mm and stepped profile (10.20, 5.65 mm) |
| holdout | `stepped_bore__nozzle_adapter_07.stl` | stepped_bore | **REVIEW** | bore 5.40mm (caliber band 5.56) with L/D 11.9 and length 64.1mm and stepped profile (18.52, 5.40, 3.29 mm) |
| holdout | `stepped_bore__plumbing_reducer_16.stl` | stepped_bore | **REVIEW** | bore 7.50mm (caliber band 7.62) with L/D 3.7 and length 27.5mm and stepped profile (16.59, 7.50 mm) |
| holdout | `tube_in_band__bushing_band_03.stl` | tube_in_band | **REVIEW** | bore 5.57mm (caliber band 5.56) with L/D 11.1 and length 61.6mm |
| holdout | `vessel__test_tube_rack_cell_03.stl` | vessel | **REVIEW** | bore 9.19mm (caliber band 9.0) with L/D 8.0 and length 73.8mm |
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

For the 52 tube parts whose main bore diameter the generator knows, the detector found a bore within 0.3 mm of the true diameter in **52/52** (100.0%).

This includes 4 band tubes exported at a random tilt (found via the principal axis).

## Assessment

_(assessment pending)_
