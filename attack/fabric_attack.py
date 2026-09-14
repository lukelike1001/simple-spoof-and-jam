from __future__ import annotations

from dataclasses import replace

from attack.spoofing_attack import SpoofingAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver


class FabricAttack(SpoofingAttack):
    """Hold the reported position at a fixed fabricated coordinate once active."""

    ATTACK_TYPE = "fabric"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
        self.fabric_lat = self.config["fabric_lat"]
        self.fabric_lon = self.config["fabric_lon"]
        self.fabric_alt = self.config["fabric_alt"]

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> GpsInputState:
        """Overwrite position with the fabricated coordinate; velocity unchanged."""
        return replace(
            nominal,
            lat=self.fabric_lat,
            lon=self.fabric_lon,
            alt=self.fabric_alt,
        )
