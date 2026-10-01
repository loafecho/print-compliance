import pytest

from pce.config import ConfigError, load_config


def test_defaults_have_generic_caliber_bands():
    c = load_config(None)
    assert c["caliber_bands"]["nominal_mm"] == [5.56, 7.62, 9.0, 11.43]
    assert c["scoring"]["ruleset"] == "combination"


def test_partial_override_deep_merges(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("scoring:\n  ld_review: 20\n")
    c = load_config(p)
    assert c["scoring"]["ld_review"] == 20
    assert c["scoring"]["ld_block"] == load_config(None)["scoring"]["ld_block"]


def test_unknown_key_rejected(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("scorng:\n  x: 1\n")
    with pytest.raises(ConfigError):
        load_config(p)
