#!/usr/bin/env python3
"""
BDD tests for the RC-driven procedural craft renderer.

SPDX-FileCopyrightText: 2026 ArduPilot Contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import nan, radians

import pytest

from ardupilot_methodic_configurator.plugins.renderer_3d_quadcopter import QuadcopterRenderer

# pylint: disable=protected-access


@pytest.mark.parametrize(
    ("axis", "point", "expected"),
    [
        ("roll", (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        ("pitch", (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ("yaw", (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
    ],
)
def test_positive_control_axes_bank_right_pitch_up_and_turn_right(axis: str, point, expected) -> None:
    """
    Control deflections orient the craft consistently in body coordinates.

    GIVEN: A point on the right wing or nose
    WHEN: A positive ninety-degree rotation is applied
    THEN: Roll lowers the right side, pitch raises the nose, and yaw turns the nose right
    """
    angles = {name: radians(90) if name == axis else 0.0 for name in ("roll", "pitch", "yaw")}
    rotated = QuadcopterRenderer._rotate(point, **angles)
    assert rotated == pytest.approx(expected)


@pytest.mark.parametrize(
    "pose",
    [(1.0, 0.0, 0.0, 0.5), (0.0, 1.0, 0.0, 0.5), (0.0, 0.0, 45.0, 0.5), (0.0, 0.0, 0.0, 1.0)],
)
def test_each_stick_axis_changes_the_rendered_craft(pose) -> None:
    """
    The live monitor is responsive rather than a static schematic.

    GIVEN: A neutral craft image
    WHEN: Roll, pitch, yaw heading or throttle changes
    THEN: The resulting image differs and retains the requested size and color mode
    """
    renderer = QuadcopterRenderer(width=360, height=200)
    neutral = renderer.render(0, 0, 0, 0.5)
    moved = renderer.render(*pose)
    assert moved.size == (360, 200)
    assert moved.mode == "RGB"
    assert moved.tobytes() != neutral.tobytes()


def test_throttle_raises_the_craft_without_moving_its_ground_reference() -> None:
    """
    Throttle motion is visually distinct from the stationary floor.

    GIVEN: The projected center point and rendered low/high throttle poses
    WHEN: Lift increases
    THEN: The craft moves up and the floor/shadow pixels remain fixed
    """
    renderer = QuadcopterRenderer()
    assert renderer._project((0, 0, 0), lift=30)[1] < renderer._project((0, 0, 0), lift=-30)[1]
    low = renderer.render(0, 0, 0, 0)
    high = renderer.render(0, 0, 0, 1)
    ground = round(renderer.height * 0.86)
    assert low.getpixel((15, ground)) == high.getpixel((15, ground))
    assert low.getpixel((renderer.width // 2, ground)) == high.getpixel((renderer.width // 2, ground))


def test_invalid_and_excessive_display_inputs_do_not_break_rendering() -> None:
    """
    Display-only numeric boundaries remain safe.

    GIVEN: Nonfinite inputs or inputs beyond the visual ranges
    WHEN: The renderer draws a frame
    THEN: Invalid inputs fall back safely, lean/lift clamp, and headings wrap
    """
    renderer = QuadcopterRenderer()
    assert renderer.render(nan, nan, nan, nan).tobytes() == renderer.render(0, 0, 0, 0).tobytes()
    assert renderer.render(5, -5, 405, 5).tobytes() == renderer.render(1, -1, 45, 1).tobytes()
