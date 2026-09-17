from __future__ import annotations

from dataclasses import replace

from attack.spoofing_attack import SpoofingAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver


class StaticAttack(SpoofingAttack):
    """Static-position spoofing: once active, replace the injected navigation
    position with a configured fixed coordinate.

    This models static-position substitution at the effect level; it does not
    claim a particular RF mechanism (it is not meaconing or replay). Velocity
    is left at the nominal value and quality/availability fields are unchanged.
    """

    ATTACK_TYPE = "static"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)
        self.static_lat = self.config["static_lat"]
        self.static_lon = self.config["static_lon"]
        self.static_alt = self.config["static_alt"]

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> GpsInputState:
        """Overwrite position with the configured static coordinate; velocity unchanged."""
        return replace(
            nominal,
            lat=self.static_lat,
            lon=self.static_lon,
            alt=self.static_alt,
        )
