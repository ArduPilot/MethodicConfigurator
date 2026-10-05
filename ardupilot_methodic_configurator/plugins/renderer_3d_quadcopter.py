"""
Dependency-free, projected 3D quadcopter preview rendered with Pillow.

This module provides a class to render a simple schematic quadcopter image
based on roll, pitch, yaw, and throttle inputs.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator
SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from math import cos, isfinite, radians, sin

from PIL import Image, ImageDraw

Point3D = tuple[float, float, float]
Point2D = tuple[float, float]


class QuadcopterRenderer:  # pylint: disable=too-few-public-methods
    """Render a stylized Quad-X from a low rear chase view; not a flight simulator."""

    def __init__(self, width: int = 400, height: int = 200) -> None:
        self.width = width
        self.height = height

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        """Keep display inputs finite and within their documented visual range."""
        return max(minimum, min(maximum, value)) if isfinite(value) else 0.0

    @staticmethod
    def _rotate(point: Point3D, roll: float, pitch: float, yaw: float) -> Point3D:
        """Rotate body coordinates (right, forward, up): positive roll right, pitch nose up, yaw right."""
        x, y, z = point
        x, z = x * cos(roll) + z * sin(roll), -x * sin(roll) + z * cos(roll)
        y, z = y * cos(pitch) - z * sin(pitch), y * sin(pitch) + z * cos(pitch)
        return x * cos(yaw) + y * sin(yaw), -x * sin(yaw) + y * cos(yaw), z

    def _project(self, point: Point3D, lift: float) -> Point2D:
        """Project from behind and 17 degrees above the craft with a mild perspective."""
        x, y, z = point
        elevation = radians(17)
        depth = y * cos(elevation) - z * sin(elevation)
        scale = min(self.width / 6.5, self.height / 3.8) * 7 / (7 + depth)
        return self.width / 2 + x * scale, self.height * 0.53 + (y * sin(elevation) - z * cos(elevation)) * scale - lift

    @staticmethod
    def _box_faces(center: Point3D, size: Point3D) -> list[list[Point3D]]:
        """Build the six faces of a rectangular body or flight-controller stack."""
        x, y, z = center
        dx, dy, dz = (side / 2 for side in size)
        corners = [
            (x - dx, y - dy, z - dz),
            (x + dx, y - dy, z - dz),
            (x + dx, y + dy, z - dz),
            (x - dx, y + dy, z - dz),
            (x - dx, y - dy, z + dz),
            (x + dx, y - dy, z + dz),
            (x + dx, y + dy, z + dz),
            (x - dx, y + dy, z + dz),
        ]
        return [
            [corners[index] for index in face]
            for face in ((0, 1, 2, 3), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7))
        ]

    @staticmethod
    def _craft_surfaces() -> list[tuple[Sequence[Point3D], str]]:
        """Construct independent procedural Quad-X geometry without external meshes or assets."""
        geometry: list[tuple[Sequence[Point3D], str]] = []

        def add_surface(points: Sequence[Point3D], color: str) -> None:
            geometry.append((points, color))

        for x, y in ((-1.25, 1.1), (1.25, 1.1), (-1.25, -1.1), (1.25, -1.1)):
            add_surface([(0, 0, -0.06), (x, y, -0.06), (x, y, 0.06), (0, 0, 0.06)], "#46576a")
            accent = "#ff815f" if y > 0 else "#61dafb"
            add_surface(
                [(x + 0.48 * cos(radians(angle)), y + 0.48 * sin(radians(angle)), 0.16) for angle in range(0, 360, 15)], accent
            )
            add_surface(
                [(x + 0.38 * cos(radians(angle)), y + 0.38 * sin(radians(angle)), 0.17) for angle in range(0, 360, 15)],
                "#182536",
            )
            add_surface(
                [(x - 0.4, y - 0.07, 0.19), (x + 0.4, y - 0.07, 0.19), (x + 0.4, y + 0.07, 0.19), (x - 0.4, y + 0.07, 0.19)],
                accent,
            )
        for center, size, color in (
            ((0, 0, 0), (0.9, 1.1, 0.22), "#d8e3f3"),
            ((0, -0.05, 0.18), (0.65, 0.75, 0.12), "#29384a"),
            ((0, 0, 0.3), (0.3, 0.35, 0.1), "#61dafb"),
        ):
            for face in QuadcopterRenderer._box_faces(center, size):
                add_surface(face, color)
        add_surface([(-0.2, 0.55, 0.14), (0.2, 0.55, 0.14), (0, 0.95, 0.14)], "#ff815f")
        return geometry

    def render(self, roll: float, pitch: float, yaw: float, throttle: float) -> Image.Image:
        """
        Renders the quadcopter based on inputs.

        Args:
            roll: Normalised roll input (-1.0 to 1.0).
            pitch: Normalised pitch input (-1.0 to 1.0).
            yaw: Accumulated preview heading in degrees (not a yaw stick deflection).
            throttle: Throttle lift (0.0 to 1.0), from bottom to top of the preview.

        Returns:
            PIL.Image: The rendered frame.

        """
        angles = (
            radians(self._clamp(roll, -1, 1) * 35),
            radians(self._clamp(pitch, -1, 1) * 35),
            radians(yaw % 360 if isfinite(yaw) else 0),
        )
        lift = (self._clamp(throttle, 0, 1) - 0.5) * self.height * 0.3
        image = Image.new("RGB", (self.width, self.height), "#101a29")
        draw = ImageDraw.Draw(image)
        # Fixed floor/shadow makes throttle lift easy to see without suggesting actual altitude.
        floor = round(self.height * 0.86)
        draw.line((12, floor, self.width - 12, floor), fill="#29384a")
        draw.ellipse((self.width * 0.31, floor - 5, self.width * 0.69, floor + 5), fill="#080e18")
        surfaces: list[tuple[float, list[Point2D], str]] = []

        def add_surface(points: Sequence[Point3D], color: str) -> None:
            rotated = [self._rotate(point, *angles) for point in points]
            depth = sum(point[1] * cos(radians(17)) - point[2] * sin(radians(17)) for point in rotated) / len(rotated)
            surfaces.append((depth, [self._project(point, lift) for point in rotated], color))

        for points, color in self._craft_surfaces():
            add_surface(points, color)
        for surface in sorted(surfaces, key=lambda surface: surface[0], reverse=True):
            draw.polygon(surface[1], fill=surface[2], outline="#0a111c")
        return image
