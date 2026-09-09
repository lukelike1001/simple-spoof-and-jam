from __future__ import annotations

from abc import ABC, abstractmethod
from drone.gps_receiver import GpsReceiver
from pathlib import Path
import yaml

PRESET_DIR = Path(__file__).parent / "presets"

class SpoofingAttack(ABC):
    """Abstract GPS spoofing attack class intended for extension"""
    config = None

    def _from_yaml(self, attack_type: str, spawn_location: str) -> None:
        config_path = PRESET_DIR / f"{attack_type}.yaml"
        with config_path.open() as file:
            attack_config = yaml.safe_load(file)
        self.config = attack_config[spawn_location]

    @abstractmethod
    def compute_spoofed_position(self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Given a drone and the elapsed time, calculate the new spoofed location."""

    @abstractmethod
    def compute_spoofed_velocity(self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> tuple[float, float, float]:
        """Given a drone and the elapsed time, calculate the new spoofed velocity (NED)."""
