from __future__ import annotations

import math
from pathlib import Path

import yaml

from drone.gps_receiver import GpsReceiver

PRESET_DIR = Path(__file__).parent / "presets"


class GpsAttack:
    """Shared YAML loading and altitude-triggered activation for spoofing and jamming."""

    config = None

    def __init__(self, attack_type: str, spawn_location: str):
        self.reached_time = math.inf
        self.activated_at = math.inf

    def _from_yaml(self, attack_type: str, spawn_location: str) -> None:
        config_path = PRESET_DIR / f"{attack_type}.yaml"
        with config_path.open() as file:
            attack_config = yaml.safe_load(file)
        self.config = attack_config[spawn_location]

    def check_activation_altitude(
        self, gps_receiver: GpsReceiver, elapsed_seconds: float
    ) -> bool:
        """True once the vehicle has been at activation_alt long enough.

        If the preset has no activation_alt, the attack is active immediately
        (needed so passthrough still works).
        """
        if not self.config or "activation_alt" not in self.config:
            return True

        _, _, alt = gps_receiver.get_position()
        tolerance = self.config.get("activation_alt_tolerance", 1.0)
        delay = self.config.get("activation_delay_seconds", 0.0)

        if abs(alt - self.config["activation_alt"]) < tolerance:
            if self.reached_time == math.inf:
                print(
                    f"Activation altitude reached. Attack starts in {delay} seconds."
                )
                self.reached_time = elapsed_seconds

        if elapsed_seconds - self.reached_time >= delay:
            if self.activated_at == math.inf:
                self.activated_at = elapsed_seconds
                print("Attack active.")
            return True
        return False

    def seconds_since_activation(self, elapsed_seconds: float) -> float:
        if self.activated_at == math.inf:
            return elapsed_seconds
        return elapsed_seconds - self.activated_at
