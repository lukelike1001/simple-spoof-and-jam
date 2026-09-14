from __future__ import annotations

from attack.gps_attack import GpsAttack
from drone.gps_input_state import GpsInputState
from drone.gps_receiver import GpsReceiver


class JammingAttack(GpsAttack):
    """Withhold GPS_INPUT once altitude activation has fired (complete loss)."""

    ATTACK_TYPE = "jamming"

    def __init__(self, attack_type: str, spawn_location: str):
        super().__init__(attack_type, spawn_location)
        self._from_yaml(attack_type, spawn_location)

    def apply(
        self,
        nominal: GpsInputState,
        receiver: GpsReceiver,
        elapsed_seconds: float,
    ) -> GpsInputState | None:
        """Deliver no GPS input, so the MAV GPS backend loses lock."""
        return None
