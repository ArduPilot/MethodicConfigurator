"""
Business logic for the ESC RPM scale plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Erwan Billard

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import isfinite
from pathlib import Path

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

DEFAULT_HOBBYWING_6X_SE_SCALE = 0.714
SCRIPTING_PROTOCOL = "Scripting"
SCRIPT_FILENAME = "esc_rpm_scale.lua"
SCRIPT_REMOTE_PATH = f"/APM/Scripts/{SCRIPT_FILENAME}"

# Number of ESC outputs used when the frame layout cannot be resolved
# (no FRAME_CLASS parameter available, e.g. FC not connected). A quad is the
# most common ArduPilot frame, so it is the safest neutral fallback.
FALLBACK_ESC_OUTPUT_COUNT = 4


class EscRpmScaleDataModel:
    """Generate and upload an ArduPilot Lua ESC RPM scaling script."""

    def __init__(self, flight_controller: FlightController, filesystem: LocalFilesystem) -> None:
        self.flight_controller = flight_controller
        self.filesystem = filesystem
        self._motor_data_loader = FilesystemJSONWithSchema(
            json_filename="AP_Motors_test.json",
            schema_filename=str(Path("plugins", "AP_Motors_test_schema.json")),
        )

    @staticmethod
    def _normalized_product_value(value: object) -> str:
        """Normalize product metadata for a tolerant manufacturer/model match."""
        return " ".join(str(value or "").casefold().replace("-", " ").split())

    def is_hobbywing_6x_se(self) -> bool:
        """Return whether either the ESC or motor product identifies a Hobbywing 6X SE."""
        data = self.filesystem.vehicle_components_fs.data or {}
        components = data.get("Components", data)
        if not isinstance(components, dict):
            return False

        for component_name in ("ESC", "Motors"):
            component = components.get(component_name, {})
            product = component.get("Product", {}) if isinstance(component, dict) else {}
            if not isinstance(product, dict):
                continue
            manufacturer = self._normalized_product_value(product.get("Manufacturer"))
            model = self._normalized_product_value(product.get("Model"))
            if manufacturer == "hobbywing" and model in ("6x se", "6xse"):
                return True
        return False

    def is_scripting_telemetry_protocol(self) -> bool:
        """Return whether the selected ESC->FC telemetry protocol is Scripting."""
        data = self.filesystem.vehicle_components_fs.data or {}
        components = data.get("Components", data)
        if not isinstance(components, dict):
            return False

        esc = components.get("ESC", {})
        if not isinstance(esc, dict):
            return False

        esc_telemetry = esc.get("ESC->FC Telemetry", {})
        if not isinstance(esc_telemetry, dict):
            return False

        return str(esc_telemetry.get("Protocol") or "") == SCRIPTING_PROTOCOL

    @property
    def recommended_scale(self) -> float:
        """Return the known Hobbywing 6X SE scale, or a neutral scale otherwise."""
        return DEFAULT_HOBBYWING_6X_SE_SCALE if self.is_hobbywing_6x_se() else 1.0

    @staticmethod
    def esc_count_for_frame_class(frame_class: int, motor_data: dict) -> int | None:
        """
        Return the number of motors for ``frame_class`` from the motor layout data.

        The motor count is constant for a given frame class regardless of the
        frame type, so the first matching layout is authoritative.

        Args:
            frame_class: ArduPilot ``FRAME_CLASS`` parameter value.
            motor_data: Parsed ``AP_Motors_test.json`` content.

        Returns:
            The number of motors, or ``None`` when the class is unknown.

        """
        for layout in motor_data.get("layouts", []):
            if layout.get("Class") == frame_class and "motors" in layout:
                return len(layout["motors"])
        return None

    def esc_count(self) -> int:
        """
        Derive the number of ESC outputs from the ``FRAME_CLASS`` parameter.

        Falls back to :data:`FALLBACK_ESC_OUTPUT_COUNT` when the flight
        controller is not connected or the frame class cannot be resolved.
        """
        fc_parameters = self.flight_controller.fc_parameters or {}
        frame_class_raw = fc_parameters.get("FRAME_CLASS", fc_parameters.get("Q_FRAME_CLASS"))
        if frame_class_raw is None:
            return FALLBACK_ESC_OUTPUT_COUNT

        motor_data = self._motor_data_loader.load_json_data(str(Path(__file__).parent))
        count = self.esc_count_for_frame_class(int(frame_class_raw), motor_data or {})
        return count or FALLBACK_ESC_OUTPUT_COUNT

    @staticmethod
    def generate_script(scale_factor: float, esc_count: int) -> str:
        """Generate the Lua script for ESC indexes 0 through ``esc_count - 1``."""
        if not isfinite(scale_factor) or scale_factor <= 0:
            msg = _("RPM scale factor must be a finite positive number")
            raise ValueError(msg)
        if esc_count <= 0:
            msg = _("ESC output count must be positive")
            raise ValueError(msg)

        scale = format(scale_factor, ".6g")
        lines = [f"esc_telem:set_rpm_scale({index}, {scale})" for index in range(esc_count)]
        lines.append(f'gcs:send_text(0, "LUA set RPM scale to {scale}")')
        return "\n".join(lines) + "\n"

    def write_script(self, scale_factor: float) -> Path:
        """Generate the script inside the active vehicle directory."""
        vehicle_dir = Path(self.filesystem.vehicle_dir)
        if not self.filesystem.vehicle_dir or not vehicle_dir.is_dir():
            msg = _("Vehicle directory is not available")
            raise RuntimeError(msg)

        script_path = vehicle_dir / SCRIPT_FILENAME
        script_path.write_text(self.generate_script(scale_factor, self.esc_count()), encoding="utf-8")
        return script_path

    def generate_and_upload_script(self, scale_factor: float) -> bool:
        """Generate the local script and upload it to the FC with existing MAVFTP support."""
        if self.flight_controller.master is None:
            return False
        script_path = self.write_script(scale_factor)
        return bool(self.flight_controller.upload_file(str(script_path), SCRIPT_REMOTE_PATH, None))
