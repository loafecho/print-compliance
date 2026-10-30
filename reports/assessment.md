*Hand-written (`reports/assessment.md`); the generator appends it verbatim. The numbers quoted here come from the run above.*

**Bottom line: geometry signals alone can't push the BLOCK false-positive rate to near zero.** They work as a screen that sorts files into PASS and REVIEW. A geometry-only BLOCK needs a second layer behind it (provenance, a near-duplicate match against known-bad files, a model, or a human).

### What trips the rules (held-out half, v1 rules with geometry BLOCK enabled)

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

Run with `geometry_can_block: false` until a second layer exists (this is now the shipped default). In that posture a full-signal match becomes a **PRIORITY REVIEW**, and only the exact-match geohash blocklist BLOCKs. Held-out results in that posture: **0.0% BLOCK, 22.6% REVIEW** (the same files are flagged, just none are auto-rejected). The control still goes red (REVIEW, marked PRIORITY). With `geometry_can_block: true`, roughly 1 in 10 innocent long stepped tubes in this stress corpus gets hard-rejected.

### Detector limits that bias these numbers

- The 100% bore recall (68/68 known main bores) covers axis-aligned tubes and a few tilted ones found through the principal axis. A bore tilted away from every world and principal axis is measured as an ellipse. Measured: a 9.0 mm hole reads 9.15 mm at 15° and 9.28 mm at 20° (so it falls out of the ±0.3 band past roughly 15–18°), and it is **missed entirely** past ~20°. A bore that breaks out of the surface (an open channel) is also missed. Misses lower the FP rate and the true-positive rate together, so a low FP rate on oddly oriented parts is not evidence of precision.
- Holes with 7 or fewer facets fail the circularity test (measured: 6- and 7-gon rejected, 8-gon accepted). That rejects hex/square holes on purpose, but a deliberately coarse polygonal bore would slip past. That evasion should be closed in Phase 2 (for example, inscribed-circle fitting on polygonal rings).
- The external shape is not used at all. That keeps the engine generic, and it is also why it can't tell a pen from anything else with the same bore.

### Geohash (Layer 1) note

Across the 186 corpus parts there are 184 distinct geohashes. The two collisions are real near-duplicates, not random clashes: two solid rods whose length/diameter ratios differ by 0.2% (11.13 vs 11.15), and two thin tubes (L/D 19.8 vs 20.0, ID/OD ratio within 1%). The hash is scale-invariant and quantized to 3 decimals, so shapes whose proportions agree to about 1% hash identically. For an exact-match blocklist that is mostly harmless. It does mean **never blocklist a plain primitive** (a bare tube, rod or box), because every proportionally similar innocent part would BLOCK.
