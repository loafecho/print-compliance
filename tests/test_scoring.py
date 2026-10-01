import copy

import pytest

from pce.features import caliber_match
from pce.scoring import score_file


def bore(d, length, stepped=False, cfg=None):
    return {
        "diameter_mm": d,
        "min_diameter_mm": d,
        "max_diameter_mm": d * (1.4 if stepped else 1.0),
        "length_mm": length,
        "ld_ratio": length / d,
        "stepped": stepped,
        "segments": [{"diameter_mm": d, "length_mm": length}],
        "caliber_match": caliber_match(d, cfg) if cfg else None,
    }


def body(bores, watertight=True):
    return {"watertight": watertight, "bores": bores, "rails": None}


def test_no_bores_pass(cfg):
    r = score_file([body([])], cfg)
    assert r["verdict"] == "PASS"
    assert r["reasons"] == []


def test_caliber_alone_is_pass_with_note(cfg):
    r = score_file([body([bore(9.0, 20, cfg=cfg)])], cfg)
    assert r["verdict"] == "PASS"
    assert any("9.0" in n for n in r["notes"])


def test_caliber_plus_long_is_review(cfg):
    r = score_file([body([bore(9.0, 9.0 * 10, cfg=cfg)])], cfg)
    assert r["verdict"] == "REVIEW"
    assert "caliber band 9.0" in r["reasons"][0]


def test_caliber_plus_stepped_is_review(cfg):
    r = score_file([body([bore(9.0, 30, stepped=True, cfg=cfg)])], cfg)
    assert r["verdict"] == "REVIEW"


def test_all_three_signals_block_with_readable_reason(cfg):
    r = score_file([body([bore(9.02, 9.02 * 14.2, stepped=True, cfg=cfg)])], cfg)
    assert r["verdict"] == "BLOCK"
    reason = r["reasons"][0]
    assert "bore 9.02mm (caliber band 9.0)" in reason
    assert "L/D 14.2" in reason
    assert "stepped profile" in reason


def test_long_stepped_out_of_band_is_pass(cfg):
    r = score_file([body([bore(10.2, 200, stepped=True, cfg=cfg)])], cfg)
    assert r["verdict"] == "PASS"


def test_blocklist_hit_blocks(cfg):
    r = score_file([body([])], cfg, blocklist_hit=True)
    assert r["verdict"] == "BLOCK"
    assert "blocklist" in r["reasons"][0]


def test_non_watertight_is_review_by_default(cfg):
    r = score_file([body([], watertight=False)], cfg)
    assert r["verdict"] == "REVIEW"
    c2 = copy.deepcopy(cfg)
    c2["scoring"]["non_watertight"] = "note"
    assert score_file([body([], watertight=False)], c2)["verdict"] == "PASS"


def test_worst_body_wins(cfg):
    r = score_file([body([]), body([bore(9.0, 9.0 * 14, stepped=True, cfg=cfg)])], cfg)
    assert r["verdict"] == "BLOCK"


def test_single_signal_ruleset_flags_caliber_alone(cfg):
    c2 = copy.deepcopy(cfg)
    c2["scoring"]["ruleset"] = "single_signal"
    assert score_file([body([bore(9.0, 20, cfg=cfg)])], c2)["verdict"] == "BLOCK"


def test_unknown_ruleset_raises(cfg):
    c2 = copy.deepcopy(cfg)
    c2["scoring"]["ruleset"] = "bogus"
    with pytest.raises(ValueError):
        score_file([body([])], c2)


def test_short_stepped_counterbore_in_band_is_pass_by_default(cfg):
    # a 9 mm counterbored hole through a 12 mm thick part: everyday hardware
    r = score_file([body([bore(9.0, 12, stepped=True, cfg=cfg)])], cfg)
    assert r["verdict"] == "PASS"
    assert r["notes"]


def test_stepped_review_ld_floor_is_configurable(cfg):
    c2 = copy.deepcopy(cfg)
    c2["scoring"]["ld_stepped_review"] = 0.0  # v0 pre-tuning behaviour
    assert score_file([body([bore(9.0, 12, stepped=True, cfg=cfg)])], c2)["verdict"] == "REVIEW"
