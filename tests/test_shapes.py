import numpy as np
import pytest

from pce import shapes


def test_stepped_tube_is_watertight_with_expected_volume():
    m = shapes.stepped_tube([(100.0, 4.5, 6.0)], sections=128)
    assert m.is_watertight
    expected = np.pi * (6.0**2 - 4.5**2) * 100.0
    assert m.volume == pytest.approx(expected, rel=0.01)


def test_blind_segment_with_zero_inner_radius_is_watertight():
    m = shapes.stepped_tube([(10.0, 0.0, 8.0), (40.0, 6.0, 8.0)])
    assert m.is_watertight
    assert m.volume > 0


def test_plate_with_holes_is_watertight(hole_plate):
    assert hole_plate.is_watertight
    assert hole_plate.extents == pytest.approx([60, 40, 3])


def test_control_block_is_abstract_box_with_through_hole(control_block):
    assert control_block.is_watertight
    # a plain rectangular block: its bounding box volume is close to its convex hull volume
    assert control_block.convex_hull.volume == pytest.approx(np.prod(control_block.extents), rel=0.01)
