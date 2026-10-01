"""Shared fixtures. Every mesh here is an innocent primitive or the abstract control block."""
import numpy as np
from pytest import fixture
import trimesh

from pce import shapes
from pce.config import load_config


@fixture
def cfg():
    return load_config(None)


@fixture
def tube_9mm():
    # plain 9.0 mm ID straw-like tube, 100 mm long, 1.5 mm wall
    return shapes.stepped_tube([(100.0, 4.5, 6.0)])


@fixture
def stepped_spacer():
    # counterbored spacer: 20 mm of 12 mm ID, then 30 mm of 6 mm ID, OD 20
    return shapes.stepped_tube([(20.0, 6.0, 10.0), (30.0, 3.0, 10.0)])


@fixture
def solid_rod():
    return trimesh.creation.cylinder(radius=4.0, height=80.0, sections=48)


@fixture
def hole_plate():
    return shapes.plate_with_holes(60.0, 40.0, 3.0, [(-20, -10), (20, -10), (-20, 10), (20, 10)], 5.0)


@fixture
def control_block():
    return shapes.control_abstract_bore_block()


@fixture
def open_mesh():
    m = trimesh.creation.box((10, 10, 10))
    m.update_faces(np.arange(len(m.faces)) != 0)  # drop one face -> not watertight
    return m
