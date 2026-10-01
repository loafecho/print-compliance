"""Generate the legitimate-parts corpus (false-positive floor) + the abstract control.

    uv run python corpus/generate_legit.py            # writes corpus/legit/{tune,holdout}/ + manifest
    uv run python corpus/generate_legit.py --seed 7

Every part is an innocent, everyday object built from trimesh/shapely primitives.
The corpus is DELIBERATELY HARD: many tubes have inner diameters inside the configured
caliber bands, many are long and thin, and many have stepped bores, because the point
is to find where the rules produce false positives.

The corpus is split per category into a tuning half and a held-out half (fixed seed).
Thresholds may only be adjusted against `tune/`; `holdout/` is for reporting.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pce import shapes  # noqa: E402

HERE = Path(__file__).resolve().parent
BANDS = [5.56, 7.62, 9.0, 11.43]  # mirrors the default config; used to make the corpus hard


def band_d(rng, jitter=0.2):
    return float(rng.choice(BANDS) + rng.uniform(-jitter, jitter))


def other_d(rng, lo=3.0, hi=30.0):
    while True:
        d = float(rng.uniform(lo, hi))
        if all(abs(d - b) > 0.6 for b in BANDS):
            return d


def maybe_band(rng, p=0.5, lo=3.0, hi=30.0):
    return band_d(rng) if rng.random() < p else other_d(rng, lo, hi)


# ------------------------------------------------------------------ categories
def l_brackets(rng, n):
    for i in range(n):
        a, b = rng.uniform(20, 70, 2)
        yield f"l_bracket_{i:02d}", "bracket", shapes.l_bracket(
            a, b, rng.uniform(10, 30), rng.uniform(3, 6), hole_d=maybe_band(rng, 0.3, 3, 8))


def shelf_brackets(rng, n):
    for i in range(n):
        a = rng.uniform(40, 120)
        t = rng.uniform(4, 8)
        w = rng.uniform(15, 30)
        m = shapes.l_bracket(a, a * rng.uniform(0.7, 1.0), w, t)
        gus = shapes.extrude(Polygon([(t, t), (a * 0.7, t), (t, a * 0.6)]), t)
        gus.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        gus.apply_translation([0, -w / 2 + t / 2, 0])
        m = m.union(gus)
        hd = maybe_band(rng, 0.3, 3.5, 8)
        m = shapes.drill(m, hd, 3 * t, (a * 0.85, -w / 2, t / 2), axis="z")
        yield f"shelf_bracket_{i:02d}", "bracket", m


def hole_plates(rng, n):
    for i in range(n):
        w, h = rng.uniform(30, 150, 2)
        t = rng.uniform(2, 12)
        d = maybe_band(rng, 0.5, 3, 12)
        nx, ny = int(rng.integers(1, 5)), int(rng.integers(1, 4))
        xs = np.linspace(-w / 2 + d * 1.5, w / 2 - d * 1.5, nx)
        ys = np.linspace(-h / 2 + d * 1.5, h / 2 - d * 1.5, ny)
        centers = [(x, y) for x in xs for y in ys]
        yield f"hole_plate_{i:02d}", "plate", shapes.plate_with_holes(w, h, t, centers, d)


def pins_rods(rng, n):
    for i in range(n):
        d = maybe_band(rng, 0.5, 2, 16)
        L = rng.uniform(10, 250)
        kind = ["dowel", "pin", "rod"][i % 3]
        yield f"{kind}_{i:02d}", "pin_rod", shapes.cylinder_z(d, L)


def band_tubes(rng, n):
    names = ["straw", "pipe_spacer", "standoff", "bushing"]
    for i in range(n):
        idd = band_d(rng)
        wall = rng.uniform(0.8, 4)
        L = rng.uniform(5, 70)
        m = shapes.stepped_tube([(L, idd / 2, idd / 2 + wall)])
        if i % 5 == 0:  # some exported tilted
            m.apply_transform(trimesh.transformations.random_rotation_matrix(rng.random(3)))
        yield f"{names[i % 4]}_band_{i:02d}", "tube_in_band", m, {"expect_d": idd}


def general_tubes(rng, n):
    for i in range(n):
        idd = other_d(rng, 3, 40)
        wall = rng.uniform(1, 5)
        L = rng.uniform(5, 120)
        yield f"tube_{i:02d}", "tube_other", shapes.stepped_tube([(L, idd / 2, idd / 2 + wall)]), {"expect_d": idd}


def long_thin_tubes(rng, n):
    kinds = ["pen_barrel", "antenna_tube", "curtain_rod_sleeve", "flute_body", "straw_long"]
    for i in range(n):
        kind = kinds[i % len(kinds)]
        idd = maybe_band(rng, 0.5, 4, 22)
        wall = rng.uniform(1, 3)
        L = idd * rng.uniform(10, 35)
        if kind == "pen_barrel" and i % 2 == 0:
            # tapered writing tip: a narrow section at one end (stepped bore)
            tip = rng.uniform(2.5, 4.0)
            m = shapes.stepped_tube([(rng.uniform(8, 15), tip / 2, idd / 2 + wall),
                                     (L, idd / 2, idd / 2 + wall)])
        elif kind == "flute_body":
            # plain bore + perpendicular tone holes; some with a wider socket at one end
            segs = [(L, idd / 2, idd / 2 + wall)]
            if i % 2 == 1:
                segs.append((rng.uniform(15, 30), idd / 2 + wall * 0.6, idd / 2 + wall * 1.8))
            m = shapes.stepped_tube(segs)
            for k in range(6):
                m = shapes.drill(m, rng.uniform(3, 7), idd + 4 * wall,
                                 (0, idd / 2 + wall, L * (0.35 + 0.08 * k)), axis="y")
        else:
            m = shapes.stepped_tube([(L, idd / 2, idd / 2 + wall)])
        yield f"{kind}_{i:02d}", "long_thin_tube", m, {"expect_d": idd}


def stepped_bores(rng, n):
    kinds = ["plumbing_reducer", "counterbored_spacer", "bearing_housing", "nozzle_adapter"]
    for i in range(n):
        kind = kinds[i % 4]
        if kind == "plumbing_reducer":
            d1, d2 = maybe_band(rng, 0.5, 6, 30), maybe_band(rng, 0.4, 6, 30)
            if abs(d1 - d2) < 2:
                d2 = d1 + 4
            od = max(d1, d2) + rng.uniform(3, 8)
            segs = [(rng.uniform(10, 30), d1 / 2, od / 2), (rng.uniform(10, 30), d2 / 2, od / 2)]
        elif kind == "counterbored_spacer":
            d = maybe_band(rng, 0.5, 3, 12)
            cb = d + rng.uniform(3, 6)
            od = cb + rng.uniform(3, 8)
            segs = [(rng.uniform(3, 8), cb / 2, od / 2), (rng.uniform(5, 40), d / 2, od / 2)]
        elif kind == "bearing_housing":
            bearing = float(rng.choice([16, 19, 22, 26, 28]))
            shaft = maybe_band(rng, 0.5, 5, 14)
            od = bearing + rng.uniform(6, 12)
            segs = [(rng.uniform(5, 9), bearing / 2, od / 2), (rng.uniform(3, 10), shaft / 2, od / 2),
                    (rng.uniform(5, 9), bearing / 2, od / 2)]
        else:  # nozzle adapter: three steps narrowing
            d1 = rng.uniform(14, 25)
            d2 = maybe_band(rng, 0.6, 6, 13)
            d3 = rng.uniform(2, 4.5)
            od = d1 + rng.uniform(3, 6)
            segs = [(rng.uniform(8, 20), d1 / 2, od / 2), (rng.uniform(10, 60), d2 / 2, od / 2),
                    (rng.uniform(4, 10), d3 / 2, od / 2 * 0.6)]
        yield f"{kind}_{i:02d}", "stepped_bore", shapes.stepped_tube(segs)


def vessels(rng, n):
    for i in range(n):
        kind = ["cup", "vase", "pen_holder", "test_tube_rack_cell"][i % 4]
        if kind == "vase":
            H = rng.uniform(60, 200)
            R = rng.uniform(15, 50)
            wall = rng.uniform(1.5, 3)
            zs = np.linspace(0, H, 40)
            r = R * (0.7 + 0.3 * np.sin(zs / H * np.pi * rng.uniform(1, 2.5)) + 0.15)
            base = 3.0
            outer = [(float(a), float(z)) for a, z in zip(r, zs)]
            inner = [(float(a - wall), float(z)) for a, z in zip(r, zs) if z >= base][::-1]
            prof = [(0.0, 0.0)] + outer + inner + [(0.0, base)]
            m = shapes.revolve_profile(prof)
        else:
            if kind == "test_tube_rack_cell":
                inner_d = maybe_band(rng, 0.7, 8, 20)  # narrow blind holes, sometimes in band
                H = rng.uniform(30, 120)
            else:
                inner_d = rng.uniform(40, 90)
                H = rng.uniform(60, 130)
            wall = rng.uniform(1.5, 4)
            base = rng.uniform(2, 5)
            m = shapes.stepped_tube([(base, 0.0, inner_d / 2 + wall), (H, inner_d / 2, inner_d / 2 + wall)])
        yield f"{kind}_{i:02d}", "vessel", m


def spools(rng, n):
    for i in range(n):
        bore = maybe_band(rng, 0.4, 5, 55)
        hub = bore / 2 + rng.uniform(3, 15)
        fl = hub + rng.uniform(15, 60)
        f_t, w = rng.uniform(2, 5), rng.uniform(15, 70)
        m = shapes.stepped_tube([(f_t, bore / 2, fl), (w, bore / 2, hub), (f_t, bore / 2, fl)])
        yield f"spool_{i:02d}", "spool", m


def gears(rng, n):
    for i in range(n):
        teeth = int(rng.integers(10, 48))
        R = rng.uniform(10, 50)
        h = R * rng.uniform(0.06, 0.12)
        th = np.linspace(0, 2 * np.pi, teeth * 16, endpoint=False)
        phase = (th * teeth / (2 * np.pi)) % 1.0
        r = np.where(phase < 0.5, R + h, R)
        outline = Polygon(np.c_[r * np.cos(th), r * np.sin(th)])
        bore = maybe_band(rng, 0.5, 3, R * 0.6)
        poly = outline.difference(shapes.regular_polygon(0, 0, bore, 64))
        m = shapes.extrude(poly, rng.uniform(4, 15))
        if i % 3 == 0:  # gear with a hub
            hub = shapes.stepped_tube([(rng.uniform(5, 12), bore / 2, bore / 2 + rng.uniform(3, 6))])
            hub.apply_translation([0, 0, m.bounds[1][2] - 0.5])
            m = m.union(hub)
        yield f"gear_{i:02d}", "gear", m


def knobs(rng, n):
    for i in range(n):
        R = rng.uniform(8, 25)
        H = rng.uniform(10, 30)
        shaft = maybe_band(rng, 0.4, 3, 8)
        depth = rng.uniform(5, H - 3)
        prof = [(shaft / 2, 0.0), (R, 0.0), (R, H * 0.7), (R * 0.8, H), (0.0, H),
                (0.0, depth), (shaft / 2, depth)]
        sections = 12 if i % 4 == 0 else 64  # some low-poly knurled-looking knobs
        yield f"knob_{i:02d}", "knob", shapes.revolve_profile(prof, sections=sections)


def combos(rng, n):
    for i in range(n):
        kind = ["flanged_tube", "bracket_with_bushing", "multi_body_kit"][i % 3]
        if kind == "flanged_tube":
            idd = maybe_band(rng, 0.5, 5, 25)
            wall = rng.uniform(1.5, 3)
            L = rng.uniform(20, 160)
            fl = idd / 2 + wall + rng.uniform(6, 15)
            m = shapes.stepped_tube([(rng.uniform(2, 5), idd / 2, fl), (L, idd / 2, idd / 2 + wall)])
            m = [m]
        elif kind == "bracket_with_bushing":
            a = rng.uniform(30, 60)
            t = rng.uniform(4, 6)
            w = rng.uniform(15, 25)
            br = shapes.l_bracket(a, a * 0.8, w, t)
            idd = maybe_band(rng, 0.6, 4, 12)
            L = rng.uniform(10, 40)
            bush = shapes.stepped_tube([(L, idd / 2, idd / 2 + rng.uniform(2, 4))])
            bush.apply_translation([a * 0.6, -w / 2, 0])
            br = shapes.drill(br, idd, 3 * t, (a * 0.6, -w / 2, t / 2), axis="z")
            m = [br.union(bush)]
        else:
            idd = maybe_band(rng, 0.7, 4, 12)
            tube = shapes.stepped_tube([(rng.uniform(40, 200), idd / 2, idd / 2 + rng.uniform(1, 2.5))])
            plate = shapes.plate_with_holes(40, 30, 3, [(-10, 0), (10, 0)], 4.0)
            plate.apply_translation([40, 0, 0])
            m = [tube, plate]
        yield f"{kind}_{i:02d}", "combo", m


def triple_signal(rng, n):
    """Legit parts that carry ALL THREE combination signals at once: an in-band bore,
    long (L/D >= 12), and stepped. Added after the first report showed the corpus only
    had such parts by chance; these stress the BLOCK rule directly."""
    kinds = ["pen_barrel_tip", "recorder_body", "dropper_pipette", "telescoping_sleeve"]
    for i in range(n):
        kind = kinds[i % 4]
        idd = band_d(rng, 0.15)
        wall = rng.uniform(1.2, 3)
        L = idd * rng.uniform(13, 30)
        if kind == "pen_barrel_tip":
            tip = rng.uniform(2.5, 4.0)
            segs = [(rng.uniform(8, 15), tip / 2, idd / 2 + wall), (L, idd / 2, idd / 2 + wall)]
        elif kind == "recorder_body":
            # a wider joint socket at one end; tone holes added below
            segs = [(L, idd / 2, idd / 2 + wall), (rng.uniform(15, 25), idd / 2 + 1.5, idd / 2 + wall + 2)]
        elif kind == "dropper_pipette":
            segs = [(L, idd / 2, idd / 2 + wall), (rng.uniform(15, 30), 1.0, 2.5)]
        else:  # telescoping sleeve: one section slides into the next
            segs = [(L * 0.6, idd / 2, idd / 2 + wall), (L * 0.6, idd / 2 + wall + 0.3, idd / 2 + 2 * wall + 0.3)]
        m = shapes.stepped_tube(segs)
        if kind == "recorder_body":
            for k in range(5):
                m = shapes.drill(m, rng.uniform(3, 6), idd + 4 * wall,
                                 (0, idd / 2 + wall, L * (0.3 + 0.1 * k)), axis="y")
        yield f"{kind}_{i:02d}", "triple_signal_legit", m, {"expect_d": idd}


PLAN = [
    (l_brackets, 12), (shelf_brackets, 8), (hole_plates, 14), (pins_rods, 12),
    (band_tubes, 20), (general_tubes, 12), (long_thin_tubes, 20), (stepped_bores, 20),
    (vessels, 12), (spools, 8), (gears, 10), (knobs, 10), (combos, 12),
    # appended (not inserted) so the parts above keep identical random draws
    (triple_signal, 16),
]


def _export(meshes, path: Path):
    if len(meshes) == 1 and path.suffix == ".stl":
        meshes[0].export(path)
    else:
        scene = trimesh.Scene()
        for k, m in enumerate(meshes):
            scene.add_geometry(m, geom_name=f"body{k}")
        scene.export(path)


def generate(out: Path, seed: int = 20260922, limit: int | None = None) -> list[dict]:
    rng = np.random.default_rng(seed)
    split_rng = np.random.default_rng(seed + 1)
    manifest = []
    for fn, n in PLAN:
        items = list(fn(rng, n if limit is None else min(n, limit)))
        order = split_rng.permutation(len(items))
        for rank, idx in enumerate(order):
            name, cat, mesh, *meta = items[idx]
            meta = meta[0] if meta else {}
            meshes = mesh if isinstance(mesh, list) else [mesh]
            split = "tune" if rank % 2 == 0 else "holdout"
            ext = ".3mf" if (len(meshes) > 1 or idx % 5 == 4) else ".stl"
            rel = Path(split) / f"{cat}__{name}{ext}"
            (out / split).mkdir(parents=True, exist_ok=True)
            _export(meshes, out / rel)
            manifest.append({"file": str(rel), "name": name, "category": cat, "split": split,
                             "watertight": all(m.is_watertight for m in meshes),
                             **{k: round(float(v), 3) for k, v in meta.items()}})
    manifest.sort(key=lambda r: r["file"])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def generate_control(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "control_abstract_bore_block.stl"
    shapes.control_abstract_bore_block().export(p)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260922)
    ap.add_argument("--out", default=str(HERE / "legit"))
    args = ap.parse_args()
    man = generate(Path(args.out), args.seed)
    generate_control(HERE / "control")
    cats: dict[str, int] = {}
    for r in man:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    print(f"wrote {len(man)} legit parts to {args.out} ({sum(r['split'] == 'holdout' for r in man)} held out)")
    print("non-watertight:", [r["file"] for r in man if not r["watertight"]])
    for c, k in sorted(cats.items()):
        print(f"  {c:16s} {k}")


if __name__ == "__main__":
    main()
